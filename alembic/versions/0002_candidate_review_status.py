"""candidate review status (pending/added/skipped triage gate)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # postgresql.ENUM is only auto-created by Alembic/SQLAlchemy when used
    # inside op.create_table() — a standalone op.add_column() on an existing
    # table does NOT create the backing type, so it must be created
    # explicitly first (checkfirst=True makes this safe to re-run).
    review_status_enum = postgresql.ENUM("pending", "added", "skipped", name="review_status")
    review_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "external_candidates",
        sa.Column("review_status", review_status_enum, nullable=False, server_default="pending"),
    )
    op.add_column("external_candidates", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("external_candidates", sa.Column("reviewed_by", sa.String(255), nullable=True))
    op.create_index("ix_external_candidates_review_status", "external_candidates", ["review_status"])


def downgrade() -> None:
    op.drop_index("ix_external_candidates_review_status", table_name="external_candidates")
    op.drop_column("external_candidates", "reviewed_by")
    op.drop_column("external_candidates", "reviewed_at")
    op.drop_column("external_candidates", "review_status")
    postgresql.ENUM(name="review_status").drop(op.get_bind(), checkfirst=True)
