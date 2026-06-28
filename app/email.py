# ruff: noqa: E501
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import make_msgid
from html import escape
from pathlib import Path

from app.config import Settings, get_settings
from app.i18n import DEFAULT_LOCALE, normalize_locale, section

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "ibb-logo.png"
RTL_LANGUAGES = {"ar", "ckb", "fa", "he"}


class EmailDeliveryError(Exception):
    pass


def language_direction(language: str) -> str:
    return "rtl" if language in RTL_LANGUAGES else "ltr"


def html_shell(*, language: str, logo_src: str, title: str, body: str, security: str) -> str:
    direction = language_direction(language)
    return f"""\
<!doctype html>
<html lang="{escape(language, quote=True)}" dir="{direction}">
  <body dir="{direction}" style="margin:0;padding:0;background:#f7f9fc;font-family:Arial,Helvetica,sans-serif;color:#0a2f66;">
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
                <h1 style="margin:0 0 14px;font-family:Georgia,'Times New Roman',serif;font-size:30px;line-height:1.2;font-weight:400;color:#082f68;">{escape(title)}</h1>
                {body}
              </td>
            </tr>
            <tr>
              <td style="padding:18px 32px 28px;background:#fffaf2;border-top:1px solid #ecd8ad;">
                <p style="margin:0;font-size:13px;line-height:1.6;color:#6b5a35;">{escape(security)}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def add_inline_logo(message: EmailMessage, logo_cid: str, logo_path: Path) -> None:
    if logo_path.exists():
        html_part = message.get_payload()[-1]
        html_part.add_related(
            logo_path.read_bytes(),
            maintype="image",
            subtype="png",
            cid=logo_cid,
            filename="ibb-logo.png",
        )


def build_invite_email_message(
    *,
    to_email: str,
    invite_link: str,
    temporary_password: str,
    from_email: str,
    language: str = DEFAULT_LOCALE,
    logo_path: Path = LOGO_PATH,
) -> EmailMessage:
    copy = section(language, "email.invite")
    normalized_language = normalize_locale(language)
    logo_cid = make_msgid(domain="ibb.expert")
    logo_src = f"cid:{logo_cid[1:-1]}"
    safe_invite_link = escape(invite_link, quote=True)
    safe_password = escape(temporary_password)

    message = EmailMessage()
    message["Subject"] = copy["subject"]
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                "IBB Insurance Portal",
                "",
                copy["plain_invited"],
                copy["plain_use_link"],
                "",
                f"{copy['login_link']}: {invite_link}",
                f"{copy['temporary_password']}: {temporary_password}",
                "",
                copy["do_not_forward"],
            ]
        )
    )
    body = f"""\
                <p style="margin:0 0 18px;font-size:16px;line-height:1.6;color:#1f3f70;">{escape(copy["intro"])}</p>
                <p style="margin:0 0 26px;font-size:14px;line-height:1.6;color:#526987;">{escape(copy["hint"])}</p>
                <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 28px;"><tr><td style="border-radius:8px;background:#0057a8;"><a href="{safe_invite_link}" style="display:inline-block;padding:14px 28px;font-size:15px;line-height:20px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">{escape(copy["button"])}</a></td></tr></table>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fbff;border:1px solid #dce8f6;border-radius:8px;margin:0 0 24px;"><tr><td style="padding:18px 20px;"><p style="margin:0 0 6px;font-size:13px;line-height:18px;color:#526987;">{escape(copy["password_label"])}</p><p style="margin:0;font-family:'Courier New',monospace;font-size:18px;line-height:24px;font-weight:700;color:#082f68;letter-spacing:0.4px;">{safe_password}</p></td></tr></table>
                <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#526987;">{escape(copy["fallback_hint"])}</p>
                <p style="margin:0 0 26px;font-size:13px;line-height:1.6;word-break:break-all;color:#0057a8;">{safe_invite_link}</p>
"""
    message.add_alternative(
        html_shell(
            language=language if language in RTL_LANGUAGES else normalized_language,
            logo_src=logo_src,
            title=copy["title"],
            body=body,
            security=copy["security"],
        ),
        subtype="html",
    )
    add_inline_logo(message, logo_cid, logo_path)
    return message


def build_first_login_email_message(
    *,
    to_email: str,
    first_login_link: str,
    from_email: str,
    language: str = DEFAULT_LOCALE,
    logo_path: Path = LOGO_PATH,
) -> EmailMessage:
    copy = section(language, "email.invite")
    normalized_language = normalize_locale(language)
    logo_cid = make_msgid(domain="ibb.expert")
    logo_src = f"cid:{logo_cid[1:-1]}"
    safe_link = escape(first_login_link, quote=True)

    message = EmailMessage()
    message["Subject"] = copy["subject"]
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                "IBB Insurance Portal",
                "",
                copy["plain_invited"],
                copy["plain_use_link"],
                "",
                f"{copy['login_link']}: {first_login_link}",
                "",
                copy["do_not_forward"],
            ]
        )
    )
    body = f"""\
                <p style="margin:0 0 18px;font-size:16px;line-height:1.6;color:#1f3f70;">{escape(copy["intro"])}</p>
                <p style="margin:0 0 26px;font-size:14px;line-height:1.6;color:#526987;">{escape(copy["hint"])}</p>
                <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 28px;"><tr><td style="border-radius:8px;background:#0057a8;"><a href="{safe_link}" style="display:inline-block;padding:14px 28px;font-size:15px;line-height:20px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">{escape(copy["button"])}</a></td></tr></table>
                <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#526987;">{escape(copy["fallback_hint"])}</p>
                <p style="margin:0 0 26px;font-size:13px;line-height:1.6;word-break:break-all;color:#0057a8;">{safe_link}</p>
