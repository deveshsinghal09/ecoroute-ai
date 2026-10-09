"""Load only operator-controlled verified artifacts, enforcing hash and dependency versions."""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ecoroute.environment.api import read_rows
from ecoroute.environment.schema import utc
from ecoroute.ml.preprocessing import FEATURES, feature_row, measured

VERSION = re.compile(r"^[a-f0-9]{24}$")


class MLUnavailable(ValueError):
    pass


class LocalRegistry:
    def __init__(self, root="work/ml/models"):
        self.root = Path(root)

    def models(self):
        result = []
        for path in self.root.glob("*/manifest.json"):
            if VERSION.fullmatch(path.parent.name):
                result.append(json.loads(path.read_text(encoding="utf-8")))
        return sorted(result, key=lambda m: m["trained_at"], reverse=True)

    def select(self, version=None):
        if version is not None and not VERSION.fullmatch(version):
            raise MLUnavailable("invalid_model_version")
        candidates = [
            m
            for m in self.models()
            if m.get("verified") and (version is None or m["model_version"] == version)
        ]
        if not candidates:
            raise MLUnavailable("no_verified_station_model")
        return candidates[0]

    def load(self, manifest):
        import importlib.metadata
        import joblib

        for name, version in manifest["packages"].items():
            if importlib.metadata.version(name) != version:
                raise MLUnavailable("model_dependency_version_mismatch")
        path = self.root / manifest["model_version"] / "model.joblib"
        if (
            manifest["feature_schema"] != FEATURES
            or hashlib.sha256(path.read_bytes()).hexdigest() != manifest["model_sha256"]
        ):
            raise MLUnavailable("untrusted_model_artifact")
        # Hash does not make arbitrary pickle safe. Only exact operator-controlled registry paths are accepted.
        return joblib.load(path)


class MLService:
    def __init__(self, registry, repo, *, clock=lambda: datetime.now(UTC)):
        self.registry, self.repo, self.clock = registry, repo, clock
        self._models, self._history = {}, {}
        self._selected = {}

    def status(self):
        models = self.registry.models()
        return {
            "status": "ready" if any(m.get("verified") for m in models) else "unavailable",
            "verified_models": sum(bool(m.get("verified")) for m in models),
            "horizon_hours": 1,
            "forecast_type": "station_prediction",
            "reason": None
            if any(m.get("verified") for m in models)
            else "No measured-data model passed chronological evaluation",
        }

    def predict(self, station_id, *, issued_at=None, model_version=None):
        from ecoroute.ml.training import matrix

        issued = utc(issued_at) if isinstance(issued_at, str) else issued_at or self.clock()
        if (
            not self.clock() - timedelta(minutes=30)
            <= issued
            <= self.clock() + timedelta(seconds=5)
        ):
            raise MLUnavailable("prediction_issuance_must_be_current")
        if model_version not in self._selected:
            self._selected[model_version] = self.registry.select(model_version)
        manifest = self._selected[model_version]
        if station_id not in manifest["supported_stations"]:
            raise MLUnavailable("monitoring_station_not_verified")
        key = issued.isoformat()
        if key not in self._history:
            self._history[key] = read_rows(
                self.repo, "openaq", issued - timedelta(hours=48), issued
            )
        rows, truncated = self._history[key]
        if truncated:
            raise MLUnavailable("history_truncated")
        groups, _ = measured(rows)
        features = feature_row(groups.get(station_id, []), issued)
        if features is None:
            raise MLUnavailable("fresh_observed_station_history_missing")
        if manifest["model_version"] not in self._models:
            self._models[manifest["model_version"]] = self.registry.load(manifest)
        value = max(
            0.0, float(self._models[manifest["model_version"]].predict(matrix([features]))[0])
        )
        return {
            "station_id": station_id,
            **manifest["station_locations"][station_id],
            "value_ug_m3": value,
            "pollutant": "pm25",
            "unit": "ug/m3",
            "forecast_type": "station_prediction",
            "issued_at": issued.isoformat(),
            "valid_at": (issued + timedelta(hours=1)).isoformat(),
            "horizon_hours": 1,
            "model_version": manifest["model_version"],
            "confidence": manifest["confidence"],
            "prediction_interval": None,
            "warnings": manifest["limitations"],
        }

    def batch(self, station_ids, **kwargs):
        kwargs["issued_at"] = kwargs.get("issued_at") or self.clock()
        result = []
        for station in station_ids:
            try:
                result.append(
                    {"status": "available", "prediction": self.predict(station, **kwargs)}
                )
            except MLUnavailable as exc:
                result.append({"station_id": station, "status": "unavailable", "reason": str(exc)})
        return {"results": result, "execution": "bounded_load_on_demand", "horizon_hours": 1}
