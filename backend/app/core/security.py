from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return password_hash.verify(password, encoded_hash)


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> UUID | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "access":
            return None
        return UUID(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        return None
