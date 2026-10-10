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
                     frontend_origins=["https://example.org"],
                     google_routes_secret_arn="arn:aws:secretsmanager:ap-south-1:123456789012:secret:ecoroute/google-AbCdEf",
                     provider_secret_arn="arn:aws:secretsmanager:ap-south-1:123456789012:secret:ecoroute/demo-AbCdEf")
    optional = IotStack(app, "IoT", env=env, data=data, asset_path=asset)
    return {name: Template.from_stack(stack).to_json() for name, stack in (
        ("data", data), ("ml", ml), ("core", core), ("iot", optional))}


def resources(template, kind):
    return [r for r in template["Resources"].values() if r["Type"] == kind]


def test_guest_routes_are_opt_in_and_secret_permissions_are_scoped(templates, tmp_path):
    from infra.stacks import CoreStack, DataStack
    assert not any(r["Properties"].get("RouteKey") == "POST /api/v1/routes/preview"
                   for r in resources(templates["core"], "AWS::ApiGatewayV2::Route"))
    asset = tmp_path / "asset"
    asset.mkdir()
    (asset / "handler.py").write_text("# structural test asset\n")
    app = cdk.App()
    env = cdk.Environment(account="123456789012", region="ap-south-1")
    data = DataStack(app, "GuestData", env=env)
    google_secret = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:google-AbCdEf"
    cycle_secret = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:cycling-AbCdEf"
    stack = CoreStack(app, "GuestCore", data=data, env=env, asset_path=str(asset),
                      google_routes_secret_arn=google_secret, cycling_secret_arn=cycle_secret,
                      enable_guest_routes=True)
    template = Template.from_stack(stack).to_json()
    guest = next(r["Properties"] for r in resources(template, "AWS::ApiGatewayV2::Route")
                 if r["Properties"].get("RouteKey") == "POST /api/v1/routes/preview")
    assert guest["AuthorizationType"] == "NONE"
    private = next(r["Properties"] for r in resources(template, "AWS::ApiGatewayV2::Route")
                   if r["Properties"].get("RouteKey") == "POST /api/v1/{proxy+}")
    assert private["AuthorizationType"] == "JWT" and private["AuthorizationScopes"] == ["ecoroute/write"]
    policies = resources(template, "AWS::IAM::Policy")
    grants = [s for p in policies for s in p["Properties"]["PolicyDocument"]["Statement"]
              if s.get("Action") == "secretsmanager:GetSecretValue"]
    assert any(s["Resource"] == google_secret for s in grants)
    assert any(s["Resource"] == cycle_secret for s in grants)


def test_frontend_cors_is_exact_and_not_credentialed(templates):
    api = resources(templates["core"], "AWS::ApiGatewayV2::Api")[0]["Properties"]
    assert api["CorsConfiguration"]["AllowOrigins"] == ["https://example.org"]
    assert api["CorsConfiguration"]["AllowCredentials"] is False
    assert "Authorization" in api["CorsConfiguration"]["AllowHeaders"]
    assert "OPTIONS" in api["CorsConfiguration"]["AllowMethods"]


@pytest.mark.parametrize("origin", ["*", "https://*.example.org", "http://example.org", "https://example.org/path"])
def test_frontend_cors_rejects_unsafe_origins(origin):
    app = cdk.App()
    with pytest.raises(ValueError, match="exact HTTPS"):
        CoreStack(app, "Unsafe", data=None, asset_path="unused", frontend_origins=[origin])


def test_no_idle_compute_or_nat(templates):
    for template in templates.values():
        for resource in template.get("Resources", {}).values():
            assert resource["Type"] not in {"AWS::EC2::NatGateway", "AWS::ECS::Service",
                "AWS::SageMaker::Endpoint", "AWS::RDS::DBInstance", "AWS::IoT::Certificate"}


def test_iot_rule_envelope_permission_and_retention(templates):
    iot = templates["iot"]
    rule = resources(iot, "AWS::IoT::TopicRule")[0]["Properties"]["TopicRulePayload"]
    assert rule["RuleDisabled"] is True
    assert "encode(*, 'base64')" in rule["Sql"] and "principal()" in rule["Sql"]
    permission = resources(iot, "AWS::Lambda::Permission")[0]["Properties"]
    assert permission["Principal"] == "iot.amazonaws.com" and permission["SourceAccount"] == "123456789012"
    assert permission["SourceArn"]
    assert not resources(iot, "AWS::IoT::Certificate")
    queue = resources(iot, "AWS::SQS::Queue")[0]["Properties"]
    assert queue["MessageRetentionPeriod"] == 86400 and queue["SqsManagedSseEnabled"]


