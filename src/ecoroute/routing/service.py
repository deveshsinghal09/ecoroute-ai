import json
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ecoroute.models import Point
from ecoroute.environment.repository import BudgetExceeded
from ecoroute.routing.geometry import segments
from ecoroute.routing.models import CompareRequest, RoutingError
from ecoroute.routing.pollution import PollutionIndex, rank_routes, score_exposure
from ecoroute.routing.providers import AmazonLocation, OsrmProvider, in_delhi
from ecoroute.storage import fingerprint

logger = logging.getLogger("ecoroute.routing")


class DisabledProvider:
    name = "disabled"

    def resolve(self, place):
        raise RoutingError("amazon_location_not_enabled")

    def candidates(self, origin, destination, request):
        raise RoutingError("amazon_location_not_enabled")


class RouteService:
    def __init__(self, provider, store, objects, *, index_factory=None, cache_namespace="routing-v1"):
        self.cache_namespace = cache_namespace
        self.provider, self.store, self.objects = provider, store, objects
        self.index_factory = index_factory or (
            lambda start, end: PollutionIndex.load(objects, start, end)
        )

    def read(self, owner, route_id, *, internal=False):
        meta = self.store.get("routes", owner, route_id)
        if meta is None:
            raise RoutingError("route_not_found", 404)
        try:
            body = json.loads(self.objects.get_bytes(meta["object_key"]))
        except (OSError, ValueError, KeyError):
            raise RoutingError("route_storage_unavailable") from None
        return body if internal else body["response"]

    def compare(self, owner, request):
        started = time.monotonic()
        cache_key = fingerprint([self.cache_namespace, self.provider.name, request.model_dump(mode="json")])
        cached = self.store.get("route_cache", owner, cache_key)
        if cached:
            result = json.loads(self.objects.get_bytes(cached["object_key"]))
            result["cache_hit"] = True
            return result
        if request.mode == "cycling":
            raise RoutingError("cycling_provider_not_configured", 422)
        origin = in_delhi(self.provider.resolve(request.origin))
        destination = in_delhi(self.provider.resolve(request.destination))
        if origin == destination:
            raise RoutingError("origin_equals_destination", 422)
        candidates = self.provider.candidates(origin, destination, request)
        if not candidates:
            raise RoutingError("no_road_route_available", 422)
        if len(candidates) > 6:
            raise RoutingError("provider_candidate_limit", 502)
        candidates = list({r["candidate_key"]: r for r in candidates}.values())
        index = self.index_factory(
            request.departure_at,
            request.departure_at + timedelta(seconds=max(c["duration_s"] for c in candidates)),
        )
        scored = [
            score_exposure(c, segments(c, request.departure_at, request.segment_length_m), index)
            for c in candidates
        ]
        result = rank_routes(scored, request)
        ids = {r["candidate_key"]: uuid.uuid4().hex for r in scored}
        for r in scored:
            r["route_id"] = ids[r["candidate_key"]]
            r["baseline_route_id"] = ids[r["baseline_candidate_key"]]
            r["expires_at"] = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        result["recommended_route_ids"] = {
            k: ids[v] if v else None for k, v in result.pop("recommendations").items()
        }
        result["selected_route_id"] = ids[result.pop("selected_candidate_key")]
        result["baseline_route_id"] = ids[result.pop("baseline_candidate_key")]
        result.update(
            cache_hit=False,
            objective=request.objective,
            exposure_weight=request.exposure_weight,
            max_detour_percent=request.max_detour_percent,
            resolved_origin=origin,
            resolved_destination=destination,
            candidate_count=len(candidates),
            requested_candidates=request.max_alternatives + 1,
        )
        encoded = json.dumps(result, allow_nan=False).encode()
        if len(encoded) > 4 * 1024 * 1024:
            raise RoutingError(
                "result_too_large_increase_segment_length_or_reduce_alternatives", 422
            )
        candidate_map = {c["candidate_key"]: c for c in candidates}
        owner_hash = fingerprint(owner)
        for r in scored:
            key = f"routes/{owner_hash}/{r['route_id']}.json"
            body = {
                "response": r,
                "candidate": candidate_map[r["candidate_key"]],
                "segment_length_m": request.segment_length_m,
            }
            self.objects.put_bytes(
                key, json.dumps(body, allow_nan=False).encode(), "application/json"
            )
            self.store.put_record("routes", owner, r["route_id"], {"object_key": key}, 7 * 86400)
        # Aggregate report deliberately omits route geometry, coordinates, text, subject and route IDs.
        aggregate = {
            "city": "Delhi",
            "date": request.departure_at.date().isoformat(),
            "mode": request.mode,
            "provider": self.provider.name,
            "candidate_count": len(scored),
            "engine_version": "routing-v1",
            "metrics": [
                {
                    "duration_s": r["duration_s"],
                    "distance_m": r["distance_m"],
                    "pm25_exposure_ug_h_m3": r["estimated_pm25_exposure_ug_h_m3"],
                    "coverage_fraction": r["pm25_coverage_fraction"],
                }
                for r in scored
            ],
        }
        self.objects.put_bytes(
            f"reports/routes/date={aggregate['date']}/{uuid.uuid4().hex}.json",
            json.dumps(aggregate).encode(),
            "application/json",
        )
        cache_object = f"routes/{owner_hash}/cache-{uuid.uuid4().hex}.json"
        self.objects.put_bytes(cache_object, encoded, "application/json")
        self.store.put_record("route_cache", owner, cache_key, {"object_key": cache_object}, 300)
        logger.info(
            json.dumps(
                {
                    "event": "routes_scored",
                    "provider": self.provider.name,
                    "candidates": len(scored),
                    "covered_routes": sum(
                        r["estimated_pm25_exposure_ug_h_m3"] is not None for r in scored
                    ),
                    "latency_ms": round((time.monotonic() - started) * 1000),
                }
            )
        )
        return result

    def exposure(self, owner, request):
        body = self.read(owner, request.route_id, internal=True)
        original = body["response"]
        departure = request.departure_at or datetime.fromisoformat(original["departure_at"])
        if (
            not datetime.now(UTC) - timedelta(days=7)
            <= departure
            <= datetime.now(UTC) + timedelta(hours=48)
        ):
            raise RoutingError("exposure_time_outside_supported_window", 422)
        candidate = body["candidate"]
        index = self.index_factory(
            departure, departure + timedelta(seconds=candidate["duration_s"])
        )
        score = score_exposure(
            candidate, segments(candidate, departure, body["segment_length_m"]), index
        )
        score.update(
            route_id=request.route_id,
            relative_exposure_change_percent=None,
            recommendation_reason="Exposure recomputed for stored provider geometry; no alternative-route baseline for this calculation.",
        )
        score["warnings"].append(
            "Stored routing duration reused; traffic timing is not recalculated by this endpoint."
        )
        return score

    def departure_analysis(self, owner, request):
        results = []
        started = time.monotonic()
        origin, destination = request.origin, request.destination
        for departure in request.departures:
            if time.monotonic() - started > 16:
                raise RoutingError("departure_analysis_deadline_reduce_departures")
            data = request.model_dump(exclude={"departures"})
            data.update(origin=origin, destination=destination, departure_at=departure)
            comparison = self.compare(owner, CompareRequest.model_validate(data))
            results.append({"departure_at": departure.isoformat(), "comparison": comparison})
            # Resolve text once; still obtain genuine routes again for each departure.
            origin = Point(
                longitude=comparison["resolved_origin"][0],
                latitude=comparison["resolved_origin"][1],
            )
            destination = Point(
                longitude=comparison["resolved_destination"][0],
                latitude=comparison["resolved_destination"][1],
            )
        covered = [
            entry
            for entry in results
            if any(
                r["route_id"] == entry["comparison"]["selected_route_id"]
                and r["estimated_pm25_exposure_ug_h_m3"] is not None
                for r in entry["comparison"]["routes"]
            )
        ]

        def selected(entry):
            return next(
                r
                for r in entry["comparison"]["routes"]
                if r["route_id"] == entry["comparison"]["selected_route_id"]
            )

        best = (
            min(covered, key=lambda e: selected(e)["estimated_pm25_exposure_ug_h_m3"])
            if len(covered) == len(results)
            else None
        )
        for entry in results:
            entry["comparison"]["routes"] = [
                {k: v for k, v in route.items() if k not in {"segments", "geometry"}}
                for route in entry["comparison"]["routes"]
            ]
        return {
            "departures": results,
            "lowest_estimated_exposure_departure": best["departure_at"] if best else None,
            "baseline_definition": "Each comparison uses its own fastest returned route at that departure; no cross-time reduction percentage is inferred.",
            "warnings": [
                "Bounded to three departures. Forecast coverage is required to recommend a departure time."
            ],
        }


