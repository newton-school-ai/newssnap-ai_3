from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.auth import get_user_store
from src.api.middleware import CurrentUser, get_current_user

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


@router.get("/me", response_model=UserProfileResponse)
def get_me(current_user: CurrentUser = Depends(get_current_user)):
    store = get_user_store()
    user = store.get(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserProfileResponse(
        id=user["id"],
        email=user["email"],
        display_name=user["display_name"],
        avatar_url=user.get("avatar_url"),
        role=user["role"],
        needs_onboarding=user.get("needs_onboarding", False),
        preferred_languages=user.get("preferred_languages"),
        preferred_categories=user.get("preferred_categories"),
    )


@router.post("/me/onboarding", response_model=UserProfileResponse)
def complete_onboarding(
    request: OnboardingRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    if len(request.preferred_categories) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least 3 categories",
        )

    if not request.preferred_languages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least 1 language",
        )

    store = get_user_store()
    user = store.get(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user["preferred_languages"] = ",".join(request.preferred_languages)
    user["preferred_categories"] = ",".join(request.preferred_categories)
    user["needs_onboarding"] = False

    return UserProfileResponse(
        id=user["id"],
        email=user["email"],
        display_name=user["display_name"],
        avatar_url=user.get("avatar_url"),
        role=user["role"],
        needs_onboarding=False,
        preferred_languages=user["preferred_languages"],
        preferred_categories=user["preferred_categories"],
    )


@router.patch("/me", response_model=UserProfileResponse)
def update_profile(
    request: UpdateProfileRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    store = get_user_store()
    user = store.get(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if request.display_name is not None:
        user["display_name"] = request.display_name
    if request.preferred_languages is not None:
        user["preferred_languages"] = ",".join(request.preferred_languages)
    if request.preferred_categories is not None:
        if len(request.preferred_categories) < 3:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least 3 categories")
        user["preferred_categories"] = ",".join(request.preferred_categories)
    if request.notification_enabled is not None:
        user["notification_enabled"] = request.notification_enabled
    if request.fcm_token is not None:
        user["fcm_token"] = request.fcm_token

    return UserProfileResponse(
        id=user["id"],
        email=user["email"],
        display_name=user["display_name"],
        avatar_url=user.get("avatar_url"),
        role=user["role"],
        needs_onboarding=user.get("needs_onboarding", False),
        preferred_languages=user.get("preferred_languages"),
        preferred_categories=user.get("preferred_categories"),
    )
