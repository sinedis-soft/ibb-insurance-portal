from __future__ import annotations

ROLES = [
    {"code": "client_executor", "name_ru": "Клиент-исполнитель", "name_ka": "კლიენტი შემსრულებელი", "is_system": True, "is_active": True},
    {"code": "client_admin", "name_ru": "Клиент-администратор", "name_ka": "კლიენტი ადმინისტრატორი", "is_system": True, "is_active": True},
    {"code": "client_viewer", "name_ru": "Клиент-наблюдатель", "name_ka": "კლიენტი დამკვირვებელი", "is_system": True, "is_active": True},
    {"code": "partner", "name_ru": "Партнёр", "name_ka": "პარტნიორი", "is_system": True, "is_active": True},
    {"code": "superadmin", "name_ru": "Суперадмин", "name_ka": "სუპერადმინისტრატორი", "is_system": True, "is_active": True},
]

COUNTRIES = [
    {"code": "poland", "name_ru": "Польша", "name_ka": "პოლონეთი", "iso2": "PL", "iso3": "POL", "sort_order": 10},
    {"code": "kazakhstan", "name_ru": "Казахстан", "name_ka": "ყაზახეთი", "iso2": "KZ", "iso3": "KAZ", "sort_order": 20},
    {"code": "georgia", "name_ru": "Грузия", "name_ka": "საქართველო", "iso2": "GE", "iso3": "GEO", "sort_order": 30},
    {"code": "belarus", "name_ru": "Беларусь", "name_ka": "ბელარუსი", "iso2": "BY", "iso3": "BLR", "sort_order": 40},
    {"code": "russia", "name_ru": "Россия", "name_ka": "რუსეთი", "iso2": "RU", "iso3": "RUS", "sort_order": 50},
    {"code": "latvia", "name_ru": "Латвия", "name_ka": "ლატვია", "iso2": "LV", "iso3": "LVA", "sort_order": 60},
    {"code": "lithuania", "name_ru": "Литва", "name_ka": "ლიტვა", "iso2": "LT", "iso3": "LTU", "sort_order": 70},
    {"code": "european_union", "name_ru": "EU / European Union", "name_ka": "ევროკავშირი", "iso2": None, "iso3": None, "sort_order": 80},
    {"code": "other", "name_ru": "Другое", "name_ka": "სხვა", "iso2": None, "iso3": None, "sort_order": 999},
]

LANGUAGES = [
    {"code": "ru", "name": "Russian", "native_name": "Русский", "is_default": True, "is_active": True},
    {"code": "ka", "name": "Georgian", "native_name": "ქართული", "is_default": False, "is_active": True},
]

PRODUCT_GROUPS = [
    {"code": "auto", "name_ru": "Автострахование", "name_ka": "ავტოდაზღვევა", "sort_order": 10},
    {"code": "cargo", "name_ru": "Страхование грузов", "name_ka": "ტვირთის დაზღვევა", "sort_order": 20},
]

PRODUCT_TYPES = [
    {"group_code": "auto", "code": "osago_rf_non_resident", "name_ru": "ОСАГО РФ для нерезидентов", "name_ka": "რუსეთის ОСАГО არარეზიდენტებისთვის", "sort_order": 10},
    {"group_code": "auto", "code": "osago_kz_non_resident", "name_ru": "ОСАГО для ТС с казахской регистрацией", "name_ka": "ОСАГО ყაზახური რეგისტრაციის ტრანსპორტისთვის", "sort_order": 20},
    {"group_code": "auto", "code": "green_card_kz", "name_ru": "Green Card для казахской регистрации", "name_ka": "Green Card ყაზახური რეგისტრაციისთვის", "sort_order": 30},
    {"group_code": "auto", "code": "green_card_ge", "name_ru": "Green Card для грузинской регистрации", "name_ka": "Green Card ქართული რეგისტრაციისთვის", "sort_order": 40},
    {"group_code": "auto", "code": "rocta", "name_ru": "ROCTA", "name_ka": "ROCTA", "sort_order": 50},
    {"group_code": "cargo", "code": "cargo_single_shipment", "name_ru": "Разовая перевозка", "name_ka": "ერთჯერადი გადაზიდვა", "sort_order": 10},
    {"group_code": "cargo", "code": "cargo_contract_cover", "name_ru": "Договорное покрытие", "name_ka": "საკონტრაქტო დაფარვა", "sort_order": 20},
    {"group_code": "cargo", "code": "cargo_document_request", "name_ru": "Запрос документа по договору", "name_ka": "დოკუმენტის მოთხოვნა ხელშეკრულებით", "sort_order": 30},
]

