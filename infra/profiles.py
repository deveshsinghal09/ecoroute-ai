"""Credential-free deployment configuration. Mutually exclusive, opt-in paid profiles."""
import json
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


def context_list(value):
    """CDK CLI context values are strings; context JSON can contain actual arrays."""
    if value is None:
        return None
    try:
        result = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        raise ValueError("URL/topic context must be a JSON array") from None
    if not isinstance(result, list) or not all(isinstance(item, str) for item in result):
        raise ValueError("URL/topic context must be an array of strings")
    return result


class DeploymentOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    runtime: Literal["lambda", "ecs-fargate", "ec2", "eks", "apprunner", "lightsail-proxy"] = "lambda"
    hosting: Literal["none", "cloudfront", "amplify"] = "none"
    analytics: Literal["none", "rds", "aurora"] = "none"
    lambda_reserved_concurrency: bool = False
    image_uri: str | None = None
    sql_image_uri: str | None = None
    backend_origin: str | None = None
    api_gateway_origin: str | None = None
    regional_certificate_arn: str | None = None
    cloudfront_certificate_arn: str | None = None
    domain_name: str | None = None
    hosted_zone_id: str | None = None
    hosted_zone_name: str | None = None
    existing_apprunner_customer: bool = False
    eks_version: str | None = None
    eks_operator_arn: str | None = None
    eks_admin_cidrs: list[str] = Field(default_factory=list)
    postgres_version: str = "16.6"
    sql_writer_secret_arn: str | None = None

    @model_validator(mode="after")
    def validate_profiles(self):
        for name in ("backend_origin", "api_gateway_origin"):
            value = getattr(self, name)
            if value:
                url = urlsplit(value)
                if url.scheme != "https" or not url.hostname or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment:
                    raise ValueError(f"{name} must be an exact HTTPS origin")
        for name in ("image_uri", "sql_image_uri"):
            value = getattr(self, name)
            if value and not re.fullmatch(r"(?:[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com|public\.ecr\.aws)/[a-z0-9/_-]+@sha256:[0-9a-f]{64}", value):
                raise ValueError(f"{name} requires a pinned ECR image digest")
        if self.runtime != "lambda" and not self.image_uri:
            raise ValueError("Container runtime requires image_uri")
        if self.runtime in ("ecs-fargate", "ec2") and not self.regional_certificate_arn:
            raise ValueError("ALB runtime requires a regional ACM certificate")
        if self.runtime == "apprunner" and not self.existing_apprunner_customer:
            raise ValueError("App Runner is restricted to existing eligible customers")
        if self.runtime == "lightsail-proxy":
            if not self.api_gateway_origin or not self.image_uri.startswith("public.ecr.aws/"):
                raise ValueError("Lightsail proxy requires API Gateway origin and public digest-pinned proxy image")
            if self.backend_origin:
                raise ValueError("Lightsail must not be the API Gateway backend (proxy loop)")
        elif self.runtime != "lambda" and self.image_uri.startswith("public.ecr.aws/"):
            raise ValueError("Backend runtime requires an account-owned private ECR image")
        if self.runtime == "lambda" and self.backend_origin:
            raise ValueError("Select the deployed runtime before switching API Gateway")
        if self.runtime == "eks":
            import ipaddress
            if not self.eks_version or not self.eks_operator_arn or not self.eks_admin_cidrs:
                raise ValueError("EKS requires supported version, operator IAM ARN and restricted admin CIDRs")
            for cidr in self.eks_admin_cidrs:
                if ipaddress.ip_network(cidr).prefixlen == 0:
                    raise ValueError("EKS API must not allow the whole internet")
        for name in ("regional_certificate_arn", "cloudfront_certificate_arn", "sql_writer_secret_arn", "eks_operator_arn"):
            value = getattr(self, name)
            if value and (not value.startswith("arn:aws:") or "*" in value):
                raise ValueError(f"{name} requires an exact commercial AWS ARN")
        if self.analytics != "none" and not self.sql_writer_secret_arn:
            raise ValueError("SQL requires a separately provisioned restricted writer secret ARN")
        if self.analytics == "rds" and not self.sql_image_uri:
            raise ValueError("RDS requires SQL Lambda image with psycopg and verified RDS CA bundle")
        if not re.fullmatch(r"[0-9]+\.[0-9]+", self.postgres_version):
            raise ValueError("PostgreSQL version must be an explicit major.minor")
        if any((self.domain_name, self.hosted_zone_id, self.hosted_zone_name, self.cloudfront_certificate_arn)):
            if self.hosting != "cloudfront" or not all((self.domain_name, self.hosted_zone_id, self.hosted_zone_name, self.cloudfront_certificate_arn)):
                raise ValueError("Custom domain requires CloudFront, zone identifiers and us-east-1 certificate")
            if not self.cloudfront_certificate_arn.startswith("arn:aws:acm:us-east-1:"):
                raise ValueError("CloudFront certificate must be in us-east-1")
            zone = self.hosted_zone_name.rstrip(".")
            if not re.fullmatch(r"[a-z0-9.-]+", self.domain_name) or not (self.domain_name == zone or self.domain_name.endswith("." + zone)):
                raise ValueError("Domain must belong to the selected zone")
        return self

    @classmethod
    def load(cls, path: str | Path | None):
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8"))) if path else cls()

    def plan(self):
        return {"runtime": self.runtime, "hosting": self.hosting, "analytics": self.analytics,
                "deployed": False, "aws_calls": False,
                "paid_options_enabled": [v for v in (self.runtime, self.hosting, self.analytics) if v not in ("lambda", "none")],
                "switch_gateway_after_runtime_verification": self.runtime not in ("lambda", "lightsail-proxy") and not self.backend_origin,
                "schedules_enabled": False, "nat_gateways": 0,
                "lambda_reserved_concurrency": self.lambda_reserved_concurrency,
                "training_started": False, "notifications_enabled": False}
