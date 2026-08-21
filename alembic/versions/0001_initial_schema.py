"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("crm_vacancy_id", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("auto_search_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("interval_minutes", sa.Integer, nullable=True),
        sa.Column("score_thresholds", postgresql.JSONB, nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "search_template_criteria",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "search_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column(
            "mode",
            postgresql.ENUM("required", "preferred", "ignore", name="criterion_mode"),
            nullable=False,
        ),
        sa.Column("weight", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_search_template_criteria_search_template_id", "search_template_criteria", ["search_template_id"]
    )

    op.create_table(
        "search_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "search_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigger", postgresql.ENUM("manual", "scheduled", name="search_run_trigger"), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("queued", "running", "completed", "failed", name="search_run_status"),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_runs_search_template_id", "search_runs", ["search_template_id"])
    op.create_index("ix_search_runs_status", "search_runs", ["status"])

    op.create_table(
        "external_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB, nullable=True),
        sa.Column("parsed_profile", postgresql.JSONB, nullable=True),
        sa.Column("crm_candidate_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "candidate_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "external_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("external_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", postgresql.ENUM("hh", "telegram", name="source_type"), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("external_url", sa.String(1000), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_candidate_sources_source_external_id"),
    )
    op.create_index("ix_candidate_sources_external_candidate_id", "candidate_sources", ["external_candidate_id"])

    op.create_table(
        "candidate_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "external_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("external_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "search_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("tier", postgresql.ENUM("low", "medium", "high", "hot", name="score_tier"), nullable=False),
        sa.Column("breakdown", postgresql.JSONB, nullable=True),
        sa.Column("hard_filters_passed", sa.Boolean, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "external_candidate_id", "search_template_id", name="uq_candidate_scores_candidate_template"
        ),
    )
    op.create_index("ix_candidate_scores_external_candidate_id", "candidate_scores", ["external_candidate_id"])
    op.create_index("ix_candidate_scores_search_template_id", "candidate_scores", ["search_template_id"])

    op.create_table(
        "telegram_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=False),
        sa.Column("vacancy_ref", sa.String(255), nullable=True),
        sa.Column("candidate_text", sa.Text, nullable=True),
        sa.Column("resume_file_ref", sa.String(500), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "external_candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("external_candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "sync_status",
            postgresql.ENUM("pending", "synced", "failed", name="telegram_sync_status"),
            nullable=False,
            server_default="pending",
        ),
    )

    op.create_table(
        "provider_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", postgresql.ENUM("hh", name="provider_type"), nullable=False, server_default="hh"),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("connected", "disconnected", "error", name="provider_account_status"),
            nullable=False,
            server_default="disconnected",
        ),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "provider_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "provider_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_provider_tokens_provider_account_id", "provider_tokens", ["provider_account_id"])

    op.create_table(
        "integration_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("level", sa.String(20), nullable=False, server_default="info"),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("context", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_integration_logs_event_type", "integration_logs", ["event_type"])
    op.create_index("ix_integration_logs_occurred_at", "integration_logs", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("integration_logs")
    op.drop_table("provider_tokens")
    op.drop_table("provider_accounts")
    op.drop_table("telegram_applications")
    op.drop_table("candidate_scores")
    op.drop_table("candidate_sources")
    op.drop_table("external_candidates")
    op.drop_table("search_runs")
    op.drop_table("search_template_criteria")
    op.drop_table("search_templates")

    postgresql.ENUM(name="provider_account_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="provider_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="telegram_sync_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="score_tier").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="source_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="search_run_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="search_run_trigger").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="criterion_mode").drop(op.get_bind(), checkfirst=True)
