from __future__ import annotations

ROLES = [
    {"code": "client_executor", "name_ru": "Клиент-исполнитель", "name_ka": "კლიენტი შემსრულებელი", "is_system": True, "is_active": True},
    {"code": "client_admin", "name_ru": "Клиент-администратор", "name_ka": "კლიენტი ადმინისტრატორი", "is_system": True, "is_active": True},
    {"code": "client_viewer", "name_ru": "Клиент-наблюдатель", "name_ka": "კლიენტი დამკვირვებელი", "is_system": True, "is_active": True},
    {"code": "partner", "name_ru": "Партнёр", "name_ka": "პარტნიორი", "is_system": True, "is_active": True},
    {"code": "superadmin", "name_ru": "Суперадмин", "name_ka": "სუპერადმინისტრატორი", "is_system": True, "is_active": True},
]

COUNTRIES = [
    {"code": "PL", "name_ru": "Польша", "name_ka": "პოლონეთი", "iso2": "PL", "iso3": "POL", "sort_order": 10},
    {"code": "KZ", "name_ru": "Казахстан", "name_ka": "ყაზახეთი", "iso2": "KZ", "iso3": "KAZ", "sort_order": 20},
    {"code": "GE", "name_ru": "Грузия", "name_ka": "საქართველო", "iso2": "GE", "iso3": "GEO", "sort_order": 30},
    {"code": "BY", "name_ru": "Беларусь", "name_ka": "ბელარუსი", "iso2": "BY", "iso3": "BLR", "sort_order": 40},
    {"code": "RU", "name_ru": "Россия", "name_ka": "რუსეთი", "iso2": "RU", "iso3": "RUS", "sort_order": 50},
    {"code": "LV", "name_ru": "Латвия", "name_ka": "ლატვია", "iso2": "LV", "iso3": "LVA", "sort_order": 60},
    {"code": "LT", "name_ru": "Литва", "name_ka": "ლიეტუვა", "iso2": "LT", "iso3": "LTU", "sort_order": 70},
    {"code": "EU", "name_ru": "Европейский союз", "name_ka": "ევროკავშირი", "iso2": None, "iso3": None, "sort_order": 80},
    {"code": "OTHER", "name_ru": "Другое", "name_ka": "სხვა", "iso2": None, "iso3": None, "sort_order": 999},
]

LANGUAGES = [
    {"code": "ru", "name": "Russian", "native_name": "Русский", "is_default": True, "is_active": True},
    {"code": "ka", "name": "Georgian", "native_name": "ქართული", "is_default": False, "is_active": True},
]

LANGUAGES.extend(
    [
        {"code": "be", "name": "Belarusian", "native_name": "Беларусский", "is_default": False, "is_active": True},
        {"code": "uk", "name": "Ukrainian", "native_name": "Украинский", "is_default": False, "is_active": True},
        {"code": "hy", "name": "Armenian", "native_name": "Армянский", "is_default": False, "is_active": True},
        {"code": "tr", "name": "Turkish", "native_name": "Турецкий", "is_default": False, "is_active": True},
        {"code": "az", "name": "Azerbaijani", "native_name": "Азербайджанский", "is_default": False, "is_active": True},
        {"code": "kk", "name": "Kazakh", "native_name": "Казахский", "is_default": False, "is_active": True},
        {"code": "uz", "name": "Uzbek", "native_name": "Узбекский", "is_default": False, "is_active": True},
        {"code": "ky", "name": "Kyrgyz", "native_name": "Кыргызский", "is_default": False, "is_active": True},
        {"code": "en", "name": "English", "native_name": "Английский", "is_default": False, "is_active": True},
        {"code": "pl", "name": "Polish", "native_name": "Польский", "is_default": False, "is_active": True},
        {"code": "ar", "name": "Arabic", "native_name": "Арабский", "is_default": False, "is_active": True},
        {"code": "ckb", "name": "Central Kurdish", "native_name": "Центральнокурдский (сорани)", "is_default": False, "is_active": True},
        {"code": "kmr", "name": "Northern Kurdish", "native_name": "Севернокурдский (курманджи)", "is_default": False, "is_active": True},
        {"code": "ro", "name": "Romanian", "native_name": "Румынский", "is_default": False, "is_active": True},
        {"code": "sr", "name": "Serbian", "native_name": "Сербский", "is_default": False, "is_active": True},
        {"code": "sq", "name": "Albanian", "native_name": "Албанский", "is_default": False, "is_active": True},
        {"code": "fa", "name": "Persian", "native_name": "Персидский", "is_default": False, "is_active": True},
        {"code": "he", "name": "Hebrew", "native_name": "Иврит", "is_default": False, "is_active": True},
        {"code": "mn", "name": "Mongolian", "native_name": "Монгольский", "is_default": False, "is_active": True},
    ]
)

