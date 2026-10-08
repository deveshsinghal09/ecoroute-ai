"""Offline synthesis; deployment is a separate, explicitly approved action."""
import os

import aws_cdk as cdk
from stacks import CoreStack, DataStack, IotStack, MlStack

app = cdk.App(outdir="cdk.out")
region = os.environ.get("ECOROUTE_DEPLOY_REGION", "ap-south-1")
env = cdk.Environment(region=region, account=os.environ.get("EXPECTED_AWS_ACCOUNT_ID"))
data = DataStack(app, "EcoRouteData", env=env)
MlStack(app, "EcoRouteML", env=env)
CoreStack(app, "EcoRouteCore", data=data, asset_path="build/lambda", env=env,
          callback_urls=app.node.try_get_context("callback_urls"),
          provider_secret_arn=app.node.try_get_context("provider_secret_arn"))
if app.node.try_get_context("enable_iot") is True:
    IotStack(app, "EcoRouteIoT", env=env)
cdk.Tags.of(app).add("Project", "ecoroute-ai")
cdk.Tags.of(app).add("Environment", "hackathon")
app.synth()
