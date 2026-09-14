from __future__ import annotations

from datetime import datetime
from email.utils import parseaddr
import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dateutil.tz import gettz

from pydantic import BaseModel, Field, field_validator, model_validator


ScheduleType = Literal["interval", "daily", "weekly"]
_EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
_ALLOWED_SUBJECT_FIELDS = {"schedule_name", "status", "finished_at"}


def _validate_mailbox(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or any(ch in value for ch in "\r\n"):
        raise ValueError("recipient_email must be a single valid email address")
    _, address = parseaddr(value)
    if address != value or not _EMAIL_RE.fullmatch(address) or len(value) > 320:
        raise ValueError("recipient_email must be a single valid email address")
    return value


def _validate_header(value: str | None, field: str, max_length: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if any(ch in value for ch in "\r\n"):
        raise ValueError(f"{field} cannot contain line breaks")
    if len(value) > max_length:
        raise ValueError(f"{field} is too long")
    return value or None


def _validate_subject_placeholders(value: str | None) -> str | None:
    value = _validate_header(value, "email_subject", 500)
    if value is None:
        return None
    fields = set(re.findall(r"(?<!{){([a-zA-Z_][a-zA-Z0-9_]*)}(?!})", value))
    unknown = fields - _ALLOWED_SUBJECT_FIELDS
    if unknown:
        raise ValueError(f"unsupported email subject placeholder: {sorted(unknown)[0]}")
    return value


class EmailNotificationPolicy(BaseModel):
    email_enabled: bool = False
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient_email: str | None = Field(default=None, max_length=320)
    email_subject: str | None = Field(default=None, max_length=500)

    @field_validator("recipient_email")
    @classmethod
    def validate_recipient_email(cls, value: str | None) -> str | None:
        return _validate_mailbox(value)

    @field_validator("recipient_name")
    @classmethod
    def validate_recipient_name(cls, value: str | None) -> str | None:
        return _validate_header(value, "recipient_name", 200)

    @field_validator("email_subject")
    @classmethod
    def validate_email_subject(cls, value: str | None) -> str | None:
        return _validate_subject_placeholders(value)

    @model_validator(mode="after")
    def validate_email_policy(self):
        if self.email_enabled and (not self.recipient_email or not self.email_subject):
            raise ValueError("recipient_email and email_subject are required when email is enabled")
        return self


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


class ScheduleCreate(ScheduleRule, TaskSnapshot, EmailNotificationPolicy):
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
    email_enabled: bool | None = None
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient_email: str | None = Field(default=None, max_length=320)
    email_subject: str | None = Field(default=None, max_length=500)

    @field_validator("recipient_email")
    @classmethod
    def validate_recipient_email(cls, value: str | None) -> str | None:
        return _validate_mailbox(value)

    @field_validator("recipient_name")
    @classmethod
    def validate_recipient_name(cls, value: str | None) -> str | None:
        return _validate_header(value, "recipient_name", 200)

    @field_validator("email_subject")
    @classmethod
    def validate_email_subject(cls, value: str | None) -> str | None:
        return _validate_subject_placeholders(value)


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
