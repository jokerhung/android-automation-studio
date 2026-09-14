from __future__ import annotations

import ipaddress
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_EMAIL_LOCAL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_\x60{|}~-]+$")


def _clean_header(value: str, field_name: str, *, max_length: int) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    if len(value) > max_length:
        raise ValueError(f"{field_name} is too long")
    if _CONTROL_RE.search(value):
        raise ValueError(f"{field_name} cannot contain control characters")
    return value


def validate_email_address(value: str) -> str:
    value = _clean_header(value, "email address", max_length=254)
    if value.count("@") != 1:
        raise ValueError("invalid email address")
    local, domain = value.rsplit("@", 1)
    if not local or len(local) > 64 or not _EMAIL_LOCAL_RE.fullmatch(local):
        raise ValueError("invalid email address")
    if local.startswith(".") or local.endswith(".") or ".." in local:
        raise ValueError("invalid email address")
    try:
        ascii_domain = domain.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("invalid email address") from exc
    if not ascii_domain or len(ascii_domain) > 253:
        raise ValueError("invalid email address")
    try:
        ipaddress.ip_address(ascii_domain.strip("[]"))
    except ValueError:
        labels = ascii_domain.split(".")
        if any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or not re.fullmatch(r"[a-z0-9-]+", label)
            for label in labels
        ):
            raise ValueError("invalid email address") from None
    return f"{local}@{ascii_domain}"


def validate_smtp_host(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 253 or _CONTROL_RE.search(value):
        raise ValueError("invalid SMTP host")
    if any(char in value for char in ("/", "\\", "@", "?", "#")) or "://" in value:
        raise ValueError("SMTP host must be a hostname or IP address, not a URL")
    candidate = value[1:-1] if value.startswith("[") and value.endswith("]") else value
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        if ":" in candidate:
            raise ValueError("invalid SMTP host") from None
    try:
        ascii_host = candidate.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("invalid SMTP host") from exc
    labels = ascii_host.split(".")
    if any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or not re.fullmatch(r"[a-z0-9-]+", label)
        for label in labels
    ):
        raise ValueError("invalid SMTP host")
    return ascii_host


class EmailSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    smtp_host: str
    smtp_port: int = Field(ge=1, le=65535, strict=True)
    security: Literal["starttls", "ssl"]
    smtp_username: str = Field(default="", max_length=320)
    password: SecretStr | None = Field(default=None, max_length=1024, repr=False)
    sender_email: str
    sender_name: str = Field(default="Artemis", max_length=128)
    enabled: bool = Field(default=False, strict=True)
    expected_version: int | None = Field(default=None, ge=0, strict=True)

    @field_validator("smtp_host")
    @classmethod
    def valid_host(cls, value: str) -> str:
        return validate_smtp_host(value)

    @field_validator("smtp_username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        value = value.strip()
        if _CONTROL_RE.search(value):
            raise ValueError("username cannot contain control characters")
        return value

    @field_validator("sender_email")
    @classmethod
    def valid_sender_email(cls, value: str) -> str:
        return validate_email_address(value)

    @field_validator("sender_name")
    @classmethod
    def valid_sender_name(cls, value: str) -> str:
        return _clean_header(value, "sender name", max_length=128)

    @field_validator("password")
    @classmethod
    def blank_password_means_unchanged(cls, value: SecretStr | None) -> SecretStr | None:
        return None if value is not None and not value.get_secret_value() else value


class EmailSettingsResponse(BaseModel):
    smtp_host: str = ""
    smtp_port: int = 587
    security: Literal["starttls", "ssl"] = "starttls"
    smtp_username: str = ""
    sender_email: str = ""
    sender_name: str = "Artemis"
    enabled: bool = False
    version: int = 0
    password_configured: bool = False


class SendTestEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_email: str
    recipient_name: str | None = Field(default=None, max_length=128)
    subject: str = Field(default="Artemis SMTP test", max_length=200)

    @field_validator("recipient_email")
    @classmethod
    def valid_recipient_email(cls, value: str) -> str:
        return validate_email_address(value)

    @field_validator("recipient_name")
    @classmethod
    def valid_recipient_name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_header(value, "recipient name", max_length=128)

    @field_validator("subject")
    @classmethod
    def valid_subject(cls, value: str) -> str:
        return _clean_header(value, "subject", max_length=200)


class EmailOperationResponse(BaseModel):
    success: bool
    message: str
