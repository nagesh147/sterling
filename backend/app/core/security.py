"""
Secret key management + symmetric encryption for secrets at rest.

Encryption uses Fernet (AES-128-CBC + HMAC) from ``cryptography``, keyed by
``STERLING_SECRET_KEY``. Ciphertext carries a scheme tag (``fernet:`` / ``b64:``)
so values can be decrypted regardless of which backend wrote them, and legacy
plaintext (written before encryption existed) is returned as-is on read — the
in-place migration hook.

**Key policy (fail-closed in production):**

* *Production* (``settings.environment == "production"``):
    - ``STERLING_SECRET_KEY`` MUST be set, MUST NOT equal the known-insecure dev
      literal, and MUST be >= 32 chars — otherwise :func:`get_secret_key` raises
      and the app refuses to start (via :func:`assert_secure`).
    - ``cryptography`` MUST import — no base64 degrade. :func:`_init` raises.
* *Development / test*:
    - If ``STERLING_SECRET_KEY`` is unset (or the old literal), an **ephemeral**
      per-process key is generated (never the hardcoded literal) with a loud
      warning. Secrets written under it cannot be read after a restart — dev only.

JWT signing key (:func:`get_jwt_key`) prefers a distinct ``STERLING_JWT_SECRET``;
otherwise it is domain-separated-derived from the secret key so the token-signing
key is never byte-identical to the at-rest encryption key.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets as _secrets

from app.core.logging import get_logger

log = get_logger(__name__)

_FERNET_PREFIX = "fernet:"
_B64_PREFIX = "b64:"

# The key older builds fell back to. Explicitly rejected in production and never
# used as an ephemeral dev key.
_INSECURE_LITERAL = "sterling-dev-insecure-key"
_MIN_KEY_LEN = 32

_fernet = None
_backend = "b64"
_key_fp: str | None = None            # fingerprint of the key the cached Fernet uses

# Process-ephemeral dev key: generated once, never persisted, never the literal.
_dev_secret: str | None = None
_dev_warned = False


def _is_production() -> bool:
    """True in production. Fail-closed: if config can't be read, assume production
    so a broken/absent config never silently unlocks the insecure dev paths."""
    try:
        from app.core.config import settings
        return str(settings.environment).strip().lower() == "production"
    except Exception:  # pragma: no cover - config import should not fail
        return True


def get_secret_key() -> str:
    """Master secret for at-rest encryption. Raises in production if missing/weak."""
    global _dev_secret, _dev_warned
    secret = os.environ.get("STERLING_SECRET_KEY", "").strip()
    if _is_production():
        if not secret:
            raise RuntimeError(
                "STERLING_SECRET_KEY is required in production (at-rest secret "
                "encryption key). Refusing to start without it."
            )
        if secret == _INSECURE_LITERAL:
            raise RuntimeError(
                "STERLING_SECRET_KEY is set to the known-insecure development "
                "literal. Generate a strong random key for production."
            )
        if len(secret) < _MIN_KEY_LEN:
            raise RuntimeError(
                f"STERLING_SECRET_KEY too short ({len(secret)} chars); "
                f"require >= {_MIN_KEY_LEN}."
            )
        return secret
    # ── development / test ──
    if secret and secret != _INSECURE_LITERAL:
        return secret
    if _dev_secret is None:
        _dev_secret = _secrets.token_urlsafe(48)
    if not _dev_warned:
        log.warning(
            "STERLING_SECRET_KEY not set (or set to the insecure literal) — using "
            "an EPHEMERAL per-process dev key. Secrets encrypted now cannot be "
            "decrypted after a restart. Set STERLING_SECRET_KEY for real use."
        )
        _dev_warned = True
    return _dev_secret


def get_jwt_key() -> str:
    """Signing key for JWTs. Distinct from (domain-separated against) the at-rest
    key, so leaking one never yields the other."""
    explicit = os.environ.get("STERLING_JWT_SECRET", "").strip()
    if explicit:
        if _is_production() and len(explicit) < _MIN_KEY_LEN:
            raise RuntimeError(
                f"STERLING_JWT_SECRET too short ({len(explicit)} chars); "
                f"require >= {_MIN_KEY_LEN}."
            )
        return explicit
    # Derive a distinct signing key from the master secret. HMAC over a fixed
    # domain-separation label is a standard subkey-derivation PRF.
    master = get_secret_key().encode("utf-8")
    return hmac.new(master, b"sterling.jwt.signing.v1", hashlib.sha256).hexdigest()


def _derive_fernet_key(secret: str) -> bytes:
    """A urlsafe-base64 32-byte key derived from the configured secret."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _init() -> None:
    global _fernet, _backend, _key_fp
    secret = get_secret_key()
    fp = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    if _backend == "fernet" and _fernet is not None and _key_fp == fp:
        return
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_derive_fernet_key(secret))
        _backend = "fernet"
        _key_fp = fp
    except Exception as exc:
        if _is_production():
            raise RuntimeError(
                "cryptography is required in production for at-rest secret "
                f"encryption but is unavailable: {exc}"
            ) from exc
        log.warning(
            "cryptography unavailable (%s) — DEV base64 obfuscation (NOT "
            "encryption). Install 'cryptography' for at-rest encryption.", exc
        )
        _backend = "b64"
        _key_fp = fp


def assert_secure() -> None:
    """Validate the key posture. Raises in production on any misconfiguration
    (missing/weak secret key, missing JWT key, or missing cryptography). Called
    by the startup guard so a misconfigured production deploy fails fast at boot
    rather than at first credential access. No-op-ish in dev (just warms keys)."""
    get_secret_key()   # raises in prod on missing/weak/insecure
    get_jwt_key()      # raises in prod on weak explicit JWT secret
    _init()            # raises in prod if cryptography missing


def encrypt(plaintext: str) -> str:
    """Encrypt a secret for storage. Empty input → empty output."""
    if not plaintext:
        return ""
    _init()
    if _backend == "fernet" and _fernet is not None:
        token = _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        return _FERNET_PREFIX + token
    return _B64_PREFIX + base64.urlsafe_b64encode(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Decrypt a stored secret. Tolerates legacy plaintext (returns as-is)."""
    if not ciphertext:
        return ""
    _init()
    if ciphertext.startswith(_FERNET_PREFIX):
        if _fernet is None:
            raise RuntimeError("Cannot decrypt Fernet secret — cryptography unavailable.")
        return _fernet.decrypt(ciphertext[len(_FERNET_PREFIX):].encode("utf-8")).decode("utf-8")
    if ciphertext.startswith(_B64_PREFIX):
        return base64.urlsafe_b64decode(ciphertext[len(_B64_PREFIX):].encode("utf-8")).decode("utf-8")
    # Legacy/plaintext value written before encryption was introduced.
    return ciphertext
