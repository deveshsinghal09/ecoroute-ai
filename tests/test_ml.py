"""Synthetic data here is exclusively for mechanics; it is not a real training result."""

import copy
import json
import math
from datetime import UTC, datetime, timedelta

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template
from botocore.session import get_session
from botocore.validate import validate_parameters

from ecoroute.environment.repository import LocalRepository, pack
from ecoroute.environment.schema import make_record
from ecoroute.ml.api import ml_service
from ecoroute.ml.inference import LocalRegistry, MLService, MLUnavailable
from ecoroute.ml.preprocessing import (
    InsufficientData,
    feature_row,
    load_dataset,
    prepare,
    write_dataset,
)
from ecoroute.ml.route_index import StationPredictionIndex
from ecoroute.ml.sagemaker import job_spec
from ecoroute.ml.training import matrix, train
from ecoroute.routing.pollution import PollutionIndex
from infra.stacks import CoreStack, DataStack, MlStack


@pytest.fixture(scope="module")
def observed():
    start = datetime(2026, 8, 1, tzinfo=UTC)
    return [
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
            location_id="TEST_ONLY_STATION",
            sensor_id="TEST_ONLY_SENSOR",
            provenance={"synthetic_test_only": True},
        ).model_dump(mode="json")
        for i in range(360)
    ]


@pytest.fixture(scope="module")
def trained(observed, tmp_path_factory):
    root = tmp_path_factory.mktemp("ml")
    parts, manifest = prepare(observed)
    dataset = write_dataset(parts, manifest, root / "datasets")
    artifact, metadata = train(dataset, root / "models")
    return parts, dataset, artifact, metadata, root


def test_modeled_data_and_tiny_history_never_train(observed):
    modeled = copy.deepcopy(observed)
    for row in modeled:
        row.update(source="open_meteo", kind="modeled")
    with pytest.raises(InsufficientData) as denied:
        prepare(modeled)
    assert denied.value.report["measured_pm25_records"] == 0
    with pytest.raises(InsufficientData):
        prepare(observed[:48])


def test_late_backfills_do_not_claim_historical_feature_availability(observed):
    late = copy.deepcopy(observed)
    for row in late:
        row["collected_at"] = "2026-10-10T00:00:00Z"
    with pytest.raises(InsufficientData) as denied:
        prepare(late)
    assert denied.value.report["eligible_samples"] == 0


def test_feature_availability_and_future_poison_do_not_leak(observed):
    issued = datetime(2026, 8, 5, tzinfo=UTC)
    features = feature_row(observed, issued)
    poisoned = copy.deepcopy(observed)
    for row in poisoned:
        if datetime.fromisoformat(row["collected_at"]) > issued:
            row["value"] = 99999
    assert feature_row(poisoned, issued) == features
    future_weather = [
        {
            "available_at": (issued + timedelta(hours=1)).isoformat(),
            "reported_at": issued.isoformat(),
            "latitude": 28.6139,
            "longitude": 77.209,
            "temperature_c": 30,
        }
    ]
    assert feature_row(observed, issued, future_weather)["temperature_c"] is None
    assert features["pm25_lag1"] == pytest.approx(observed[95]["value"])


def test_chronological_purge_schema_and_serialize(trained):
    parts, dataset, artifact, metadata, root = trained
    for first, next_part in (("train", "validation"), ("validation", "test")):
        assert max(r["target_at"] for r in parts[first]) < min(
            r["issued_at"] for r in parts[next_part]
        )
    reloaded, manifest = load_dataset(dataset)
    assert reloaded == parts and manifest["split_counts"]["train"] >= 72
    registry = LocalRegistry(root / "models")
    prediction = registry.load(metadata).predict(matrix(parts["test"][:2]))
    assert len(prediction) == 2 and all(math.isfinite(v) for v in prediction)
    assert metadata["prediction_interval"] is None
    assert metadata["metrics"]["test"]["persistence"]["overall"]["sample_count"] == len(
        parts["test"]
    )
    assert metadata["metrics"]["test"]["provider_forecast"]["paired_cohort"] is None
    assert (artifact / "model.joblib").is_file()


