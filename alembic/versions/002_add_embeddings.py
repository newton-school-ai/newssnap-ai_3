"""add embeddings and dedup columns

Revision ID: 002
Revises: 001
Create Date: 2026-07-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add parent_id FK to articles (self-referencing for dedup linking)
    op.add_column(
        "articles",
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_articles_parent_id", "articles", ["parent_id"])

    # Add duplicate_count to articles (how many duplicates point to this article)
    op.add_column(
        "articles",
        sa.Column(
            "duplicate_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )

    # Add priority to sources (lower = higher priority, mirrors SourceConfig)
    op.add_column(
        "sources",
        sa.Column(
            "priority",
            sa.Integer,
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("sources", "priority")
    op.drop_column("articles", "duplicate_count")
    op.drop_index("ix_articles_parent_id", table_name="articles")
    op.drop_column("articles", "parent_id")
