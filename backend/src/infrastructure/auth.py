"""Password hashing and session tokens.

Infrastructure, not domain: it depends on bcrypt, and `src/domain` is meant to
import nothing outside the standard library.

Passwords are bcrypt-hashed. Session tokens are high-entropy random strings, so
they only need a fast digest at rest — SHA-256 — not a password KDF. Storing the
digest rather than the token means a dump of the sessions table hands out no
usable session.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

import bcrypt


SESSION_TTL = timedelta(days=30)

# bcrypt silently ignores everything past 72 bytes; refuse instead of pretending
# a longer password was checked in full.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_CHARS = 8


class PasswordError(ValueError):
    """Raised when a password cannot be accepted as given."""


def validate_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_CHARS:
        raise PasswordError(f"password must be at least {MIN_PASSWORD_CHARS} characters")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise PasswordError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
    return password


def hash_password(password: str) -> str:
    validate_password(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False


def new_session_token() -> str:
    """The secret handed to the client. Never stored as-is."""
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry(now: datetime | None = None) -> datetime:
    return (now or datetime.now()) + SESSION_TTL
