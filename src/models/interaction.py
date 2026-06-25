from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.snap import Snap
    from src.models.user import User


class Interaction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "interactions"
    __table_args__ = (
        Index("ix_interactions_user_snap", "user_id", "snap_id"),
        Index("ix_interactions_user_type", "user_id", "interaction_type"),
    )

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snap_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("snaps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interaction_type: Mapped[str] = mapped_column(String(20), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="interactions")
    snap: Mapped["Snap"] = relationship("Snap", back_populates="interactions")


class Comment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "comments"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snap_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("snaps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="comments")
    replies: Mapped[list["Comment"]] = relationship("Comment", back_populates="parent", cascade="all, delete-orphan")
    parent: Mapped[Optional["Comment"]] = relationship("Comment", back_populates="replies", remote_side="Comment.id")
