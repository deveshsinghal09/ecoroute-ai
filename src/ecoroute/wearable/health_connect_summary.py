"""Conservative daily summaries; no prorating counts or guessing overlapping-source priority."""
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ecoroute.wearable.health_connect import HealthConnectError
from ecoroute.wearable.health_connect_models import HealthConnectSummary, HealthMetric, HealthMetrics


def timezone(value):
    try:
        if not isinstance(value, str) or len(value) > 100:
            raise ValueError()
        return ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        raise HealthConnectError("health_connect_invalid_timezone", 422) from None


def latest(rows, unit, now):
    rows = [r for r in rows if r.timestamp <= now]
    if not rows:
        return HealthMetric(unit=unit)
    stamp = max(r.timestamp for r in rows)
    selected = [r for r in rows if r.timestamp == stamp]
    values = {str(r.value) for r in selected}
    if len(values) != 1:
        return HealthMetric(unit=unit, warnings=["conflicting_latest_records"])
    row = selected[0]
    return HealthMetric(value=row.value, unit=unit, status="available", timestamp=stamp,
        source_applications=sorted({r.source_application for r in selected if r.source_application}),
        resolution=row.resolution, stale=(now - stamp).total_seconds() > 900,
        warnings=["source_application_not_reported"] if not row.source_application else [])


def intervals(rows, unit, start, end, now, full_window, invalid=False):
    candidates = [r for r in rows if r.start_time < end and r.end_time > start]
    if not full_window:
        return HealthMetric(unit=unit, warnings=["cached_incremental_payload_not_a_daily_total"])
    if invalid:
        return HealthMetric(unit=unit, warnings=["invalid_records_prevent_daily_total"])
    if not candidates:
        return HealthMetric(unit=unit)
    if any(r.end_time > now for r in candidates):
        return HealthMetric(unit=unit, warnings=["unfinished_or_projected_intervals_not_actual_daily_total"])
    if any(r.start_time < start or r.end_time > end for r in candidates):
        return HealthMetric(unit=unit, warnings=["cross_midnight_counts_cannot_be_split_without_samples"])
    candidates.sort(key=lambda r: (r.start_time, r.end_time))
    if any(current.start_time < previous.end_time for previous, current in zip(candidates, candidates[1:], strict=False)):
        return HealthMetric(unit=unit, warnings=["overlapping_intervals_total_unavailable"])
    return HealthMetric(value=sum(r.value for r in candidates), unit=unit, status="available",
        timestamp=max(r.end_time for r in candidates), resolution="recorded_interval_sum",
        source_applications=sorted({r.source_application for r in candidates if r.source_application}),
        warnings=["total_of_available_records_not_proof_of_full_day_coverage"])


def sleep_metric(rows, day, zone, now, full_window, invalid=False):
    sessions = sorted([r for r in rows if r.end_time <= now and r.end_time.astimezone(zone).date() == day],
                      key=lambda r: r.start_time)
    if not sessions or not full_window or invalid:
        return HealthMetric(unit="s", warnings=[] if full_window else ["cached_sleep_window_incomplete"]), sessions
    merged = []
    for row in sessions:
        if merged and row.start_time <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], row.end_time)
        else:
            merged.append([row.start_time, row.end_time])
    return HealthMetric(value=sum((end - start).total_seconds() for start, end in merged), unit="s",
        status="available", timestamp=max(r.end_time for r in sessions), resolution="session_interval_union",
        source_applications=sorted({r.source_application for r in sessions if r.source_application}),
        warnings=["session_duration_includes_any_awake_time_and_is_not_a_sleep_score"]), sessions


def summarize(data, *, selected_date: date | None = None, zone_name="UTC", now=None):
    now = now or datetime.now(UTC)
    zone = timezone(zone_name)
    day = selected_date or now.astimezone(zone).date()
    if not (now - timedelta(days=data.days - 1)).astimezone(zone).date() <= day <= now.astimezone(zone).date():
        raise HealthConnectError("health_connect_date_outside_window", 422)
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    by_kind = {kind: [r for r in data.records if r.measurement_type == kind] for kind in (
        "heart_rate", "blood_pressure", "oxygen_saturation", "resting_heart_rate", "respiratory_rate",
        "steps", "total_calories", "active_calories", "sleep")}
    # Latest vital measurements come from the requested rolling window, rather than being zero-filled
    # when the selected day's interval metrics have no records. Dates/age remain attached to each value.
    metrics = {kind: latest([r for r in by_kind[kind] if r.timestamp >= now - timedelta(days=data.days)], unit, now)
               for kind, unit in (("heart_rate", "bpm"), ("blood_pressure", "mmHg"),
                   ("oxygen_saturation", "%"), ("resting_heart_rate", "bpm"), ("respiratory_rate", "breaths/min"))}
    metrics["steps"] = intervals(by_kind["steps"], "count", start, end, now, data.full_window,
                                 "invalid_records_skipped:steps" in data.warnings)
    # Total energy already includes active energy. Never add active and total together.
    total_on_day = any(r.start_time < end and r.end_time > start for r in by_kind["total_calories"])
    active_on_day = any(r.start_time < end and r.end_time > start for r in by_kind["active_calories"])
    basis = "total" if total_on_day else "active" if active_on_day else None
    kind = (basis or "total") + "_calories"
    metrics["calories_burned"] = intervals(by_kind[kind], "kcal", start, end, now, data.full_window,
                                          "invalid_records_skipped:" + kind in data.warnings)
    metrics["sleep"], sessions = sleep_metric(by_kind["sleep"], day, zone, now, data.full_window,
                                              "invalid_records_skipped:sleep" in data.warnings)
    return HealthConnectSummary(status="available" if any(m.value is not None for m in metrics.values()) else "empty",
        selected_date=day, timezone=zone_name, fetched_at=data.fetched_at,
        payload_generated_at=data.payload_generated_at, last_synchronization_at=data.last_synchronization_at,
        retrieval=data.retrieval, metrics=HealthMetrics(**metrics), calorie_basis=basis, sleep_sessions=sessions,
        warnings=data.warnings, skipped_records=data.skipped_records)
