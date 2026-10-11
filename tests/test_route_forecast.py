"""Synthetic provider fixtures only; no fabricated production pollution values."""
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from ecoroute.config import Settings
from ecoroute.environment.repository import BudgetExceeded
from ecoroute.main import create_app
from ecoroute.routing.forecast import RouteForecast
from ecoroute.routing.pollution import PollutionIndex
from ecoroute.storage import LocalStore


def fixture_payload(lat, lon, *, unit="µg/m³", value=20):
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    variables = ("pm2_5", "pm10", "nitrogen_dioxide", "ozone")
    return {"latitude": lat, "longitude": lon, "utc_offset_seconds": 0,
            "hourly_units": dict.fromkeys(variables, unit),
            "hourly": {"time": [int((start + timedelta(hours=i)).timestamp()) for i in range(5)],
                       **{v: [value] * 5 for v in variables}}}


def pieces(lon=72.8347, lat=18.922):
    return [[{"sample_position": [lon, lat],
              "sample_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}]]


def test_mumbai_gap_uses_actual_adapter_and_same_grid_cache():
    calls, budgets = [], []
    def send(req):
        calls.append(req)
        return httpx.Response(200, json=fixture_payload(float(req.url.params["latitude"]),
                                                        float(req.url.params["longitude"])))
    forecast = RouteForecast(lambda: budgets.append(True), client=httpx.Client(transport=httpx.MockTransport(send)))
    point = pieces()
    index, status = forecast.supplement(PollutionIndex([]), point)
    sample = index.sample(point[0][0]["sample_position"], datetime.fromisoformat(point[0][0]["sample_at"]))
    assert status == "provider_forecast" and sample["value_ug_m3"] == 20
    assert sample["status"] == "forecast" and sample["resolution_km"] == 45
    _, status = forecast.supplement(PollutionIndex([]), pieces(lon=72.835))
    assert status == "forecast_cache" and len(calls) == len(budgets) == 1
    assert calls[0].url.params["domains"] == "cams_global"


@pytest.mark.parametrize("problem", ["outage", "schema", "unit", "missing"])
def test_bad_forecasts_remain_unavailable(problem):
    def send(req):
        payload = fixture_payload(18.8, 72.8, unit="AQI" if problem == "unit" else "µg/m³",
                                  value=None if problem == "missing" else 20)
        return httpx.Response(503 if problem == "outage" else 200,
                              json={} if problem == "schema" else payload)
    forecast = RouteForecast(lambda: None, client=httpx.Client(transport=httpx.MockTransport(send)))
    point = pieces()
    index, _ = forecast.supplement(PollutionIndex([]), point)
    assert index.sample(point[0][0]["sample_position"], datetime.fromisoformat(point[0][0]["sample_at"]))["value_ug_m3"] is None


def test_limit_prevents_network_and_only_three_cells_attempted():
    def denied():
        raise BudgetExceeded()
    def never(req):
        pytest.fail("Allowance must be checked before network")
    index, status = RouteForecast(denied, client=httpx.Client(transport=httpx.MockTransport(never))).supplement(PollutionIndex([]), pieces())
    assert not index.rows and status == "request_allowance"
    calls = []
    def send(req):
        calls.append(req)
        return httpx.Response(200, json=fixture_payload(float(req.url.params["latitude"]), float(req.url.params["longitude"])))
    forecast = RouteForecast(lambda: None, client=httpx.Client(transport=httpx.MockTransport(send)))
    route = sum([pieces(lon=70 + i)[0] for i in range(5)], [])
    index, _ = forecast.supplement(PollutionIndex([]), [route])
    assert len(calls) == 3
    assert index.sample(route[-1]["sample_position"], datetime.fromisoformat(route[-1]["sample_at"]))["value_ug_m3"] is None


def test_existing_valid_data_is_used_without_network():
    from ecoroute.environment.providers import OpenMeteo
    def never(*args):
        pytest.fail("Fresh curated coverage must not fetch another forecast")
    envelope = {"payload": fixture_payload(18.8, 72.8), "collected_at": datetime.now(UTC).isoformat(),
                "request": {}, "attribution": "fixture", "license": "fixture"}
    rows = [r.model_dump(mode="json") for r in OpenMeteo().clean(envelope)]
    index, status = RouteForecast(never).supplement(PollutionIndex(rows), pieces())
    assert status == "not_needed" and index.rows == rows


def test_guest_explanation_uses_server_metrics_and_no_saved_route(monkeypatch):
    from ecoroute.routing import api
    from ecoroute.advisory import explanation
    calls = []
    class Provider:
        name, persist_results = "google_routes", False
    class Engine:
        provider = Provider()
        def compare(self, owner, body):
            assert owner == "guest-request-only"
            return {"routes": [{"route_id": "server-generated", "duration_s": 600}], "persistence": "request_only"}
    def explain(routes, settings, repo):
        calls.append(routes)
        return {"mode": "gemini_arranged_approved_text", "explanation": "approved", "fallback_reason": None}
    monkeypatch.setattr(explanation, "explain", explain)
    monkeypatch.setattr(api, "repository", lambda: None)
    app = create_app(Settings(_env_file=None, routing_provider="google", enable_guest_routes=True), store=LocalStore(":memory:"))
    app.state.route_service = Engine()
    body = {"origin": {"latitude": 18.922, "longitude": 72.8347}, "destination": {"latitude": 18.9432, "longitude": 72.8236},
            "departure_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(), "include_explanation": True}
    client = TestClient(app)
    result = client.post("/api/v1/routes/preview", json=body)
    assert result.status_code == 200 and result.json()["explanation"]["mode"] == "gemini_arranged_approved_text"
    assert calls == [[{"route_id": "server-generated", "duration_s": 600}]]
    assert client.post("/api/v1/routes/preview", json={**body, "estimated_pm25_exposure_ug_h_m3": 999}).status_code == 422
    assert client.post("/api/v1/ai/explain-route", json={"route_ids": ["a" * 32]}).status_code == 401
    client.post("/api/v1/routes/preview", json={**body, "include_explanation": False})
    assert len(calls) == 1


def test_gemini_hundred_per_hour_configuration():
    assert Settings(_env_file=None, gemini_hourly_limit=100, gemini_daily_limit=100).gemini_hourly_limit == 100
