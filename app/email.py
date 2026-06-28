# ruff: noqa: E501
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import make_msgid
from html import escape
from pathlib import Path

from app.config import Settings, get_settings

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "ibb-logo.png"
DEFAULT_LANGUAGE = "ru"
RTL_LANGUAGES = {"ar", "ckb", "fa", "he"}

INVITE_EMAIL_COPY = {
    "ru": {
        "subject": "Приглашение в IBB Insurance Portal",
        "title": "Добро пожаловать в IBB Insurance Portal",
        "intro": "Вы получили приглашение в портал для управления заявками, полисами, документами, статусами и продлениями в одном защищенном пространстве.",
        "hint": "Используйте кнопку ниже для входа. Временный пароль указан отдельно для первого доступа.",
        "button": "Войти в портал",
        "password_label": "Временный пароль",
        "fallback_hint": "Если кнопка не работает, скопируйте и вставьте эту ссылку в браузер:",
        "security": "В целях безопасности не пересылайте это письмо. IBB никогда не попросит отправить этот пароль по email или в мессенджере.",
        "plain_invited": "Вы получили приглашение в IBB Insurance Portal.",
        "plain_use_link": "Используйте защищенную ссылку ниже для входа и настройки доступа.",
        "login_link": "Ссылка для входа",
        "temporary_password": "Временный пароль",
        "do_not_forward": "В целях безопасности не пересылайте это письмо.",
    },
    "en": {
        "subject": "Invitation to IBB Insurance Portal",
        "title": "Welcome to IBB Insurance Portal",
        "intro": "You have been invited to manage insurance applications, policies, documents, statuses, and renewals in one secure place.",
        "hint": "Use the button below to sign in. Your temporary password is shown separately for your first access.",
        "button": "Log in to portal",
        "password_label": "Temporary password",
        "fallback_hint": "If the button does not work, copy and paste this link into your browser:",
        "security": "For security, do not forward this message. IBB will never ask you to send this password by email or messenger.",
        "plain_invited": "You have been invited to the IBB Insurance Portal.",
        "plain_use_link": "Use the secure link below to sign in and set up your access.",
        "login_link": "Login link",
        "temporary_password": "Temporary password",
        "do_not_forward": "For security, do not forward this message.",
    },
    "ka": {
        "subject": "მოწვევა IBB Insurance Portal-ში",
        "title": "კეთილი იყოს თქვენი მობრძანება IBB Insurance Portal-ში",
        "intro": "თქვენ მოწვეული ხართ პორტალში, სადაც შეგიძლიათ მართოთ სადაზღვევო განაცხადები, პოლისები, დოკუმენტები, სტატუსები და განახლებები ერთ დაცულ სივრცეში.",
        "hint": "შესასვლელად გამოიყენეთ ქვემოთ მოცემული ღილაკი. დროებითი პაროლი მითითებულია ცალკე პირველი შესვლისთვის.",
        "button": "პორტალში შესვლა",
        "password_label": "დროებითი პაროლი",
        "fallback_hint": "თუ ღილაკი არ მუშაობს, დააკოპირეთ და ჩასვით ეს ბმული ბრაუზერში:",
        "security": "უსაფრთხოების მიზნით, ნუ გადააგზავნით ამ წერილს. IBB არასოდეს მოგთხოვთ ამ პაროლის გაგზავნას email-ით ან მესენჯერით.",
        "plain_invited": "თქვენ მოწვეული ხართ IBB Insurance Portal-ში.",
        "plain_use_link": "შესასვლელად და წვდომის დასაყენებლად გამოიყენეთ დაცული ბმული.",
        "login_link": "შესვლის ბმული",
        "temporary_password": "დროებითი პაროლი",
        "do_not_forward": "უსაფრთხოების მიზნით, ნუ გადააგზავნით ამ წერილს.",
    },
}

