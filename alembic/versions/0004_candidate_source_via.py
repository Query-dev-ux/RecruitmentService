"""add via (discovery channel) to candidate_sources

Distinguishes, per HH sighting, whether a candidate was found via active
resume search vs. an inbound negotiation response to a posted vacancy —
both funnel through the same candidate_sources row today with no way to
tell them apart in storage (only in worker logs). Null for Telegram and for
rows sourced before this field existed.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # See 0002's note: postgresql.ENUM must be created explicitly before a
    # standalone op.add_column() — op.create_table() is the only place that
    # auto-creates the backing type.
    discovery_channel_enum = postgresql.ENUM("search", "negotiation", name="discovery_channel")
    discovery_channel_enum.create(op.get_bind(), checkfirst=True)

    op.add_column("candidate_sources", sa.Column("via", discovery_channel_enum, nullable=True))


def downgrade() -> None:
    op.drop_column("candidate_sources", "via")
    postgresql.ENUM(name="discovery_channel").drop(op.get_bind(), checkfirst=True)
