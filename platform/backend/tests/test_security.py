from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    validate_password,
    verify_password,
)

EMAIL = "ana@example.com"


def test_password_hash_verifies_only_the_original_password():
    hashed = hash_password("correct horse battery")

    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong horse battery", hashed)


def test_verify_password_rejects_missing_hash_and_overlong_input():
    assert not verify_password("anything at all", None)
    assert not verify_password("x" * 73, hash_password("correct horse battery"))


@pytest.mark.parametrize(
    ("password", "reason"),
    [
        ("short1", "at least 10"),
        ("ñ" * 37, "at most 72 bytes"),
        ("1234567890123", "only digits"),
        ("Ana@Example.com", "email address"),
    ],
)
def test_validate_password_rejects_each_broken_rule(password, reason):
    with pytest.raises(AppError) as error:
        validate_password(password, EMAIL)

    assert error.value.status == 400
    assert error.value.code == "weak_password"
    assert reason in error.value.message


def test_validate_password_accepts_a_good_password():
    validate_password("correct horse battery", EMAIL)


def test_access_token_round_trip_returns_the_user_id():
    assert decode_access_token(create_access_token(42, "user")) == 42


def test_expired_access_token_is_rejected_as_expired():
    token = create_access_token(42, "user", now=datetime.now(UTC) - timedelta(hours=1))

    with pytest.raises(AppError) as error:
        decode_access_token(token)

    assert (error.value.status, error.value.code) == (401, "token_expired")


def test_tampered_access_token_is_rejected():
    token = create_access_token(42, "user")
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")

    with pytest.raises(AppError) as error:
        decode_access_token(tampered)

    assert (error.value.status, error.value.code) == (401, "unauthorized")


def test_token_of_another_type_is_rejected():
    now = datetime.now(UTC)
    claims = {"sub": "42", "type": "refresh", "iat": now, "exp": now + timedelta(minutes=5)}
    token = jwt.encode(claims, "test-secret-key-with-enough-length-for-hs256", algorithm="HS256")

    with pytest.raises(AppError) as error:
        decode_access_token(token)

    assert error.value.code == "unauthorized"


def test_token_hash_is_stable_sha256_hex():
    assert hash_token("abc") == hash_token("abc")
    assert len(hash_token("abc")) == 64
