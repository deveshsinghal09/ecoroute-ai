from botocore.exceptions import ClientError
from scripts.aws_readiness import check, quota_summary, training_quota


def test_denial_never_prints_aws_error_message():
    def denied():
        raise ClientError({"Error": {"Code": "AccessDenied", "Message": "PRIVATE_DESTINATION"}}, "Read")
    result = check("metadata", denied, lambda value: value)
    assert result == {"check": "metadata", "status": "unverified", "error_code": "AccessDenied"}


def test_sagemaker_quota_does_not_confuse_training_with_endpoint_limit():
    result = quota_summary({"Quotas": [
        {"QuotaName": "ml.m5.large for training job usage", "QuotaCode": "training", "Value": 0},
        {"QuotaName": "ml.m5.large for endpoint usage", "QuotaCode": "endpoint", "Value": 1},
        {"QuotaName": "ml.m5.large for training warm pool usage", "QuotaCode": "warm", "Value": 8},
    ]})
    assert result == [{"name": "ml.m5.large for training job usage", "code": "training", "value": 0,
                       "adjustable": False}]


def test_training_quota_uses_exact_quota_not_first_list_page():
    class Client:
        def get_service_quota(self, **kwargs):
            assert kwargs == {"ServiceCode": "sagemaker", "QuotaCode": "L-611FA074"}
            return {"Quota": {"QuotaName": "ml.m5.large for training job usage",
                              "QuotaCode": "L-611FA074", "Value": 0, "Adjustable": True}}

    result = training_quota(Client())
    assert result["training_limit_identified"]
    assert not result["incomplete"]
    assert result["matching"][0]["value"] == 0


def test_stack_absence_requires_specific_service_response():
    def response(code, message):
        def operation():
            raise ClientError({"Error": {"Code": code, "Message": message}}, "DescribeStacks")
        return operation

    assert check("stack:EcoRouteData", response("ValidationError", "Stack does not exist"),
                 lambda value: value)["status"] == "not_found"
    for code, message in (("AccessDenied", "PRIVATE_MARKER"),
                          ("ValidationError", "Other validation failure")):
        result = check("stack:EcoRouteData", response(code, message), lambda value: value)
        assert result["status"] == "unverified"
        assert "PRIVATE_MARKER" not in str(result)


def test_ecr_registry_token_exception_requires_exact_regional_condition():
    from scripts.security_review import review
    statement = {"Effect": "Allow", "Action": "ecr:GetAuthorizationToken", "Resource": "*",
                 "Condition": {"StringEquals": {"aws:RequestedRegion": "ap-south-1"}}}
    template = {"Resources": {"RolePolicy": {"Type": "AWS::IAM::Policy", "Properties": {
        "PolicyDocument": {"Statement": [statement]}}}}}
    assert not review(template)["issues"]
    statement.pop("Condition")
    assert review(template)["issues"]


def test_deployment_context_rejects_keys_without_printing_values(tmp_path):
    import json
    import pytest
    from scripts.manage_cloud import load_context
    path = tmp_path / "context.json"
    for value in ({"GEMINI_API_KEY": "PRIVATE_TEST_MARKER"},
                  {"gemini_secret_arn": "PRIVATE_TEST_MARKER"}):
        path.write_text(json.dumps(value))
        with pytest.raises(ValueError) as error:
            load_context(path)
        assert "PRIVATE_TEST_MARKER" not in str(error.value)
    path.write_text(json.dumps({"gemini_secret_arn": "arn:aws:secretsmanager:ap-south-1:123456789012:secret:gemini-AbCdEf",
                                "frontend_origins": ["https://example.org"]}))
    assert load_context(path)["frontend_origins"] == ["https://example.org"]


def test_workflow_context_survives_deployment_command(monkeypatch):
    from infra.profiles import context_list
    from scripts.manage_cloud import command
    monkeypatch.setattr("scripts.manage_cloud.shutil.which", lambda name: "node")
    value = command("deploy", "test", workflows=True,
                    context={"frontend_origins": ["https://example.org"]})
    assert "enable_workflows=true" in value
    assert 'frontend_origins=["https://example.org"]' in value
    assert context_list(value[-1].split("=", 1)[1]) == ["https://example.org"]
