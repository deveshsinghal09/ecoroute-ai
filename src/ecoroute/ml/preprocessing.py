"""One-hour station targets with strict retrieval-vintage availability, never forecast labels."""

import hashlib
import io
import json
import math
from collections import defaultdict
from datetime import timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ecoroute.environment.schema import AirRecord, digest, utc

FEATURES = [
    "pm25_latest",
    "pm25_lag1",
    "pm25_lag2",
    "pm25_lag3",
    "pm25_lag24",
    "pm25_mean3",
    "pm25_mean6",
    "observation_age_hours",
    "latitude",
    "longitude",
    "hour_sin",
    "hour_cos",
    "week_sin",
    "week_cos",
    "temperature_c",
    "humidity_pct",
    "wind_m_s",
    "wind_direction_sin",
    "wind_direction_cos",
]
SCHEMA_VERSION = "station-next-hour-v1"
IST = timezone(timedelta(hours=5, minutes=30))


class InsufficientData(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__("insufficient_measured_history")


def measured(rows):
    groups = defaultdict(list)
    rejected = defaultdict(int)
    for raw in rows:
        try:
            row = AirRecord.model_validate(raw).model_dump(mode="json")
        except ValueError:
            rejected["schema"] += 1
            continue
        if row["source"] != "openaq" or row["kind"] != "observed" or row["pollutant"] != "pm25":
            rejected["not_measured_pm25"] += 1
            continue
        if (
            row["value"] is None
            or row["quality_flags"]
            or not 76.8 <= row["longitude"] <= 77.6
            or not 28.3 <= row["latitude"] <= 29.0
        ):
            rejected["quality_or_geography"] += 1
            continue
        if (
            row["period_start"]
            and not 0 < (utc(row["reported_at"]) - utc(row["period_start"])).total_seconds() <= 3600
        ):
            rejected["unsupported_averaging_period"] += 1
            continue
        station = row["location_id"] + ":" + str(row["sensor_id"] or "unknown")
        groups[station].append(row)
    return {
        k: sorted(v, key=lambda r: (r["reported_at"], r["collected_at"])) for k, v in groups.items()
    }, dict(rejected)


def eligible_history(rows, issued):
    # A later revision or late backfill cannot supply a feature at an earlier issuance.
    vintages = {}
    for row in rows:
        valid, received = utc(row["reported_at"]), utc(row["collected_at"])
        if valid <= issued and received <= issued:
            if valid not in vintages or received > utc(vintages[valid]["collected_at"]):
                vintages[valid] = row
    return sorted(vintages.values(), key=lambda r: r["reported_at"])


def feature_row(rows, issued, weather=()):
    history = eligible_history(rows, issued)
    if not history or issued - utc(history[-1]["reported_at"]) > timedelta(minutes=90):
        return None
    last = history[-1]
    # Do not mix mobile sensors or inconsistent station coordinates.
    if any(
        abs(r["latitude"] - last["latitude"]) > 0.001
        or abs(r["longitude"] - last["longitude"]) > 0.001
        for r in history
    ):
        return None
    values = {
        "pm25_latest": last["value"],
        "observation_age_hours": (issued - utc(last["reported_at"])).total_seconds() / 3600,
        "latitude": last["latitude"],
        "longitude": last["longitude"],
    }
    for lag in (1, 2, 3, 24):
        stamp = issued - timedelta(hours=lag)
        matches = [
            r for r in history if abs((utc(r["reported_at"]) - stamp).total_seconds()) <= 300
        ]
        values["pm25_lag" + str(lag)] = matches[-1]["value"] if matches else None
    for hours in (3, 6):
        previous = [
            r["value"]
            for r in history
            if issued - timedelta(hours=hours) < utc(r["reported_at"]) <= issued
        ]
        values["pm25_mean" + str(hours)] = (
            sum(previous) / len(previous) if len(previous) >= hours - 1 else None
        )
    local = issued.astimezone(IST)
    hour = local.hour + local.minute / 60
    values.update(
        hour_sin=math.sin(2 * math.pi * hour / 24),
        hour_cos=math.cos(2 * math.pi * hour / 24),
        week_sin=math.sin(2 * math.pi * local.weekday() / 7),
        week_cos=math.cos(2 * math.pi * local.weekday() / 7),
    )
    # Optional weather must provide an explicit vintage, valid time, coordinates and normalized units.
    candidates = [
        w
        for w in weather
        if utc(w["available_at"]) <= issued
        and utc(w["reported_at"]) <= issued
        and issued - utc(w["reported_at"]) <= timedelta(hours=2)
        and abs(w["latitude"] - last["latitude"]) <= 0.2
        and abs(w["longitude"] - last["longitude"]) <= 0.2
    ]
    chosen = max(candidates, key=lambda w: w["reported_at"], default={})
    for key, low, high in (
        ("temperature_c", -60, 60),
        ("humidity_pct", 0, 100),
        ("wind_m_s", 0, 100),
    ):
        value = chosen.get(key)
        values[key] = (
            value
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and low <= value <= high
            else None
        )
    direction = chosen.get("wind_direction_deg")
    valid_direction = (
        isinstance(direction, (int, float)) and math.isfinite(direction) and 0 <= direction <= 360
    )
    values["wind_direction_sin"] = math.sin(math.radians(direction)) if valid_direction else None
    values["wind_direction_cos"] = math.cos(math.radians(direction)) if valid_direction else None
    return {key: values.get(key) for key in FEATURES}


def provider_baseline(rows, latitude, longitude, issued, target):
    candidates = [
        r
        for r in rows
        if r.get("source") == "open_meteo"
        and r.get("kind") == "forecast"
        and r.get("pollutant") == "pm25"
        and r.get("unit") == "ug/m3"
        and r.get("value") is not None
        and not r.get("quality_flags")
        and utc(r["collected_at"]) <= issued
        and (not r.get("model_run_at") or utc(r["model_run_at"]) <= issued)
        and abs((utc(r["reported_at"]) - target).total_seconds()) <= 1800
        and abs(r["latitude"] - latitude) <= 0.2001
        and abs(r["longitude"] - longitude) <= 0.2001
    ]
    return max(candidates, key=lambda r: r["collected_at"])["value"] if candidates else None


def prepare(rows, *, weather=(), min_train=72, min_validation=24, min_test=24, min_span_days=7):
    groups, rejected = measured(rows)
    samples = []
    for station, observations in groups.items():
        # Use exact hourly valid times; do not interpolate labels across missing hours.
        by_time = defaultdict(list)
        for r in observations:
            by_time[utc(r["reported_at"])].append(r)
        for issued in sorted(by_time):
            if issued.minute or issued.second or issued.microsecond:
                continue
            target = issued + timedelta(hours=1)
            labels = by_time.get(target, [])
            features = feature_row(observations, issued, weather)
            if not labels or features is None:
                continue
            label = min(labels, key=lambda r: r["collected_at"])
            samples.append(
                {
                    **features,
                    "station_id": station,
                    "issued_at": issued.isoformat(),
                    "target_at": target.isoformat(),
                    "label_available_at": label["collected_at"],
                    "target_pm25": label["value"],
                    "persistence": features["pm25_latest"],
                    "provider_forecast": provider_baseline(
                        rows, label["latitude"], label["longitude"], issued, target
                    ),
                }
            )
    times = sorted({r["issued_at"] for r in samples})
    report = {
        "input_records": len(rows),
        "measured_pm25_records": sum(map(len, groups.values())),
        "supported_station_series": len(groups),
        "eligible_samples": len(samples),
        "rejected": rejected,
        "feature_schema": FEATURES,
        "schema_version": SCHEMA_VERSION,
        "horizon_hours": 1,
        "availability_rule": "reported_at <= issuance and collected_at <= issuance for every feature",
    }
    if len(times) < 3 or (utc(times[-1]) - utc(times[0])).total_seconds() < min_span_days * 86400:
        raise InsufficientData(
            {
                **report,
                "status": "insufficient_data",
                "reason": "insufficient_span_or_hourly_samples",
            }
        )
    val_start, test_start = times[int(len(times) * 0.6)], times[int(len(times) * 0.8)]
    parts = {"train": [], "validation": [], "test": []}
    for row in samples:
        if row["issued_at"] < val_start:
            if row["target_at"] < val_start and utc(row["label_available_at"]) < utc(val_start):
                parts["train"].append(row)
        elif row["issued_at"] < test_start:
            if row["target_at"] < test_start and utc(row["label_available_at"]) < utc(test_start):
                parts["validation"].append(row)
        else:
            parts["test"].append(row)
    # A model supports only monitoring series actually represented in every split.
    supported = set.intersection(*({r["station_id"] for r in values} for values in parts.values()))
    parts = {k: [r for r in v if r["station_id"] in supported] for k, v in parts.items()}
    report.update(
        split_counts={k: len(v) for k, v in parts.items()},
        validation_start=val_start,
        test_start=test_start,
        supported_stations=sorted(supported),
    )
    if any(
        len(parts[k]) < minimum
        for k, minimum in (("train", min_train), ("validation", min_validation), ("test", min_test))
    ):
        raise InsufficientData(
            {
                **report,
                "status": "insufficient_data",
                "reason": "insufficient_chronological_split_counts",
            }
        )
    report.update(
        status="ready",
        dataset_version=digest([SCHEMA_VERSION, samples])[:24],
        date_ranges={
            k: {
                "first_issued_at": min(r["issued_at"] for r in v),
                "last_target_at": max(r["target_at"] for r in v),
            }
            for k, v in parts.items()
        },
    )
    return parts, report


def write_dataset(parts, manifest, destination):
    root = Path(destination) / manifest["dataset_version"]
    root.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name, rows in parts.items():
        fields = [
            pa.field(k, pa.float64())
            for k in FEATURES + ["target_pm25", "persistence", "provider_forecast"]
        ]
        fields += [
            pa.field(k, pa.string())
            for k in ("station_id", "issued_at", "target_at", "label_available_at")
        ]
        path = root / (name + ".parquet")
        pq.write_table(
            pa.Table.from_pylist(rows, schema=pa.schema(fields)), path, compression="snappy"
        )
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {**manifest, "sha256": hashes}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return root


def load_dataset(root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "ready"
        or manifest.get("feature_schema") != FEATURES
        or manifest.get("schema_version") != SCHEMA_VERSION
    ):
        raise ValueError("unverified_dataset_schema")
    parts = {}
    for name in ("train", "validation", "test"):
        content = (root / (name + ".parquet")).read_bytes()
        if hashlib.sha256(content).hexdigest() != manifest["sha256"][name + ".parquet"]:
            raise ValueError("dataset_hash_mismatch")
        parts[name] = pq.ParquetFile(io.BytesIO(content)).read().to_pylist()
    for first, second in (("train", "validation"), ("validation", "test")):
        cutoff = min(utc(r["issued_at"]) for r in parts[second])
        if any(
            max(utc(r["target_at"]), utc(r["label_available_at"])) >= cutoff for r in parts[first]
        ):
            raise ValueError("chronological_label_leakage")
    return parts, manifest
