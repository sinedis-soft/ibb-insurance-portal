# ruff: noqa: E501
from __future__ import annotations

from typing import Any

DEFAULT_LOCALE = "ru"
SUPPORTED_LOCALES = {"ru", "ka"}
FUTURE_LOCALES = {"pl", "kk", "en"}

LOCALE_ALIASES = {
    "be": "ru",
    "uk": "ru",
    "hy": "ru",
    "kk": "ru",
    "uz": "ru",
    "ky": "ru",
    "mn": "ru",
}

MESSAGES: dict[str, dict[str, Any]] = {
    "ru": {
        "errors": {
            "INVALID_CREDENTIALS": "Неверный email или пароль",
            "TOO_MANY_LOGIN_ATTEMPTS": "Слишком много попыток входа. Попробуйте позже.",
            "SESSION_EXPIRED": "Сессия истекла",
            "UNAUTHORIZED": "Войдите в личный кабинет",
            "FORBIDDEN": "Доступ запрещен",
            "USER_BLOCKED": "Пользователь заблокирован",
            "USER_NOT_FOUND": "Пользователь не найден",
            "TOKEN_INVALID": "Ссылка недействительна",
            "TOKEN_EXPIRED": "Срок действия ссылки истек",
            "TOKEN_ALREADY_USED": "Ссылка уже была использована",
            "PASSWORD_TOO_WEAK": "Пароль не соответствует требованиям безопасности",
            "TOO_MANY_REQUESTS": "Слишком много запросов. Попробуйте позже.",
            "EMAIL_SEND_FAILED": "Не удалось отправить письмо",
            "EMAIL_NOT_CONFIGURED": "Отправка email не настроена",
            "EMAIL_DELIVERY_FAILED": "Не удалось доставить письмо",
            "COMPANY_ACCESS_DENIED": "Нет доступа к этой компании",
            "ROLE_NOT_ALLOWED": "Эту роль нельзя назначить для доступа к компании",
            "COMPANY_ROLE_ALREADY_EXISTS": "Такая связь пользователя с компанией уже существует",
            "COMPANY_ROLE_NOT_FOUND": "Связь пользователя с компанией не найдена",
            "BITRIX_COMPANY_NOT_FOUND": "Компания Bitrix24 не найдена",
            "BITRIX_UNAVAILABLE": "Bitrix24 временно недоступен",
            "SUPERADMIN_REQUIRED": "Требуются права суперадминистратора",
            "ACCESS_DENIED": "Доступ запрещён",
            "APPLICATION_NOT_FOUND": "Заявка не найдена",
            "DOCUMENT_NOT_FOUND": "Документ не найден",
            "POLICY_NOT_FOUND": "Полис не найден",
            "APPLICATION_ACCESS_DENIED": "Нет доступа к этой заявке",
            "DOCUMENT_ACCESS_DENIED": "Нет доступа к этому документу",
            "POLICY_ACCESS_DENIED": "Нет доступа к этому полису",
            "PARTNER_ACCESS_DENIED": "Нет доступа в партнёрском контуре",
            "ACTION_NOT_ALLOWED": "Действие недоступно для вашей роли",
            "PARTNER_ROLE_REQUIRED": "Пользователь должен быть партнёром",
            "PARTNER_LINK_STATUS_NOT_ALLOWED": "Недопустимый статус партнёрской связи",
            "PARTNER_CLIENT_LINK_ALREADY_EXISTS": "Такая партнёрская связь уже существует",
            "PARTNER_CLIENT_LINK_NOT_FOUND": "Партнёрская связь не найдена",
        },
        "roles": {
            "client_executor": "Клиент-исполнитель",
            "client_admin": "Клиент-администратор",
            "client_viewer": "Клиент-наблюдатель",
            "partner": "Партнёр",
            "superadmin": "Суперадминистратор",
        },
        "access_statuses": {
            "pending": "Ожидает подтверждения",
            "active": "Активен",
            "revoked": "Отозван",
            "rejected": "Отклонён",
        },
        "partner_link_statuses": {
            "pending": "Ожидает подтверждения",
            "active": "Активна",
            "another_partner": "Клиент другого партнёра",
            "rejected": "Отклонена",
            "revoked": "Отозвана",
        },
        "bitrix_link_statuses": {
            "not_checked": "Не проверено",
            "confirmed": "Подтверждено",
            "not_found": "Не найдено",
            "mismatch": "Несовпадение",
            "bitrix_unavailable": "Bitrix24 недоступен",
        },
        "statuses": {
            "draft": "Черновик",
            "received": "Получена заявка",
            "approval_pending": "Ожидает согласования",
            "returned_for_revision": "Возвращена на исправление",
            "sent_to_work": "Отправлена в работу",
            "in_work": "В работе",
            "documents_expected": "Ожидаются документы",
            "signed_documents_expected": "Ожидаются подписанные документы",
            "payment_expected": "Ожидается оплата",
            "insurer_review": "На согласовании со страховой",
            "policy_issuing": "Выпускается полис",
            "policy_issued": "Полис выпущен",
            "rejected": "Отказано",
            "cancelled": "Отменено",
            "annulled": "Аннулировано",
        },
        "email": {
            "invite": {
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
            "password_reset": {
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
        },
    },
    "ka": {
        "errors": {
            "INVALID_CREDENTIALS": "Email ან პაროლი არასწორია",
            "TOO_MANY_LOGIN_ATTEMPTS": "შესვლის მცდელობა ძალიან ბევრია. სცადეთ მოგვიანებით.",
            "SESSION_EXPIRED": "სესიის ვადა ამოიწურა",
            "UNAUTHORIZED": "შედით პირად კაბინეტში",
            "FORBIDDEN": "წვდომა აკრძალულია",
            "USER_BLOCKED": "მომხმარებელი დაბლოკილია",
            "USER_NOT_FOUND": "მომხმარებელი ვერ მოიძებნა",
            "TOKEN_INVALID": "ბმული არასწორია",
            "TOKEN_EXPIRED": "ბმულის ვადა ამოიწურა",
            "TOKEN_ALREADY_USED": "ბმული უკვე გამოყენებულია",
            "PASSWORD_TOO_WEAK": "პაროლი არ აკმაყოფილებს უსაფრთხოების მოთხოვნებს",
            "TOO_MANY_REQUESTS": "მოთხოვნა ძალიან ბევრია. სცადეთ მოგვიანებით.",
            "EMAIL_SEND_FAILED": "წერილის გაგზავნა ვერ მოხერხდა",
            "EMAIL_NOT_CONFIGURED": "Email გაგზავნა არ არის დაყენებული",
            "EMAIL_DELIVERY_FAILED": "წერილის მიწოდება ვერ მოხერხდა",
            "COMPANY_ACCESS_DENIED": "ამ კომპანიაზე წვდომა არ გაქვთ",
            "ROLE_NOT_ALLOWED": "ეს როლი კომპანიის წვდომისთვის არ დაინიშნება",
            "COMPANY_ROLE_ALREADY_EXISTS": "მომხმარებლის და კომპანიის ასეთი კავშირი უკვე არსებობს",
            "COMPANY_ROLE_NOT_FOUND": "მომხმარებლის და კომპანიის კავშირი ვერ მოიძებნა",
            "BITRIX_COMPANY_NOT_FOUND": "Bitrix24 კომპანია ვერ მოიძებნა",
            "BITRIX_UNAVAILABLE": "Bitrix24 დროებით მიუწვდომელია",
            "SUPERADMIN_REQUIRED": "საჭიროა სუპერადმინისტრატორის უფლებები",
            "ACCESS_DENIED": "წვდომა აკრძალულია",
            "APPLICATION_NOT_FOUND": "განაცხადი ვერ მოიძებნა",
            "DOCUMENT_NOT_FOUND": "დოკუმენტი ვერ მოიძებნა",
            "POLICY_NOT_FOUND": "პოლისი ვერ მოიძებნა",
            "APPLICATION_ACCESS_DENIED": "ამ განაცხადზე წვდომა არ გაქვთ",
            "DOCUMENT_ACCESS_DENIED": "ამ დოკუმენტზე წვდომა არ გაქვთ",
            "POLICY_ACCESS_DENIED": "ამ პოლისზე წვდომა არ გაქვთ",
            "PARTNER_ACCESS_DENIED": "პარტნიორის კონტურში წვდომა არ გაქვთ",
            "ACTION_NOT_ALLOWED": "ეს მოქმედება თქვენი როლისთვის მიუწვდომელია",
            "PARTNER_ROLE_REQUIRED": "მომხმარებელი პარტნიორი უნდა იყოს",
            "PARTNER_LINK_STATUS_NOT_ALLOWED": "პარტნიორული კავშირის სტატუსი დაუშვებელია",
            "PARTNER_CLIENT_LINK_ALREADY_EXISTS": "ასეთი პარტნიორული კავშირი უკვე არსებობს",
            "PARTNER_CLIENT_LINK_NOT_FOUND": "პარტნიორული კავშირი ვერ მოიძებნა",
        },
        "roles": {
            "client_executor": "კლიენტი შემსრულებელი",
            "client_admin": "კლიენტი ადმინისტრატორი",
            "client_viewer": "კლიენტი დამკვირვებელი",
            "partner": "პარტნიორი",
            "superadmin": "სუპერადმინისტრატორი",
        },
        "access_statuses": {
            "pending": "დადასტურების მოლოდინში",
            "active": "აქტიური",
            "revoked": "გაუქმებული",
            "rejected": "უარყოფილი",
        },
        "partner_link_statuses": {
            "pending": "დადასტურების მოლოდინში",
            "active": "აქტიური",
            "another_partner": "სხვა პარტნიორის კლიენტი",
            "rejected": "უარყოფილი",
            "revoked": "გაუქმებული",
        },
        "bitrix_link_statuses": {
            "not_checked": "არ შემოწმებულა",
            "confirmed": "დადასტურებული",
            "not_found": "ვერ მოიძებნა",
            "mismatch": "შეუსაბამობა",
            "bitrix_unavailable": "Bitrix24 მიუწვდომელია",
        },
        "statuses": {
            "draft": "შავი ვერსია",
            "received": "განაცხადი მიღებულია",
            "approval_pending": "ელოდება შეთანხმებას",
            "returned_for_revision": "დაბრუნებულია შესასწორებლად",
            "sent_to_work": "გაგზავნილია სამუშაოდ",
            "in_work": "მუშავდება",
            "documents_expected": "ელოდება დოკუმენტებს",
            "signed_documents_expected": "ელოდება ხელმოწერილ დოკუმენტებს",
            "payment_expected": "ელოდება გადახდას",
            "insurer_review": "სადაზღვევოს განხილვაზეა",
            "policy_issuing": "პოლისი მზადდება",
            "policy_issued": "პოლისი გამოშვებულია",
            "rejected": "უარყოფილია",
            "cancelled": "გაუქმებულია",
            "annulled": "ანულირებულია",
        },
        "email": {
            "invite": {
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
            "password_reset": {
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
        },
    },
}


def normalize_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LOCALE
    normalized = locale.lower().split("-", maxsplit=1)[0].strip()
    if normalized in SUPPORTED_LOCALES:
        return normalized
    return LOCALE_ALIASES.get(normalized, DEFAULT_LOCALE)


def t(locale: str | None, key: str) -> str:
    normalized = normalize_locale(locale)
    return _lookup(MESSAGES[normalized], key) or _lookup(MESSAGES[DEFAULT_LOCALE], key) or key


def section(locale: str | None, key: str) -> dict[str, str]:
    normalized = normalize_locale(locale)
    value = _lookup_raw(MESSAGES[normalized], key)
    fallback = _lookup_raw(MESSAGES[DEFAULT_LOCALE], key)
    if isinstance(value, dict):
        return value
    if isinstance(fallback, dict):
        return fallback
    return {}


def _lookup(dictionary: dict[str, Any], key: str) -> str | None:
    value = _lookup_raw(dictionary, key)
    return value if isinstance(value, str) else None


def _lookup_raw(dictionary: dict[str, Any], key: str) -> Any:
    current: Any = dictionary
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current
