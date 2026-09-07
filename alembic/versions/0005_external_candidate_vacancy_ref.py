"""add vacancy_ref to external_candidates

The vacancy a Telegram candidate applied to was already captured on
telegram_applications.vacancy_ref, but never surfaced through
GET /external-candidates — CRM had no way to see which vacancy a Telegram
reply was for. This denormalizes the latest vacancy_ref onto the candidate
itself, next to crm_candidate_id, so it's visible in the API response CRM
actually reads.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("external_candidates", sa.Column("vacancy_ref", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("external_candidates", "vacancy_ref")