PASSWORD_RESET_EMAIL_COPY = {
    "ru": {
        "subject": "Восстановление пароля IBB Insurance Portal",
        "title": "Восстановление пароля",
        "intro": "Мы получили запрос на восстановление пароля для IBB Insurance Portal.",
        "hint": "Используйте кнопку ниже, чтобы задать новый пароль. Ссылка действует ограниченное время.",
        "button": "Задать новый пароль",
        "fallback_hint": "Если кнопка не работает, скопируйте и вставьте эту ссылку в браузер:",
        "security": "Если вы не запрашивали восстановление пароля, просто проигнорируйте это письмо.",
        "plain_intro": "Мы получили запрос на восстановление пароля для IBB Insurance Portal.",
        "plain_use_link": "Используйте защищенную ссылку ниже, чтобы задать новый пароль.",
        "reset_link": "Ссылка для восстановления пароля",
        "do_not_forward": "Если вы не запрашивали восстановление пароля, просто проигнорируйте это письмо.",
    },
    "en": {
        "subject": "IBB Insurance Portal password reset",
        "title": "Reset your password",
        "intro": "We received a password reset request for IBB Insurance Portal.",
        "hint": "Use the button below to set a new password. This link is valid for a limited time.",
        "button": "Set new password",
        "fallback_hint": "If the button does not work, copy and paste this link into your browser:",
        "security": "If you did not request a password reset, you can ignore this email.",
        "plain_intro": "We received a password reset request for IBB Insurance Portal.",
        "plain_use_link": "Use the secure link below to set a new password.",
        "reset_link": "Password reset link",
        "do_not_forward": "If you did not request a password reset, you can ignore this email.",
    },
    "ka": {
        "subject": "IBB Insurance Portal პაროლის აღდგენა",
        "title": "პაროლის აღდგენა",
        "intro": "მივიღეთ მოთხოვნა IBB Insurance Portal-ის პაროლის აღდგენაზე.",
        "hint": "ახალი პაროლის დასაყენებლად გამოიყენეთ ქვემოთ მოცემული ღილაკი. ბმული მოქმედებს შეზღუდული დროით.",
        "button": "ახალი პაროლის დაყენება",
        "fallback_hint": "თუ ღილაკი არ მუშაობს, დააკოპირეთ და ჩასვით ეს ბმული ბრაუზერში:",
        "security": "თუ პაროლის აღდგენა თქვენ არ მოგითხოვიათ, უბრალოდ უგულებელყავით ეს წერილი.",
        "plain_intro": "მივიღეთ მოთხოვნა IBB Insurance Portal-ის პაროლის აღდგენაზე.",
        "plain_use_link": "ახალი პაროლის დასაყენებლად გამოიყენეთ დაცული ბმული.",
        "reset_link": "პაროლის აღდგენის ბმული",
        "do_not_forward": "თუ პაროლის აღდგენა თქვენ არ მოგითხოვიათ, უბრალოდ უგულებელყავით ეს წერილი.",
    },
}

LANGUAGE_COPY_ALIASES = {
    "be": "ru",
    "uk": "ru",
    "hy": "ru",
    "tr": "en",
    "az": "en",
    "kk": "ru",
    "uz": "ru",
    "ky": "ru",
    "pl": "en",
    "ar": "en",
    "ckb": "en",
    "kmr": "en",
    "ro": "en",
    "sr": "en",
    "sq": "en",
    "fa": "en",
    "he": "en",
    "mn": "ru",
}


class EmailDeliveryError(Exception):
    pass


