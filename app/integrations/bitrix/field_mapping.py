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

REQUIRED_DEAL_FIELDS = frozenset(BITRIX_DEAL_FIELDS.values())
