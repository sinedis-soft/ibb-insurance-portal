CONTACT_LANGUAGE_FIELD = "UF_CRM_1753957395750"

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
