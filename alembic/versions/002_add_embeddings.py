"""add duplicate_of_id to articles

Revision ID: 002
Revises: 001
Create Date: 2025-07-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column(
            "duplicate_of_id",
            UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_articles_duplicate_of_id", "articles", ["duplicate_of_id"])


def downgrade() -> None:
    op.drop_index("ix_articles_duplicate_of_id", table_name="articles")
    op.drop_column("articles", "duplicate_of_id")
