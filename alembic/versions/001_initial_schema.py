"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-06-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("google_id", sa.String(255), unique=True, nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="reader"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_google_id", "users", ["google_id"])

    # User Preferences
    op.create_table(
        "user_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("preferred_languages", sa.String(50), nullable=False, server_default="en"),
        sa.Column("preferred_categories", sa.Text, nullable=True),
        sa.Column("notification_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("fcm_token", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Categories
    op.create_table(
        "categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("icon", sa.String(50), nullable=False, server_default="📰"),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"])

    # Sources
    op.create_table(
        "sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("feed_url", sa.Text, nullable=True),
        sa.Column("scrape_type", sa.String(20), nullable=False),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("category_slug", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("reliability_score", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("selectors", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sources_language", "sources", ["language"])
    op.create_index("ix_sources_category_slug", "sources", ["category_slug"])

    # Stories
    op.create_table(
        "stories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("category_slug", sa.String(50), nullable=False),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("importance_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("article_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stories_category_slug", "stories", ["category_slug"])
    op.create_index("ix_stories_language", "stories", ["language"])

    # Articles
    op.create_table(
        "articles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text, unique=True, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("category_slug", sa.String(50), nullable=False),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("author", sa.String(200), nullable=True),
        sa.Column("publish_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("embedding_vector", sa.Text, nullable=True),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("story_id", UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_articles_language", "articles", ["language"])
    op.create_index("ix_articles_category_slug", "articles", ["category_slug"])
    op.create_index("ix_articles_publish_time", "articles", ["publish_time"])
    op.create_index("ix_articles_source_id", "articles", ["source_id"])
    op.create_index("ix_articles_story_id", "articles", ["story_id"])

    # Snaps
    op.create_table(
        "snaps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("story_id", UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("headline", sa.String(300), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("image_path", sa.Text, nullable=True),
        sa.Column("card_image_path", sa.Text, nullable=True),
        sa.Column("source_attribution", sa.String(200), nullable=True),
        sa.Column("view_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("like_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("share_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_snaps_story_id", "snaps", ["story_id"])
    op.create_index("ix_snaps_language", "snaps", ["language"])

    # Interactions
    op.create_table(
        "interactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snap_id", UUID(as_uuid=True), sa.ForeignKey("snaps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interaction_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_interactions_user_id", "interactions", ["user_id"])
    op.create_index("ix_interactions_snap_id", "interactions", ["snap_id"])
    op.create_index("ix_interactions_user_snap", "interactions", ["user_id", "snap_id"])
    op.create_index("ix_interactions_user_type", "interactions", ["user_id", "interaction_type"])

    # Comments
    op.create_table(
        "comments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snap_id", UUID(as_uuid=True), sa.ForeignKey("snaps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_comments_user_id", "comments", ["user_id"])
    op.create_index("ix_comments_snap_id", "comments", ["snap_id"])

    # Notifications
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("notification_type", sa.String(30), nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deep_link", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_type", "notifications", ["notification_type"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("comments")
    op.drop_table("interactions")
    op.drop_table("snaps")
    op.drop_table("articles")
    op.drop_table("stories")
    op.drop_table("sources")
    op.drop_table("categories")
    op.drop_table("user_preferences")
    op.drop_table("users")
