from ecoroute.environment.schema import utc
from ecoroute.routing.geometry import distance


class StationPredictionIndex:
    def __init__(self, base, predictions):
        self.base, self.predictions = base, predictions
        self.as_of, self.truncated = base.as_of, base.truncated

    def sample(self, position, when, pollutant="pm25"):
        eligible = [
            p
            for p in self.predictions
            if pollutant == "pm25"
            and utc(p["issued_at"]) <= self.as_of
            and abs((utc(p["valid_at"]) - when).total_seconds()) <= 1800
            and distance(position, [p["longitude"], p["latitude"]]) <= 1000
        ]
        if not eligible:
            return self.base.sample(position, when, pollutant)
        p = min(eligible, key=lambda p: distance(position, [p["longitude"], p["latitude"]]))
        return {
            "value_ug_m3": p["value_ug_m3"],
            "status": "station_prediction",
            "source": "ecoroute_ml",
            "record_id": p["model_version"] + ":" + p["station_id"] + ":" + p["valid_at"],
            "location_id": p["station_id"],
            "model_version": p["model_version"],
            "horizon_hours": 1,
            "reported_at": p["valid_at"],
            "collected_at": p["issued_at"],
            "confidence": p["confidence"],
            "quality_flags": [],
            "resolution_km": None,
            "spatial_proxy_radius_m": 1000,
            "uncertainty": "No calibrated prediction interval",
            "prediction_interval": None,
            "warnings": [
                "Route-segment estimate uses a nearby station prediction; on-road concentration is not measured."
            ],
        }
