"""Conservative joins to existing curated data. No provider calls or invented concentrations."""

from datetime import UTC, datetime, timedelta

from ecoroute.environment.api import read_rows
from ecoroute.environment.schema import utc
from ecoroute.routing.geometry import distance


class PollutionIndex:
    def __init__(self, rows, *, as_of=None, truncated=False):
        self.rows = rows
        self.as_of = as_of or datetime.now(UTC)
        self.truncated = truncated

    @classmethod
    def load(cls, repo, start, end):
        rows, truncated = [], False
        for source in ("openaq", "open_meteo"):
            data, cut = read_rows(
                repo, source, start - timedelta(hours=1), end + timedelta(minutes=30)
            )
            rows.extend(data)
            truncated = truncated or cut
        return cls(rows, truncated=truncated)

    def sample(self, position, when, pollutant="pm25"):
        eligible = []
        for row in self.rows:
            if (
                row.get("pollutant") != pollutant
                or row.get("value") is None
                or row.get("unit") != "ug/m3"
                or row.get("quality_flags")
            ):
                continue
            valid, collected = utc(row["reported_at"]), utc(row["collected_at"])
            if collected > self.as_of + timedelta(minutes=1):
                continue
            delta = abs((when - valid).total_seconds())
            separation = distance(position, [row["longitude"], row["latitude"]])
            if row["source"] == "openaq":
                # No extrapolation of measured observations into future trips.
                if when > self.as_of or valid > when or delta > 3600 or separation > 1000:
                    continue
                rank = (0, separation, delta, -collected.timestamp())
            elif row["source"] == "open_meteo":
                # CAMS global native request grid is 0.4 degrees. Do not spread a cell indefinitely.
                if (
                    abs(position[0] - row["longitude"]) > 0.2001
                    or abs(position[1] - row["latitude"]) > 0.2001
                    or delta > 1800
                    or self.as_of - collected > timedelta(hours=24)
                ):
                    continue
                # The provider labels the current hourly model value "modeled" once
                # its valid time passes. It still supports nearest-hour sampling
                # within the same 30-minute tolerance; it is never an observation.
                if row["kind"] not in {"forecast", "modeled"}:
                    continue
                rank = (1, delta, -collected.timestamp(), separation)
            else:
                continue
            eligible.append((rank, row, separation))
        if not eligible:
            return {
                "value_ug_m3": None,
                "status": "unavailable",
                "confidence": "unavailable",
                "warnings": [
                    "No eligible time-matched, fresh pollutant coverage at this position."
                ],
            }
        _, row, separation = min(eligible, key=lambda x: x[0])
        modeled = row["source"] == "open_meteo"
        return {
            "value_ug_m3": row["value"],
            "status": row["kind"],
            "source": row["source"],
            "record_id": row["record_id"],
            "location_id": row["location_id"],
            "sensor_id": row.get("sensor_id"),
            "reported_at": row["reported_at"],
            "collected_at": row["collected_at"],
            "resolution_km": row.get("resolution_km"),
            "native_interval_hours": row.get("native_interval_hours"),
            "model_run_at": row.get("model_run_at"),
            "sample_distance_m": round(separation, 1),
            "quality_flags": row.get("quality_flags", []),
            "provider_quality": row.get("provider_quality", "not_supplied"),
            "raw_key": row.get("raw_key"),
            "attribution": "Open-Meteo / CAMS" if modeled else "OpenAQ / original provider",
            "provenance_json": row.get("provenance_json", "{}"),
            "confidence": "low" if modeled else "limited",
            "uncertainty": "No calibrated uncertainty interval is available.",
            "warnings": ["Coarse model cell; not street-level sensing."]
            if modeled
            else ["Nearby station is a spatial proxy, not an on-route measurement."],
        }


