"""Read-only Health Connect contracts. Missing values remain null, never zero-filled."""
from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict


class HealthModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class BloodPressureValue(HealthModel):
    systolic: float
    diastolic: float


class HealthRecord(HealthModel):
    measurement_type: Literal["heart_rate", "blood_pressure", "oxygen_saturation", "steps", "sleep",
                              "active_calories", "total_calories", "resting_heart_rate", "respiratory_rate"]
    value: float | BloodPressureValue
    unit: Literal["bpm", "mmHg", "%", "count", "s", "kcal", "breaths/min"]
    timestamp: AwareDatetime
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None
    source_application: str | None = None
    recording_method: str | None = None
    resolution: Literal["sample", "bucket_average", "interval", "session"]
    quality: list[str] = []


class HealthConnectData(HealthModel):
    status: Literal["available", "empty"]
    retrieval: Literal["fresh", "phone_cache"]
    full_window: bool
    days: int
    fetched_at: AwareDatetime
    payload_generated_at: AwareDatetime | None
    last_synchronization_at: AwareDatetime | None
    records: list[HealthRecord]
    skipped_records: int
    warnings: list[str]


class HealthMetric(HealthModel):
    value: float | BloodPressureValue | None = None
    unit: str
    status: Literal["available", "unavailable", "partial"] = "unavailable"
    timestamp: AwareDatetime | None = None
    source_applications: list[str] = []
    resolution: str | None = None
    stale: bool = False
    warnings: list[str] = []


class HealthMetrics(HealthModel):
    heart_rate: HealthMetric
    blood_pressure: HealthMetric
    oxygen_saturation: HealthMetric
    steps: HealthMetric
    sleep: HealthMetric
    calories_burned: HealthMetric
    resting_heart_rate: HealthMetric
    respiratory_rate: HealthMetric


class HealthConnectSummary(HealthModel):
    status: Literal["available", "empty"]
    selected_date: date
    timezone: str
    fetched_at: AwareDatetime
    payload_generated_at: AwareDatetime | None
    last_synchronization_at: AwareDatetime | None
    retrieval: Literal["fresh", "phone_cache"]
    metrics: HealthMetrics
    calorie_basis: Literal["total", "active"] | None
    sleep_sessions: list[HealthRecord]
    warnings: list[str]
    skipped_records: int
    medical_assessment: Literal[False] = False


class HealthConnectStatus(HealthModel):
    status: Literal["connected"] = "connected"
    phone_reachable: Literal[True] = True
    last_synchronization_at: AwareDatetime | None = None
    fetched_at: AwareDatetime
    authentication: Literal["local_pairing", "cognito"]
