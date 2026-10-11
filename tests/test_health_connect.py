"""Explicit synthetic payloads matching the verified upstream JSON shapes; no real health fixtures."""
import json
import time
from datetime import UTC, date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ecoroute.config import Settings
from ecoroute.main import create_app
from ecoroute.wearable.health_connect import HealthConnectClient, HealthConnectError, normalize
from ecoroute.wearable.health_connect_api import client as phone_dependency
from ecoroute.wearable.health_connect_summary import summarize

NOW = datetime(2026, 10, 11, 12, tzinfo=UTC)
BASE = "http://192.168.1.20:8787"
TEST_KEY = "synthetic-test-pairing-key-not-a-live-key-0123456789"


def payload(**types):
    return {"timestamp": NOW.isoformat(), "app_version": "test-fixture", **types}


def sample(value, at="2026-10-11T11:59:00Z", field="bpm", source="test.app"):
    return {field: value, "time": at, "metadata": {"data_origin": source, "recording_method": "automatically_recorded"}}


def interval(value, start="2026-10-11T08:00:00Z", end="2026-10-11T09:00:00Z", field="count"):
    return {field: value, "start_time": start, "end_time": end}


def summary(value, **kwargs):
    return summarize(normalize(value, days=7, now=NOW), now=NOW, **kwargs)


def mock_phone(settings, value=None, *, status=200):
    def handle(request):
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok", "lastSyncTime": None})
        if request.url.path == "/ping":
            return httpx.Response(200, json={"status": "ok"})
        assert request.url.params.get("days") == "7" or request.url.path == "/latest"
        return httpx.Response(status, json=value if value is not None else payload())
    return HealthConnectClient(settings, transport=httpx.MockTransport(handle), clock=lambda: NOW)


def test_latest_by_timestamp_averages_and_units():
    result = summary(payload(heart_rate=[sample(80), sample(65, "2026-10-11T10:00:00Z"),
        {"time": "2026-10-11T11:59:30Z", "avg": 76.5, "min": 70, "max": 85, "bpm": 76.5}],
        blood_pressure=[{"systolic": 120, "diastolic": 80, "time": "2026-10-11T11:00:00Z"}],
        oxygen_saturation=[sample(98, field="percentage")],
        resting_heart_rate=[sample(60)], respiratory_rate=[sample(15, field="rate")]))
    assert result.metrics.heart_rate.value == 76.5
    assert result.metrics.heart_rate.resolution == "bucket_average"
    assert result.metrics.blood_pressure.value.systolic == 120
    assert result.metrics.blood_pressure.unit == "mmHg"
    assert result.metrics.oxygen_saturation.unit == "%"
    assert result.metrics.respiratory_rate.unit == "breaths/min"


def test_steps_duplicates_and_zero_do_not_invent_measurements():
    row = interval(100)
    result = summary(payload(steps=[row, row, interval(0, "2026-10-11T09:00:00Z", "2026-10-11T10:00:00Z")]))
    assert result.metrics.steps.value == 100
    assert "exact_duplicate_records_removed" in result.warnings
    assert result.metrics.heart_rate.value is None
    assert summary(payload(steps=[interval(0)])).metrics.steps.value == 0


def test_ambiguous_overlaps_and_cross_midnight_are_unavailable():
    result = summary(payload(steps=[interval(100), interval(120, "2026-10-11T08:30:00Z", "2026-10-11T09:30:00Z")]))
    assert result.metrics.steps.value is None
    assert result.metrics.steps.warnings == ["overlapping_intervals_total_unavailable"]
    result = summary(payload(steps=[interval(100, "2026-10-10T23:00:00Z", "2026-10-11T01:00:00Z")]))
    assert result.metrics.steps.value is None


def test_browser_timezone_dst_and_calorie_categories():
    result = summary(payload(steps=[interval(40, "2026-10-10T20:00:00Z", "2026-10-10T21:00:00Z")],
        total_calories=[interval(500, field="calories")], active_calories=[interval(100, field="calories")]),
        zone_name="Asia/Kolkata")
    assert result.metrics.steps.value == 40
    assert result.metrics.calories_burned.value == 500  # Never 600.
    assert result.calorie_basis == "total"
    # DST fall-back creates a 25-hour day; counts are not assigned using a fixed UTC offset.
    later = datetime(2026, 11, 2, 12, tzinfo=UTC)
    value = {"timestamp": later.isoformat(), "app_version": "test", "steps": [
        interval(50, "2026-11-01T04:30:00Z", "2026-11-02T04:30:00Z")]}
    result = summarize(normalize(value, days=7, now=later), now=later,
                       selected_date=date(2026, 11, 1), zone_name="America/New_York")
    assert result.metrics.steps.value == 50


