"""Private, pseudonymous history. This is not anonymized health data."""
import json
from pathlib import Path

import boto3

from ecoroute.wearable.repository import owner_key


class Archive:
    def __init__(self, settings):
        self.settings = settings
        self.cloud = settings.ecoroute_profile == "aws"
        self.s3 = boto3.client("s3", region_name=settings.aws_region) if self.cloud else None

    def prefix(self, subject, device):
        return f"wearables/{owner_key(subject)}/{device}/"

    def write(self, repo, subject, record):
        device = repo.device(subject, record["device_id"])
        if not record["archive"] or device["deleting"] or not device["consent"].get("history") or device["epoch"] != record["consent_epoch"]:
            return False
        key = self.prefix(subject, record["device_id"]) + f"date={record['timestamp'][:10]}/{record['event_id']}.json"
        # Direct subject excluded; hash/device/GPS/HR remain re-identifiable, kept private.
        payload = json.dumps({k: v for k, v in record.items() if k != "user_id"}).encode()
        if self.cloud:
            self.s3.put_object(Bucket=self.settings.s3_data_bucket, Key=key, Body=payload,
                               ServerSideEncryption="AES256", ContentType="application/json")
        else:
            path = Path(self.settings.wearable_archive_path) / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        after = repo.device(subject, record["device_id"])
        if after["deleting"] or not after["consent"].get("history") or after["epoch"] != record["consent_epoch"]:
            if self.cloud:
                self.s3.delete_object(Bucket=self.settings.s3_data_bucket, Key=key)
            else:
                path.unlink(missing_ok=True)
            return False
        return True

    def purge(self, subject, device):
        prefix = self.prefix(subject, device)
        if not self.cloud:
            root = Path(self.settings.wearable_archive_path).resolve()
            folder = (root / prefix).resolve()
            if not folder.is_relative_to(root):
                raise ValueError("invalid_archive_prefix")
            for path in folder.rglob("*.json"):
                if path.resolve().is_relative_to(folder):
                    path.unlink()
            return False
        response = self.s3.list_objects_v2(Bucket=self.settings.s3_data_bucket, Prefix=prefix, MaxKeys=200)
        for row in response.get("Contents", []):
            self.s3.delete_object(Bucket=self.settings.s3_data_bucket, Key=row["Key"])
        return bool(response.get("IsTruncated"))
