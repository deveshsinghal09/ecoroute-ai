"""Verify saved route arithmetic without requesting providers or inventing missing coverage."""
import argparse
import hashlib
import json
from pathlib import Path

from ecoroute.environment.repository import LocalRepository
from scripts.benchmark_routes import verify_arithmetic


def verify(report, repository):
    count = 0
    for row in report["results"]:
        if row["status"] != "available":
            continue
        for route in row["comparison"]["routes"]:
            verify_arithmetic(route)
            assert route["geometry"]["type"] == "LineString"
            assert len(route["geometry"]["coordinates"]) > 2
            count += 1
    hashes = report.get("curated_object_hashes", {})
    for key, digest in hashes.items():
        assert hashlib.sha256(repository.get_bytes(key)).hexdigest() == digest
    return {"routes_verified": count, "content_hashes_verified": len(hashes),
            "provider_calls": 0, "live_provider_reverified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="work/phase7-benchmark.json")
    parser.add_argument("--data", default="work/environment")
    args = parser.parse_args()
    print(json.dumps(verify(json.loads(Path(args.report).read_text(encoding="utf-8")), LocalRepository(args.data))))
