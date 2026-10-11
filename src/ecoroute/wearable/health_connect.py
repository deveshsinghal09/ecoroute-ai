"""Fixed-target LAN adapter for mcnaveen/health-connect-webhook's documented JSON API.

No raw health responses, provider errors or Authorization headers are logged or persisted.
Only the requested nine arrays are normalized; the other sensitive data types are discarded.
"""
import ipaddress
import json
import math
import re
import threading
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from ecoroute.wearable.health_connect_models import BloodPressureValue, HealthConnectData, HealthRecord

MAX_BYTES = 4 * 1024 * 1024
MAX_RECORDS = 20000
TYPES = {
    "heart_rate": ("bpm", "bpm", 1, 300),
    "resting_heart_rate": ("bpm", "bpm", 1, 300),
    "oxygen_saturation": ("percentage", "%", 0, 100),
    "respiratory_rate": ("rate", "breaths/min", 0, 100),
    "steps": ("count", "count", 0, 1000000),
    "active_calories": ("calories", "kcal", 0, 50000),
    "total_calories": ("calories", "kcal", 0, 50000),
    "sleep": ("duration_seconds", "s", 1, 172800),
    "blood_pressure": ("systolic", "mmHg", 1, 400),
}


class HealthConnectError(Exception):
    def __init__(self, code, status=503):
        super().__init__(code)
        self.code, self.status = code, status


