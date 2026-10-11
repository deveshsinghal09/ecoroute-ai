"""Default offline plans. Explicit, identity-checked deployment or retaining teardown only."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from infra.profiles import DeploymentOptions  # noqa: E402
STACKS = ["EcoRouteCore", "EcoRouteML", "EcoRouteData"]
CONTEXT_KEYS = {"callback_urls", "frontend_origins", "ml_image_uri", "gemini_secret_arn",
                "gemini_model_id", "google_routes_secret_arn", "cycling_secret_arn",
                "provider_secret_arn", "enable_guest_routes", "ingestion_interval_minutes"}


def load_context(path):
    values = json.loads(Path(path).read_text(encoding="utf-8")) if path else {}
    if not isinstance(values, dict) or set(values) - CONTEXT_KEYS:
        raise ValueError("Context file accepts only reviewed non-secret identifiers and settings")
    for key, value in values.items():
        if key.endswith("_secret_arn") and (not isinstance(value, str) or
                not value.startswith("arn:aws:secretsmanager:") or "*" in value):
            raise ValueError("Context secrets must be complete ARNs, never secret values")
        if key in {"callback_urls", "frontend_origins"} and (
                not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value)):
            raise ValueError("Callback/CORS context requires a nonempty list of exact URLs")
    return values


def guard_identity(identity, expected):
    if not expected or identity.get("Account") != expected or identity.get("Arn", "").endswith(":root"):
        raise ValueError("expected_nonroot_account_required")


def command(action, profile, *, iot=False, location=False, workflows=False, context=None, optional_stacks=()):
    node = shutil.which("node")
    cli = ROOT / "node_modules/aws-cdk/bin/cdk"
    if not node or not cli.exists():
        raise ValueError("Node_or_pinned_local_CDK_missing_run_npm_ci")
    flags = ["-c", "enable_iot=true"] if iot else []
    if location:
        flags += ["-c", "enable_location=true"]
    if workflows:
        flags += ["-c", "enable_workflows=true"]
    for key, value in (context or {}).items():
        flags += ["-c", key + "=" + (value if isinstance(value, str) else json.dumps(value))]
    if action == "deploy":
        return [node, str(cli), "deploy", "--all", "--profile", profile, "--require-approval", "broadening", "--outputs-file", "work/deployed-outputs.json", *flags]
    return [node, str(cli), "destroy", "--force", "--profile", profile, *optional_stacks, *( (["EcoRouteIoT"] if iot else []) + STACKS), *flags]


def main(argv=None):
    configuration = {**dotenv_values(ROOT / ".env"), **os.environ}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "deploy", "teardown"])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--accept-estimated-charges", action="store_true")
    parser.add_argument("--confirm-retaining-teardown", action="store_true")
    parser.add_argument("--profile", default=configuration.get("AWS_PROFILE"))
    parser.add_argument("--region", default=configuration.get("AWS_REGION") or "ap-south-1")
    parser.add_argument("--expected-account-id", default=configuration.get("EXPECTED_AWS_ACCOUNT_ID"))
    parser.add_argument("--iot", action="store_true")
    parser.add_argument("--location", action="store_true")
    parser.add_argument("--workflows", action="store_true")
    parser.add_argument("--context-file", help="Local JSON with reviewed non-secret CDK context only")
    parser.add_argument("--deployment-config", default=configuration.get("ECOROUTE_DEPLOY_CONFIG"))
    args = parser.parse_args(argv)
    options = DeploymentOptions.load(args.deployment_config)
    context = load_context(args.context_file)
    optional_stacks = (["EcoRouteHosting"] if options.hosting != "none" else []) + (["EcoRouteCompute"] if options.runtime != "lambda" else []) + (["EcoRouteAnalytics"] if options.analytics != "none" else [])
    missing = [name for name, value in (("AWS_PROFILE", args.profile), ("AWS_REGION", args.region), ("EXPECTED_AWS_ACCOUNT_ID", args.expected_account_id)) if not value]
    plan = {"action": args.action, "apply": args.apply, "stacks": optional_stacks + (["EcoRouteIoT"] if args.iot else []) + STACKS,
        "deployment_options": options.plan(),
        "context_names": sorted(context), "workflows_defined": args.workflows,
        "missing_names": missing, "aws_resources_currently_verified": False,
        "unverified_prerequisites": ["CDK_BOOTSTRAP", "DEPLOY_IAM_PERMISSIONS", "SERVICE_QUOTAS", "COGNITO_CALLBACK_URLS", "CREDIT_ELIGIBILITY"],
        "estimated_small_demo_monthly_usd": "Default serverless: 5-20 planning range. Paid profiles cost EXTRA; review MULTISERVICE_INTEGRATION.md before approval.",
        "warning": "Teardown removes these stacks but RETAINS protected DynamoDB/S3/Cognito and bootstrap assets. Retained resources may incur charges. No permanent data purge is performed."}
    print(json.dumps(plan, indent=2))
    if not args.apply or args.action == "plan":
        return 0
    if missing:
        parser.error("Missing names shown above. Configure CLI temporary IAM/SSO profile and ignored .env; never paste keys in chat.")
    if args.action == "deploy" and not args.accept_estimated_charges:
        parser.error("Review DEMO_READINESS.md cost proposal and obtain deployment approval before --accept-estimated-charges")
    if args.action == "teardown" and not args.confirm_retaining_teardown:
        parser.error("Retaining teardown requires --confirm-retaining-teardown; not a zero-cost/full data purge")
    cmd = command(args.action, args.profile, iot=args.iot, location=args.location,
                  workflows=args.workflows, context=context, optional_stacks=optional_stacks)
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    config = Config(connect_timeout=2, read_timeout=5, retries={"total_max_attempts": 1})
    guard_identity(session.client("sts", config=config).get_caller_identity(), args.expected_account_id)
    cloudformation = session.client("cloudformation", config=config)
    if args.action == "deploy":
        cloudformation.describe_stacks(StackName="CDKToolkit")
        if not (ROOT / "build/lambda/ecoroute/handlers/api.py").exists():
            parser.error("Build Linux Lambda asset before deployment")
    else:
        inventory = []
        for stack in plan["stacks"]:
            paginator = cloudformation.get_paginator("list_stack_resources")
            for page in paginator.paginate(StackName=stack):
                inventory.extend({"stack": stack, "type": r["ResourceType"], "logical_id": r["LogicalResourceId"], "physical_id": r.get("PhysicalResourceId")} for r in page["StackResourceSummaries"])
        (ROOT / "work").mkdir(exist_ok=True)
        (ROOT / "work/teardown-resource-inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
        # Stop/disable any active schedules, executions, training jobs and broker access first;
        # this wrapper intentionally does not guess which user jobs should be interrupted.
    environment = {**os.environ, "AWS_PROFILE": args.profile, "AWS_REGION": args.region,
        "AWS_DEFAULT_REGION": args.region, "ECOROUTE_DEPLOY_REGION": args.region,
        "EXPECTED_AWS_ACCOUNT_ID": args.expected_account_id}
    if args.deployment_config:
        environment["ECOROUTE_DEPLOY_CONFIG"] = str(Path(args.deployment_config).resolve())
    subprocess.run(cmd, cwd=ROOT, env=environment, check=True)
    print("Cloud command completed; verify actual resources/outputs and retained-resource inventory separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
