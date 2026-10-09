"""Exact publish-only device policies. No health-data subscribe permissions."""
import re


def policy(account, region, owner, device):
    if not re.fullmatch(r"[0-9]{12}", account) or not re.fullmatch(r"[a-f0-9]{64}", owner) or not re.fullmatch(r"[a-f0-9]{32}", device):
        raise ValueError("validated_account_owner_hash_device_required")
    if region != "ap-south-1":
        raise ValueError("This reviewed plan targets Mumbai")
    prefix = f"arn:aws:iot:{region}:{account}:"
    return {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": "iot:Connect", "Resource": prefix + "client/eco-" + device,
         "Condition": {"Bool": {"iot:Connection.Thing.IsAttached": "true"}}},
        {"Effect": "Allow", "Action": "iot:Publish", "Resource": prefix + f"topic/ecoroute/users/{owner}/devices/{device}/measurements"},
    ]}
