from __future__ import annotations

import sqlalchemy as sa

metadata = sa.MetaData()


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )


roles = sa.Table(
    "roles",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("code", sa.String(64), nullable=False, unique=True),
    sa.Column("name_ru", sa.String(255), nullable=False),
    sa.Column("name_ka", sa.String(255), nullable=False),
    sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    *timestamps(),
)

countries = sa.Table(
    "countries",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("code", sa.String(64), nullable=False, unique=True),
    sa.Column("name_ru", sa.String(255), nullable=False),
    sa.Column("name_ka", sa.String(255), nullable=False),
    sa.Column("iso2", sa.String(2), nullable=True),
    sa.Column("iso3", sa.String(3), nullable=True),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    *timestamps(),
    sa.UniqueConstraint("iso2", name="uq_countries_iso2"),
    sa.UniqueConstraint("iso3", name="uq_countries_iso3"),
)

languages = sa.Table(
    "languages",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("code", sa.String(16), nullable=False, unique=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("native_name", sa.String(255), nullable=False),
    sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    *timestamps(),
)

product_groups = sa.Table(
    "product_groups",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("code", sa.String(64), nullable=False, unique=True),
    sa.Column("name_ru", sa.String(255), nullable=False),
    sa.Column("name_ka", sa.String(255), nullable=False),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    *timestamps(),
)

product_types = sa.Table(
    "product_types",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("product_group_id", sa.Integer, sa.ForeignKey("product_groups.id"), nullable=False),
    sa.Column("code", sa.String(128), nullable=False),
    sa.Column("name_ru", sa.String(255), nullable=False),
    sa.Column("name_ka", sa.String(255), nullable=False),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    *timestamps(),
    sa.UniqueConstraint("product_group_id", "code", name="uq_product_types_group_code"),
)

portal_statuses = sa.Table(
    "portal_statuses",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("code", sa.String(64), nullable=False, unique=True),
    sa.Column("name_ru", sa.String(255), nullable=False),
    sa.Column("name_ka", sa.String(255), nullable=False),
    sa.Column("is_final", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    *timestamps(),
)

bitrix_categories = sa.Table(
    "bitrix_categories",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("bitrix_category_id", sa.Integer, nullable=False, unique=True),
    sa.Column("code", sa.String(64), nullable=False),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    *timestamps(),
)

bitrix_stage_mappings = sa.Table(
    "bitrix_stage_mappings",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("bitrix_category_id", sa.Integer, nullable=False),
    sa.Column("bitrix_stage_id", sa.String(128), nullable=False),
    sa.Column("portal_status", sa.String(64), nullable=False),
    sa.Column("is_visible_to_client", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("is_visible_to_partner", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("allowed_client_action", sa.String(128), nullable=True),
    *timestamps(),
    sa.ForeignKeyConstraint(
        ["bitrix_category_id"],
        ["bitrix_categories.bitrix_category_id"],
        name="fk_stage_mapping_bitrix_category",
    ),
    sa.ForeignKeyConstraint(
        ["portal_status"],
        ["portal_statuses.code"],
        name="fk_stage_mapping_portal_status",
    ),
    sa.UniqueConstraint(
        "bitrix_category_id",
        "bitrix_stage_id",
        name="uq_bitrix_stage_mappings_category_stage",
    ),
)

portal_users = sa.Table(
    "portal_users",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("email", sa.String(320), nullable=False, unique=True),
    sa.Column("phone", sa.String(64), nullable=True),
    sa.Column("password_hash", sa.String(512), nullable=False),
    sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
    sa.Column("user_type", sa.String(32), nullable=False, server_default="client"),
    sa.Column("role_code", sa.String(64), nullable=True),
    sa.Column("language", sa.String(16), nullable=False, server_default="ru"),
    sa.Column("bitrix_contact_id", sa.Integer, nullable=True),
    sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    *timestamps(),
    sa.CheckConstraint("status in ('pending', 'active', 'blocked')", name="ck_portal_users_status"),
    sa.CheckConstraint("user_type in ('client', 'partner')", name="ck_portal_users_user_type"),
    sa.ForeignKeyConstraint(["role_code"], ["roles.code"], name="fk_portal_users_role_code"),
    sa.ForeignKeyConstraint(["language"], ["languages.code"], name="fk_portal_users_language"),
)

user_company_roles = sa.Table(
    "user_company_roles",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, nullable=False),
    sa.Column("bitrix_company_id", sa.Integer, nullable=False),
    sa.Column("role_code", sa.String(64), nullable=False),
    sa.Column("access_status", sa.String(32), nullable=False, server_default="pending"),
    sa.Column("bitrix_link_status", sa.String(32), nullable=False, server_default="not_checked"),
    sa.Column("confirmed_by_user_id", sa.Integer, nullable=True),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_by_user_id", sa.Integer, nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_by_user_id", sa.Integer, nullable=True),
    sa.Column("company_title_cache", sa.String(255), nullable=True),
    sa.Column("company_country_code_cache", sa.String(16), nullable=True),
    sa.Column("bitrix_updated_at_cache", sa.String(64), nullable=True),
    sa.Column("cache_refreshed_at", sa.DateTime(timezone=True), nullable=True),
    *timestamps(),
    sa.CheckConstraint(
        "role_code in ('client_executor', 'client_admin', 'client_viewer')",
        name="ck_user_company_roles_role_code",
    ),
    sa.CheckConstraint(
        "access_status in ('pending', 'active', 'revoked', 'rejected')",
        name="ck_user_company_roles_access_status",
    ),
    sa.CheckConstraint(
        "bitrix_link_status in ('not_checked', 'confirmed', 'not_found', 'mismatch', 'bitrix_unavailable')",
        name="ck_user_company_roles_bitrix_link_status",
    ),
    sa.ForeignKeyConstraint(["user_id"], ["portal_users.id"], name="fk_user_company_roles_user_id"),
    sa.ForeignKeyConstraint(["role_code"], ["roles.code"], name="fk_user_company_roles_role_code"),
    sa.ForeignKeyConstraint(
        ["confirmed_by_user_id"],
        ["portal_users.id"],
        name="fk_user_company_roles_confirmed_by_user_id",
    ),
    sa.ForeignKeyConstraint(
        ["revoked_by_user_id"],
        ["portal_users.id"],
        name="fk_user_company_roles_revoked_by_user_id",
    ),
    sa.ForeignKeyConstraint(
        ["created_by_user_id"],
        ["portal_users.id"],
        name="fk_user_company_roles_created_by_user_id",
    ),
    sa.Index("ix_user_company_roles_user_id", "user_id"),
    sa.Index("ix_user_company_roles_bitrix_company_id", "bitrix_company_id"),
    sa.Index("ix_user_company_roles_access_status", "access_status"),
    sa.Index(
        "uq_user_company_roles_active_pending",
        "user_id",
        "bitrix_company_id",
        "role_code",
        unique=True,
        sqlite_where=sa.text("access_status in ('pending', 'active')"),
        postgresql_where=sa.text("access_status in ('pending', 'active')"),
    ),
)

partner_client_links = sa.Table(
    "partner_client_links",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("partner_user_id", sa.Integer, nullable=False),
    sa.Column("client_user_id", sa.Integer, nullable=True),
    sa.Column("bitrix_company_id", sa.Integer, nullable=False),
    sa.Column("access_status", sa.String(32), nullable=False, server_default="active"),
    sa.Column("created_by_user_id", sa.Integer, nullable=True),
    sa.Column("revoked_by_user_id", sa.Integer, nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    *timestamps(),
    sa.CheckConstraint(
        "access_status in ('pending', 'active', 'revoked', 'rejected')",
        name="ck_partner_client_links_access_status",
    ),
    sa.ForeignKeyConstraint(["partner_user_id"], ["portal_users.id"], name="fk_partner_client_links_partner_user_id"),
    sa.ForeignKeyConstraint(["client_user_id"], ["portal_users.id"], name="fk_partner_client_links_client_user_id"),
    sa.ForeignKeyConstraint(
        ["created_by_user_id"],
        ["portal_users.id"],
        name="fk_partner_client_links_created_by_user_id",
    ),
    sa.ForeignKeyConstraint(
        ["revoked_by_user_id"],
        ["portal_users.id"],
        name="fk_partner_client_links_revoked_by_user_id",
    ),
    sa.Index("ix_partner_client_links_partner_user_id", "partner_user_id"),
    sa.Index("ix_partner_client_links_client_user_id", "client_user_id"),
    sa.Index("ix_partner_client_links_bitrix_company_id", "bitrix_company_id"),
)

portal_applications = sa.Table(
    "portal_applications",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("bitrix_deal_id", sa.Integer, nullable=True, unique=True),
    sa.Column("bitrix_company_id", sa.Integer, nullable=False),
    sa.Column("portal_status", sa.String(64), nullable=False, server_default="draft"),
    sa.Column("created_by_user_id", sa.Integer, nullable=True),
    sa.Column("partner_user_id", sa.Integer, nullable=True),
    sa.Column("is_hidden_from_partner", sa.Boolean, nullable=False, server_default=sa.false()),
    *timestamps(),
    sa.ForeignKeyConstraint(
        ["portal_status"],
        ["portal_statuses.code"],
        name="fk_portal_applications_portal_status",
    ),
    sa.ForeignKeyConstraint(
        ["created_by_user_id"],
        ["portal_users.id"],
        name="fk_portal_applications_created_by_user_id",
    ),
    sa.ForeignKeyConstraint(
        ["partner_user_id"],
        ["portal_users.id"],
        name="fk_portal_applications_partner_user_id",
    ),
    sa.Index("ix_portal_applications_bitrix_company_id", "bitrix_company_id"),
    sa.Index("ix_portal_applications_partner_user_id", "partner_user_id"),
)

document_transfer_logs = sa.Table(
    "document_transfer_logs",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("application_id", sa.Integer, nullable=False),
    sa.Column("bitrix_document_id", sa.String(128), nullable=True),
    sa.Column("document_type", sa.String(64), nullable=False, server_default="client_document"),
    sa.Column("is_policy_file", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("transfer_status", sa.String(64), nullable=False, server_default="pending"),
    sa.Column("created_by_user_id", sa.Integer, nullable=True),
    *timestamps(),
    sa.CheckConstraint(
        "document_type in ('client_document', 'policy_file', 'invoice', 'certificate', 'other')",
        name="ck_document_transfer_logs_document_type",
    ),
    sa.ForeignKeyConstraint(
        ["application_id"],
        ["portal_applications.id"],
        name="fk_document_transfer_logs_application_id",
    ),
    sa.ForeignKeyConstraint(
        ["created_by_user_id"],
        ["portal_users.id"],
        name="fk_document_transfer_logs_created_by_user_id",
    ),
    sa.Index("ix_document_transfer_logs_application_id", "application_id"),
    sa.Index("ix_document_transfer_logs_bitrix_document_id", "bitrix_document_id"),
)

invite_tokens = sa.Table(
    "invite_tokens",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, nullable=False),
    sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    *timestamps(),
    sa.ForeignKeyConstraint(["user_id"], ["portal_users.id"], name="fk_invite_tokens_user_id"),
)

auth_tokens = sa.Table(
    "auth_tokens",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, nullable=False),
    sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
    sa.Column("token_type", sa.String(32), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_by_user_id", sa.Integer, nullable=True),
    sa.Column("ip_address_used", sa.String(64), nullable=True),
    sa.Column("user_agent_used", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint(
        "token_type in ('first_login', 'password_reset')",
        name="ck_auth_tokens_token_type",
    ),
    sa.ForeignKeyConstraint(["user_id"], ["portal_users.id"], name="fk_auth_tokens_user_id"),
    sa.ForeignKeyConstraint(
        ["created_by_user_id"],
        ["portal_users.id"],
        name="fk_auth_tokens_created_by_user_id",
    ),
    sa.Index("ix_auth_tokens_user_id", "user_id"),
    sa.Index("ix_auth_tokens_token_type", "token_type"),
    sa.Index("ix_auth_tokens_expires_at", "expires_at"),
    sa.Index("ix_auth_tokens_used_at", "used_at"),
)

user_sessions = sa.Table(
    "user_sessions",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, nullable=False),
    sa.Column("refresh_token_hash", sa.String(128), nullable=False, unique=True),
    sa.Column("ip_address", sa.String(64), nullable=True),
    sa.Column("user_agent", sa.Text, nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    *timestamps(),
    sa.ForeignKeyConstraint(["user_id"], ["portal_users.id"], name="fk_user_sessions_user_id"),
)

audit_logs = sa.Table(
    "audit_logs",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("actor_user_id", sa.Integer, nullable=True),
    sa.Column("target_user_id", sa.Integer, nullable=True),
    sa.Column("company_group_id", sa.Integer, nullable=True),
    sa.Column("bitrix_company_id", sa.Integer, nullable=True),
    sa.Column("application_id", sa.Integer, nullable=True),
    sa.Column("bitrix_deal_id", sa.Integer, nullable=True),
    sa.Column("action", sa.String(128), nullable=False),
    sa.Column("object_type", sa.String(128), nullable=False),
    sa.Column("object_id", sa.String(128), nullable=True),
    sa.Column("ip_address", sa.String(64), nullable=True),
    sa.Column("user_agent", sa.Text, nullable=True),
    sa.Column("metadata_json", sa.JSON, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(["actor_user_id"], ["portal_users.id"], name="fk_audit_logs_actor_user_id"),
    sa.ForeignKeyConstraint(["target_user_id"], ["portal_users.id"], name="fk_audit_logs_target_user_id"),
)
