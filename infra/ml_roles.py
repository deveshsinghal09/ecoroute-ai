"""SageMaker job execution only: specific datasets, artifacts, image repository and logs."""
from aws_cdk import ArnFormat, Stack
from aws_cdk import aws_iam as iam


def training_role(scope, identifier, bucket, repository_arn):
    stack = Stack.of(scope)
    role = iam.Role(scope, identifier, assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com",
        conditions={"StringEquals": {"aws:SourceAccount": stack.account}, "ArnLike": {
            "aws:SourceArn": stack.format_arn(service="sagemaker", resource="training-job",
                                              resource_name="ecoroute-*")}}))
    role.add_to_policy(iam.PolicyStatement(actions=["s3:GetObject"],
                                         resources=[bucket.arn_for_objects("datasets/*")]))
    role.add_to_policy(iam.PolicyStatement(actions=["s3:ListBucket"], resources=[bucket.bucket_arn],
        conditions={"StringLike": {"s3:prefix": ["datasets/*"]}}))
    role.add_to_policy(iam.PolicyStatement(actions=["s3:PutObject"],
                                         resources=[bucket.arn_for_objects("models/training/*")]))
    role.add_to_policy(iam.PolicyStatement(actions=["ecr:GetAuthorizationToken"], resources=["*"],
        conditions={"StringEquals": {"aws:RequestedRegion": stack.region}}))
    role.add_to_policy(iam.PolicyStatement(actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer",
        "ecr:BatchCheckLayerAvailability"], resources=[repository_arn]))
    role.add_to_policy(iam.PolicyStatement(actions=["logs:CreateLogGroup", "logs:CreateLogStream",
        "logs:PutLogEvents"], resources=[stack.format_arn(service="logs", resource="log-group",
            resource_name="/aws/sagemaker/TrainingJobs:*", arn_format=ArnFormat.COLON_RESOURCE_NAME)]))
    return role
