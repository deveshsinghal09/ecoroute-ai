"""Recorded road geometry and explicitly artificial weather for scoring contracts."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from ecoroute.ml.api import ml_service
from ecoroute.routing.api import service
from ecoroute.routing.cycling import OpenRouteCycling
from ecoroute.routing.google import GoogleRoutes
from ecoroute.routing.models import CompareRequest
from ecoroute.routing.pollution import PollutionIndex, rank_routes, score_exposure
from ecoroute.routing.geometry import segments
from ecoroute.routing.providers import OsrmProvider
from ecoroute.routing.service import RouteService
from ecoroute.routing.weather import RouteWeather, attach_weather


@pytest.fixture
def routes():
    fixture = json.loads(Path("tests/fixtures/delhi_osrm_routes.json").read_text(encoding="utf-8"))
    return fixture, OsrmProvider.parse(
        fixture["payload"],
        fixture["origin"],
        fixture["destination"],
        fixture=True,
        collected_at=fixture["collected_at"],
    )


def request(fixture, **options):
    return CompareRequest(
        origin={"longitude": fixture["origin"][0], "latitude": fixture["origin"][1]},
        destination={"longitude": fixture["destination"][0], "latitude": fixture["destination"][1]},
        departure_at=datetime.now(UTC) + timedelta(minutes=10),
        consent_to_store=True,
        **options,
    )


def test_google_traffic_and_driving_modifiers(routes):
    fixture, candidates = routes
    route = candidates[0]

    def respond(wire):
        body = json.loads(wire.content)
        assert body["routingPreference"] == "TRAFFIC_AWARE"
        assert body["routeModifiers"] == {
            "avoidTolls": True,
            "avoidHighways": True,
            "avoidFerries": False,
        }
        assert "routes.staticDuration" in wire.headers["X-Goog-FieldMask"]
        return httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "duration": f"{route['duration_s']}s",
                        "staticDuration": "300s",
                        "distanceMeters": route["distance_m"],
                        "polyline": {"geoJsonLinestring": route["geometry"]},
                    }
                ]
            },
        )

    provider = GoogleRoutes(
        "test-only", client=httpx.Client(transport=httpx.MockTransport(respond))
    )
    output = provider.candidates(
        fixture["origin"],
        fixture["destination"],
        request(fixture, mode="driving", avoid_tolls=True, avoid_highways=True),
    )[0]
    traffic = output["routing_source"]["traffic"]
    assert traffic["historical_baseline_duration_s"] == 300
    assert traffic["difference_from_historical_s"] == route["duration_s"] - 300


def test_cycling_modeled_ascent_and_step_preference(routes):
    fixture, candidates = routes
    route = candidates[0]

    def respond(wire):
        body = json.loads(wire.content)
        assert body["options"] == {"avoid_features": ["steps"]} and body["elevation"]
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": route["geometry"],
                        "properties": {
                            "ascent": 12.5,
                            "descent": 10,
                            "summary": {
                                "distance": route["distance_m"],
                                "duration": route["duration_s"],
                            },
                        },
                    }
                ],
            },
        )

    provider = OpenRouteCycling(
        "test-only", client=httpx.Client(transport=httpx.MockTransport(respond))
    )
    output = provider.candidates(
        fixture["origin"],
        fixture["destination"],
        request(fixture, mode="cycling", terrain_weight=0.2, avoid_steps=True),
    )[0]
    assert (
        output["terrain"]["ascent_m"] == 12.5 and output["terrain"]["resolution"] == "not_supplied"
    )


@pytest.mark.parametrize(
    "options",
    [
        {"mode": "walking", "avoid_tolls": True},
        {"mode": "walking", "avoid_steps": True},
        {"mode": "driving", "terrain_weight": 0.1},
        {"exposure_weight": 0.8, "weather_weight": 0.3},
    ],
)
def test_invalid_preferences_are_rejected(routes, options):
    with pytest.raises(ValidationError):
        request(routes[0], **options)


def weather_response(stamp):
    return {
        "latitude": 28.6,
        "longitude": 77.2,
        "hourly_units": {"temperature_2m": "°C", "precipitation": "mm", "wind_speed_10m": "m/s"},
        "hourly": {
            "time": [stamp.replace(tzinfo=None).isoformat(timespec="minutes")],
            "temperature_2m": [30],
            "precipitation": [2],
            "wind_speed_10m": [3],
        },
    }


def test_weather_cache_units_time_and_outage():
    stamp = datetime(2026, 10, 11, 10, tzinfo=UTC)
    payload = weather_response(stamp)
    calls = []
    provider = RouteWeather(
        reserve=lambda: calls.append(1),
        clock=lambda: stamp,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ),
    )
    assert provider.sample([77.21, 28.61], stamp)["status"] == "forecast"
    assert provider.sample([77.22, 28.62], stamp)["preference_cost"] > 0
    assert len(calls) == 1
    with pytest.raises(ValueError, match="time_coverage"):
        provider.sample([77.22, 28.62], stamp + timedelta(hours=3))
    invalid = copy.deepcopy(payload)
    invalid["hourly_units"]["wind_speed_10m"] = "km/h"
    provider = RouteWeather(
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=invalid))
        )
    )
    with pytest.raises(ValueError, match="units_changed"):
        provider.sample([77.2, 28.6], stamp)
    provider = RouteWeather(
        client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    )
    routes = [
        {
            "geometry": {"coordinates": [[77.2, 28.6], [77.21, 28.61]]},
            "duration_s": 60,
            "warnings": [],
        }
    ]
    attach_weather(routes, SimpleNamespace(weather_weight=0.2, departure_at=stamp), provider)
    assert routes[0]["weather"]["preference_cost"] is None


def test_weather_weight_changes_ranking_only_with_complete_inputs(routes):
    fixture, candidates = routes
    body = request(
        fixture, mode="driving", exposure_weight=0, weather_weight=0.9, max_detour_percent=100
    )
    scored = [
        score_exposure(c, segments(c, body.departure_at, 250), PollutionIndex([]))
        for c in candidates
    ]
    fastest = min(scored, key=lambda r: r["duration_s"])
    slowest = max(scored, key=lambda r: r["duration_s"])
    for r in scored:
        r["estimated_pm25_exposure_ug_h_m3"] = 1  # Explicit arithmetic-only fixture.
        r["weather"] = {"preference_cost": 1 if r is fastest else 0}
    result = rank_routes(scored, body)
    assert result["selected_candidate_key"] == slowest["candidate_key"]
    slowest["weather"]["preference_cost"] = None
    result = rank_routes(scored, body)
    assert result["recommendations"]["balanced"] is None
    assert result["selected_candidate_key"] == fastest["candidate_key"]


def test_predicted_route_api_auth_missing_model_and_full_geometry(secured, routes, tmp_path):
    from ecoroute.environment.repository import LocalRepository
    from ecoroute.storage import LocalStore

    fixture, candidates = routes

    class RecordedProvider:
        name = "recorded_test_only"

        def resolve(self, point):
            return [point.longitude, point.latitude]

        def candidates(self, *args):
            return copy.deepcopy(candidates)

    scoring = RouteService(RecordedProvider(), LocalStore(":memory:"), LocalRepository(tmp_path))
    secured.app.dependency_overrides[service] = lambda: scoring
    batch = {"results": []}
    secured.app.dependency_overrides[ml_service] = lambda: SimpleNamespace(
        batch=lambda *args, **kwargs: batch
    )
    body = {
        **request(fixture, mode="driving").model_dump(mode="json"),
        "station_ids": ["TEST_ONLY"],
        "model_version": "a" * 24,
    }
    assert secured.client.post("/api/v1/routes/predict", json=body).status_code == 401
    headers = {"Authorization": "Bearer " + secured.token()}
    assert (
        secured.client.post("/api/v1/routes/predict", headers=headers, json=body).status_code == 503
    )
    issued = datetime.now(UTC)
    batch["results"] = [
        {
            "status": "available",
            "prediction": {
                "latitude": 28.6139,
                "longitude": 77.209,
                "station_id": "TEST_ONLY",
                "value_ug_m3": 30,
                "model_version": "a" * 24,
                "issued_at": issued.isoformat(),
                "valid_at": (issued + timedelta(hours=1)).isoformat(),
                "confidence": "synthetic_test_only",
            },
        }
    ]
    output = secured.client.post("/api/v1/routes/predict", headers=headers, json=body)
    assert output.status_code == 200
    result = output.json()
    assert result["routes"][0]["geometry"]["type"] == "LineString"
    assert result["routes"][0]["segments"]
    assert result["model_versions"] == ["a" * 24]
    # Invalid temporal match does not fill missing pollution with a prediction.
    assert all(r["estimated_pm25_exposure_ug_h_m3"] is None for r in result["routes"])

@pytest.mark.parametrize(
    "objective,weight,expected",
    [("fastest", 0.9, "fast"), ("lowest_exposure", 0.1, "slow"),
     ("balanced", 0.1, "fast"), ("balanced", 0.9, "slow")],
)
def test_objectives_and_pollution_priority_change_selection(routes, objective, weight, expected):
    fixture, candidates = routes
    body = request(fixture, objective=objective, exposure_weight=weight, max_detour_percent=100)
    scored = [score_exposure(c, segments(c, body.departure_at, 250), PollutionIndex([])) for c in candidates]
    fast, slow = sorted(scored, key=lambda r: r["duration_s"])
    # Artificial scoring costs only; no measured/provider concentrations are asserted.
    fast["estimated_pm25_exposure_ug_h_m3"] = 10
    slow["estimated_pm25_exposure_ug_h_m3"] = 1
    result = rank_routes(scored, body)
    assert result["selected_candidate_key"] == (fast if expected == "fast" else slow)["candidate_key"]


def test_zero_weight_pollution_does_not_block_weather_but_is_never_filled(routes):
    fixture, candidates = routes
    body = request(fixture, exposure_weight=0, weather_weight=0.8, max_detour_percent=100)
    scored = [score_exposure(c, segments(c, body.departure_at, 250), PollutionIndex([])) for c in candidates]
    fast, slow = sorted(scored, key=lambda r: r["duration_s"])
    fast["weather"] = {"preference_cost": 1}
    slow["weather"] = {"preference_cost": 0}
    result = rank_routes(scored, body)
    assert result["selected_candidate_key"] == slow["candidate_key"]
    assert result["recommendations"]["lowest_exposure"] is None
    assert all(r["estimated_pm25_exposure_ug_h_m3"] is None for r in result["routes"])
    body.exposure_weight = 0.1
    assert rank_routes(scored, body)["recommendations"]["balanced"] is None


def test_climbing_priority_changes_choice_without_changing_pollution(routes):
    fixture, candidates = routes
    body = request(fixture, mode="cycling", exposure_weight=0, terrain_weight=0.8, max_detour_percent=100)
    scored = [score_exposure(c, segments(c, body.departure_at, 250), PollutionIndex([])) for c in candidates]
    fast, slow = sorted(scored, key=lambda r: r["duration_s"])
    fast["terrain"] = {"ascent_m": 100}
    slow["terrain"] = {"ascent_m": 0}
    result = rank_routes(scored, body)
    assert result["selected_candidate_key"] == slow["candidate_key"]
    assert all(r["estimated_pm25_exposure_ug_h_m3"] is None for r in result["routes"])
    body.max_detour_percent = 0
    result = rank_routes(scored, body)
    assert result["selected_candidate_key"] == fast["candidate_key"]
    assert not slow["within_detour_limit"]
