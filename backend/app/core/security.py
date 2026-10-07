"""Password hashing (bcrypt) and JSON Web Tokens (PyJWT).

Two token types are issued:
  * access  - short-lived (minutes), sent on every API call in the Authorization header
  * refresh - long-lived (days), used only at /auth/refresh to obtain a new pair
The "type" claim stops a refresh token from being accepted as an access token.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]

# bcrypt only looks at the first 72 bytes of a password; longer input is rejected
# by the request schema so two different long passwords can never collide.
BCRYPT_MAX_BYTES = 72

# Pre-computed hash used when a login email does not exist, so the response time
# is the same as for a wrong password (prevents user enumeration by timing).
_DUMMY_HASH = bcrypt.hashpw(b"timing-attack-guard", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed_password: str | None) -> bool:
    if hashed_password is None:
        bcrypt.checkpw(password.encode(), _DUMMY_HASH.encode())
        return False
    return bcrypt.checkpw(password.encode(), hashed_password.encode())


def create_token(subject: str, token_type: TokenType) -> str:
    now = datetime.now(UTC)
    lifetime = (
        timedelta(minutes=settings.access_token_expire_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_expire_days)
    )
    payload = {
        "sub": subject,  # who the token is about (user id)
        "type": token_type,
        "iat": now,  # issued at
        "exp": now + lifetime,  # expiry, enforced by jwt.decode
        "jti": uuid.uuid4().hex,  # unique id, enables revocation lists later
    }
    return jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Verify signature + expiry + type. Raises jwt.InvalidTokenError on any problem."""
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],  # pinned list: blocks "alg=none" attacks
        options={"require": ["exp", "sub", "type"]},
    )
    if payload["type"] != expected_type:
        raise jwt.InvalidTokenError(f"Expected {expected_type} token")
    return payload