def create_service(settings, store, objects):
    def reserve():
        try:
            objects.reserve(
                "location", settings.location_daily_limit, settings.location_hourly_limit
            )
        except BudgetExceeded:
            raise RoutingError("location_request_budget_exhausted", 429) from None

    if settings.routing_provider == "osrm":
        if not settings.osrm_base_url:
            raise RoutingError("fallback_endpoint_not_configured")
        provider = OsrmProvider(settings.osrm_base_url, reserve=reserve)
    else:
        if not settings.enable_aws_location:
            return RouteService(DisabledProvider(), store, objects)
        session = boto3.Session(
            profile_name=settings.aws_profile or None, region_name=settings.aws_region
        )
        config = Config(connect_timeout=1, read_timeout=3, retries={"total_max_attempts": 1})
        if settings.ecoroute_profile == "local":
            try:
                identity = session.client("sts", config=config).get_caller_identity()
                if identity["Account"] != settings.expected_aws_account_id or identity[
                    "Arn"
                ].endswith(":root"):
                    raise RoutingError("location_requires_expected_nonroot_identity")
            except (ClientError, BotoCoreError):
                raise RoutingError("location_credentials_unavailable") from None
        provider = AmazonLocation(
            session.client("geo-routes", config=config),
            session.client("geo-places", config=config),
            reserve=reserve,
        )
    return RouteService(provider, store, objects)