def test_tampering_and_invalid_model_paths_refused(trained, tmp_path):
    _, _, artifact, metadata, _ = trained
    import shutil

    destination = tmp_path / artifact.name
    shutil.copytree(artifact, destination)
    (destination / "model.joblib").write_bytes(b"tampered")
    registry = LocalRegistry(tmp_path)
    with pytest.raises(MLUnavailable, match="untrusted_model"):
        registry.load(metadata)
    with pytest.raises(MLUnavailable, match="invalid_model_version"):
        registry.select("../../private")
    with pytest.raises(MLUnavailable, match="no_verified"):
        LocalRegistry(tmp_path / "absent").select()


def test_live_prediction_requires_known_station_and_fresh_observations(trained, observed, tmp_path):
    _, _, _, metadata, root = trained
    # This dataset is synthetic and exists only inside test temp paths.
    assert metadata["verified"], "Synthetic sinusoid fixture should exercise the promotion path"
    issued = datetime(2026, 8, 15, 23, 10, tzinfo=UTC)
    repo = LocalRepository(tmp_path)
    eligible = [
        r
        for r in observed
        if datetime.fromisoformat(r["reported_at"]) >= issued - timedelta(hours=48)
    ]
    key = "curated/source=openaq/date=2026-08-15/test.parquet"
    repo.put_bytes(key, pack(eligible), "application/vnd.apache.parquet")
    repo.put("FILES#openaq", "2026-08-15#fixture", {"key": key})
    engine = MLService(LocalRegistry(root / "models"), repo, clock=lambda: issued)
    station = metadata["supported_stations"][0]
    result = engine.predict(station)
    assert result["horizon_hours"] == 1 and result["forecast_type"] == "station_prediction"
    assert result["model_version"] == metadata["model_version"]
    assert result["valid_at"] == (issued + timedelta(hours=1)).isoformat()
    with pytest.raises(MLUnavailable, match="not_verified"):
        engine.predict("other-station")
    with pytest.raises(MLUnavailable, match="issuance"):
        engine.predict(station, issued_at=issued + timedelta(hours=2))
    empty = MLService(engine.registry, LocalRepository(tmp_path / "empty"), clock=lambda: issued)
    assert empty.batch([station])["results"][0]["status"] == "unavailable"


def test_ml_api_auth_and_unavailable_state(secured, tmp_path):
    secured.app.dependency_overrides[ml_service] = lambda: MLService(
        LocalRegistry(tmp_path), LocalRepository(tmp_path / "data")
    )
    for route in ("status", "models", "metrics"):
        assert secured.client.get("/api/v1/ml/" + route).status_code == 401
    for route in ("predict", "batch-predict"):
        assert secured.client.post("/api/v1/ml/" + route, json={}).status_code == 401
    assert secured.client.post("/api/v1/routes/predict-departure-times", json={}).status_code == 401
    headers = {"Authorization": "Bearer " + secured.token()}
    assert (
        secured.client.get("/api/v1/ml/status", headers=headers).json()["status"] == "unavailable"
    )
    assert secured.client.get("/api/v1/ml/models", headers=headers).json() == {"models": []}
    assert (
        secured.client.post(
            "/api/v1/ml/predict", json={"station_id": "a"}, headers=headers
        ).status_code
        == 503
    )
    assert (
        secured.client.post(
            "/api/v1/ml/batch-predict", json={"station_ids": ["a"] * 21}, headers=headers
        ).status_code
        == 422
    )
    assert (
        secured.client.post(
            "/api/v1/ml/predict",
            json={"station_id": "a"},
            headers={"Authorization": "Bearer " + secured.token(scope="ecoroute/read")},
        ).status_code
        == 403
    )


