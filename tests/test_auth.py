import time
import uuid

from src.utils.auth_utils import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
)


def test_create_access_token():
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id, "reader")
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_access_token():
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id, "admin")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_create_refresh_token():
    user_id = str(uuid.uuid4())
    token = create_refresh_token(user_id)
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "refresh"


def test_create_token_pair():
    user_id = str(uuid.uuid4())
    pair = create_token_pair(user_id, "reader")
    assert "access_token" in pair
    assert "refresh_token" in pair
    assert pair["token_type"] == "bearer"

    access_payload = decode_token(pair["access_token"])
    refresh_payload = decode_token(pair["refresh_token"])
    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert access_payload["sub"] == user_id
    assert refresh_payload["sub"] == user_id


def test_decode_invalid_token():
    result = decode_token("invalid.token.here")
    assert result is None


def test_decode_empty_token():
    result = decode_token("")
    assert result is None


def test_access_token_has_expiry():
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)
    payload = decode_token(token)
    assert "exp" in payload
    assert payload["exp"] > time.time()


def test_refresh_token_has_longer_expiry():
    user_id = str(uuid.uuid4())
    access = create_access_token(user_id)
    refresh = create_refresh_token(user_id)
    access_payload = decode_token(access)
    refresh_payload = decode_token(refresh)
    assert refresh_payload["exp"] > access_payload["exp"]


def test_tokens_have_unique_jti():
    user_id = str(uuid.uuid4())
    t1 = create_access_token(user_id)
    t2 = create_access_token(user_id)
    p1 = decode_token(t1)
    p2 = decode_token(t2)
    assert p1["jti"] != p2["jti"]


def test_middleware_current_user():
    from src.api.middleware import CurrentUser

    user = CurrentUser(user_id="abc-123", role="admin")
    assert user.user_id == "abc-123"
    assert user.role == "admin"
