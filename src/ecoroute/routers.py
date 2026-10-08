"""Versioned routers; unconnected data products return explicit 503 responses."""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response

from ecoroute.auth import Principal, require
from ecoroute.models import Identifier, Preferences, RouteRequest, TelemetryBatch, TripCreate

IdempotencyKey = Annotated[str, Header(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
navigation = APIRouter(prefix="/navigation", tags=["navigation"])
air_quality = APIRouter(prefix="/air-quality", tags=["air quality"])
predictions = APIRouter(prefix="/predictions", tags=["predictions"])
wearables = APIRouter(prefix="/wearables", tags=["wearable telemetry"])
alerts = APIRouter(prefix="/alerts", tags=["alerts"])
school_safety = APIRouter(prefix="/school-safety", tags=["school safety"])
trips = APIRouter(prefix="/trips", tags=["trips"])


@navigation.post("/routes")
def routes(body: RouteRequest, user: Principal = Depends(require("write"))):
    raise HTTPException(503, "routing_provider_not_connected")


@air_quality.get("")
def air(longitude: float = Query(ge=-180, le=180, allow_inf_nan=False),
        latitude: float = Query(ge=-90, le=90, allow_inf_nan=False),
        user: Principal = Depends(require("read"))):
    raise HTTPException(503, "air_quality_data_unavailable")


@predictions.get("")
def forecast(longitude: float = Query(ge=-180, le=180, allow_inf_nan=False),
             latitude: float = Query(ge=-90, le=90, allow_inf_nan=False),
             horizon_hours: int = Query(default=1, ge=1, le=6),
             user: Principal = Depends(require("read"))):
    raise HTTPException(503, "forecast_model_unavailable")


@school_safety.get("")
def school(longitude: float = Query(ge=-180, le=180, allow_inf_nan=False),
           latitude: float = Query(ge=-90, le=90, allow_inf_nan=False),
           user: Principal = Depends(require("read"))):
    raise HTTPException(503, "school_safety_data_unavailable")


@trips.post("", status_code=201)
def create_trip(body: TripCreate, request: Request, response: Response,
                idempotency_key: IdempotencyKey, user: Principal = Depends(require("write"))):
    record, created = request.app.state.store.create(
        "journeys", user.subject, {**body.model_dump(mode="json"), "status": "active"}, idempotency_key,
    )
    response.status_code = 201 if created else 200
    return record


@trips.get("/{trip_id}")
def get_trip(trip_id: Identifier, request: Request, user: Principal = Depends(require("read"))):
    record = request.app.state.store.get("journeys", user.subject, trip_id)
    if record is None:
        raise HTTPException(404, "trip_not_found")
    return record


@wearables.post("/telemetry", status_code=201)
def telemetry(body: TelemetryBatch, request: Request, response: Response,
              idempotency_key: IdempotencyKey, user: Principal = Depends(require("write"))):
    record, created = request.app.state.store.create(
        "telemetry", user.subject, body.model_dump(mode="json"), idempotency_key,
    )
    response.status_code = 201 if created else 200
    return {"id": record["id"], "sample_count": len(record["samples"]),
            "source": record["source"], "expires_at": record["expires_at"]}


@alerts.put("/preferences")
def set_preferences(body: Preferences, request: Request, user: Principal = Depends(require("write"))):
    return request.app.state.store.put_preferences(user.subject, body.model_dump())


@alerts.get("/preferences")
def get_preferences(request: Request, user: Principal = Depends(require("read"))):
    return request.app.state.store.get("preferences", user.subject, "settings") or Preferences().model_dump()


@alerts.get("/{alert_id}")
def get_alert(alert_id: Identifier, request: Request, user: Principal = Depends(require("read"))):
    record = request.app.state.store.get("alerts", user.subject, alert_id)
    if record is None:
        raise HTTPException(404, "alert_not_found")
    return record


ROUTERS = (navigation, air_quality, predictions, wearables, alerts, school_safety, trips)