def test_station_route_join_time_space_and_provenance():
    issued = datetime(2026, 10, 10, tzinfo=UTC)
    base = PollutionIndex([], as_of=issued)
    prediction = {
        "latitude": 28.6139,
        "longitude": 77.209,
        "station_id": "test-only",
        "value_ug_m3": 30,
        "model_version": "a" * 24,
        "issued_at": issued.isoformat(),
        "valid_at": (issued + timedelta(hours=1)).isoformat(),
        "confidence": "test-only",
    }
    index = StationPredictionIndex(base, [prediction])
    result = index.sample([77.209, 28.6139], issued + timedelta(hours=1))
    assert result["status"] == "station_prediction" and result["model_version"] == "a" * 24
    assert index.sample([77.5, 28.8], issued + timedelta(hours=1))["status"] == "unavailable"
    assert index.sample([77.209, 28.6139], issued + timedelta(hours=3))["status"] == "unavailable"
    assert (
        index.sample([77.209, 28.6139], issued + timedelta(hours=1), "no2")["status"]
        == "unavailable"
    )


def test_real_sagemaker_spec_schema_limits_and_digest():
    image = "123456789012.dkr.ecr.ap-south-1.amazonaws.com/ecoroute-ml@sha256:" + "a" * 64
    spec = job_spec(
        name="ecoroute-test",
        bucket="ecoroute-test",
        dataset_version="a" * 24,
        role_arn="arn:aws:iam::123456789012:role/EcoRouteTraining",
        image_uri=image,
    )
    validate_parameters(
        spec,
        get_session()
        .get_service_model("sagemaker")
        .operation_model("CreateTrainingJob")
        .input_shape,
    )
    assert spec["ResourceConfig"]["InstanceCount"] == 1
    assert spec["StoppingCondition"]["MaxRuntimeInSeconds"] == 900
    assert spec["EnableNetworkIsolation"] is True
    with pytest.raises(ValueError, match="digest"):
        job_spec(
            name="ecoroute-test",
            bucket="ecoroute-test",
            dataset_version="a" * 24,
            role_arn="arn:aws:iam::123456789012:role/EcoRouteTraining",
            image_uri=image.split("@")[0] + ":latest",
        )


def test_optional_ml_workflow_has_no_endpoint_no_enabled_schedule_and_scoped_roles(tmp_path):
    asset = tmp_path / "asset"
    asset.mkdir()
    (asset / "handler.py").write_text("# structural fixture only")
    app = cdk.App(outdir=str(tmp_path / "assembly"))
    env = cdk.Environment(account="123456789012", region="ap-south-1")
    data = DataStack(app, "Data", env=env)
    ml = MlStack(
        app,
        "ML",
        env=env,
        data=data,
        asset_path=str(asset),
        image_uri="123456789012.dkr.ecr.ap-south-1.amazonaws.com/ecoroute-ml@sha256:" + "a" * 64,
    )
    core = CoreStack(
        app, "Core", env=env, data=data, asset_path=str(asset), ml_inference_arn=ml.inference_arn
    )
    assembly = app.synth()
    assert len(assembly.stacks) == 3
    resources = Template.from_stack(ml).to_json()["Resources"].values()
    assert not any(
        r["Type"]
        in {"AWS::SageMaker::Endpoint", "AWS::SageMaker::TrainingJob", "AWS::EC2::NatGateway"}
        for r in resources
    )
    schedule = next(r for r in resources if r["Type"] == "AWS::Scheduler::Schedule")
    assert schedule["Properties"]["State"] == "DISABLED"
    machine = next(r for r in resources if r["Type"] == "AWS::StepFunctions::StateMachine")
    definition = json.dumps(machine)
    assert "createTrainingJob.sync" in definition and "VerifyAndPublish" in definition
    assert "Retry" not in definition
    policies = [r for r in resources if r["Type"] == "AWS::IAM::Policy"]
    for policy in policies:
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
            actions = statement["Action"]
            assert "sagemaker:*" not in json.dumps(actions)
            if statement["Resource"] == "*":
                assert actions == "ecr:GetAuthorizationToken" and statement.get("Condition")
    assert "ML_INFERENCE_FUNCTION_ARN" in json.dumps(Template.from_stack(core).to_json())
