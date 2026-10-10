"""Optional RDS/Aurora analytics consumes existing reports/routes S3 events."""
from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as alarm_actions
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications as notifications
from aws_cdk import aws_secretsmanager as secrets
from aws_cdk import aws_sqs as sqs


class AnalyticsStack(Stack):
    def __init__(self, scope, name, *, data, options, asset_path, alert_topic=None, **kwargs):
        super().__init__(scope, name, **kwargs)
        if options.analytics not in ("rds", "aurora"):
            raise ValueError("SQL analytics disabled")
        if not options.sql_writer_secret_arn.startswith(f"arn:aws:secretsmanager:{self.region}:{self.account}:"):
            raise ValueError("Writer secret must be in the selected account and region")
        vpc = ec2.Vpc(self, "DatabaseVpc", max_azs=2, nat_gateways=0,
            subnet_configuration=[ec2.SubnetConfiguration(name="isolated", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED)])
        security = ec2.SecurityGroup(self, "DatabaseSecurity", vpc=vpc, allow_all_outbound=False)
        # Master credentials are generated and NEVER passed to the worker. Restricted writer is separate.
        master = rds.Credentials.from_generated_secret("ecoroute_admin")
        version = options.postgres_version
        if options.analytics == "rds":
            database = rds.DatabaseInstance(self, "Postgres", vpc=vpc, security_groups=[security],
                vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
                engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.of(version, version.split(".")[0])),
                credentials=master, database_name="ecoroute", instance_type=ec2.InstanceType("t3.micro"),
                allocated_storage=20, max_allocated_storage=20, storage_encrypted=True, publicly_accessible=False,
                multi_az=False, deletion_protection=True, removal_policy=RemovalPolicy.SNAPSHOT,
                backup_retention=Duration.days(1), enable_performance_insights=False,
                parameter_group=rds.ParameterGroup(self, "TlsRequired", engine=rds.DatabaseInstanceEngine.postgres(
                    version=rds.PostgresEngineVersion.of(version, version.split(".")[0])), parameters={"rds.force_ssl": "1"}))
        else:
            database = rds.DatabaseCluster(self, "Aurora", vpc=vpc, security_groups=[security],
                vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
                engine=rds.DatabaseClusterEngine.aurora_postgres(version=rds.AuroraPostgresEngineVersion.of(version, version.split(".")[0])),
                credentials=master, default_database_name="ecoroute", storage_encrypted=True,
                writer=rds.ClusterInstance.serverless_v2("Writer", publicly_accessible=False),
                serverless_v2_min_capacity=0.5, serverless_v2_max_capacity=1,
                enable_data_api=True, deletion_protection=True, removal_policy=RemovalPolicy.SNAPSHOT,
                backup=rds.BackupProps(retention=Duration.days(1)))
        environment = {"SQL_ANALYTICS_ENGINE": options.analytics, "SQL_WRITER_SECRET_ARN": options.sql_writer_secret_arn,
                       "S3_DATA_BUCKET": data.bucket.bucket_name}
        writer_secret = secrets.Secret.from_secret_complete_arn(self, "RestrictedWriter", options.sql_writer_secret_arn)
        role = iam.Role(self, "WriterRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        writer_secret.grant_read(role)
        role.add_to_policy(iam.PolicyStatement(actions=["s3:GetObject"], resources=[data.bucket.arn_for_objects("reports/routes/*")]))
        group = logs.LogGroup(self, "WriterLogs", retention=logs.RetentionDays.ONE_WEEK, removal_policy=RemovalPolicy.DESTROY)
        group.grant_write(role)
        props = {}
        if options.analytics == "aurora":
            environment["SQL_CLUSTER_ARN"] = database.cluster_arn
            role.add_to_policy(iam.PolicyStatement(actions=["rds-data:ExecuteStatement"], resources=[database.cluster_arn]))
            code = lambda_.Code.from_asset(asset_path)
            worker = lambda_.Function(self, "ReportWriter", runtime=lambda_.Runtime.PYTHON_3_11,
                code=code, handler="ecoroute.analytics.handler", environment=environment, role=role,
                log_group=group, timeout=Duration.seconds(30), memory_size=256, reserved_concurrent_executions=2)
        else:
            environment.update(SQL_HOST=database.db_instance_endpoint_address, SQL_CA_BUNDLE="/opt/rds-ca.pem")
            lambda_security = ec2.SecurityGroup(self, "WorkerSecurity", vpc=vpc)
            security.add_ingress_rule(lambda_security, ec2.Port.tcp(5432))
            # No NAT. S3 gateway is free; Secrets Manager endpoint has hourly/data charges.
            vpc.add_gateway_endpoint("S3", service=ec2.GatewayVpcEndpointAwsService.S3)
            endpoint_security = ec2.SecurityGroup(self, "EndpointSecurity", vpc=vpc)
            endpoint_security.add_ingress_rule(lambda_security, ec2.Port.tcp(443))
            endpoint = vpc.add_interface_endpoint("Secrets", service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
                security_groups=[endpoint_security], subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED))
            endpoint.add_to_policy(iam.PolicyStatement(actions=["secretsmanager:GetSecretValue"],
                principals=[iam.ArnPrincipal(role.role_arn)], resources=[writer_secret.secret_arn]))
            # These ENI operations require Resource=*; isolated worker role only.
            role.add_to_policy(iam.PolicyStatement(actions=["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces",
                "ec2:DeleteNetworkInterface", "ec2:AssignPrivateIpAddresses", "ec2:UnassignPrivateIpAddresses"], resources=["*"],
                conditions={"StringEquals": {"aws:RequestedRegion": self.region}}))
            image, digest = options.sql_image_uri.split("@", 1)
            registry, repository_name = image.split("/", 1)
            if registry != f"{self.account}.dkr.ecr.{self.region}.amazonaws.com":
                raise ValueError("SQL image must be account/region owned")
            repository = ecr.Repository.from_repository_name(self, "SqlImage", repository_name)
            props = {"vpc": vpc, "security_groups": [lambda_security],
                     "vpc_subnets": ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED)}
            worker = lambda_.DockerImageFunction(self, "ReportWriter",
                code=lambda_.DockerImageCode.from_ecr(repository, tag_or_digest=digest),
                environment=environment, role=role, log_group=group, timeout=Duration.seconds(30),
                memory_size=256, reserved_concurrent_executions=2, **props)
        dlq = sqs.Queue(self, "ReportDeadLetters", encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True, retention_period=Duration.days(14))
        queue = sqs.Queue(self, "Reports", encryption=sqs.QueueEncryption.SQS_MANAGED, enforce_ssl=True,
            visibility_timeout=Duration.seconds(180), retention_period=Duration.days(1),
            dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=3))
        # Explicit Data->Analytics bucket reference would create a dependency cycle with notifications.
        # Use an imported view in this stack; the custom resource merges notifications on the SAME bucket.
        existing = s3.Bucket.from_bucket_attributes(self, "ExistingReports", bucket_name=data.bucket.bucket_name)
        existing.add_event_notification(s3.EventType.OBJECT_CREATED, notifications.SqsDestination(queue),
                                        s3.NotificationKeyFilter(prefix="reports/routes/", suffix=".json"))
        worker.add_event_source(sources.SqsEventSource(queue, batch_size=1, report_batch_item_failures=True, max_concurrency=2))
        dlq_alarm = cloudwatch.Alarm(self, "DeadLettersVisible", metric=dlq.metric_approximate_number_of_messages_visible(),
            threshold=1, evaluation_periods=1, treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING)
        # Partial-batch failures don't increment Lambda Errors: expose a log metric instead.
        failures = logs.MetricFilter(self, "Failures", log_group=group,
            filter_pattern=logs.FilterPattern.string_value("$.event", "=", "route_analytics_failed"),
            metric_namespace="EcoRoute/Analytics", metric_name="ProcessingFailures", metric_value="1")
        failure_alarm = cloudwatch.Alarm(self, "ProcessingFailed", metric=failures.metric(), threshold=1, evaluation_periods=1)
        if alert_topic:
            for alarm in (dlq_alarm, failure_alarm):
                alarm.add_alarm_action(alarm_actions.SnsAction(alert_topic))
        CfnOutput(self, "WriterFunction", value=worker.function_name)
        CfnOutput(self, "ReportQueue", value=queue.queue_url)
        CfnOutput(self, "AdminSecretArn", value=database.secret.secret_arn)
        CfnOutput(self, "Status", value="Initialize schema/restricted writer with sql/route_analytics.sql before replaying reports; master is NOT used by worker")
