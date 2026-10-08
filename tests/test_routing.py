"""Phase 3 validation: recorded genuine road geometry; synthetic pollution is test-only."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import boto3
import httpx
import pytest
from botocore.stub import Stubber
from pydantic import ValidationError

from ecoroute.environment.repository import LocalRepository
from ecoroute.models import Point
from ecoroute.routing.api import service
from ecoroute.routing.geometry import decode_flexible, distance, segments
from ecoroute.routing.models import CompareRequest, DepartureRequest, ExposureRequest, RoutingError
from ecoroute.routing.pollution import PollutionIndex, rank_routes, score_exposure
from ecoroute.routing.providers import AmazonLocation, OsrmProvider, in_delhi
from ecoroute.routing.service import RouteService
from ecoroute.storage import LocalStore


@pytest.fixture
def recording():
    return json.loads(Path("tests/fixtures/delhi_osrm_routes.json").read_text(encoding="utf-8"))


@pytest.fixture
def candidates(recording):
    return OsrmProvider.parse(
        recording["payload"],
        recording["origin"],
        recording["destination"],
        fixture=True,
        collected_at=recording["collected_at"],
    )


@pytest.fixture
def request_model(recording):
    return CompareRequest(
        origin=Point(longitude=recording["origin"][0], latitude=recording["origin"][1]),
        destination=Point(
            longitude=recording["destination"][0], latitude=recording["destination"][1]
        ),
        mode="driving",
        departure_at=datetime.now(UTC) + timedelta(minutes=10),
        consent_to_store=True,
    )


def synthetic_rows(when, value=36, source="open_meteo"):
    """Explicit fabricated arithmetic inputs, never production fallback data."""
    clock = datetime.now(UTC)
    return [
        {
            "record_id": "synthetic-pm25",
            "source": source,
            "kind": "forecast" if source == "open_meteo" else "observed",
            "pollutant": "pm25",
            "value": value,
            "unit": "ug/m3",
            "quality_flags": [],
            "latitude": 28.8,
            "longitude": 77.2,
            "location_id": "synthetic-grid",
            "sensor_id": None,
            "reported_at": when.isoformat(),
            "collected_at": clock.isoformat(),
            "resolution_km": 45,
            "native_interval_hours": 3,
            "provider_quality": "not_supplied",
            "raw_key": "SYNTHETIC_TEST_ONLY",
        }
    ]


@pytest.fixture
def engine(candidates, request_model, tmp_path):
    class Recorded:
        name = "recorded_osrm_test_only"
        calls = 0

        def resolve(self, p):
            return in_delhi([p.longitude, p.latitude])

        def candidates(self, origin, destination, request):
            self.calls += 1
            return copy.deepcopy(candidates)

    rows = synthetic_rows(request_model.departure_at)
    return RouteService(
        Recorded(),
        LocalStore(":memory:"),
        LocalRepository(tmp_path),
        index_factory=lambda a, b: PollutionIndex(rows),
    )


def test_real_geometry_preserved_and_distance_segmentation(candidates, request_model, recording):
    assert recording["fixture_type"] == "recorded_live_public_landmark_routes"
    assert len(candidates) == 2
    for route, raw in zip(candidates, recording["payload"]["routes"], strict=True):
        assert route["geometry"] == raw["geometry"]
        assert len(route["geometry"]["coordinates"]) > 50
        assert route["distance_m"] > distance(recording["origin"], recording["destination"])
        pieces = segments(route, request_model.departure_at, 250)
        assert all(s["length_m"] <= 250.001 for s in pieces)
        assert sum(s["duration_s"] for s in pieces) == pytest.approx(route["duration_s"])
        assert pieces[0]["geometry"]["coordinates"][0] == route["geometry"]["coordinates"][0]
        assert pieces[-1]["geometry"]["coordinates"][-1] == route["geometry"]["coordinates"][-1]
        for a, b in zip(pieces[:-1], pieces[1:], strict=True):
            assert a["geometry"]["coordinates"][-1] == b["geometry"]["coordinates"][0]
            assert a["end_at"] == b["arrival_at"]
        retained = [p for s in pieces for p in s["geometry"]["coordinates"]]
        assert all(p in retained for p in raw["geometry"]["coordinates"])


def test_exposure_hours_arithmetic_and_single_grid_warning(candidates, request_model):
    index = PollutionIndex(synthetic_rows(request_model.departure_at, 36))
    scored = [
        score_exposure(c, segments(c, request_model.departure_at, 250), index) for c in candidates
    ]
    result = rank_routes(scored, request_model)
    for route in result["routes"]:
        assert route["estimated_pm25_exposure_ug_h_m3"] == pytest.approx(
            36 * route["duration_s"] / 3600
        )
        assert sum(s["pm25_exposure_ug_h_m3"] for s in route["segments"]) == pytest.approx(
            route["estimated_pm25_exposure_ug_h_m3"]
        )
        assert route["pm25_coverage_fraction"] == pytest.approx(1)
    assert result["spatial_differentiation"] == "not_resolved_same_model_cell"
    assert any("not demonstrated street-level" in w for w in result["routes"][0]["warnings"])
    slow = max(scored, key=lambda r: r["duration_s"])
    assert slow["relative_exposure_change_percent"] > 0


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "stale",
        "distant",
        "wrong_unit",
        "flagged",
        "future_collection",
        "future_observation",
    ],
)
def test_unavailable_never_zero(candidates, request_model, fault):
    rows = synthetic_rows(request_model.departure_at)
    if fault == "missing":
        rows = []
    elif fault == "stale":
        rows[0]["collected_at"] = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    elif fault == "distant":
        rows[0]["latitude"] = 29.5
    elif fault == "wrong_unit":
        rows[0]["unit"] = "AQI"
    elif fault == "flagged":
        rows[0]["quality_flags"] = ["provider_flagged"]
    elif fault == "future_collection":
        rows[0]["collected_at"] = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    else:
        rows[0].update(source="openaq", kind="observed")
    score = score_exposure(
        candidates[0],
        segments(candidates[0], request_model.departure_at, 250),
        PollutionIndex(rows),
    )
    assert score["estimated_pm25_exposure_ug_h_m3"] is None
    assert score["pm25_coverage_fraction"] == 0
    assert score["relative_exposure_change_percent"] is None


def test_station_radius_and_timestamp_limits():
    clock = datetime.now(UTC)
    rows = synthetic_rows(clock - timedelta(minutes=15), source="openaq")
    rows[0].update(latitude=28.613, longitude=77.23, location_id="synthetic-station")
    index = PollutionIndex(rows, as_of=clock + timedelta(seconds=1))
    assert index.sample([77.23, 28.613], clock)["status"] == "observed"
    assert index.sample([77.3, 28.7], clock)["status"] == "unavailable"
    rows[0]["reported_at"] = (clock - timedelta(hours=2)).isoformat()
    assert index.sample([77.23, 28.613], clock)["status"] == "unavailable"


def test_partial_coverage_and_truncation_are_not_ranked(candidates, request_model):
    pieces = segments(candidates[0], request_model.departure_at, 250)

    class Partial:
        as_of = datetime.now(UTC)
        truncated = False

        def sample(self, position, when, pollutant):
            return {
                "value_ug_m3": 36
                if when == datetime.fromisoformat(pieces[0]["sample_at"])
                else None,
                "confidence": "low",
                "warnings": [],
            }

    score = score_exposure(candidates[0], pieces, Partial())
    assert 0 < score["pm25_coverage_fraction"] < 1
    assert (
        score["known_pm25_exposure_ug_h_m3"] > 0
        and score["estimated_pm25_exposure_ug_h_m3"] is None
    )
    result = rank_routes([score], request_model)
    assert result["recommendations"]["lowest_exposure"] is None
    assert result["recommendations"]["balanced"] is None
    complete = PollutionIndex(synthetic_rows(request_model.departure_at), truncated=True)
    assert (
        score_exposure(candidates[0], pieces, complete)["estimated_pm25_exposure_ug_h_m3"] is None
    )


def test_detour_normalization_and_missing_comparability(candidates, request_model):
    request_model.max_detour_percent = 5
    index = PollutionIndex(synthetic_rows(request_model.departure_at))
    routes = [
        score_exposure(c, segments(c, request_model.departure_at, 250), index) for c in candidates
    ]
    slower = max(routes, key=lambda r: r["duration_s"])
    slower["estimated_pm25_exposure_ug_h_m3"] = 0.01  # synthetic arithmetic override only
    result = rank_routes(routes, request_model)
    assert not slower["within_detour_limit"]
    assert result["selected_candidate_key"] != slower["candidate_key"]
    request_model.max_detour_percent = 100
    result = rank_routes(routes, request_model)
    assert result["recommendations"]["lowest_exposure"] == slower["candidate_key"]
    assert all(0 <= r["balanced_score"] <= 1 for r in routes)
    routes[0]["estimated_pm25_exposure_ug_h_m3"] = None
    assert rank_routes(routes, request_model)["recommendations"]["balanced"] is None


def test_zero_baseline_not_divided(candidates, request_model):
    rows = synthetic_rows(request_model.departure_at, 0)
    routes = [
        score_exposure(c, segments(c, request_model.departure_at, 250), PollutionIndex(rows))
        for c in candidates
    ]
    result = rank_routes(routes, request_model)
    assert all(r["relative_exposure_change_percent"] is None for r in routes)
    assert result["selected_candidate_key"]


def test_timezone_and_invalid_input(request_model):
    data = request_model.model_dump(mode="json")
    from datetime import timezone

    data["departure_at"] = request_model.departure_at.astimezone(
        timezone(timedelta(hours=5, minutes=30))
    ).isoformat()
    assert CompareRequest.model_validate(data).departure_at == request_model.departure_at
    data["departure_at"] = "2026-10-09T12:00:00"
    with pytest.raises(ValidationError):
        CompareRequest.model_validate(data)
    data = request_model.model_dump(mode="json")
    data["origin"] = {"longitude": float("nan"), "latitude": 28.6}
    with pytest.raises(ValidationError):
        CompareRequest.model_validate(data)
    data = request_model.model_dump(mode="json")
    data["geometry"] = {"type": "LineString", "coordinates": []}
    with pytest.raises(ValidationError):
        CompareRequest.model_validate(data)
    data = request_model.model_dump(mode="json")
    data["consent_to_store"] = False
    with pytest.raises(ValidationError):
        CompareRequest.model_validate(data)


def test_cache_ownership_and_private_storage(engine, request_model):
    result = engine.compare("alice", request_model)
    assert engine.compare("alice", request_model)["cache_hit"] is True
    assert engine.provider.calls == 1
    route_id = result["selected_route_id"]
    assert engine.read("alice", route_id)["geometry"]
    with pytest.raises(RoutingError, match="route_not_found"):
        engine.read("bob", route_id)
    engine.compare("bob", request_model)
    assert engine.provider.calls == 2
    for path in engine.objects.root.glob("reports/routes/**/*.json"):
        report = path.read_text()
        assert all(x not in report for x in ("alice", "geometry", "origin", "latitude", "route_id"))
    stored = engine.store.get("routes", "alice", route_id)
    assert stored["expires_at"] > datetime.now(UTC).timestamp()
    assert "geometry" not in stored


def test_api_auth_validation_retrieval_and_exposure(secured, engine, request_model):
    secured.app.dependency_overrides[service] = lambda: engine
    data = request_model.model_dump(mode="json")
    for endpoint in ("compare", "optimize", "exposure", "departure-time-analysis"):
        assert secured.client.post("/api/v1/routes/" + endpoint, json=data).status_code == 401
    headers = {"Authorization": "Bearer " + secured.token()}
    response = secured.client.post("/api/v1/routes/compare", json=data, headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    route_id = result["selected_route_id"]
    assert secured.client.get("/api/v1/routes/" + route_id, headers=headers).status_code == 200
    other = {"Authorization": "Bearer " + secured.token(sub="bob")}
    assert secured.client.get("/api/v1/routes/" + route_id, headers=other).status_code == 404
    piece = secured.client.get(
        "/api/v1/routes/" + route_id + "/segments?limit=2", headers=headers
    ).json()
    assert len(piece["segments"]) == 2 and piece["next_offset"] == 2
    exposure = secured.client.post(
        "/api/v1/routes/exposure", json={"route_id": route_id}, headers=headers
    )
    assert exposure.status_code == 200 and exposure.json()["estimated_pm25_exposure_ug_h_m3"] > 0
    assert (
        secured.client.post(
            "/api/v1/routes/compare", json={**data, "max_detour_percent": -1}, headers=headers
        ).status_code
        == 422
    )
    assert (
        secured.client.post(
            "/api/v1/routes/compare",
            json=data,
            headers={"Authorization": "Bearer " + secured.token(scope="ecoroute/read")},
        ).status_code
        == 403
    )
    assert (
        secured.client.post(
            "/api/v1/routes/compare", json={**data, "mode": "cycling"}, headers=headers
        ).status_code
        == 422
    )


def test_departures_are_separate_routes_and_bounded(engine, request_model):
    request = DepartureRequest(
        **request_model.model_dump(),
        departures=[request_model.departure_at, request_model.departure_at + timedelta(hours=3)],
    )
    report = engine.departure_analysis("alice", request)
    assert len(report["departures"]) == 2 and engine.provider.calls == 2
    assert report["lowest_estimated_exposure_departure"] is None  # second time lacks pollution
    assert "segments" not in report["departures"][0]["comparison"]["routes"][0]
    with pytest.raises(ValidationError):
        DepartureRequest(**request_model.model_dump(), departures=[request_model.departure_at] * 4)


def test_exposure_only_accepts_owned_provider_route(engine):
    with pytest.raises(RoutingError, match="route_not_found"):
        engine.exposure("alice", ExposureRequest(route_id="0" * 32))


def client(service_name):
    return boto3.client(
        service_name,
        region_name="ap-south-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def test_aws_real_method_schema_coordinate_order_and_failure(request_model):
    routes, places = client("geo-routes"), client("geo-places")
    provider = AmazonLocation(routes, places)
    expected = {
        "Origin": [77.2295, 28.6129],
        "Destination": [77.2167, 28.6315],
        "TravelMode": "Car",
        "DepartureTime": request_model.departure_at.isoformat().replace("+00:00", "Z"),
        "MaxAlternatives": 2,
        "OptimizeRoutingFor": "FastestRoute",
        "LegGeometryFormat": "FlexiblePolyline",
        "LegAdditionalFeatures": ["Summary"],
    }
    with Stubber(routes) as stub:
        stub.add_client_error(
            "calculate_routes",
            service_error_code="AccessDeniedException",
            service_message="private account data",
            expected_params=expected,
        )
        with pytest.raises(RoutingError, match="location_access_unavailable"):
            provider.candidates([77.2295, 28.6129], [77.2167, 28.6315], request_model)
        stub.assert_no_pending_responses()
    request_model.mode = "cycling"
    with pytest.raises(RoutingError, match="cycling_not_supported"):
        provider.candidates([77.2295, 28.6129], [77.2167, 28.6315], request_model)


@pytest.mark.parametrize(
    "items,code",
    [
        ([], "geocoding_no_match"),
        ([{"Position": [77.2, 28.6], "PlaceType": "Locality"}], "geocoding_too_broad"),
        ([{"Position": [77.2, 28.6]}, {"Position": [77.5, 28.8]}], "geocoding_ambiguous"),
        ([{"Position": [28.6, 77.2]}], "outside_supported_delhi"),
        ([{"Position": [float("nan"), 28.6]}], "invalid_geocoding"),
    ],
)
def test_invalid_geocoding(items, code):
    class Places:
        def geocode(self, **kwargs):
            assert kwargs["IntendedUse"] == "Storage" and kwargs["Filter"] == {
                "IncludeCountries": ["IND"]
            }
            return {"ResultItems": items}

    with pytest.raises(RoutingError, match=code):
        AmazonLocation(None, Places()).resolve("a place in Delhi")


def test_amazon_parser_uses_recorded_road_geometry_only(recording):
    original = recording["payload"]["routes"][0]
    # Schema mock contains recorded OSRM geometry; this is not a successful AWS response claim.
    response = {
        "Routes": [
            {
                "Legs": [
                    {
                        "Type": "Vehicle",
                        "TravelMode": "Car",
                        "Geometry": {"LineString": original["geometry"]["coordinates"]},
                        "VehicleLegDetails": {"Summary": {"Overview": {"Duration": 207}}},
                    }
                ],
                "Summary": {"Duration": 207, "Distance": 2823},
            }
        ]
    }
    result = AmazonLocation.parse(
        response, recording["origin"], recording["destination"], "driving"
    )
    assert result[0]["geometry"]["coordinates"] == original["geometry"]["coordinates"]
    response["Routes"][0]["Legs"][0]["Geometry"] = {}
    with pytest.raises(RoutingError, match="schema_changed"):
        AmazonLocation.parse(response, recording["origin"], recording["destination"], "driving")


def test_osrm_transport_no_route_no_straight_line_fallback(request_model):
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"code": "NoRoute"}))
    p = OsrmProvider("https://example.invalid", client=httpx.Client(transport=transport))
    with pytest.raises(RoutingError, match="no_road_route"):
        p.candidates([77.2, 28.6], [77.3, 28.7], request_model)
    with pytest.raises(RoutingError, match="requires_coordinates"):
        p.resolve("India Gate")


@pytest.mark.parametrize("polyline", ["", "B", "CFAA", "BF?", "BF_____", "BFg"])
def test_malformed_polyline_fails(polyline):
    with pytest.raises(RoutingError):
        decode_flexible(polyline)


def test_flexible_polyline_reference_vector():
    # HERE flexible-polyline specification example: lat/lon converted to GeoJSON lon/lat.
    points = decode_flexible("BFoz5xJ67i1B1B7PzIhaxL7Y")
    assert points[0] == pytest.approx([8.69821, 50.10228])
    assert points[-1] == pytest.approx([8.68752, 50.09878])


def test_sdk_valid_response_and_coordinate_order(recording, request_model):
    # SDK validates every required nested field. This mock is not AWS live evidence.
    road = recording["payload"]["routes"][0]
    details = {key: [] for key in (
        "AfterTravelSteps", "Incidents", "Notices", "PassThroughWaypoints", "Spans",
        "Tolls", "TollSystems", "TravelSteps", "TruckRoadTypes", "Zones")}
    details.update(TruckRoadTypes=["0"], Arrival={"Place": {"Position": recording["destination"]}},
                   Departure={"Place": {"Position": recording["origin"]}},
                   Summary={"Overview": {"Duration": 207, "Distance": 2823}})
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

    def unsigned(value):
        encoded = ""
        while value >= 32:
            encoded += alphabet[(value & 31) | 32]
            value >>= 5
        return encoded + alphabet[value]

    polyline, previous = "BG", [0, 0]  # version 1, precision 6, two dimensions
    for lon, lat in road["geometry"]["coordinates"]:
        current = [round(lat * 1e6), round(lon * 1e6)]
        for value, old in zip(current, previous, strict=True):
            delta = value - old
            polyline += unsigned(delta * 2 if delta >= 0 else -delta * 2 - 1)
        previous = current
    payload = {"LegGeometryFormat": "FlexiblePolyline", "Notices": [], "PricingBucket": "Core",
               "Routes": [{"MajorRoadLabels": [], "Summary": {"Duration": 207, "Distance": 2823},
                           "Legs": [{"Type": "Vehicle", "TravelMode": "Car",
                                     "Geometry": {"Polyline": polyline},
                                     "VehicleLegDetails": details}]}]}
    routes = client("geo-routes")
    with Stubber(routes) as stub:
        stub.add_response("calculate_routes", payload, {
            "Origin": recording["origin"], "Destination": recording["destination"],
            "TravelMode": "Car", "DepartureTime": request_model.departure_at.isoformat().replace("+00:00", "Z"),
            "MaxAlternatives": 2, "OptimizeRoutingFor": "FastestRoute",
            "LegGeometryFormat": "FlexiblePolyline", "LegAdditionalFeatures": ["Summary"]})
        result = AmazonLocation(routes, None).candidates(
            recording["origin"], recording["destination"], request_model)
        assert result[0]["duration_s"] == 207
        assert result[0]["geometry"]["coordinates"] == road["geometry"]["coordinates"]
        stub.assert_no_pending_responses()


def test_local_concurrent_request_budget_is_atomic(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from ecoroute.environment.repository import BudgetExceeded

    repo = LocalRepository(tmp_path)

    def reserve(_):
        try:
            repo.reserve("location", daily=5, hourly=5)
            return True
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(20))) == 5
