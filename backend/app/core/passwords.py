"""
Password hashing — Argon2id (OWASP's default choice for new systems).

One-way by design: a password hash is verified, never decrypted. This is
deliberately NOT routed through :mod:`app.core.security` (that is *reversible*
encryption, correct for broker secrets we must recover — wrong for passwords).

``argon2-cffi``'s library defaults track OWASP guidance; :func:`needs_rehash`
lets callers transparently upgrade stored hashes when those defaults change.
"""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from app.core.logging import get_logger

log = get_logger(__name__)

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Return an Argon2id hash (includes salt + parameters) for storage."""
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time verify. False on mismatch or any malformed/blank hash —
    never raises, so callers can treat it as a plain boolean gate."""
    if not hashed:
        return False
    try:
        return _ph.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("password verify error: %s", exc)
        return False


def needs_rehash(hashed: str) -> bool:
    """True when a stored hash was made with weaker-than-current parameters and
    should be re-hashed on the next successful login."""
    try:
        return _ph.check_needs_rehash(hashed)
    except Exception:
        return False
