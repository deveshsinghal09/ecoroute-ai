import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from ecoroute.config import Settings
from ecoroute.models import Point
from ecoroute.routing.google import GoogleRoutes
from ecoroute.routing.models import CompareRequest, RoutingError
from ecoroute.routing.service import RouteService, create_service
from ecoroute.routing.pollution import PollutionIndex
from ecoroute.environment.repository import LocalRepository
from ecoroute.storage import LocalStore


@pytest.fixture
def setup():
    saved = json.loads(Path("tests/fixtures/delhi_osrm_routes.json").read_text())
    req = CompareRequest(origin=Point(longitude=saved["origin"][0], latitude=saved["origin"][1]),
                         destination=Point(longitude=saved["destination"][0], latitude=saved["destination"][1]),
                         departure_at=datetime.now(UTC)+timedelta(minutes=10), consent_to_store=True)
    route = saved["payload"]["routes"][0]
    return saved, req, {"routes": [{"duration": f"{route['duration']}s", "distanceMeters": route["distance"],
                                 "polyline": {"geoJsonLinestring": route["geometry"]}, "warnings": []}]}


@pytest.mark.parametrize("mode,wire", [("walking", "WALK"), ("cycling", "BICYCLE"), ("driving", "DRIVE")])
def test_modes_and_header_secret(setup, mode, wire):
    saved, req, payload = setup
    def handler(request):
        body = json.loads(request.content)
        assert body["travelMode"] == wire
        assert body["origin"]["location"]["latLng"]["longitude"] == saved["origin"][0]
        assert ("departureTime" in body) == (mode == "driving")
        assert request.headers["X-Goog-Api-Key"] == "test-only"
        assert "test-only" not in str(request.url)
        return httpx.Response(200, json=payload)
    provider = GoogleRoutes("test-only", client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = provider.candidates(saved["origin"], saved["destination"], req.model_copy(update={"mode": mode}))
    assert result[0]["geometry"]["coordinates"] == payload["routes"][0]["polyline"]["geoJsonLinestring"]["coordinates"]


@pytest.mark.parametrize("status,code", [(403,"google_access_or_billing_unavailable"),(429,"google_quota_exceeded"),(500,"google_provider_unavailable")])
def test_failures_redacted(setup,status,code):
    saved,req,_=setup
    client=httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(status,json={"error":"secret"})))
    with pytest.raises(RoutingError,match=code):
        GoogleRoutes("secret",client=client).candidates(saved["origin"],saved["destination"],req)


def test_empty_and_schema(setup):
    saved,req,_=setup
    for body,code in [({"routes":[]},"google_no_route"),({"routes":[{}]},"google_route_schema")]:
        client=httpx.Client(transport=httpx.MockTransport(lambda _,b=body:httpx.Response(200,json=b)))
        with pytest.raises(RoutingError,match=code):
            GoogleRoutes("test",client=client).candidates(saved["origin"],saved["destination"],req)


def test_google_comparison_not_persisted(setup,tmp_path):
    _,req,payload=setup
    client=httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=payload)))
    store=LocalStore(str(tmp_path/"state.db"))
    objects=LocalRepository(tmp_path/"objects")
    provider=GoogleRoutes("test",client=client)
    engine=RouteService(provider,store,objects,index_factory=lambda *_:PollutionIndex([]))
    result=engine.compare("owner",req.model_copy(update={"mode":"cycling"}))
    assert result["persistence"]=="request_only"
    assert store.get("routes","owner",result["selected_route_id"]) is None
    assert not list((tmp_path/"objects").rglob("*.json"))


def test_missing_key_no_network(tmp_path):
    settings=Settings(routing_provider="google",osrm_base_url="",google_routes_api_key="")
    engine=create_service(settings,LocalStore(str(tmp_path/"s.db")),LocalRepository(tmp_path/"objects"))
    with pytest.raises(RoutingError,match="google_routes_key_missing"):
        engine.provider.resolve("India Gate Delhi")
    assert "hidden-secret" not in repr(Settings(google_routes_api_key="hidden-secret"))


def test_geocoding_is_not_forced_to_delhi_or_india():
    def handler(request):
        body = json.loads(request.content)
        assert body == {"textQuery": "A precise Mumbai landmark", "pageSize": 2}
        return httpx.Response(200, json={"places": [{"location": {"longitude": 72.8347, "latitude": 18.922}}]})
    provider = GoogleRoutes("test-only", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert provider.resolve("A precise Mumbai landmark") == [72.8347, 18.922]
    assert provider.resolve(Point(longitude=-0.1278, latitude=51.5074)) == [-0.1278, 51.5074]


def test_comparison_passes_global_coordinates_to_google_provider(tmp_path):
    from ecoroute.routing.cycling import GoogleModeRouting
    class Provider(GoogleRoutes):
        def candidates(self, origin, destination, request):
            assert origin == [72.8347, 18.922] and destination == [72.8258, 18.9352]
            raise RoutingError("test_provider_reached_without_city_restriction")
    request = CompareRequest(origin=Point(longitude=72.8347, latitude=18.922),
        destination=Point(longitude=72.8258, latitude=18.9352),
        departure_at=datetime.now(UTC)+timedelta(minutes=10), consent_to_store=True, mode="walking")
    engine = RouteService(GoogleModeRouting(Provider("test")), LocalStore(str(tmp_path/"state.db")), LocalRepository(tmp_path/"objects"))
    with pytest.raises(RoutingError, match="test_provider_reached_without_city_restriction"):
        engine.compare("owner", request)


@pytest.mark.parametrize("point", [[181, 20], [77, 91], [float("nan"), 20], [True, 20], [77], "untrusted"])
def test_global_coordinate_validation_rejects_bad_values(point):
    from ecoroute.routing.providers import valid_world_point
    with pytest.raises(RoutingError, match="invalid_geocoding_coordinates"):
        valid_world_point(point)
