"""Opt-in Linux container smoke using synthetic mechanics data only; no AWS/network runtime."""

import json
import os
import subprocess
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from ecoroute.environment.schema import make_record
from ecoroute.ml.preprocessing import FEATURES, prepare, write_dataset


@pytest.mark.skipif(
    os.getenv("ECOROUTE_TEST_ML_CONTAINER") != "true",
    reason="Docker container test is explicit opt-in",
)
def test_sagemaker_train_and_serve_container(tmp_path):
    import math

    start = datetime(2026, 8, 1, tzinfo=UTC)
    rows = [
        make_record(
            source="openaq",
            kind="observed",
            pollutant="pm25",
            value=50 + 20 * math.sin(i * math.pi / 12),
            unit="ug/m3",
            reported_at=(start + timedelta(hours=i)).isoformat(),
            collected_at=(start + timedelta(hours=i, minutes=5)).isoformat(),
            latitude=28.6139,
            longitude=77.209,
            location_id="TEST_ONLY",
            sensor_id="TEST_ONLY",
            provenance={"synthetic_test_only": True},
        ).model_dump(mode="json")
        for i in range(360)
    ]
    parts, manifest = prepare(rows)
    dataset = write_dataset(parts, manifest, tmp_path / "datasets")
    output = tmp_path / "models"
    output.mkdir()
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "-v",
            f"{dataset}:/opt/ml/input/data/dataset:ro",
            "-v",
            f"{output}:/opt/ml/model",
            "ecoroute-ml:ci",
            "train",
        ],
        check=True,
        timeout=120,
    )
    manifests = list(output.glob("*/manifest.json"))
    assert len(manifests) == 1 and not json.loads(manifests[0].read_text())["verified"]
    # Serving must refuse a synthetic artifact, including one that beats a synthetic baseline.
    refused = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "-v", f"{output}:/opt/ml/model:ro", "ecoroute-ml:ci", "serve"],
        capture_output=True, text=True, timeout=30,
    )
    assert refused.returncode != 0 and "no_verified_station_model" in refused.stderr
    # Test-only fixture metadata supplies a stub approved registry for the HTTP contract below.
    model = json.loads(manifests[0].read_text())
    model.update(verified=True, supported_stations=model["all_training_stations"])
    model["dataset_manifest"]["synthetic"] = False
    manifests[0].write_text(json.dumps(model))
    container = subprocess.check_output(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "-p",
            "127.0.0.1:8767:8080",
            "-v",
            f"{output}:/opt/ml/model:ro",
            "ecoroute-ml:ci",
            "serve",
        ],
        text=True,
    ).strip()
    try:
        for _ in range(60):
            try:
                if httpx.get("http://127.0.0.1:8767/ping", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        response = httpx.post(
            "http://127.0.0.1:8767/invocations",
            json=[{k: parts["test"][0][k] for k in FEATURES}],
            timeout=10,
        )
        assert response.status_code == 200 and len(response.json()["predictions_ug_m3"]) == 1
    finally:
        subprocess.run(["docker", "stop", container], check=False, timeout=30)
