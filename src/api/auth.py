from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.utils.auth_utils import create_token_pair, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

_user_store: dict[str, dict] = {}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    needs_onboarding: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class GoogleCallbackRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None


@router.get("/google")
def google_login():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth not configured")

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    return {"auth_url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}"}


@router.get("/google/callback")
async def google_callback(code: str):
    return await _handle_google_code(code, GOOGLE_REDIRECT_URI)


@router.post("/google/token")
async def google_token(request: GoogleCallbackRequest):
    redirect_uri = request.redirect_uri or GOOGLE_REDIRECT_URI
    return await _handle_google_code(request.code, redirect_uri)


async def _handle_google_code(code: str, redirect_uri: str) -> TokenResponse:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth not configured")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )

        if token_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange authorization code")

        google_tokens = token_resp.json()
        access_token = google_tokens.get("access_token")

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to fetch user profile")

        profile = userinfo_resp.json()

    google_id = profile.get("id")
    email = profile.get("email")
    name = profile.get("name", email)
    avatar = profile.get("picture")

    user = _find_or_create_user(google_id=google_id, email=email, name=name, avatar=avatar)

    tokens = create_token_pair(user["id"], user["role"])
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        needs_onboarding=user.get("needs_onboarding", False),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshRequest):
    payload = decode_token(request.refresh_token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = payload.get("sub")
    user = _user_store.get(user_id, {})
    role = user.get("role", "reader")

    tokens = create_token_pair(user_id, role)
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )


def _find_or_create_user(google_id: str, email: str, name: str, avatar: str | None) -> dict:
    for user in _user_store.values():
        if user.get("google_id") == google_id:
            user["last_login_at"] = datetime.now(timezone.utc).isoformat()
            return user

    for user in _user_store.values():
        if user.get("email") == email:
            user["google_id"] = google_id
            user["avatar_url"] = avatar
            user["last_login_at"] = datetime.now(timezone.utc).isoformat()
            return user

    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": email,
        "display_name": name,
        "avatar_url": avatar,
        "google_id": google_id,
        "role": "reader",
        "is_active": True,
        "needs_onboarding": True,
        "last_login_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _user_store[user_id] = user
    return user


def get_user_store() -> dict[str, dict]:
    return _user_store