PORTAL_STATUSES = [
    {"code": "draft", "name_ru": "Черновик", "name_ka": "შავი ვერსია", "is_final": False, "sort_order": 10},
    {"code": "received", "name_ru": "Получена заявка", "name_ka": "განაცხადი მიღებულია", "is_final": False, "sort_order": 20},
    {"code": "approval_pending", "name_ru": "Ожидает согласования", "name_ka": "ელოდება შეთანხმებას", "is_final": False, "sort_order": 30},
    {"code": "returned_for_revision", "name_ru": "Возвращена на исправление", "name_ka": "დაბრუნებულია შესასწორებლად", "is_final": False, "sort_order": 40},
    {"code": "sent_to_work", "name_ru": "Отправлена в работу", "name_ka": "გაგზავნილია სამუშაოდ", "is_final": False, "sort_order": 50},
    {"code": "in_work", "name_ru": "В работе", "name_ka": "მუშავდება", "is_final": False, "sort_order": 60},
    {"code": "documents_expected", "name_ru": "Ожидаются документы", "name_ka": "ელოდება დოკუმენტებს", "is_final": False, "sort_order": 70},
    {"code": "signed_documents_expected", "name_ru": "Ожидаются подписанные документы", "name_ka": "ელოდება ხელმოწერილ დოკუმენტებს", "is_final": False, "sort_order": 80},
    {"code": "payment_expected", "name_ru": "Ожидается оплата", "name_ka": "ელოდება გადახდას", "is_final": False, "sort_order": 90},
    {"code": "insurer_review", "name_ru": "На согласовании со страховой", "name_ka": "სადაზღვევოს განხილვაზეა", "is_final": False, "sort_order": 100},
    {"code": "policy_issuing", "name_ru": "Выпускается полис", "name_ka": "პოლისი მზადდება", "is_final": False, "sort_order": 110},
    {"code": "policy_issued", "name_ru": "Полис выпущен", "name_ka": "პოლისი გამოშვებულია", "is_final": True, "sort_order": 120},
    {"code": "rejected", "name_ru": "Отказано", "name_ka": "უარყოფილია", "is_final": True, "sort_order": 130},
    {"code": "cancelled", "name_ru": "Отменено", "name_ka": "გაუქმებულია", "is_final": True, "sort_order": 140},
    {"code": "annulled", "name_ru": "Аннулировано", "name_ka": "ანულირებულია", "is_final": True, "sort_order": 150},
]

BITRIX_CATEGORIES = [
    {"bitrix_category_id": 0, "code": "auto", "name": "АВТОСТРАХОВАНИЕ (default)", "is_active": True},
    {"bitrix_category_id": 19, "code": "cargo", "name": "ГРУЗЫ", "is_active": True},
]