def test_unfinished_projection_is_not_actual_burned_calories():
    result = summary(payload(total_calories=[interval(2000, "2026-10-11T00:00:00Z", "2026-10-12T00:00:00Z", "calories")]))
    assert result.metrics.calories_burned.value is None
    assert "unfinished_or_projected" in result.metrics.calories_burned.warnings[0]


def test_other_days_total_energy_does_not_hide_todays_active_energy():
    result = summary(payload(total_calories=[interval(500, "2026-10-10T08:00:00Z", "2026-10-10T09:00:00Z", "calories")],
        active_calories=[interval(100, field="calories")]))
    assert result.calorie_basis == "active"
    assert result.metrics.calories_burned.value == 100


def test_sleep_session_union_and_overnight_date():
    result = summary(payload(sleep=[
        {"session_end_time": "2026-10-11T07:00:00Z", "duration_seconds": 8 * 3600, "stages": []},
        {"session_end_time": "2026-10-11T08:00:00Z", "duration_seconds": 2 * 3600, "stages": []},
    ]))
    assert result.metrics.sleep.value == 9 * 3600
    assert len(result.sleep_sessions) == 2


def test_invalid_nan_naive_dates_and_conflicting_samples():
    result = summary(payload(steps=[interval(True)], heart_rate=[sample(float("nan")),
        sample(76, "2026-10-11T11:00:00"), sample(76), sample(77)]))
    assert result.skipped_records == 3
    assert result.metrics.heart_rate.value is None
    assert result.metrics.heart_rate.warnings == ["conflicting_latest_records"]


def test_phone_cache_is_explicit_and_cannot_supply_daily_totals():
    data = normalize(payload(steps=[interval(100)]), days=7, cached=True, now=NOW)
    result = summarize(data, now=NOW)
    assert result.retrieval == "phone_cache"
    assert result.metrics.steps.value is None
    assert normalize({"status": "no_data"}, days=7, cached=True, now=NOW).status == "empty"


@pytest.mark.parametrize("value", [{}, {"timestamp": "bad", "app_version": "test"}, payload(steps={"count": 5})])
def test_schema_changes_fail_safely(value):
    with pytest.raises(HealthConnectError):
        normalize(value, days=7, now=NOW)


@pytest.mark.parametrize("url", ["http://127.0.0.1:8787", "http://169.254.169.254:80", "http://example.org:8787",
    "http://8.8.8.8:8787", BASE + "/private", BASE + "?token=secret", "http://secret@192.168.1.20:8787"])
def test_phone_target_cannot_be_public_metadata_or_url_credentials(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, health_connect_base_url=url)


def test_aws_profile_cannot_enable_lan_or_local_pairing():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ecoroute_profile="aws", health_connect_base_url=BASE)


@pytest.mark.parametrize("failure,code", [(httpx.ConnectError, "health_connect_phone_unreachable"),
    (httpx.ReadTimeout, "health_connect_timeout")])
def test_disconnect_timeout_and_no_response_leak(failure, code):
    def handle(request):
        raise failure("PRIVATE_HEALTH_MARKER", request=request)
    phone = HealthConnectClient(Settings(_env_file=None, health_connect_base_url=BASE),
                                transport=httpx.MockTransport(handle))
    with pytest.raises(HealthConnectError) as error:
        phone.data()
    assert str(error.value) == code


@pytest.mark.parametrize("status", [301, 401, 403, 429, 500])
def test_provider_http_failures_do_not_echo_body(status):
    phone = mock_phone(Settings(_env_file=None, health_connect_base_url=BASE),
                       {"message": "PRIVATE_HEALTH_MARKER"}, status=status)
    with pytest.raises(HealthConnectError) as error:
        phone.data()
    assert "PRIVATE_HEALTH_MARKER" not in str(error.value)


def test_secret_header_and_response_size_limits(monkeypatch):
    def handle(request):
        assert request.headers["authorization"] == "Bearer SYNTHETIC_PHONE_TOKEN"
        assert "SYNTHETIC_PHONE_TOKEN" not in str(request.url)
        return httpx.Response(200, content=b"x" * 100, headers={"content-type": "application/json"})
    monkeypatch.setattr("ecoroute.wearable.health_connect.MAX_BYTES", 50)
    phone = HealthConnectClient(Settings(_env_file=None, health_connect_base_url=BASE,
        health_connect_token="SYNTHETIC_PHONE_TOKEN"), transport=httpx.MockTransport(handle))
    with pytest.raises(HealthConnectError, match="payload_too_large"):
        phone.data()


