"""Descriptive time/location matching, never causation or medical dose."""
from ecoroute.environment.schema import utc
from ecoroute.routing.geometry import distance


def correlate(rows, route, index):
    output = []
    for row in rows:
        when, position = utc(row["timestamp"]), row.get("position")
        if not position or row.get("accuracy_m", 10001) > 100:
            output.append({"event_id": row["event_id"], "status": "unavailable", "reason": "GPS missing or accuracy worse than 100m"})
            continue
        point = [position["longitude"], position["latitude"]]
        candidates = [s for s in route["segments"]
            if utc(s["arrival_at"]) <= when <= utc(s["end_at"])
            and distance(point, s["sample_position"]) <= max(100, s["length_m"] / 2 + 100)]
        if not candidates:
            output.append({"event_id": row["event_id"], "status": "unavailable", "reason": "Outside planned route space/time window"})
            continue
        segment = min(candidates, key=lambda s: distance(point, s["sample_position"]))
        pollution = index.sample(point, when)
        output.append({"event_id": row["event_id"], "timestamp": row["timestamp"],
            "heart_rate_bpm": row.get("heart_rate_bpm"), "activity": row["activity"],
            "segment_index": segment["segment_index"], "pm25": pollution,
            "status": "paired" if pollution["value_ug_m3"] is not None else "unavailable"})
    return {"samples": output, "paired_count": sum(r["status"] == "paired" for r in output),
        "exposure_index": None, "medical_stress_score": None,
        "warnings": ["Heart rate is not a pollution measurement; pairing establishes no causal relationship.",
                     "Planned route windows and sparse samples do not prove actual exposure or dose.",
                     "No instant PM2.5 value is compared with a 24-hour guideline."]}
