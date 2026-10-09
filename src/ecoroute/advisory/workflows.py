"""Trusted IAM-triggered jobs; no public endpoint can choose an owner or start a run."""
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Literal

import boto3
from pydantic import Field, model_validator

from ecoroute.advisory.alerts import daily_window, evaluate
from ecoroute.advisory.api import AlertRequest
from ecoroute.advisory.notifications import notify_sms
from ecoroute.config import Settings
from ecoroute.environment.pipeline import ingest, repository
from ecoroute.environment.repository import curate
from ecoroute.environment.providers import grid
from ecoroute.environment.schema import digest
from ecoroute.ml.api import ml_service
from ecoroute.ml.inference import MLUnavailable
from ecoroute.models import Point, StrictModel
from ecoroute.storage import DynamoStore

logger = logging.getLogger("ecoroute.workflow")
logger.setLevel(logging.INFO)


class WorkflowJob(StrictModel):
    run_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    owner: str = Field(min_length=1, max_length=128)
    position: Point
    evaluation: AlertRequest
    station_ids: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def location(self):
        lat, lon = grid(self.position.latitude, self.position.longitude)
        if self.evaluation.source != "open_meteo" or self.evaluation.location_id != f"cams_global:{lat:.4f}:{lon:.4f}":
            raise ValueError("Workflow forecast must match configured position")
        return self


class DailyTemplate(StrictModel):
    owner: str = Field(min_length=1, max_length=128)
    position: Point
    location_id: str = Field(min_length=1, max_length=100)
    notify: bool = False
    station_ids: list[str] = Field(default_factory=list, max_length=20)


def run_stage(stage, job, store, repo, settings, *, ingest_fn=ingest, curate_fn=curate, predictor=None):
    if stage == "ingestion":
        if job.evaluation.source != "open_meteo":
            raise ValueError("Scheduled pipeline currently collects grid forecasts only")
        key, cached = ingest_fn("open_meteo", job.position.model_dump(), repo)
        # Existing duplicate S3->SQS cleaning remains idempotent. Wait for curated output here.
        return {"raw_key": key, "cached": cached, "curation": curate_fn(repo, key)}
    if stage == "prediction":
        if not job.station_ids:
            return {"status": "unavailable", "reason": "no_supported_stations_configured", "horizon_hours": 1}
        try:
            predictor = predictor or ml_service(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings))))
            return predictor.batch(job.station_ids)
        except MLUnavailable:
            return {"status": "unavailable", "reason": "verified_model_not_available", "horizon_hours": 1}
    if stage == "risk":
        return daily_window(repo, job.evaluation.source, job.evaluation.location_id, job.evaluation.end_at)
    if stage == "alerts":
        prior = store.get("workflows", job.owner, job.run_id)
        if not prior or "risk" not in prior:
            raise ValueError("risk_stage_required")
        return evaluate(store, job.owner, prior["risk"])
    if stage == "notification":
        prior = store.get("workflows", job.owner, job.run_id)
        alert = (prior or {}).get("alerts", {}).get("alert")
        return notify_sms(store, job.owner, alert, settings) if alert and job.evaluation.notify else {"status": "disabled", "delivered": False}
    raise ValueError("unknown_stage")


class StageEvent(StrictModel):
    stage: Literal["ingestion", "prediction", "risk", "alerts", "notification"]
    job: WorkflowJob


def stage_handler(event, context):
    parsed = StageEvent.model_validate(event)
    settings = Settings()
    store = DynamoStore(boto3.client("dynamodb"), {
        "workflows": settings.alerts_table, "alerts": settings.alerts_table,
        "notification_state": settings.alerts_table, "preferences": settings.preferences_table,
        "notification_config": settings.preferences_table}, settings.idempotency_table)
    try:
        result = run_stage(parsed.stage, parsed.job, store, repository(), settings)
        manifest = store.get("workflows", parsed.job.owner, parsed.job.run_id) or {}
        manifest[parsed.stage] = result
        manifest.update(status="complete" if parsed.stage == "notification" else "running",
                        updated_at=datetime.now(UTC).isoformat())
        store.put_record("workflows", parsed.job.owner, parsed.job.run_id, manifest, 7 * 86400)
        logger.info(json.dumps({"event": "workflow_stage_complete", "stage": parsed.stage,
            "_aws": {"Timestamp": int(datetime.now(UTC).timestamp() * 1000), "CloudWatchMetrics": [{"Namespace": "EcoRoute/Environment", "Dimensions": [[]], "Metrics": [{"Name": "AlertCount", "Unit": "Count"}]}]},
            "AlertCount": int(parsed.stage == "alerts" and result.get("created", False))}))
        return {"status": "stage_complete"}
    except Exception:
        manifest = store.get("workflows", parsed.job.owner, parsed.job.run_id) or {}
        manifest.update(status="failed", failed_stage=parsed.stage)
        store.put_record("workflows", parsed.job.owner, parsed.job.run_id, manifest, 7 * 86400)
        logger.error(json.dumps({"event": "workflow_stage_failed", "stage": parsed.stage}))
        raise RuntimeError("workflow_stage_failed") from None


def dispatch_handler(event, context):
    failures = []
    for message in event.get("Records", []):
        try:
            if os.getenv("ENABLE_ENVIRONMENT_WORKFLOW") != "true":
                raise ValueError("workflow_activation_requires_approval")
            body = json.loads(message["body"])
            if set(body) == {"daily_template"}:
                template = DailyTemplate.model_validate(body["daily_template"])
                if template.owner == "CONFIGURE_COGNITO_SUB":
                    raise ValueError("configure_owner_before_activation")
                now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
                body = {"run_id": digest([template.owner, template.location_id, now.date().isoformat()])[:32],
                    "owner": template.owner, "position": template.position.model_dump(), "station_ids": template.station_ids,
                    "evaluation": {"source": "open_meteo", "location_id": template.location_id,
                        "end_at": (now + timedelta(hours=25)).isoformat(), "notify": template.notify}}
            job = WorkflowJob.model_validate(body)
            boto3.client("stepfunctions").start_execution(stateMachineArn=os.environ["WORKFLOW_STATE_MACHINE_ARN"],
                name=job.run_id, input=json.dumps({"job": job.model_dump(mode="json")}))
        except Exception:
            failures.append({"itemIdentifier": message["messageId"]})
    return {"batchItemFailures": failures}
