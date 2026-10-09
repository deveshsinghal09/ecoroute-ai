"""Explicit upload of a verified versioned dataset to an existing approved ML bucket."""
import argparse
import json
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

from ecoroute.ml.preprocessing import load_dataset


def main():
    load_dotenv(override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE"))
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "ap-south-1"))
    args = parser.parse_args()
    _, manifest = load_dataset(args.dataset)
    if not args.profile or not os.getenv("EXPECTED_AWS_ACCOUNT_ID"):
        parser.error("Explicit CLI profile and EXPECTED_AWS_ACCOUNT_ID required")
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != os.environ["EXPECTED_AWS_ACCOUNT_ID"] or identity["Arn"].endswith(":root"):
        parser.error("Expected non-root account identity required")
    s3 = session.client("s3")
    uploaded = []
    for name in ("train.parquet", "validation.parquet", "test.parquet", "manifest.json"):
        key = f"datasets/{manifest['dataset_version']}/{name}"
        s3.put_object(Bucket=args.bucket, Key=key, Body=(Path(args.dataset) / name).read_bytes(),
                      ExpectedBucketOwner=identity["Account"],
                      ServerSideEncryption="AES256", IfNoneMatch="*",
                      ContentType="application/json" if name.endswith(".json") else "application/vnd.apache.parquet")
        uploaded.append(key)
    print(json.dumps({"bucket": args.bucket, "objects_uploaded": uploaded, "training_launched": False}))


if __name__ == "__main__":
    main()
