"""Read-only account/quota/image checks. Never starts jobs, endpoints or containers."""

import argparse
import json
import re
import subprocess
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ecoroute.ml.policy import operational_dataset
from ecoroute.ml.preprocessing import load_dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--role-arn", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--image-uri", default="")
    parser.add_argument("--output", default="work/ml/sagemaker-readiness.json")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]{12}", args.account) or not args.role_arn.startswith(
        f"arn:aws:iam::{args.account}:role/"
    ):
        parser.error("Explicit same-account execution role required")
    _, manifest = load_dataset(args.dataset)
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    config = Config(connect_timeout=2, read_timeout=5, retries={"total_max_attempts": 1})
    identity = session.client("sts", config=config).get_caller_identity()
    if identity["Account"] != args.account or identity["Arn"].endswith(":root"):
        raise ValueError("expected_nonroot_identity_required")
    result = {
        "account": args.account,
        "region": args.region,
        "identity_type": "nonroot",
        "dataset_version": manifest["dataset_version"],
        "dataset_scope": manifest["training_scope"],
        "operational_dataset": operational_dataset(manifest),
        "paid_training_approved": False,
        "launched": False,
        "checks": {},
        "blockers": [],
    }
    try:
        quota = session.client("service-quotas", config=config).get_service_quota(
            ServiceCode="sagemaker", QuotaCode="L-611FA074"
        )["Quota"]["Value"]
        result["checks"]["ml.m5.large_training_quota"] = quota
        if quota < 1:
            result["blockers"].append(
                "Request ml.m5.large training quota >=1 in Mumbai; do not launch with quota zero"
            )
    except (ClientError, BotoCoreError):
        result["blockers"].append("Cannot verify quota; need service-quotas:GetServiceQuota")
    try:
        role = session.client("iam", config=config).get_role(
            RoleName=args.role_arn.rsplit("/", 1)[1]
        )["Role"]
        statements = role["AssumeRolePolicyDocument"].get("Statement", [])
        trust = any(
            s.get("Effect") == "Allow"
            and "sagemaker.amazonaws.com" in str(s.get("Principal", {}).get("Service", ""))
            for s in statements
        )
        result["checks"]["execution_role_sagemaker_trust"] = trust
        if not trust:
            result["blockers"].append("Execution role does not trust sagemaker.amazonaws.com")
    except (ClientError, BotoCoreError):
        result["blockers"].append(
            "Cannot verify role trust; need iam:GetRole on the exact training role"
        )
    match = re.fullmatch(
        re.escape(f"{args.account}.dkr.ecr.{args.region}.amazonaws.com/")
        + r"([a-z0-9/_-]+)@sha256:([a-f0-9]{64})",
        args.image_uri,
    )
    if match:
        try:
            image = session.client("ecr", config=config).describe_images(
                repositoryName=match[1], imageIds=[{"imageDigest": "sha256:" + match[2]}]
            )["imageDetails"]
            result["checks"]["pinned_image_exists"] = bool(image)
            if not image:
                result["blockers"].append("Pinned training image not found")
        except (ClientError, BotoCoreError):
            result["blockers"].append(
                "Cannot verify image; check ecr:DescribeImages and the digest"
            )
    else:
        result["blockers"].append("Missing actual digest-pinned training image in regional ECR")
    try:
        docker = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        result["checks"]["docker_engine_running"] = docker.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        result["checks"]["docker_engine_running"] = False
    result["blockers"].extend(
        [
            "Verify exact S3/ECR/logs execution-role grants and operator iam:PassRole/CreateTrainingJob grants",
            "Review the actual job specification and costs; obtain separate paid-training approval",
        ]
    )
    if not operational_dataset(manifest):
        result["blockers"].append(
            "Dataset is experimental: may train an explicitly approved experiment but must never publish to navigation registry"
        )
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
