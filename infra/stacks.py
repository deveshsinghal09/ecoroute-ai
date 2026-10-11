from pathlib import Path
import json
from urllib.parse import urlsplit

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_authorizers as authorizers
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as alarm_actions
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from aws_cdk import aws_iot as iot
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_lambda_destinations as destinations
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications as s3_notifications
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
        for table_name in ("journeys", "preferences", "route_metadata", "idempotency", "alerts", "environment", "wearables"):
            table = dynamodb.Table(
                self, table_name, partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
                sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                encryption=dynamodb.TableEncryption.AWS_MANAGED,
                time_to_live_attribute="expires_at", deletion_protection=True,
                removal_policy=RemovalPolicy.RETAIN,
                max_read_request_units=10, max_write_request_units=10,
                stream=dynamodb.StreamViewType.NEW_IMAGE if table_name == "wearables" else None,
            )
            self.tables[table_name] = table
            CfnOutput(self, table_name + "Table", value=table.table_name)
        self.bucket = bucket(self, "AirData", [("raw/", 30), ("curated/", 90), ("reports/", 30), ("reports/routes/", 7), ("routes/", 7), ("wearables/", 7)])
        self.dlq = sqs.Queue(self, "DeadLetters", encryption=sqs.QueueEncryption.SQS_MANAGED,
                             enforce_ssl=True, retention_period=Duration.days(14))
        self.queue = sqs.Queue(self, "Tasks", encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True, retention_period=Duration.days(4), visibility_timeout=Duration.seconds(180),
            dead_letter_queue=sqs.DeadLetterQueue(queue=self.dlq, max_receive_count=3))
        # S3 raw-object events feed the existing cleaning queue; no raw response is sent through SQS.
        self.bucket.add_event_notification(s3.EventType.OBJECT_CREATED,
            s3_notifications.SqsDestination(self.queue), s3.NotificationKeyFilter(prefix="raw/source="))
        CfnOutput(self, "DataBucket", value=self.bucket.bucket_name)


class MlStack(Stack):
    def __init__(self, scope, name, *, data=None, asset_path=None, image_uri=None, **kwargs):
        super().__init__(scope, name, **kwargs)
        self.bucket = bucket(self, "MlArtifacts", [("datasets/", 90), ("models/", 180)])
        CfnOutput(self, "MlBucket", value=self.bucket.bucket_name)
        self.training_repository = ecr.Repository(self, "TrainingImages",
            repository_name="ecoroute-ai-ml-training", image_tag_mutability=ecr.TagMutability.IMMUTABLE,
            image_scan_on_push=True, removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=5)])
        CfnOutput(self, "TrainingImageRepositoryUri", value=self.training_repository.repository_uri)
        self.inference_arn = None
        if image_uri:
            if data is None or not asset_path:
                raise ValueError("ML workflow requires existing Data stack and packaged handlers")
            if __package__ == "infra":
                from .ml_workflow import MlWorkflow
            else:
                from ml_workflow import MlWorkflow
            workflow = MlWorkflow(self, "ML", bucket=self.bucket, data=data, asset_path=asset_path, image_uri=image_uri)
            self.inference_arn = workflow.inference.attr_arn
        else:
            if __package__ == "infra":
                from .ml_roles import training_role
            else:
                from ml_roles import training_role
            role = training_role(self, "TrainingRole", self.bucket, self.training_repository.repository_arn)
            CfnOutput(self, "TrainingRoleArn", value=role.role_arn)
            CfnOutput(self, "TrainingStatus", value="Execution role and ECR repository only; image, measured dataset, quota and paid-job approval still required")


