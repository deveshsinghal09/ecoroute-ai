"""Download licensed real historical data, or generate explicitly synthetic test scenarios."""

import argparse
import hashlib
import json
from pathlib import Path

import httpx

from ecoroute.ml.benchmark_data import (
    UCI_SOURCE,
    UCI_URL,
    prepare_experiment,
    read_uci,
    synthetic_series,
)
from ecoroute.ml.preprocessing import write_dataset


def download(path):
    if path.exists():
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", UCI_URL, timeout=90, follow_redirects=False) as response:
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > 30 * 1024 * 1024:
                raise ValueError("dataset_download_too_large")
            chunks.append(chunk)
    content = b"".join(chunks)
    read_uci(content)  # Verify schema/archive limits before keeping the source.
    path.write_bytes(content)
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["uci-beijing", "synthetic"], default="uci-beijing")
    parser.add_argument(
        "--download", action="store_true", help="Explicitly allow public UCI download"
    )
    parser.add_argument("--archive", default="work/ml/experiments/source/uci-beijing.zip")
    parser.add_argument("--records", type=int, default=100_000)
    parser.add_argument("--stations", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="work/ml/experiments/datasets")
    args = parser.parse_args()
    synthetic = args.source == "synthetic"
    if synthetic:
        groups, audit = synthetic_series(
            records=args.records, stations=args.stations, seed=args.seed
        )
        source = "ecoroute_synthetic_scenarios_v1"
        fingerprint = hashlib.sha256(json.dumps(audit, sort_keys=True).encode()).hexdigest()
    else:
        archive = Path(args.archive)
        content = download(archive) if args.download else archive.read_bytes()
        groups, audit = read_uci(content)
        source, fingerprint = UCI_SOURCE, hashlib.sha256(content).hexdigest()
    parts, manifest = prepare_experiment(
        groups, audit, source=source, source_sha256=fingerprint, synthetic=synthetic
    )
    path = Path(args.output) / manifest["dataset_version"]
    if path.exists():
        raise ValueError("dataset_already_exists_choose_another_output_to_preserve_completed_work")
    dataset = write_dataset(parts, manifest, args.output)
    print(
        json.dumps(
            {
                "dataset_directory": str(dataset),
                "input_records": audit["input_records"],
                "split_counts": manifest["split_counts"],
                "synthetic": synthetic,
                "deployment_eligible": False,
                "source_sha256": fingerprint,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