def score_exposure(candidate, pieces, index):
    known, covered = 0.0, 0.0
    source_metadata = {}
    for segment in pieces:
        stamp = utc(segment["sample_at"])
        pollutants = {
            name: index.sample(segment["sample_position"], stamp, name)
            for name in ("pm25", "pm10", "no2", "o3")
        }
        pm25 = pollutants["pm25"]
        value = pm25["value_ug_m3"]
        contribution = None if value is None else value * segment["duration_s"] / 3600
        segment.update(
            pollutants=pollutants,
            pm25_exposure_ug_h_m3=contribution,
            confidence=pm25["confidence"],
            warnings=pm25["warnings"],
        )
        if contribution is not None:
            known += contribution
            covered += segment["duration_s"]
        for point in pollutants.values():
            if point.get("record_id"):
                source_metadata[point["record_id"]] = {
                    k: v for k, v in point.items() if k not in {"value_ug_m3", "sample_distance_m"}
                }
    duration = candidate["duration_s"]
    complete = abs(covered - duration) < 1e-5
    warnings = list(candidate["warnings"])
    if not complete:
        warnings.append(
            "Incomplete PM2.5 coverage: full-route exposure and reduction are unavailable; known contribution is not a full-route total."
        )
    if index.truncated:
        warnings.append(
            "Environmental file query limit reached; available matches may omit newer or closer data."
        )
        complete = False
    if any(m.get("source") == "open_meteo" for m in source_metadata.values()):
        warnings.append(
            "Model values have coarse spatial support; small segment geometry does not improve pollution resolution."
        )
    return {
        "geometry": candidate["geometry"],
        "duration_s": duration,
        "distance_m": candidate["distance_m"],
        "departure_at": pieces[0]["arrival_at"],
        "mode": candidate["mode"],
        "routing_source": candidate["routing_source"],
        "terrain": candidate.get("terrain", {"status": "unavailable", "ascent_m": None, "descent_m": None}),
        "estimated_pm25_exposure_ug_h_m3": known if complete else None,
        "known_pm25_exposure_ug_h_m3": known,
        "pm25_coverage_fraction": min(1.0, max(0.0, covered / duration)),
        "exposure_definition": "sum(PM2.5 ug/m3 * segment duration hours); concentration-time index, not medical dose",
        "relative_exposure_change_percent": None,
        "confidence": "low" if complete else "unavailable",
        "pollutants": ["pm25", "pm10", "no2", "o3"],
        "source_metadata": list(source_metadata.values()),
        "segments": pieces,
        "warnings": warnings,
        "recommendation_reason": "Not yet ranked",
        "scored_at": index.as_of.isoformat(),
        "candidate_key": candidate["candidate_key"],
    }


