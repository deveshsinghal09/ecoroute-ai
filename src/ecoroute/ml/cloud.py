"""On-demand container Lambda and SageMaker batch inference share the verified registry."""

import json
import os

import boto3

from ecoroute.environment.pipeline import repository
from ecoroute.ml.inference import LocalRegistry, MLService, MLUnavailable, VERSION


class S3Registry(LocalRegistry):
    def __init__(self, bucket, *, s3=None, root="/tmp/ecoroute-models"):
        super().__init__(root)
        self.bucket, self.s3 = bucket, s3 or boto3.client("s3")

    def get(self, key, maximum):
        response = self.s3.get_object(Bucket=self.bucket, Key=key)
        if response["ContentLength"] > maximum:
            raise MLUnavailable("model_registry_object_too_large")
        return response["Body"].read()

    def models(self):
        response = self.s3.list_objects_v2(
            Bucket=self.bucket, Prefix="models/registry/", MaxKeys=200
        )
        if response.get("IsTruncated"):
            raise MLUnavailable("model_registry_requires_archive_cleanup")
        result = []
        for item in response.get("Contents", []):
            pieces = item["Key"].split("/")
            if len(pieces) == 4 and pieces[-1] == "manifest.json" and VERSION.fullmatch(pieces[-2]):
                manifest = json.loads(self.get(item["Key"], 1024 * 1024))
                if manifest["model_version"] != pieces[-2]:
                    raise MLUnavailable("model_registry_version_mismatch")
                result.append(manifest)
        return sorted(result, key=lambda m: m["trained_at"], reverse=True)

    def load(self, manifest):
        root = self.root / manifest["model_version"]
        root.mkdir(parents=True, exist_ok=True)
        content = self.get(
            "models/registry/" + manifest["model_version"] + "/model.joblib", 32 * 1024 * 1024
        )
        (root / "model.joblib").write_bytes(content)
        return super().load(manifest)


def _handle(event, context):
    # Invokable only by the API execution role; never a public Lambda function URL.
    try:
        engine = MLService(S3Registry(os.environ["ML_BUCKET"]), repository())
        operation = event.get("operation")
        if operation == "status":
            return engine.status()
        if operation == "models":
            return {
                "models": [
                    {
                        k: m[k]
                        for k in (
                            "model_version",
                            "algorithm",
                            "verified",
                            "trained_at",
                            "supported_stations",
                            "horizon_hours",
                        )
                    }
                    for m in engine.registry.models()
                ]
            }
        if operation == "metrics":
            m = engine.registry.select(event.get("model_version"))
            return {
                "model_version": m["model_version"],
                "metrics": m["metrics"],
                "limitations": m["limitations"],
            }
        from ecoroute.ml.api import BatchRequest, PredictionRequest

        if operation == "predict":
            data = PredictionRequest.model_validate(
                {k: v for k, v in event.items() if k != "operation"}
            )
            return engine.predict(**data.model_dump())
        if operation == "batch":
            data = BatchRequest.model_validate({k: v for k, v in event.items() if k != "operation"})
            return engine.batch(**data.model_dump())
        raise MLUnavailable("invalid_ml_operation")
    except MLUnavailable as exc:
        return {"error": str(exc)}
    except Exception:
        return {"error": "ml_worker_unavailable"}


def handler(event, context):
    import time

    started = time.monotonic()
    result = _handle(event, context)
    print(
        json.dumps(
            {
                "event": "ml_inference",
                "status": "unavailable" if result.get("error") else "completed",
                "latency_ms": round((time.monotonic() - started) * 1000),
            }
        )
    )
    return result