def validate_phone_url(value):
    try:
        p = urlsplit(value)
        address = ipaddress.ip_address(p.hostname or "")
        private_lan = any(address in ipaddress.ip_network(network) for network in (
            "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
        if (p.scheme not in {"http", "https"} or not private_lan or p.username or p.password
                or p.query or p.fragment or p.path not in {"", "/"} or not p.port):
            raise ValueError()
    except ValueError:
        raise ValueError("Health Connect requires a private LAN IP, explicit port and no URL credentials") from None
    return value.rstrip("/")


def instant(value):
    if not isinstance(value, str) or len(value) > 50:
        raise ValueError()
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError()
    return dt.astimezone(UTC)


def numeric(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError()
    if not low <= value <= high:
        raise ValueError()
    return value


def normalize(payload, *, days, cached=False, now=None, last_sync=None):
    now = now or datetime.now(UTC)
    if payload == {"status": "no_data"} and cached:
        return HealthConnectData(status="empty", retrieval="phone_cache", full_window=False, days=days,
            fetched_at=now, payload_generated_at=None, last_synchronization_at=last_sync,
            records=[], skipped_records=0, warnings=["phone_cache_empty"])
    if not isinstance(payload, dict) or not isinstance(payload.get("app_version"), str):
        raise HealthConnectError("health_connect_invalid_response", 502)
    try:
        generated = instant(payload["timestamp"])
        if generated.timestamp() > now.timestamp() + 300:
            raise ValueError()
    except (ValueError, KeyError):
        raise HealthConnectError("health_connect_invalid_response", 502) from None
    records, warnings, skipped, seen = [], set(), 0, set()
    count = sum(len(payload[k]) for k in TYPES if isinstance(payload.get(k), list))
    if count > MAX_RECORDS:
        raise HealthConnectError("health_connect_payload_too_large", 502)
    for kind, (field, unit, low, high) in TYPES.items():
        rows = payload.get(kind, [])
        if not isinstance(rows, list):
            raise HealthConnectError("health_connect_schema_changed", 502)
        for row in rows:
            try:
                if not isinstance(row, dict):
                    raise ValueError()
                metadata = row.get("metadata") or {}
                if not isinstance(metadata, dict):
                    raise ValueError()
                origin = metadata.get("data_origin")
                # A package identifier is provenance, not a verified watch manufacturer.
                if origin is not None and (not isinstance(origin, str) or
                        not re.fullmatch(r"[A-Za-z0-9_.]{1,200}", origin)):
                    raise ValueError()
                method = metadata.get("recording_method")
                if method not in {None, "actively_recorded", "automatically_recorded", "manual_entry", "unknown"}:
                    method = "unknown"
                aggregate = kind in {"heart_rate", "oxygen_saturation", "respiratory_rate"} and any(
                    key in row for key in ("avg", "min", "max"))
                value = numeric(row.get("avg") if aggregate else row.get(field), low, high)
                if aggregate:
                    minimum, maximum = numeric(row.get("min"), low, high), numeric(row.get("max"), low, high)
                    if not minimum <= value <= maximum:
                        raise ValueError()
                if kind == "steps" and int(value) != value:
                    raise ValueError()
                if kind == "blood_pressure":
                    diastolic = numeric(row.get("diastolic"), 1, 300)
                    if diastolic > value:
                        raise ValueError()
                    value = BloodPressureValue(systolic=value, diastolic=diastolic)
                start, end, quality = None, None, []
                resolution = "bucket_average" if aggregate else "sample"
                if kind in {"steps", "active_calories", "total_calories", "sleep"}:
                    if kind == "sleep":
                        from datetime import timedelta
                        end = instant(row["session_end_time"])
                        start = end - timedelta(seconds=value)
                        resolution = "session"
                    else:
                        start, end = instant(row["start_time"]), instant(row["end_time"])
                        resolution = "interval"
                    if start >= end or start > now:
                        raise ValueError()
                    if end > now:
                        quality.append("interval_not_finished")
                    stamp = end
                else:
                    stamp = instant(row["time"])
                    if stamp.timestamp() > now.timestamp() + 300:
                        raise ValueError()
                record = HealthRecord(measurement_type=kind, value=value, unit=unit, timestamp=stamp,
                    start_time=start, end_time=end, source_application=origin, recording_method=method,
                    resolution=resolution, quality=quality)
                signature = json.dumps(record.model_dump(mode="json"), sort_keys=True)
                if signature in seen:
                    warnings.add("exact_duplicate_records_removed")
                    continue
                seen.add(signature)
                records.append(record)
                if not origin:
                    warnings.add("source_application_not_reported")
            except (ValueError, KeyError, TypeError, OverflowError):
                skipped += 1
                warnings.add("invalid_records_skipped:" + kind)
    if not records:
        warnings.add("missing_arrays_do_not_identify_permission_state")
    if cached:
        warnings.add("phone_cache_may_be_incremental_daily_totals_unavailable")
    return HealthConnectData(status="available" if records else "empty", days=days,
        retrieval="phone_cache" if cached else "fresh", full_window=not cached,
        fetched_at=now, payload_generated_at=generated, last_synchronization_at=last_sync,
        records=sorted(records, key=lambda r: r.timestamp), skipped_records=skipped, warnings=sorted(warnings))


class HealthConnectClient:
    def __init__(self, settings, *, transport=None, clock=None):
        self.settings, self.transport = settings, transport
        self.clock = clock or (lambda: datetime.now(UTC))
        self.lock = threading.Lock()

    def get_json(self, path, params=None):
        if not self.settings.health_connect_base_url:
            raise HealthConnectError("health_connect_not_configured")
        base = validate_phone_url(self.settings.health_connect_base_url)
        token = self.settings.health_connect_token.get_secret_value()
        try:
            with httpx.Client(transport=self.transport, timeout=httpx.Timeout(6, connect=2),
                    follow_redirects=False, trust_env=False) as client:
                with client.stream("GET", base + path, params=params,
                        headers={"Authorization": "Bearer " + token} if token else {}) as response:
                    if response.status_code in {401, 403}:
                        raise HealthConnectError("health_connect_phone_permission_denied", 502)
                    if response.status_code == 429:
                        raise HealthConnectError("health_connect_phone_rate_limited", 429)
                    if response.status_code != 200:
                        raise HealthConnectError("health_connect_phone_read_failed", 502)
                    if "application/json" not in response.headers.get("content-type", "").lower():
                        raise HealthConnectError("health_connect_invalid_response", 502)
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > MAX_BYTES:
                            raise HealthConnectError("health_connect_payload_too_large", 502)
                    def reject_constant(value):
                        raise ValueError()
                    return json.loads(raw, parse_constant=reject_constant)
        except httpx.TimeoutException:
            raise HealthConnectError("health_connect_timeout", 504) from None
        except httpx.RequestError:
            raise HealthConnectError("health_connect_phone_unreachable") from None
        except (ValueError, UnicodeError, RecursionError):
            raise HealthConnectError("health_connect_invalid_response", 502) from None

    def synchronization(self):
        try:
            payload = self.get_json("/health")
            ms = payload.get("lastSyncTime") if isinstance(payload, dict) else None
            if isinstance(ms, (int, float)) and not isinstance(ms, bool) and 0 < ms <= self.clock().timestamp() * 1000:
                return datetime.fromtimestamp(ms / 1000, UTC)
        except (HealthConnectError, ValueError, OverflowError):
            pass
        return None

    def status(self):
        payload = self.get_json("/ping")
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            raise HealthConnectError("health_connect_invalid_response", 502)
        return self.synchronization()

    def data(self, days=7, cached=False):
        if not 1 <= days <= 30:
            raise HealthConnectError("health_connect_invalid_days", 422)
        if not self.lock.acquire(blocking=False):
            raise HealthConnectError("health_connect_request_in_progress", 429)
        try:
            payload = self.get_json("/latest" if cached else "/", None if cached else {"days": days})
            return normalize(payload, days=days, cached=cached, now=self.clock(), last_sync=self.synchronization())
        finally:
            self.lock.release()
