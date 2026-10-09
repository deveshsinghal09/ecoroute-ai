"""Prepare real measurements locally/S3, or run the identical prepared-data SageMaker entrypoint."""

import argparse
import io
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import boto3
import pyarrow.parquet as pq
from dotenv import load_dotenv

from ecoroute.ml.preprocessing import InsufficientData, prepare, write_dataset
from ecoroute.ml.training import train


def load_history(source, *, profile=None, region="ap-south-1", expected_account=None):
    if not source.startswith("s3://"):
        paths = list(Path(source).rglob("*.parquet"))
        if len(paths) > 1000:
            raise ValueError("history_file_limit")
        return [r for p in paths for r in pq.ParquetFile(p).read().to_pylist()]
    uri = urlsplit(source)
    if (
        not uri.netloc
        or not uri.path.lstrip("/").startswith("curated/")
        or not profile
        or not expected_account
    ):
        raise ValueError(
            "S3 history requires scoped curated prefix, explicit profile and expected account"
        )
    session = boto3.Session(profile_name=profile, region_name=region)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != expected_account or identity["Arn"].endswith(":root"):
        raise ValueError("expected_nonroot_identity_required")
    s3, rows, size, files = session.client("s3"), [], 0, 0
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=uri.netloc, Prefix=uri.path.lstrip("/")
    ):
        for item in page.get("Contents", []):
            if not item["Key"].endswith(".parquet"):
                continue
            files += 1
            size += item["Size"]
            if files > 1000 or size > 100 * 1024 * 1024:
                raise ValueError("history_export_limit_reached_narrow_the_prefix")
            content = s3.get_object(Bucket=uri.netloc, Key=item["Key"])["Body"].read()
            rows.extend(pq.ParquetFile(io.BytesIO(content)).read().to_pylist())
    return rows


def main():
    load_dotenv(override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="work/environment/curated")
    parser.add_argument("--prepared-dir", default=os.environ.get("SM_CHANNEL_DATASET"))
    parser.add_argument("--dataset-output", default="work/ml/datasets")
    parser.add_argument("--output", default=os.environ.get("SM_MODEL_DIR", "work/ml/models"))
    parser.add_argument("--weather-json")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    try:
        dataset = args.prepared_dir
        if not dataset:
            rows = load_history(
                args.source,
                profile=os.getenv("AWS_PROFILE"),
                region=os.getenv("AWS_REGION", "ap-south-1"),
                expected_account=os.getenv("EXPECTED_AWS_ACCOUNT_ID"),
            )
            weather = json.loads(Path(args.weather_json).read_text()) if args.weather_json else []
            parts, manifest = prepare(rows, weather=weather)
            dataset = write_dataset(parts, manifest, args.dataset_output)
        if args.prepare_only:
            print(json.dumps({"status": "prepared", "dataset_directory": str(dataset)}))
        else:
            path, metadata = train(dataset, args.output)
            print(
                json.dumps(
                    {
                        "status": "evaluated",
                        "model_directory": str(path),
                        "verified": metadata["verified"],
                    }
                )
            )
    except InsufficientData as exc:
        path = Path(args.dataset_output).parent / "data_audit.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(exc.report, indent=2), encoding="utf-8")
        print(json.dumps(exc.report, indent=2))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
