"""Offline exact-device enrollment policy plan; does not provision or create private keys."""
import argparse
import json
from pathlib import Path

from botocore.session import get_session
from botocore.validate import validate_parameters
from ecoroute.wearable.policy import policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--owner-key", required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--region", default="ap-south-1")
    args = parser.parse_args()
    document = policy(args.account, args.region, args.owner_key, args.device_id)
    client = get_session().get_service_model("iot")
    create = {"policyName": "eco-" + args.device_id, "policyDocument": json.dumps(document)}
    validate_parameters(create, client.operation_model("CreatePolicy").input_shape)
    path = Path("work/iot")
    path.mkdir(parents=True, exist_ok=True)
    (path / "device-policy.json").write_text(json.dumps(document, indent=2))
    (path / "create-policy.json").write_text(json.dumps(create, indent=2))
    print(json.dumps({"thing_name": "eco-" + args.device_id, "policy_file": str(path / "device-policy.json"), "provisioned": False}))


if __name__ == "__main__":
    main()
