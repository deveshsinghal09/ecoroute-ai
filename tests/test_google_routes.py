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
