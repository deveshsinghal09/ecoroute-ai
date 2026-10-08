import json
import logging
from urllib.parse import unquote_plus

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from ecoroute.environment.pipeline import ingest, repository
from ecoroute.environment.repository import curate

logger = logging.getLogger("ecoroute.ingestion")
logger.setLevel(logging.INFO)


class IngestionJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["open_meteo", "openaq"]
    request: dict = Field(default_factory=dict)


def collect(event, context):
    job = IngestionJob.model_validate(event)
    try:
        key, cached = ingest(job.source, job.request, repository())
        logger.info(json.dumps({"event": "raw_saved", "source": job.source, "cached": cached}))
        return {"raw_key": key, "cached": cached}
    except Exception:
        logger.error(json.dumps({"event": "ingestion_failed", "source": job.source}))
        # Suppress SDK/HTTP error text that might contain credential URLs.
        raise RuntimeError("ingestion_failed; inspect credential/configuration and provider status") from None


def clean(event, context, *, repo=None):
    repo = repo or repository()
    failures = []
    for message in event.get("Records", []):
        try:
            body = json.loads(message["body"])
            if body.get("Event") == "s3:TestEvent":
                continue
            for notification in body["Records"]:
                if notification.get("eventSource") != "aws:s3":
                    raise ValueError("unexpected event")
                if hasattr(repo, "bucket") and notification["s3"]["bucket"]["name"] != repo.bucket:
                    raise ValueError("unexpected bucket")
                key = unquote_plus(notification["s3"]["object"]["key"])
                if not key.startswith("raw/source="):
                    raise ValueError("unexpected key")
                report = curate(repo, key)
                logger.info(json.dumps({"event": "curated", "source": report["source"], "records": report["records"]}))
        except Exception:
            failures.append({"itemIdentifier": message["messageId"]})
            logger.error(json.dumps({"event": "cleaning_failed"}))
    return {"batchItemFailures": failures}
