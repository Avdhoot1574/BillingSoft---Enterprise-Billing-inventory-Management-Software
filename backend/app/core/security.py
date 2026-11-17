import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()
_dummy_hash: str | None = None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def burn_password_check(password: str) -> None:
    """Spend the same time as a real verification (avoids user-enumeration by timing)."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = _hasher.hash("not-a-real-password")
    verify_password(_dummy_hash, password)


def new_refresh_token() -> tuple[str, str]:
    """Return (plain token for the client, sha256 hash for the database)."""
    token = secrets.token_urlsafe(48)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=s.access_token_minutes)
    payload = {"sub": str(user_id), "sid": str(session_id), "type": "access", "iat": now, "exp": expires}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), s.access_token_minutes * 60


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError on any problem."""
    s = get_settings()
    payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["exp", "sub", "sid"]})
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload
