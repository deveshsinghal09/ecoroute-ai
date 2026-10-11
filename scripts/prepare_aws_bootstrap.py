"""Generate a scoped Console bootstrap offline; never reads credentials or calls AWS."""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUALIFIER = "hnb659fds"
BOUNDARY = "EcoRouteWorkloadBoundary"
EXECUTION = ("EcoRouteExecuteStorage", "EcoRouteExecuteCompute",
             "EcoRouteExecuteAutomation", "EcoRouteExecuteIam")


def allow(actions, resources, condition=None):
    result = {"Effect": "Allow", "Action": actions.split(), "Resource": resources}
    if condition:
        result["Condition"] = condition
    return result


def document(statements):
    return {"Version": "2012-10-17", "Statement": statements}


def specialize(value, conditions):
    """Remove unreachable canonical options after fixing the bootstrap configuration."""
    if value == {"Ref": "AWS::NoValue"}:
        return None
    if isinstance(value, dict):
        if "Fn::If" in value and value["Fn::If"][0] in conditions:
            name, yes, no = value["Fn::If"]
            return specialize(yes if conditions[name] else no, conditions)
        return {k: v for k, raw in value.items() if (v := specialize(raw, conditions)) is not None}
    if isinstance(value, list):
        return [v for raw in value if (v := specialize(raw, conditions)) is not None]
    return value


