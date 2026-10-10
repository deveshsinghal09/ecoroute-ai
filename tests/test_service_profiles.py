import io
import json
from datetime import datetime, UTC

import httpx
import pytest
from fastapi.testclient import TestClient

from infra.profiles import DeploymentOptions
from ecoroute.analytics import AuroraAnalytics, SqliteAnalytics, ingest_report, process_records
from ecoroute.edge import create_edge


def report():
    return {"city": "Delhi", "date": datetime.now(UTC).date().isoformat(),
            "mode": "walking", "provider": "osrm", "candidate_count": 1, "engine_version": "routing-v1",
            "metrics": [{"duration_s": 1800, "distance_m": 2200, "pm25_exposure_ug_h_m3": 15,
                         "coverage_fraction": 1}]}


def test_default_configuration_does_not_enable_idle_services():
    plan = DeploymentOptions().plan()
    assert plan["paid_options_enabled"] == [] and not plan["aws_calls"]
    assert plan["nat_gateways"] == 0 and not plan["training_started"]


@pytest.mark.parametrize("configuration", [
    {"runtime": "eks"}, {"runtime": "ec2"}, {"analytics": "rds"},
    {"runtime": "apprunner", "image_uri": "123456789012.dkr.ecr.ap-south-1.amazonaws.com/backend@sha256:" + "a" * 64},
    {"backend_origin": "http://example.org"}, {"hosting": "cloudfront", "domain_name": "example.org"},
    {"AWS_SECRET_ACCESS_KEY": "do-not-put-secrets-in-deployment-json"},
])
def test_missing_and_unsafe_profile_configuration_fails_closed(configuration):
    with pytest.raises(ValueError):
        DeploymentOptions.model_validate(configuration)


def test_sql_report_deduplication_and_retention(tmp_path):
    sink = SqliteAnalytics(tmp_path / "analytics.db")
    value = report()
    key = f"reports/routes/date={value['date']}/request.json"
    raw = json.dumps(value).encode()
    first = ingest_report(raw, key, sink)
    assert ingest_report(raw, key, sink) == first
    assert sink.connection.execute("SELECT count(*) FROM route_reports").fetchone()[0] == 1
    sink.prune("2100-01-01")
    assert sink.connection.execute("SELECT count(*) FROM route_reports").fetchone()[0] == 0
    sink.close()


@pytest.mark.parametrize("change", [
    {"owner_id": "must-not-retain-personal-data"}, {"geometry": {"coordinates": []}},
    {"provider": "google_routes"}, {"candidate_count": 2}, {"date": "2000-01-01"},
    {"metrics": [{"duration_s": 10, "distance_m": 20, "pm25_exposure_ug_h_m3": float("nan"), "coverage_fraction": 1}]},
])
def test_sql_rejects_personal_invalid_and_restricted_data(tmp_path, change):
    sink = SqliteAnalytics(tmp_path / "a.db")
    value = {**report(), **change}
    with pytest.raises(ValueError):
        ingest_report(json.dumps(value).encode(), f"reports/routes/date={value['date']}/id.json", sink)
    assert sink.connection.execute("SELECT count(*) FROM route_reports").fetchone()[0] == 0
    sink.close()


def test_sql_partial_batch_failure_is_retryable_and_logs_no_payload(tmp_path, capsys):
    class S3:
        def get_object(self, **kwargs):
            return {"Body": io.BytesIO(json.dumps(report()).encode())}
    sink = SqliteAnalytics(tmp_path / "a.db")
    key = f"reports/routes/date={report()['date']}/id.json"
    event = {"Records": [{"messageId": "valid", "body": json.dumps({"Records": [{"s3": {"bucket": {"name": "expected"}, "object": {"key": key}}}]})},
                         {"messageId": "bad", "body": "password=secret-invalid-json"}]}
    assert process_records(event, S3(), sink, "expected") == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert "password" not in capsys.readouterr().out
    sink.close()


def test_aurora_uses_bound_parameters_and_date_hint():
    calls = []
    class Client:
        def execute_statement(self, **kwargs):
            calls.append(kwargs)
    sink = AuroraAnalytics(Client(), "cluster", "secret")
    sink.insert({"id": "a", "day": "2026-10-10", "mode": "walking", "provider": "osrm", "count": 1, "payload": "{}"})
    assert calls[0]["secretArn"] == "secret" and ":payload" in calls[0]["sql"]
    assert next(p for p in calls[0]["parameters"] if p["name"] == "day")["typeHint"] == "DATE"


