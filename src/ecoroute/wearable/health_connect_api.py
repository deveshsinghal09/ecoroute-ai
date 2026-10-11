"""Owner-bound private LAN health bridge, independent of public guest routing."""
import secrets
import time
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials

from ecoroute.auth import Principal, bearer
from ecoroute.wearable.health_connect import HealthConnectClient, HealthConnectError
from ecoroute.wearable.health_connect_models import HealthConnectData, HealthConnectStatus, HealthConnectSummary
from ecoroute.wearable.health_connect_summary import summarize, timezone

router = APIRouter(prefix="/wearables/health-connect", tags=["private local Health Connect"])


def owner(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != "bearer" or len(credentials.credentials) > 8192:
        raise HTTPException(401, "bearer_token_required", headers={"WWW-Authenticate": "Bearer"})
    settings = request.app.state.settings
    local_key = settings.health_connect_local_access_token.get_secret_value()
    paired = local_key and secrets.compare_digest(credentials.credentials.encode(), local_key.encode())
    if paired:
        if (settings.ecoroute_profile != "local" or not request.client or request.client.host not in {
                "127.0.0.1", "::1"} or request.url.hostname not in {"127.0.0.1", "localhost", "::1"}):
            raise HTTPException(403, "health_connect_local_access_only")
        origin = request.headers.get("origin")
        if origin and origin not in settings.cors_origins:
            raise HTTPException(403, "health_connect_origin_denied")
        if time.time() >= settings.health_connect_local_access_expires_at:
            raise HTTPException(401, "health_connect_pairing_expired")
        user = Principal(settings.health_connect_owner_sub, frozenset({"ecoroute/read"}))
        request.state.health_connect_authentication = "local_pairing"
    else:
        if local_key and not request.app.state.verifier.configured:
            raise HTTPException(401, "invalid_access_token")
        user = request.app.state.verifier.verify(credentials.credentials)
        request.state.health_connect_authentication = "cognito"
        if "ecoroute/read" not in user.scopes:
            raise HTTPException(403, "insufficient_scope")
    if not settings.health_connect_owner_sub:
        raise HTTPException(503, "health_connect_owner_not_configured")
    if not secrets.compare_digest(user.subject.encode(), settings.health_connect_owner_sub.encode()):
        raise HTTPException(403, "health_connect_owner_mismatch")
    return user


def client(request: Request):
    return request.app.state.health_connect


def invoke(operation):
    try:
        return operation()
    except HealthConnectError as error:
        raise HTTPException(error.status, error.code) from None


def consented(consent: bool = Query(default=False), user: Principal = Depends(owner)):
    if not consent:
        raise HTTPException(403, "health_connect_consent_required")
    return user


@router.get("/status", response_model=HealthConnectStatus)
def status(request: Request, user: Principal = Depends(owner), phone: HealthConnectClient = Depends(client)):
    sync = invoke(phone.status)
    return HealthConnectStatus(last_synchronization_at=sync, fetched_at=datetime.now(UTC),
                               authentication=request.state.health_connect_authentication)


@router.get("/data", response_model=HealthConnectData)
def data(days: int = Query(default=7, ge=1, le=30), cached: bool = False,
         user: Principal = Depends(consented), phone: HealthConnectClient = Depends(client)):
    return invoke(lambda: phone.data(days, cached))


@router.get("/summary", response_model=HealthConnectSummary)
def summary(days: int = Query(default=7, ge=1, le=30), selected_date: date | None = None,
            timezone_name: str = Query(default="UTC", min_length=1, max_length=100),
            cached: bool = False, user: Principal = Depends(consented),
            phone: HealthConnectClient = Depends(client)):
    # Reject invalid timezone/date before performing any phone request.
    zone = invoke(lambda: timezone(timezone_name))
    now = phone.clock()
    if selected_date and not (now - timedelta(days=days - 1)).astimezone(zone).date() <= selected_date <= now.astimezone(zone).date():
        raise HTTPException(422, "health_connect_date_outside_window")
    return invoke(lambda: summarize(phone.data(days, cached), selected_date=selected_date,
                                    zone_name=timezone_name, now=phone.clock()))
