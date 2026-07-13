"""Initial production schema.

Revision ID: 20260712_0001
Revises:
Create Date: 2026-07-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20260712_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("phone", sa.String()),
        sa.Column("password_hash", sa.String()),
        sa.Column("role", sa.String(), default="user"),
        sa.Column("avatar_url", sa.String()),
        sa.Column("google_sub", sa.String()),
        sa.Column("plan", sa.String(), default="free"),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_google_sub", "users", ["google_sub"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(), nullable=False),
        sa.Column("device_id", sa.String()),
        sa.Column("user_agent", sa.String()),
        sa.Column("ip_address", sa.String()),
        sa.Column("revoked", sa.Boolean(), default=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("last_seen_at", sa.DateTime()),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_refresh_token_hash", "sessions", ["refresh_token_hash"])
    op.create_index("ix_sessions_device_id", "sessions", ["device_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("used", sa.Boolean(), default=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String()),
        sa.Column("icon", sa.String()),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "experts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("name", sa.String()),
        sa.Column("category", sa.String()),
        sa.Column("bio", sa.Text()),
        sa.Column("years_experience", sa.Integer(), default=0),
        sa.Column("fee", sa.Float(), default=0),
        sa.Column("rating", sa.Float(), default=0),
        sa.Column("verified", sa.Boolean(), default=False),
        sa.Column("available", sa.Boolean(), default=True),
        sa.Column("city", sa.String()),
        sa.Column("languages", sa.String()),
        sa.Column("profile_photo_url", sa.String()),
        sa.Column("aadhaar_url", sa.String()),
        sa.Column("certificate_url", sa.String()),
        sa.Column("certificate_required", sa.Boolean(), default=False),
        sa.Column("certificate_verified", sa.Boolean(), default=False),
        sa.Column("portfolio_url", sa.String()),
        sa.Column("application_status", sa.String(), default="approved"),
        sa.Column("aadhaar_verified", sa.Boolean(), default=False),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_experts_category", "experts", ["category"])

    op.create_table(
        "availability",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expert_id", sa.Integer(), sa.ForeignKey("experts.id")),
        sa.Column("days", sa.String(), default="Mon,Tue,Wed,Thu,Fri"),
        sa.Column("from_time", sa.String(), default="09:00"),
        sa.Column("to_time", sa.String(), default="18:00"),
        sa.UniqueConstraint("expert_id"),
    )

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("expert_id", sa.Integer(), sa.ForeignKey("experts.id")),
        sa.Column("scheduled_at", sa.DateTime()),
        sa.Column("mode", sa.String(), default="video"),
        sa.Column("status", sa.String(), default="pending"),
        sa.Column("fee", sa.Float(), default=0),
        sa.Column("meeting_token", sa.String()),
        sa.Column("free_minutes", sa.Integer(), default=2),
        sa.Column("rate_per_minute", sa.Float(), default=25),
        sa.Column("call_started_at", sa.DateTime()),
        sa.Column("call_ended_at", sa.DateTime()),
        sa.Column("billable_minutes", sa.Integer(), default=0),
        sa.Column("call_charge_status", sa.String(), default="not_started"),
        sa.Column("details_unlocked", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_bookings_meeting_token", "bookings", ["meeting_token"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id")),
        sa.Column("amount", sa.Float()),
        sa.Column("currency", sa.String(), default="INR"),
        sa.Column("provider", sa.String()),
        sa.Column("provider_ref", sa.String()),
        sa.Column("status", sa.String(), default="initiated"),
        sa.Column("description", sa.String()),
        sa.Column("refunded_amount", sa.Float(), default=0),
        sa.Column("refund_ref", sa.String()),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id")),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id")),
        sa.Column("invoice_number", sa.String()),
        sa.Column("amount", sa.Float()),
        sa.Column("currency", sa.String(), default="INR"),
        sa.Column("status", sa.String(), default="issued"),
        sa.Column("pdf_path", sa.String()),
        sa.Column("issued_at", sa.DateTime()),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index("ix_invoices_user_id", "invoices", ["user_id"])
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])

    op.create_table(
        "otp_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String()),
        sa.Column("phone", sa.String()),
        sa.Column("purpose", sa.String(), default="consultant_registration"),
        sa.Column("code", sa.String()),
        sa.Column("verified", sa.Boolean(), default=False),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_otp_verifications_email", "otp_verifications", ["email"])
    op.create_index("ix_otp_verifications_phone", "otp_verifications", ["phone"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("plan", sa.String()),
        sa.Column("status", sa.String(), default="active"),
        sa.Column("renews_at", sa.DateTime()),
        sa.Column("provider", sa.String()),
        sa.Column("provider_ref", sa.String()),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("expert_id", sa.Integer(), sa.ForeignKey("experts.id")),
        sa.Column("rating", sa.Integer()),
        sa.Column("comment", sa.Text()),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("helpful", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id")),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("content", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("title", sa.String()),
        sa.Column("body", sa.Text()),
        sa.Column("read", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id")),
        sa.Column("type", sa.String()),
        sa.Column("amount", sa.Float()),
        sa.Column("meta", sa.JSON()),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "ai_chats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("messages", sa.JSON()),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("email", sa.String()),
        sa.Column("subject", sa.String()),
        sa.Column("body", sa.Text()),
        sa.Column("status", sa.String(), default="open"),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "complaints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("email", sa.String()),
        sa.Column("subject", sa.String()),
        sa.Column("body", sa.Text()),
        sa.Column("priority", sa.String(), default="normal"),
        sa.Column("status", sa.String(), default="open"),
        sa.Column("resolution", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("target_type", sa.String()),
        sa.Column("target_id", sa.Integer()),
        sa.Column("reason", sa.Text()),
        sa.Column("status", sa.String(), default="open"),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.JSON()),
        sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"])

    op.create_table(
        "admin_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String()),
        sa.Column("meta", sa.JSON()),
        sa.Column("created_at", sa.DateTime()),
    )


def downgrade():
    for table in (
        "admin_logs",
        "support_tickets",
        "system_settings",
        "reports",
        "complaints",
        "ai_chats",
        "transactions",
        "notifications",
        "messages",
        "reviews",
        "subscriptions",
        "otp_verifications",
        "invoices",
        "payments",
        "bookings",
        "availability",
        "experts",
        "categories",
        "password_reset_tokens",
        "sessions",
        "users",
    ):
        op.drop_table(table)
