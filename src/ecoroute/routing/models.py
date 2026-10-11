from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from ecoroute.models import Point, StrictModel

Place = Annotated[str, StringConstraints(min_length=3, max_length=200, strip_whitespace=True)]


class CompareRequest(StrictModel):
    origin: Point | Place
    destination: Point | Place
    mode: Literal["walking", "cycling", "driving"] = "walking"
    departure_at: AwareDatetime
    objective: Literal["fastest", "lowest_exposure", "balanced"] = "balanced"
    max_detour_percent: float = Field(default=25, ge=0, le=100)
    exposure_weight: float = Field(default=0.5, ge=0, le=1)
    weather_weight: float = Field(default=0, ge=0, le=1)
    terrain_weight: float = Field(default=0, ge=0, le=1)
    avoid_tolls: bool = False
    avoid_highways: bool = False
    avoid_ferries: bool = False
    avoid_steps: bool = False
    segment_length_m: int = Field(default=250, ge=100, le=1000)
    max_alternatives: int = Field(default=2, ge=0, le=5)
    consent_to_store: Literal[True]

    @model_validator(mode="after")
    def window(self):
        if self.exposure_weight + self.weather_weight + self.terrain_weight > 1 + 1e-9:
            raise ValueError("Exposure, weather and terrain weights must sum to at most one; remaining weight is travel time")
        if self.mode != "driving" and any((self.avoid_tolls, self.avoid_highways, self.avoid_ferries)):
            raise ValueError("Toll/highway/ferry preferences are supported only for driving")
        if self.mode != "cycling" and (self.avoid_steps or self.terrain_weight):
            raise ValueError("Step avoidance and terrain scoring currently require the cycling provider")
        self.departure_at = self.departure_at.astimezone(UTC)
        if (
            not datetime.now(UTC) - timedelta(minutes=5)
            <= self.departure_at
            <= datetime.now(UTC) + timedelta(hours=48)
        ):
            raise ValueError("Departure must be now through 48 hours ahead")
        return self


class PreviewRequest(CompareRequest):
    """Guest route processing with no permission to persist personal route data."""
    consent_to_store: Literal[False] = False
    max_alternatives: int = Field(default=2, ge=0, le=2)
    segment_length_m: int = Field(default=250, ge=250, le=1000)


class ExposureRequest(StrictModel):
    route_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    departure_at: AwareDatetime | None = None


class DepartureRequest(CompareRequest):
    departures: list[AwareDatetime] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def departures_window(self):
        self.departures = [d.astimezone(UTC) for d in self.departures]
        if len(set(self.departures)) != len(self.departures):
            raise ValueError("Distinct departure times required")
        for d in self.departures:
            if (
                not datetime.now(UTC) - timedelta(minutes=5)
                <= d
                <= datetime.now(UTC) + timedelta(hours=48)
            ):
                raise ValueError("Departure must be now through 48 hours ahead")
        return self


class RoutingError(Exception):
    def __init__(self, code, status=503):
        self.code, self.status = code, status
        super().__init__(code)
