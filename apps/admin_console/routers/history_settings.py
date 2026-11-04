"""Settings -> History: retention policy for old task history (stored in SQLite)."""

from __future__ import annotations

import asyncio
import sqlite3
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

try:
    from admin_console.routers.system import _require_server_bound_request
    from admin_console.services.history_retention_service import (
        RetentionSettingsError,
        history_retention_service,
    )
except ImportError:
    from apps.admin_console.routers.system import _require_server_bound_request
    from apps.admin_console.services.history_retention_service import (
        RetentionSettingsError,
        history_retention_service,
    )

router = APIRouter(prefix="/api/settings/history", tags=["settings"])


class HistorySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    media_retention_days: int
    history_retention_days: int


def authorize(request: Request) -> None:
    _require_server_bound_request(
        request, "History settings require access through the server console."
    )
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc.lower() != request.headers.get("host", "").lower():
        raise HTTPException(403, "Use the same-origin Artemis console.")


@router.get("")
async def get_history_settings(request: Request):
    authorize(request)
    try:
        return await asyncio.to_thread(history_retention_service.get_settings)
    except (OSError, sqlite3.Error):
        raise HTTPException(500, "Unable to read history settings.") from None


@router.put("")
async def save_history_settings(payload: HistorySettingsUpdate, request: Request):
    authorize(request)
    try:
        return await asyncio.to_thread(
            history_retention_service.update_settings,
            payload.media_retention_days,
            payload.history_retention_days,
        )
    except RetentionSettingsError as exc:
        raise HTTPException(422, str(exc)) from None
    except (OSError, sqlite3.Error):
        raise HTTPException(500, "Unable to save history settings.") from None


@router.post("/run")
async def run_history_cleanup(request: Request):
    """Apply the saved retention rules now instead of waiting for the hourly pass."""
    authorize(request)
    try:
        result = await asyncio.to_thread(history_retention_service.run_once)
    except (OSError, sqlite3.Error):
        raise HTTPException(500, "History cleanup failed.") from None
    if result.get("status") == "busy":
        raise HTTPException(409, "A history cleanup is already running.")
    return {**result, "settings": history_retention_service.get_settings()}
