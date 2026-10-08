"""SQS task handler: records a scheduled tick; no provider ingestion claimed."""
import json
import logging
import os
from functools import lru_cache
from typing import Literal

import boto3
from botocore.config import Config
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("ecoroute.tasks")
logger.setLevel(logging.INFO)


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["ingestion_tick"]
    event_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")


@lru_cache
def s3_client():
    return boto3.client("s3", config=Config(connect_timeout=2, read_timeout=3,
                                          retries={"max_attempts": 2, "mode": "standard"}))


def process(task, client, bucket):
    report = {"event_id": task.event_id, "status": "deferred", "reason": "provider_not_configured"}
    client.put_object(Bucket=bucket, Key=f"reports/ingestion/{task.event_id}.json",
                      Body=json.dumps(report).encode(), ContentType="application/json",
                      ServerSideEncryption="AES256")


def handler(event, context, *, client=None, bucket=None):
    failures = []
    for record in event.get("Records", []):
        try:
            task = Task.model_validate_json(record["body"])
            process(task, client or s3_client(), bucket or os.environ["S3_DATA_BUCKET"])
        except Exception:
            failures.append({"itemIdentifier": record["messageId"]})
            logger.warning(json.dumps({"event": "task_failed", "retry": True}))
    return {"batchItemFailures": failures}
