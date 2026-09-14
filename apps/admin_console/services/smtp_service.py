from __future__ import annotations
from email.message import EmailMessage
from email.utils import formataddr
import smtplib
import ssl
from typing import Callable

try:
    from admin_console.schemas.email_schema import EmailSettingsResponse
except ImportError:
    from apps.admin_console.schemas.email_schema import EmailSettingsResponse


class SMTPServiceError(RuntimeError):
    pass


class SMTPService:
    def __init__(
        self,
        *,
        timeout: float = 15.0,
        smtp_factory: Callable = smtplib.SMTP,
        smtp_ssl_factory: Callable = smtplib.SMTP_SSL,
        ssl_context_factory: Callable = ssl.create_default_context,
    ):
        self._timeout = timeout
        self._smtp_factory = smtp_factory
        self._smtp_ssl_factory = smtp_ssl_factory
        self._ssl_context_factory = ssl_context_factory

    def _connect(self, settings: EmailSettingsResponse, password: str):
        context = self._ssl_context_factory()
        if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
            raise SMTPServiceError("SMTP TLS certificate verification must be enabled.")
        client = None
        try:
            if settings.security == "ssl":
                client = self._smtp_ssl_factory(
                    settings.smtp_host, settings.smtp_port, timeout=self._timeout, context=context
                )
                client.ehlo()
            elif settings.security == "starttls":
                client = self._smtp_factory(
                    settings.smtp_host, settings.smtp_port, timeout=self._timeout
                )
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            else:
                raise SMTPServiceError("SMTP must use STARTTLS or implicit SSL.")
            if settings.smtp_username:
                client.login(settings.smtp_username, password)
            return client
        except Exception:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            raise

    def test_connection(self, settings, password):
        try:
            client = self._connect(settings, password)
            client.quit()
        except SMTPServiceError:
            raise
        except (OSError, smtplib.SMTPException) as exc:
            raise SMTPServiceError(
                "Unable to connect, negotiate TLS, or authenticate to SMTP."
            ) from exc

    def send(
        self,
        settings,
        password,
        recipient_email,
        subject,
        body,
        attachment_text=None,
        filename=None,
        message_id=None,
    ):
        message = EmailMessage()
        message["From"] = formataddr((settings.sender_name, settings.sender_email))
        message["To"] = recipient_email
        message["Subject"] = subject
        if message_id:
            message["Message-ID"] = message_id
        message.set_content(body, charset="utf-8")
        if attachment_text is not None:
            message.add_attachment(
                attachment_text.encode("utf-8"),
                maintype="text",
                subtype="plain",
                filename=filename or "artemis_log.txt",
            )
        try:
            client = self._connect(settings, password)
            client.send_message(
                message, from_addr=settings.sender_email, to_addrs=[recipient_email]
            )
            client.quit()
        except SMTPServiceError:
            raise
        except (OSError, smtplib.SMTPException) as exc:
            raise SMTPServiceError("The SMTP server did not accept the task email.") from exc

    def send_test(self, settings, password, *, recipient_email, recipient_name, subject):
        message = EmailMessage()
        message["From"] = formataddr((settings.sender_name, settings.sender_email))
        message["To"] = formataddr((recipient_name or "", recipient_email))
        message["Subject"] = subject
        message.set_content(
            "This is a test email from Artemis. No task data, logs, or credentials are included."
        )
        try:
            client = self._connect(settings, password)
            client.send_message(
                message, from_addr=settings.sender_email, to_addrs=[recipient_email]
            )
            client.quit()
        except SMTPServiceError:
            raise
        except (OSError, smtplib.SMTPException) as exc:
            raise SMTPServiceError("The SMTP server did not accept the test email.") from exc


smtp_service = SMTPService()
