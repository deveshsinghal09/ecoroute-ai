"""Offline provider contracts and public-request isolation, not live bicycle coverage."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from ecoroute.config import Settings
from ecoroute.environment.repository import LocalRepository
from ecoroute.main import create_app
from ecoroute.models import Point
from ecoroute.routing.cycling import DelhiGoogleRouting, OpenRouteCycling
from ecoroute.routing.google import GoogleRoutes
from ecoroute.routing.models import PreviewRequest, RoutingError
from ecoroute.routing.pollution import PollutionIndex
from ecoroute.routing.service import RouteService, create_service
from ecoroute.storage import LocalStore


@pytest.fixture
def route_contract():
    # Reuse captured road geometry to exercise parsing/scoring only. This fixture
    # is not evidence that ORS returned a Delhi bicycle route.
    saved = json.loads(Path("tests/fixtures/delhi_osrm_routes.json").read_text())
    road = saved["payload"]["routes"][0]
    request = PreviewRequest(
        origin=Point(longitude=saved["origin"][0], latitude=saved["origin"][1]),
        destination=Point(longitude=saved["destination"][0], latitude=saved["destination"][1]),
        departure_at=datetime.now(UTC) + timedelta(minutes=10), mode="cycling",
    )
    payload = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": road["geometry"],
        "properties": {"summary": {"distance": road["distance"], "duration": 1800}}}]}
    return saved, request, payload


def test_cycle_profile_header_units_geometry_and_budget(route_contract):
    saved, request, payload = route_contract
    reservations = []
    def handler(wire):
        assert str(wire.url) == "https://api.heigit.org/openrouteservice/v2/directions/cycling-regular/geojson"
        assert wire.headers["Authorization"] == "private-test-key"
        assert "private-test-key" not in str(wire.url)
        body = json.loads(wire.content)
        assert body["coordinates"] == [saved["origin"], saved["destination"]]
        assert body["units"] == "m" and body["alternative_routes"]["target_count"] == 3
        return httpx.Response(200, json=payload)
    provider = OpenRouteCycling("private-test-key", reserve=lambda: reservations.append(1),
                               client=httpx.Client(transport=httpx.MockTransport(handler)))
    route = provider.candidates(saved["origin"], saved["destination"], request)[0]
    assert reservations == [1]
    assert route["mode"] == "cycling" and route["duration_s"] == 1800
    assert route["distance_m"] == payload["features"][0]["properties"]["summary"]["distance"]
    assert route["geometry"] == payload["features"][0]["geometry"]


@pytest.mark.parametrize("status,code", [(403, "cycling_access_unavailable"), (429, "cycling_quota_exceeded"),
    (400, "cycling_request_rejected"), (500, "cycling_provider_unavailable")])
def test_provider_failures_never_echo_body(route_contract, status, code):
    saved, request, _ = route_contract
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status, json={"error": "secret-coordinate"})))
    with pytest.raises(RoutingError, match=code) as raised:
        OpenRouteCycling("secret-coordinate", client=client).candidates(saved["origin"], saved["destination"], request)
    assert "secret-coordinate" not in str(raised.value)


@pytest.mark.parametrize("body,code", [({}, "cycling_schema_changed"),
    ({"type": "FeatureCollection", "features": [{}]}, "cycling_schema_changed"),
    ({"type": "FeatureCollection", "features": []}, "cycling_no_route")])
def test_schema_change_and_missing_route(route_contract, body, code):
    saved, request, _ = route_contract
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    with pytest.raises(RoutingError, match=code):
        OpenRouteCycling("key", client=client).candidates(saved["origin"], saved["destination"], request)


def test_missing_cycle_key_no_network(route_contract):
    saved, request, _ = route_contract
    def unexpected(_):
        pytest.fail("Missing credentials must not send a request")
    with pytest.raises(RoutingError, match="cycling_key_missing"):
        OpenRouteCycling("", client=httpx.Client(transport=httpx.MockTransport(unexpected))).candidates(saved["origin"], saved["destination"], request)


def test_missing_cycle_configuration_precedes_geocoding(tmp_path, route_contract):
    _, request, _ = route_contract
    settings = Settings(_env_file=None, routing_provider="google")
    engine = create_service(settings, LocalStore(str(tmp_path / "state.db")), LocalRepository(tmp_path / "objects"))
    with pytest.raises(RoutingError, match="cycling_provider_not_configured"):
        engine.compare("guest", request.model_copy(update={"origin": "India Gate Delhi"}))
    assert "private-key" not in repr(Settings(_env_file=None, openrouteservice_api_key="private-key"))


def test_guest_cycle_scoring_stays_request_only_and_private_routes_require_auth(tmp_path, route_contract):
    _, request, payload = route_contract
    store = LocalStore(str(tmp_path / "state.db"))
    objects = LocalRepository(tmp_path / "objects")
    cycle = OpenRouteCycling("test", client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))))
    provider = DelhiGoogleRouting(GoogleRoutes(""), cycle)
    app = create_app(Settings(_env_file=None, routing_provider="google", enable_guest_routes=True), store=store)
    app.state.route_service = RouteService(provider, store, objects, index_factory=lambda *_: PollutionIndex([]))
    client = TestClient(app)
    result = client.post("/api/v1/routes/preview", json=request.model_dump(mode="json"))
    assert result.status_code == 200
    assert result.json()["persistence"] == "request_only"
    assert result.json()["routes"][0]["routing_source"]["profile"] == "cycling-regular"
    assert result.json()["routes"][0]["estimated_pm25_exposure_ug_h_m3"] is None
    assert not list((tmp_path / "objects").rglob("*.json"))
    assert client.post("/api/v1/routes/compare", json=request.model_dump(mode="json")).status_code == 401
    assert client.get("/api/v1/wearables/latest").status_code == 401
    assert client.post("/api/v1/routes/preview", json={**request.model_dump(mode="json"), "consent_to_store": True}).status_code == 422


def test_guest_disabled_does_not_initialize_providers(route_contract):
    _, request, _ = route_contract
    app = create_app(Settings(_env_file=None, local_db_path=":memory:"))
    result = TestClient(app).post("/api/v1/routes/preview", json=request.model_dump(mode="json"))
    assert result.status_code == 503 and result.json()["error"]["code"] == "guest_routes_disabled"
    assert not hasattr(app.state, "route_service")