def test_tables_retention_encryption_and_caps(templates):
    tables = resources(templates["data"], "AWS::DynamoDB::Table")
    assert len(tables) == 7
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
    queues = resources(templates["data"], "AWS::SQS::Queue")
    assert len(queues) == 2
    assert all(q["Properties"]["SqsManagedSseEnabled"] for q in queues)
    source = next(r["Properties"] for r in resources(template, "AWS::Lambda::EventSourceMapping") if "ScalingConfig" in r["Properties"])
    assert source["FunctionResponseTypes"] == ["ReportBatchItemFailures"]
    assert source["ScalingConfig"]["MaximumConcurrency"] == 2
    assert resources(template, "AWS::Scheduler::Schedule")[0]["Properties"]["State"] == "DISABLED"
    assert len(resources(template, "AWS::CloudWatch::Alarm")) == 8
    for group in resources(template, "AWS::Logs::LogGroup"):
        assert group["Properties"]["RetentionInDays"] == 7
    assert len(resources(template, "AWS::Lambda::Function")) == 4


def test_no_broad_runtime_permissions_or_embedded_secrets(templates):
    for policy in resources(templates["core"], "AWS::IAM::Policy"):
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
            actions = statement["Action"]
            actions = [actions] if isinstance(actions, str) else actions
            assert not any("*" in action for action in actions)
            if statement["Resource"] == "*":
                assert actions == ["dynamodb:ListStreams"] and statement.get("Condition")
    assert not resources(templates["core"], "AWS::SecretsManager::Secret")
    functions = resources(templates["core"], "AWS::Lambda::Function")
    assert any("OPENAQ_SECRET_ARN" in fn["Properties"]["Environment"]["Variables"] for fn in functions)
    assert "AWS_SECRET_ACCESS_KEY" not in json.dumps(functions)


def test_location_is_explicit_and_scoped(tmp_path, templates):
    assert "geo-routes:CalculateRoutes" not in json.dumps(templates["core"])
    asset = tmp_path / "asset"
    asset.mkdir()
    (asset / "handler.py").write_text("# structural test")
    app = cdk.App(outdir=str(tmp_path / "assembly"))
    env = cdk.Environment(account="123456789012", region="ap-south-1")
    data = DataStack(app, "Data", env=env)
    core = CoreStack(app, "Core", data=data, asset_path=asset, env=env, enable_location=True)
    template = Template.from_stack(core).to_json()
    statements = [s for p in resources(template, "AWS::IAM::Policy")
                  for s in p["Properties"]["PolicyDocument"]["Statement"]]
    geo = [s for s in statements if "geo-" in json.dumps(s["Action"])]
    assert len(geo) == 2
    for s in geo:
        assert "ap-south-1::provider/default" in json.dumps(s["Resource"])
        assert "*" not in json.dumps(s)
    api = next(f["Properties"] for f in resources(template, "AWS::Lambda::Function")
               if f["Properties"]["Handler"] == "ecoroute.handlers.api.handler")
    assert api["Environment"]["Variables"]["ENABLE_AWS_LOCATION"] == "true"
    assert api["Timeout"] < 30

def test_google_secret_is_reference_only(templates):
    functions = resources(templates["core"], "AWS::Lambda::Function")
    envs = [f["Properties"].get("Environment", {}).get("Variables", {}) for f in functions]
    google = next(e for e in envs if e.get("ROUTING_PROVIDER") == "google")
    assert google["GOOGLE_ROUTES_SECRET_ARN"].endswith("google-AbCdEf")
    assert "GOOGLE_ROUTES_API_KEY" not in google
    policies = json.dumps(resources(templates["core"], "AWS::IAM::Policy"))
    assert "secretsmanager:GetSecretValue" in policies
    assert google["GOOGLE_ROUTES_SECRET_ARN"] in policies
