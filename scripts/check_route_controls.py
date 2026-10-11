"""Explicit, bounded live smoke checks on public landmarks; no quota bypass."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Make up to three billable provider comparisons")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--origin", nargs=2, type=float, default=[72.8346543, 18.9219841], metavar=("LON", "LAT"))
    parser.add_argument("--destination", nargs=2, type=float, default=[72.822581, 18.943994], metavar=("LON", "LAT"))
    parser.add_argument("--output", type=Path, help="Optional local summary; no tokens or full route geometry")
    args = parser.parse_args()
    if not args.live:
        print("No network calls made. Add --live to check Drive, Walk and Cycle on the configured API. Requests can incur provider charges; 429 stops the run.")
        return 0
    for point in (args.origin, args.destination):
        if not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90:
            parser.error("Coordinates must use longitude, latitude within geographic bounds")
    results = []
    with httpx.Client(trust_env=False, timeout=40) as client:
        for mode in ("driving", "walking", "cycling"):
            body = {
                "origin": dict(zip(("longitude", "latitude"), args.origin, strict=True)),
                "destination": dict(zip(("longitude", "latitude"), args.destination, strict=True)),
                "mode": mode, "departure_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
                "objective": "balanced", "max_detour_percent": 50, "exposure_weight": 0.5,
                "weather_weight": 0.2 if mode != "cycling" else 0,
                "terrain_weight": 0.2 if mode == "cycling" else 0,
                "max_alternatives": 1, "segment_length_m": 250, "consent_to_store": False,
            }
            try:
                response = client.post(args.api_base_url.rstrip("/") + "/api/v1/routes/preview", json=body)
                payload = response.json()
                result = {"mode": mode, "http_status": response.status_code}
                if response.status_code != 200:
                    result["error_code"] = payload.get("error", {}).get("code", "unexpected_response")
                    result["retry_after_seconds"] = response.headers.get("Retry-After")
                else:
                    result["candidate_count"] = payload["candidate_count"]
                    result["recommendations_available"] = {k: bool(v) for k, v in payload["recommended_route_ids"].items()}
                    result["routes"] = [{
                        "provider": r["routing_source"]["provider"], "returned_mode": r["mode"],
                        "geometry_points": len(r["geometry"]["coordinates"]),
                        "duration_s": r["duration_s"], "distance_m": r["distance_m"],
                        "exposure_ug_h_m3": r["estimated_pm25_exposure_ug_h_m3"],
                        "pm25_coverage_fraction": r["pm25_coverage_fraction"],
                        "weather_status": r.get("weather", {}).get("status"),
                        "terrain_status": r.get("terrain", {}).get("status"),
                    } for r in payload["routes"]]
                results.append(result)
                if response.status_code == 429:
                    break
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                results.append({"mode": mode, "error_code": "network_or_response_unavailable"})
                break
    summary = {"checked_at": datetime.now(UTC).isoformat(), "checks": results}
    encoded = json.dumps(summary, indent=2)
    print(encoded)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0 if len(results) == 3 and all(r.get("http_status") == 200 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
