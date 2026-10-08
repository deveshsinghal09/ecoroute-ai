from fastapi import APIRouter, Depends, Query, Request

from ecoroute.auth import Principal, require
from ecoroute.environment.pipeline import repository
from ecoroute.models import Identifier
from ecoroute.routing.models import CompareRequest, DepartureRequest, ExposureRequest
from ecoroute.routing.service import create_service

router = APIRouter(prefix="/routes", tags=["pollution-aware routes"])


def service(request: Request):
    if not hasattr(request.app.state, "route_service"):
        request.app.state.route_service = create_service(
            request.app.state.settings, request.app.state.store, repository()
        )
    return request.app.state.route_service


@router.post("/compare")
def compare(
    body: CompareRequest, user: Principal = Depends(require("write")), engine=Depends(service)
):
    return engine.compare(user.subject, body)


@router.post("/optimize")
def optimize(
    body: CompareRequest, user: Principal = Depends(require("write")), engine=Depends(service)
):
    comparison = engine.compare(user.subject, body)
    return {
        "recommended_route": next(
            r for r in comparison["routes"] if r["route_id"] == comparison["selected_route_id"]
        ),
        "recommended_route_ids": comparison["recommended_route_ids"],
        "baseline_route_id": comparison["baseline_route_id"],
        "baseline_definition": comparison["baseline_definition"],
        "score_definition": comparison["score_definition"],
        "spatial_differentiation": comparison["spatial_differentiation"],
        "warnings": comparison["warnings"],
    }


@router.post("/exposure")
def exposure(
    body: ExposureRequest, user: Principal = Depends(require("write")), engine=Depends(service)
):
    return engine.exposure(user.subject, body)


@router.post("/departure-time-analysis")
def departures(
    body: DepartureRequest, user: Principal = Depends(require("write")), engine=Depends(service)
):
    return engine.departure_analysis(user.subject, body)


@router.get("/{route_id}")
def get_route(
    route_id: Identifier, user: Principal = Depends(require("read")), engine=Depends(service)
):
    result = engine.read(user.subject, route_id)
    return {k: v for k, v in result.items() if k != "segments"}


@router.get("/{route_id}/segments")
def get_segments(
    route_id: Identifier,
    offset: int = Query(default=0, ge=0, le=600),
    limit: int = Query(default=100, ge=1, le=200),
    user: Principal = Depends(require("read")),
    engine=Depends(service),
):
    rows = engine.read(user.subject, route_id)["segments"]
    return {
        "route_id": route_id,
        "segments": rows[offset : offset + limit],
        "next_offset": offset + limit if offset + limit < len(rows) else None,
        "total": len(rows),
    }
