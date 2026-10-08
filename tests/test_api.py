import json
import time
from datetime import UTC, datetime

import jwt
import pytest
from pydantic import ValidationError

from ecoroute.config import Settings

TRIP = {"origin": {"longitude": 77.2, "latitude": 28.6},
        "destination": {"longitude": 77.3, "latitude": 28.7}, "consent": True}


def headers(secured, **claims):
    return {"Authorization": "Bearer " + secured.token(**claims), "Idempotency-Key": "request-001"}


@pytest.mark.parametrize("changes", [
    {"exp": 1}, {"iat": int(time.time()) + 3600}, {"nbf": int(time.time()) + 3600},
    {"iss": "https://attacker.example"}, {"client_id": "other"}, {"token_use": "id"},
    {"aud": "other"}, {"sub": ""},
])
def test_bad_claims_rejected(secured, changes):
    response = secured.client.get("/api/v1/alerts/preferences", headers=headers(secured, **changes))
    assert response.status_code == 401


def test_missing_forged_and_insufficient_auth(secured):
    path = "/api/v1/alerts/preferences"
    assert secured.client.get(path).status_code == 401
    forged = jwt.encode({"sub": "alice"}, "not-the-key" * 4, algorithm="HS256", headers={"kid": "test-key"})
    assert secured.client.get(path, headers={"Authorization": "Bearer " + forged}).status_code == 401
    assert secured.client.get(path, headers=headers(secured, scope="unrelated")).status_code == 403
    assert secured.client.get("/api/v1/ready").status_code == 200


def test_signature_tampering_rejected(secured):
    parts = secured.token().split(".")
    parts[1] = jwt.utils.base64url_encode(json.dumps({"sub": "mallory"}).encode()).decode()
    assert secured.client.get("/api/v1/alerts/preferences",
        headers={"Authorization": "Bearer " + ".".join(parts)}).status_code == 401


def test_trip_idempotency_conflict_and_owner_isolation(secured):
    first = secured.client.post("/api/v1/trips", json=TRIP, headers=headers(secured))
    assert first.status_code == 201
    again = secured.client.post("/api/v1/trips", json=TRIP, headers=headers(secured))
    assert again.status_code == 200
    assert first.json() == again.json()
    changed = {**TRIP, "destination": {"longitude": 78, "latitude": 29}}
    assert secured.client.post("/api/v1/trips", json=changed, headers=headers(secured)).status_code == 409
    path = "/api/v1/trips/" + first.json()["id"]
    assert secured.client.get(path, headers=headers(secured)).status_code == 200
    assert secured.client.get(path, headers=headers(secured, sub="bob")).status_code == 404


@pytest.mark.parametrize("body", [
    {**TRIP, "origin": {"longitude": 181, "latitude": 28}},
    {**TRIP, "consent": False}, {**TRIP, "user_id": "bob"},
])
def test_invalid_trip_rejected(secured, body):
    assert secured.client.post("/api/v1/trips", json=body, headers=headers(secured)).status_code == 422


def test_body_limit_and_validation_do_not_echo_input(secured):
    response = secured.client.post("/api/v1/trips", content=b"x" * 262145, headers=headers(secured))
    assert response.status_code == 413
    response = secured.client.post("/api/v1/trips", json={"private": "do-not-echo"}, headers=headers(secured))
    assert response.status_code == 422
    assert "do-not-echo" not in response.text


def test_telemetry_requires_auth_consent_and_valid_time(secured):
    sample = {"observed_at": datetime.now(UTC).isoformat(), "position": TRIP["origin"], "accuracy_m": 10}
    body = {"source": "synthetic_fixture", "consent": True, "samples": [sample]}
    assert secured.client.post("/api/v1/wearables/telemetry", json=body).status_code == 401
    result = secured.client.post("/api/v1/wearables/telemetry", json=body, headers=headers(secured))
    assert result.status_code == 201
    assert result.json()["source"] == "synthetic_fixture"
    assert "position" not in result.text
    body["samples"] *= 2
    assert secured.client.post("/api/v1/wearables/telemetry", json=body, headers=headers(secured)).status_code == 422


def test_preferences_are_owner_scoped(secured):
    path = "/api/v1/alerts/preferences"
    assert secured.client.put(path, json={"alerts_enabled": True}, headers=headers(secured)).status_code == 200
    assert secured.client.get(path, headers=headers(secured)).json()["alerts_enabled"] is True
    assert secured.client.get(path, headers=headers(secured, sub="bob")).json()["alerts_enabled"] is False


@pytest.mark.parametrize("path", ["air-quality", "predictions", "school-safety"])
def test_unconnected_products_are_honest(secured, path):
    response = secured.client.get(f"/api/v1/{path}?longitude=77.2&latitude=28.6", headers=headers(secured))
    assert response.status_code == 503


def test_cors_rejects_wildcard():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=["*"])


def test_logs_do_not_include_subject_position_or_token(secured, caplog):
    auth = headers(secured)
    secured.client.post("/api/v1/trips", json=TRIP, headers=auth)
    assert "77.2" not in caplog.text
    assert "alice" not in caplog.text
    assert auth["Authorization"] not in caplog.text
