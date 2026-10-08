from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_authorizers as authorizers
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as alarm_actions
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_iot as iot
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_secretsmanager as secrets
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from constructs import Construct


def bucket(scope, name, rules):
    return s3.Bucket(scope, name, encryption=s3.BucketEncryption.S3_MANAGED,
                     block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                     enforce_ssl=True, minimum_tls_version=1.2,
                     object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
                     versioned=False, removal_policy=RemovalPolicy.RETAIN,
                     lifecycle_rules=[s3.LifecycleRule(id=prefix.replace("/", ""), prefix=prefix,
                                                       expiration=Duration.days(days),
                                                       abort_incomplete_multipart_upload_after=Duration.days(1))
                                      for prefix, days in rules])


class DataStack(Stack):
    def __init__(self, scope: Construct, name: str, **kwargs):
        super().__init__(scope, name, **kwargs)
        self.tables = {}
        for table_name in ("journeys", "preferences", "route_metadata", "idempotency", "alerts"):
            table = dynamodb.Table(
                self, table_name, partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
                sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                encryption=dynamodb.TableEncryption.AWS_MANAGED,
                time_to_live_attribute="expires_at", deletion_protection=True,
                removal_policy=RemovalPolicy.RETAIN,
                max_read_request_units=10, max_write_request_units=10,
            )
            self.tables[table_name] = table
            CfnOutput(self, table_name + "Table", value=table.table_name)
        self.bucket = bucket(self, "AirData", [("raw/", 30), ("cleaned/", 90), ("reports/", 30)])
        CfnOutput(self, "DataBucket", value=self.bucket.bucket_name)


class MlStack(Stack):
    def __init__(self, scope, name, **kwargs):
        super().__init__(scope, name, **kwargs)
        self.bucket = bucket(self, "MlArtifacts", [("datasets/", 90), ("models/", 180)])
        CfnOutput(self, "MlBucket", value=self.bucket.bucket_name)
        # No training instances, endpoint, Studio domain or model invoke privileges.


