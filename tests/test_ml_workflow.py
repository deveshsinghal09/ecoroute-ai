"""Offline orchestration tests; artificial archives never become real model evidence."""
import hashlib
import io
import json
import tarfile
from types import SimpleNamespace

import pytest

from ecoroute.ml import workflow


def test_unready_dataset_stops_before_training(monkeypatch):
    monkeypatch.setenv("ML_BUCKET", "ecoroute-test")
    body = json.dumps({"status": "insufficient_data"}).encode()
    s3 = SimpleNamespace(get_object=lambda **kw: {"ContentLength": len(body), "Body": io.BytesIO(body)})
    with pytest.raises(ValueError, match="measured_dataset_not_ready"):
        workflow.validate(s3, {"dataset_version": "a" * 24})


@pytest.mark.parametrize("tamper", [False, True])
def test_publication_checks_hash_before_registry_write(monkeypatch, tamper):
    bucket, name, version = "ecoroute-test", "ecoroute-test-job", "a" * 24
    artifact = b"synthetic archive bytes, deliberately not a pickle"
    manifest = {
        "model_version": version, "model_sha256": hashlib.sha256(artifact).hexdigest(),
        "algorithm": "random_forest", "verified": True,
        "dataset_manifest": {"training_scope": "delhi_station_operational", "synthetic": False, "feature_availability_verified": True},
        "metrics": {"test": {
            "random_forest": {"overall": {"mae": 1, "rmse": 2}},
            "persistence": {"overall": {"mae": 3, "rmse": 4}},
        }},
    }
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for filename, content in (
            ("manifest.json", json.dumps(manifest).encode()),
            ("model.joblib", b"tampered" if tamper else artifact),
        ):
            member = tarfile.TarInfo(f"{version}/{filename}")
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    payload = output.getvalue()
    writes = []
    s3 = SimpleNamespace(
        get_object=lambda **kw: {"ContentLength": len(payload), "Body": io.BytesIO(payload)},
        put_object=lambda **kw: writes.append(kw),
    )
    monkeypatch.setenv("ML_BUCKET", bucket)
    monkeypatch.setattr(workflow.boto3, "client", lambda service: SimpleNamespace(
        describe_training_job=lambda **kw: {
            "TrainingJobStatus": "Completed",
            "ModelArtifacts": {"S3ModelArtifacts": f"s3://{bucket}/models/training/{name}/output/model.tar.gz"},
        }))
    if tamper:
        with pytest.raises(ValueError, match="model_hash_mismatch"):
            workflow.publish(s3, name)
        assert not writes
    else:
        assert workflow.publish(s3, name)["promoted"] is True
        assert len(writes) == 2
        assert all(x["Key"].startswith(f"models/registry/{version}/") for x in writes)
        assert all(x["ServerSideEncryption"] == "AES256" for x in writes)
