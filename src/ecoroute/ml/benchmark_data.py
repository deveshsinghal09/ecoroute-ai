"""Large retrospective experiments; never relabel foreign or synthetic records as OpenAQ."""

import csv
import hashlib
import io
import math
import random
import re
import zipfile
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone

from ecoroute.ml.preprocessing import FEATURES, SCHEMA_VERSION, InsufficientData

UCI_URL = "https://archive.ics.uci.edu/static/public/501/beijing+multi+site+air+quality+data.zip"
UCI_SOURCE = "https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data"
BEIJING = timezone(timedelta(hours=8))
CSV_NAME = re.compile(r"(?:.*/)?PRSA_Data_([A-Za-z]+)_20130301-20170228.csv$")
REQUIRED = {"year", "month", "day", "hour", "PM2.5", "TEMP", "WSPM", "wd", "station"}
WINDS = {
    name: index * 22.5
    for index, name in enumerate(
        [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
    )
}


def number(value, low=-math.inf, high=math.inf):
    if value in (None, "", "NA"):
        return None
    result = float(value)
    return result if math.isfinite(result) and low <= result <= high else None


def read_uci(content):
    """Bound archives and parse in memory; never extract paths supplied by a ZIP."""
    if len(content) > 30 * 1024 * 1024:
        raise ValueError("dataset_download_too_large")
    archive = zipfile.ZipFile(io.BytesIO(content))
    info = archive.infolist()
    if len(info) > 50 or sum(item.file_size for item in info) > 200 * 1024 * 1024:
        raise ValueError("dataset_archive_too_large")
    nested = [
        item for item in info if item.filename.endswith("PRSA2017_Data_20130301-20170228.zip")
    ]
    if nested:
        if len(nested) != 1:
            raise ValueError("unexpected_nested_archives")
        archive = zipfile.ZipFile(io.BytesIO(archive.read(nested[0])))
        info = archive.infolist()
        if len(info) > 50 or sum(item.file_size for item in info) > 200 * 1024 * 1024:
            raise ValueError("dataset_archive_too_large")
    count, groups = Counter(), {}
    for item in info:
        match = CSV_NAME.fullmatch(item.filename)
        if not match:
            continue
        station = match[1]
        if station in groups:
            raise ValueError("duplicate_station_file")
        rows = {}
        with archive.open(item) as binary:
            reader = csv.DictReader(io.TextIOWrapper(binary, encoding="utf-8-sig"))
            if not REQUIRED <= set(reader.fieldnames or []):
                raise ValueError("uci_schema_changed")
            for raw in reader:
                count["input_records"] += 1
                if raw["station"] != station:
                    raise ValueError("station_identity_mismatch")
                stamp = datetime(
                    *(int(raw[k]) for k in ("year", "month", "day", "hour")), tzinfo=BEIJING
                ).astimezone(UTC)
                if stamp in rows:
                    raise ValueError("duplicate_station_timestamp")
                value = number(raw["PM2.5"], 0, 2000)
                if value is None:
                    count["missing_or_invalid_pm25"] += 1
                rows[stamp] = {
                    "value": value,
                    "temperature_c": number(raw["TEMP"], -80, 65),
                    "wind_m_s": number(raw["WSPM"], 0, 100),
                    "wind_direction": WINDS.get(raw["wd"]),
                }
        groups["uci_beijing:" + station] = rows
    if not groups:
        raise ValueError("uci_station_files_missing")
    return groups, dict(count)


def synthetic_series(*, records=100_000, stations=8, seed=42):
    """Correlated hourly test scenarios, never measurements or validated Delhi distributions."""
    if not 360 <= records <= 1_000_000 or not 1 <= stations <= 24:
        raise ValueError("synthetic_size_out_of_bounds")
    rng = random.Random(seed)
    start = datetime(2020, 1, 1, tzinfo=UTC)
    groups = {}
    for station in range(stations):
        history, previous = {}, 35 + station * 4
        hours = records // stations + int(station < records % stations)
        for hour in range(hours):
            daily = math.sin(2 * math.pi * hour / 24)
            seasonal = math.cos(2 * math.pi * hour / (24 * 365))
            wind = max(0, 2 + rng.gauss(0, 0.7))
            equilibrium = 45 + 18 * seasonal + 15 * daily + station * 4 - 4 * wind
            previous = max(0, 0.8 * previous + 0.2 * equilibrium + rng.gauss(0, 7))
            history[start + timedelta(hours=hour)] = {
                "value": None if rng.random() < 0.01 else previous,
                "temperature_c": 24 - 8 * seasonal + 4 * daily + rng.gauss(0, 1),
                "wind_m_s": wind,
                "wind_direction": rng.uniform(0, 360),
            }
        groups[f"synthetic:scenario-{station + 1}"] = history
    return groups, {"input_records": records, "seed": seed, "scenario_stations": stations}


def prepare_experiment(groups, audit, *, source, source_sha256, synthetic=False):
    samples = []
    local_zone = UTC if synthetic else BEIJING
    for station, history in sorted(groups.items()):
        for issued, observation in sorted(history.items()):
            target = issued + timedelta(hours=1)
            label = history.get(target)
            if observation["value"] is None or label is None or label["value"] is None:
                continue
            row = dict.fromkeys(FEATURES)
            row.update(
                pm25_latest=observation["value"],
                observation_age_hours=0,
                temperature_c=observation["temperature_c"],
                wind_m_s=observation["wind_m_s"],
            )
            for lag in (1, 2, 3, 24):
                row["pm25_lag" + str(lag)] = history.get(issued - timedelta(hours=lag), {}).get(
                    "value"
                )
            for window in (3, 6):
                values = [
                    history.get(issued - timedelta(hours=k), {}).get("value") for k in range(window)
                ]
                values = [v for v in values if v is not None]
                row["pm25_mean" + str(window)] = (
                    sum(values) / len(values) if len(values) >= window - 1 else None
                )
            local = issued.astimezone(local_zone)
            row.update(
                hour_sin=math.sin(2 * math.pi * local.hour / 24),
                hour_cos=math.cos(2 * math.pi * local.hour / 24),
                week_sin=math.sin(2 * math.pi * local.weekday() / 7),
                week_cos=math.cos(2 * math.pi * local.weekday() / 7),
            )
            wind = observation["wind_direction"]
            if wind is not None:
                row.update(
                    wind_direction_sin=math.sin(math.radians(wind)),
                    wind_direction_cos=math.cos(math.radians(wind)),
                )
            row.update(
                station_id=station,
                issued_at=issued.isoformat(),
                target_at=target.isoformat(),
                label_available_at=target.isoformat(),
                target_pm25=label["value"],
                persistence=observation["value"],
                provider_forecast=None,
            )
            samples.append(row)
    times = sorted({row["issued_at"] for row in samples})
    if len(times) < 168:
        raise InsufficientData({"status": "insufficient_data", "eligible_samples": len(samples)})
    validation, test = times[int(len(times) * 0.6)], times[int(len(times) * 0.8)]
    parts = {"train": [], "validation": [], "test": []}
    for row in samples:
        split = (
            "train"
            if row["issued_at"] < validation
            else "validation"
            if row["issued_at"] < test
            else "test"
        )
        boundary = validation if split == "train" else test if split == "validation" else None
        if boundary is None or row["target_at"] < boundary:
            parts[split].append(row)
    if any(len(part) < 24 for part in parts.values()):
        raise InsufficientData({"status": "insufficient_data", "reason": "split_counts"})
    limitations = [
        "Experimental only: not a Delhi model and cannot be promoted to navigation inference.",
        "No station coordinates supplied; latitude/longitude remain missing, never fabricated.",
        "No archived issued provider forecasts; provider baseline unavailable.",
        "Retrospective assumption: observations were available at their recorded hour; actual publication delays/revisions unknown.",
        "Weather values are historical observations, not future forecasts; humidity not supplied and remains missing.",
    ]
    if synthetic:
        limitations.append(
            "All values generated; seasonal patterns/noise are test assumptions, not calibrated real-world distributions."
        )
    version = hashlib.sha256((SCHEMA_VERSION + source + source_sha256).encode()).hexdigest()[:24]
    manifest = {
        **audit,
        "status": "ready",
        "dataset_version": version,
        "schema_version": SCHEMA_VERSION,
        "feature_schema": FEATURES,
        "horizon_hours": 1,
        "source": source,
        "source_sha256": source_sha256,
        "training_scope": "synthetic_experiment"
        if synthetic
        else "beijing_retrospective_experiment",
        "synthetic": synthetic,
        "feature_availability_verified": False,
        "availability_rule": "Retrospective hour-availability assumption, NOT verified provider publication times",
        "unit": "ug/m3",
        "timezone": "UTC" if synthetic else "Asia/Shanghai converted to UTC",
        "geography": "none_synthetic" if synthetic else "Beijing, China",
        "license": "generated_test_data" if synthetic else "CC BY 4.0",
        "attribution": "EcoRoute generated scenarios"
        if synthetic
        else "Chen, S. (2017). Beijing Multi-Site Air Quality. UCI. DOI:10.24432/C5RK5G",
        "eligible_samples": len(samples),
        "purged_boundary_samples": len(samples) - sum(map(len, parts.values())),
        "supported_stations": sorted(groups),
        "split_counts": {k: len(v) for k, v in parts.items()},
        "date_ranges": {
            k: {
                "first_issued_at": min(r["issued_at"] for r in rows),
                "last_target_at": max(r["target_at"] for r in rows),
            }
            for k, rows in parts.items()
        },
        "limitations": limitations,
    }
    return parts, manifest
