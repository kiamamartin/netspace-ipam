"""Add subnet ownership and location tracking (M7-AC-002).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-01

Additive only: two nullable columns on ``subnets`` (``owner``, ``location``),
fully reversible with no default backfill, so existing rows are untouched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subnets", sa.Column("owner", sa.String(length=200), nullable=True))
    op.add_column("subnets", sa.Column("location", sa.String(length=200), nullable=True))
    op.create_index("ix_subnets_owner", "subnets", ["owner"])


def downgrade() -> None:
    op.drop_index("ix_subnets_owner", table_name="subnets")
    op.drop_column("subnets", "location")
    op.drop_column("subnets", "owner")