"""
    message.add_alternative(
        html_shell(
            language=language if language in RTL_LANGUAGES else normalized_language,
            logo_src=logo_src,
            title=copy["title"],
            body=body,
            security=copy["security"],
        ),
        subtype="html",
    )
    add_inline_logo(message, logo_cid, logo_path)
    return message


def build_password_reset_email_message(
    *,
    to_email: str,
    reset_link: str,
    from_email: str,
    language: str = DEFAULT_LOCALE,
    logo_path: Path = LOGO_PATH,
) -> EmailMessage:
    copy = section(language, "email.password_reset")
    normalized_language = normalize_locale(language)
    logo_cid = make_msgid(domain="ibb.expert")
    logo_src = f"cid:{logo_cid[1:-1]}"
    safe_reset_link = escape(reset_link, quote=True)

    message = EmailMessage()
    message["Subject"] = copy["subject"]
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                "IBB Insurance Portal",
                "",
                copy["plain_intro"],
                copy["plain_use_link"],
                "",
                f"{copy['reset_link']}: {reset_link}",
                "",
                copy["do_not_forward"],
            ]
        )
    )
    body = f"""\
                <p style="margin:0 0 18px;font-size:16px;line-height:1.6;color:#1f3f70;">{escape(copy["intro"])}</p>
                <p style="margin:0 0 26px;font-size:14px;line-height:1.6;color:#526987;">{escape(copy["hint"])}</p>
                <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 28px;"><tr><td style="border-radius:8px;background:#0057a8;"><a href="{safe_reset_link}" style="display:inline-block;padding:14px 28px;font-size:15px;line-height:20px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">{escape(copy["button"])}</a></td></tr></table>
                <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#526987;">{escape(copy["fallback_hint"])}</p>
                <p style="margin:0 0 26px;font-size:13px;line-height:1.6;word-break:break-all;color:#0057a8;">{safe_reset_link}</p>
"""
    message.add_alternative(
        html_shell(
            language=language if language in RTL_LANGUAGES else normalized_language,
            logo_src=logo_src,
            title=copy["title"],
            body=body,
            security=copy["security"],
        ),
        subtype="html",
    )
    add_inline_logo(message, logo_cid, logo_path)
    return message


def send_invite_email(
    *,
    to_email: str,
    invite_link: str,
    temporary_password: str,
    language: str = DEFAULT_LOCALE,
    settings: Settings | None = None,
) -> None:
    resolved = settings or get_settings()
    if not resolved.email_enabled:
        raise EmailDeliveryError("EMAIL_NOT_CONFIGURED")
    message = build_invite_email_message(
        to_email=to_email,
        invite_link=invite_link,
        temporary_password=temporary_password,
        from_email=resolved.resolved_smtp_from_email or "",
        language=language,
    )
    send_message(message, resolved)


def send_first_login_email(
    *,
    to_email: str,
    first_login_link: str,
    language: str = DEFAULT_LOCALE,
    settings: Settings | None = None,
) -> None:
    resolved = settings or get_settings()
    if not resolved.email_enabled:
        raise EmailDeliveryError("EMAIL_NOT_CONFIGURED")
    message = build_first_login_email_message(
        to_email=to_email,
        first_login_link=first_login_link,
        from_email=resolved.resolved_smtp_from_email or "",
        language=language,
    )
    send_message(message, resolved)


def send_password_reset_email(
    *,
    to_email: str,
    reset_link: str,
    language: str = DEFAULT_LOCALE,
    settings: Settings | None = None,
) -> None:
    resolved = settings or get_settings()
    if not resolved.email_enabled:
        raise EmailDeliveryError("EMAIL_NOT_CONFIGURED")
    message = build_password_reset_email_message(
        to_email=to_email,
        reset_link=reset_link,
        from_email=resolved.resolved_smtp_from_email or "",
        language=language,
    )
    send_message(message, resolved)


def send_message(message: EmailMessage, settings: Settings) -> None:
    try:
        smtp_class = smtplib.SMTP_SSL if settings.smtp_secure else smtplib.SMTP
        with smtp_class(settings.smtp_host or "", settings.smtp_port, timeout=10) as smtp:
            if not settings.smtp_secure and settings.smtp_use_tls:
                smtp.starttls()
            if settings.resolved_smtp_username and settings.resolved_smtp_password:
                smtp.login(settings.resolved_smtp_username, settings.resolved_smtp_password)
            smtp.send_message(message)
    except OSError as exc:
        raise EmailDeliveryError("EMAIL_DELIVERY_FAILED") from exc
