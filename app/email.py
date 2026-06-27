# ruff: noqa: E501
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import make_msgid
from html import escape
from pathlib import Path

from app.config import Settings, get_settings

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "ibb-logo.png"


class EmailDeliveryError(Exception):
    pass


def build_invite_email_message(
    *,
    to_email: str,
    invite_link: str,
    temporary_password: str,
    from_email: str,
    logo_path: Path = LOGO_PATH,
) -> EmailMessage:
    logo_cid = make_msgid(domain="ibb.expert")
    logo_src = f"cid:{logo_cid[1:-1]}"
    safe_invite_link = escape(invite_link, quote=True)
    safe_password = escape(temporary_password)

    message = EmailMessage()
    message["Subject"] = "Invitation to IBB Insurance Portal"
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                "IBB Insurance Portal",
                "",
                "You have been invited to the IBB Insurance Portal.",
                "Use the secure link below to sign in and set up your access.",
                "",
                f"Login link: {invite_link}",
                f"Temporary password: {temporary_password}",
                "",
                "For security, do not forward this message.",
            ]
        )
    )

    message.add_alternative(
        f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background:#f7f9fc;font-family:Arial,Helvetica,sans-serif;color:#0a2f66;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f7f9fc;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border:1px solid #dfe7f2;border-radius:8px;box-shadow:0 12px 32px rgba(10,47,102,0.08);overflow:hidden;">
            <tr>
              <td style="padding:28px 32px 20px;border-bottom:1px solid #e8eef6;">
                <img src="{logo_src}" width="96" alt="IBB" style="display:block;border:0;outline:none;text-decoration:none;width:96px;height:auto;">
              </td>
            </tr>
            <tr>
              <td style="padding:34px 32px 12px;">
                <div style="width:48px;height:2px;background:#c89b3c;margin-bottom:22px;"></div>
                <h1 style="margin:0 0 14px;font-family:Georgia,'Times New Roman',serif;font-size:30px;line-height:1.2;font-weight:400;color:#082f68;">Welcome to IBB Insurance Portal</h1>
                <p style="margin:0 0 18px;font-size:16px;line-height:1.6;color:#1f3f70;">You have been invited to manage insurance applications, policies, documents, statuses, and renewals in one secure place.</p>
                <p style="margin:0 0 26px;font-size:14px;line-height:1.6;color:#526987;">Use the button below to sign in. Your temporary password is shown separately for your first access.</p>
                <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 28px;">
                  <tr>
                    <td style="border-radius:8px;background:#0057a8;">
                      <a href="{safe_invite_link}" style="display:inline-block;padding:14px 28px;font-size:15px;line-height:20px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">Log in to portal</a>
                    </td>
                  </tr>
                </table>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fbff;border:1px solid #dce8f6;border-radius:8px;margin:0 0 24px;">
                  <tr>
                    <td style="padding:18px 20px;">
                      <p style="margin:0 0 6px;font-size:13px;line-height:18px;color:#526987;">Temporary password</p>
                      <p style="margin:0;font-family:'Courier New',monospace;font-size:18px;line-height:24px;font-weight:700;color:#082f68;letter-spacing:0.4px;">{safe_password}</p>
                    </td>
                  </tr>
                </table>
                <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#526987;">If the button does not work, copy and paste this link into your browser:</p>
                <p style="margin:0 0 26px;font-size:13px;line-height:1.6;word-break:break-all;color:#0057a8;">{safe_invite_link}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 32px 28px;background:#fffaf2;border-top:1px solid #ecd8ad;">
                <p style="margin:0;font-size:13px;line-height:1.6;color:#6b5a35;">For security, do not forward this message. IBB will never ask you to send this password by email or messenger.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""",
        subtype="html",
    )

    if logo_path.exists():
        html_part = message.get_payload()[-1]
        html_part.add_related(
            logo_path.read_bytes(),
            maintype="image",
            subtype="png",
            cid=logo_cid,
            filename="ibb-logo.png",
        )
    return message


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
    message = build_invite_email_message(
        to_email=to_email,
        invite_link=invite_link,
        temporary_password=temporary_password,
        from_email=smtp_from_email,
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
