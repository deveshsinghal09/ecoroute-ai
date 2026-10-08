"""Explicit local real-data collection. Never writes AWS unless called via approved Lambda."""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

from ecoroute.environment.pipeline import credential, ingest
from ecoroute.environment.providers import JsonTransport, OpenAQ, ProviderError
from ecoroute.environment.repository import BudgetExceeded, LocalRepository, curate


def main():
    load_dotenv(override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["open_meteo", "openaq"], required=True)
    parser.add_argument("--output", default="work/environment")
    parser.add_argument("--latitude", type=float, default=28.6139)
    parser.add_argument("--longitude", type=float, default=77.209)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--location-id", type=int)
    parser.add_argument("--sensor-id", type=int)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--stations", action="store_true")
    args = parser.parse_args()
    if (os.getenv("ECOROUTE_PROFILE") or "local") != "local":
        parser.error("CLI is local-only; unset ECOROUTE_PROFILE=aws")
    if not 1 <= args.max_pages <= 10 or args.page < 1:
        parser.error("page >= 1 and max-pages 1..10 required")
    repo = LocalRepository(args.output)
    try:
        if args.source == "open_meteo":
            request = {"latitude": args.latitude, "longitude": args.longitude}
            if args.start or args.end:
                request.update(start=args.start, end=args.end)
            key, cached = ingest(args.source, request, repo)
            print(json.dumps({**curate(repo, key), "cache_hit": cached}, indent=2))
        elif args.stations:
            adapter = OpenAQ(credential("openaq"), JsonTransport(reserve=lambda: repo.reserve("openaq")))
            for page in range(args.page, args.page + args.max_pages):
                payload = adapter.stations(page=page)
                key = f"raw/stations/date={date.today().isoformat()}/page={page}.json"
                repo.put_bytes(key, json.dumps(payload).encode(), "application/json")
                for station in payload["results"]:
                    repo.put("STATIONS#openaq", str(station["id"]), station)
                print(json.dumps({"page": page, "stations": len(payload["results"]), "raw_key": key}))
                if len(payload["results"]) < 100:
                    break
            else:
                print(json.dumps({"incomplete": True, "resume_page": page + 1}))
                return 2
        else:
            if not all((args.location_id, args.sensor_id, args.start, args.end)):
                parser.error("OpenAQ measurements require location-id, sensor-id, start, end")
            start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(args.end.replace("Z", "+00:00"))
            if start.tzinfo is None or end.tzinfo is None or not timedelta(0) <= end - start <= timedelta(days=7):
                parser.error("OpenAQ requires aware timestamps and a window of at most 7 days")
            for page in range(args.page, args.page + args.max_pages):
                key, cached = ingest("openaq", {"location_id": args.location_id, "sensor_id": args.sensor_id,
                    "start": args.start, "end": args.end, "page": page, "limit": 100}, repo)
                report = curate(repo, key)
                print(json.dumps({**report, "cache_hit": cached, "page": page}))
                raw = json.loads(repo.get_bytes(key))
                if len(raw["payload"]["results"]) < 100:
                    break
            else:
                print(json.dumps({"incomplete": True, "resume_page": page + 1}))
                return 2
    except (ProviderError, BudgetExceeded, ValueError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