def test_proxy_preserves_authentication_but_never_cookies():
    seen = []
    def upstream(request):
        seen.append(request)
        return httpx.Response(401, json={"error": "invalid_token"})
    client = TestClient(create_edge("https://api.example.org", httpx.MockTransport(upstream)))
    assert client.get("/healthz").status_code == 200
    assert client.get("/api/v1/wearables/latest").status_code == 401 and not seen
    result = client.get("/api/v1/wearables/latest", headers={"Authorization": "Bearer invalid", "Cookie": "private=session"})
    assert result.status_code == 401
    assert seen[0].headers["Authorization"] == "Bearer invalid" and "cookie" not in seen[0].headers
    assert result.headers["cache-control"] == "no-store"


def test_proxy_outage_and_body_limit():
    def upstream(request):
        raise httpx.ConnectError("do not expose provider detail", request=request)
    client = TestClient(create_edge("https://api.example.org", httpx.MockTransport(upstream)))
    response = client.get("/api/v1/ready", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 502 and "provider" not in response.text
    assert client.post("/api/v1/trips", content=b"a" * 262145, headers={"Authorization": "Bearer invalid"}).status_code == 413


def test_offline_publisher_plan_never_authenticates(monkeypatch, capsys):
    from scripts.publish_frontend import main
    monkeypatch.setattr("scripts.publish_frontend.boto3.Session", lambda **kwargs: (_ for _ in ()).throw(AssertionError("AWS action")))
    assert main(["--target", "cloudfront"]) == 0
    assert json.loads(capsys.readouterr().out)["apply"] is False
    with pytest.raises(SystemExit):
        main(["--target", "amplify", "--apply"])


def test_amplify_upload_failure_never_prints_temporary_credential(tmp_path):
    from scripts.publish_frontend import upload_zip
    bundle = tmp_path / "frontend.zip"
    bundle.write_bytes(b"offline-fixture-only")
    url = "https://example.org/upload?temporary_secret=DO_NOT_PRINT_TEST_MARKER"
    with pytest.raises(SystemExit) as error:
        upload_zip(bundle, url, httpx.MockTransport(lambda request: httpx.Response(403)))
    assert "DO_NOT_PRINT" not in str(error.value)
    def outage(request):
        raise httpx.ConnectError(url, request=request)
    with pytest.raises(SystemExit) as error:
        upload_zip(bundle, url, httpx.MockTransport(outage))
    assert "DO_NOT_PRINT" not in str(error.value) and error.value.__suppress_context__


def test_kubernetes_manifest_is_nonroot_private_and_resource_bounded():
    from scripts.render_eks import manifest
    result = manifest({"BackendImage": "image@sha256:" + "a" * 64,
                       "BackendEnvironment": json.dumps({"ECOROUTE_PROFILE": "aws", "COGNITO_CLIENT_ID": "public-id"})})
    deployment = next(i for i in result["items"] if i["kind"] == "Deployment")
    service = next(i for i in result["items"] if i["kind"] == "Service")
    pod = deployment["spec"]["template"]["spec"]
    assert service["spec"]["type"] == "ClusterIP" and pod["securityContext"]["runAsNonRoot"]
    assert pod["containers"][0]["securityContext"]["readOnlyRootFilesystem"]
    assert pod["containers"][0]["resources"]["limits"]["memory"] == "512Mi"


def test_real_route_engine_report_contract_enters_sql_without_personal_data(secured, tmp_path):
    from datetime import timedelta
    from ecoroute.environment.repository import LocalRepository
    from ecoroute.routing.api import service
    from ecoroute.routing.service import RouteService
    from scripts.demo_routes import RecordedDelhi
    repo = LocalRepository(tmp_path / "objects")
    engine = RouteService(RecordedDelhi(), secured.store, repo)
    secured.app.dependency_overrides[service] = lambda: engine
    body = {"origin": {"longitude": 77.2295, "latitude": 28.6129},
            "destination": {"longitude": 77.2167, "latitude": 28.6315}, "mode": "driving",
            "departure_at": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(), "consent_to_store": True}
    response = secured.client.post("/api/v1/routes/compare", headers={"Authorization": "Bearer " + secured.token()}, json=body)
    assert response.status_code == 200
    files = list((tmp_path / "objects").rglob("reports/routes/**/*.json"))
    assert len(files) == 1
    key = files[0].relative_to(repo.root).as_posix()
    sink = SqliteAnalytics(tmp_path / "a.db")
    ingest_report(files[0].read_bytes(), key, sink)
    stored = sink.connection.execute("SELECT report_json FROM route_reports").fetchone()[0]
    assert "longitude" not in stored and "route_id" not in stored and "owner" not in stored
    assert json.loads(stored)["metrics"][0]["pm25_exposure_ug_h_m3"] is None
    sink.close()