BITRIX_STAGE_MAPPINGS = [
    {"bitrix_category_id": 0, "bitrix_stage_id": "NEW", "portal_status": "received", "allowed_client_action": "withdraw"},
    {"bitrix_category_id": 0, "bitrix_stage_id": "PREPARATION", "portal_status": "in_work", "allowed_client_action": "withdraw"},
    {"bitrix_category_id": 0, "bitrix_stage_id": "PREPAYMENT_INVOICE", "portal_status": "payment_expected", "allowed_client_action": "upload_payment_documents"},
    {"bitrix_category_id": 0, "bitrix_stage_id": "UC_P4KMQB", "portal_status": "insurer_review", "allowed_client_action": None},
    {"bitrix_category_id": 0, "bitrix_stage_id": "EXECUTING", "portal_status": "policy_issued", "allowed_client_action": "policy_after_issue_actions"},
    {"bitrix_category_id": 0, "bitrix_stage_id": "UC_J37SCC", "portal_status": "signed_documents_expected", "allowed_client_action": "upload_signed_documents"},
    {"bitrix_category_id": 0, "bitrix_stage_id": "FINAL_INVOICE", "portal_status": "policy_issued", "allowed_client_action": "policy_after_issue_actions"},
    {"bitrix_category_id": 0, "bitrix_stage_id": "UC_KUX5LN", "portal_status": "policy_issued", "allowed_client_action": "policy_after_issue_actions"},
    {"bitrix_category_id": 0, "bitrix_stage_id": "UC_VEK6VN", "portal_status": "in_work", "is_visible_to_client": False, "is_visible_to_partner": False, "allowed_client_action": None},
    {"bitrix_category_id": 0, "bitrix_stage_id": "WON", "portal_status": "policy_issued", "allowed_client_action": "policy_after_issue_actions"},
    {"bitrix_category_id": 0, "bitrix_stage_id": "LOSE", "portal_status": "rejected", "allowed_client_action": None},
    {"bitrix_category_id": 0, "bitrix_stage_id": "UC_RUOFYB", "portal_status": "cancelled", "allowed_client_action": None},
    {"bitrix_category_id": 0, "bitrix_stage_id": "UC_YD1LLO", "portal_status": "cancelled", "allowed_client_action": None},
    {"bitrix_category_id": 0, "bitrix_stage_id": "UC_NMOF7M", "portal_status": "cancelled", "allowed_client_action": None},
    {"bitrix_category_id": 0, "bitrix_stage_id": "APOLOGY", "portal_status": "annulled", "allowed_client_action": None},
    {"bitrix_category_id": 19, "bitrix_stage_id": "C19:NEW", "portal_status": "received", "allowed_client_action": "withdraw"},
    {"bitrix_category_id": 19, "bitrix_stage_id": "C19:UC_NK7MTA", "portal_status": "in_work", "allowed_client_action": "withdraw"},
    {"bitrix_category_id": 19, "bitrix_stage_id": "C19:UC_WKJMVP", "portal_status": "payment_expected", "allowed_client_action": "upload_payment_documents"},
    {"bitrix_category_id": 19, "bitrix_stage_id": "C19:PREPARATION", "portal_status": "in_work", "allowed_client_action": "withdraw"},
    {"bitrix_category_id": 19, "bitrix_stage_id": "C19:PREPAYMENT_INVOIC", "portal_status": "insurer_review", "allowed_client_action": None},
    {"bitrix_category_id": 19, "bitrix_stage_id": "C19:EXECUTING", "portal_status": "in_work", "allowed_client_action": None},
    {"bitrix_category_id": 19, "bitrix_stage_id": "C19:FINAL_INVOICE", "portal_status": "policy_issued", "allowed_client_action": "policy_after_issue_actions"},
    {"bitrix_category_id": 19, "bitrix_stage_id": "C19:WON", "portal_status": "policy_issued", "allowed_client_action": "policy_after_issue_actions"},
    {"bitrix_category_id": 19, "bitrix_stage_id": "C19:LOSE", "portal_status": "cancelled", "allowed_client_action": None},
    {"bitrix_category_id": 19, "bitrix_stage_id": "C19:APOLOGY", "portal_status": "annulled", "allowed_client_action": None},
]

REQUIRED_REFERENCE_CODES = {
    "roles": [row["code"] for row in ROLES],
    "languages": [row["code"] for row in LANGUAGES],
    "product_groups": [row["code"] for row in PRODUCT_GROUPS],
    "portal_statuses": [row["code"] for row in PORTAL_STATUSES],
    "bitrix_categories": [0, 19],
}
