"""Synthetic mechanics fixtures; no actual smartwatch integration is claimed."""
import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from ecoroute.config import Settings
from ecoroute.wearable.handlers import process_mqtt
from ecoroute.wearable.models import Measurement
from ecoroute.wearable.repository import WearableRepository, owner_key, topic
from scripts.iot_device_plan import policy


def headers(secured, **kwargs):
    return {"Authorization": "Bearer " + secured.token(**kwargs), "Idempotency-Key": "wearable-test-key"}


def setup(secured, tmp_path):
    secured.app.state.settings.wearable_archive_path = str(tmp_path)
    body = {"manufacturer": "Synthetic fixture", "model": "No watch", "bridge": "companion_https"}
    response = secured.client.post("/api/v1/devices/register", headers=headers(secured), json=body)
    assert response.status_code == 201
    device = response.json()["device_id"]
    sample = {"device_id": device, "user_id": "alice", "event_id": uuid.uuid4().hex,
        "timestamp": datetime.now(UTC).isoformat(), "heart_rate_bpm": 80,
        "provenance": {"bridge": "companion_https", "sensor": "synthetic unit fixture", "source_record_id": "fixture"}}
    return device, sample, body


def consent(secured, device, **extra):
    return secured.client.post("/api/v1/wearables/consent", headers=headers(secured),
        json={"device_id": device, "telemetry": True, **extra})


def test_registration_idempotency_and_ownership(secured, tmp_path):
    device, sample, registration = setup(secured, tmp_path)
    repeated = secured.client.post("/api/v1/devices/register", headers=headers(secured), json=registration)
    assert repeated.status_code == 200 and repeated.json()["device_id"] == device
    registration["model"] = "Changed"
    assert secured.client.post("/api/v1/devices/register", headers=headers(secured), json=registration).status_code == 409
    assert secured.client.post("/api/v1/wearables/measurements", json=sample).status_code == 401
    assert secured.client.post("/api/v1/wearables/measurements", headers=headers(secured, sub="bob"), json=sample).status_code == 403
    assert secured.client.get("/api/v1/wearables/latest", params={"device_id": device}, headers=headers(secured, sub="bob")).status_code == 404


def test_consent_revoke_dedupe_latest_and_delete(secured, tmp_path):
    device, sample, _ = setup(secured, tmp_path)
    def post(s):
        return secured.client.post("/api/v1/wearables/measurements", headers=headers(secured), json=s)
    assert post(sample).status_code == 403
    assert consent(secured, device, history=True).status_code == 200
    assert post(sample).status_code == 201
    assert post(sample).status_code == 200
    changed = {**sample, "heart_rate_bpm": 99}
    assert post(changed).status_code == 409
    older = {**sample, "event_id": uuid.uuid4().hex, "timestamp": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()}
    assert post(older).status_code == 201
    latest = secured.client.get("/api/v1/wearables/latest", params={"device_id": device}, headers=headers(secured))
    assert latest.json()["measurement"]["event_id"] == sample["event_id"]
    assert len(list(tmp_path.rglob("*.json"))) == 2
    revoked = secured.client.post("/api/v1/wearables/consent", headers=headers(secured), json={"device_id": device, "telemetry": False})
    assert revoked.status_code == 200 and post(sample).status_code == 403
    result = secured.client.delete("/api/v1/wearables/data", params={"device_id": device}, headers=headers(secured))
    assert result.status_code == 200 and result.json()["status"] == "deleted"
    assert not list(tmp_path.rglob("*.json"))
    assert consent(secured, device).status_code == 409
    assert not secured.store.db.execute("SELECT id FROM records WHERE id LIKE 'measurement#%'").fetchall()


def test_schema_gps_scope_history_pagination_and_invalid_readings(secured, tmp_path):
    device, sample, _ = setup(secured, tmp_path)
    consent(secured, device, history=True)
    sample["heart_rate_bpm"] = 300
    assert secured.client.post("/api/v1/wearables/measurements", headers=headers(secured), json=sample).status_code == 422
    sample["heart_rate_bpm"] = 80
    sample.update(position={"latitude": 28.6, "longitude": 77.2}, accuracy_m=10)
    assert secured.client.post("/api/v1/wearables/measurements", headers=headers(secured), json=sample).status_code == 403
    consent(secured, device, history=True, location=True)
    for i in range(2):
        sample.update(event_id=uuid.uuid4().hex, timestamp=(datetime.now(UTC) - timedelta(seconds=i)).isoformat())
        assert secured.client.post("/api/v1/wearables/measurements", headers=headers(secured), json=sample).status_code == 201
    params = {"device_id": device, "start": (datetime.now(UTC) - timedelta(hours=1)).isoformat(), "end": datetime.now(UTC).isoformat(), "limit": 1}
    first = secured.client.get("/api/v1/wearables/history", params=params, headers=headers(secured)).json()
    assert first["truncated"] and len(first["measurements"]) == 1
    params["cursor"] = first["next_cursor"]
    second = secured.client.get("/api/v1/wearables/history", params=params, headers=headers(secured)).json()
    assert len(second["measurements"]) == 1 and not second["truncated"]
    params["cursor"] = "measurement#" + "f" * 32
    assert secured.client.get("/api/v1/wearables/history", params=params, headers=headers(secured)).status_code == 422
    sample["timestamp"] = "2020-01-01T00:00:00Z"
    assert secured.client.post("/api/v1/wearables/measurements", headers=headers(secured), json=sample).status_code == 422


