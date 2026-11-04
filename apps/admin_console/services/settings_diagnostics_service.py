"""Console diagnostics for the email settings kept in SQLite."""

import sys

from artemis.core.diagnostics.schema import ProbeAction, ProbeCategory, ProbeResult, ProbeStatus

try:
    from admin_console.services.email_settings_service import EmailSettingsService
    from admin_console.services.secret_store import create_secret_store
except ImportError:
    from apps.admin_console.services.email_settings_service import EmailSettingsService
    from apps.admin_console.services.secret_store import create_secret_store


def email_settings_probe() -> ProbeResult:
    metadata = {"storage": "sqlite"}
    status = ProbeStatus.PASS
    summary = "Disabled (optional)"
    description = "Email notifications are disabled in SQLite settings."
    try:
        secret_store = create_secret_store() if sys.platform == "win32" else None
        value = EmailSettingsService(secret_store).get()
        ready = bool(
            value.smtp_host
            and value.sender_email
            and value.smtp_username
            and value.password_configured
        )
        metadata.update(enabled=value.enabled, ready=value.enabled and ready)
        if value.enabled:
            status = ProbeStatus.PASS if ready else ProbeStatus.WARN
            summary = "Configured" if ready else "Configuration incomplete"
            description = (
                "SMTP settings and password are configured in SQLite. Use Email > Test connection to verify SMTP access."
                if ready
                else "Complete the SMTP settings in Settings > Email before scheduling email notifications."
            )
    except Exception:
        status = ProbeStatus.WARN
        summary = "Unable to check email settings"
        description = "Check database access and SMTP password storage in Settings > Email."
    return ProbeResult(
        id="email_settings",
        category=ProbeCategory.CREDENTIALS,
        title="Email settings (SQLite)",
        status=status,
        is_blocker=False,
        summary=summary,
        description=description,
        metadata=metadata,
        actions=[
            ProbeAction(action_type="link", label="Email settings", payload="/settings/?tab=email")
        ],
    )
