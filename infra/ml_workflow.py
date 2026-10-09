"""Optional reviewed ML resources. Defines jobs/workflow; never starts training at deployment."""

import json
import re

from aws_cdk import ArnFormat, CfnOutput, Duration, RemovalPolicy
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_stepfunctions as sfn
from constructs import Construct


class MlWorkflow(Construct):
    def __init__(self, scope, name, *, bucket, data, asset_path, image_uri):
        super().__init__(scope, name)
        stack = scope
        match = re.fullmatch(
            r"([0-9]{12})\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com/([a-z0-9/_-]+)@sha256:[a-f0-9]{64}",
            image_uri,
        )
        if not match or match[2] != stack.region:
            raise ValueError("ML image must be a digest-pinned regional ECR image")
        training = iam.Role(
            self,
            "TrainingRole",
            assumed_by=iam.ServicePrincipal(
                "sagemaker.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": stack.account},
                    "ArnLike": {
                        "aws:SourceArn": stack.format_arn(
                            service="sagemaker", resource="training-job", resource_name="ecoroute-*"
                        )
                    },
                },
            ),
        )
        training.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"], resources=[bucket.arn_for_objects("datasets/*")]
            )
        )
        training.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket"],
                resources=[bucket.bucket_arn],
                conditions={"StringLike": {"s3:prefix": ["datasets/*"]}},
            )
        )
        training.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:PutObject"], resources=[bucket.arn_for_objects("models/training/*")]
            )
        )
        training.add_to_policy(
            iam.PolicyStatement(
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
                conditions={"StringEquals": {"aws:RequestedRegion": stack.region}},
            )
        )
        repo_arn = f"arn:aws:ecr:{match[2]}:{match[1]}:repository/{match[3]}"
        training.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchCheckLayerAvailability",
                ],
                resources=[repo_arn],
            )
        )
        training.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    stack.format_arn(
                        service="logs",
                        resource="log-group",
                        resource_name="/aws/sagemaker/TrainingJobs:*",
                        arn_format=ArnFormat.COLON_RESOURCE_NAME,
                    )
                ],
            )
        )
        log = logs.LogGroup(
            self,
            "WorkflowHandlerLogs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        worker_role = iam.Role(
            self, "WorkflowHandlerRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )
        worker_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[log.log_group_arn + ":*"],
            )
        )
        worker_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[
                    bucket.arn_for_objects("datasets/*"),
                    bucket.arn_for_objects("models/training/*"),
                ],
            )
        )
        worker_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:PutObject"], resources=[bucket.arn_for_objects("models/registry/*")]
            )
        )
        jobs = stack.format_arn(
            service="sagemaker", resource="training-job", resource_name="ecoroute-*"
        )
        worker_role.add_to_policy(
            iam.PolicyStatement(actions=["sagemaker:DescribeTrainingJob"], resources=[jobs])
        )
        machine_name = "ecoroute-pm25-training"
        machine_arn = stack.format_arn(
            service="states",
            resource="stateMachine",
            resource_name=machine_name,
            arn_format=ArnFormat.COLON_RESOURCE_NAME,
        )
        worker_role.add_to_policy(
            iam.PolicyStatement(actions=["states:StartExecution"], resources=[machine_arn])
        )
        worker = lam.Function(
            self,
            "WorkflowHandler",
            runtime=lam.Runtime.PYTHON_3_11,
            code=lam.Code.from_asset(asset_path),
            handler="ecoroute.ml.workflow.handler",
            role=worker_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            reserved_concurrent_executions=1,
            log_group=log,
            environment={
                "ML_BUCKET": bucket.bucket_name,
                "ML_TRAINING_ROLE": training.role_arn,
                "ML_IMAGE_URI": image_uri,
                "ML_STATE_MACHINE_ARN": machine_arn,
                "ML_SCHEDULE_APPROVED": "false",
            },
        )
        machine_role = iam.Role(
            self, "WorkflowRole", assumed_by=iam.ServicePrincipal("states.amazonaws.com")
        )
        worker.grant_invoke(machine_role)
        machine_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:CreateTrainingJob",
                    "sagemaker:DescribeTrainingJob",
                    "sagemaker:StopTrainingJob",
                    "sagemaker:AddTags",
                    "sagemaker:ListTags",
                ],
                resources=[jobs],
            )
        )
        machine_role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[training.role_arn],
                conditions={"StringEquals": {"iam:PassedToService": "sagemaker.amazonaws.com"}},
            )
        )
        rule_arn = stack.format_arn(
            service="events",
            resource="rule",
            resource_name="StepFunctionsGetEventsForSageMakerTrainingJobsRule",
        )
        machine_role.add_to_policy(
            iam.PolicyStatement(
                actions=["events:PutTargets", "events:PutRule", "events:DescribeRule"],
                resources=[rule_arn],
            )
        )
        parameters = {
            key + ".$": "$.approved." + key
            for key in (
                "TrainingJobName",
                "RoleArn",
                "AlgorithmSpecification",
                "InputDataConfig",
                "OutputDataConfig",
                "ResourceConfig",
                "StoppingCondition",
                "EnableNetworkIsolation",
                "EnableInterContainerTrafficEncryption",
                "EnableManagedSpotTraining",
                "ProfilerConfig",
                "Tags",
            )
        }
        definition = {
            "StartAt": "ValidateDataset",
            "TimeoutSeconds": 3600,
            "States": {
                "ValidateDataset": {
                    "Type": "Task",
                    "Resource": worker.function_arn,
                    "Parameters": {
                        "operation": "validate",
                        "dataset_version.$": "$.dataset_version",
                        "job_name.$": "$.job_name",
                    },
                    "ResultPath": "$.approved",
                    "Next": "Train",
                    "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "Failed"}],
                },
                "Train": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::sagemaker:createTrainingJob.sync",
                    "Parameters": parameters,
                    "ResultPath": "$.training",
                    "Next": "VerifyAndPublish",
                    "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "Failed"}],
                },
                "VerifyAndPublish": {
                    "Type": "Task",
                    "Resource": worker.function_arn,
                    "Parameters": {"operation": "publish", "job_name.$": "$.job_name"},
                    "End": True,
                    "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "Failed"}],
                },
                "Failed": {
                    "Type": "Fail",
                    "Error": "MLWorkflowFailed",
                    "Cause": "Dataset, training or model gate failed; no automatic paid retry",
                },
            },
        }
        self.machine = sfn.CfnStateMachine(
            self,
            "TrainingWorkflow",
            state_machine_name=machine_name,
            role_arn=machine_role.role_arn,
            definition_string=json.dumps(definition),
        )
        schedule_role = iam.Role(
            self,
            "ScheduleRole",
            assumed_by=iam.ServicePrincipal(
                "scheduler.amazonaws.com",
                conditions={"StringEquals": {"aws:SourceAccount": stack.account}},
            ),
        )
        worker.grant_invoke(schedule_role)
        scheduler.CfnSchedule(
            self,
            "RetrainingSchedule",
            state="DISABLED",
            schedule_expression="rate(7 days)",
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(mode="OFF"),
            target=scheduler.CfnSchedule.TargetProperty(
                arn=worker.function_arn,
                role_arn=schedule_role.role_arn,
                input=json.dumps({"operation": "scheduled"}),
                retry_policy=scheduler.CfnSchedule.RetryPolicyProperty(maximum_retry_attempts=0),
            ),
        )
        self.inference = lam.CfnFunction(
            self,
            "OnDemandInference",
            package_type="Image",
            role=worker_role.role_arn,
            code=lam.CfnFunction.CodeProperty(image_uri=image_uri),
            timeout=20,
            memory_size=1024,
            reserved_concurrent_executions=1,
            image_config=lam.CfnFunction.ImageConfigProperty(
                entry_point=["python", "-m", "awslambdaric"], command=["ecoroute.ml.cloud.handler"]
            ),
            environment=lam.CfnFunction.EnvironmentProperty(
                variables={
                    "ECOROUTE_PROFILE": "aws",
                    "ML_BUCKET": bucket.bucket_name,
                    "S3_DATA_BUCKET": data.bucket.bucket_name,
                    "ENVIRONMENT_TABLE": data.tables["environment"].table_name,
                }
            ),
            logging_config=lam.CfnFunction.LoggingConfigProperty(log_group=log.log_group_name),
        )
        # Separate read-only inference role; never reuse training/workflow permissions.
        inference_role = iam.Role(
            self, "InferenceRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )
        inference_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[log.log_group_arn + ":*"],
            )
        )
        inference_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[
                    bucket.arn_for_objects("models/registry/*"),
                    data.bucket.arn_for_objects("curated/*"),
                ],
            )
        )
        inference_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket"],
                resources=[bucket.bucket_arn],
                conditions={"StringLike": {"s3:prefix": ["models/registry/*"]}},
            )
        )
        inference_role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Query"], resources=[data.tables["environment"].table_arn]
            )
        )
        self.inference.role = inference_role.role_arn
        cw.Alarm(
            self, "MlWorkerErrors", metric=worker.metric_errors(), threshold=1, evaluation_periods=1
        )
        cw.Alarm(
            self,
            "MlWorkflowFailed",
            metric=cw.Metric(
                namespace="AWS/States",
                metric_name="ExecutionsFailed",
                dimensions_map={"StateMachineArn": self.machine.attr_arn},
                statistic="Sum",
            ),
            threshold=1,
            evaluation_periods=1,
        )
        CfnOutput(scope, "TrainingRoleArn", value=training.role_arn)
        CfnOutput(scope, "MlWorkflowArn", value=self.machine.attr_arn)
        CfnOutput(scope, "MlInferenceFunctionArn", value=self.inference.attr_arn)
