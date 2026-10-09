from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime, Field, model_validator

from ecoroute.advisory.alerts import daily_window, evaluate
from ecoroute.advisory.explanation import explain
from ecoroute.advisory.notifications import notify_sms
from ecoroute.auth import Principal, require
from ecoroute.environment.pipeline import repository
from ecoroute.environment.providers import grid
from ecoroute.models import Identifier, Point, StrictModel
from ecoroute.routing.api import service as routes_service
from ecoroute.routing.models import CompareRequest

INDIA = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")

router = APIRouter(tags=["grounded environmental advisories"])


class ExplanationRequest(StrictModel):
    route_ids: list[Identifier] = Field(min_length=1, max_length=6)


class AlertRequest(StrictModel):
    source: Literal["openaq", "open_meteo"]
    location_id: str = Field(min_length=1, max_length=100)
    end_at: AwareDatetime
    notify: bool = False


class SchoolRequest(StrictModel):
    school_id: Identifier
    school_name: str = Field(min_length=1, max_length=100)
    position: Point
    forecast_location_id: str = Field(min_length=1, max_length=100)
    commute_start: time
    commute_end: time
    route: CompareRequest

    @model_validator(mode="after")
    def commute(self):
        lat, lon = grid(self.position.latitude, self.position.longitude)
        if self.forecast_location_id != f"cams_global:{lat:.4f}:{lon:.4f}":
            raise ValueError("Forecast grid must correspond to school coordinates")
        if self.commute_start.tzinfo or self.commute_end.tzinfo or self.commute_start >= self.commute_end:
            raise ValueError("Commute window uses increasing local Asia/Kolkata times")
        if not isinstance(self.route.destination, Point) or self.route.destination != self.position:
            raise ValueError("Route destination must equal configured school coordinates")
        local = self.route.departure_at.astimezone(INDIA).time().replace(tzinfo=None)
        if not self.commute_start <= local <= self.commute_end:
            raise ValueError("Departure must be in configured commute window")
        return self


@router.post("/ai/explain-route")
def explanation(body: ExplanationRequest, request: Request, user: Principal = Depends(require("write")), engine=Depends(routes_service), repo=Depends(repository)):
    routes = [engine.read(user.subject, identifier) for identifier in body.route_ids]
    if len({r.get("baseline_route_id") for r in routes}) > 1:
        raise HTTPException(422, "routes_must_share_documented_baseline")
    return explain(routes, request.app.state.settings, repo)


@router.post("/alerts/evaluate")
def alert_evaluation(body: AlertRequest, request: Request, user: Principal = Depends(require("write")), repo=Depends(repository)):
    result = evaluate(request.app.state.store, user.subject,
                      daily_window(repo, body.source, body.location_id, body.end_at))
    result["notification"] = notify_sms(request.app.state.store, user.subject, result["alert"], request.app.state.settings) if body.notify and result["alert"] else {"status": "not_requested", "delivered": False}
    return result


@router.get("/alerts")
def alerts(request: Request, user: Principal = Depends(require("read"))):
    rows, truncated = request.app.state.store.list_records("alerts", user.subject)
    return {"alerts": rows, "truncated": truncated}


@router.post("/schools/compare-routes")
def school_compare(body: SchoolRequest, request: Request, user: Principal = Depends(require("write")), engine=Depends(routes_service)):
    comparison = engine.compare(user.subject, body.route)
    request.app.state.store.put_record("schools", user.subject, body.school_id,
        body.model_dump(mode="json", exclude={"route"}), 90 * 86400)
    return {"school_id": body.school_id, "comparison": comparison, "confidence": "low",
            "advisory": "Estimated route exposure comparison; no official closure decision or medical advice."}


@router.get("/schools/forecast")
def school_forecast(request: Request, school_id: Identifier, forecast_date: date | None = Query(default=None), user: Principal = Depends(require("read")), repo=Depends(repository)):
    school = request.app.state.store.get("schools", user.subject, school_id)
    if not school:
        raise HTTPException(404, "school_not_found")
    day = forecast_date or (datetime.now(INDIA).date() + timedelta(days=1))
    # India midnight is not UTC-hour aligned. Use the preceding UTC hour for an
    # explicit approximate school-day window, within the provider's two-day forecast.
    commute = datetime.combine(day, time.fromisoformat(school["commute_start"]), INDIA)
    start = datetime.combine(day, time.min, INDIA).astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    result = daily_window(repo, "open_meteo", school["forecast_location_id"], start + timedelta(hours=24))
    return {"school_id": school_id, "commute_start": commute.isoformat(), "forecast": result,
            "official_closure_status": "not_provided", "warning": "Window starts at the UTC hour preceding India midnight, not exact local calendar midnight; coarse grid is not school-site sensing."}


@router.get("/workflows/status")
def workflow_status(request: Request, user: Principal = Depends(require("read"))):
    rows, truncated = request.app.state.store.list_records("workflows", user.subject)
    return {"configured": bool(request.app.state.settings.workflow_state_machine_arn),
            "schedule_enablement": "requires_separate_operator_approval", "runs": rows,
            "truncated": truncated, "deployment_verified": False}
