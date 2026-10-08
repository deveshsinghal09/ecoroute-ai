from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")
    ecoroute_profile: Literal["local", "aws"] = "local"
    project_name: str = "ecoroute-ai"
    enable_aws_location: bool = False
    enable_openaq: bool = False
    enable_weather: bool = False
    enable_wearable: bool = False

    @model_validator(mode="after")
    def phase_zero_guard(self):
        if self.ecoroute_profile != "local" or any((
            self.enable_aws_location, self.enable_openaq,
            self.enable_weather, self.enable_wearable,
        )):
            raise ValueError("Phase 0 supports local scaffold only; live adapters are not implemented")
        return self
