"""Bind an already approved/enrolled certificate to an existing owned backend device."""
import argparse
import json
import os
import re
from urllib.parse import unquote

import boto3
from dotenv import load_dotenv

from ecoroute.wearable.repository import WearableRepository, owner_key
from ecoroute.wearable.policy import policy
from types import SimpleNamespace


def main():
    load_dotenv(override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--owner-sub", required=True)
    parser.add_argument("--certificate-id", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE"))
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--apply", action="store_true", help="Requires prior explicit approval; reads AWS and updates binding")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{32}", args.device_id) or not re.fullmatch(r"[a-f0-9]{64}", args.certificate_id):
        parser.error("Actual device and certificate identifiers required")
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "updated": False, "required": "Reviewed enrollment, scoped operator IAM, non-root credit account and explicit --apply approval"}))
        return
    expected = os.getenv("EXPECTED_AWS_ACCOUNT_ID")
    if not args.profile or not expected or args.region != "ap-south-1":
        parser.error("Explicit profile, expected account and Mumbai region required")
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != expected or identity["Arn"].endswith(":root"):
        parser.error("Expected non-root AWS identity required")
    iot = session.client("iot")
    cert = iot.describe_certificate(certificateId=args.certificate_id)["certificateDescription"]
    thing = "eco-" + args.device_id
    if cert["status"] != "ACTIVE" or cert["certificateArn"] not in iot.list_thing_principals(thingName=thing)["principals"]:
        parser.error("Active certificate must be attached to the exact thing")
    attributes = iot.describe_thing(thingName=thing).get("attributes", {})
    if attributes.get("owner_key") != owner_key(args.owner_sub):
        parser.error("Thing owner attribute must match backend owner")
    policies = iot.list_attached_policies(target=cert["certificateArn"], pageSize=250)
    if policies.get("nextMarker") or [p["policyName"] for p in policies["policies"]] != [thing]:
        parser.error("Exactly the reviewed device policy must be attached")
    document = iot.get_policy(policyName=thing)["policyDocument"]
    actual = json.loads(unquote(document)) if isinstance(document, str) else document
    if actual != policy(expected, args.region, owner_key(args.owner_sub), args.device_id):
        parser.error("Attached policy differs from exact reviewed device scope")
    repo = WearableRepository(SimpleNamespace(client=session.client("dynamodb")), args.table)
    record = repo.device(args.owner_sub, args.device_id)
    if record["deleting"]:
        parser.error("Deleted device cannot be bound")
    prior_epoch = record["epoch"]
    record.update(certificate_thumbprint=args.certificate_id, epoch=prior_epoch + 1)
    repo.store.client.put_item(TableName=args.table, Item=repo.device_item(record),
        ConditionExpression="epoch = :old AND deleting = :no",
        ExpressionAttributeValues={":old": {"N": str(prior_epoch)}, ":no": {"BOOL": False}})
    print(json.dumps({"device_id": args.device_id, "bound": True, "private_key_handled": False}))


if __name__ == "__main__":
    main()
