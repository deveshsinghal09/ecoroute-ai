"""Offline structural checks, not a penetration test or live IAM proof."""
import json
from collections import Counter
from pathlib import Path

ALLOWED_ACCOUNT_READS = {"dynamodb:ListStreams", "sns:GetSMSSandboxAccountStatus", "sns:ListSMSSandboxPhoneNumbers", "sns:GetSMSAttributes"}


def review(template):
    issues, exceptions = [], []
    resources = template.get("Resources", {})
    for identifier, resource in resources.items():
        kind, props = resource["Type"], resource.get("Properties", {})
        if kind in {"AWS::EC2::NatGateway", "AWS::ECS::Service", "AWS::SageMaker::Endpoint"}:
            issues.append(identifier + ": idle paid infrastructure")
        if kind == "AWS::Scheduler::Schedule" and props.get("State") != "DISABLED":
            issues.append(identifier + ": schedule enabled")
        if kind == "AWS::S3::Bucket" and not all(props.get("PublicAccessBlockConfiguration", {}).get(flag) for flag in ("BlockPublicAcls", "BlockPublicPolicy", "IgnorePublicAcls", "RestrictPublicBuckets")):
            issues.append(identifier + ": public bucket guard missing")
        if kind == "AWS::IAM::Policy":
            for statement in props["PolicyDocument"]["Statement"]:
                if statement.get("Effect") != "Allow":
                    continue
                actions = statement["Action"]
                actions = [actions] if isinstance(actions, str) else actions
                if any(action in {"*", "*:*"} or action.endswith(":*") for action in actions):
                    issues.append(identifier + ": service-wide IAM action")
                if statement.get("Resource") == "*":
                    if set(actions) == {"ecr:GetAuthorizationToken"} and statement.get("Condition") == {
                            "StringEquals": {"aws:RequestedRegion": "ap-south-1"}}:
                        exceptions.append({"policy": identifier, "actions": actions,
                            "reason": "ECR registry authentication has no resource-level ARN; Mumbai only; image pulls separately restricted to project repository"})
                    elif set(actions) <= ALLOWED_ACCOUNT_READS and statement.get("Condition"):
                        exceptions.append({"policy": identifier, "actions": actions, "reason": "account-level read API; regional condition"})
                    else:
                        issues.append(identifier + ": unreviewed wildcard resource")
    return {"issues": issues, "documented_exceptions": exceptions, "counts": dict(Counter(r["Type"] for r in resources.values()))}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    assembly = root / "cdk.out"
    manifest = json.loads((assembly / "manifest.json").read_text(encoding="utf-8")) if (assembly / "manifest.json").exists() else {}
    files = [assembly / artifact["properties"]["templateFile"] for artifact in manifest.get("artifacts", {}).values() if artifact["type"] == "aws:cloudformation:stack"]
    if not files:
        raise SystemExit("Run offline CDK synth first")
    reports = {p.stem: review(json.loads(p.read_text(encoding="utf-8"))) for p in files}
    (root / "work").mkdir(exist_ok=True)
    (root / "work/phase7-infra-review.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps({"structural_review": "pass" if not any(r["issues"] for r in reports.values()) else "fail", "templates": list(reports), "issues": [i for r in reports.values() for i in r["issues"]], "live_IAM_verified": False}))
    raise SystemExit(int(any(r["issues"] for r in reports.values())))
