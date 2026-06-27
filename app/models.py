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
    sa.Column("role_code", sa.String(64), nullable=False),
    sa.Column("language", sa.String(16), nullable=False, server_default="ru"),
    sa.Column("bitrix_contact_id", sa.Integer, nullable=True),
    sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    *timestamps(),
    sa.CheckConstraint("status in ('pending', 'active', 'blocked')", name="ck_portal_users_status"),
    sa.ForeignKeyConstraint(["role_code"], ["roles.code"], name="fk_portal_users_role_code"),
    sa.ForeignKeyConstraint(["language"], ["languages.code"], name="fk_portal_users_language"),
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
