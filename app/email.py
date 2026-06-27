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

    message = EmailMessage()
    message["Subject"] = "IBB Insurance Portal invitation"
    message["From"] = resolved.smtp_from_email or ""
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
        with smtplib.SMTP(resolved.smtp_host or "", resolved.smtp_port, timeout=10) as smtp:
            if resolved.smtp_use_tls:
                smtp.starttls()
            if resolved.smtp_username and resolved.smtp_password:
                smtp.login(resolved.smtp_username, resolved.smtp_password)
            smtp.send_message(message)
    except OSError as exc:
        raise EmailDeliveryError("EMAIL_DELIVERY_FAILED") from exc
