CONTACT_LANGUAGE_FIELD = "UF_CRM_1753957395750"

BITRIX_COMPANY_FIELDS = {
    "partner_client_check_status": "UF_CRM_1782757925237",
    "portal_partner_bitrix_id": "UF_CRM_1777876263",
}

PARTNER_CLIENT_CHECK_COMPANY_STATUS_IDS = {
    "pending": 6479,
    "clarification_required": 6481,
    "confirmed": 6483,
    "duplicate_found": 6485,
    "rejected": 6487,
}

PARTNER_CLIENT_CHECK_COMPANY_STATUS_VALUES = {
    (
        "\u041e\u0436\u0438\u0434\u0430\u0435\u0442 "
        "\u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438"
    ): "pending",
    (
        "\u0422\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f "
        "\u0443\u0442\u043e\u0447\u043d\u0435\u043d\u0438\u0435"
    ): "clarification_required",
    "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d": "confirmed",
    "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d": "confirmed",
    (
        "\u041d\u0430\u0439\u0434\u0435\u043d "
        "\u0434\u0443\u0431\u043b\u044c"
    ): "duplicate_found",
    "\u041e\u0442\u043a\u043b\u043e\u043d\u0451\u043d": "rejected",
    "\u041e\u0442\u043a\u043b\u043e\u043d\u0435\u043d": "rejected",
    (
        "\u0421\u0432\u044f\u0437\u0430\u043d \u0441 "
        "\u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u043c "
        "\u043a\u043b\u0438\u0435\u043d\u0442\u043e\u043c"
    ): "linked_to_existing",
}

PARTNER_CLIENT_CHECK_COMPANY_STATUS_ID_TO_PORTAL = {
    str(bitrix_status_id): portal_status
    for portal_status, bitrix_status_id in PARTNER_CLIENT_CHECK_COMPANY_STATUS_IDS.items()
}

BITRIX_DEAL_FIELDS = {
    "portal_application_id": "UF_CRM_1782659474410",
    "portal_application_type": "UF_CRM_1782660209555",
    "portal_source": "UF_CRM_1782660734915",
    "portal_channel": "UF_CRM_1782660775332",
    "portal_sync_status": "UF_CRM_1782660821873",
    "portal_last_sync_at": "UF_CRM_1782660834442",
    "portal_sync_error": "UF_CRM_1782660852370",
}

BITRIX_DEAL_FIELD_TODOS = {
    # Configure this after the Bitrix24 custom deal field is created.
    "portal_created_by_user_id": None,
}

BITRIX_POLICY_FIELDS = {
    "policy_number": "UF_CRM_POLICY_NUMBER_TODO",
    "policy_start_date": "UF_CRM_POLICY_START_DATE_TODO",
    "policy_end_date": "UF_CRM_POLICY_END_DATE_TODO",
    "policy_issue_date": "UF_CRM_POLICY_ISSUE_DATE_TODO",
    "premium": "OPPORTUNITY",
    "premium_currency": "CURRENCY_ID",
    "insurer": "UF_CRM_POLICY_INSURER_TODO",
    "product": "UF_CRM_POLICY_PRODUCT_TODO",
    "policy_document": "UF_CRM_POLICY_DOCUMENT_TODO",
    "show_in_portal": "UF_CRM_SHOW_IN_PORTAL_TODO",
    "client_comment": "UF_CRM_CLIENT_COMMENT_TODO",
    "client_action_required": "UF_CRM_CLIENT_ACTION_REQUIRED_TODO",
    "client_required_action": "UF_CRM_CLIENT_REQUIRED_ACTION_TODO",
}

REQUIRED_DEAL_FIELDS = frozenset(BITRIX_DEAL_FIELDS.values())