def rank_routes(routes, request):
    baseline = min(routes, key=lambda r: (r["duration_s"], r["distance_m"]))
    allowed = baseline["duration_s"] * (1 + request.max_detour_percent / 100)
    eligible = []
    for r in routes:
        r["detour_percent"] = (r["duration_s"] / baseline["duration_s"] - 1) * 100
        r["within_detour_limit"] = r["duration_s"] <= allowed + 1e-6
        r["balanced_score"] = None
        if r["within_detour_limit"]:
            eligible.append(r)
            r["recommendation_reason"] = (
                "Eligible provider candidate; compare the selected route and objective scores."
                if r["estimated_pm25_exposure_ug_h_m3"] is not None
                else "Navigable provider candidate; full exposure ranking unavailable because pollution coverage is incomplete."
            )
        else:
            r["warnings"].append("Excluded from recommendation by maximum time detour.")
            r["recommendation_reason"] = "Excluded from recommendation by maximum time detour."
        base = baseline["estimated_pm25_exposure_ug_h_m3"]
        value = r["estimated_pm25_exposure_ug_h_m3"]
        if base is not None and base > 0 and value is not None:
            r["relative_exposure_change_percent"] = (value - base) / base * 100
        r["baseline_candidate_key"] = baseline["candidate_key"]
    full = [r for r in eligible if r["estimated_pm25_exposure_ug_h_m3"] is not None]
    lowest = (
        min(full, key=lambda r: (r["estimated_pm25_exposure_ug_h_m3"], r["duration_s"]))
        if full
        else None
    )
    # Partial coverage is not treated as cheap exposure or given an imputed full-route score.
    balanced = None
    weighted_factors_available = all(
        (not request.weather_weight or r.get("weather", {}).get("preference_cost") is not None)
        and (not request.terrain_weight or r.get("terrain", {}).get("ascent_m") is not None)
        for r in eligible
    )
    # Zero pollution weight means the user requests a time/weather/terrain score.
    # Missing PM2.5 must remain unavailable, but must not block unused factors.
    if (not request.exposure_weight or len(full) == len(eligible)) and weighted_factors_available:
        times = [r["duration_s"] for r in eligible]
        exposures = [r["estimated_pm25_exposure_ug_h_m3"] for r in full]

        def normalized(value, values):
            span = max(values) - min(values)
            return (value - min(values)) / span if span else 0.0

        for r in eligible:
            r["balanced_score"] = (1 - request.exposure_weight - request.weather_weight - request.terrain_weight) * normalized(
                r["duration_s"], times
            )
            if request.exposure_weight:
                r["balanced_score"] += request.exposure_weight * normalized(
                    r["estimated_pm25_exposure_ug_h_m3"], exposures
                )
            if request.weather_weight:
                r["balanced_score"] += request.weather_weight * normalized(r["weather"]["preference_cost"], [v["weather"]["preference_cost"] for v in eligible])
            if request.terrain_weight:
                r["balanced_score"] += request.terrain_weight * normalized(r["terrain"]["ascent_m"] / (r["distance_m"] / 1000), [v["terrain"]["ascent_m"] / (v["distance_m"] / 1000) for v in eligible])
        balanced = min(eligible, key=lambda r: (r["balanced_score"], r["duration_s"]))
    selected = {"fastest": baseline, "lowest_exposure": lowest, "balanced": balanced}[
        request.objective
    ] or baseline
    units = {
        m["location_id"]
        for r in routes
        for m in r["source_metadata"]
        if m.get("source") == "open_meteo"
    }
    all_model = all(
        s["pollutants"]["pm25"].get("source") == "open_meteo" for r in routes for s in r["segments"]
    )
    if len(units) == 1 and all_model:
        for r in routes:
            r["warnings"].append(
                "All candidates share one coarse forecast cell: any exposure difference reflects duration/time, not demonstrated street-level pollution differences."
            )
    reason = (
        "Fastest valid provider candidate; requested objective unavailable due to incomplete pollution or weighted-factor coverage."
        if request.objective != "fastest"
        and (lowest if request.objective == "lowest_exposure" else balanced) is None
        else "Selected among returned provider candidates within the time-detour limit using "
        + request.objective
        + "; not a globally optimal road-network solution."
    )
    selected["recommendation_reason"] = reason
    recommendations = {
        "fastest": baseline["candidate_key"],
        "lowest_exposure": lowest["candidate_key"] if lowest else None,
        "balanced": balanced["candidate_key"] if balanced else None,
    }
    routes.sort(
        key=lambda r: (
            not r["within_detour_limit"],
            0 if r is selected else 1,
            r["balanced_score"] if r["balanced_score"] is not None else float("inf"),
            r["duration_s"],
        )
    )
    return {
        "routes": routes,
        "selected_candidate_key": selected["candidate_key"],
        "recommendations": recommendations,
        "baseline_candidate_key": baseline["candidate_key"],
        "baseline_definition": "Fastest returned valid provider candidate at this departure; negative relative change means lower estimated exposure.",
        "score_definition": "Min-max normalization over detour-eligible candidates; (1-exposure-weather-terrain)*time + exposure_weight*exposure + weather_weight*weather_preference_cost + terrain_weight*ascent_m_per_km. Traffic is already included in driving time. Undefined if any eligible route lacks an enabled weighted factor, including pollution when exposure_weight > 0. Zero-weight factors do not block scoring; unavailable pollution remains unavailable.",
        "spatial_differentiation": "not_resolved_same_model_cell"
        if len(units) == 1 and all_model
        else "limited_by_source_coverage",
        "warnings": ["Fewer than two distinct provider routes available."]
        if len(routes) < 2
        else [],
    }
