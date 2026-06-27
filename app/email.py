from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import Settings, get_settings


class EmailDeliveryError(Exception):
    pass


def send_invite_email(
    *,
    to_email: str,
    invite_link: str,
    temporary_password: str,
    settings: Settings | None = None,
) -> None:
    resolved = settings or get_settings()
    if not resolved.email_enabled:
        raise EmailDeliveryError("EMAIL_NOT_CONFIGURED")

    smtp_from_email = resolved.resolved_smtp_from_email or ""
    smtp_username = resolved.resolved_smtp_username
    smtp_password = resolved.resolved_smtp_password
    message = EmailMessage()
    message["Subject"] = "IBB Insurance Portal invitation"
    message["From"] = smtp_from_email
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                "IBB Insurance Portal",
                "",
                "You have been invited to the portal.",
                f"Login link: {invite_link}",
                f"Temporary password: {temporary_password}",
                "",
                "Do not forward this message.",
            ]
        )
    )

    try:
        smtp_class = smtplib.SMTP_SSL if resolved.smtp_secure else smtplib.SMTP
        with smtp_class(resolved.smtp_host or "", resolved.smtp_port, timeout=10) as smtp:
            if not resolved.smtp_secure and resolved.smtp_use_tls:
                smtp.starttls()
            if smtp_username and smtp_password:
                smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
    except OSError as exc:
        raise EmailDeliveryError("EMAIL_DELIVERY_FAILED") from exc
