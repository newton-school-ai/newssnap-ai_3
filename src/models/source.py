from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.article import Article


class Source(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    feed_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scrape_type: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False, server_default="en", index=True)
    category_slug: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    logo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selectors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    articles: Mapped[list["Article"]] = relationship("Article", back_populates="source")
