"""Explicit local Phase 3 demonstration. Recorded roads are labelled; pollution is never fabricated."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from ecoroute.config import Settings
from ecoroute.environment.repository import LocalRepository
from ecoroute.models import Point
from ecoroute.routing.models import CompareRequest, RoutingError
from ecoroute.routing.providers import OsrmProvider
from ecoroute.routing.service import RouteService, create_service
from ecoroute.storage import LocalStore


class RecordedDelhi:
    name = "recorded_osrm"

    def __init__(self):
        self.recording = json.loads(
            (
                Path(__file__).resolve().parents[1] / "tests/fixtures/delhi_osrm_routes.json"
            ).read_text(encoding="utf-8")
        )

    def resolve(self, place):
        return [place.longitude, place.latitude]

    def candidates(self, origin, destination, request):
        if (
            origin != self.recording["origin"]
            or destination != self.recording["destination"]
            or request.mode != "driving"
        ):
            raise RoutingError("recording_only_matches_the_public_landmark_demo", 422)
        return OsrmProvider.parse(
            self.recording["payload"],
            origin,
            destination,
            fixture=True,
            collected_at=self.recording["collected_at"],
        )


def main():
    load_dotenv(override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["recorded", "aws"], default="recorded")
    parser.add_argument("--profile", default="dev-admin")
    parser.add_argument("--expected-account-id")
    parser.add_argument("--data", default="work/environment")
    parser.add_argument("--output", default="work/phase3-demo.json")
    args = parser.parse_args()
    settings = Settings()
    if settings.ecoroute_profile != "local":
        parser.error(
            "This CLI writes local demonstration files only; ECOROUTE_PROFILE must be local"
        )
    store = LocalStore("work/route-demo.sqlite3")
    objects = LocalRepository(args.data)
    request = CompareRequest(
        origin=Point(longitude=77.2295, latitude=28.6129),
        destination=Point(longitude=77.2167, latitude=28.6315),
        departure_at=datetime.now(UTC) + timedelta(minutes=10),
        mode="driving",
        consent_to_store=True,
    )
    try:
        if args.provider == "recorded":
            engine = RouteService(RecordedDelhi(), store, objects)
        else:
            account = args.expected_account_id or settings.expected_aws_account_id
            settings = Settings(
                enable_aws_location=True, aws_profile=args.profile, expected_aws_account_id=account
            )
            engine = create_service(settings, store, objects)
        result = engine.compare("local-public-landmark-demo", request)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
        print(
            json.dumps(
                {
                    "status": "success",
                    "provider": args.provider,
                    "aws_route_verified": args.provider == "aws",
                    "route_count": len(result["routes"]),
                    "spatial_differentiation": result["spatial_differentiation"],
                    "routes": [
                        {
                            "route_id": r["route_id"],
                            "distance_m": r["distance_m"],
                            "duration_s": r["duration_s"],
                            "pm25_exposure_ug_h_m3": r["estimated_pm25_exposure_ug_h_m3"],
                            "coverage_fraction": r["pm25_coverage_fraction"],
                            "relative_exposure_change_percent": r[
                                "relative_exposure_change_percent"
                            ],
                            "segments": len(r["segments"]),
                        }
                        for r in result["routes"]
                    ],
                    "output": str(output),
                },
                indent=2,
            )
        )
    except RoutingError as exc:
        print(json.dumps({"status": "failed", "code": exc.code, "aws_route_verified": False}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
