import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from infra.analytics import AnalyticsStack
from infra.compute import ComputeStack
from infra.hosting import HostingStack
from infra.profiles import DeploymentOptions
from infra.stacks import CoreStack, DataStack

IMAGE = "123456789012.dkr.ecr.ap-south-1.amazonaws.com/backend@sha256:" + "a" * 64
SECRET = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:writer-AbCdEf"
CERT = "arn:aws:acm:ap-south-1:123456789012:certificate/example"


@pytest.fixture(scope="module")
def templates(tmp_path_factory):
    work = tmp_path_factory.mktemp("optional")
    asset = work / "asset"
    asset.mkdir()
    (asset / "handler.py").write_text("# structural asset, not deployable\n")
    results = {}
    for runtime in ("ecs-fargate", "ec2", "eks", "apprunner", "lightsail-proxy"):
        app = cdk.App(outdir=str(work / runtime))
        env = cdk.Environment(account="123456789012", region="ap-south-1")
        data = DataStack(app, "Data", env=env)
        core = CoreStack(app, "Core", data=data, asset_path=asset, env=env)
        options = DeploymentOptions(runtime=runtime, image_uri=IMAGE if runtime != "lightsail-proxy" else "public.ecr.aws/example/proxy@sha256:" + "a" * 64,
            regional_certificate_arn=CERT, existing_apprunner_customer=True, eks_version="1.35",
            eks_operator_arn="arn:aws:iam::123456789012:role/operator", eks_admin_cidrs=["203.0.113.1/32"],
            api_gateway_origin="https://example.execute-api.ap-south-1.amazonaws.com")
        compute = ComputeStack(app, "Compute", core=core, options=options, env=env)
        results[runtime] = Template.from_stack(compute).to_json()
        app.synth()
    for hosting in ("cloudfront", "amplify"):
        app = cdk.App(outdir=str(work / hosting))
        stack = HostingStack(app, "Hosting", options=DeploymentOptions(hosting=hosting))
        results[hosting] = Template.from_stack(stack).to_json()
        app.synth()
    for engine in ("rds", "aurora"):
        app = cdk.App(outdir=str(work / engine))
        env = cdk.Environment(account="123456789012", region="ap-south-1")
        data = DataStack(app, "Data", env=env)
        stack = AnalyticsStack(app, "Analytics", data=data, options=DeploymentOptions(analytics=engine,
            sql_writer_secret_arn=SECRET, sql_image_uri=IMAGE), asset_path=str(asset), env=env)
        results[engine] = Template.from_stack(stack).to_json()
        app.synth()
    return results


def resources(template, kind):
    return [r for r in template["Resources"].values() if r["Type"] == kind]


def test_each_runtime_uses_existing_app_and_no_nat(templates):
    for runtime in ("ecs-fargate", "ec2", "eks", "apprunner"):
        text = json.dumps(templates[runtime])
        assert "COGNITO_USER_POOL_ID" in text and "WEARABLES_TABLE" in text
        assert "AWS::EC2::NatGateway" not in text
        assert "AWS::Cognito::UserPool" not in text and "AWS::DynamoDB::Table" not in text
    ecs = resources(templates["ecs-fargate"], "AWS::ECS::Service")[0]["Properties"]
    assert ecs["DesiredCount"] == 1
    assert "ExistingApiAccess" in json.dumps(templates["eks"])
    assert resources(templates["eks"], "AWS::EKS::PodIdentityAssociation")
    assert "UPSTREAM_API_ORIGIN" in json.dumps(templates["lightsail-proxy"])
    assert not resources(templates["lightsail-proxy"], "AWS::IAM::Role")


def test_private_hosting_and_manual_amplify(templates):
    cloud = templates["cloudfront"]
    bucket = resources(cloud, "AWS::S3::Bucket")[0]["Properties"]
    assert all(bucket["PublicAccessBlockConfiguration"].values())
    assert resources(cloud, "AWS::CloudFront::OriginAccessControl")
    assert "cloudfront.amazonaws.com" in json.dumps(cloud) and "AWS:SourceArn" in json.dumps(cloud)
    branch = resources(templates["amplify"], "AWS::Amplify::Branch")[0]["Properties"]
    assert branch["EnableAutoBuild"] is False


def test_sql_is_private_bounded_and_connected_to_existing_reports(templates):
    for engine in ("rds", "aurora"):
        text = json.dumps(templates[engine])
        assert "reports/routes/" in text and "ReportBatchItemFailures" in text
        assert "SQL_WRITER_SECRET_ARN" in text and SECRET in text
        assert "AWS::EC2::NatGateway" not in text
        assert "ProcessingFailures" in text and "DeletionProtection" in text
        resource = resources(templates[engine], "AWS::RDS::DBInstance")[0]["Properties"]
        assert resource["PubliclyAccessible"] is False
        if engine == "aurora":
            cluster = resources(templates[engine], "AWS::RDS::DBCluster")[0]["Properties"]
            assert cluster["EnableHttpEndpoint"] is True and cluster["StorageEncrypted"] is True
            assert cluster["ServerlessV2ScalingConfiguration"]["MaxCapacity"] == 1


def test_http_runtime_handoff_preserves_paths_jwt_and_scopes(tmp_path):
    asset = tmp_path / "asset"
    asset.mkdir()
    (asset / "handler.py").write_text("# structural only\n")
    app = cdk.App(outdir=str(tmp_path / "out"))
    env = cdk.Environment(account="123456789012", region="ap-south-1")
    data = DataStack(app, "Data", env=env)
    core = CoreStack(app, "Core", data=data, asset_path=asset, env=env, backend_origin="https://backend.example.org")
    template = Template.from_stack(core).to_json()
    integration = resources(template, "AWS::ApiGatewayV2::Integration")[0]["Properties"]
    assert integration["IntegrationType"] == "HTTP_PROXY"
    assert integration["RequestParameters"] == {"overwrite:path": "$request.path"}
    assert integration["IntegrationUri"] == "https://backend.example.org"
    assert integration["TimeoutInMillis"] == 28000
    for route in resources(template, "AWS::ApiGatewayV2::Route"):
        props = route["Properties"]
        if "proxy+" in props["RouteKey"]:
            assert props["AuthorizationType"] == "JWT" and props["AuthorizationScopes"]
    app.synth()
