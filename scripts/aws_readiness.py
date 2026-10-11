"""Bounded, read-only AWS service/permission assessment. Never creates resources or reads secrets."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Config(connect_timeout=3, read_timeout=8, retries={"total_max_attempts": 1})


def check(name, operation, select):
    try:
        return {"check": name, "status": "verified_read", "result": select(operation())}
    except ClientError as error:
        code = error.response["Error"]["Code"]
        # Messages can contain account identities, destinations or user data. Keep only codes.
        return {"check": name, "status": "unverified", "error_code": code}
    except BotoCoreError:
        return {"check": name, "status": "unverified", "error_code": "sdk_or_network_error"}


def quota_summary(value):
    return [{"name": q["QuotaName"], "code": q["QuotaCode"], "value": q["Value"],
             "adjustable": q.get("Adjustable", False)} for q in value.get("Quotas", [])
            if "ml.m5.large" in q["QuotaName"] and "training" in q["QuotaName"].lower()]


def assess(session, account, region):
    # Construct clients sequentially: boto3 Sessions are not shared across client creation threads.
    clients = {name: session.client(name, config=CONFIG) for name in (
        "sts", "cloudformation", "lambda", "ssm", "iam", "service-quotas", "sagemaker",
        "ec2", "apigatewayv2", "cognito-idp", "dynamodb", "s3", "scheduler", "sqs", "sns",
        "iot", "ecr", "stepfunctions", "secretsmanager", "cloudwatch")}
    identity = clients["sts"].get_caller_identity()
    if not account or identity["Account"] != account or not identity["Arn"].startswith(
            "arn:aws:iam::" + account + ":user/"):
        raise ValueError("explicit_expected_account_and_IAM_user_required_for_permission_audit")
    user = identity["Arn"].rsplit("/", 1)[1]
    tasks = []
    def add(name, operation, select):
        tasks.append((name, operation, select))
    for stack in ("CDKToolkit", "EcoRouteData", "EcoRouteCore", "EcoRouteML", "EcoRouteIoT", "EcoRouteHosting"):
        add("stack:" + stack, lambda stack=stack: clients["cloudformation"].describe_stacks(StackName=stack),
            lambda value: {"status": value["Stacks"][0]["StackStatus"]})
    add("bootstrap_version", lambda: clients["ssm"].get_parameter(Name="/cdk-bootstrap/hnb659fds/version"),
        lambda value: {"version": value["Parameter"]["Value"]})
    add("lambda_limits", clients["lambda"].get_account_settings, lambda value: value["AccountLimit"])
    add("region", lambda: clients["ec2"].describe_regions(RegionNames=[region]),
        lambda value: [{"region": r["RegionName"], "status": r["OptInStatus"]} for r in value["Regions"]])
    add("attached_user_policies", lambda: clients["iam"].list_attached_user_policies(UserName=user),
        lambda value: {"policy_names": [p["PolicyName"] for p in value["AttachedPolicies"]],
                       "truncated": value.get("IsTruncated", False)})
    add("sagemaker_training_quota", lambda: clients["service-quotas"].list_service_quotas(ServiceCode="sagemaker", MaxResults=100),
        lambda value: {"matching": quota_summary(value), "incomplete": bool(value.get("NextToken"))})
    probes = (
        ("sagemaker", "list_training_jobs", {"MaxResults": 1}, "TrainingJobSummaries"),
        ("apigatewayv2", "get_apis", {"MaxResults": "1"}, "Items"),
        ("cognito-idp", "list_user_pools", {"MaxResults": 1}, "UserPools"),
        ("dynamodb", "list_tables", {"Limit": 1}, "TableNames"),
        ("s3", "list_buckets", {}, "Buckets"),
        ("scheduler", "list_schedules", {"MaxResults": 1}, "Schedules"),
        ("sqs", "list_queues", {"MaxResults": 1}, "QueueUrls"),
        ("sns", "list_topics", {}, "Topics"),
        ("iot", "list_things", {"maxResults": 1}, "things"),
        ("ecr", "describe_repositories", {"maxResults": 1}, "repositories"),
        ("stepfunctions", "list_state_machines", {"maxResults": 1}, "stateMachines"),
        ("secretsmanager", "list_secrets", {"MaxResults": 1}, "SecretList"),
        ("cloudwatch", "describe_alarms", {"MaxRecords": 1}, "MetricAlarms"),
    )
    for service, method, args, key in probes:
        add("service_read:" + service,
            lambda service=service, method=method, args=args: getattr(clients[service], method)(**args),
            lambda value, key=key: {"returned_count": len(value.get(key, [])),
                                    "incomplete": bool(value.get("NextToken"))})
    actions = ["cloudformation:CreateStack", "iam:CreateRole", "iam:PassRole", "lambda:CreateFunction",
               "s3:CreateBucket", "dynamodb:CreateTable", "apigateway:POST", "cognito-idp:CreateUserPool",
               "sagemaker:CreateTrainingJob", "ecr:CreateRepository", "states:CreateStateMachine",
               "scheduler:CreateSchedule", "sqs:CreateQueue", "sns:CreateTopic", "iot:CreateTopicRule"]
    add("permission_simulation", lambda: clients["iam"].simulate_principal_policy(
        PolicySourceArn=identity["Arn"], ActionNames=actions, ResourceArns=["*"],
        ContextEntries=[{"ContextKeyName": "aws:RequestedRegion", "ContextKeyType": "string",
                         "ContextKeyValues": [region]}]),
        lambda value: {"assessment_only_not_deployment_proof": True,
            "decisions": [{"action": r["EvalActionName"], "decision": r["EvalDecision"],
                           "missing_context": r.get("MissingContextValues", [])}
                          for r in value["EvaluationResults"]]})
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda task: check(*task), tasks))
    return {"account": account, "region": region, "identity": "IAM user (not root)",
            "resources_created": False, "training_launched": False,
            "warning": "Successful list/read calls do not prove creation, PassRole, quota or runtime permissions.",
            "checks": results}


def main():
    values = dotenv_values(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=values.get("AWS_PROFILE"))
    parser.add_argument("--region", default=values.get("AWS_REGION") or "ap-south-1")
    parser.add_argument("--expected-account-id", default=values.get("EXPECTED_AWS_ACCOUNT_ID"))
    parser.add_argument("--output", default="work/aws-service-readiness.json")
    args = parser.parse_args()
    if not args.profile or not args.expected_account_id:
        parser.error("Configure AWS_PROFILE and EXPECTED_AWS_ACCOUNT_ID locally; no secret values required")
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    report = assess(session, args.expected_account_id, args.region)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
