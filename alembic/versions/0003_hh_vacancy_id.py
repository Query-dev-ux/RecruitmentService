"""add hh_vacancy_id to search_templates (for reading HH negotiations)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("search_templates", sa.Column("hh_vacancy_id", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("search_templates", "hh_vacancy_id")
