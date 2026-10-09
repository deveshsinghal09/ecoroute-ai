from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Point(StrictModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class RouteRequest(StrictModel):
    origin: Point
    destination: Point
    travel_mode: Literal["Car", "Pedestrian", "Bicycle"] = "Pedestrian"
    departure_at: AwareDatetime


class TripCreate(StrictModel):
    origin: Point
    destination: Point
    consent: Literal[True]
    route_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")] | None = None


class TelemetrySample(StrictModel):
    observed_at: AwareDatetime
    position: Point
    accuracy_m: float = Field(ge=0, le=10000)
    heart_rate_bpm: int | None = Field(default=None, ge=20, le=250)

    @model_validator(mode="after")
    def recent(self):
        now = datetime.now(UTC)
        if not now - timedelta(days=7) <= self.observed_at <= now + timedelta(minutes=5):
            raise ValueError("Sample must be within the last 7 days and at most 5 minutes ahead")
        return self


class TelemetryBatch(StrictModel):
    consent: Literal[True]
    source: Literal["manual_import", "phone_bridge", "synthetic_fixture"]
    samples: list[TelemetrySample] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def ordered(self):
        times = [s.observed_at for s in self.samples]
        if times != sorted(times) or len(times) != len(set(times)):
            raise ValueError("Sample timestamps must be unique and ascending")
        return self


class Preferences(StrictModel):
    alerts_enabled: bool = False
    channel: Literal["in_app", "sms"] = "in_app"


Identifier = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
