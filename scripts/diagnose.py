"""Read-only first-run checks. Default is offline; --aws enables control-plane reads.

Never prints CLI stderr, tokens, identity ARNs, account IDs, or environment values.
No route/model calls, provisioning, bootstrap, or paid data queries.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CHECKS = []
SERVICES = {
    "geo-routes": "location", "lambda": "lambda", "apigatewayv2": "apigateway",
    "s3": "s3", "dynamodb": "dynamodb", "scheduler": "scheduler", "sqs": "sqs",
    "cognito-idp": "cognito-idp", "logs": "logs", "secretsmanager": "secretsmanager",
    "sns": "sns", "stepfunctions": "states", "sagemaker": "sagemaker",
    "bedrock": "bedrock", "iot": "iot", "ecs": "ecs", "ecr": "ecr", "rds": "rds",
}


def record(name, status, detail):
    CHECKS.append({"check": name, "status": status, "detail": detail})
    print(f"{status:7} {name}: {detail}")


def run(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=25, check=False)
        if result.returncode:
            match = re.search(r"\(([A-Za-z0-9]+)\)", result.stderr)
            return False, match.group(1) if match else "command_failed"
        return True, result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False, "unavailable_or_timeout"


def present(name):
    value = os.environ.get(name, "").strip()
    return bool(value) and not value.startswith(("<", "YOUR_", "REPLACE_"))


def enabled(name):
    return os.environ.get(name, "").lower() in {"true", "1", "yes"}


def evaluate_identity(identity, expected, allow_root_read_only=False):
    if identity.get("Arn", "").endswith(":root") and not allow_root_read_only:
        return "FAIL", "Root identity is forbidden for development"
    if not expected:
        return "FAIL", "Set EXPECTED_AWS_ACCOUNT_ID locally before account reads"
    if identity.get("Account") != expected:
        return "FAIL", "Account mismatch; further AWS reads stopped"
    return "PASS", "Temporary/profile identity matches expected account (identifier redacted)"


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
    except ImportError:
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aws", action="store_true")
    parser.add_argument("--allow-root-read-only", action="store_true",
                        help="Explicit exception for this script's read-only checks; not deployment approval")
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    parser.add_argument("--region", default=(os.environ.get("AWS_REGION") or "ap-south-1"))
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    record("Python", "PASS" if (3, 11) <= sys.version_info[:2] < (3, 14) else "FAIL",
           sys.version.split()[0] + "; scaffold supported range 3.11-3.13")
    for tool, parameters, required in [
        ("docker", ["--version"], False), ("aws", ["--version"], True),
        ("node", ["--version"], True), ("git", ["--version"], True),
    ]:
        executable = shutil.which(tool)
        ok, output = run([executable, *parameters]) if executable else (False, "not installed")
        if ok and tool == "node" and int(output.lstrip("v").split(".")[0]) < 22:
            ok, output = False, "Node 22+ required for CDK"
        record(tool, "PASS" if ok else ("FAIL" if required else "WARN"), output)
    if shutil.which("docker"):
        ok, _ = run(["docker", "info", "--format", "{{.ServerVersion}}"])
        record("Docker engine", "PASS" if ok else "WARN",
               "reachable" if ok else "stopped/unreachable; optional for local Python checks")
    cdk = Path("node_modules/.bin/cdk.cmd" if os.name == "nt" else "node_modules/.bin/cdk")
    record("CDK CLI", "PASS" if cdk.exists() else "WARN",
           "local CLI installed" if cdk.exists() else "run npm ci; global install unnecessary")
    for flag, key in [("ENABLE_OPENAQ", "OPENAQ_API_KEY"),
                      ("ENABLE_WEATHER", "WEATHER_API_KEY"),
                      ("ENABLE_WEARABLE", "WEARABLE_CLIENT_SECRET")]:
        record(key, "PASS" if present(key) else ("FAIL" if enabled(flag) else "SKIP"),
               "present (not validated)" if present(key) else "absent; needed only for selected adapter")
    record("OPEN_METEO_API_KEY", "PASS" if present("OPEN_METEO_API_KEY") else "SKIP",
           "present (not validated)" if present("OPEN_METEO_API_KEY") else "optional commercial key absent; eligible free service needs none")
    for key in ("COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID"):
        record(key, "PASS" if present(key) else "WARN",
               "configured (not validated)" if present(key) else "missing; protected live login unavailable")
    record("Region expectation", "PASS" if args.region == (os.environ.get("EXPECTED_AWS_REGION") or "ap-south-1") else "FAIL", "selected=" + args.region)
    try:
        budget = float(os.environ.get("MONTHLY_BUDGET_USD", ""))
        budget_ok = budget > 0 and budget < float("inf")
    except ValueError:
        budget_ok = False
    record("Budget expectation", "PASS" if budget_ok else "WARN",
           "positive USD threshold configured; not a hard cap" if budget_ok
           else "monthly USD alert threshold missing/invalid; credits do not cap spend")
    try:
        import boto3
        from botocore.session import Session
        sdk = Session()
        for service in SERVICES:
            model = sdk.get_service_model(service)
            regions = boto3.Session().get_available_regions(service)
            record("SDK " + service, "PASS" if args.region in regions else "WARN",
                   "region in SDK endpoint metadata; account access unverified"
                   if args.region in regions else "endpoint metadata inconclusive; check official region docs")
            if service == "geo-routes":
                record("Routes V2 API", "PASS" if "CalculateRoutes" in model.operation_names
                       else "FAIL", "SDK model checked; no billed route request sent")
    except ImportError:
        record("SDK models", "WARN", "install project dependencies to validate service models")
    if args.aws:
        aws_checks(args, budget_ok)
    else:
        record("AWS live checks", "SKIP", "use --aws --profile NAME after SSO setup; offline run")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(CHECKS, indent=2) + "\n", encoding="utf-8")
    return int(any(check["status"] == "FAIL" for check in CHECKS))


def aws_checks(args, budget_ok):
    if not shutil.which("aws") or not args.profile:
        record("AWS identity", "FAIL", "AWS CLI and an explicit named profile required")
        return
    configured, profile_region = run(["aws", "configure", "get", "region", "--profile", args.profile])
    record("CLI profile region", "PASS" if configured and profile_region == args.region else "WARN",
           "matches selected region" if configured and profile_region == args.region
           else "profile default missing/different; explicit --region used for checks")
    if any(present(name) for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")):
        record("Credential source", "WARN", "credential environment variables present; verify profile precedence")
    base = ["aws", "--profile", args.profile, "--region", args.region,
            "--output", "json", "--no-cli-pager", "--cli-connect-timeout", "5",
            "--cli-read-timeout", "10"]
    ok, value = run([*base, "sts", "get-caller-identity"])
    if not ok:
        record("AWS identity", "FAIL", value + "; configure/login to temporary profile locally")
        return
    status, detail = evaluate_identity(json.loads(value), os.environ.get("EXPECTED_AWS_ACCOUNT_ID"),
                                       args.allow_root_read_only)
    record("AWS identity", status, detail)
    if status != "PASS":
        return
    if json.loads(value).get("Arn", "").endswith(":root"):
        record("Root session", "WARN", "explicit read-only exception; use scoped roles for workloads")
    if args.region != (os.environ.get("EXPECTED_AWS_REGION") or "ap-south-1"):
        record("AWS region gate", "FAIL", "region mismatch; further account reads stopped")
        return
    account = json.loads(value)["Account"]
    ok, value = run([*base, "ec2", "describe-regions", "--all-regions",
                     "--region-names", args.region])
    region_enabled = ok and any(r["OptInStatus"] in ("opt-in-not-required", "opted-in")
                               for r in json.loads(value).get("Regions", []))
    record("Account region access", "PASS" if region_enabled else "WARN",
           "enabled" if region_enabled else "unverified/disabled; check ec2:DescribeRegions")
    ok, value = run([*base, "lambda", "get-account-settings"])
    record("Lambda account service access", "PASS" if ok else "WARN",
           "account settings readable; review concurrency before reserving six slots" if ok
           else value + "; resolve service entitlement/permission before deployment")
    qualifier = os.environ.get("CDK_BOOTSTRAP_QUALIFIER") or "hnb659fds"
    stack = os.environ.get("CDK_TOOLKIT_STACK_NAME") or "CDKToolkit"
    ok, value = run([*base, "cloudformation", "describe-stacks", "--stack-name", stack])
    healthy = ok and json.loads(value)["Stacks"][0]["StackStatus"] in {
        "CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"}
    record("CDK bootstrap stack", "PASS" if healthy else "WARN",
           "stack healthy; deployment permissions still unverified" if healthy
           else "missing, unhealthy or inaccessible (not bootstrapped by this script)")
    ok, _ = run([*base, "ssm", "get-parameter", "--name", f"/cdk-bootstrap/{qualifier}/version"])
    record("CDK bootstrap version", "PASS" if ok else "WARN",
           "version parameter readable; compare required version before deployment" if ok
           else "unverified; missing parameter or permission")
    for service in ("lambda", "apigateway", "geo", "dynamodb", "sagemaker"):
        ok, value = run([*base, "service-quotas", "list-service-quotas", "--service-code", service])
        count = len(json.loads(value).get("Quotas", [])) if ok else 0
        record("Account quotas " + service, "PASS" if count else "WARN",
               f"{count} quota entries readable; not proof of sufficient capacity" if count
               else "unverified/not listed; inspect Service Quotas console")
    budget_name = os.environ.get("BUDGET_NAME")
    if budget_name:
        ok, value = run([*base, "budgets", "describe-budget", "--account-id", account,
                         "--budget-name", budget_name])
        if ok:
            actual = json.loads(value)["Budget"]["BudgetLimit"]
            matches = budget_ok and actual["Unit"] == "USD" and float(actual["Amount"]) == float(
                os.environ["MONTHLY_BUDGET_USD"])
            record("AWS Budget", "PASS" if matches else "FAIL",
                   "amount matches; verify notification subscribers in Console" if matches
                   else "budget currency/amount mismatch")
        else:
            record("AWS Budget", "WARN", "missing/inaccessible; proposal only until created")
    else:
        record("AWS Budget", "WARN", "BUDGET_NAME missing; no budget verified")
    record("Deployment readiness", "WARN",
           "No deployment approved. SCPs, resource permissions, provider coverage and costs need review")


if __name__ == "__main__":
    raise SystemExit(main())
