from __future__ import annotations
import sqlite3
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

try:
    from admin_console.routers.system import _require_server_bound_request
    from admin_console.schemas.email_schema import (
        EmailOperationResponse,
        EmailSettingsResponse,
        EmailSettingsUpdate,
        SendTestEmailRequest,
    )
    from admin_console.services.email_settings_service import (
        EmailSettingsConflict,
        EmailSettingsError,
        create_email_settings_service,
    )
    from admin_console.services.secret_store import SecretStoreError
    from admin_console.services.smtp_service import SMTPService, SMTPServiceError
except ImportError:
    from apps.admin_console.routers.system import _require_server_bound_request
    from apps.admin_console.schemas.email_schema import (
        EmailOperationResponse,
        EmailSettingsResponse,
        EmailSettingsUpdate,
        SendTestEmailRequest,
    )
    from apps.admin_console.services.email_settings_service import (
        EmailSettingsConflict,
        EmailSettingsError,
        create_email_settings_service,
    )
    from apps.admin_console.services.secret_store import SecretStoreError
    from apps.admin_console.services.smtp_service import SMTPService, SMTPServiceError

router = APIRouter(prefix="/api/settings/email", tags=["email-settings"])
_email_settings_service = None
_smtp_service = SMTPService()


def get_email_settings_service():
    global _email_settings_service
    if _email_settings_service is None:
        _email_settings_service = create_email_settings_service()
    return _email_settings_service


def get_smtp_service():
    return _smtp_service


def require_console_same_origin(request: Request):
    _require_server_bound_request(request, "SMTP settings require the local console on this server.")
    origin = request.headers.get("origin")
    host = request.headers.get("host", "").lower()
    if origin and urlsplit(origin).netloc.lower() != host:
        raise HTTPException(403, "SMTP settings require the same-origin Artemis console.")


def _error(exc):
    if isinstance(exc, EmailSettingsConflict):
        return HTTPException(409, str(exc))
    if isinstance(exc, SMTPServiceError):
        return HTTPException(502, str(exc))
    if isinstance(exc, (EmailSettingsError, SecretStoreError)):
        return HTTPException(400, str(exc))
    return HTTPException(500, "Unable to process SMTP settings.")


@router.get("/readiness")
def get_readiness(service=Depends(get_email_settings_service)) -> dict[str, bool]:
    """Expose configuration readiness to schedule clients without SMTP metadata."""
    try:
        settings = service.get()
        return {"ready": bool(
            settings.enabled and settings.smtp_host and settings.sender_email
            and settings.smtp_username and settings.password_configured
        )}
    except (EmailSettingsError, SecretStoreError, sqlite3.Error):
        raise HTTPException(503, "Unable to check SMTP readiness.") from None


@router.get(
    "", response_model=EmailSettingsResponse, dependencies=[Depends(require_console_same_origin)]
)
def get_settings(service=Depends(get_email_settings_service)):
    try:
        return service.get()
    except (EmailSettingsError, SecretStoreError, sqlite3.Error) as exc:
        raise _error(exc) from None


@router.put(
    "", response_model=EmailSettingsResponse, dependencies=[Depends(require_console_same_origin)]
)
def put_settings(payload: EmailSettingsUpdate, service=Depends(get_email_settings_service)):
    try:
        return service.update(payload)
    except (EmailSettingsError, SecretStoreError, sqlite3.Error) as exc:
        raise _error(exc) from None


@router.delete(
    "/password",
    response_model=EmailSettingsResponse,
    dependencies=[Depends(require_console_same_origin)],
)
def clear_password(service=Depends(get_email_settings_service)):
    try:
        return service.clear_password()
    except (EmailSettingsError, SecretStoreError, sqlite3.Error) as exc:
        raise _error(exc) from None


@router.post(
    "/test-connection",
    response_model=EmailOperationResponse,
    dependencies=[Depends(require_console_same_origin)],
)
async def test_connection(
    service=Depends(get_email_settings_service), smtp=Depends(get_smtp_service)
):
    try:
        settings, password = service.connection_parameters()
        await run_in_threadpool(smtp.test_connection, settings, password)
        return EmailOperationResponse(success=True, message="SMTP connection succeeded.")
    except (EmailSettingsError, SecretStoreError, SMTPServiceError) as exc:
        raise _error(exc) from None


@router.post(
    "/send-test",
    response_model=EmailOperationResponse,
    dependencies=[Depends(require_console_same_origin)],
)
async def send_test(
    payload: SendTestEmailRequest,
    service=Depends(get_email_settings_service),
    smtp=Depends(get_smtp_service),
):
    try:
        settings, password = service.connection_parameters()
        await run_in_threadpool(
            smtp.send_test,
            settings,
            password,
            recipient_email=payload.recipient_email,
            recipient_name=payload.recipient_name,
            subject=payload.subject,
        )
        return EmailOperationResponse(success=True, message="Test email accepted by SMTP.")
    except (EmailSettingsError, SecretStoreError, SMTPServiceError) as exc:
        raise _error(exc) from None
