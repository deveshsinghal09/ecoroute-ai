import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from infra.stacks import CoreStack, DataStack, IotStack, MlStack


@pytest.fixture(scope="module")
def templates(tmp_path_factory):
    work = tmp_path_factory.mktemp("cdk")
    asset = work / "asset"
    asset.mkdir()
    (asset / "handler.py").write_text("# structural test asset only\n")
    app = cdk.App(outdir=str(work / "assembly"))
    env = cdk.Environment(account="123456789012", region="ap-south-1")
    data = DataStack(app, "Data", env=env)
    ml = MlStack(app, "ML", env=env)
    core = CoreStack(app, "Core", data=data, asset_path=asset, env=env,
                     callback_urls=["https://example.org/callback"],
                     provider_secret_arn="arn:aws:secretsmanager:ap-south-1:123456789012:secret:ecoroute/demo-AbCdEf")
    optional = IotStack(app, "IoT", env=env)
    return {name: Template.from_stack(stack).to_json() for name, stack in (
        ("data", data), ("ml", ml), ("core", core), ("iot", optional))}


def resources(template, kind):
    return [r for r in template["Resources"].values() if r["Type"] == kind]


def test_no_idle_compute_or_nat(templates):
    for template in templates.values():
        for resource in template.get("Resources", {}).values():
            assert resource["Type"] not in {"AWS::EC2::NatGateway", "AWS::ECS::Service",
                "AWS::SageMaker::Endpoint", "AWS::RDS::DBInstance", "AWS::IoT::Certificate"}


def test_tables_retention_encryption_and_caps(templates):
    tables = resources(templates["data"], "AWS::DynamoDB::Table")
    assert len(tables) == 5
    for table in tables:
        props = table["Properties"]
        assert props["BillingMode"] == "PAY_PER_REQUEST"
        assert props["SSESpecification"]["SSEEnabled"] is True
        assert props["TimeToLiveSpecification"] == {"AttributeName": "expires_at", "Enabled": True}
        assert props["DeletionProtectionEnabled"] is True
        assert props["OnDemandThroughput"]["MaxWriteRequestUnits"] == 10
        assert table["DeletionPolicy"] == "Retain"


def test_s3_private_encrypted_tls_and_lifecycle(templates):
    for name in ("data", "ml"):
        template = templates[name]
        b = resources(template, "AWS::S3::Bucket")[0]
        assert all(b["Properties"]["PublicAccessBlockConfiguration"].values())
        assert b["Properties"]["BucketEncryption"]["ServerSideEncryptionConfiguration"]
        assert b["Properties"]["LifecycleConfiguration"]["Rules"]
        assert b["DeletionPolicy"] == "Retain"
        policy = resources(template, "AWS::S3::BucketPolicy")[0]
        assert "aws:SecureTransport" in json.dumps(policy)


def test_jwt_protects_all_domain_routes(templates):
    template = templates["core"]
    public = {"GET /api/v1/health", "GET /healthz", "GET /docs", "GET /openapi.json"}
    for route in resources(template, "AWS::ApiGatewayV2::Route"):
        props = route["Properties"]
        if props["RouteKey"] in public:
            assert props["AuthorizationType"] == "NONE"
        else:
            assert props["AuthorizationType"] == "JWT"
            assert props["AuthorizationScopes"] in (["ecoroute/read"], ["ecoroute/write"])
    authorizer = resources(template, "AWS::ApiGatewayV2::Authorizer")[0]["Properties"]
    assert authorizer["IdentitySource"] == ["$request.header.Authorization"]
    assert authorizer["JwtConfiguration"]["Audience"]
    client = resources(template, "AWS::Cognito::UserPoolClient")[0]["Properties"]
    assert client["GenerateSecret"] is False
    assert client["AllowedOAuthFlows"] == ["code"]
    scopes = client["AllowedOAuthScopes"]
    assert "openid" in scopes and len(scopes) == 3
    assert "/read" in json.dumps(scopes) and "/write" in json.dumps(scopes)


def test_queue_worker_schedule_and_alarms(templates):
    template = templates["core"]
    queues = resources(template, "AWS::SQS::Queue")
    assert len(queues) == 2
    assert all(q["Properties"]["SqsManagedSseEnabled"] for q in queues)
    source = resources(template, "AWS::Lambda::EventSourceMapping")[0]["Properties"]
    assert source["FunctionResponseTypes"] == ["ReportBatchItemFailures"]
    assert source["ScalingConfig"]["MaximumConcurrency"] == 2
    assert resources(template, "AWS::Scheduler::Schedule")[0]["Properties"]["State"] == "DISABLED"
    assert len(resources(template, "AWS::CloudWatch::Alarm")) == 5
    for group in resources(template, "AWS::Logs::LogGroup"):
        assert group["Properties"]["RetentionInDays"] == 7
    assert len(resources(template, "AWS::Lambda::Function")) == 2


def test_no_broad_runtime_permissions_or_embedded_secrets(templates):
    for policy in resources(templates["core"], "AWS::IAM::Policy"):
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
            actions = statement["Action"]
            actions = [actions] if isinstance(actions, str) else actions
            assert not any("*" in action for action in actions)
            assert statement["Resource"] != "*"
    assert not resources(templates["core"], "AWS::SecretsManager::Secret")
    functions = resources(templates["core"], "AWS::Lambda::Function")
    assert any("POLLUTION_SECRET_ARN" in fn["Properties"]["Environment"]["Variables"] for fn in functions)
    assert "AWS_SECRET_ACCESS_KEY" not in json.dumps(functions)
