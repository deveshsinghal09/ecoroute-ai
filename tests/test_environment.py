"""Synthetic contract fixtures only; live observations are never invented by the app."""
import copy
import io
import json
from datetime import UTC, datetime, timedelta

import httpx
import pyarrow.parquet as pq
import pytest

from ecoroute.environment.api import read_rows
from ecoroute.environment.pipeline import ingest, repository
from ecoroute.environment.providers import JsonTransport, MissingCredential, OpenAQ, OpenMeteo, ProviderError, SchemaChanged, VARIABLES
from ecoroute.environment.repository import BudgetExceeded, LocalRepository, curate, save_raw
from ecoroute.environment.schema import normalized
from ecoroute.handlers.ingestion import clean


@pytest.fixture
def raw():
    clock = datetime.now(UTC).replace(microsecond=0)
    times = [int((clock + timedelta(hours=i)).timestamp()) for i in (-1, 1)]
    return {"schema_version": 1, "source": "open_meteo", "collected_at": clock.isoformat(),
            "request": {}, "historical": False, "attribution": "SYNTHETIC TEST FIXTURE", "license": "test",
            "payload": {"latitude": 28.6, "longitude": 77.2, "utc_offset_seconds": 0,
                        "hourly_units": {v: "µg/m³" for v in VARIABLES},
                        "hourly": {"time": times, **{v: [12.0, None] for v in VARIABLES}}}}


@pytest.fixture
def repo(tmp_path):
    return LocalRepository(tmp_path / "data")


@pytest.mark.parametrize("value,unit,expected,flag", [
    (1.2, "mg/m³", 1200, None), (0, "ug/m3", 0, None),
    (None, "ug/m3", None, "missing"), (-1, "ug/m3", None, "negative_concentration"),
    (float("nan"), "ug/m3", None, "non_finite"), (12, "ppm", None, "unsupported_unit"),
    (100001, "ug/m3", None, "implausible_concentration")])
def test_units_are_explicit(value, unit, expected, flag):
    result, flags = normalized(value, unit)
    assert result == expected
    assert flags == ([flag] if flag else [])


def test_forecast_provenance_and_gaps(raw):
    rows = OpenMeteo().clean(raw)
    assert len(rows) == 8
    assert {r.kind for r in rows} == {"modeled", "forecast"}
    assert all(r.resolution_km == 45 and r.model_run_at is None for r in rows)
    assert sum(r.value is None for r in rows) == 4
    assert all(r.kind != "observed" for r in rows)


@pytest.mark.parametrize("change", ["missing", "length", "timezone", "coordinate", "value_type"])
def test_schema_changes_fail_closed(raw, change):
    if change == "missing":
        del raw["payload"]["hourly"]["pm10"]
    elif change == "length":
        raw["payload"]["hourly"]["pm10"] = []
    elif change == "timezone":
        raw["payload"]["utc_offset_seconds"] = 3600
    elif change == "coordinate":
        raw["payload"]["latitude"] = 200
    else:
        raw["payload"]["hourly"]["pm10"][0] = "unknown"
    with pytest.raises(SchemaChanged):
        OpenMeteo().clean(raw)


@pytest.mark.parametrize("status,attempts,error", [(401, 1, MissingCredential), (429, 1, ProviderError), (503, 3, ProviderError)])
def test_outages_are_bounded_and_redacted(status, attempts, error):
    calls = []
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, text="secret-server-message")))
    transport = JsonTransport(client, reserve=lambda: calls.append(1), sleep=lambda _: None)
    with pytest.raises(error) as raised:
        transport.get("https://example.invalid?apikey=secret", headers={"X-API-Key": "secret"})
    assert len(calls) == attempts
    assert "secret" not in str(raised.value)


def test_network_and_invalid_json():
    def broken(request):
        raise httpx.ConnectError("private endpoint detail", request=request)
    transport = JsonTransport(httpx.Client(transport=httpx.MockTransport(broken)), sleep=lambda _: None)
    with pytest.raises(ProviderError, match="network_unavailable"):
        transport.get("https://example.invalid")
    transport = JsonTransport(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="bad"))), sleep=lambda _: None)
    with pytest.raises(SchemaChanged):
        transport.get("https://example.invalid")


