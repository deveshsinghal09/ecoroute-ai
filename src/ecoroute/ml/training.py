"""Validation selects a candidate; untouched test data gates promotion against persistence."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from ecoroute.environment.schema import digest
from ecoroute.ml.preprocessing import FEATURES, load_dataset


def metrics(rows, predictions):
    import numpy as np

    truth = np.array([r["target_pm25"] for r in rows], dtype=float)
    difference = np.asarray(predictions) - truth
    return {
        "mae": float(np.mean(np.abs(difference))),
        "rmse": float(np.sqrt(np.mean(difference**2))),
        "mean_bias": float(np.mean(difference)),
        "sample_count": len(rows),
        "unit": "ug/m3",
        "first_target_at": min(r["target_at"] for r in rows),
        "last_target_at": max(r["target_at"] for r in rows),
    }


def matrix(rows):
    import numpy as np

    return np.array(
        [[float("nan") if r.get(k) is None else r[k] for k in FEATURES] for r in rows], dtype=float
    )


def report(rows, predictions):
    groups = {}
    for index, row in enumerate(rows):
        groups.setdefault(row["station_id"], []).append(index)
    return {
        "overall": metrics(rows, predictions),
        "by_station": {
            station: metrics([rows[i] for i in indices], [predictions[i] for i in indices])
            for station, indices in groups.items()
        },
    }


def evaluate(parts, models):
    scores = {}
    for name in ("validation", "test"):
        rows = parts[name]
        scores[name] = {"persistence": report(rows, [r["persistence"] for r in rows])}
        for algorithm, model in models.items():
            scores[name][algorithm] = report(rows, model.predict(matrix(rows)).clip(min=0))
        paired = [r for r in rows if r["provider_forecast"] is not None]
        scores[name]["provider_forecast"] = {
            "status": "available" if paired else "unavailable_no_historical_issued_forecasts",
            "coverage_fraction": len(paired) / len(rows),
            "paired_cohort": {
                "provider": report(paired, [r["provider_forecast"] for r in paired]),
                "persistence": report(paired, [r["persistence"] for r in paired]),
                **{
                    algorithm: report(paired, model.predict(matrix(paired)).clip(min=0))
                    for algorithm, model in models.items()
                },
            }
            if paired
            else None,
        }
    return scores


def train(dataset, destination):
    import joblib
    import numpy as np
    import scipy
    import sklearn
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from threadpoolctl import threadpool_limits

    parts, manifest = load_dataset(dataset)
    models = {
        "random_forest": make_pipeline(
            SimpleImputer(add_indicator=True, keep_empty_features=True),
            RandomForestRegressor(
                n_estimators=100, max_depth=8, min_samples_leaf=3, random_state=42, n_jobs=1
            ),
        ),
        "hist_gradient_boosting": make_pipeline(
            SimpleImputer(add_indicator=True, keep_empty_features=True),
            HistGradientBoostingRegressor(
                max_iter=100,
                max_leaf_nodes=15,
                min_samples_leaf=10,
                random_state=42,
                early_stopping=False,
            ),
        ),
    }
    with threadpool_limits(limits=1):
        for model in models.values():
            model.fit(matrix(parts["train"]), [r["target_pm25"] for r in parts["train"]])
        scores = evaluate(parts, models)
    selected = min(models, key=lambda name: (scores["validation"][name]["overall"]["mae"], name))
    base = scores["test"]["persistence"]["overall"]
    actual = scores["test"][selected]["overall"]
    verified = actual["mae"] < base["mae"] and actual["rmse"] <= base["rmse"]
    # Do not promote a station with no observed test evidence of improvement.
    station_verified = [
        station
        for station, score in scores["test"][selected]["by_station"].items()
        if score["sample_count"] >= 12
        and score["mae"] < scores["test"]["persistence"]["by_station"][station]["mae"]
        and score["rmse"] <= scores["test"]["persistence"]["by_station"][station]["rmse"]
    ]
    metadata = {
        "schema_version": manifest["schema_version"],
        "feature_schema": FEATURES,
        "horizon_hours": 1,
        "dataset_version": manifest["dataset_version"],
        "dataset_manifest": manifest,
        "algorithm": selected,
        "trained_at": datetime.now(UTC).isoformat(),
        "verified": verified and bool(station_verified),
        "supported_stations": station_verified if verified else [],
        "all_training_stations": manifest["supported_stations"],
        "station_locations": {
            r["station_id"]: {"latitude": r["latitude"], "longitude": r["longitude"]}
            for r in parts["train"]
        },
        "metrics": scores,
        "promotion_rule": "Validation MAE selects; test MAE must beat persistence and RMSE must not be worse, also per promoted station with >=12 test samples",
        "confidence": "limited_empirical_station_validation",
        "prediction_interval": None,
        "limitations": [
            "Station prediction, not street-level pollution",
            "No calibrated interval; one temporal test does not establish seasonal generalization",
        ],
        "packages": {
            "scikit-learn": sklearn.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "joblib": joblib.__version__,
        },
    }
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / "training-model.joblib"
    joblib.dump(models[selected], temporary, compress=3)
    sha = hashlib.sha256(temporary.read_bytes()).hexdigest()
    version = digest([manifest["dataset_version"], selected, sha])[:24]
    target = root / version
    target.mkdir(exist_ok=True)
    temporary.replace(target / "model.joblib")
    metadata.update(model_version=version, model_sha256=sha)
    (target / "manifest.json").write_text(
        json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "event": "ml_training_evaluated",
                "model_version": version,
                "algorithm": selected,
                "verified": metadata["verified"],
                "test_mae": actual["mae"],
                "persistence_mae": base["mae"],
            }
        )
    )
    return target, metadata
