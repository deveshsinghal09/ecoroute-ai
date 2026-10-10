"""Offline inventory of integrated services and mutually exclusive deployment profiles."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from infra.profiles import DeploymentOptions  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    args = parser.parse_args(argv)
    options = DeploymentOptions.load(args.config)
    print(json.dumps({**options.plan(), "shared_core": ["Lambda", "API Gateway", "Cognito", "DynamoDB", "S3", "SQS", "CloudWatch"],
        "existing_opt_in": ["SageMaker AI training/inference", "Step Functions", "EventBridge Scheduler", "SNS", "IoT Core", "Bedrock"],
        "new_profiles": {"runtime": ["ECS + Fargate", "EC2", "EKS", "App Runner (existing customers)", "Lightsail HTTPS proxy"],
                         "hosting": ["S3 + CloudFront + optional Route 53", "Amplify manual hosting"],
                         "analytics": ["RDS PostgreSQL", "Aurora PostgreSQL Data API"]},
        "configuration_needed_later": ["AWS_PROFILE", "AWS_REGION", "EXPECTED_AWS_ACCOUNT_ID", "CDK_BOOTSTRAP", "DEPLOY_IAM_PERMISSIONS",
                                       "COGNITO_CALLBACK_URLS", "FRONTEND_ORIGINS", "selected_profile_identifiers"],
        "warning": "No AWS verification or deployment performed. Credits are not a spending cap. See docs/MULTISERVICE_INTEGRATION.md."}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
