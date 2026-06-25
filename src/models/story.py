from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.article import Article
    from src.models.snap import Snap


class Story(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "stories"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category_slug: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(5), nullable=False, server_default="en", index=True)
    importance_score: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    articles: Mapped[list["Article"]] = relationship("Article", back_populates="story")
    snaps: Mapped[list["Snap"]] = relationship("Snap", back_populates="story")
