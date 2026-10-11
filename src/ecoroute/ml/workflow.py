"""Small orchestration handlers: data gate, approved job parameters and verified publication."""

import hashlib
import io
import json
import os
import tarfile

import boto3

from ecoroute.ml.inference import VERSION
from ecoroute.ml.preprocessing import FEATURES
from ecoroute.ml.sagemaker import job_spec
from ecoroute.ml.policy import operational_dataset, operational_model


def validate(s3, event):
    version = event["dataset_version"]
    if not VERSION.fullmatch(version):
        raise ValueError("invalid_dataset_version")
    bucket = os.environ["ML_BUCKET"]
    content = s3.get_object(Bucket=bucket, Key=f"datasets/{version}/manifest.json")
    if content["ContentLength"] > 256 * 1024:
        raise ValueError("manifest_too_large")
    manifest = json.loads(content["Body"].read())
    if (
        manifest.get("status") != "ready"
        or manifest.get("dataset_version") != version
        or manifest.get("feature_schema") != FEATURES
        or not operational_dataset(manifest)
        or any(
            manifest.get("split_counts", {}).get(k, 0) < n
            for k, n in (("train", 72), ("validation", 24), ("test", 24))
        )
    ):
        raise ValueError("measured_dataset_not_ready")
    return job_spec(
        name=event["job_name"],
        bucket=bucket,
        dataset_version=version,
        role_arn=os.environ["ML_TRAINING_ROLE"],
        image_uri=os.environ["ML_IMAGE_URI"],
        region=os.environ.get("AWS_REGION", "ap-south-1"),
    )


def publish(s3, job_name):
    if not job_name.startswith("ecoroute-"):
        raise ValueError("invalid_job_name")
    job = boto3.client("sagemaker").describe_training_job(TrainingJobName=job_name)
    bucket = os.environ["ML_BUCKET"]
    expected = f"s3://{bucket}/models/training/{job_name}/output/model.tar.gz"
    if (
        job["TrainingJobStatus"] != "Completed"
        or job["ModelArtifacts"]["S3ModelArtifacts"] != expected
    ):
        raise ValueError("unverified_training_output")
    response = s3.get_object(Bucket=bucket, Key=expected.split(bucket + "/", 1)[1])
    if response["ContentLength"] > 32 * 1024 * 1024:
        raise ValueError("model_archive_too_large")
    files = {}
    archive_version = None
    with tarfile.open(fileobj=io.BytesIO(response["Body"].read()), mode="r:gz") as archive:
        for member in archive:
            if member.isdir():
                continue
            if not member.isfile() or member.size > 32 * 1024 * 1024 or len(files) >= 2:
                raise ValueError("unsafe_model_archive")
            pieces = member.name.split("/")
            if (
                len(pieces) != 2
                or not VERSION.fullmatch(pieces[0])
                or pieces[1] not in {"model.joblib", "manifest.json"}
            ):
                raise ValueError("unexpected_model_archive_layout")
            if pieces[1] in files or (archive_version and pieces[0] != archive_version):
                raise ValueError("inconsistent_model_archive")
            archive_version = pieces[0]
            files[pieces[1]] = archive.extractfile(member).read()
    if set(files) != {"model.joblib", "manifest.json"}:
        raise ValueError("incomplete_model_archive")
    manifest = json.loads(files["manifest.json"])
    if hashlib.sha256(files["model.joblib"]).hexdigest() != manifest[
        "model_sha256"
    ] or not VERSION.fullmatch(manifest["model_version"]) or manifest["model_version"] != archive_version:
        raise ValueError("model_hash_mismatch")
    # Recheck the claimed global promotion rule from the stored actual metrics.
    score = manifest["metrics"]["test"][manifest["algorithm"]]["overall"]
    baseline = manifest["metrics"]["test"]["persistence"]["overall"]
    promoted = (
        operational_model(manifest)
        and score["mae"] < baseline["mae"]
        and score["rmse"] <= baseline["rmse"]
    )
    if promoted:
        for name, content in files.items():
            s3.put_object(
                Bucket=bucket,
                Key=f"models/registry/{manifest['model_version']}/{name}",
                Body=content,
                ServerSideEncryption="AES256",
            )
    return {
        "model_version": manifest["model_version"],
        "promoted": bool(promoted),
        "job_name": job_name,
    }


def handler(event, context):
    s3 = boto3.client("s3")
    operation = event.get("operation")
    if operation == "validate":
        return validate(s3, event)
    if operation == "publish":
        return publish(s3, event["job_name"])
    if operation == "scheduled":
        # Disabled at deploy; operator must populate an approved dataset version and enable this gate.
        if os.getenv("ML_SCHEDULE_APPROVED") != "true":
            raise ValueError("scheduled_training_not_approved")
        from datetime import UTC, datetime
        import uuid

        payload = {
            "dataset_version": os.environ["ML_SCHEDULE_DATASET_VERSION"],
            "job_name": "ecoroute-"
            + datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            + "-"
            + uuid.uuid4().hex[:8],
        }
        return boto3.client("stepfunctions").start_execution(
            stateMachineArn=os.environ["ML_STATE_MACHINE_ARN"], input=json.dumps(payload)
        )
    raise ValueError("invalid_ml_workflow_operation")
