from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException

from src.api.auth_tokens import create_access_token, decode_jwt, hash_password, verify_password


def test_password_hash_verifies_original_password_only():
    password_hash = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong", password_hash)
    assert not verify_password("wrong", "not-a-valid-hash")


def test_access_token_round_trips_user_claims():
    token = create_access_token(
        user_id="user-1",
        role="admin",
        secret="test-secret",
        expires_delta=timedelta(minutes=5),
    )

    payload = decode_jwt(token, "test-secret")

    assert payload["sub"] == "user-1"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_decode_jwt_rejects_invalid_signature():
    token = create_access_token(
        user_id="user-1",
        role="admin",
        secret="test-secret",
        expires_delta=timedelta(minutes=5),
    )

    with pytest.raises(HTTPException) as exc:
        decode_jwt(token, "other-secret")

    assert exc.value.status_code == 401