def test_grid_cache_raw_replay_and_parquet(raw, repo, monkeypatch):
    monkeypatch.delenv("OPEN_METEO_API_KEY", raising=False)
    monkeypatch.setenv("ECOROUTE_PROFILE", "local")
    requests = []
    def response(request):
        requests.append(request)
        return httpx.Response(200, json=raw["payload"])
    transport = JsonTransport(httpx.Client(transport=httpx.MockTransport(response)), sleep=lambda _: None)
    key, cached = ingest("open_meteo", {"latitude": 28.61, "longitude": 77.21}, repo, transport=transport)
    key2, cached2 = ingest("open_meteo", {"latitude": 28.62, "longitude": 77.22}, repo, transport=transport)
    assert key == key2 and not cached and cached2 and len(requests) == 1
    report = curate(repo, key)
    assert curate(repo, key) == report
    assert report["records"] == 8 and report["missing_or_rejected"] == 4
    rows = [row for k in report["curated_keys"] for row in pq.read_table(io.BytesIO(repo.get_bytes(k))).to_pylist()]
    assert len(rows) == 8 and all(r["raw_key"] == key for r in rows)
    assert len(repo.query("QUALITY#open_meteo")[0]) == 1


def test_request_budget_and_missing_credentials(repo, monkeypatch):
    repo.reserve("open_meteo", daily=1)
    with pytest.raises(BudgetExceeded):
        repo.reserve("open_meteo", daily=1)
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    monkeypatch.setenv("ECOROUTE_PROFILE", "local")
    with pytest.raises(MissingCredential):
        ingest("openaq", {}, repo)


def test_open_aq_observations_and_original_units():
    raw = {"source": "openaq", "collected_at": "2026-10-08T12:00:00Z", "attribution": "SYNTHETIC",
           "request": {"sensor_id": 5}, "station": {"id": 9, "coordinates": {"latitude": 28.6, "longitude": 77.2}, "licenses": []},
           "payload": {"results": [{"value": 0.03, "parameter": {"name": "no2", "units": "ppm"},
                                    "coordinates": None, "period": {"datetimeFrom": {"utc": "2026-10-08T03:00:00Z"},
                                                                      "datetimeTo": {"utc": "2026-10-08T04:00:00Z"}}}]}}
    row = OpenAQ("fixture-only").clean(raw)[0]
    assert row.kind == "observed" and row.value is None and row.original_value == 0.03
    assert set(row.quality_flags) == {"unsupported_unit", "stale_at_collection"}
    assert row.provider_quality == '"not_supplied"'
    later = copy.deepcopy(raw)
    later["collected_at"] = "2026-10-08T13:00:00Z"
    assert OpenAQ("fixture-only").clean(later)[0].record_id == row.record_id


def test_clean_partial_batch_and_replay(raw, repo):
    key = save_raw(repo, raw)
    body = {"Records": [{"eventSource": "aws:s3", "s3": {"object": {"key": key}}}]}
    event = {"Records": [{"messageId": "ok", "body": json.dumps(body)}, {"messageId": "bad", "body": "invalid"}]}
    assert clean(event, None, repo=repo) == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert clean(event, None, repo=repo) == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert len(repo.query("QUALITY#open_meteo")[0]) == 1


def test_clean_rejects_unrelated_raw_objects(repo):
    body = {"Records": [{"eventSource": "aws:s3", "s3": {"object": {"key": "raw/untrusted.json"}}}]}
    event = {"Records": [{"messageId": "unrelated", "body": json.dumps(body)}]}
    assert clean(event, None, repo=repo) == {"batchItemFailures": [{"itemIdentifier": "unrelated"}]}
    assert repo.query("QUALITY#open_meteo")[0] == []


def test_protected_dataset_apis_and_validation(raw, repo, secured):
    secured.app.dependency_overrides[repository] = lambda: repo
    for path in ("air-quality/current?location_id=x", "air-quality/forecast?location_id=x", "air-quality/stations", "data/quality"):
        assert secured.client.get("/api/v1/" + path).status_code == 401
    headers = {"Authorization": "Bearer " + secured.token()}
    assert secured.client.get("/api/v1/air-quality/stations", headers=headers).json()["status"] == "unavailable"
    curate(repo, save_raw(repo, raw))
    location = "cams_global:28.6000:77.2000"
    response = secured.client.get("/api/v1/air-quality/current", params={"source": "open_meteo", "location_id": location}, headers=headers)
    assert response.status_code == 200 and len(response.json()["records"]) == 4
    assert all(r["kind"] == "modeled" for r in response.json()["records"])
    assert secured.client.get("/api/v1/data/quality", headers=headers).json()["reports"][0]["records"] == 8
    assert secured.client.get("/api/v1/air-quality/history", params={"source": "openaq", "location_id": "9", "start": "2026-10-01", "end": "2026-10-08"}, headers=headers).status_code == 422
    clock = datetime.now(UTC)
    rows, _ = read_rows(repo, "open_meteo", clock-timedelta(days=1), clock+timedelta(days=1))
    assert len(rows) == 8


