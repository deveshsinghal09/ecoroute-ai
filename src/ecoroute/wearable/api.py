from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import AwareDatetime

from ecoroute.auth import Principal, require
from ecoroute.models import Identifier
from ecoroute.routers import IdempotencyKey
from ecoroute.wearable.archive import Archive
from ecoroute.wearable.models import Consent, Measurement, Registration
from ecoroute.wearable.repository import WearableRepository, topic

router = APIRouter(tags=["devices and consented wearable readings"])


def repository(request: Request):
    return WearableRepository(request.app.state.store, request.app.state.settings.wearables_table)


def access(repo, user, device, scope="telemetry"):
    record = repo.device(user.subject, device)
    if record["deleting"] or not record["consent"].get("telemetry") or not record["consent"].get(scope):
        raise HTTPException(403, "wearable_consent_required")
    return record


@router.post("/devices/register", status_code=201)
def register(body: Registration, request: Request, response: Response,
             idempotency_key: IdempotencyKey, user: Principal = Depends(require("write")),
             repo=Depends(repository)):
    if body.bridge == "demo" and not (request.app.state.settings.ecoroute_profile == "local" and request.app.state.settings.wearable_demo_mode):
        raise HTTPException(403, "synthetic_telemetry_disabled")
    device, created = repo.register(user.subject, body, idempotency_key)
    response.status_code = 201 if created else 200
    return {"device_id": device["device_id"], "consent": device["consent"],
            "mqtt_topic": topic(user.subject, device["device_id"]),
            "mqtt_client_id": "eco-" + device["device_id"], "hardware_connected": False}


@router.post("/wearables/consent")
def consent(body: Consent, user: Principal = Depends(require("write")), repo=Depends(repository)):
    record = repo.consent(user.subject, body)
    return {"device_id": body.device_id, "consent": record["consent"], "revision": record["epoch"],
            "warning": "Revocation blocks processing immediately; revoke an enrolled certificate separately to stop broker access."}


@router.post("/wearables/measurements", status_code=201)
def measurements(body: Measurement, request: Request, response: Response,
                 user: Principal = Depends(require("write")), repo=Depends(repository)):
    if body.journey_id and not request.app.state.store.get("journeys", user.subject, body.journey_id):
        raise HTTPException(404, "journey_not_found")
    settings = request.app.state.settings
    record, created = repo.ingest(user.subject, body,
        allow_demo=settings.ecoroute_profile == "local" and settings.wearable_demo_mode)
    # AWS stream archives accepted records asynchronously, including HTTPS events.
    if settings.ecoroute_profile == "local":
        Archive(settings).write(repo, user.subject, record)
    response.status_code = 201 if created else 200
    return {"event_id": body.event_id, "device_id": body.device_id, "accepted": True,
            "duplicate": not created, "expires_at": record["expires_at"]}


@router.get("/wearables/history")
def history(device_id: Identifier, start: AwareDatetime, end: AwareDatetime,
            limit: int = Query(default=100, ge=1, le=200), cursor: str | None = Query(default=None, max_length=150),
            user: Principal = Depends(require("read")), repo=Depends(repository)):
    access(repo, user, device_id, "history")
    now = datetime.now(UTC)
    if not now - timedelta(days=7) <= start < end <= now + timedelta(minutes=5):
        raise HTTPException(422, "invalid_history_window")
    rows, next_cursor = repo.history(user.subject, device_id, start, end, limit=limit, cursor=cursor)
    return {"measurements": rows, "next_cursor": next_cursor, "truncated": next_cursor is not None}


@router.get("/wearables/latest")
def latest(device_id: Identifier, user: Principal = Depends(require("read")), repo=Depends(repository)):
    access(repo, user, device_id)
    # Reverse query retains latest by observed time, not message arrival order.
    pk = repo.device(user.subject, device_id)["owner_key"]
    prefix = f"measurement#{device_id}#"
    if repo.local:
        with repo.store.lock:
            row = repo.store.db.execute("SELECT payload FROM records WHERE owner=? AND kind='wearable' AND id BETWEEN ? AND ? AND expires>? ORDER BY id DESC LIMIT 1",
                (pk, prefix, prefix + "z", int(datetime.now(UTC).timestamp()))).fetchone()
        import json
        result = json.loads(row[0]) if row else None
    else:
        import json
        response = repo.store.client.query(TableName=repo.table,
            KeyConditionExpression="pk = :pk AND begins_with(sk, :prefix)",
            ExpressionAttributeValues={":pk": {"S": pk}, ":prefix": {"S": prefix}},
            ScanIndexForward=False, ConsistentRead=True, Limit=1)
        rows = response.get("Items", [])
        result = json.loads(rows[0]["payload"]["S"]) if rows and int(rows[0]["expires_at"]["N"]) > datetime.now(UTC).timestamp() else None
    return {"measurement": result, "status": "available" if result else "unavailable"}


@router.delete("/wearables/data")
def delete_data(device_id: Identifier, request: Request, user: Principal = Depends(require("write")), repo=Depends(repository)):
    repo.consent(user.subject, Consent(device_id=device_id, telemetry=False), deleting=True)
    pending = repo.purge(user.subject, device_id)
    pending = Archive(request.app.state.settings).purge(user.subject, device_id) or pending
    return {"device_id": device_id, "status": "deletion_pending_repeat_request" if pending else "deleted",
            "device_disabled": True, "retained": "Device/consent tombstone90d; primary readings removed. AWS stream/failure records expire within24h; in-flight archive writes recheck deletion."}


@router.get("/journeys/{journey_id}/wearable-correlation")
def correlation(journey_id: Identifier, device_id: Identifier, request: Request,
                user: Principal = Depends(require("read")), repo=Depends(repository)):
    from ecoroute.environment.pipeline import repository as environment_repository
    from ecoroute.routing.api import service
    from ecoroute.routing.pollution import PollutionIndex
    from ecoroute.environment.schema import utc
    from ecoroute.wearable.correlation import correlate
    access(repo, user, device_id, "correlation")
    journey = request.app.state.store.get("journeys", user.subject, journey_id)
    if not journey:
        raise HTTPException(404, "journey_not_found")
    if not journey.get("route_id"):
        raise HTTPException(409, "journey_route_not_linked")
    route = service(request).read(user.subject, journey["route_id"])
    if not route.get("segments"):
        raise HTTPException(409, "journey_route_has_no_segments")
    start, end = utc(route["segments"][0]["arrival_at"]), utc(route["segments"][-1]["end_at"])
    rows, cursor = repo.history(user.subject, device_id, start, end)
    rows = [r for r in rows if r.get("journey_id") in (None, journey_id)]
    result = correlate(rows, route, PollutionIndex.load(environment_repository(), start, end))
    return {"journey_id": journey_id, "device_id": device_id, "truncated": cursor is not None, **result}
