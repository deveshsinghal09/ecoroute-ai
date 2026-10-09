"""Contract, isolation and end-to-end mechanics; no live AWS claim from fixtures."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ecoroute.config import Settings
from ecoroute.main import create_app
from scripts.demo_backend import run_demo
from scripts.export_api import export
from scripts.manage_cloud import guard_identity, main as cloud_main
from scripts.security_review import review


def validator(spec, schema):
    return Draft202012Validator({"components": spec["components"], **schema})


def test_runtime_export_and_all_response_schemas(tmp_path):
    spec, collection = export(tmp_path)
    app = create_app(Settings(_env_file=None, local_db_path=":memory:"))
    assert spec == app.openapi()
    app.state.store.db.close()
    operations = [(p, m, op) for p, ops in spec["paths"].items() for m, op in ops.items()]
    assert len(operations) == len(collection["item"]) == 42
    for definition in spec["components"]["schemas"].values():
        Draft202012Validator.check_schema(definition)
    for _, _, operation in operations:
        for response in operation["responses"].values():
            schema = response.get("content", {}).get("application/json", {}).get("schema", {})
            assert schema  # no undocumented {} success or default validation envelopes
    environment = json.loads((tmp_path / "examples/ecoroute.postman_environment.json").read_text())
    assert next(v for v in environment["values"] if v["key"] == "access_token")["value"] == ""
    assert all("AWS_SECRET_ACCESS_KEY" not in json.dumps(item) for item in collection["item"])


def test_every_protected_endpoint_requires_auth_and_write_scope(secured):
    spec = secured.app.openapi()
    for path, operations in spec["paths"].items():
        for method, op in operations.items():
            if not op.get("security"):
                continue
            actual_path = path
            for param in op.get("parameters", []):
                if param["in"] == "path":
                    actual_path = actual_path.replace("{" + param["name"] + "}", "a" * 32)
            result = secured.client.request(method, actual_path)
            assert result.status_code == 401, (method, path, result.text)
            validator(spec, op["responses"]["401"]["content"]["application/json"]["schema"]).validate(result.json())
            if method != "get":
                result = secured.client.request(method, actual_path, headers={"Authorization": "Bearer " + secured.token(scope="ecoroute/read")})
                assert result.status_code == 403, (method, path)


def test_log_and_error_do_not_echo_secrets_or_location(secured, caplog):
    marker = "SECRET_LOCATION_MARKER_DO_NOT_LOG"
    token = secured.token()
    response = secured.client.post("/api/v1/routes/compare", json={"origin": marker}, headers={"Authorization": "Bearer " + token})
    assert response.status_code == 422
    assert marker not in response.text + caplog.text and token not in caplog.text


def test_integrated_demo_missing_data_is_explicit_and_synthetic_is_isolated(tmp_path, monkeypatch):
    from ecoroute.environment.pipeline import repository
    repository.cache_clear()
    monkeypatch.setenv("ENVIRONMENT_LOCAL_PATH", str(tmp_path))
    report = run_demo(tmp_path)
    assert report["arithmetic_verified"] and report["comparison"]["candidate_count"] == 2
    assert all(r["estimated_pm25_exposure_ug_h_m3"] is None for r in report["comparison"]["routes"])
    assert report["wearable"]["synthetic"] and report["wearable"]["revocation_verified"]
    assert report["explanation"]["mode"] == "deterministic"
    assert report["alert"]["created"] and report["alert"]["synthetic_test_only"]
    assert report["alert"]["notification"]["delivered"] is False
    assert not list(Path(tmp_path).rglob("*.parquet"))
    app = create_app(Settings(_env_file=None, local_db_path=":memory:"))
    spec = app.openapi()
    validator(spec, {"$ref": "#/components/schemas/RouteComparison"}).validate(report["comparison"])
    validator(spec, {"$ref": "#/components/schemas/Explanation"}).validate(report["explanation"])
    app.state.store.db.close()
    repository.cache_clear()


def test_real_shape_route_responses_and_missing_errors(secured, tmp_path):
    from ecoroute.routing.api import service
    from ecoroute.environment.repository import LocalRepository
    from ecoroute.routing.service import RouteService
    from scripts.demo_routes import RecordedDelhi
    repo = LocalRepository(tmp_path)
    engine = RouteService(RecordedDelhi(), secured.store, repo)
    secured.app.dependency_overrides[service] = lambda: engine
    spec = secured.app.openapi()
    auth = {"Authorization": "Bearer " + secured.token()}
    body = {"origin": {"longitude": 77.2295, "latitude": 28.6129}, "destination": {"longitude": 77.2167, "latitude": 28.6315},
            "departure_at": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(), "mode": "driving", "consent_to_store": True}
    result = secured.client.post("/api/v1/routes/compare", headers=auth, json=body)
    assert result.status_code == 200
    validator(spec, {"$ref": "#/components/schemas/RouteComparison"}).validate(result.json())
    identifier = result.json()["selected_route_id"]
    for path, method, body in (("/api/v1/routes/" + identifier, "get", None),
        ("/api/v1/routes/" + identifier + "/segments", "get", None),
        ("/api/v1/routes/exposure", "post", {"route_id": identifier})):
        result = secured.client.request(method, path, headers=auth, json=body)
        assert result.status_code == 200
        schema_path = path.replace(identifier, "{route_id}")
        schema = spec["paths"][schema_path][method]["responses"]["200"]["content"]["application/json"]["schema"]
        validator(spec, schema).validate(result.json())
    denied = secured.client.get("/api/v1/routes/" + identifier, headers={"Authorization": "Bearer " + secured.token(sub="bob")})
    assert denied.status_code == 404
    repo.db.close()


@pytest.mark.parametrize("identity", [{"Account": "other", "Arn": "arn:aws:iam::other:user/user"}, {"Account": "123", "Arn": "arn:aws:iam::123:root"}])
def test_cloud_identity_guard(identity):
    with pytest.raises(ValueError):
        guard_identity(identity, "123")


def test_cloud_default_plan_never_calls_aws(monkeypatch):
    import os
    before = dict(os.environ)
    monkeypatch.setattr("scripts.manage_cloud.boto3.Session", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected AWS action")))
    assert cloud_main(["plan"]) == 0
    assert cloud_main(["deploy"]) == 0
    with pytest.raises(SystemExit):
        cloud_main(["deploy", "--apply"])
    assert dict(os.environ) == before


def test_structural_review_detects_public_storage_active_schedule_and_broad_iam():
    bad = {"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}, "Schedule": {"Type": "AWS::Scheduler::Schedule", "Properties": {"State": "ENABLED"}},
        "Policy": {"Type": "AWS::IAM::Policy", "Properties": {"PolicyDocument": {"Statement": [{"Effect": "Allow", "Action": "sns:*", "Resource": "*"}]}}}}}
    assert len(review(bad)["issues"]) == 4


def test_benchmark_arithmetic_detects_seconds_hours_error():
    from scripts.benchmark_routes import verify_arithmetic
    route = {"duration_s": 3600, "estimated_pm25_exposure_ug_h_m3": 30,
             "segments": [{"duration_s": 3600, "pollutants": {"pm25": {"value_ug_m3": 30}}, "pm25_exposure_ug_h_m3": 30}]}
    assert verify_arithmetic(route)
    route["segments"][0]["pm25_exposure_ug_h_m3"] = 30 * 3600
    with pytest.raises(AssertionError):
        verify_arithmetic(route)