def test_openaq_request_contract_and_flag_quarantine():
    calls = []
    stamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    station = {"id": 9, "sensors": [{"id": 5}], "coordinates": {"latitude": 28.6, "longitude": 77.2}}
    item = {"value": 12, "parameter": {"name": "pm25", "units": "ug/m3"},
            "flagInfo": {"hasFlags": True}, "period": {"datetimeFrom": {"utc": stamp}, "datetimeTo": {"utc": stamp}}}
    def response(request):
        calls.append(request)
        return httpx.Response(200, json={"meta": {"page": 1}, "results": [station] if '/locations/' in request.url.path else [item]})
    adapter = OpenAQ("fixture-only", JsonTransport(httpx.Client(transport=httpx.MockTransport(response)), sleep=lambda _: None))
    raw = adapter.fetch(location_id=9, sensor_id=5, start=stamp, end=stamp)
    assert calls[1].url.params["datetime_from"] == stamp
    assert calls[1].headers["X-API-Key"] == "fixture-only"
    assert "fixture-only" not in json.dumps(raw)
    row = adapter.clean(raw)[0]
    assert row.value is None and row.original_value == 12
    assert "provider_flagged" in row.quality_flags
    assert json.loads(row.provider_quality)["hasFlags"] is True


def test_invalid_backfill_does_not_request(repo, monkeypatch):
    monkeypatch.setenv("OPENAQ_API_KEY", "fixture-only")
    with pytest.raises(ValueError, match="seven days"):
        ingest("openaq", {"location_id": 9, "sensor_id": 5, "start": "2026-10-01T00:00:00Z", "end": "2026-10-09T00:00:00Z"}, repo)
    with pytest.raises(ValueError, match="1-7 days"):
        ingest("open_meteo", {"start": "2020-01-01", "end": "2020-01-02"}, repo)


def test_aws_metadata_ttl_budget_and_encrypted_upload():
    import boto3
    from botocore.stub import ANY, Stubber
    from ecoroute.environment.repository import AwsRepository
    def client(service):
        return boto3.client(service, region_name="ap-south-1", aws_access_key_id="test", aws_secret_access_key="test")
    s3, dynamo = client("s3"), client("dynamodb")
    repo = AwsRepository(s3, dynamo, "fixture-bucket", "environment")
    with Stubber(s3) as stub:
        stub.add_response("put_object", {}, {"Bucket": "fixture-bucket", "Key": "raw/source=openaq/test.json", "Body": b"{}", "ContentType": "application/json", "ServerSideEncryption": "AES256"})
        repo.put_bytes("raw/source=openaq/test.json", b"{}", "application/json")
        stub.assert_no_pending_responses()
    with Stubber(dynamo) as stub:
        stub.add_response("query", {"Items": [{"pk": {"S": "FILES#openaq"}, "sk": {"S": "x"}, "expires_at": {"N": "1"}, "payload": {"S": "{}"}}]}, {"TableName": "environment", "KeyConditionExpression": ANY, "ExpressionAttributeValues": ANY, "ScanIndexForward": False, "Limit": 20, "ConsistentRead": True})
        assert repo.query("FILES#openaq", limit=20) == ([], False)
        stub.add_client_error("transact_write_items", service_error_code="TransactionCanceledException",
                              modeled_fields={"CancellationReasons": [{"Code": "ConditionalCheckFailed"}, {"Code": "None"}]})
        with pytest.raises(BudgetExceeded):
            repo.reserve("openaq")
        stub.assert_no_pending_responses()


def test_collector_failure_does_not_expose_credentials(monkeypatch):
    from ecoroute.handlers import ingestion
    monkeypatch.setattr(ingestion, "repository", lambda: object())
    def fail(*args):
        raise RuntimeError("private-token-in-error")
    monkeypatch.setattr(ingestion, "ingest", fail)
    with pytest.raises(RuntimeError) as raised:
        ingestion.collect({"source": "openaq", "request": {}}, None)
    assert "private-token" not in str(raised.value)


def test_http_gateway_v2_event(secured):
    from mangum import Mangum
    adapter = Mangum(secured.app, lifespan="off")
    event = {"version": "2.0", "routeKey": "GET /api/v1/health", "rawPath": "/api/v1/health", "rawQueryString": "", "headers": {"host": "example.invalid"}, "requestContext": {"http": {"method": "GET", "path": "/api/v1/health", "sourceIp": "127.0.0.1", "protocol": "HTTP/1.1"}, "stage": "$default"}, "isBase64Encoded": False}
    response = adapter(event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["status"] == "ok"
