import hashlib
import json
import math
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


def now():
    return datetime.now(UTC)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     default=str).encode()).hexdigest()


def utc(value):
    if isinstance(value, (float, int)):
        return datetime.fromtimestamp(value, UTC)
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return result.astimezone(UTC)


class AirRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    record_id: str
    source: Literal["open_meteo", "openaq"]
    kind: Literal["observed", "forecast", "modeled"]
    pollutant: Literal["pm25", "pm10", "no2", "o3"]
    value: float | None
    unit: Literal["ug/m3"] = "ug/m3"
    original_value: float | None
    original_unit: str
    reported_at: AwareDatetime
    period_start: AwareDatetime | None = None
    collected_at: AwareDatetime
    model_run_at: AwareDatetime | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_id: str
    sensor_id: str | None = None
    resolution_km: float | None = None
    native_interval_hours: float | None = None
    model: str | None = None
    quality_flags: list[str] = Field(default_factory=list)
    provider_quality: str = "not_supplied"
    provenance_json: str
    raw_key: str = ""


def normalized(value, unit):
    """No conversion from gas mixing ratio without pressure/temperature assumptions."""
    flags = []
    if value is None:
        return None, ["missing"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("numeric value schema changed")
    if not math.isfinite(value):
        return None, ["non_finite"]
    factors = {"ug/m3": 1, "µg/m³": 1, "μg/m³": 1, "µg/m3": 1,
               "mg/m3": 1000, "mg/m³": 1000}
    if unit not in factors:
        return None, ["unsupported_unit"]
    converted = value * factors[unit]
    if converted < 0:
        return None, ["negative_concentration"]
    # Broad engineering quarantine bound, not an air-quality or medical threshold.
    if converted > 100000:
        return None, ["implausible_concentration"]
    return converted, flags


def make_record(*, source, kind, pollutant, value, unit, reported_at, collected_at,
                latitude, longitude, location_id, provenance, **extras):
    converted, flags = normalized(value, unit)
    reported, collected = utc(reported_at), utc(collected_at)
    if kind == "observed":
        if (collected - reported).total_seconds() > 6 * 3600:
            flags.append("stale_at_collection")
        if (reported - collected).total_seconds() > 300:
            flags.append("future_observation")
            converted = None
    identity = [source, kind, location_id, extras.get("sensor_id"), pollutant,
                reported.isoformat(), extras.get("period_start"), value, unit]
    if source == "open_meteo":
        # Run time is not provided: retain retrieval vintage rather than inventing an issue time.
        identity.append(collected.isoformat())
    return AirRecord(record_id=digest(identity), source=source, kind=kind, pollutant=pollutant,
        value=converted, original_value=value if value is None or math.isfinite(value) else None,
        original_unit=unit, reported_at=reported, collected_at=collected, latitude=latitude,
        longitude=longitude, location_id=location_id, quality_flags=flags,
        provenance_json=json.dumps(provenance, sort_keys=True), **extras)
