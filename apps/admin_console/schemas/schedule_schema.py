from __future__ import annotations

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dateutil.tz import gettz

from pydantic import BaseModel, Field, field_validator, model_validator


ScheduleType = Literal["interval", "daily", "weekly"]


class ScheduleRule(BaseModel):
    schedule_type: ScheduleType
    interval_minutes: int | None = Field(default=None, ge=1, le=10080)
    time_of_day: str | None = None
    weekdays: list[int] = Field(default_factory=list)
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("timezone is required")
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            if gettz(value) is None:
                raise ValueError(f"IANA timezone is unavailable: {value}")
        return value

    @field_validator("time_of_day")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = datetime.strptime(value, "%H:%M:%S")
        except ValueError as exc:
            raise ValueError("time_of_day must use HH:mm:ss") from exc
        return parsed.strftime("%H:%M:%S")

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        if any(day < 1 or day > 7 for day in value):
            raise ValueError("weekdays must use ISO values 1 (Monday) through 7 (Sunday)")
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_rule(self):
        if self.schedule_type == "interval":
            if self.interval_minutes is None:
                raise ValueError("interval_minutes is required for interval schedules")
            if self.time_of_day is not None or self.weekdays:
                raise ValueError("interval schedules cannot define time_of_day or weekdays")
        elif self.schedule_type == "daily":
            if self.time_of_day is None:
                raise ValueError("time_of_day is required for daily schedules")
            if self.interval_minutes is not None or self.weekdays:
                raise ValueError("daily schedules cannot define interval_minutes or weekdays")
        else:
            if self.time_of_day is None:
                raise ValueError("time_of_day is required for weekly schedules")
            if not self.weekdays:
                raise ValueError("at least one weekday is required for weekly schedules")
            if self.interval_minutes is not None:
                raise ValueError("weekly schedules cannot define interval_minutes")
        return self


class TaskSnapshot(BaseModel):
    goal: str = Field(min_length=1, max_length=100000)
    profile: Literal["flash", "pro"] = "flash"
    device_serial: str = Field(min_length=1, max_length=255)
    expected_output: str | None = None
    enable_outputter: bool | None = None
    verification_level: str | None = None
    explorer_mode: str | None = None
    locked_app_package: str | None = None
    app_path: str | None = None

    @field_validator("goal", "device_serial")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value


class ScheduleCreate(ScheduleRule, TaskSnapshot):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class SchedulePatch(BaseModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    goal: str | None = Field(default=None, min_length=1, max_length=100000)
    profile: Literal["flash", "pro"] | None = None
    device_serial: str | None = Field(default=None, min_length=1, max_length=255)
    expected_output: str | None = None
    enable_outputter: bool | None = None
    verification_level: str | None = None
    explorer_mode: str | None = None
    locked_app_package: str | None = None
    app_path: str | None = None
    schedule_type: ScheduleType | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=10080)
    time_of_day: str | None = None
    weekdays: list[int] | None = None
    timezone: str | None = None
    enabled: bool | None = None


class SchedulePreview(ScheduleRule):
    anchor_at: datetime | None = None
    count: int = Field(default=5, ge=1, le=20)


class RunNowRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=200)

    @field_validator("idempotency_key")
    @classmethod
    def strip_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("idempotency_key cannot be blank")
        return value
