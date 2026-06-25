from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.interaction import Comment, Interaction
    from src.models.notification import Notification


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="reader")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    preference: Mapped[Optional["UserPreference"]] = relationship("UserPreference", back_populates="user", uselist=False)
    interactions: Mapped[list["Interaction"]] = relationship("Interaction", back_populates="user")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="user")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user")


class UserPreference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    preferred_languages: Mapped[str] = mapped_column(String(50), nullable=False, server_default="en")
    preferred_categories: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notification_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    fcm_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="preference")
