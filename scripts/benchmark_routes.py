"""Repeatable Delhi road-route benchmark; no synthetic pollution or silent fallback."""
import argparse
import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ecoroute.config import Settings
from ecoroute.environment.repository import LocalRepository
from ecoroute.models import Point
from ecoroute.routing.models import CompareRequest, RoutingError
from ecoroute.routing.providers import OsrmProvider
from ecoroute.routing.service import RouteService, create_service
from ecoroute.storage import LocalStore
from scripts.demo_routes import RecordedDelhi

CASES = [
    {"id": "india_gate_connaught_place", "origin": [77.2295, 28.6129], "destination": [77.2167, 28.6315]},
    {"id": "connaught_place_ito", "origin": [77.2167, 28.6315], "destination": [77.2415, 28.6289]},
    {"id": "india_gate_lodhi_garden", "origin": [77.2295, 28.6129], "destination": [77.2193, 28.5933]},
]


def engine_for(provider, store, repo, *, live=False):
    if provider != "recorded" and not live:
        raise ValueError("live_provider_requires_explicit_live_flag")
    if provider == "recorded":
        return RouteService(RecordedDelhi(), store, repo)
    if provider == "osrm":
        return RouteService(OsrmProvider("https://router.project-osrm.org", reserve=lambda: repo.reserve("benchmark_osrm", 20, 10)), store, repo)
    settings = Settings()
    if not settings.enable_aws_location or settings.ecoroute_profile != "local":
        raise ValueError("configure_approved_local_location_profile_region_account_permissions_first")
    return create_service(settings, store, repo)


def verify_arithmetic(route):
    contributions = [s["pm25_exposure_ug_h_m3"] for s in route["segments"]]
    for segment in route["segments"]:
        value = segment["pollutants"]["pm25"]["value_ug_m3"]
        actual = segment["pm25_exposure_ug_h_m3"]
        if value is None:
            assert actual is None
        else:
            assert abs(actual - value * segment["duration_s"] / 3600) < 1e-8
    assert abs(sum(s["duration_s"] for s in route["segments"]) - route["duration_s"]) < 1e-5
    total = route["estimated_pm25_exposure_ug_h_m3"]
    if total is not None:
        assert all(c is not None for c in contributions)
        assert abs(sum(contributions) - total) < 1e-8
    return True


def benchmark(engine, departures, cases=CASES, pause=lambda: None):
    results = []
    for case in cases:
        for departure in departures:
            request = CompareRequest(origin=Point(longitude=case["origin"][0], latitude=case["origin"][1]),
                destination=Point(longitude=case["destination"][0], latitude=case["destination"][1]),
                departure_at=departure, mode="driving", objective="lowest_exposure",
                max_detour_percent=25, exposure_weight=0.5, segment_length_m=250,
                max_alternatives=2, consent_to_store=True)
            row = {"case_id": case["id"], "departure_at": departure.isoformat(), "input": request.model_dump(mode="json")}
            try:
                pause()
                comparison = engine.compare("public-landmark-benchmark", request)
                by_id = {r["route_id"]: r for r in comparison["routes"]}
                for route in by_id.values():
                    verify_arithmetic(route)
                categories = comparison["recommended_route_ids"]
                row.update(status="available", comparison=comparison,
                    fastest=by_id[categories["fastest"]],
                    lowest_estimated_exposure=by_id.get(categories["lowest_exposure"]),
                    arithmetic_verified=True, candidate_count=len(by_id))
            except RoutingError as exc:
                row.update(status="unavailable", reason=exc.code, arithmetic_verified=False)
            results.append(row)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["recorded", "osrm", "aws"], default="recorded")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--departure-at", help="Aware ISO timestamp now through 46 hours ahead")
    parser.add_argument("--data", default="work/environment")
    parser.add_argument("--output", default="work/phase7-benchmark.json")
    args = parser.parse_args()
    departure = datetime.fromisoformat(args.departure_at.replace("Z", "+00:00")) if args.departure_at else datetime.now(UTC) + timedelta(minutes=10)
    store, repo = LocalStore(":memory:"), LocalRepository(args.data)
    try:
        engine = engine_for(args.provider, store, repo, live=args.live)
        results = benchmark(engine, [departure, departure + timedelta(hours=2)], pause=lambda: time.sleep(2.1) if args.live else None)
        files, truncated = [], False
        for source in ("open_meteo", "openaq"):
            entries, cut = repo.query("FILES#" + source, limit=100)
            files.extend(entries)
            truncated = truncated or cut
        object_hashes = {f["key"]: hashlib.sha256(repo.get_bytes(f["key"])).hexdigest() for f in files}
        snapshot = hashlib.sha256(json.dumps(object_hashes, sort_keys=True).encode()).hexdigest()
        report = {"created_at": datetime.now(UTC).isoformat(), "provider": args.provider,
            "geometry_mode": "recorded_real_roads" if args.provider == "recorded" else "live_provider_roads",
            "pollution_mode": "actual_local_provider_records_or_unavailable", "aws_routes_verified": args.provider == "aws" and any(r["status"] == "available" for r in results),
            "dataset_key_snapshot_sha256": snapshot, "dataset_index_truncated": truncated,
            "curated_object_hashes": object_hashes,
            "assumptions": "Same saved dataset index, 250m segments, uniform within-leg speed, driving, max25% time detour, weight0.5; negative relative exposure change means lower than fastest returned route at SAME departure. Coarse grids do not establish roadside differences. Repeat live calls can change provider geometry/data.",
            "cases": CASES, "results": results}
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print(json.dumps({"output": str(path), "provider": args.provider, "available": sum(r["status"] == "available" for r in results), "unavailable": sum(r["status"] != "available" for r in results), "aws_routes_verified": report["aws_routes_verified"]}))
    finally:
        store.db.close()
        repo.db.close()


if __name__ == "__main__":
    main()
