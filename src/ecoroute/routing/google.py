"""Google Routes + Places adapter. Keys only in headers; never log response bodies."""
from datetime import UTC, datetime

import httpx

from ecoroute.routing.geometry import distance
from ecoroute.routing.models import RoutingError
from ecoroute.routing.providers import valid_world_point, validate_candidate


class GoogleRoutes:
    name = "google_routes"
    persist_results = False
    validate_location = staticmethod(valid_world_point)

    def __init__(self, key, reserve=lambda: None, client=None):
        self.key, self.reserve = key, reserve
        self.client = client or httpx.Client(timeout=4, follow_redirects=False)

    def call(self, url, body, mask):
        key = self.key() if callable(self.key) else self.key
        if not key:
            raise RoutingError("google_routes_key_missing")
        self.reserve()
        try:
            response = self.client.post(url, json=body, headers={
                "X-Goog-Api-Key": key, "X-Goog-FieldMask": mask,
            })
            if response.status_code in (401, 403):
                raise RoutingError("google_access_or_billing_unavailable")
            if response.status_code == 429:
                raise RoutingError("google_quota_exceeded", 429)
            if response.status_code == 400:
                raise RoutingError("google_route_request_rejected", 422)
            if response.status_code != 200 or len(response.content) > 2 * 1024 * 1024:
                raise RoutingError("google_provider_unavailable")
            value = response.json()
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (httpx.HTTPError, ValueError):
            raise RoutingError("google_provider_unavailable") from None

    def resolve(self, place):
        if not isinstance(place, str):
            return valid_world_point([place.longitude, place.latitude])
        data = self.call("https://places.googleapis.com/v1/places:searchText", {
            "textQuery": place, "pageSize": 2,
        }, "places.location")
        try:
            points = [valid_world_point([p["location"]["longitude"], p["location"]["latitude"]]) for p in data.get("places", [])]
            if not points:
                raise RoutingError("geocoding_no_match", 422)
            if len(points) > 1 and distance(points[0], points[1]) > 500:
                raise RoutingError("geocoding_ambiguous_use_coordinates", 422)
            return points[0]
        except (KeyError, TypeError, ValueError):
            raise RoutingError("google_geocoding_schema_changed", 502) from None

    def candidates(self, origin, destination, request):
        def waypoint(p):
            return {"location": {"latLng": {"latitude": p[1], "longitude": p[0]}}}
        body = {
            "origin": waypoint(origin), "destination": waypoint(destination),
            "travelMode": {"walking": "WALK", "cycling": "BICYCLE", "driving": "DRIVE"}[request.mode],
            "computeAlternativeRoutes": request.max_alternatives > 0,
            "polylineQuality": "HIGH_QUALITY", "polylineEncoding": "GEO_JSON_LINESTRING",
            "units": "METRIC", "languageCode": "en",
        }
        if request.mode == "driving":
            body.update(routingPreference="TRAFFIC_AWARE", departureTime=request.departure_at.astimezone(UTC).isoformat().replace("+00:00", "Z"))
        data = self.call("https://routes.googleapis.com/directions/v2:computeRoutes", body,
                         "routes.duration,routes.distanceMeters,routes.polyline.geoJsonLinestring,routes.warnings")
        result = []
        try:
            for raw in data.get("routes", [])[:request.max_alternatives + 1]:
                duration = raw["duration"]
                if not isinstance(duration, str) or not duration.endswith("s"):
                    raise ValueError()
                geometry = raw["polyline"]["geoJsonLinestring"]
                if geometry["type"] != "LineString":
                    raise ValueError()
                warnings = raw.get("warnings", [])
                if not isinstance(warnings, list) or not all(isinstance(w, str) for w in warnings):
                    raise ValueError()
                warnings += ["Google route is request-only; saved route retrieval is unavailable.",
                             "Segment timing assumes uniform speed along the returned geometry."]
                if request.mode != "driving":
                    warnings += ["Walking and bicycling routes may be missing sidewalks or cycling paths. Use caution.",
                                 "Departure time selects pollution forecasts; walking/cycling duration is not traffic-predicted."]
                result.append(validate_candidate({
                    "provider": self.name, "mode": request.mode,
                    "legs": [{"coordinates": geometry["coordinates"], "duration_s": float(duration[:-1])}],
                    "distance_m": raw["distanceMeters"], "warnings": warnings,
                    "routing_source": {"provider": self.name, "fixture": False,
                                       "attribution": "Google Maps", "persistence": "request_only",
                                       "collected_at": datetime.now(UTC).isoformat()},
                }, origin, destination))
        except (KeyError, TypeError, ValueError):
            raise RoutingError("google_route_schema_changed", 502) from None
        if not result:
            raise RoutingError("google_no_route_for_selected_mode", 422)
        return list({r["candidate_key"]: r for r in result}.values())
