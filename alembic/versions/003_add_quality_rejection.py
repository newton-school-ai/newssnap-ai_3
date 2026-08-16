"""add is_rejected and rejection_reason to articles

Revision ID: 003
Revises: 002
Create Date: 2026-08-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("is_rejected", sa.Boolean, nullable=False, server_default="false"),
    )
    op.add_column(
        "articles",
        sa.Column("rejection_reason", sa.Text, nullable=True),
    )
    op.create_index("ix_articles_is_rejected", "articles", ["is_rejected"])


def downgrade() -> None:
    op.drop_index("ix_articles_is_rejected", table_name="articles")
    op.drop_column("articles", "rejection_reason")
    op.drop_column("articles", "is_rejected")
