from typing import Literal
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")
    ecoroute_profile: Literal["local", "aws"] = "local"
    project_name: str = "ecoroute-ai"
    aws_region: str = "ap-south-1"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cors_origins: list[str] = []
    local_db_path: str = "work/ecoroute.sqlite3"
    journeys_table: str = ""
    preferences_table: str = ""
    route_metadata_table: str = ""
    idempotency_table: str = ""
    alerts_table: str = ""
    enable_aws_location: bool = False
    enable_openaq: bool = False
    enable_weather: bool = False
    enable_wearable: bool = False

    @model_validator(mode="after")
    def configuration_guard(self):
        if any((
            self.enable_aws_location, self.enable_openaq,
            self.enable_weather, self.enable_wearable,
        )):
            raise ValueError("Live domain providers are not implemented in Phase 1")
        for origin in self.cors_origins:
            parsed = urlsplit(origin)
            if ("*" in origin or parsed.scheme not in {"http", "https"} or not parsed.netloc
                    or parsed.path or parsed.query or parsed.fragment or parsed.username):
                raise ValueError("CORS requires exact origins without paths or wildcards")
            if self.ecoroute_profile == "aws" and parsed.scheme != "https":
                raise ValueError("AWS CORS origins must use HTTPS")
        if self.cognito_user_pool_id and not self.cognito_user_pool_id.startswith(self.aws_region + "_"):
            raise ValueError("Cognito user pool must belong to the configured region")
        if self.ecoroute_profile == "aws" and not all((
            self.cognito_user_pool_id, self.cognito_client_id, self.journeys_table,
            self.preferences_table, self.route_metadata_table, self.idempotency_table,
            self.alerts_table,
        )):
            raise ValueError("AWS profile requires Cognito IDs and all five DynamoDB table names")
        return self

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.aws_region}.amazonaws.com/{self.cognito_user_pool_id}"
