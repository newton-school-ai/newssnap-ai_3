from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.interaction import Interaction
    from src.models.story import Story


class Snap(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "snaps"

    story_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(5), nullable=False, server_default="en", index=True)
    headline: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    card_image_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_attribution: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    share_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    story: Mapped["Story"] = relationship("Story", back_populates="snaps")
    interactions: Mapped[list["Interaction"]] = relationship("Interaction", back_populates="snap")