def build_invite_email_message(
    *,
    to_email: str,
    invite_link: str,
    temporary_password: str,
    from_email: str,
    language: str = DEFAULT_LANGUAGE,
    logo_path: Path = LOGO_PATH,
) -> EmailMessage:
    copy_key = language if language in INVITE_EMAIL_COPY else LANGUAGE_COPY_ALIASES.get(language, DEFAULT_LANGUAGE)
    copy = INVITE_EMAIL_COPY.get(copy_key, INVITE_EMAIL_COPY[DEFAULT_LANGUAGE])
    direction = "rtl" if language in RTL_LANGUAGES else "ltr"
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

    message.add_alternative(
        f"""\
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
                <h1 style="margin:0 0 14px;font-family:Georgia,'Times New Roman',serif;font-size:30px;line-height:1.2;font-weight:400;color:#082f68;">{escape(copy["title"])}</h1>
                <p style="margin:0 0 18px;font-size:16px;line-height:1.6;color:#1f3f70;">{escape(copy["intro"])}</p>
                <p style="margin:0 0 26px;font-size:14px;line-height:1.6;color:#526987;">{escape(copy["hint"])}</p>
                <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 28px;">
                  <tr>
                    <td style="border-radius:8px;background:#0057a8;">
                      <a href="{safe_invite_link}" style="display:inline-block;padding:14px 28px;font-size:15px;line-height:20px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">{escape(copy["button"])}</a>
                    </td>
                  </tr>
                </table>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fbff;border:1px solid #dce8f6;border-radius:8px;margin:0 0 24px;">
                  <tr>
                    <td style="padding:18px 20px;">
                      <p style="margin:0 0 6px;font-size:13px;line-height:18px;color:#526987;">{escape(copy["password_label"])}</p>
                      <p style="margin:0;font-family:'Courier New',monospace;font-size:18px;line-height:24px;font-weight:700;color:#082f68;letter-spacing:0.4px;">{safe_password}</p>
                    </td>
                  </tr>
                </table>
                <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#526987;">{escape(copy["fallback_hint"])}</p>
                <p style="margin:0 0 26px;font-size:13px;line-height:1.6;word-break:break-all;color:#0057a8;">{safe_invite_link}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 32px 28px;background:#fffaf2;border-top:1px solid #ecd8ad;">
                <p style="margin:0;font-size:13px;line-height:1.6;color:#6b5a35;">{escape(copy["security"])}</p>
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


def build_password_reset_email_message(
    *,
    to_email: str,
    reset_link: str,
    from_email: str,
    language: str = DEFAULT_LANGUAGE,
    logo_path: Path = LOGO_PATH,
) -> EmailMessage:
    copy_key = language if language in PASSWORD_RESET_EMAIL_COPY else LANGUAGE_COPY_ALIASES.get(language, DEFAULT_LANGUAGE)
    copy = PASSWORD_RESET_EMAIL_COPY.get(copy_key, PASSWORD_RESET_EMAIL_COPY[DEFAULT_LANGUAGE])
    direction = "rtl" if language in RTL_LANGUAGES else "ltr"
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
    message.add_alternative(
        f"""\
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
                <h1 style="margin:0 0 14px;font-family:Georgia,'Times New Roman',serif;font-size:30px;line-height:1.2;font-weight:400;color:#082f68;">{escape(copy["title"])}</h1>
                <p style="margin:0 0 18px;font-size:16px;line-height:1.6;color:#1f3f70;">{escape(copy["intro"])}</p>
                <p style="margin:0 0 26px;font-size:14px;line-height:1.6;color:#526987;">{escape(copy["hint"])}</p>
                <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 28px;">
                  <tr>
                    <td style="border-radius:8px;background:#0057a8;">
                      <a href="{safe_reset_link}" style="display:inline-block;padding:14px 28px;font-size:15px;line-height:20px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">{escape(copy["button"])}</a>
                    </td>
                  </tr>
                </table>
                <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#526987;">{escape(copy["fallback_hint"])}</p>
                <p style="margin:0 0 26px;font-size:13px;line-height:1.6;word-break:break-all;color:#0057a8;">{safe_reset_link}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 32px 28px;background:#fffaf2;border-top:1px solid #ecd8ad;">
                <p style="margin:0;font-size:13px;line-height:1.6;color:#6b5a35;">{escape(copy["security"])}</p>
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


def build_first_login_email_message(
    *,
    to_email: str,
    first_login_link: str,
    from_email: str,
    language: str = DEFAULT_LANGUAGE,
    logo_path: Path = LOGO_PATH,
) -> EmailMessage:
    copy_key = language if language in INVITE_EMAIL_COPY else LANGUAGE_COPY_ALIASES.get(language, DEFAULT_LANGUAGE)
    copy = INVITE_EMAIL_COPY.get(copy_key, INVITE_EMAIL_COPY[DEFAULT_LANGUAGE])
    direction = "rtl" if language in RTL_LANGUAGES else "ltr"
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
    message.add_alternative(
        f"""\
<!doctype html>
<html lang="{escape(language, quote=True)}" dir="{direction}">
  <body dir="{direction}" style="margin:0;padding:0;background:#f7f9fc;font-family:Arial,Helvetica,sans-serif;color:#0a2f66;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f7f9fc;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border:1px solid #dfe7f2;border-radius:8px;box-shadow:0 12px 32px rgba(10,47,102,0.08);overflow:hidden;">
            <tr><td style="padding:28px 32px 20px;border-bottom:1px solid #e8eef6;"><img src="{logo_src}" width="96" alt="IBB" style="display:block;border:0;outline:none;text-decoration:none;width:96px;height:auto;"></td></tr>
            <tr>
              <td style="padding:34px 32px 12px;">
                <div style="width:48px;height:2px;background:#c89b3c;margin-bottom:22px;"></div>
                <h1 style="margin:0 0 14px;font-family:Georgia,'Times New Roman',serif;font-size:30px;line-height:1.2;font-weight:400;color:#082f68;">{escape(copy["title"])}</h1>
                <p style="margin:0 0 18px;font-size:16px;line-height:1.6;color:#1f3f70;">{escape(copy["intro"])}</p>
                <p style="margin:0 0 26px;font-size:14px;line-height:1.6;color:#526987;">{escape(copy["hint"])}</p>
                <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 28px;"><tr><td style="border-radius:8px;background:#0057a8;"><a href="{safe_link}" style="display:inline-block;padding:14px 28px;font-size:15px;line-height:20px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">{escape(copy["button"])}</a></td></tr></table>
                <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#526987;">{escape(copy["fallback_hint"])}</p>
                <p style="margin:0 0 26px;font-size:13px;line-height:1.6;word-break:break-all;color:#0057a8;">{safe_link}</p>
              </td>
            </tr>
            <tr><td style="padding:18px 32px 28px;background:#fffaf2;border-top:1px solid #ecd8ad;"><p style="margin:0;font-size:13px;line-height:1.6;color:#6b5a35;">{escape(copy["security"])}</p></td></tr>
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
    language: str = DEFAULT_LANGUAGE,
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
        language=language,
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


def send_first_login_email(
    *,
    to_email: str,
    first_login_link: str,
    language: str = DEFAULT_LANGUAGE,
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
    try:
        smtp_class = smtplib.SMTP_SSL if resolved.smtp_secure else smtplib.SMTP
        with smtp_class(resolved.smtp_host or "", resolved.smtp_port, timeout=10) as smtp:
            if not resolved.smtp_secure and resolved.smtp_use_tls:
                smtp.starttls()
            if resolved.resolved_smtp_username and resolved.resolved_smtp_password:
                smtp.login(resolved.resolved_smtp_username, resolved.resolved_smtp_password)
            smtp.send_message(message)
    except OSError as exc:
        raise EmailDeliveryError("EMAIL_DELIVERY_FAILED") from exc


def send_password_reset_email(
    *,
    to_email: str,
    reset_link: str,
    language: str = DEFAULT_LANGUAGE,
    settings: Settings | None = None,
) -> None:
    resolved = settings or get_settings()
    if not resolved.email_enabled:
        raise EmailDeliveryError("EMAIL_NOT_CONFIGURED")

    smtp_from_email = resolved.resolved_smtp_from_email or ""
    smtp_username = resolved.resolved_smtp_username
    smtp_password = resolved.resolved_smtp_password
    message = build_password_reset_email_message(
        to_email=to_email,
        reset_link=reset_link,
        from_email=smtp_from_email,
        language=language,
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
