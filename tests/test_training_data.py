"""Small generated cases verify mechanics, never substitute for measured-data evidence."""

import copy
import io
import json
import zipfile
from pathlib import Path
from datetime import UTC, datetime, timedelta

import pytest

from ecoroute.ml.benchmark_data import prepare_experiment, read_uci, synthetic_series
from ecoroute.ml.inference import LocalRegistry, MLService, MLUnavailable
from ecoroute.ml.policy import operational_dataset
from ecoroute.ml.preprocessing import load_dataset, write_dataset
from ecoroute.ml.training import train
from ecoroute.ml import workflow


def archive(csv):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as handle:
        handle.writestr("PRSA_Data_Aotizhongxin_20130301-20170228.csv", csv)
    return stream.getvalue()


def test_source_schema_units_timezone_missing_and_negative():
    content = "year,month,day,hour,PM2.5,TEMP,WSPM,wd,station\n"
    content += "2013,3,1,0,76,12,2,N,Aotizhongxin\n"
    content += "2013,3,1,1,NA,12,2,NA,Aotizhongxin\n"
    content += "2013,3,1,2,-10,12,2,NA,Aotizhongxin\n"
    groups, report = read_uci(archive(content))
    values = groups["uci_beijing:Aotizhongxin"]
    assert values[datetime(2013, 2, 28, 16, tzinfo=UTC)]["value"] == 76
    assert report == {"input_records": 3, "missing_or_invalid_pm25": 2}
    assert [v["value"] for v in values.values()] == [76, None, None]
    with pytest.raises(ValueError, match="schema_changed"):
        read_uci(archive("year,PM2.5\n2013,42\n"))
    with pytest.raises(ValueError, match="duplicate_station_timestamp"):
        read_uci(archive(content + "2013,3,1,0,76,12,2,N,Aotizhongxin\n"))


def experiment(records=1440):
    groups, audit = synthetic_series(records=records, stations=2)
    return groups, prepare_experiment(
        groups, audit, source="test", source_sha256="a" * 64, synthetic=True
    )


def test_determinism_lags_and_no_future_feature_leakage():
    groups, (parts, manifest) = experiment()
    repeat = synthetic_series(records=1440, stations=2)[0]
    assert groups == repeat and not operational_dataset(manifest)
    row = parts["train"][50]
    issued = datetime.fromisoformat(row["issued_at"])
    history = groups[row["station_id"]]
    assert row["pm25_lag24"] == history[issued - timedelta(hours=24)]["value"]
    poison = copy.deepcopy(groups)
    for stamp in poison[row["station_id"]]:
        if stamp > issued:
            poison[row["station_id"]][stamp].update(value=99999, temperature_c=-70)
    updated, _ = prepare_experiment(
        poison, {}, source="test", source_sha256="b" * 64, synthetic=True
    )
    match = next(
        r
        for r in updated["train"]
        if r["station_id"] == row["station_id"] and r["issued_at"] == row["issued_at"]
    )
    from ecoroute.ml.preprocessing import FEATURES

    assert {k: match[k] for k in FEATURES} == {k: row[k] for k in FEATURES}


def test_experimental_serialization_metrics_and_registry_promotion_block(tmp_path):
    _, (parts, manifest) = experiment()
    dataset = write_dataset(parts, manifest, tmp_path / "datasets")
    reloaded, _ = load_dataset(dataset)
    assert reloaded == parts
    artifact, metadata = train(dataset, tmp_path / "models")
    assert metadata["verified"] is False and metadata["supported_stations"] == []
    registry = LocalRegistry(tmp_path / "models")
    assert MLService(registry, None).status()["status"] == "unavailable"
    # A forged boolean is insufficient: independent provenance gate still rejects selection.
    metadata["verified"] = True
    (artifact / "manifest.json").write_text(json.dumps(metadata))
    with pytest.raises(MLUnavailable, match="no_verified"):
        registry.select()


def test_operational_workflow_rejects_experiment_before_paid_job(monkeypatch):
    from types import SimpleNamespace

    _, (_, manifest) = experiment()
    body = json.dumps(manifest).encode()
    s3 = SimpleNamespace(
        get_object=lambda **kw: {"ContentLength": len(body), "Body": io.BytesIO(body)}
    )
    monkeypatch.setenv("ML_BUCKET", "ecoroute-test")
    with pytest.raises(ValueError, match="measured_dataset_not_ready"):
        workflow.validate(
            s3, {"dataset_version": manifest["dataset_version"], "job_name": "ecoroute-test"}
        )


def test_synthetic_bounds_and_separate_dataset_identity():
    with pytest.raises(ValueError):
        synthetic_series(records=1_000_001)
    groups, (parts, a) = experiment()
    _, b = prepare_experiment(groups, {}, source="uci", source_sha256="a" * 64)
    assert a["dataset_version"] != b["dataset_version"]
    assert b["synthetic"] is False and b["feature_availability_verified"] is False
    assert not operational_dataset(b)
    for first, second in (("train", "validation"), ("validation", "test")):
        assert max(r["target_at"] for r in parts[first]) < min(
            r["issued_at"] for r in parts[second]
        )


def test_training_permission_proposals_exclude_idle_endpoints_and_bound_compute():
    for filename in (
        "iam-sagemaker-training-operator.json",
        "iam-sagemaker-workflow-boundary-additions.json",
    ):
        policy = json.loads((Path("config") / filename).read_text(encoding="utf-8"))
        launch = next(
            s for s in policy["Statement"] if s["Action"] == "sagemaker:CreateTrainingJob"
        )
        assert launch["Resource"].endswith("training-job/ecoroute-*")
        assert launch["Condition"]["NumericLessThanEquals"]["sagemaker:MaxRuntimeInSeconds"] == 900
        assert launch["Condition"]["ForAllValues:StringEquals"]["sagemaker:InstanceTypes"] == [
            "ml.m5.large"
        ]
        for statement in policy["Statement"]:
            actions = statement["Action"]
            actions = [actions] if isinstance(actions, str) else actions
            assert not any(
                a
                in {
                    "*",
                    "sagemaker:*",
                    "sagemaker:CreateEndpoint",
                    "sagemaker:CreateHyperParameterTuningJob",
                }
                for a in actions
            )
