from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.source import Source
    from src.models.story import Story


class Article(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "articles"

    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(5), nullable=False, server_default="en", index=True)
    category_slug: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    publish_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    embedding_vector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    source_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    story_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="SET NULL"), nullable=True, index=True
    )

    source: Mapped[Optional["Source"]] = relationship("Source", back_populates="articles")
    story: Mapped[Optional["Story"]] = relationship("Story", back_populates="articles")
