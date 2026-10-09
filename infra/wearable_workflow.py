"""Archive validated HTTPS/MQTT telemetry asynchronously, with bounded retries."""
import json

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sqs as sqs


def worker(scope, name, *, data, code, handler, archive=False):
    log = logs.LogGroup(scope, name + "Logs", retention=logs.RetentionDays.ONE_WEEK,
                        removal_policy=RemovalPolicy.DESTROY)
    role = iam.Role(scope, name + "Role", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
    actions = ["dynamodb:GetItem"] if archive else ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:ConditionCheckItem"]
    role.add_to_policy(iam.PolicyStatement(actions=actions, resources=[data.tables["wearables"].table_arn]))
    role.add_to_policy(iam.PolicyStatement(actions=["logs:CreateLogStream", "logs:PutLogEvents"], resources=[log.log_group_arn]))
    queue = sqs.Queue(scope, name + "Failures", encryption=sqs.QueueEncryption.SQS_MANAGED,
        enforce_ssl=True, retention_period=Duration.days(1))
    queue.grant_send_messages(role)
    environment = {"WEARABLES_TABLE": data.tables["wearables"].table_name}
    if archive:
        environment["S3_DATA_BUCKET"] = data.bucket.bucket_name
        role.add_to_policy(iam.PolicyStatement(actions=["s3:PutObject", "s3:DeleteObject"],
            resources=[data.bucket.arn_for_objects("wearables/*")]))
    function = lam.Function(scope, name, runtime=lam.Runtime.PYTHON_3_11,
        architecture=lam.Architecture.X86_64, handler=handler, code=code, environment=environment,
        timeout=Duration.seconds(30), memory_size=256, reserved_concurrent_executions=1,
        role=role, log_group=log, dead_letter_queue=None if archive else queue)
    cw.Alarm(scope, name + "Errors", metric=function.metric_errors(), threshold=1, evaluation_periods=1)
    cw.Alarm(scope, name + "FailureQueue", metric=queue.metric_approximate_number_of_messages_visible(),
             threshold=1, evaluation_periods=1)
    if archive:
        role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:DescribeStream", "dynamodb:GetRecords", "dynamodb:GetShardIterator"],
            resources=[data.tables["wearables"].table_stream_arn]))
        # ListStreams has no resource-level scope; constrain the required exception by region.
        role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:ListStreams"], resources=["*"],
            conditions={"StringEquals": {"aws:RequestedRegion": scope.region}}))
        mapping = lam.CfnEventSourceMapping(scope, name + "Stream", function_name=function.function_name,
            event_source_arn=data.tables["wearables"].table_stream_arn, starting_position="LATEST",
            batch_size=10, maximum_retry_attempts=2, maximum_record_age_in_seconds=3600,
            parallelization_factor=1, bisect_batch_on_function_error=True,
            function_response_types=["ReportBatchItemFailures"],
            destination_config=lam.CfnEventSourceMapping.DestinationConfigProperty(
                on_failure=lam.CfnEventSourceMapping.OnFailureProperty(destination=queue.queue_arn)),
            filter_criteria=lam.CfnEventSourceMapping.FilterCriteriaProperty(filters=[
                lam.CfnEventSourceMapping.FilterProperty(pattern=json.dumps({"eventName": ["INSERT"],
                    "dynamodb": {"NewImage": {"sk": {"S": [{"prefix": "measurement#"}]}}}}))]))
        mapping.node.add_dependency(role)
    return function
