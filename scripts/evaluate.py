"""Re-evaluate a trusted exported candidate, including candidates that failed promotion."""

import argparse
import json

from ecoroute.ml.inference import LocalRegistry
from ecoroute.ml.preprocessing import load_dataset
from ecoroute.ml.training import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--models", default="work/ml/models")
    parser.add_argument("--model-version", required=True)
    args = parser.parse_args()
    registry = LocalRegistry(args.models)
    manifest = next(m for m in registry.models() if m["model_version"] == args.model_version)
    parts, dataset = load_dataset(args.dataset)
    if manifest["dataset_version"] != dataset["dataset_version"]:
        raise ValueError("evaluation_dataset_version_mismatch")
    result = evaluate(parts, {manifest["algorithm"]: registry.load(manifest)})
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
