"""Only remote routing providers generate candidates. No straight-line fallback exists."""

import math
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from botocore.exceptions import BotoCoreError, ClientError

from ecoroute.routing.geometry import decode_flexible, distance, validate_line
from ecoroute.routing.models import RoutingError
from ecoroute.storage import fingerprint


class RoutingProvider(Protocol):
    name: str

    def resolve(self, place) -> list[float]: ...
    def candidates(self, origin, destination, request) -> list[dict]: ...


def in_delhi(p):
    if not 76.8 <= p[0] <= 77.6 or not 28.3 <= p[1] <= 29.0:
        raise RoutingError("outside_supported_delhi_area", 422)
    return p


def validate_candidate(candidate, origin, destination):
    coordinates = []
    duration = 0
    for leg in candidate["legs"]:
        line = validate_line(leg["coordinates"])
        if coordinates and distance(coordinates[-1], line[0]) > 1:
            raise RoutingError("disconnected_provider_legs", 502)
        leg["coordinates"] = line
        coordinates.extend(line if not coordinates else line[1:])
        value = leg["duration_s"]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise RoutingError("invalid_provider_duration", 502)
        duration += value
    if not coordinates or len(coordinates) > 10000:
        raise RoutingError("invalid_provider_geometry", 502)
    if distance(coordinates[0], origin) > 250 or distance(coordinates[-1], destination) > 250:
        raise RoutingError("provider_snapping_too_far", 422)
    length = sum(distance(a, b) for a, b in zip(coordinates[:-1], coordinates[1:], strict=True))
    reported = candidate["distance_m"]
    if not math.isfinite(reported) or not 1 <= reported <= 100000 or not 1 <= duration <= 21600:
        raise RoutingError("route_outside_demo_limits", 422)
    if length <= 0 or abs(length - reported) / reported > 0.25:
        raise RoutingError("provider_distance_geometry_mismatch", 502)
    candidate.update(
        geometry={"type": "LineString", "coordinates": coordinates},
        duration_s=duration,
        candidate_key=fingerprint(coordinates),
    )
    return candidate


class AmazonLocation:
    name = "amazon_location_v2"

    def __init__(self, routes, places, reserve=lambda: None):
        self.routes, self.places, self.reserve = routes, places, reserve

    def call(self, method, **kwargs):
        self.reserve()
        try:
            return method(**kwargs)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {
                "AccessDeniedException",
                "SubscriptionRequiredException",
                "UnrecognizedClientException",
                "ExpiredTokenException",
            }:
                raise RoutingError("location_access_unavailable") from None
            if code in {"ValidationException", "ResourceNotFoundException"}:
                raise RoutingError("location_request_rejected", 422) from None
            raise RoutingError("location_provider_unavailable") from None
        except BotoCoreError:
            raise RoutingError("location_provider_unavailable") from None

    def resolve(self, place):
        if not isinstance(place, str):
            return in_delhi([place.longitude, place.latitude])
        result = self.call(
            self.places.geocode,
            QueryText=place,
            MaxResults=2,
            Filter={"IncludeCountries": ["IND"]},
            BiasPosition=[77.209, 28.6139],
            IntendedUse="Storage",
        )
        items = result.get("ResultItems", [])
        if not items:
            raise RoutingError("geocoding_no_match", 422)
        positions = []
        for item in items:
            point = item.get("Position")
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(
                    isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in point
                )
                or not -180 <= point[0] <= 180
                or not -90 <= point[1] <= 90
            ):
                raise RoutingError("invalid_geocoding_response", 502)
            if item.get("PlaceType") in {
                "Locality",
                "Region",
                "SubRegion",
                "Country",
                "District",
                "SubDistrict",
                "PostalCode",
                "Block",
                "SubBlock",
            }:
                raise RoutingError("geocoding_too_broad_use_coordinates", 422)
            positions.append(point)
        if len(positions) > 1 and distance(positions[0], positions[1]) > 500:
            raise RoutingError("geocoding_ambiguous_use_coordinates", 422)
        p = positions[0]
        return in_delhi(p)

    def candidates(self, origin, destination, request):
        mode = {"walking": "Pedestrian", "driving": "Car"}.get(request.mode)
        if not mode:
            raise RoutingError("cycling_not_supported_by_amazon_routes_v2", 422)
        response = self.call(
            self.routes.calculate_routes,
            Origin=origin,
            Destination=destination,
            TravelMode=mode,
            DepartureTime=request.departure_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            MaxAlternatives=request.max_alternatives,
            OptimizeRoutingFor="FastestRoute",
            LegGeometryFormat="FlexiblePolyline",
            LegAdditionalFeatures=["Summary"],
        )
        return self.parse(response, origin, destination, request.mode)

    @staticmethod
    def parse(response, origin, destination, mode):
        result = []
        try:
            for raw in response["Routes"]:
                legs = []
                for leg in raw["Legs"]:
                    if leg["Type"] not in {"Vehicle", "Pedestrian"}:
                        raise RoutingError("non_road_leg_not_supported", 422)
                    if leg.get("TravelMode") not in (
                        {"Car", "Pedestrian"} if mode == "driving" else {"Pedestrian"}
                    ):
                        raise RoutingError("provider_travel_mode_mismatch", 502)
                    geometry = leg["Geometry"]
                    line = (
                        decode_flexible(geometry["Polyline"])
                        if "Polyline" in geometry
                        else validate_line(geometry["LineString"])
                    )
                    detail = leg[leg["Type"] + "LegDetails"]
                    legs.append(
                        {
                            "coordinates": line,
                            "duration_s": detail["Summary"]["Overview"]["Duration"],
                        }
                    )
                summary = raw["Summary"]
                if abs(sum(part["duration_s"] for part in legs) - summary["Duration"]) > max(
                    2, len(legs)
                ):
                    raise RoutingError("provider_duration_mismatch", 502)
                result.append(
                    validate_candidate(
                        {
                            "provider": "amazon_location_v2",
                            "legs": legs,
                            "distance_m": summary["Distance"],
                            "mode": mode,
                            "routing_source": {
                                "provider": "amazon_location_v2",
                                "pricing_bucket": response.get("PricingBucket"),
                                "collected_at": datetime.now(UTC).isoformat(),
                                "attribution": "Amazon Location Service and its data providers",
                                "attribution_url": "https://docs.aws.amazon.com/location/latest/developerguide/data-attribution.html",
                                "notices": response.get("Notices", []),
                                "leg_notices": [
                                    notice for part in raw["Legs"]
                                    for notice in part[part["Type"] + "LegDetails"].get("Notices", [])
                                ],
                                "fixture": False,
                            },
                            "warnings": [
                                "Segment timing assumes uniform speed within each provider leg; not turn-by-turn traffic timing."
                            ],
                        },
                        origin,
                        destination,
                    )
                )
        except (KeyError, TypeError, ValueError):
            raise RoutingError("location_schema_changed", 502) from None
        if not result:
            raise RoutingError("no_road_route_available", 422)
        return list({r["candidate_key"]: r for r in result}.values())


