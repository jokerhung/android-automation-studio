"""Fail-closed redaction for notification reports and SMTP metadata."""

from __future__ import annotations
import json
import re
from typing import Any

REDACTED = "[REDACTED]"
_SENSITIVE_KEY = re.compile(
    r"(?:^|[_-])(password|passwd|pwd|secret|token|api[_-]?key|authorization|auth|cookie|session[_-]?key|private[_-]?key|client[_-]?secret|access[_-]?key|refresh[_-]?token)(?:$|[_-])",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{6,}")
_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|authorization|cookie)(\s*[:=]\s*)([^\s,;]+)"
)
_QUOTED_SECRET = re.compile(
    r"""(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|mật khẩu)(\s*[:=]?\s*)(["'])(.*?)\3"""
)
_OTHER = (
    re.compile(r"(?i)(https?://[^:/\s]+:)[^@/\s]+@"),
    re.compile(
        r"-----BEGIN [^-]*(?:PRIVATE KEY|CERTIFICATE)-----.*?-----END [^-]+-----", re.DOTALL
    ),
    re.compile(r"\b(?:sk|pk|AIza|ghp|github_pat|xox[baprs])[-_A-Za-z0-9]{12,}\b"),
    re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])"),
)


def redact_text(value: str) -> str:
    text = _QUOTED_SECRET.sub(lambda m: f"{m.group(1)}: {REDACTED}", str(value))
    text = _BEARER.sub(lambda m: f"{m.group(1)} {REDACTED}", text)
    text = _ASSIGNMENT.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    for pattern in _OTHER:
        text = pattern.sub(REDACTED, text)
    return text


def redact(value: Any) -> Any:
    """Recursively redact mappings, JSON embedded in strings, and free text."""
    if isinstance(value, dict):
        return {
            str(key): REDACTED if _SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        if value.strip()[:1] in "[{":
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                pass
            else:
                return json.dumps(
                    redact(parsed), ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
        return redact_text(value)
    return value
