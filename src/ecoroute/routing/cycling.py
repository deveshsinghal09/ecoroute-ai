"""Explicit bicycle routing; never relabel a car route as a cycle route."""
from datetime import UTC, datetime

import httpx

from ecoroute.routing.models import RoutingError
from ecoroute.routing.providers import valid_world_point, validate_candidate


class OpenRouteCycling:
    name = "openrouteservice"

    def __init__(self, key, reserve=lambda: None, client=None):
        self.key, self.reserve = key, reserve
        self.client = client or httpx.Client(timeout=4, follow_redirects=False)

    def candidates(self, origin, destination, request):
        if request.mode != "cycling":
            raise RoutingError("cycling_mode_required", 422)
        key = self.key() if callable(self.key) else self.key
        if not key:
            raise RoutingError("cycling_key_missing")
        self.reserve()
        body = {"coordinates": [origin, destination], "units": "m", "instructions": False}
        if request.max_alternatives:
            body["alternative_routes"] = {"target_count": min(3, request.max_alternatives + 1)}
        try:
            response = self.client.post(
                "https://api.heigit.org/openrouteservice/v2/directions/cycling-regular/geojson",
                json=body, headers={"Authorization": key},
            )
            if response.status_code in (401, 403):
                raise RoutingError("cycling_access_unavailable")
            if response.status_code == 429:
                raise RoutingError("cycling_quota_exceeded", 429)
            if response.status_code in (400, 404, 422):
                raise RoutingError("cycling_request_rejected", 422)
            if response.status_code != 200 or len(response.content) > 2 * 1024 * 1024:
                raise RoutingError("cycling_provider_unavailable")
            data = response.json()
        except (httpx.HTTPError, ValueError):
            raise RoutingError("cycling_provider_unavailable") from None
        result = []
        try:
            if data["type"] != "FeatureCollection" or not isinstance(data["features"], list):
                raise ValueError()
            for feature in data["features"][:min(3, request.max_alternatives + 1)]:
                if feature["type"] != "Feature" or feature["geometry"]["type"] != "LineString":
                    raise ValueError()
                summary = feature["properties"]["summary"]
                if isinstance(summary["distance"], bool) or isinstance(summary["duration"], bool):
                    raise ValueError()
                result.append(validate_candidate({
                    "provider": self.name, "mode": "cycling",
                    "legs": [{"coordinates": feature["geometry"]["coordinates"], "duration_s": summary["duration"]}],
                    "distance_m": summary["distance"],
                    "warnings": [
                        "Bicycle paths depend on OpenStreetMap coverage; review local access and safety.",
                        "At most three provider routes requested; alternatives are not guaranteed.",
                        "Departure selects pollution forecasts, not future bicycle traffic.",
                        "Segment timing assumes uniform speed along the returned geometry.",
                    ],
                    "routing_source": {"provider": self.name, "profile": "cycling-regular", "fixture": False,
                                       "attribution": "openrouteservice / © OpenStreetMap contributors",
                                       "collected_at": datetime.now(UTC).isoformat()},
                }, origin, destination))
        except (KeyError, TypeError, ValueError):
            raise RoutingError("cycling_schema_changed", 502) from None
        if not result:
            raise RoutingError("cycling_no_route", 422)
        return list({r["candidate_key"]: r for r in result}.values())


class GoogleModeRouting:
    name = "google_routes"
    persist_results = False
    validate_location = staticmethod(valid_world_point)

    def __init__(self, google, cycling=None):
        self.google, self.cycling = google, cycling

    def validate_mode(self, request):
        if request.mode == "cycling" and self.cycling is None:
            raise RoutingError("cycling_provider_not_configured", 422)

    def resolve(self, place):
        return self.google.resolve(place)

    def candidates(self, origin, destination, request):
        self.validate_mode(request)
        provider = self.cycling if request.mode == "cycling" else self.google
        return provider.candidates(origin, destination, request)