class CoreStack(Stack):
    def __init__(self, scope, name, *, data, asset_path, callback_urls=None, frontend_origins=None,
                 google_routes_secret_arn=None, cycling_secret_arn=None, enable_guest_routes=False, enable_self_signup=False, enable_route_weather=False, provider_secret_arn=None, gemini_secret_arn=None, gemini_model_id=None, ingestion_interval_minutes=60, enable_location=False, ml_inference_arn=None, enable_workflows=False, bedrock_model_arn=None, sms_topic_arns=None, backend_origin=None, **kwargs):
        super().__init__(scope, name, **kwargs)
        frontend_origins = frontend_origins or []
        if not isinstance(frontend_origins, list):
            raise ValueError("frontend_origins must be a list of exact HTTPS origins")
        for origin in frontend_origins:
            parsed = urlsplit(origin)
            if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or "*" in origin:
                raise ValueError("frontend_origins must contain exact HTTPS origins without paths")
        if not 60 <= ingestion_interval_minutes <= 1440:
            raise ValueError("Collection interval must be 60..1440 minutes")
        api_logs = logs.LogGroup(self, "ApiLogs", retention=logs.RetentionDays.ONE_WEEK,
                                 removal_policy=RemovalPolicy.DESTROY)
        worker_logs = logs.LogGroup(self, "WorkerLogs", retention=logs.RetentionDays.ONE_WEEK,
                                    removal_policy=RemovalPolicy.DESTROY)
        access_logs = logs.LogGroup(self, "AccessLogs", retention=logs.RetentionDays.ONE_WEEK,
                                    removal_policy=RemovalPolicy.DESTROY)
        ingest_logs = logs.LogGroup(self, "IngestionLogs", retention=logs.RetentionDays.ONE_WEEK,
                                    removal_policy=RemovalPolicy.DESTROY)
        api_role = iam.Role(self, "ApiRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        if ml_inference_arn:
            api_role.add_to_policy(iam.PolicyStatement(actions=["lambda:InvokeFunction"], resources=[ml_inference_arn]))
        worker_role = iam.Role(self, "WorkerRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        for role, group in ((api_role, api_logs), (worker_role, worker_logs)):
            role.add_to_policy(iam.PolicyStatement(actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                                                   resources=[group.log_group_arn]))
        self.pool = cognito.UserPool(
            self, "Users", self_sign_up_enabled=enable_self_signup,
            user_verification=cognito.UserVerificationConfig(
                email_style=cognito.VerificationEmailStyle.CODE),
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
                      "ALERTS_TABLE": "alerts", "WEARABLES_TABLE": "wearables"}
        environment = {"ECOROUTE_PROFILE": "aws", "COGNITO_USER_POOL_ID": self.pool.user_pool_id,
                       "COGNITO_CLIENT_ID": self.client.user_pool_client_id,
                       "S3_DATA_BUCKET": data.bucket.bucket_name,
                       "ENVIRONMENT_TABLE": data.tables["environment"].table_name,
                       "ENABLE_AWS_LOCATION": str(enable_location).lower(),
                       "EXPECTED_AWS_ACCOUNT_ID": self.account,
                       "CORS_ORIGINS": json.dumps(frontend_origins),
                        "LOCATION_DAILY_LIMIT": "100", "LOCATION_HOURLY_LIMIT": "30",
                        "ML_INFERENCE_FUNCTION_ARN": ml_inference_arn or "",
                       **{env: data.tables[key].table_name for env, key in table_vars.items()}}
        # Runtime only uses get/put and transactional puts; DynamoDB authorizes transactions via PutItem.
        api_role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:GetItem", "dynamodb:PutItem"],
            resources=[data.tables[k].table_arn for k in ("journeys", "preferences", "idempotency", "route_metadata")]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:Query"], resources=[data.tables["preferences"].table_arn]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"],
                                                  resources=[data.tables["alerts"].table_arn]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:DescribeTable"],
                                                  resources=[t.table_arn for t in data.tables.values()]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:Query"],
            resources=[data.tables["environment"].table_arn]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["s3:GetObject"],
            resources=[data.bucket.arn_for_objects("curated/*")]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["s3:GetObject", "s3:PutObject"],
            resources=[data.bucket.arn_for_objects("routes/*")]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["s3:PutObject"],
            resources=[data.bucket.arn_for_objects("reports/routes/*")]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:UpdateItem"],
            resources=[data.tables["environment"].table_arn]))
        if google_routes_secret_arn:
            if "*" in google_routes_secret_arn or ":secretsmanager:" not in google_routes_secret_arn:
                raise ValueError("Use a complete Google secret ARN")
            environment.update(ROUTING_PROVIDER="google", GOOGLE_ROUTES_SECRET_ARN=google_routes_secret_arn)
            api_role.add_to_policy(iam.PolicyStatement(actions=["secretsmanager:GetSecretValue"], resources=[google_routes_secret_arn]))
        if cycling_secret_arn:
            if "*" in cycling_secret_arn or ":secretsmanager:" not in cycling_secret_arn:
                raise ValueError("Use a complete cycling secret ARN")
            environment.update(CYCLING_PROVIDER="openrouteservice", OPENROUTESERVICE_SECRET_ARN=cycling_secret_arn)
            api_role.add_to_policy(iam.PolicyStatement(actions=["secretsmanager:GetSecretValue"], resources=[cycling_secret_arn]))
        if enable_guest_routes and not google_routes_secret_arn:
            raise ValueError("Guest routes require a request-only Google provider secret")
        environment["ENABLE_GUEST_ROUTES"] = str(enable_guest_routes).lower()
        environment["ENABLE_ROUTE_WEATHER"] = str(enable_route_weather).lower()
        if enable_location:
            for service, action in (("geo-routes", "CalculateRoutes"), ("geo-places", "Geocode")):
                api_role.add_to_policy(iam.PolicyStatement(actions=[service + ":" + action],
                    resources=[self.format_arn(service=service, account="", resource="provider", resource_name="default")]))
        if gemini_secret_arn or gemini_model_id:
            import re
            if bedrock_model_arn:
                raise ValueError("Select either Gemini or Bedrock explanations")
            if not (gemini_secret_arn and re.fullmatch(
                    rf"arn:aws:secretsmanager:{self.region}:{self.account}:secret:[A-Za-z0-9/_+=.@-]+", gemini_secret_arn)
                    and gemini_model_id and re.fullmatch(r"gemini-[a-zA-Z0-9.-]{1,100}", gemini_model_id)):
                raise ValueError("Gemini requires an exact same-account regional secret ARN and model ID")
            environment.update(ENABLE_GEMINI="true", GEMINI_SECRET_ARN=gemini_secret_arn,
                               GEMINI_MODEL_ID=gemini_model_id, ENABLE_BEDROCK="false")
            api_role.add_to_policy(iam.PolicyStatement(actions=["secretsmanager:GetSecretValue"],
                                                       resources=[gemini_secret_arn]))
        code = lambda_.Code.from_asset(str(Path(asset_path).resolve()))
        if __package__ == "infra":
            from .wearable_workflow import worker as wearable_worker
        else:
            from wearable_workflow import worker as wearable_worker
        wearable_worker(self, "WearableArchive", data=data, code=code,
            handler="ecoroute.wearable.handlers.archive_handler", archive=True)
        api_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:DeleteItem", "dynamodb:ConditionCheckItem"],
            resources=[data.tables["wearables"].table_arn]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["s3:DeleteObject"], resources=[data.bucket.arn_for_objects("wearables/*")]))
        api_role.add_to_policy(iam.PolicyStatement(actions=["s3:ListBucket"], resources=[data.bucket.bucket_arn],
            conditions={"StringLike": {"s3:prefix": ["wearables/*"]}}))
        self.api_function = lambda_.Function(self, "Api", runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.X86_64, handler="ecoroute.handlers.api.handler",
            code=code, role=api_role, environment=environment, timeout=Duration.seconds(28),
            memory_size=512, reserved_concurrent_executions=3, log_group=api_logs)
        if bedrock_model_arn:
            if not bedrock_model_arn.startswith(f"arn:aws:bedrock:{self.region}::foundation-model/") or "*" in bedrock_model_arn:
                raise ValueError("Use an exact regional foundation model ARN; cross-region profiles need separate review")
            api_role.add_to_policy(iam.PolicyStatement(actions=["bedrock:InvokeModel"], resources=[bedrock_model_arn]))
            self.api_function.add_environment("BEDROCK_MODEL_ID", bedrock_model_arn.split("/", 1)[1])
            environment["BEDROCK_MODEL_ID"] = bedrock_model_arn.split("/", 1)[1]
        if sms_topic_arns:
            if any(not arn.startswith(f"arn:aws:sns:{self.region}:{self.account}:") or "*" in arn for arn in sms_topic_arns):
                raise ValueError("SMS uses exact dedicated topics in the selected account and region")
            api_role.add_to_policy(iam.PolicyStatement(actions=["sns:Publish", "sns:ListSubscriptionsByTopic"], resources=sms_topic_arns))
            # These read-only SMS account APIs do not support resource-level permissions.
            api_role.add_to_policy(iam.PolicyStatement(actions=["sns:GetSMSSandboxAccountStatus", "sns:ListSMSSandboxPhoneNumbers", "sns:GetSMSAttributes"], resources=["*"], conditions={"StringEquals": {"aws:RequestedRegion": self.region}}))
            self.api_function.add_environment("SNS_ALLOWED_TOPIC_ARNS", __import__("json").dumps(sms_topic_arns))
            environment["SNS_ALLOWED_TOPIC_ARNS"] = json.dumps(sms_topic_arns)
        if enable_workflows:
            if __package__ == "infra":
                from .environment_workflow import EnvironmentalWorkflow
            else:
                from environment_workflow import EnvironmentalWorkflow
            workflow = EnvironmentalWorkflow(self, "EnvironmentalWorkflow", data=data, code=code, environment=environment, sms_topic_arns=sms_topic_arns)
            self.api_function.add_environment("WORKFLOW_STATE_MACHINE_ARN", workflow.machine.state_machine_arn)
            environment["WORKFLOW_STATE_MACHINE_ARN"] = workflow.machine.state_machine_arn
            CfnOutput(self, "EnvironmentalWorkflowArn", value=workflow.machine.state_machine_arn)
            CfnOutput(self, "EnvironmentalJobsQueue", value=workflow.queue.queue_url)
        self.queue, self.dlq = data.queue, data.dlq
        worker_role.add_to_policy(iam.PolicyStatement(actions=["s3:GetObject"],
                                                       resources=[data.bucket.arn_for_objects("raw/*")]))
        worker_role.add_to_policy(iam.PolicyStatement(actions=["s3:PutObject"],
                                                       resources=[data.bucket.arn_for_objects("curated/*")]))
        worker_role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:PutItem"],
                                                       resources=[data.tables["environment"].table_arn]))
        worker_env = {"S3_DATA_BUCKET": data.bucket.bucket_name, "ECOROUTE_PROFILE": "aws",
                      "ENVIRONMENT_TABLE": data.tables["environment"].table_name}
        ingest_role = iam.Role(self, "IngestionRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        ingest_role.add_to_policy(iam.PolicyStatement(actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                                                      resources=[ingest_logs.log_group_arn]))
        ingest_role.add_to_policy(iam.PolicyStatement(actions=["s3:PutObject"],
                                                      resources=[data.bucket.arn_for_objects("raw/*")]))
        ingest_role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"],
                                                      resources=[data.tables["environment"].table_arn]))
        ingest_env = {**worker_env, "PROVIDER_DAILY_REQUEST_LIMIT": "100", "PROVIDER_HOURLY_REQUEST_LIMIT": "30"}
        if provider_secret_arn:
            imported = secrets.Secret.from_secret_complete_arn(self, "ProviderSecret", provider_secret_arn)
            ingest_env["OPENAQ_SECRET_ARN"] = imported.secret_arn
            ingest_role.add_to_policy(iam.PolicyStatement(actions=["secretsmanager:GetSecretValue"],
                                                          resources=[imported.secret_arn]))
        collector = lambda_.Function(self, "Collector", runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.X86_64, handler="ecoroute.handlers.ingestion.collect",
            code=code, role=ingest_role, environment=ingest_env, timeout=Duration.seconds(180),
            memory_size=256, reserved_concurrent_executions=1, log_group=ingest_logs)
        worker = lambda_.Function(self, "Worker", runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.X86_64, handler="ecoroute.handlers.ingestion.clean",
            code=code, role=worker_role, environment=worker_env, timeout=Duration.seconds(30),
            memory_size=512, reserved_concurrent_executions=2, log_group=worker_logs)
        worker.add_event_source(sources.SqsEventSource(self.queue, batch_size=5,
                                                       report_batch_item_failures=True, max_concurrency=2))
        schedule_role = iam.Role(self, "ScheduleRole", assumed_by=iam.ServicePrincipal(
            "scheduler.amazonaws.com", conditions={"StringEquals": {"aws:SourceAccount": self.account},
                "ArnEquals": {"aws:SourceArn": self.format_arn(service="scheduler", resource="schedule-group",
                                                               resource_name="default")}}))
        collector.grant_invoke(schedule_role)
        scheduler.CfnSchedule(self, "IngestionSchedule", state="DISABLED",
            schedule_expression=f"rate({ingestion_interval_minutes} minutes)", flexible_time_window={"mode": "OFF"},
            target=scheduler.CfnSchedule.TargetProperty(
                arn=collector.function_arn, role_arn=schedule_role.role_arn,
                input='{"source":"open_meteo","request":{"latitude":28.6139,"longitude":77.209}}',
                retry_policy={"maximum_event_age_in_seconds": 3600, "maximum_retry_attempts": 2}))
        collector.configure_async_invoke(retry_attempts=1, max_event_age=Duration.hours(1),
                                          on_failure=destinations.SqsDestination(self.dlq))
        issuer = f"https://cognito-idp.{self.region}.amazonaws.com/{self.pool.user_pool_id}"
        authorizer = authorizers.HttpJwtAuthorizer("Cognito", issuer,
                                                   jwt_audience=[self.client.user_pool_client_id])
        api = apigw.HttpApi(self, "HttpApi", create_default_stage=False,
                            cors_preflight=apigw.CorsPreflightOptions(
                                allow_origins=frontend_origins, allow_credentials=False,
                                allow_methods=[apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST,
                                               apigw.CorsHttpMethod.PUT, apigw.CorsHttpMethod.DELETE,
                                               apigw.CorsHttpMethod.OPTIONS],
                                allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
                                expose_headers=["X-Request-ID"], max_age=Duration.minutes(5),
                            ) if frontend_origins else None,
                            default_authorizer=authorizer, default_authorization_scopes=["ecoroute/read"])
        self.http_api = api
        self.runtime_environment = {**environment, "AWS_REGION": self.region}
        self.runtime_policy_document = api_role.node.find_child("DefaultPolicy").document
        if backend_origin:
            parsed = urlsplit(backend_origin)
            if parsed.scheme != "https" or not parsed.hostname or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password:
                raise ValueError("backend_origin must be an exact HTTPS origin")
            integration = integrations.HttpUrlIntegration("FastApi", backend_origin.rstrip("/"),
                parameter_mapping=apigw.ParameterMapping().overwrite_path(apigw.MappingValue.request_path()),
                timeout=Duration.seconds(28))
        else:
            integration = integrations.HttpLambdaIntegration("FastApi", self.api_function)
        for path in ("/api/v1/health", "/healthz", "/docs", "/openapi.json"):
            api.add_routes(path=path, methods=[apigw.HttpMethod.GET], integration=integration,
                           authorizer=apigw.HttpNoneAuthorizer(), authorization_scopes=[])
        # Ready is protected in AWS to avoid public paid dependency probes.
        if enable_guest_routes:
            api.add_routes(path="/api/v1/routes/preview", methods=[apigw.HttpMethod.POST], integration=integration,
                           authorizer=apigw.HttpNoneAuthorizer(), authorization_scopes=[])
        api.add_routes(path="/api/v1/{proxy+}", methods=[apigw.HttpMethod.GET], integration=integration,
                       authorization_scopes=["ecoroute/read"])
        api.add_routes(path="/api/v1/{proxy+}", methods=[apigw.HttpMethod.POST, apigw.HttpMethod.PUT, apigw.HttpMethod.DELETE],
                       integration=integration, authorization_scopes=["ecoroute/write"])
        apigw.CfnStage(self, "Stage", api_id=api.api_id, stage_name="$default", auto_deploy=True,
            default_route_settings=apigw.CfnStage.RouteSettingsProperty(
                throttling_rate_limit=2, throttling_burst_limit=5),
            access_log_settings=apigw.CfnStage.AccessLogSettingsProperty(destination_arn=access_logs.log_group_arn,
                format=(
                    '{"requestId":"$context.requestId","route":"$context.routeKey",'
                    '"status":"$context.status","latency":"$context.responseLatency"}')))
        topic = sns.Topic(self, "OperationalAlerts", enforce_ssl=True)
        self.operational_alerts = topic
        alarm_list = [
            cloudwatch.Alarm(self, "ApiErrors", metric=self.api_function.metric_errors(),
                             threshold=1, evaluation_periods=1),
            cloudwatch.Alarm(self, "ApiDuration", metric=self.api_function.metric_duration(statistic="p95"),
                             threshold=10000, evaluation_periods=2),
            cloudwatch.Alarm(self, "WorkerErrors", metric=worker.metric_errors(), threshold=1, evaluation_periods=1),
            cloudwatch.Alarm(self, "CollectorErrors", metric=collector.metric_errors(), threshold=1, evaluation_periods=1),
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
    """Optional mTLS rule; certificate enrollment is a separate reviewed operator action."""
    def __init__(self, scope, name, *, data, asset_path, **kwargs):
        super().__init__(scope, name, **kwargs)
        if __package__ == "infra":
            from .wearable_workflow import worker
        else:
            from wearable_workflow import worker
        validator = worker(self, "WearableValidator", data=data,
            code=lambda_.Code.from_asset(str(Path(asset_path).resolve())),
            handler="ecoroute.wearable.handlers.mqtt_handler")
        rule = iot.CfnTopicRule(self, "Measurements", rule_name="ecoroute_wearable_measurements",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
            aws_iot_sql_version="2016-03-23", rule_disabled=True,
            sql="SELECT encode(*, 'base64') AS payload_b64, topic(3) AS owner_key, topic(5) AS device_id, topic() AS mqtt_topic, clientid() AS mqtt_client_id, principal() AS principal FROM 'ecoroute/users/+/devices/+/measurements'",
            actions=[iot.CfnTopicRule.ActionProperty(lambda_=iot.CfnTopicRule.LambdaActionProperty(function_arn=validator.function_arn))]))
        validator.add_permission("OnlyProjectRule", principal=iam.ServicePrincipal("iot.amazonaws.com"),
            source_arn=rule.attr_arn, source_account=self.account)
        CfnOutput(self, "RuleName", value=rule.ref)
        CfnOutput(self, "Status", value="Rule disabled; no certificates or physical device enrolled")
