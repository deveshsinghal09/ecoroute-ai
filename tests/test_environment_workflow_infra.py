import json

import aws_cdk as cdk
from aws_cdk.assertions import Template

from infra.stacks import CoreStack, DataStack


def test_optional_workflow_is_inactive_scoped_and_has_failure_paths(tmp_path):
    asset = tmp_path / "asset"
    asset.mkdir()
    (asset / "handler.py").write_text("# fixture asset\n")
    app = cdk.App(outdir=str(tmp_path / "assembly"))
    env = cdk.Environment(account="123456789012", region="ap-south-1")
    data = DataStack(app, "Data", env=env)
    core = CoreStack(app, "Core", data=data, asset_path=asset, env=env, enable_workflows=True,
        bedrock_model_arn="arn:aws:bedrock:ap-south-1::foundation-model/reviewed-test-model",
        sms_topic_arns=["arn:aws:sns:ap-south-1:123456789012:private-alerts"])
    template = Template.from_stack(core).to_json()
    resources = list(template["Resources"].values())
    schedules = [r["Properties"] for r in resources if r["Type"] == "AWS::Scheduler::Schedule"]
    assert all(s["State"] == "DISABLED" for s in schedules) and len(schedules) == 2
    functions = [r["Properties"] for r in resources if r["Type"] == "AWS::Lambda::Function"]
    dispatcher = next(f for f in functions if f["Handler"].endswith("dispatch_handler"))
    assert dispatcher["Environment"]["Variables"]["ENABLE_ENVIRONMENT_WORKFLOW"] == "false"
    machine = next(r for r in resources if r["Type"] == "AWS::StepFunctions::StateMachine")
    text = json.dumps(machine)
    for stage in ("Ingestion", "Prediction", "Risk", "Alerts", "Notification", "CaptureFailure"):
        assert stage in text
    assert "Catch" in text and '"Retry"' not in text
    policy = json.dumps([r for r in resources if r["Type"] == "AWS::IAM::Policy"])
    assert "bedrock:InvokeModel" in policy and "sns:Publish" in policy
    assert "sns:*" not in policy and "bedrock:*" not in policy
    assert not any(r["Type"] in {"AWS::EC2::NatGateway", "AWS::SageMaker::Endpoint"} for r in resources)