class CoreStack(Stack):
    def __init__(self, scope, name, *, data, asset_path, callback_urls=None,
                 provider_secret_arn=None, **kwargs):
        super().__init__(scope, name, **kwargs)
        api_logs = logs.LogGroup(self, "ApiLogs", retention=logs.RetentionDays.ONE_WEEK,
                                 removal_policy=RemovalPolicy.DESTROY)
        worker_logs = logs.LogGroup(self, "WorkerLogs", retention=logs.RetentionDays.ONE_WEEK,
                                    removal_policy=RemovalPolicy.DESTROY)
        access_logs = logs.LogGroup(self, "AccessLogs", retention=logs.RetentionDays.ONE_WEEK,
                                    removal_policy=RemovalPolicy.DESTROY)
        api_role = iam.Role(self, "ApiRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        worker_role = iam.Role(self, "WorkerRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        for role, group in ((api_role, api_logs), (worker_role, worker_logs)):
            role.add_to_policy(iam.PolicyStatement(actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                                                   resources=[group.log_group_arn]))
        self.pool = cognito.UserPool(
            self, "Users", self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(otp=True, sms=False),
            password_policy=cognito.PasswordPolicy(min_length=14, require_digits=True,
                require_lowercase=True, require_uppercase=True, require_symbols=True),
            removal_policy=RemovalPolicy.RETAIN, deletion_protection=True,
        )
        read = cognito.ResourceServerScope(scope_name="read", scope_description="Read own EcoRoute data")
        write = cognito.ResourceServerScope(scope_name="write", scope_description="Write own EcoRoute data")
        server = self.pool.add_resource_server("Scopes", identifier="ecoroute", scopes=[read, write])
        client_args = {}
        if callback_urls:
            client_args["o_auth"] = cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True), callback_urls=callback_urls,
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.resource_server(server, read),
                        cognito.OAuthScope.resource_server(server, write)],
            )
        else:
            client_args["disable_o_auth"] = True
        self.client = self.pool.add_client("PublicClient", generate_secret=False,
            prevent_user_existence_errors=True, access_token_validity=Duration.minutes(15),
            id_token_validity=Duration.minutes(15), refresh_token_validity=Duration.days(1),
            auth_flows=cognito.AuthFlow(user_srp=True), **client_args)
        # Domain avoids a globally unique user-selected prefix and enables future PKCE login.
        self.pool.add_domain("Domain", cognito_domain=cognito.CognitoDomainOptions(
            domain_prefix=f"ecoroute-{self.account}-{self.region}"))
        table_vars = {"JOURNEYS_TABLE": "journeys", "PREFERENCES_TABLE": "preferences",
                      "ROUTE_METADATA_TABLE": "route_metadata", "IDEMPOTENCY_TABLE": "idempotency",
                      "ALERTS_TABLE": "alerts"}
        environment = {"ECOROUTE_PROFILE": "aws", "COGNITO_USER_POOL_ID": self.pool.user_pool_id,
                       "COGNITO_CLIENT_ID": self.client.user_pool_client_id,
                       **{env: data.tables[key].table_name for env, key in table_vars.items()}}
        # Runtime only uses get/put and transactional puts; DynamoDB authorizes transactions via PutItem.
        api_role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:GetItem", "dynamodb:PutItem"],
            resources=[data.tables[k].table_arn for k in ("journeys", "preferences", "idempotency")]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:GetItem"],
                                                  resources=[data.tables["alerts"].table_arn]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:DescribeTable"],
                                                  resources=[t.table_arn for t in data.tables.values()]))
        code = lambda_.Code.from_asset(str(Path(asset_path).resolve()))
        self.api_function = lambda_.Function(self, "Api", runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.X86_64, handler="ecoroute.handlers.api.handler",
            code=code, role=api_role, environment=environment, timeout=Duration.seconds(20),
            memory_size=512, reserved_concurrent_executions=3, log_group=api_logs)
        self.dlq = sqs.Queue(self, "DeadLetters", encryption=sqs.QueueEncryption.SQS_MANAGED,
                             enforce_ssl=True, retention_period=Duration.days(14))
        self.queue = sqs.Queue(self, "Tasks", encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True, retention_period=Duration.days(4), visibility_timeout=Duration.seconds(180),
            dead_letter_queue=sqs.DeadLetterQueue(queue=self.dlq, max_receive_count=3))
        worker_role.add_to_policy(iam.PolicyStatement(actions=["s3:PutObject"],
                                                       resources=[data.bucket.arn_for_objects("reports/ingestion/*")]))
        worker_env = {"S3_DATA_BUCKET": data.bucket.bucket_name}
        if provider_secret_arn:
            imported = secrets.Secret.from_secret_complete_arn(self, "ProviderSecret", provider_secret_arn)
            worker_env["POLLUTION_SECRET_ARN"] = imported.secret_arn
            # Reference only: no secret read grant until ingestion implementation actually uses it.
        worker = lambda_.Function(self, "Worker", runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.X86_64, handler="ecoroute.handlers.tasks.handler",
            code=code, role=worker_role, environment=worker_env, timeout=Duration.seconds(30),
            memory_size=256, reserved_concurrent_executions=2, log_group=worker_logs)
        worker.add_event_source(sources.SqsEventSource(self.queue, batch_size=5,
                                                       report_batch_item_failures=True, max_concurrency=2))
        schedule_role = iam.Role(self, "ScheduleRole", assumed_by=iam.ServicePrincipal(
            "scheduler.amazonaws.com", conditions={"StringEquals": {"aws:SourceAccount": self.account},
                "ArnEquals": {"aws:SourceArn": self.format_arn(service="scheduler", resource="schedule-group",
                                                               resource_name="default")}}))
        self.queue.grant_send_messages(schedule_role)
        scheduler.CfnSchedule(self, "IngestionSchedule", state="DISABLED",
            schedule_expression="rate(1 hour)", flexible_time_window={"mode": "OFF"},
            target=scheduler.CfnSchedule.TargetProperty(
                arn=self.queue.queue_arn, role_arn=schedule_role.role_arn,
                input='{"type":"ingestion_tick","event_id":"<aws.scheduler.execution-id>"}',
                retry_policy={"maximum_event_age_in_seconds": 3600, "maximum_retry_attempts": 2}))
        issuer = f"https://cognito-idp.{self.region}.amazonaws.com/{self.pool.user_pool_id}"
        authorizer = authorizers.HttpJwtAuthorizer("Cognito", issuer,
                                                   jwt_audience=[self.client.user_pool_client_id])
        api = apigw.HttpApi(self, "HttpApi", create_default_stage=False,
                            default_authorizer=authorizer, default_authorization_scopes=["ecoroute/read"])
        integration = integrations.HttpLambdaIntegration("FastApi", self.api_function)
        for path in ("/api/v1/health", "/healthz", "/docs", "/openapi.json"):
            api.add_routes(path=path, methods=[apigw.HttpMethod.GET], integration=integration,
                           authorizer=apigw.HttpNoneAuthorizer())
        # Ready is protected in AWS to avoid public paid dependency probes.
        api.add_routes(path="/api/v1/{proxy+}", methods=[apigw.HttpMethod.GET], integration=integration,
                       authorization_scopes=["ecoroute/read"])
        api.add_routes(path="/api/v1/{proxy+}", methods=[apigw.HttpMethod.POST, apigw.HttpMethod.PUT],
                       integration=integration, authorization_scopes=["ecoroute/write"])
        apigw.CfnStage(self, "Stage", api_id=api.api_id, stage_name="$default", auto_deploy=True,
            default_route_settings=apigw.CfnStage.RouteSettingsProperty(
                throttling_rate_limit=2, throttling_burst_limit=5),
            access_log_settings=apigw.CfnStage.AccessLogSettingsProperty(destination_arn=access_logs.log_group_arn,
                format=(
                    '{"requestId":"$context.requestId","route":"$context.routeKey",'
                    '"status":"$context.status","latency":"$context.responseLatency"}')))
        topic = sns.Topic(self, "OperationalAlerts", enforce_ssl=True)
        alarm_list = [
            cloudwatch.Alarm(self, "ApiErrors", metric=self.api_function.metric_errors(),
                             threshold=1, evaluation_periods=1),
            cloudwatch.Alarm(self, "ApiDuration", metric=self.api_function.metric_duration(statistic="p95"),
                             threshold=10000, evaluation_periods=2),
            cloudwatch.Alarm(self, "WorkerErrors", metric=worker.metric_errors(), threshold=1, evaluation_periods=1),
            cloudwatch.Alarm(self, "DeadLettersAlarm", metric=self.dlq.metric_approximate_number_of_messages_visible(),
                             threshold=1, evaluation_periods=1),
            cloudwatch.Alarm(self, "Http5xx", metric=cloudwatch.Metric(namespace="AWS/ApiGateway",
                metric_name="5xx", dimensions_map={"ApiId": api.api_id}, statistic="Sum"),
                threshold=1, evaluation_periods=1),
        ]
        for alarm in alarm_list:
            alarm.add_alarm_action(alarm_actions.SnsAction(topic))
        CfnOutput(self, "ApiUrl", value=api.api_endpoint)
        CfnOutput(self, "UserPoolId", value=self.pool.user_pool_id)
        CfnOutput(self, "ClientId", value=self.client.user_pool_client_id)
        CfnOutput(self, "QueueUrl", value=self.queue.queue_url)
        CfnOutput(self, "OperationalAlertsTopic", value=topic.topic_arn)


class IotStack(Stack):
    """Optional device identity boundary. No private key/certificate is created or embedded."""
    def __init__(self, scope, name, **kwargs):
        super().__init__(scope, name, **kwargs)
        thing = iot.CfnThing(self, "DemoGateway", thing_name="ecoroute-demo-gateway")
        iot.CfnPolicy(self, "DevicePolicy", policy_document={
            "Version": "2012-10-17", "Statement": [
                {"Effect": "Allow", "Action": "iot:Connect", "Resource": self.format_arn(
                    service="iot", resource="client", resource_name=thing.ref)},
                {"Effect": "Allow", "Action": "iot:Publish", "Resource": self.format_arn(
                    service="iot", resource="topic", resource_name=f"ecoroute/{thing.ref}/telemetry")},
            ]})
        CfnOutput(self, "Status", value="Certificate enrollment and telemetry rule deliberately not configured")
