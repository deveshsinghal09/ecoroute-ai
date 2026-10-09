"""Only exact IoT Rule/stream source permissions may invoke these cloud workers."""
import base64
import json
import logging
import os
from types import SimpleNamespace

import boto3
from fastapi import HTTPException
from pydantic import ValidationError

from ecoroute.wearable.archive import Archive
from ecoroute.wearable.models import Measurement
from ecoroute.wearable.repository import WearableRepository, owner_key, topic

logger = logging.getLogger("ecoroute.wearable")
logger.setLevel(logging.INFO)


def cloud_repository():
    settings = SimpleNamespace(ecoroute_profile="aws", aws_region=os.environ.get("AWS_REGION", "ap-south-1"),
        wearables_table=os.environ["WEARABLES_TABLE"], s3_data_bucket=os.environ.get("S3_DATA_BUCKET", ""))
    return settings, WearableRepository(SimpleNamespace(client=boto3.client("dynamodb", region_name=settings.aws_region)), settings.wearables_table)


def process_mqtt(event, repo, *, local_demo=False):
    if local_demo and not repo.local:
        raise ValueError("demo_requires_local_storage")
    # Broker-derived envelope is separate from encoded payload; user cannot forge its fields.
    raw = base64.b64decode(event["payload_b64"], validate=True)
    if len(raw) > 8192:
        raise ValueError("telemetry_payload_too_large")
    body = Measurement.model_validate_json(raw)
    device = repo.get(event["owner_key"], "device#" + event["device_id"])
    if not device or device["owner_key"] != owner_key(device["owner_sub"]):
        raise ValueError("device_not_found")
    if (event["device_id"] != body.device_id or body.user_id != device["owner_sub"]
        or event["mqtt_topic"] != topic(device["owner_sub"], body.device_id)
        or event["mqtt_client_id"] != "eco-" + body.device_id
        or not device.get("certificate_thumbprint")
        or event["principal"] != device["certificate_thumbprint"]):
        raise ValueError("mqtt_identity_mismatch")
    # A certificate conveys only its registered owner; journey association must be owned too.
    if body.journey_id:
        raise ValueError("mqtt_journey_link_requires_https")
    return repo.ingest(device["owner_sub"], body, allow_demo=local_demo)


def mqtt_handler(event, context):
    _, repo = cloud_repository()
    try:
        _, created = process_mqtt(event, repo)
        logger.info(json.dumps({"event": "wearable_mqtt", "status": "accepted", "duplicate": not created}))
        return {"accepted": True, "duplicate": not created}
    except (ValueError, KeyError, ValidationError, HTTPException):
        logger.info(json.dumps({"event": "wearable_mqtt", "status": "rejected"}))
        return {"accepted": False, "reason": "invalid_or_unauthorized_telemetry"}
    except Exception:
        raise RuntimeError("wearable_processing_failed") from None


def archive_handler(event, context):
    settings, repo = cloud_repository()
    archive, failures = Archive(settings), []
    for message in event.get("Records", []):
        try:
            image = message.get("dynamodb", {}).get("NewImage", {})
            if message["eventName"] != "INSERT" or not image.get("sk", {}).get("S", "").startswith("measurement#"):
                continue
            record = json.loads(image["payload"]["S"])
            if record["expires_at"] <= __import__("time").time():
                continue
            archive.write(repo, record["user_id"], record)
        except HTTPException:
            continue  # Expired/deleted device: do not archive.
        except Exception:
            failures.append({"itemIdentifier": message["dynamodb"]["SequenceNumber"]})
    logger.info(json.dumps({"event": "wearable_archive", "failed_count": len(failures)}))
    return {"batchItemFailures": failures}