PRODUCT_GROUPS = [
    {"code": "auto", "name_ru": "Автострахование", "name_ka": "ავტოდაზღვევა", "sort_order": 10},
    {"code": "cargo", "name_ru": "Страхование грузов", "name_ka": "ტვირთის დაზღვევა", "sort_order": 20},
]

PRODUCT_TYPES = [
    {"group_code": "auto", "code": "osago_rf_non_resident", "name_ru": "ОСАГО РФ для нерезидентов", "name_ka": "რუსეთის ОСАГО არარეზიდენტებისთვის", "sort_order": 10},
    {"group_code": "auto", "code": "osago_kz_non_resident", "name_ru": "ОСАГО для ТС с казахстанской регистрацией", "name_ka": "ОСАГО ყაზახური რეგისტრაციის ტრანსპორტისთვის", "sort_order": 20},
    {"group_code": "auto", "code": "green_card_kz", "name_ru": "Green Card для казахстанской регистрации", "name_ka": "Green Card ყაზახური რეგისტრაციისთვის", "sort_order": 30},
    {"group_code": "auto", "code": "green_card_ge", "name_ru": "Green Card для грузинской регистрации", "name_ka": "Green Card ქართული რეგისტრაციისთვის", "sort_order": 40},
    {"group_code": "auto", "code": "rocta", "name_ru": "ROCTA", "name_ka": "ROCTA", "sort_order": 50},
    {"group_code": "cargo", "code": "cargo_single_shipment", "name_ru": "Разовая перевозка", "name_ka": "ერთჯერადი გადაზიდვა", "sort_order": 10},
    {"group_code": "cargo", "code": "cargo_contract_cover", "name_ru": "Договорное покрытие", "name_ka": "საკონტრაქტო დაფარვა", "sort_order": 20},
    {"group_code": "cargo", "code": "cargo_document_request", "name_ru": "Запрос документа по договору", "name_ka": "დოკუმენტის მოთხოვნა ხელშეკრულებით", "sort_order": 30},
]

AUTO_PRODUCTS = [
    {"code": "border_oc", "sort_order": 10, "is_active": True},
    {"code": "green_card", "sort_order": 20, "is_active": True},
    {"code": "osago_rf", "sort_order": 30, "is_active": True},
    {"code": "pl_oc", "sort_order": 40, "is_active": True},
    {"code": "pl_ac", "sort_order": 50, "is_active": True},
    {"code": "casco", "sort_order": 60, "is_active": True},
    {"code": "assistance", "sort_order": 70, "is_active": True},
    {"code": "nnw", "sort_order": 80, "is_active": True},
]

AUTO_PRODUCT_RULES = [
    {
        "product_code": "border_oc",
        "company_country_code": None,
        "vehicle_registration_country_code": None,
        "coverage_country_code": None,
        "coverage_zone_code": "EU",
        "allowed_user_types": ["client"],
        "allowed_role_codes": ["client_admin", "client_executor"],
        "requires_manual_review": False,
        "is_active": True,
        "priority": 100,
    },
    {
        "product_code": "green_card",
        "company_country_code": "KZ",
        "vehicle_registration_country_code": "KZ",
        "coverage_country_code": None,
        "coverage_zone_code": "EU",
        "allowed_user_types": ["client"],
        "allowed_role_codes": ["client_admin", "client_executor"],
        "requires_manual_review": False,
        "is_active": True,
        "priority": 90,
    },
    {
        "product_code": "osago_rf",
        "company_country_code": None,
        "vehicle_registration_country_code": None,
        "coverage_country_code": "RU",
        "coverage_zone_code": None,
        "allowed_user_types": ["client"],
        "allowed_role_codes": ["client_admin", "client_executor"],
        "requires_manual_review": False,
        "is_active": True,
        "priority": 80,
    },
    {
        "product_code": "pl_oc",
        "company_country_code": "PL",
        "vehicle_registration_country_code": "PL",
        "coverage_country_code": "PL",
        "coverage_zone_code": None,
        "allowed_user_types": ["client"],
        "allowed_role_codes": ["client_admin", "client_executor"],
        "requires_manual_review": False,
        "is_active": True,
        "priority": 70,
    },
    {
        "product_code": "pl_ac",
        "company_country_code": "PL",
        "vehicle_registration_country_code": "PL",
        "coverage_country_code": "PL",
        "coverage_zone_code": None,
        "allowed_user_types": ["client"],
        "allowed_role_codes": ["client_admin", "client_executor"],
        "requires_manual_review": True,
        "is_active": True,
        "priority": 60,
    },
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
    "countries": [row["code"] for row in COUNTRIES],
    "languages": [row["code"] for row in LANGUAGES],
    "product_groups": [row["code"] for row in PRODUCT_GROUPS],
    "product_types": [row["code"] for row in PRODUCT_TYPES],
    "auto_products": [row["code"] for row in AUTO_PRODUCTS],
    "portal_statuses": [row["code"] for row in PORTAL_STATUSES],
    "bitrix_categories": [row["bitrix_category_id"] for row in BITRIX_CATEGORIES],
}