class OsrmProvider:
    """Explicit opt-in fallback. Endpoint is server configuration, never a request URL."""

    name = "osrm"

    def __init__(self, base_url, reserve=lambda: None, client=None):
        u = urlsplit(base_url)
        if (
            u.scheme != "https"
            or not u.hostname
            or u.username
            or u.query
            or u.fragment
            or u.path not in ("", "/")
        ):
            raise ValueError("OSRM requires an operator-configured HTTPS origin")
        self.url, self.reserve, self.client = (
            base_url.rstrip("/"),
            reserve,
            client or httpx.Client(timeout=4, follow_redirects=False),
        )

    def resolve(self, place):
        if isinstance(place, str):
            raise RoutingError("fallback_requires_coordinates", 422)
        return in_delhi([place.longitude, place.latitude])

    def candidates(self, origin, destination, request):
        if request.mode != "driving":
            raise RoutingError("fallback_driving_only", 422)
        self.reserve()
        coordinates = ";".join(",".join(str(v) for v in p) for p in (origin, destination))
        try:
            response = self.client.get(
                self.url + "/route/v1/driving/" + coordinates,
                params={
                    "alternatives": str(request.max_alternatives)
                    if request.max_alternatives
                    else "false",
                    "steps": "false",
                    "overview": "full",
                    "geometries": "geojson",
                },
            )
            if response.status_code != 200 or len(response.content) > 2 * 1024 * 1024:
                raise RoutingError("fallback_provider_unavailable")
            return self.parse(response.json(), origin, destination)
        except (httpx.HTTPError, ValueError):
            raise RoutingError("fallback_provider_unavailable") from None

    @staticmethod
    def parse(payload, origin, destination, *, fixture=False, collected_at=None):
        if payload.get("code") != "Ok" or not payload.get("routes"):
            raise RoutingError("no_road_route_available", 422)
        result = []
        try:
            for route in payload["routes"][:6]:
                if route["geometry"]["type"] != "LineString":
                    raise RoutingError("invalid_provider_geometry", 502)
                result.append(
                    validate_candidate(
                        {
                            "provider": "osrm",
                            "mode": "driving",
                            "legs": [
                                {
                                    "coordinates": route["geometry"]["coordinates"],
                                    "duration_s": route["duration"],
                                }
                            ],
                            "distance_m": route["distance"],
                            "routing_source": {
                                "provider": "osrm",
                                "fixture": fixture,
                                "collected_at": collected_at or datetime.now(UTC).isoformat(),
                                "attribution": "OSRM; OpenStreetMap contributors (ODbL)",
                                "data_version": payload.get("data_version"),
                            },
                            "warnings": [
                                "Explicit OSRM fallback: driving only, static travel times; departure traffic is not modeled.",
                                "Segment timing assumes uniform speed along the supplied route.",
                            ],
                        },
                        origin,
                        destination,
                    )
                )
        except (KeyError, TypeError, ValueError):
            raise RoutingError("fallback_schema_changed", 502) from None
        return list({r["candidate_key"]: r for r in result}.values())
