import io
from datetime import UTC, datetime, timedelta
from typing import Literal

import pyarrow.parquet as pq
from fastapi import APIRouter, Depends, HTTPException, Query

from ecoroute.auth import Principal, require
from ecoroute.environment.pipeline import repository
from ecoroute.environment.schema import utc

router = APIRouter(tags=["environmental datasets"])
Source = Literal["open_meteo", "openaq"]


def read_rows(repo, source, start, end):
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    files, truncated = repo.query("FILES#" + source, start.date().isoformat(),
                                  end.date().isoformat() + "~", limit=20)
    records = {}
    for obj in files:
        rows = pq.read_table(io.BytesIO(repo.get_bytes(obj["key"]))).to_pylist()
        for row in rows:
            if start <= utc(row["reported_at"]) <= end:
                old = records.get(row["record_id"])
                if old is None or row["collected_at"] > old["collected_at"]:
                    records[row["record_id"]] = row
    return list(records.values()), truncated


def envelope(rows, truncated=False):
    return {"status": "available" if rows else "unavailable", "records": rows[:200],
            "truncated": truncated or len(rows) > 200, "attribution": "Open-Meteo / CAMS; OpenAQ / original providers as recorded",
            "limitations": "Global model is approximately 45 km; not street-level sensing. Missing values are never filled."}


@router.get("/air-quality/current")
def current(source: Source = "openaq", location_id: str = Query(min_length=1, max_length=100),
            user: Principal = Depends(require("read")), repo=Depends(repository)):
    clock = datetime.now(UTC)
    rows, truncated = read_rows(repo, source, clock - timedelta(hours=6), clock)
    latest = {}
    for row in rows:
        if row["location_id"] == location_id and row["value"] is not None:
            key = (row["sensor_id"], row["pollutant"])
            if key not in latest or (row["reported_at"], row["collected_at"]) > (
                    latest[key]["reported_at"], latest[key]["collected_at"]):
                latest[key] = row
    result = list(latest.values())
    for row in result:
        row["age_seconds"] = int((clock - utc(row["reported_at"])).total_seconds())
        if row["kind"] == "forecast":
            row["kind"] = "modeled"  # its valid time is now in the past; never an observation
    return envelope(result, truncated)


@router.get("/air-quality/forecast")
def forecast(location_id: str = Query(min_length=1, max_length=100),
             hours: int = Query(default=24, ge=1, le=48),
             user: Principal = Depends(require("read")), repo=Depends(repository)):
    clock = datetime.now(UTC)
    rows, truncated = read_rows(repo, "open_meteo", clock, clock + timedelta(hours=hours))
    latest = {}
    for row in rows:
        if (row["location_id"] != location_id or row["kind"] != "forecast"
                or clock - utc(row["collected_at"]) > timedelta(hours=24)):
            continue
        key = (row["pollutant"], row["reported_at"])
        if key not in latest or row["collected_at"] > latest[key]["collected_at"]:
            latest[key] = row
    return envelope(list(latest.values()), truncated)


@router.get("/air-quality/history")
def history(source: Source, start: datetime, end: datetime,
            location_id: str = Query(min_length=1, max_length=100),
            user: Principal = Depends(require("read")), repo=Depends(repository)):
    if start.tzinfo is None or end.tzinfo is None or not timedelta(0) <= end - start <= timedelta(days=7):
        raise HTTPException(422, "history_requires_aware_timestamps_and_maximum_7_days")
    rows, truncated = read_rows(repo, source, start, end)
    return envelope([r for r in rows if r["location_id"] == location_id], truncated)


@router.get("/air-quality/stations")
def stations(user: Principal = Depends(require("read")), repo=Depends(repository)):
    rows, truncated = repo.query("STATIONS#openaq", limit=100)
    return {"status": "available" if rows else "unavailable", "stations": rows, "truncated": truncated}


@router.get("/data/quality")
def quality(source: Source = "open_meteo", user: Principal = Depends(require("read")),
            repo=Depends(repository)):
    reports, truncated = repo.query("QUALITY#" + source, limit=10)
    return {"reports": reports, "truncated": truncated,
            "status": "available" if reports else "unavailable",
            "freshness_note": "Quality flags refer to collection time; current endpoint also applies a six-hour valid-time window."}
