"""Offline synthesis; deployment is a separate, explicitly approved action."""
import os

import aws_cdk as cdk
from stacks import CoreStack, DataStack, IotStack, MlStack

app = cdk.App(outdir="cdk.out")
region = os.environ.get("ECOROUTE_DEPLOY_REGION", "ap-south-1")
env = cdk.Environment(region=region, account=os.environ.get("EXPECTED_AWS_ACCOUNT_ID"))
data = DataStack(app, "EcoRouteData", env=env)
ml = MlStack(app, "EcoRouteML", env=env, data=data, asset_path="build/lambda",
             image_uri=app.node.try_get_context("ml_image_uri"))
CoreStack(app, "EcoRouteCore", data=data, asset_path="build/lambda", env=env,
          callback_urls=app.node.try_get_context("callback_urls"),
          frontend_origins=app.node.try_get_context("frontend_origins"),
          enable_location=str(app.node.try_get_context("enable_location")).lower() == "true",
          ml_inference_arn=ml.inference_arn,
          enable_workflows=str(app.node.try_get_context("enable_workflows")).lower() == "true",
          bedrock_model_arn=app.node.try_get_context("bedrock_model_arn"),
          sms_topic_arns=app.node.try_get_context("sms_topic_arns"),
          provider_secret_arn=app.node.try_get_context("provider_secret_arn"),
          ingestion_interval_minutes=int(app.node.try_get_context("ingestion_interval_minutes") or 60))
if str(app.node.try_get_context("enable_iot")).lower() == "true":
    IotStack(app, "EcoRouteIoT", env=env, data=data, asset_path="build/lambda")
cdk.Tags.of(app).add("Project", "ecoroute-ai")
cdk.Tags.of(app).add("Environment", "hackathon")
app.synth()
