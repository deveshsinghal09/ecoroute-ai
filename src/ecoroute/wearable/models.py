from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, Protocol

from pydantic import AwareDatetime, Field, model_validator

from ecoroute.models import Identifier, Point, StrictModel

Text = Annotated[str, Field(min_length=1, max_length=100)]


class Registration(StrictModel):
    manufacturer: Text
    model: Text
    bridge: Literal["companion_https", "authorized_import", "wear_os", "health_connect", "demo"]


class Consent(StrictModel):
    device_id: Identifier
    telemetry: bool
    location: bool = False
    history: bool = False
    correlation: bool = False
    policy_version: Literal["wearable-v1"] = "wearable-v1"

    @model_validator(mode="after")
    def scopes(self):
        if not self.telemetry and any((self.location, self.history, self.correlation)):
            raise ValueError("Revoke all dependent scopes with telemetry")
        return self


class Provenance(StrictModel):
    bridge: Literal["companion_https", "authorized_import", "wear_os", "health_connect", "demo"]
    sensor: Text
    source_record_id: Text
    synthetic: bool = False


class Measurement(StrictModel):
    device_id: Identifier
    user_id: Text  # Must equal verified JWT subject or provisioned device owner.
    event_id: Identifier
    timestamp: AwareDatetime
    heart_rate_bpm: int | None = Field(default=None, ge=20, le=250, strict=True)
    activity: Literal["unknown", "resting", "walking", "cycling", "running", "driving"] = "unknown"
    steps: int | None = Field(default=None, ge=0, le=200000, strict=True)
    steps_semantics: Literal["daily_total", "interval_count"] | None = None
    position: Point | None = None
    accuracy_m: float | None = Field(default=None, ge=0, le=10000)
    journey_id: Identifier | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def validity(self):
        self.timestamp = self.timestamp.astimezone(UTC)
        now = datetime.now(UTC)
        if not now - timedelta(days=7) <= self.timestamp <= now + timedelta(minutes=5):
            raise ValueError("Observation outside accepted seven-day window")
        if (self.steps is None) != (self.steps_semantics is None):
            raise ValueError("Steps need explicit semantics")
        if (self.position is None) != (self.accuracy_m is None):
            raise ValueError("GPS needs accuracy")
        if self.heart_rate_bpm is None and self.steps is None and self.position is None:
            raise ValueError("At least one reading required")
        return self


class WearableBridge(Protocol):
    """Authorized adapters preserve source IDs, permission state, units and actual timestamps."""
    def available_permissions(self) -> set[str]: ...
    def measurements(self, since: datetime) -> list[Measurement]: ...
