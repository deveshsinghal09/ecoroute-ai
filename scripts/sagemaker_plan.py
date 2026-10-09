"""Generate a reviewable specification and arithmetic estimate; never launch a job."""

import argparse
import json
from pathlib import Path

from botocore.session import get_session
from botocore.validate import validate_parameters

from ecoroute.ml.sagemaker import job_spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("name", "bucket", "dataset-version", "role-arn", "image-uri"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--hourly-rate-usd", type=float)
    parser.add_argument("--output", default="work/training-job.json")
    args = parser.parse_args()
    spec = job_spec(
        name=args.name,
        bucket=args.bucket,
        dataset_version=args.dataset_version,
        role_arn=args.role_arn,
        image_uri=args.image_uri,
        region=args.region,
    )
    validate_parameters(
        spec,
        get_session()
        .get_service_model("sagemaker")
        .operation_model("CreateTrainingJob")
        .input_shape,
    )
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "spec": str(path),
                "instance": "ml.m5.large",
                "count": 1,
                "max_runtime_seconds": 900,
                "training_compute_at_15min_usd": args.hourly_rate_usd * 0.25
                if args.hourly_rate_usd
                else None,
                "extra_costs": "startup/billable duration, storage, requests, ECR, logs, workflow and taxes; check credit eligibility",
                "launched": False,
            }
        )
    )


if __name__ == "__main__":
    main()
