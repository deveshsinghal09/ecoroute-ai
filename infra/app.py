"""Offline synthesis; deployment is a separate, explicitly approved action."""
import os

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from stacks import CoreStack, DataStack, IotStack, MlStack
from analytics import AnalyticsStack
from compute import ComputeStack
from hosting import HostingStack
from profiles import DeploymentOptions, context_list
from concurrency import UnreservedLambda

app = cdk.App(outdir=os.environ.get("CDK_OUTDIR", "cdk.out"))
options = DeploymentOptions.load(os.environ.get("ECOROUTE_DEPLOY_CONFIG"))
region = os.environ.get("ECOROUTE_DEPLOY_REGION", "ap-south-1")
env = cdk.Environment(region=region, account=os.environ.get("EXPECTED_AWS_ACCOUNT_ID"))
data = DataStack(app, "EcoRouteData", env=env)
ml = MlStack(app, "EcoRouteML", env=env, data=data, asset_path="build/lambda",
             image_uri=app.node.try_get_context("ml_image_uri"))
core = CoreStack(app, "EcoRouteCore", data=data, asset_path="build/lambda", env=env,
          backend_origin=options.backend_origin,
          callback_urls=context_list(app.node.try_get_context("callback_urls")),
          frontend_origins=context_list(app.node.try_get_context("frontend_origins")),
          enable_location=str(app.node.try_get_context("enable_location")).lower() == "true",
          ml_inference_arn=ml.inference_arn,
          enable_workflows=str(app.node.try_get_context("enable_workflows")).lower() == "true",
          bedrock_model_arn=app.node.try_get_context("bedrock_model_arn"),
          sms_topic_arns=context_list(app.node.try_get_context("sms_topic_arns")),
          google_routes_secret_arn=app.node.try_get_context("google_routes_secret_arn"),
          cycling_secret_arn=app.node.try_get_context("cycling_secret_arn"),
          enable_guest_routes=str(app.node.try_get_context("enable_guest_routes")).lower() == "true",
          enable_self_signup=str(app.node.try_get_context("enable_self_signup")).lower() == "true",
          enable_route_weather=str(app.node.try_get_context("enable_route_weather")).lower() == "true",
          provider_secret_arn=app.node.try_get_context("provider_secret_arn"),
          gemini_secret_arn=app.node.try_get_context("gemini_secret_arn"),
          gemini_model_id=app.node.try_get_context("gemini_model_id"),
          ingestion_interval_minutes=int(app.node.try_get_context("ingestion_interval_minutes") or 60))
if str(app.node.try_get_context("enable_iot")).lower() == "true":
    IotStack(app, "EcoRouteIoT", env=env, data=data, asset_path="build/lambda")
if options.runtime != "lambda":
    ComputeStack(app, "EcoRouteCompute", env=env, core=core, options=options)
if options.hosting != "none":
    HostingStack(app, "EcoRouteHosting", env=env, options=options)
if options.analytics != "none":
    AnalyticsStack(app, "EcoRouteAnalytics", env=env, data=data, options=options, asset_path="build/lambda",
                   alert_topic=core.operational_alerts)
boundary_arn = app.node.try_get_context("workload_boundary_arn")
if boundary_arn:
    expected_boundary = f"arn:aws:iam::{os.environ.get('EXPECTED_AWS_ACCOUNT_ID')}:policy/EcoRouteWorkloadBoundary"
    if boundary_arn != expected_boundary:
        raise ValueError("Workload boundary must be the reviewed policy in the expected account")
    for child in app.node.children:
        if isinstance(child, cdk.Stack):
            boundary = iam.ManagedPolicy.from_managed_policy_arn(child, "DeploymentWorkloadBoundary", boundary_arn)
            iam.PermissionsBoundary.of(child).apply(boundary)
cdk.Tags.of(app).add("Project", "ecoroute-ai")
cdk.Tags.of(app).add("Environment", "hackathon")
if not options.lambda_reserved_concurrency:
    cdk.Aspects.of(app).add(UnreservedLambda())
app.synth()
