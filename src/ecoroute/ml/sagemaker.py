"""Dry-run job specifications; no function here launches compute."""

import re


def job_spec(*, name, bucket, dataset_version, role_arn, image_uri, region="ap-south-1"):
    if not re.fullmatch(r"ecoroute-[a-zA-Z0-9-]{1,50}", name) or not re.fullmatch(
        r"[a-f0-9]{24}", dataset_version
    ):
        raise ValueError("invalid_project_job_or_dataset_version")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise ValueError("invalid_bucket")
    if not re.fullmatch(r"arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9/_+=,.@-]+", role_arn):
        raise ValueError("explicit_execution_role_required")
    if not re.fullmatch(
        r"[0-9]{12}\.dkr\.ecr\."
        + re.escape(region)
        + r"\.amazonaws\.com/[a-z0-9/_-]+@sha256:[a-f0-9]{64}",
        image_uri,
    ):
        raise ValueError("regional_digest_pinned_training_image_required")
    return {
        "TrainingJobName": name,
        "RoleArn": role_arn,
        "AlgorithmSpecification": {"TrainingImage": image_uri, "TrainingInputMode": "File"},
        "InputDataConfig": [
            {
                "ChannelName": "dataset",
                "InputMode": "File",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{bucket}/datasets/{dataset_version}/",
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
            }
        ],
        "OutputDataConfig": {"S3OutputPath": f"s3://{bucket}/models/training/"},
        "ResourceConfig": {"InstanceType": "ml.m5.large", "InstanceCount": 1, "VolumeSizeInGB": 5},
        "StoppingCondition": {"MaxRuntimeInSeconds": 900, "MaxPendingTimeInSeconds": 1800},
        "EnableNetworkIsolation": True,
        "EnableInterContainerTrafficEncryption": True,
        "EnableManagedSpotTraining": False,
        "ProfilerConfig": {"DisableProfiler": True},
        "Tags": [
            {"Key": "Project", "Value": "ecoroute-ai"},
            {"Key": "DatasetVersion", "Value": dataset_version},
        ],
    }
