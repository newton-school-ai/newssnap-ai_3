from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.middleware import CurrentUser, get_current_user
from src.db.session import get_db
from src.models.user import User, UserPreference

router = APIRouter(prefix="/api/users", tags=["users"])


class UserProfileResponse(BaseModel):
    id: str
    email: str
    display_name: str
    avatar_url: Optional[str] = None
    role: str
    needs_onboarding: bool = False
    preferred_languages: Optional[str] = None
    preferred_categories: Optional[str] = None


class OnboardingRequest(BaseModel):
    preferred_languages: list[str]
    preferred_categories: list[str]


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    preferred_languages: Optional[list[str]] = None
    preferred_categories: Optional[list[str]] = None
    notification_enabled: Optional[bool] = None
    fcm_token: Optional[str] = None


def _user_response(user: User, pref: UserPreference | None) -> UserProfileResponse:
    return UserProfileResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        role=user.role,
        needs_onboarding=pref is None,
        preferred_languages=pref.preferred_languages if pref else None,
        preferred_categories=pref.preferred_categories if pref else None,
    )


@router.get("/me", response_model=UserProfileResponse)
def get_me(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.id == current_user.user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    pref = db.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    return _user_response(user, pref)


@router.post("/me/onboarding", response_model=UserProfileResponse)
def complete_onboarding(
    request: OnboardingRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(request.preferred_categories) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least 3 categories")

    if not request.preferred_languages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least 1 language")

    user = db.scalar(select(User).where(User.id == current_user.user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    pref = db.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    if pref is None:
        pref = UserPreference(user_id=user.id)
        db.add(pref)

    pref.preferred_languages = ",".join(request.preferred_languages)
    pref.preferred_categories = ",".join(request.preferred_categories)
    db.commit()
    db.refresh(pref)

    return _user_response(user, pref)


@router.patch("/me", response_model=UserProfileResponse)
def update_profile(
    request: UpdateProfileRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.id == current_user.user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if request.display_name is not None:
        user.display_name = request.display_name

    pref = db.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    if request.preferred_languages is not None or request.preferred_categories is not None or request.notification_enabled is not None or request.fcm_token is not None:
        if pref is None:
            pref = UserPreference(user_id=user.id)
            db.add(pref)

        if request.preferred_languages is not None:
            pref.preferred_languages = ",".join(request.preferred_languages)
        if request.preferred_categories is not None:
            if len(request.preferred_categories) < 3:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least 3 categories")
            pref.preferred_categories = ",".join(request.preferred_categories)
        if request.notification_enabled is not None:
            pref.notification_enabled = request.notification_enabled
        if request.fcm_token is not None:
            pref.fcm_token = request.fcm_token

    db.commit()
    if pref:
        db.refresh(pref)
    db.refresh(user)

    return _user_response(user, pref)
