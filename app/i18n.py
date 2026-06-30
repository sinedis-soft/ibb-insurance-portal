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

PORTAL_STATUS_LABELS: dict[str, dict[str, str]] = {
    "ru": {
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
    "ka": {
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
}

PORTAL_STATUS_LABELS["ru"].update({"submitting": "Отправляется", "submit_error": "Ошибка отправки"})
PORTAL_STATUS_LABELS["ka"].update({"submitting": "იგზავნება", "submit_error": "გაგზავნის შეცდომა"})

POLICY_STATUS_LABELS: dict[str, dict[str, str]] = {
    "ru": {
        "active": "Действует",
        "expiring_soon": "Скоро истекает",
        "expired": "Истек",
        "cancelled": "Отменен",
        "annulled": "Аннулирован",
        "draft": "Черновик",
    },
    "ka": {
        "active": "მოქმედებს",
        "expiring_soon": "მალე იწურება",
        "expired": "ვადა ამოიწურა",
        "cancelled": "გაუქმებულია",
        "annulled": "ანულირებულია",
        "draft": "შავი ვერსია",
    },
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
            "INVALID_EMAIL": "\u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 email",
            "PARTNER_CLIENT_REQUEST_REQUIRED": "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043a\u043b\u0438\u0435\u043d\u0442\u0430 \u043f\u0430\u0440\u0442\u043d\u0451\u0440\u0430",
            "PARTNER_CLIENT_REQUEST_NOT_FOUND": "\u041a\u043b\u0438\u0435\u043d\u0442 \u043f\u0430\u0440\u0442\u043d\u0451\u0440\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d",
            "PARTNER_CLIENT_NOT_CONFIRMED": "\u0417\u0430\u044f\u0432\u043a\u0443 \u043c\u043e\u0436\u043d\u043e \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u0442\u043e\u043b\u044c\u043a\u043e \u043f\u043e\u0441\u043b\u0435 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u0438 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f \u043a\u043b\u0438\u0435\u043d\u0442\u0430",
            "PARTNER_CLIENT_NOT_EDITABLE": "\u0414\u0430\u043d\u043d\u044b\u0435 \u044d\u0442\u043e\u0433\u043e \u043a\u043b\u0438\u0435\u043d\u0442\u0430 \u0441\u0435\u0439\u0447\u0430\u0441 \u043d\u0435\u043b\u044c\u0437\u044f \u0438\u0437\u043c\u0435\u043d\u0438\u0442\u044c",
            "PARTNER_CLIENT_STATUS_INVALID": "\u041d\u0435\u0434\u043e\u043f\u0443\u0441\u0442\u0438\u043c\u044b\u0439 \u0441\u0442\u0430\u0442\u0443\u0441 \u043a\u043b\u0438\u0435\u043d\u0442\u0430 \u043f\u0430\u0440\u0442\u043d\u0451\u0440\u0430",
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
            "INVALID_EMAIL": "\u10e8\u10d4\u10d0\u10db\u10dd\u10ec\u10db\u10d4\u10d7 email",
            "PARTNER_CLIENT_REQUEST_REQUIRED": "\u10d0\u10d8\u10e0\u10e9\u10d8\u10d4\u10d7 \u10de\u10d0\u10e0\u10e2\u10dc\u10d8\u10dd\u10e0\u10d8\u10e1 \u10d9\u10da\u10d8\u10d4\u10dc\u10e2\u10d8",
            "PARTNER_CLIENT_REQUEST_NOT_FOUND": "\u10de\u10d0\u10e0\u10e2\u10dc\u10d8\u10dd\u10e0\u10d8\u10e1 \u10d9\u10da\u10d8\u10d4\u10dc\u10e2\u10d8 \u10d5\u10d4\u10e0 \u10db\u10dd\u10d8\u10eb\u10d4\u10d1\u10dc\u10d0",
            "PARTNER_CLIENT_NOT_CONFIRMED": "\u10d2\u10d0\u10dc\u10d0\u10ea\u10ee\u10d0\u10d3\u10d8\u10e1 \u10e8\u10d4\u10e5\u10db\u10dc\u10d0 \u10e8\u10d4\u10e1\u10d0\u10eb\u10da\u10d4\u10d1\u10d4\u10da\u10d8\u10d0 \u10db\u10ee\u10dd\u10da\u10dd\u10d3 \u10d9\u10da\u10d8\u10d4\u10dc\u10e2\u10d8\u10e1 \u10e8\u10d4\u10db\u10dd\u10ec\u10db\u10d4\u10d1\u10d8\u10e1\u10d0 \u10d3\u10d0 \u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d8\u10e1 \u10e8\u10d4\u10db\u10d3\u10d4\u10d2",
            "PARTNER_CLIENT_NOT_EDITABLE": "\u10d0\u10db \u10d9\u10da\u10d8\u10d4\u10dc\u10e2\u10d8\u10e1 \u10db\u10dd\u10dc\u10d0\u10ea\u10d4\u10db\u10d4\u10d1\u10d8\u10e1 \u10e8\u10d4\u10ea\u10d5\u10da\u10d0 \u10d0\u10ee\u10da\u10d0 \u10e8\u10d4\u10e3\u10eb\u10da\u10d4\u10d1\u10d4\u10da\u10d8\u10d0",
            "PARTNER_CLIENT_STATUS_INVALID": "\u10de\u10d0\u10e0\u10e2\u10dc\u10d8\u10dd\u10e0\u10d8\u10e1 \u10d9\u10da\u10d8\u10d4\u10dc\u10e2\u10d8\u10e1 \u10e1\u10e2\u10d0\u10e2\u10e3\u10e1\u10d8 \u10d3\u10d0\u10e3\u10e8\u10d5\u10d4\u10d1\u10d4\u10da\u10d8\u10d0",
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


MESSAGES["ru"]["errors"].update(
    {
        "AUTO_PRODUCT_NOT_AVAILABLE": "Этот продукт недоступен для выбранной страны регистрации и зоны покрытия",
        "AUTO_PRODUCT_RULE_NOT_FOUND": "Правило доступности продукта не найдено",
        "AUTO_APPLICATION_VALIDATION_FAILED": "Проверьте данные авто-заявки",
        "AUTO_DRAFT_NOT_EDITABLE": "Этот черновик нельзя редактировать",
        "AUTO_REQUIRED_FIELD_MISSING": "Заполните обязательное поле",
        "AUTO_INVALID_COUNTRY_COMBINATION": "Недопустимая комбинация стран",
        "AUTO_INVALID_PERIOD": "Недопустимый период страхования",
        "AUTO_DOCUMENT_REQUIRED": "Требуется документ",
        "COMPANY_CONTEXT_REQUIRED": "Выберите компанию",
        "CLIENT_VIEWER_READ_ONLY": "Пользователь с ролью наблюдателя не может создавать заявки",
    }
)
MESSAGES["ka"]["errors"].update(
    {
        "AUTO_PRODUCT_NOT_AVAILABLE": "ეს პროდუქტი არჩეული რეგისტრაციის ქვეყნისა და დაფარვის ზონისთვის ხელმისაწვდომი არ არის",
        "AUTO_PRODUCT_RULE_NOT_FOUND": "პროდუქტის ხელმისაწვდომობის წესი ვერ მოიძებნა",
        "AUTO_APPLICATION_VALIDATION_FAILED": "შეამოწმეთ ავტო-განაცხადის მონაცემები",
        "AUTO_DRAFT_NOT_EDITABLE": "ამ შავი ვერსიის რედაქტირება შეუძლებელია",
        "AUTO_REQUIRED_FIELD_MISSING": "შეავსეთ სავალდებულო ველი",
        "AUTO_INVALID_COUNTRY_COMBINATION": "ქვეყნების კომბინაცია დაუშვებელია",
        "AUTO_INVALID_PERIOD": "დაზღვევის პერიოდი არასწორია",
        "AUTO_DOCUMENT_REQUIRED": "საჭიროა დოკუმენტი",
        "COMPANY_CONTEXT_REQUIRED": "აირჩიეთ კომპანია",
        "CLIENT_VIEWER_READ_ONLY": "დამკვირვებლის როლი განაცხადს ვერ ქმნის",
    }
)
MESSAGES["ru"]["autoProducts"] = {
    "border_oc": {
        "label": "Пограничное OC",
        "description": "Пограничное автострахование для поездок в Европу",
    },
    "green_card": {"label": "Green Card", "description": "Зеленая карта для международного движения"},
    "osago_rf": {
        "label": "ОСАГО РФ",
        "description": "ОСАГО РФ для транспортных средств с иностранной регистрацией",
    },
    "pl_oc": {"label": "Польское OC", "description": "Обязательное страхование ответственности в Польше"},
    "pl_ac": {"label": "Польское AC", "description": "Добровольное страхование автомобиля в Польше"},
    "casco": {"label": "CASCO", "description": "Страхование автомобиля от ущерба"},
    "assistance": {"label": "Assistance", "description": "Помощь на дороге"},
    "nnw": {"label": "NNW", "description": "Страхование от несчастных случаев"},
}
MESSAGES["ka"]["autoProducts"] = {
    "border_oc": {
        "label": "სასაზღვრო OC",
        "description": "სასაზღვრო ავტოდაზღვევა ევროპაში მგზავრობისთვის",
    },
    "green_card": {"label": "Green Card", "description": "მწვანე ბარათი საერთაშორისო მოძრაობისთვის"},
    "osago_rf": {
        "label": "რუსეთის ОСАГО",
        "description": "რუსეთის ОСАГО უცხოური რეგისტრაციის ავტომობილებისთვის",
    },
    "pl_oc": {"label": "პოლონური OC", "description": "პასუხისმგებლობის სავალდებულო დაზღვევა პოლონეთში"},
    "pl_ac": {"label": "პოლონური AC", "description": "ავტომობილის ნებაყოფლობითი დაზღვევა პოლონეთში"},
    "casco": {"label": "CASCO", "description": "ავტომობილის დაზღვევა დაზიანებისგან"},
    "assistance": {"label": "Assistance", "description": "გზაზე დახმარება"},
    "nnw": {"label": "NNW", "description": "უბედური შემთხვევის დაზღვევა"},
}


for locale in ("ru", "ka"):
    MESSAGES[locale]["errors"].update(
        {
            "CARGO_APPLICATION_TYPE_REQUIRED": "Select cargo application type.",
            "CARGO_APPLICATION_TYPE_INVALID": "Cargo application type is invalid.",
            "CARGO_ROUTE_REQUIRED": "Provide the shipment route.",
            "CARGO_COUNTRY_FROM_REQUIRED": "Provide country from.",
            "CARGO_COUNTRY_TO_REQUIRED": "Provide country to.",
            "CARGO_VALUE_REQUIRED": "Provide cargo value.",
            "CARGO_VALUE_INVALID": "Cargo value must be greater than zero.",
            "CARGO_CURRENCY_REQUIRED": "Provide currency.",
            "CARGO_TRANSPORT_TYPE_REQUIRED": "Select transport type.",
            "CARGO_DOCUMENT_REQUIRED": "A document is required for submit.",
            "CARGO_ACTIVE_CONTRACT_REQUIRED": "Active contract is required for contract coverage.",
            "CARGO_CERTIFICATE_CONTRACT_REQUIRED": "Active contract and certificate request are required for certificate.",
            "CARGO_DRAFT_NOT_EDITABLE": "This draft cannot be edited.",
            "CARGO_APPLICATION_VALIDATION_FAILED": "Check cargo application data.",
        }
    )
    MESSAGES[locale]["cargoApplicationTypes"] = {
        "single_shipment": {"label": "Single shipment"},
        "contract_coverage": {"label": "Contract coverage"},
        "certificate": {"label": "Certificate"},
    }
    MESSAGES[locale]["cargoTypes"] = {
        "general_cargo": {"label": "General cargo"},
        "perishable": {"label": "Perishable cargo"},
        "dangerous": {"label": "Dangerous cargo"},
        "vehicle": {"label": "Vehicle"},
        "equipment": {"label": "Equipment"},
        "other": {"label": "Other"},
    }
    MESSAGES[locale]["cargoTransportTypes"] = {
        "road": {"label": "Road"},
        "rail": {"label": "Rail"},
        "sea": {"label": "Sea"},
        "air": {"label": "Air"},
        "multimodal": {"label": "Multimodal"},
    }
    MESSAGES[locale]["cargoDocumentTypes"] = {
        "request_document": {"label": "Request document"},
        "invoice": {"label": "Invoice"},
        "cmr": {"label": "CMR"},
        "contract": {"label": "Contract"},
        "certificate": {"label": "Certificate"},
        "other": {"label": "Other document"},
    }


for locale in ("ru", "ka"):
    MESSAGES[locale]["errors"].update(
        {
            "PORTAL_APPLICATIONS_NOT_ALLOWED": "Portal applications are not allowed for this company.",
            "AUTO_APPLICATIONS_NOT_ALLOWED": "Auto applications are not allowed for this company.",
            "AUTO_ERGO_LV_NOT_ALLOWED": "ERGO LV auto applications are not allowed.",
            "AUTO_DIONIS_NOT_ALLOWED": "DIONIS auto applications are not allowed.",
            "AUTO_DEDA_NOT_ALLOWED": "DEDA auto applications are not allowed.",
            "AUTO_RUSSIAN_INSURERS_NOT_ALLOWED": "Russian insurer auto applications are not allowed.",
            "AUTO_BELARUSIAN_INSURERS_NOT_ALLOWED": "Belarusian insurer auto applications are not allowed.",
            "AUTO_POLISH_INSURERS_NOT_ALLOWED": "Polish insurer auto applications are not allowed.",
            "CARGO_DIONIS_NOT_ALLOWED": "DIONIS cargo applications are not allowed.",
            "CARGO_DEDA_NOT_ALLOWED": "DEDA cargo applications are not allowed.",
            "CARGO_RUSSIAN_INSURERS_NOT_ALLOWED": "Russian insurer cargo applications are not allowed.",
            "CARGO_BELARUSIAN_INSURERS_NOT_ALLOWED": "Belarusian insurer cargo applications are not allowed.",
            "CARGO_POLISH_INSURERS_NOT_ALLOWED": "Polish insurer cargo applications are not allowed.",
            "DOCUMENT_UPLOAD_FAILED": "Document upload failed.",
            "DOCUMENT_UPLOAD_NOT_ALLOWED": "Document upload is not allowed.",
            "DOCUMENT_DELETE_NOT_ALLOWED": "Document deletion is not allowed.",
            "DOCUMENT_TYPE_REQUIRED": "A document of the required type is needed.",
            "DOCUMENT_TYPE_INVALID": "Document type is not allowed.",
            "DOCUMENT_TOO_LARGE": "The file is too large.",
            "DOCUMENT_EXTENSION_NOT_ALLOWED": "This file type is not allowed.",
            "DOCUMENT_MIME_NOT_ALLOWED": "This file content type is not allowed.",
            "DOCUMENT_LIMIT_EXCEEDED": "Document limit exceeded.",
            "DOCUMENT_APPLICATION_STATUS_NOT_ALLOWED": "Documents cannot be changed in the current application status.",
            "DOCUMENT_DOWNLOAD_NOT_AVAILABLE": "Document download is not available.",
            "DOCUMENT_ALREADY_SENT": "The document has already been sent.",
            "DOCUMENT_TRANSFER_FAILED": "Document transfer failed.",
            "DOCUMENT_TEMPORARY_FILE_EXPIRED": "Temporary document file expired.",
            "DOCUMENT_REUPLOAD_REQUIRED": "Please upload the document again.",
            "DOCUMENT_REQUIRED": "A document is required.",
            "APPLICATION_SUBMIT_FAILED": "Application submit failed.",
            "BITRIX_SYNC_FAILED": "Bitrix24 sync failed.",
            "BITRIX_DEAL_CREATE_FAILED": "Bitrix24 deal creation failed.",
        }
    )

MESSAGES["ru"]["errors"].update(
    {
        "DOCUMENT_UPLOAD_FAILED": "Не удалось загрузить документ.",
        "DOCUMENT_DELETE_NOT_ALLOWED": "Удаление документа сейчас недоступно.",
        "DOCUMENT_TYPE_REQUIRED": "Требуется документ нужного типа.",
        "DOCUMENT_TYPE_INVALID": "Недопустимый тип документа.",
        "DOCUMENT_TOO_LARGE": "Файл слишком большой.",
        "DOCUMENT_EXTENSION_NOT_ALLOWED": "Расширение файла не разрешено.",
        "DOCUMENT_MIME_NOT_ALLOWED": "Тип содержимого файла не разрешен.",
        "DOCUMENT_LIMIT_EXCEEDED": "Превышен лимит документов.",
        "DOCUMENT_APPLICATION_STATUS_NOT_ALLOWED": "В текущем статусе заявки документы менять нельзя.",
        "DOCUMENT_DOWNLOAD_NOT_AVAILABLE": "Скачивание документа недоступно.",
        "DOCUMENT_ALREADY_SENT": "Документ уже отправлен.",
        "DOCUMENT_TRANSFER_FAILED": "Не удалось передать документ.",
        "DOCUMENT_TEMPORARY_FILE_EXPIRED": "Временный файл документа истек.",
        "DOCUMENT_REUPLOAD_REQUIRED": "Загрузите документ повторно.",
        "DOCUMENT_REQUIRED": "Требуется документ.",
    }
)

MESSAGES["ka"]["errors"].update(
    {
        "DOCUMENT_UPLOAD_FAILED": "დოკუმენტის ატვირთვა ვერ მოხერხდა.",
        "DOCUMENT_DELETE_NOT_ALLOWED": "დოკუმენტის წაშლა ახლა მიუწვდომელია.",
        "DOCUMENT_TYPE_REQUIRED": "საჭიროა შესაბამისი ტიპის დოკუმენტი.",
        "DOCUMENT_TYPE_INVALID": "დოკუმენტის ტიპი დაუშვებელია.",
        "DOCUMENT_TOO_LARGE": "ფაილი ძალიან დიდია.",
        "DOCUMENT_EXTENSION_NOT_ALLOWED": "ფაილის გაფართოება დაუშვებელია.",
        "DOCUMENT_MIME_NOT_ALLOWED": "ფაილის შიგთავსის ტიპი დაუშვებელია.",
        "DOCUMENT_LIMIT_EXCEEDED": "დოკუმენტების ლიმიტი გადაჭარბებულია.",
        "DOCUMENT_APPLICATION_STATUS_NOT_ALLOWED": "განაცხადის ამ სტატუსში დოკუმენტების შეცვლა შეუძლებელია.",
        "DOCUMENT_DOWNLOAD_NOT_AVAILABLE": "დოკუმენტის ჩამოტვირთვა მიუწვდომელია.",
        "DOCUMENT_ALREADY_SENT": "დოკუმენტი უკვე გაგზავნილია.",
        "DOCUMENT_TRANSFER_FAILED": "დოკუმენტის გადაცემა ვერ მოხერხდა.",
        "DOCUMENT_TEMPORARY_FILE_EXPIRED": "დროებითი დოკუმენტის ფაილს ვადა გაუვიდა.",
        "DOCUMENT_REUPLOAD_REQUIRED": "გთხოვთ, დოკუმენტი ხელახლა ატვირთოთ.",
        "DOCUMENT_REQUIRED": "საჭიროა დოკუმენტი.",
    }
)

for locale in SUPPORTED_LOCALES:
    MESSAGES[locale]["errors"].update(
        {
            "APPLICATION_ALREADY_SUBMITTED": "Application has already been submitted.",
            "APPLICATION_SUBMIT_IN_PROGRESS": "Application submit is already in progress.",
            "APPLICATION_SUBMIT_FAILED": "Application submit failed.",
            "BITRIX_DEAL_CREATE_FAILED": "Bitrix24 deal creation failed.",
            "BITRIX_DEAL_LOOKUP_FAILED": "Bitrix24 deal lookup failed.",
            "BITRIX_FIELD_MAPPING_MISSING": "Bitrix24 field mapping is missing.",
            "BITRIX_COMPANY_ID_MISSING": "Bitrix24 company ID is missing.",
            "BITRIX_CONTACT_ID_MISSING": "Bitrix24 contact ID is missing.",
            "BITRIX_SYNC_FAILED": "Bitrix24 sync failed.",
            "DOCUMENT_TRANSFER_QUEUED": "Document transfer has been queued.",
            "DOCUMENT_TRANSFER_FAILED": "Document transfer failed.",
        }
    )

MESSAGES["ru"]["errors"].update(
    {
        "APPLICATION_ALREADY_SUBMITTED": "Заявка уже отправлена.",
        "APPLICATION_SUBMIT_IN_PROGRESS": "Отправка заявки уже выполняется.",
        "APPLICATION_SUBMIT_FAILED": "Не удалось отправить заявку.",
        "BITRIX_DEAL_CREATE_FAILED": "Не удалось создать сделку Bitrix24.",
        "BITRIX_DEAL_LOOKUP_FAILED": "Не удалось проверить существующую сделку Bitrix24.",
        "BITRIX_FIELD_MAPPING_MISSING": "Не настроено поле Bitrix24 для синхронизации.",
        "BITRIX_COMPANY_ID_MISSING": "Не указан ID компании Bitrix24.",
        "BITRIX_CONTACT_ID_MISSING": "Не указан ID контакта Bitrix24.",
        "BITRIX_SYNC_FAILED": "Не удалось синхронизировать Bitrix24.",
        "DOCUMENT_TRANSFER_QUEUED": "Передача документов поставлена в очередь.",
        "DOCUMENT_TRANSFER_FAILED": "Не удалось передать документ.",
    }
)
MESSAGES["ka"]["errors"].update(
    {
        "APPLICATION_ALREADY_SUBMITTED": "განაცხადი უკვე გაგზავნილია.",
        "APPLICATION_SUBMIT_IN_PROGRESS": "განაცხადის გაგზავნა უკვე მიმდინარეობს.",
        "APPLICATION_SUBMIT_FAILED": "განაცხადის გაგზავნა ვერ მოხერხდა.",
        "BITRIX_DEAL_CREATE_FAILED": "Bitrix24-ში გარიგების შექმნა ვერ მოხერხდა.",
        "BITRIX_DEAL_LOOKUP_FAILED": "არსებული Bitrix24 გარიგების შემოწმება ვერ მოხერხდა.",
        "BITRIX_FIELD_MAPPING_MISSING": "Bitrix24-ის სინქრონიზაციის ველი არ არის დაყენებული.",
        "BITRIX_COMPANY_ID_MISSING": "Bitrix24 კომპანიის ID არ არის მითითებული.",
        "BITRIX_CONTACT_ID_MISSING": "Bitrix24 კონტაქტის ID არ არის მითითებული.",
        "BITRIX_SYNC_FAILED": "Bitrix24 სინქრონიზაცია ვერ მოხერხდა.",
        "DOCUMENT_TRANSFER_QUEUED": "დოკუმენტების გადაცემა რიგშია.",
        "DOCUMENT_TRANSFER_FAILED": "დოკუმენტის გადაცემა ვერ მოხერხდა.",
    }
)


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


def portal_status_label(locale: str | None, portal_status: str) -> str:
    normalized = normalize_locale(locale)
    labels = PORTAL_STATUS_LABELS.get(normalized, PORTAL_STATUS_LABELS[DEFAULT_LOCALE])
    return labels.get(portal_status, PORTAL_STATUS_LABELS[DEFAULT_LOCALE].get(portal_status, portal_status))


def policy_status_label(locale: str | None, policy_status: str) -> str:
    normalized = normalize_locale(locale)
    labels = POLICY_STATUS_LABELS.get(normalized, POLICY_STATUS_LABELS[DEFAULT_LOCALE])
    return labels.get(policy_status, POLICY_STATUS_LABELS[DEFAULT_LOCALE].get(policy_status, policy_status))


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