def test_deep_invalid_json_fails_safely_and_releases_read_lock():
    def handle(request):
        return httpx.Response(200, content=b"[" * 2000 + b"0" + b"]" * 2000,
                              headers={"content-type": "application/json"})
    phone = HealthConnectClient(Settings(_env_file=None, health_connect_base_url=BASE),
                                transport=httpx.MockTransport(handle))
    with pytest.raises(HealthConnectError, match="invalid_response"):
        phone.data()
    assert not phone.lock.locked()


def test_missing_configuration_and_overlapping_read_fail_before_network():
    phone = HealthConnectClient(Settings(_env_file=None))
    with pytest.raises(HealthConnectError, match="not_configured"):
        phone.data()
    phone.lock.acquire()
    try:
        with pytest.raises(HealthConnectError, match="request_in_progress"):
            phone.data()
    finally:
        phone.lock.release()


def test_cognito_owner_consent_validation_and_contracts(secured, caplog):
    settings = secured.app.state.settings
    settings.health_connect_base_url = BASE
    settings.health_connect_owner_sub = "alice"
    phone = mock_phone(settings, payload(steps=[interval(100)]))
    secured.app.dependency_overrides[phone_dependency] = lambda: phone
    base = "/api/v1/wearables/health-connect"
    auth = {"Authorization": "Bearer " + secured.token()}
    assert secured.client.get(base + "/summary").status_code == 401
    assert secured.client.get(base + "/summary", headers=auth).status_code == 403
    assert secured.client.get(base + "/summary?consent=true", headers={"Authorization": "Bearer " + secured.token(sub="bob")}).status_code == 403
    assert secured.client.get(base + "/summary?consent=true&days=31", headers=auth).status_code == 422
    assert secured.client.get(base + "/summary?consent=true&timezone_name=bad", headers=auth).status_code == 422
    result = secured.client.get(base + "/summary?consent=true", headers=auth)
    assert result.status_code == 200
    assert result.json()["metrics"]["steps"]["value"] == 100
    assert result.headers["cache-control"] == "no-store"
    assert BASE not in result.text + caplog.text
    from tests.test_phase7 import validator
    spec = secured.app.openapi()
    validator(spec, {"$ref": "#/components/schemas/HealthConnectSummary"}).validate(result.json())
    for endpoint in ("/status", "/data?consent=true"):
        result = secured.client.get(base + endpoint, headers=auth)
        assert result.status_code == 200
        assert result.json().get("authentication", "cognito") == "cognito"


def test_local_pairing_is_scoped_expiring_and_loopback_only():
    settings = Settings(_env_file=None, local_db_path=":memory:", health_connect_base_url=BASE,
        health_connect_owner_sub="local-health-test", health_connect_local_access_token=TEST_KEY,
        health_connect_local_access_expires_at=int(time.time()) + 3600,
        cors_origins=["http://127.0.0.1:5173"])
    app = create_app(settings)
    app.state.health_connect = mock_phone(settings, payload())
    auth = {"Authorization": "Bearer " + TEST_KEY}
    path = "/api/v1/wearables/health-connect/summary?consent=true"
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 60000)) as client:
        assert client.get(path).status_code == 401
        assert client.get(path, headers=auth).status_code == 200
        assert client.get(path, headers={**auth, "Origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/v1/wearables/latest?device_id=" + "a" * 32, headers=auth).status_code == 503
        settings.health_connect_local_access_expires_at = int(time.time()) - 1
        assert client.get(path, headers=auth).status_code == 401
    settings.health_connect_local_access_expires_at = int(time.time()) + 3600
    with TestClient(app, base_url="http://127.0.0.1", client=("192.168.1.20", 60000)) as client:
        assert client.get(path, headers=auth).status_code == 403
    app.state.store.db.close()


def test_pairing_configuration_preserves_existing_secrets_and_rotates(tmp_path):
    from scripts.health_connect import configure
    (tmp_path / ".env").write_text("GEMINI_API_KEY=SYNTHETIC_PRIVATE_MARKER\nHEALTH_CONNECT_TOKEN=PHONE_PRIVATE_MARKER\n")
    result = configure(BASE, root=tmp_path)
    text = (tmp_path / ".env").read_text()
    first = (tmp_path / "work/health-connect-pairing.txt").read_text()
    assert "SYNTHETIC_PRIVATE_MARKER" in text and "PHONE_PRIVATE_MARKER" in text
    assert first.strip() not in json.dumps(result)
    configure(BASE, root=tmp_path)
    assert first != (tmp_path / "work/health-connect-pairing.txt").read_text()
