"""Optional, inactive environmental orchestration; no NAT or idle compute."""
import json

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct


class EnvironmentalWorkflow(Construct):
    def __init__(self, scope, name, *, data, code, environment, sms_topic_arns=None):
        super().__init__(scope, name)
        stack = Stack.of(self)
        group = logs.LogGroup(self, "Logs", retention=logs.RetentionDays.ONE_WEEK, removal_policy=RemovalPolicy.DESTROY)
        role = iam.Role(self, "WorkerRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        role.add_to_policy(iam.PolicyStatement(actions=["logs:CreateLogStream", "logs:PutLogEvents"], resources=[group.log_group_arn]))
        role.add_to_policy(iam.PolicyStatement(actions=["s3:GetObject", "s3:PutObject"],
            resources=[data.bucket.arn_for_objects("raw/*"), data.bucket.arn_for_objects("curated/*")]))
        role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"],
            resources=[data.tables[k].table_arn for k in ("environment", "alerts", "preferences")]))
        if environment.get("ML_INFERENCE_FUNCTION_ARN"):
            role.add_to_policy(iam.PolicyStatement(actions=["lambda:InvokeFunction"], resources=[environment["ML_INFERENCE_FUNCTION_ARN"]]))
        if sms_topic_arns:
            role.add_to_policy(iam.PolicyStatement(actions=["sns:Publish", "sns:ListSubscriptionsByTopic"], resources=sms_topic_arns))
            role.add_to_policy(iam.PolicyStatement(actions=["sns:GetSMSSandboxAccountStatus", "sns:ListSMSSandboxPhoneNumbers", "sns:GetSMSAttributes"], resources=["*"], conditions={"StringEquals": {"aws:RequestedRegion": stack.region}}))
        worker = lambda_.Function(self, "Stage", code=code, runtime=lambda_.Runtime.PYTHON_3_11,
            handler="ecoroute.advisory.workflows.stage_handler", role=role,
            environment={**environment, "ENABLE_SMS": "false", "ENABLE_BEDROCK": "false", "SNS_ALLOWED_TOPIC_ARNS": json.dumps(sms_topic_arns or [])},
            timeout=Duration.seconds(180), memory_size=512, reserved_concurrent_executions=1, log_group=group)
        self.dlq = sqs.Queue(self, "Failures", encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True, retention_period=Duration.days(7))
        self.queue = sqs.Queue(self, "Jobs", encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True, retention_period=Duration.days(1), visibility_timeout=Duration.seconds(180),
            dead_letter_queue=sqs.DeadLetterQueue(queue=self.dlq, max_receive_count=2))
        failed = sfn.Fail(self, "Failed", cause="environment_workflow_failed")
        capture = tasks.SqsSendMessage(self, "CaptureFailure", queue=self.dlq,
            message_body=sfn.TaskInput.from_object({"error": "workflow_failed", "job": sfn.JsonPath.object_at("$.job")})).next(failed)
        stages = []
        for stage in ("ingestion", "prediction", "risk", "alerts", "notification"):
            task = tasks.LambdaInvoke(self, stage.title(), lambda_function=worker,
                payload=sfn.TaskInput.from_object({"stage": stage, "job": sfn.JsonPath.object_at("$.job")}),
                result_path=sfn.JsonPath.DISCARD, retry_on_service_exceptions=False)
            task.add_catch(capture, errors=["States.ALL"], result_path="$.failure")
            stages.append(task)
        chain = stages[0]
        for task in stages[1:]:
            chain = chain.next(task)
        self.machine = sfn.StateMachine(self, "Machine", definition_body=sfn.DefinitionBody.from_chainable(chain),
            state_machine_name=f"EcoRoute-{Stack.of(self).stack_name}-EnvironmentalWorkflow",
            timeout=Duration.minutes(12), tracing_enabled=False)
        dispatch_group = logs.LogGroup(self, "DispatchLogs", retention=logs.RetentionDays.ONE_WEEK, removal_policy=RemovalPolicy.DESTROY)
        dispatcher = lambda_.Function(self, "Dispatch", code=code, runtime=lambda_.Runtime.PYTHON_3_11,
            handler="ecoroute.advisory.workflows.dispatch_handler", timeout=Duration.seconds(25), memory_size=128,
            reserved_concurrent_executions=2, log_group=dispatch_group,
            environment={"WORKFLOW_STATE_MACHINE_ARN": self.machine.state_machine_arn, "ENABLE_ENVIRONMENT_WORKFLOW": "false"})
        self.machine.grant_start_execution(dispatcher)
        dispatcher.add_event_source(sources.SqsEventSource(self.queue, batch_size=1, max_concurrency=2, report_batch_item_failures=True))
        schedule_role = iam.Role(self, "ScheduleRole", assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com",
            conditions={"StringEquals": {"aws:SourceAccount": stack.account}, "ArnEquals": {
                "aws:SourceArn": stack.format_arn(service="scheduler", resource="schedule-group", resource_name="default")}}))
        self.queue.grant_send_messages(schedule_role)
        scheduler.CfnSchedule(self, "DailyForecast", state="DISABLED", schedule_expression="cron(0 18 * * ? *)",
            schedule_expression_timezone="Asia/Kolkata", flexible_time_window={"mode": "OFF"},
            target=scheduler.CfnSchedule.TargetProperty(arn=self.queue.queue_arn, role_arn=schedule_role.role_arn,
                input=json.dumps({"daily_template": {"owner": "CONFIGURE_COGNITO_SUB", "position": {"latitude": 28.6139, "longitude": 77.209},
                    "location_id": "cams_global:28.8000:77.2000", "notify": False, "station_ids": []}}),
                retry_policy={"maximum_retry_attempts": 0, "maximum_event_age_in_seconds": 3600}))
        cw.Alarm(self, "FailedRuns", metric=self.machine.metric_failed(), threshold=1, evaluation_periods=1)
        cw.Alarm(self, "StageErrors", metric=worker.metric_errors(), threshold=1, evaluation_periods=1)
        cw.Alarm(self, "QueuedFailures", metric=self.dlq.metric_approximate_number_of_messages_visible(), threshold=1, evaluation_periods=1)
        cw.Alarm(self, "AlertVolume", metric=cw.Metric(namespace="EcoRoute/Environment", metric_name="AlertCount", statistic="Sum"), threshold=10, evaluation_periods=1)
