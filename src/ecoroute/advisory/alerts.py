import math
from datetime import UTC, datetime, timedelta

from ecoroute.environment.api import read_rows
from ecoroute.environment.schema import digest, utc

GUIDANCE = {"name": "WHO Global Air Quality Guidelines 2021", "pollutant": "pm25",
    "value": 15, "unit": "ug/m3", "averaging_period_hours": 24,
    "source": "https://www.who.int/publications/i/item/9789240034228",
    "interpretation": "24-hour guideline uses the 99th percentile (3-4 exceedance days/year); this advisory is not an AQI, regulatory compliance finding or diagnosis."}


def daily_window(repo, source, location_id, end, now=None):
    now = now or datetime.now(UTC)
    end = end.astimezone(UTC)
    start = end - timedelta(hours=24)
    result = {"status": "unavailable", "confidence": "unavailable", "guidance": GUIDANCE,
              "start": start.isoformat(), "end": end.isoformat(), "source": source,
              "location_id": location_id, "mean_pm25_ug_m3": None, "breach": None,
              "warnings": [], "samples": 0}
    if end.minute or end.second or end.microsecond or not now - timedelta(hours=6) <= end <= now + timedelta(hours=48):
        result["warnings"] = ["requires_recent_or_future_hour_aligned_24h_window"]
        return result
    rows, truncated = read_rows(repo, source, start, end)
    if truncated:
        result["warnings"] = ["metadata_query_truncated"]
        return result
    kind = "observed" if source == "openaq" else "forecast"
    valid = []
    for row in rows:
        value = row.get("value")
        if row.get("location_id") != location_id or row.get("pollutant") != "pm25" or row.get("kind") != kind or row.get("unit") != "ug/m3" or row.get("quality_flags"):
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 100000:
            continue
        collected = utc(row["collected_at"])
        if not timedelta(0) <= now - collected <= timedelta(hours=24):
            continue
        reported = utc(row["reported_at"])
        if kind == "observed":
            if not row.get("period_start") or reported > now or utc(row["period_start"]) != reported - timedelta(hours=1):
                continue
            stamp = reported - timedelta(hours=1)
        else:
            stamp = reported
        if start <= stamp < end and stamp.minute == stamp.second == stamp.microsecond == 0:
            valid.append((row, stamp))
    # Never mix stations/sensors or forecast retrieval vintages into one daily window.
    groups = {}
    for row, stamp in valid:
        key = row.get("sensor_id") if kind == "observed" else row["collected_at"]
        group = groups.setdefault(key, {})
        if stamp not in group or row["collected_at"] > group[stamp]["collected_at"]:
            group[stamp] = row
    complete = [group for group in groups.values() if len(group) == 24]
    result["samples"] = max((len(g) for g in groups.values()), default=0)
    if len(complete) != 1 and kind == "observed":
        result["warnings"] = ["requires_one_unambiguous_complete_sensor_window"]
        return result
    if not complete:
        result["warnings"] = ["missing_stale_or_incomplete_24h_coverage"]
        return result
    chosen = max(complete, key=lambda g: max(r["collected_at"] for r in g.values()))
    mean = sum(r["value"] for r in chosen.values()) / 24
    result.update(status="available", confidence="low", kind=kind, samples=24,
        mean_pm25_ug_m3=mean, breach=mean > GUIDANCE["value"],
        record_ids=[r["record_id"] for r in chosen.values()],
        collected_at=max(r["collected_at"] for r in chosen.values()),
        resolution_km=max((r.get("resolution_km") or 0 for r in chosen.values()), default=0) or None)
    if kind == "forecast":
        result["warnings"] = ["hourly_model_sample_mean_approximation_not_measured_24h_mean", "coarse_grid_not_street_level", "forecast_issue_time_not_supplied_by_provider"]
    result["advisory"] = ("Consider comparing lower-exposure routes or commute times; check official local guidance."
                          if result["breach"] else "No exceedance of this daily guideline in available data; this does not guarantee safety.")
    return result


def evaluate(store, owner, window):
    if window["breach"] is not True:
        return {"evaluation": window, "alert": None, "created": False}
    identifier = digest([owner, window["source"], window["location_id"], window["start"], window["end"], GUIDANCE["name"]])[:32]
    created = store.claim("alerts", owner, identifier, {"evaluation": window}, 7 * 86400)
    return {"evaluation": window, "alert": store.get("alerts", owner, identifier), "created": created}