def policies(account, region):
    if not re.fullmatch(r"\d{12}", account) or region != "ap-south-1":
        raise ValueError("Explicit account ID and reviewed Mumbai region required")
    regional = {"StringEquals": {"aws:RequestedRegion": region}}
    def arn(service, resource):
        return f"arn:aws:{service}:{region}:{account}:{resource}"
    buckets = ["arn:aws:s3:::" + name + "-*" for name in
               ("ecoroutedata", "ecorouteml", "ecoroutehosting")]
    functions = arn("lambda", "function:EcoRoute*")
    tables = arn("dynamodb", "table/EcoRouteData*")
    queues = arn("sqs", "EcoRoute*")
    logs = [arn("logs", "log-group:" + name + suffix)
            for name in ("EcoRoute*", "/ecoroute/*", "/aws/lambda/EcoRoute*")
            for suffix in ("", ":*")]
    repository = arn("ecr", "repository/ecoroute-ai-ml-training")
    roles = f"arn:aws:iam::{account}:role/EcoRoute*"
    boundary = f"arn:aws:iam::{account}:policy/{BOUNDARY}"
    stacks = [arn("cloudformation", "stack/EcoRoute*/*"), arn("cloudformation", "stack/CDKToolkit/*")]
    changes = arn("cloudformation", "changeSet/cdk-deploy-change-set/*")
    asset = f"arn:aws:s3:::cdk-{QUALIFIER}-assets-{account}-{region}"
    stack_reads = ("cloudformation:DescribeStacks cloudformation:DescribeStackEvents "
                   "cloudformation:DescribeStackResources cloudformation:ListStackResources "
                   "cloudformation:GetTemplate cloudformation:GetTemplateSummary "
                   "cloudformation:DescribeChangeSet cloudformation:ListChangeSets")
    storage = document([
        allow("s3:CreateBucket s3:DeleteBucket s3:GetBucketLocation s3:GetBucketAcl s3:PutBucketAcl "
              "s3:GetBucketPolicy s3:PutBucketPolicy s3:DeleteBucketPolicy s3:GetBucketCORS "
              "s3:PutBucketCORS s3:GetBucketVersioning s3:PutBucketVersioning "
              "s3:GetEncryptionConfiguration s3:PutEncryptionConfiguration "
              "s3:GetBucketPublicAccessBlock s3:PutBucketPublicAccessBlock "
              "s3:GetBucketOwnershipControls s3:PutBucketOwnershipControls "
              "s3:GetLifecycleConfiguration "
              "s3:PutLifecycleConfiguration s3:GetBucketTagging s3:PutBucketTagging "
              "s3:GetBucketNotification s3:PutBucketNotification s3:GetBucketLogging "
              "s3:PutBucketLogging s3:GetBucketWebsite s3:GetBucketRequestPayment s3:ListBucket",
              buckets, regional),
        allow("dynamodb:CreateTable dynamodb:DeleteTable dynamodb:DescribeTable dynamodb:UpdateTable "
              "dynamodb:DescribeTimeToLive dynamodb:UpdateTimeToLive "
              "dynamodb:DescribeContinuousBackups dynamodb:UpdateContinuousBackups "
              "dynamodb:ListTagsOfResource dynamodb:TagResource dynamodb:UntagResource", tables, regional),
        allow("sqs:CreateQueue sqs:DeleteQueue sqs:GetQueueAttributes sqs:GetQueueUrl "
              "sqs:SetQueueAttributes sqs:TagQueue sqs:UntagQueue sqs:ListQueueTags", queues, regional),
        allow("ecr:CreateRepository ecr:DeleteRepository ecr:DescribeRepositories "
              "ecr:GetRepositoryPolicy ecr:SetRepositoryPolicy ecr:DeleteRepositoryPolicy "
              "ecr:PutLifecyclePolicy ecr:GetLifecyclePolicy ecr:PutImageScanningConfiguration "
              "ecr:PutImageTagMutability ecr:TagResource ecr:UntagResource ecr:ListTagsForResource",
              repository, regional),
        allow("s3:GetObject s3:GetObjectVersion", asset + "/*", regional),
        allow("s3:GetBucketLocation s3:ListBucket", asset, regional),
    ])
    compute = document([
        allow("lambda:CreateFunction lambda:DeleteFunction lambda:GetFunction "
              "lambda:GetFunctionConfiguration lambda:UpdateFunctionCode "
              "lambda:UpdateFunctionConfiguration lambda:TagResource lambda:UntagResource "
              "lambda:ListTags lambda:AddPermission lambda:RemovePermission lambda:GetPolicy "
              "lambda:GetFunctionConcurrency lambda:PutFunctionEventInvokeConfig "
              "lambda:GetFunctionEventInvokeConfig lambda:DeleteFunctionEventInvokeConfig "
              "lambda:InvokeFunction", functions, regional),
        allow("lambda:CreateEventSourceMapping", "*", {
            "StringEquals": {"aws:RequestedRegion": region},
            "ArnLike": {"lambda:FunctionArn": functions}}),
        allow("lambda:UpdateEventSourceMapping "
              "lambda:GetEventSourceMapping lambda:DeleteEventSourceMapping",
              arn("lambda", "event-source-mapping:*"),
              {"StringEquals": {"aws:RequestedRegion": region},
               "ArnLike": {"lambda:FunctionArn": functions}}),
        allow("lambda:TagResource lambda:UntagResource lambda:ListTags",
              arn("lambda", "event-source-mapping:*"), regional),
        allow("logs:CreateLogGroup logs:DeleteLogGroup logs:PutRetentionPolicy logs:DeleteRetentionPolicy "
              "logs:TagLogGroup logs:UntagLogGroup logs:TagResource logs:UntagResource "
              "logs:ListTagsForResource", logs, regional),
        allow("logs:DescribeLogGroups", "*", regional),
        allow("cognito-idp:CreateUserPool", "*", {"StringEquals": {
            "aws:RequestedRegion": region, "aws:RequestTag/Project": "ecoroute-ai"}}),
        allow("cognito-idp:DescribeUserPool cognito-idp:UpdateUserPool cognito-idp:DeleteUserPool "
              "cognito-idp:CreateUserPoolClient cognito-idp:DescribeUserPoolClient "
              "cognito-idp:UpdateUserPoolClient cognito-idp:DeleteUserPoolClient "
              "cognito-idp:CreateResourceServer cognito-idp:DescribeResourceServer "
              "cognito-idp:UpdateResourceServer cognito-idp:DeleteResourceServer "
              "cognito-idp:CreateUserPoolDomain cognito-idp:UpdateUserPoolDomain "
              "cognito-idp:DeleteUserPoolDomain cognito-idp:TagResource "
              "cognito-idp:UntagResource cognito-idp:ListTagsForResource",
              arn("cognito-idp", "userpool/*"), {"StringEquals": {
                  "aws:RequestedRegion": region, "aws:ResourceTag/Project": "ecoroute-ai"}}),
        allow("cognito-idp:DescribeUserPoolDomain", "*", regional),
        allow("apigateway:GET apigateway:POST apigateway:PATCH apigateway:PUT apigateway:DELETE",
              [f"arn:aws:apigateway:{region}::/apis", f"arn:aws:apigateway:{region}::/apis/*",
               f"arn:aws:apigateway:{region}::/tags/*"], regional),
    ])
    automation = document([
        allow("cloudwatch:PutMetricAlarm cloudwatch:DeleteAlarms cloudwatch:DescribeAlarms "
              "cloudwatch:TagResource cloudwatch:UntagResource cloudwatch:ListTagsForResource",
              arn("cloudwatch", "alarm:EcoRoute*"), regional),
        allow("sns:CreateTopic sns:DeleteTopic sns:GetTopicAttributes sns:SetTopicAttributes "
              "sns:TagResource sns:UntagResource sns:ListTagsForResource", arn("sns", "EcoRoute*"), regional),
        allow("states:CreateStateMachine states:DescribeStateMachine states:UpdateStateMachine "
              "states:DeleteStateMachine states:TagResource states:UntagResource "
              "states:ListTagsForResource", arn("states", "stateMachine:EcoRoute*"), regional),
        allow("scheduler:CreateSchedule scheduler:GetSchedule scheduler:UpdateSchedule "
              "scheduler:DeleteSchedule", arn("scheduler", "schedule/default/EcoRoute*"), regional),
        allow("iot:CreateTopicRule iot:GetTopicRule iot:ReplaceTopicRule iot:DeleteTopicRule "
              "iot:TagResource iot:UntagResource iot:ListTagsForResource",
              [arn("iot", "rule/EcoRoute*"), arn("iot", "rule/ecoroute_*")], regional),
        # These CloudFront creation/OAC actions lack resource-level permissions.
        allow("cloudfront:CreateDistribution", "*", {
            "StringEquals": {"aws:RequestTag/Project": "ecoroute-ai"}}),
        allow("cloudfront:CreateOriginAccessControl cloudfront:GetOriginAccessControl "
              "cloudfront:UpdateOriginAccessControl cloudfront:DeleteOriginAccessControl", "*"),
        allow("cloudfront:GetDistribution cloudfront:GetDistributionConfig cloudfront:UpdateDistribution "
              "cloudfront:DeleteDistribution cloudfront:TagResource cloudfront:UntagResource "
              "cloudfront:ListTagsForResource", f"arn:aws:cloudfront::{account}:distribution/*",
              {"StringEquals": {"aws:ResourceTag/Project": "ecoroute-ai"}}),
    ])
    iam_policy = document([
        allow("iam:CreateRole iam:PutRolePermissionsBoundary", roles,
              {"StringEquals": {"iam:PermissionsBoundary": boundary}}),
        allow("iam:GetRole iam:DeleteRole iam:UpdateAssumeRolePolicy iam:TagRole iam:UntagRole "
              "iam:ListRoleTags iam:PutRolePolicy iam:GetRolePolicy iam:DeleteRolePolicy "
              "iam:ListRolePolicies iam:ListAttachedRolePolicies", roles),
        allow("iam:AttachRolePolicy iam:DetachRolePolicy", roles, {"ArnEquals": {"iam:PolicyARN": [
              boundary, "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]}}),
        allow("iam:GetPolicy iam:GetPolicyVersion", [boundary,
              "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]),
        allow("iam:PassRole", roles, {"StringEquals": {"iam:PassedToService": [
              "lambda.amazonaws.com", "states.amazonaws.com", "scheduler.amazonaws.com", "sagemaker.amazonaws.com"]}}),
    ])
    workload = document([
        allow("dynamodb:GetItem dynamodb:PutItem dynamodb:UpdateItem dynamodb:DeleteItem dynamodb:Query "
              "dynamodb:ConditionCheckItem dynamodb:DescribeTable dynamodb:DescribeStream "
              "dynamodb:GetRecords dynamodb:GetShardIterator",
              [tables, tables + "/stream/*", tables + "/index/*"], regional),
        allow("dynamodb:ListStreams", "*", regional),
        allow("s3:GetObject s3:PutObject s3:DeleteObject", [b + "/*" for b in buckets], regional),
        allow("s3:ListBucket s3:PutBucketNotification", buckets, regional),
        allow("sqs:ReceiveMessage sqs:DeleteMessage sqs:ChangeMessageVisibility "
              "sqs:GetQueueAttributes sqs:GetQueueUrl sqs:SendMessage", queues, regional),
        allow("logs:CreateLogGroup logs:CreateLogStream logs:PutLogEvents", logs + [
              arn("logs", "log-group:/aws/sagemaker/TrainingJobs"),
              arn("logs", "log-group:/aws/sagemaker/TrainingJobs:*")], regional),
        allow("ecr:GetAuthorizationToken", "*", regional),
        allow("ecr:BatchGetImage ecr:GetDownloadUrlForLayer ecr:BatchCheckLayerAvailability", repository, regional),
        allow("lambda:InvokeFunction", functions, regional),
        allow("states:StartExecution", arn("states", "stateMachine:EcoRoute*"), regional),
        allow("secretsmanager:GetSecretValue", arn("secretsmanager", "secret:ecoroute/*"), regional),
        allow("sns:Publish", arn("sns", "EcoRoute*"), regional),
        allow("geo-routes:CalculateRoutes geo-places:SearchText geo-places:GetPlace", "*", regional),
    ])
    deployment = document([
        allow(stack_reads + " cloudformation:CreateChangeSet cloudformation:DeleteChangeSet "
              "cloudformation:ExecuteChangeSet cloudformation:CreateStack cloudformation:UpdateStack "
              "cloudformation:DeleteStack cloudformation:RollbackStack cloudformation:ContinueUpdateRollback "
              "cloudformation:UpdateTerminationProtection", stacks + [changes], regional),
        allow("cloudformation:ListExports cloudformation:ValidateTemplate", "*", regional),
        allow("iam:PassRole", f"arn:aws:iam::{account}:role/cdk-{QUALIFIER}-cfn-exec-role-{account}-{region}",
              {"StringEquals": {"iam:PassedToService": "cloudformation.amazonaws.com"}}),
        allow("s3:GetObject s3:GetObjectVersion", asset + "/*", regional),
        allow("s3:GetBucketLocation s3:GetBucketVersioning s3:ListBucket", asset, regional),
        allow("ssm:GetParameter ssm:GetParameters", arn("ssm", f"parameter/cdk-bootstrap/{QUALIFIER}/version"), regional),
    ])
    human = document([
        allow("sts:AssumeRole", [f"arn:aws:iam::{account}:role/cdk-{QUALIFIER}-{kind}-role-{account}-{region}"
              for kind in ("deploy", "file-publishing", "image-publishing", "lookup")]),
        allow(stack_reads, stacks + [changes], regional),
        allow("cloudformation:ListExports", "*", regional),
        allow("ssm:GetParameter", arn("ssm", f"parameter/cdk-bootstrap/{QUALIFIER}/version"), regional),
        allow("budgets:ViewBudget", f"arn:aws:budgets::{account}:budget/EcoRoute-Gross-Usage"),
    ])
    return dict(zip(EXECUTION, (storage, compute, automation, iam_policy), strict=True)) | {
        BOUNDARY: workload, "EcoRouteCdkDeployer": human,
        "_deployment": deployment, "_lookup": document([
            allow("ssm:GetParameter", arn("ssm", f"parameter/cdk-bootstrap/{QUALIFIER}/version"), regional),
            allow(stack_reads, stacks + [changes], regional),
        ])}


def build_template(base, account, region):
    result = copy.deepcopy(base)
    params = result["Parameters"]
    params["FileAssetsBucketKmsKeyId"].update(Default="AWS_MANAGED_KEY", AllowedValues=["AWS_MANAGED_KEY"])
    params["Qualifier"]["AllowedValues"] = [QUALIFIER]
    params["PublicAccessBlockConfiguration"].update(Default="true", AllowedValues=["true"])
    params["UseExamplePermissionsBoundary"].update(Default="false", AllowedValues=["false"])
    params["InputPermissionsBoundary"].update(Default="", AllowedValues=[""])
    params["BootstrapVariant"]["Default"] = "EcoRoute: Scoped Bootstrap v1"
    for key in ("FileAssetsBucketName", "ContainerAssetsRepositoryName"):
        params[key].update(Default="", AllowedValues=[""])
    for key in ("TrustedAccounts", "TrustedAccountsForLookup"):
        params[key]["AllowedValues"] = [""]
    params["DenyExternalId"].update(Default="true", AllowedValues=["true"])
    params.pop("CloudFormationExecutionPolicies", None)
    result["Conditions"].pop("HasCloudFormationExecutionPolicies", None)
    resources = result["Resources"]
    values = policies(account, region)
    for name, policy in values.items():
        if name.startswith("_"):
            continue
        if len(json.dumps(policy, separators=(",", ":"))) > 6144:
            raise ValueError("Managed policy exceeds AWS size quota: " + name)
        resources[name] = {"Type": "AWS::IAM::ManagedPolicy", "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain", "Properties": {
                "ManagedPolicyName": name, "PolicyDocument": policy,
                "Description": "EcoRoute scoped Mumbai serverless deployment"}}
    resources["EcoRouteCdkDeployer"]["Properties"]["Users"] = ["devesh_eco"]
    resources["CloudFormationExecutionRole"]["Properties"]["ManagedPolicyArns"] = [
        {"Ref": name} for name in EXECUTION]
    for name, key in (("DeploymentActionRole", "_deployment"), ("LookupRole", "_lookup")):
        properties = resources[name]["Properties"]
        properties.pop("ManagedPolicyArns", None)
        properties["Policies"] = [{"PolicyName": "EcoRouteScopedDeployment", "PolicyDocument": values[key]}]
    if "FilePublishingRoleDefaultPolicy" in resources:
        resources["FilePublishingRoleDefaultPolicy"]["Properties"]["PolicyDocument"] = document([
            allow("s3:GetBucketLocation s3:GetBucketVersioning s3:GetEncryptionConfiguration "
                  "s3:ListBucket s3:ListBucketMultipartUploads", {"Fn::GetAtt": ["StagingBucket", "Arn"]}),
            allow("s3:GetObject s3:GetObjectVersion s3:PutObject s3:DeleteObject "
                  "s3:DeleteObjectVersion s3:AbortMultipartUpload s3:ListMultipartUploadParts",
                  {"Fn::Sub": "${StagingBucket.Arn}/*"}),
        ])
    if "ImagePublishingRoleDefaultPolicy" in resources:
        for entry in resources["ImagePublishingRoleDefaultPolicy"]["Properties"]["PolicyDocument"]["Statement"]:
            actions = entry.get("Action", [])
            if "ecr:GetAuthorizationToken" in ([actions] if isinstance(actions, str) else actions):
                entry["Condition"] = {"StringEquals": {"aws:RequestedRegion": region}}
    fixed = {"HasTrustedAccounts": False, "HasTrustedAccountsForLookup": False,
             "HasCustomFileAssetsBucketName": False, "CreateNewKey": False, "UseAwsManagedKey": True,
             "ShouldCreatePermissionsBoundary": False, "PermissionsBoundarySet": False,
             "HasCustomContainerAssetsRepositoryName": False, "UsePublicAccessBlockConfiguration": True,
             "ShouldDenyExternalId": True}
    for name in list(resources):
        condition = resources[name].get("Condition")
        if condition in fixed:
            if not fixed[condition]:
                del resources[name]
            else:
                resources[name].pop("Condition")
    result = specialize(result, fixed)
    for name in fixed:
        result["Conditions"].pop(name, None)
    # AWS's canonical ACL option is unnecessary with explicitly enforced bucket ownership.
    if "StagingBucket" in result["Resources"]:
        bucket = result["Resources"]["StagingBucket"]["Properties"]
        bucket.pop("AccessControl", None)
        bucket["OwnershipControls"] = {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]}
    result["Outputs"]["WorkloadBoundaryArn"] = {"Value": {"Ref": BOUNDARY}}
    result["Outputs"]["BootstrapVariant"] = {"Value": {"Ref": "BootstrapVariant"}}
    # Remove options that no longer occur after specialization; keep the CLI variant marker.
    body = json.dumps({k: v for k, v in result.items() if k != "Parameters"})
    for name in list(result["Parameters"]):
        if f'"Ref": "{name}"' not in body and "${" + name + "}" not in body:
            result["Parameters"].pop(name)
    result["Rules"] = {"CorrectEnvironment": {"Assertions": [
        {"Assert": {"Fn::Equals": [{"Ref": "AWS::AccountId"}, account]},
         "AssertDescription": "Select the credited EcoRoute account"},
        {"Assert": {"Fn::Equals": [{"Ref": "AWS::Region"}, region]},
         "AssertDescription": "Select Mumbai ap-south-1"},
    ]}}
    result["Description"] = "EcoRoute scoped CDK bootstrap and IAM; no application deployment or training"
    if "AdministratorAccess" in json.dumps(result):
        raise ValueError("Unexpected broad execution policy remains")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--output", default="work/EcoRouteBootstrap.console.json")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "work/bootstrap-tools"))
    try:
        import yaml
    except ImportError:
        parser.error("Install requirements-bootstrap.txt into work/bootstrap-tools first")
    source = ROOT / "node_modules/aws-cdk/lib/api/bootstrap/bootstrap-template.yaml"
    version = json.loads((ROOT / "node_modules/aws-cdk/package.json").read_text())["version"]
    if version != "2.1145.0":
        raise ValueError("Review the canonical bootstrap template before using a different CDK CLI version")
    base = yaml.safe_load(source.read_text(encoding="utf-8"))
    result = build_template(base, args.account, args.region)
    payload = json.dumps(result, separators=(",", ":")) + "\n"
    if len(payload.encode("utf-8")) > 51200:
        raise ValueError("Template exceeds CloudFormation direct-upload size quota")
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(payload, encoding="utf-8")
    print(json.dumps({"file": str(destination), "cloud_mutations": False,
        "template_bytes": len(payload.encode("utf-8")), "requires_authorized_console_operator": True,
        "workload_boundary_arn": f"arn:aws:iam::{args.account}:policy/{BOUNDARY}"}))


if __name__ == "__main__":
    main()