def test_broker_envelope_binding_and_revocation(secured, tmp_path):
    device, sample, _ = setup(secured, tmp_path)
    consent(secured, device)
    repo = WearableRepository(secured.store)
    record = repo.device("alice", device)
    record["certificate_thumbprint"] = "test-certificate-thumbprint"
    secured.store.put_record("wearable", owner_key("alice"), "device#" + device, record, 1000)
    event = {"payload_b64": base64.b64encode(json.dumps(sample).encode()).decode(),
        "owner_key": owner_key("alice"), "device_id": device, "mqtt_client_id": "eco-" + device,
        "mqtt_topic": topic("alice", device), "principal": "test-certificate-thumbprint"}
    assert process_mqtt(event, repo)[1] is True
    for field in ("principal", "mqtt_topic", "mqtt_client_id", "device_id"):
        with pytest.raises(ValueError):
            process_mqtt({**event, field: "spoofed"}, repo)
    revoked = secured.client.post("/api/v1/wearables/consent", headers=headers(secured), json={"device_id": device, "telemetry": False})
    assert revoked.status_code == 200
    with pytest.raises(HTTPException):
        process_mqtt(event, repo)


def test_demo_guard_policy_and_utc_units():
    with pytest.raises(ValueError, match="local-only"):
        Settings(_env_file=None, ecoroute_profile="aws", wearable_demo_mode=True)
    document = policy("123456789012", "ap-south-1", "a" * 64, "b" * 32)
    assert [s["Action"] for s in document["Statement"]] == ["iot:Connect", "iot:Publish"]
    assert "*" not in json.dumps(document)
    assert "+" not in json.dumps(document) and "IsAttached" in json.dumps(document)
    sample = Measurement(device_id="a" * 32, user_id="fixture", event_id="b" * 32,
        timestamp=datetime.now(UTC).astimezone().isoformat(), heart_rate_bpm=60,
        provenance={"bridge": "authorized_import", "sensor": "fixture", "source_record_id": "1"})
    assert sample.timestamp.utcoffset() == timedelta(0)


def test_descriptive_correlation_missing_and_available():
    from ecoroute.wearable.correlation import correlate
    when = datetime.now(UTC)
    row = {"event_id": "fixture", "timestamp": when.isoformat(), "heart_rate_bpm": 70,
        "activity": "walking", "position": {"longitude": 77.2, "latitude": 28.6}, "accuracy_m": 10}
    route = {"segments": [{"arrival_at": (when - timedelta(seconds=10)).isoformat(),
        "end_at": (when + timedelta(seconds=10)).isoformat(), "sample_position": [77.2, 28.6], "length_m": 100, "segment_index": 0}]}
    index = SimpleNamespace(sample=lambda *args: {"value_ug_m3": 50, "status": "observed", "source": "synthetic unit fixture"})
    output = correlate([row], route, index)
    assert output["paired_count"] == 1 and output["exposure_index"] is None and output["medical_stress_score"] is None
    assert "causal" in output["warnings"][0]
    row["position"] = None
    assert correlate([row], route, index)["paired_count"] == 0


def test_dynamo_transaction_checks_consent_atomically_and_sdk_shapes(secured, tmp_path):
    from botocore.session import get_session
    from botocore.validate import validate_parameters
    from botocore.exceptions import ClientError
    device, sample, _ = setup(secured, tmp_path)
    consent(secured, device)
    local = WearableRepository(secured.store)
    saved = local.device("alice", device)
    model = get_session().get_service_model("dynamodb")
    calls = []

    class Client:
        def get_item(self, **kwargs):
            validate_parameters(kwargs, model.operation_model("GetItem").input_shape)
            if kwargs["Key"]["sk"]["S"].startswith("device#"):
                return {"Item": WearableRepository.device_item(saved)}
            return {}

        def transact_write_items(self, **kwargs):
            validate_parameters(kwargs, model.operation_model("TransactWriteItems").input_shape)
            calls.append(kwargs)
            return {}

    repo = WearableRepository(SimpleNamespace(client=Client()), "wearables-test")
    assert repo.ingest("alice", Measurement.model_validate(sample))[1]
    check = calls[0]["TransactItems"][0]["ConditionCheck"]
    assert "epoch = :epoch AND consent = :yes AND deleting = :no" in check["ConditionExpression"]
    assert check["ExpressionAttributeValues"][":yes"] == {"BOOL": True}

    def revoked_race(**kwargs):
        saved["consent"]["telemetry"] = False
        raise ClientError({"Error": {"Code": "TransactionCanceledException"}}, "TransactWriteItems")

    repo.store.client.transact_write_items = revoked_race
    with pytest.raises(HTTPException) as rejected:
        repo.ingest("alice", Measurement.model_validate(sample))
    assert rejected.value.status_code == 403


def test_revocation_before_archive_prevents_writes(secured, tmp_path):
    from ecoroute.wearable.archive import Archive
    device, sample, _ = setup(secured, tmp_path)
    consent(secured, device, history=True)
    repo = WearableRepository(secured.store)
    record, _ = repo.ingest("alice", Measurement.model_validate(sample))
    secured.client.post("/api/v1/wearables/consent", headers=headers(secured), json={"device_id": device, "telemetry": False})
    assert Archive(secured.app.state.settings).write(repo, "alice", record) is False
    assert not list(tmp_path.rglob("*.json"))
