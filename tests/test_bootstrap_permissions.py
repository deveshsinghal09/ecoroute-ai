import json
from fnmatch import fnmatchcase

import pytest

from scripts.prepare_aws_bootstrap import BOUNDARY, EXECUTION, build_template, policies
from scripts.manage_cloud import guard_bootstrap, load_context

ACCOUNT = "112920804206"
REGION = "ap-south-1"


def actions(policy):
    return {action for statement in policy["Statement"] for action in statement["Action"]}


def permits_resource(policy, action, resource):
    # Resource-only check: conditions can further restrict, never expand, these grants.
    return any(action in statement["Action"] and any(fnmatchcase(resource, pattern)
               for pattern in ([statement["Resource"]] if isinstance(statement["Resource"], str)
                               else statement["Resource"])) for statement in policy["Statement"])


def test_execution_cannot_modify_deployer_or_boundary_and_requires_boundary_on_roles():
    selected = policies(ACCOUNT, REGION)
    policy = selected["EcoRouteExecuteIam"]
    for forbidden in ("iam:CreatePolicy", "iam:CreatePolicyVersion", "iam:AttachUserPolicy",
                      "iam:DeleteRolePermissionsBoundary", "iam:CreateUser"):
        assert forbidden not in actions(policy)
    create = next(s for s in policy["Statement"] if "iam:CreateRole" in s["Action"])
    assert create["Condition"]["StringEquals"]["iam:PermissionsBoundary"] == (
        f"arn:aws:iam::{ACCOUNT}:policy/{BOUNDARY}")
    assert not permits_resource(policy, "iam:PutRolePolicy",
                                f"arn:aws:iam::{ACCOUNT}:role/cdk-hnb659fds-cfn-exec-role-{ACCOUNT}-{REGION}")


def test_workload_boundary_cannot_read_unrelated_health_data_or_launch_training():
    boundary = policies(ACCOUNT, REGION)[BOUNDARY]
    assert not permits_resource(boundary, "s3:GetObject", "arn:aws:s3:::other-private-bucket/health.json")
    assert not permits_resource(boundary, "secretsmanager:GetSecretValue",
                                f"arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:other/api-KeyAbc")
    assert not permits_resource(boundary, "dynamodb:GetItem",
                                f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/OtherPatients")
    assert not any(a.startswith("iam:") or a == "sagemaker:CreateTrainingJob" for a in actions(boundary))
    assert permits_resource(boundary, "s3:GetObject", "arn:aws:s3:::ecoroutedata-airdata-abc/curated/air.parquet")


def test_policies_fit_managed_limit_and_use_explicit_actions():
    values = policies(ACCOUNT, REGION)
    for policy in values.values():
        assert len(json.dumps(policy, separators=(",", ":"))) <= 6144
        assert all("*" not in action for action in actions(policy))
    assert "cloudfront:CreateDistributionWithTags" not in actions(values["EcoRouteExecuteAutomation"])
    assert "s3:DeleteBucketOwnershipControls" not in actions(values["EcoRouteExecuteStorage"])
    create = next(s for s in values["EcoRouteExecuteCompute"]["Statement"]
                  if "lambda:CreateEventSourceMapping" in s["Action"])
    assert create["Resource"] == "*"
    assert "lambda:FunctionArn" in create["Condition"]["ArnLike"]


def test_execution_can_resolve_only_its_bootstrap_version_parameter():
    policy = policies(ACCOUNT, REGION)["EcoRouteExecuteStorage"]
    parameter = f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/cdk-bootstrap/hnb659fds/version"
    for action in ("ssm:GetParameter", "ssm:GetParameters"):
        assert permits_resource(policy, action, parameter)
        assert not permits_resource(policy, action,
            f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/other/private")
    assert "ssm:PutParameter" not in actions(policy)


def test_cognito_mfa_configuration_is_project_tag_and_region_restricted():
    policy = policies(ACCOUNT, REGION)["EcoRouteExecuteCompute"]
    statement = next(s for s in policy["Statement"]
                     if "cognito-idp:SetUserPoolMfaConfig" in s["Action"])
    assert "cognito-idp:GetUserPoolMfaConfig" in statement["Action"]
    assert statement["Resource"] == f"arn:aws:cognito-idp:{REGION}:{ACCOUNT}:userpool/*"
    assert statement["Condition"]["StringEquals"] == {
        "aws:RequestedRegion": REGION, "aws:ResourceTag/Project": "ecoroute-ai"}


def test_bootstrap_removes_admin_and_cross_account_deployment_grants():
    keys = ("FileAssetsBucketKmsKeyId", "Qualifier", "TrustedAccounts", "TrustedAccountsForLookup",
            "CloudFormationExecutionPolicies", "PublicAccessBlockConfiguration", "UseExamplePermissionsBoundary",
            "InputPermissionsBoundary", "FileAssetsBucketName", "ContainerAssetsRepositoryName", "BootstrapVariant")
    keys = (*keys, "DenyExternalId")
    base = {"Parameters": {k: {} for k in keys}, "Conditions": {"HasCloudFormationExecutionPolicies": {}},
            "Resources": {k: {"Properties": {"ManagedPolicyArns": ["AdministratorAccess"]}}
                          for k in ("CloudFormationExecutionRole", "DeploymentActionRole", "LookupRole")},
            "Outputs": {}}
    result = build_template(base, ACCOUNT, REGION)
    assert "AdministratorAccess" not in json.dumps(result)
    assert result["Resources"]["CloudFormationExecutionRole"]["Properties"]["ManagedPolicyArns"] == [
        {"Ref": n} for n in EXECUTION]
    assert result["Resources"]["EcoRouteCdkDeployer"]["Properties"]["Users"] == ["devesh_eco"]
    assert "PublicAccessBlockConfiguration" not in result["Parameters"]
    assert "FileAssetsBucketKmsKeyId" not in result["Parameters"]
    assert "UseExamplePermissionsBoundary" not in result["Parameters"]
    assert "AdministratorAccess" in json.dumps(base), "original template must remain untouched"


def test_bootstrap_rejects_other_regions_and_invalid_accounts():
    for account, region in (("invalid", REGION), (ACCOUNT, "us-east-1")):
        with pytest.raises(ValueError):
            policies(account, region)


def test_context_accepts_only_exact_named_boundary(tmp_path):
    path = tmp_path / "context.json"
    path.write_text(json.dumps({"workload_boundary_arn": f"arn:aws:iam::{ACCOUNT}:policy/{BOUNDARY}"}))
    assert load_context(path)["workload_boundary_arn"].endswith(BOUNDARY)
    path.write_text(json.dumps({"workload_boundary_arn": f"arn:aws:iam::{ACCOUNT}:policy/*"}))
    with pytest.raises(ValueError):
        load_context(path)


def test_deploy_stops_before_partial_creation_when_boundary_is_missing():
    stack = {"StackStatus": "CREATE_COMPLETE", "Parameters": [
        {"ParameterKey": "BootstrapVariant", "ParameterValue": "EcoRoute: Scoped Bootstrap v1"}]}
    with pytest.raises(ValueError, match="workload boundary"):
        guard_bootstrap(stack, {}, ACCOUNT)
    guard_bootstrap(stack, {"workload_boundary_arn": f"arn:aws:iam::{ACCOUNT}:policy/{BOUNDARY}"}, ACCOUNT)
    stack["StackStatus"] = "ROLLBACK_COMPLETE"
    with pytest.raises(ValueError, match="complete deployment state"):
        guard_bootstrap(stack, {}, ACCOUNT)
