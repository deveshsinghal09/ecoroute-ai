import json
from datetime import UTC, datetime

import boto3
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import AwareDatetime, Field

from ecoroute.auth import Principal, require
from ecoroute.environment.pipeline import repository
from ecoroute.models import StrictModel
from ecoroute.ml.inference import LocalRegistry, MLService, MLUnavailable
from ecoroute.ml.route_index import StationPredictionIndex
from ecoroute.routing.api import service as routes_service
from ecoroute.routing.models import DepartureRequest
from ecoroute.routing.pollution import PollutionIndex
from ecoroute.routing.service import RouteService

router = APIRouter(tags=["station PM2.5 forecasting"])


class PredictionRequest(StrictModel):
    station_id: str = Field(min_length=1, max_length=100)
    issued_at: AwareDatetime | None = None
    model_version: str | None = Field(default=None, pattern=r"^[a-f0-9]{24}$")


class BatchRequest(StrictModel):
    station_ids: list[str] = Field(min_length=1, max_length=20)
    issued_at: AwareDatetime | None = None
    model_version: str | None = Field(default=None, pattern=r"^[a-f0-9]{24}$")


class PredictedDepartures(DepartureRequest):
    station_ids: list[str] = Field(min_length=1, max_length=20)
    model_version: str | None = Field(default=None, pattern=r"^[a-f0-9]{24}$")


class RemoteML:
    """Base API Lambda remains lean; optional container Lambda loads the numerical model."""

    def __init__(self, arn, region):
        self.arn, self.client = arn, boto3.client("lambda", region_name=region)

    def call(self, operation, **data):
        payload = json.dumps({"operation": operation, **data}, default=str).encode()
        response = self.client.invoke(
            FunctionName=self.arn, InvocationType="RequestResponse", Payload=payload
        )
        result = json.loads(response["Payload"].read())
        if response.get("FunctionError") or result.get("error"):
            raise MLUnavailable(result.get("error", "ml_worker_unavailable"))
        return result

    def status(self):
        return self.call("status")

    def predict(self, station_id, **data):
        return self.call("predict", station_id=station_id, **data)

    def batch(self, station_ids, **data):
        return self.call("batch", station_ids=station_ids, **data)


def ml_service(request: Request, environment=Depends(repository)):
    settings = request.app.state.settings
    if settings.ecoroute_profile == "aws":
        if not settings.ml_inference_function_arn:
            raise MLUnavailable("ml_inference_worker_not_configured")
        return RemoteML(settings.ml_inference_function_arn, settings.aws_region)
    return MLService(LocalRegistry(settings.ml_local_root), environment)


@router.get("/ml/status")
def status(user: Principal = Depends(require("read")), engine=Depends(ml_service)):
    return engine.status()


@router.get("/ml/models")
def models(user: Principal = Depends(require("read")), engine=Depends(ml_service)):
    if isinstance(engine, RemoteML):
        return engine.call("models")
    return {
        "models": [
            {
                k: m[k]
                for k in (
                    "model_version",
                    "algorithm",
                    "verified",
                    "trained_at",
                    "supported_stations",
                    "horizon_hours",
                )
            }
            for m in engine.registry.models()
        ]
    }


@router.get("/ml/metrics")
def model_metrics(
    model_version: str | None = None,
    user: Principal = Depends(require("read")),
    engine=Depends(ml_service),
):
    if isinstance(engine, RemoteML):
        return engine.call("metrics", model_version=model_version)
    manifest = engine.registry.select(model_version)
    return {
        "model_version": manifest["model_version"],
        "metrics": manifest["metrics"],
        "limitations": manifest["limitations"],
    }


@router.post("/ml/predict")
def predict(
    body: PredictionRequest, user: Principal = Depends(require("write")), engine=Depends(ml_service)
):
    return engine.predict(**body.model_dump())


@router.post("/ml/batch-predict")
def batch(
    body: BatchRequest, user: Principal = Depends(require("write")), engine=Depends(ml_service)
):
    return engine.batch(**body.model_dump())


@router.post("/routes/predict-departure-times")
def predicted_departures(
    body: PredictedDepartures,
    user: Principal = Depends(require("write")),
    engine=Depends(ml_service),
    routes=Depends(routes_service),
):
    forecast = engine.batch(body.station_ids, model_version=body.model_version)
    predictions = [r["prediction"] for r in forecast["results"] if r["status"] == "available"]
    if not predictions:
        raise HTTPException(503, "no_verified_station_predictions_available")
    versions = sorted({p["model_version"] for p in predictions})
    scoring = RouteService(
        routes.provider,
        routes.store,
        routes.objects,
        index_factory=lambda start, end: StationPredictionIndex(
            PollutionIndex.load(routes.objects, start, end), predictions
        ),
        cache_namespace="station-ml-" + "-".join(versions) + "-" + predictions[0]["issued_at"],
    )
    request = DepartureRequest(**body.model_dump(exclude={"station_ids", "model_version"}))
    result = scoring.departure_analysis(user.subject, request)
    result.update(
        station_forecasts=forecast,
        model_versions=versions,
        horizon_hours=1,
        forecast_issued_at=datetime.now(UTC).isoformat(),
        warnings=result["warnings"]
        + [
            "One-hour station predictions apply only within 1 km and 30 minutes of their valid time; unmatched segments use separately labelled provider coverage."
        ],
    )
    return result
