"""Multi-tenant TrueData credential store.

Per-user credential + session persistence in SQLite table ``truedata_credentials``
with sensitive fields (password, session_token) encrypted at rest via
:mod:`app.core.security` keyed by ``STERLING_SECRET_KEY``.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.core.logging import get_logger
from app.core.security import decrypt, encrypt
from app.services.market_data.truedata import TrueDataHistoricalClient

from .config import DEFAULT_CONFIG
from .models import (
    TrueDataCredentialCreate,
    TrueDataCredentialResponse,
    TrueDataCredentialUpdate,
)

log = get_logger(__name__)

_credentials: Dict[str, "_Account"] = {}
_loaded = False


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_id() -> str:
    return "TD-" + uuid.uuid4().hex[:10].upper()


@dataclass
class _Account:
    id: str
    user_id: str
    label: str
    username: str = ""
    password_enc: str = ""
    session_token_enc: str = ""
    token_expires_at: Optional[float] = None
    realtime_port: int = 8082
    is_active: bool = False
    last_login_at_ms: Optional[int] = None
    created_at_ms: int = field(default_factory=_now_ms)
    updated_at_ms: int = field(default_factory=_now_ms)

    @property
    def password(self) -> str:
        return decrypt(self.password_enc)

    @property
    def session_token(self) -> str:
        return decrypt(self.session_token_enc)

    @property
    def has_credentials(self) -> bool:
        return bool(self.username and self.password_enc)

    @property
    def connected(self) -> bool:
        if self.session_token_enc:
            if self.token_expires_at and time.time() >= self.token_expires_at:
                return False
            return True
        return self.has_credentials

    def username_hint(self) -> str:
        if not self.username:
            return "****"
        if len(self.username) <= 4:
            return "****"
        return self.username[:2] + "****" + self.username[-2:]


# ── SQLite Persistence ────────────────────────────────────────────────────────
def _init_table() -> None:
    from app.services import db

    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("BEGIN")
            try:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS truedata_credentials (
                        id                 TEXT PRIMARY KEY,
                        user_id            TEXT NOT NULL,
                        label              TEXT NOT NULL DEFAULT 'My TrueData Feed',
                        username           TEXT NOT NULL DEFAULT '',
                        password_enc       TEXT NOT NULL DEFAULT '',
                        session_token_enc  TEXT NOT NULL DEFAULT '',
                        token_expires_at   REAL,
                        realtime_port      INTEGER NOT NULL DEFAULT 8082,
                        is_active          INTEGER NOT NULL DEFAULT 0,
                        last_login_at_ms   INTEGER,
                        created_at_ms      INTEGER NOT NULL,
                        updated_at_ms      INTEGER NOT NULL
                    )
                """)
                c.execute(
                    "CREATE INDEX IF NOT EXISTS ix_truedata_creds_user ON truedata_credentials(user_id)"
                )
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
    except Exception as exc:
        log.warning("truedata_credentials table init failed: %s", exc)


def _persist(a: _Account) -> None:
    from app.services import db

    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO truedata_credentials
                    (id, user_id, label, username, password_enc, session_token_enc,
                     token_expires_at, realtime_port, is_active, last_login_at_ms,
                     created_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    a.id,
                    a.user_id,
                    a.label,
                    a.username,
                    a.password_enc,
                    a.session_token_enc,
                    a.token_expires_at,
                    a.realtime_port,
                    int(a.is_active),
                    a.last_login_at_ms,
                    a.created_at_ms,
                    a.updated_at_ms,
                ),
            )
    except Exception as exc:
        log.warning("truedata_credentials persist failed for %s: %s", a.id, exc)


def _delete_db(account_id: str) -> None:
    from app.services import db

    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("DELETE FROM truedata_credentials WHERE id = ?", (account_id,))
    except Exception as exc:
        log.warning("truedata_credentials delete failed: %s", exc)


def _load_from_db() -> List[_Account]:
    from app.services import db

    if not db._available:
        return []
    try:
        with db._conn() as c:
            rows = c.execute("SELECT * FROM truedata_credentials").fetchall()
        out = []
        for r in rows:
            out.append(
                _Account(
                    id=r["id"],
                    user_id=r["user_id"],
                    label=r["label"],
                    username=r["username"],
                    password_enc=r["password_enc"],
                    session_token_enc=r["session_token_enc"],
                    token_expires_at=r["token_expires_at"],
                    realtime_port=r["realtime_port"],
                    is_active=bool(r["is_active"]),
                    last_login_at_ms=r["last_login_at_ms"],
                    created_at_ms=r["created_at_ms"],
                    updated_at_ms=r["updated_at_ms"],
                )
            )
        return out
    except Exception as exc:
        log.warning("truedata_credentials load failed: %s", exc)
        return []


def bootstrap() -> None:
    global _loaded
    if _loaded:
        return
    _init_table()
    for a in _load_from_db():
        _credentials[a.id] = a
    _loaded = True


# ── CRUD Methods ──────────────────────────────────────────────────────────────
def add(user_id: str, data: TrueDataCredentialCreate) -> _Account:
    bootstrap()
    first_for_user = not any(a.user_id == user_id for a in _credentials.values())
    clean_user = data.username.strip() if data.username else ""
    clean_pass = data.password.strip() if data.password else ""
    a = _Account(
        id=_new_id(),
        user_id=user_id,
        label=data.label or "My TrueData Feed",
        username=clean_user,
        password_enc=encrypt(clean_pass),
        realtime_port=data.realtime_port,
        is_active=first_for_user,
    )
    _credentials[a.id] = a
    _persist(a)
    return a


def get(user_id: str, account_id: str) -> Optional[_Account]:
    bootstrap()
    a = _credentials.get(account_id)
    return a if a and a.user_id == user_id else None


def list_credentials(user_id: str) -> List[_Account]:
    bootstrap()
    return [a for a in _credentials.values() if a.user_id == user_id]


def update(user_id: str, account_id: str, data: TrueDataCredentialUpdate) -> Optional[_Account]:
    bootstrap()
    a = get(user_id, account_id)
    if not a:
        return None
    if data.label is not None:
        a.label = data.label
    if data.username is not None:
        a.username = data.username.strip()
    if data.password is not None:
        a.password_enc = encrypt(data.password.strip())
    if data.realtime_port is not None:
        a.realtime_port = data.realtime_port
    a.updated_at_ms = _now_ms()
    _persist(a)
    return a


def delete(user_id: str, account_id: str) -> bool:
    bootstrap()
    a = get(user_id, account_id)
    if not a:
        return False
    was_active = a.is_active
    del _credentials[account_id]
    _delete_db(account_id)
    if was_active:
        remaining = list_credentials(user_id)
        if remaining:
            remaining[0].is_active = True
            remaining[0].updated_at_ms = _now_ms()
            _persist(remaining[0])
    return True


def get_active(user_id: str) -> Optional[_Account]:
    bootstrap()
    active = next((a for a in _credentials.values() if a.user_id == user_id and a.is_active), None)
    if active:
        return active
    # Environment variable fallback if configured
    env_user = DEFAULT_CONFIG.env_username
    env_pass = DEFAULT_CONFIG.env_password
    if env_user and env_pass:
        return _Account(
            id="TD-ENV",
            user_id=user_id,
            label="Environment TrueData",
            username=env_user,
            password_enc=encrypt(env_pass),
            is_active=True,
        )
    return None


def save_session(
    user_id: str, account_id: str, *, access_token: str, expires_at: float
) -> Optional[_Account]:
    a = get(user_id, account_id)
    if not a:
        return None
    a.session_token_enc = encrypt(access_token)
    a.token_expires_at = expires_at
    a.last_login_at_ms = _now_ms()
    a.updated_at_ms = a.last_login_at_ms
    _persist(a)
    return a


def to_response(a: _Account) -> TrueDataCredentialResponse:
    return TrueDataCredentialResponse(
        id=a.id,
        user_id=a.user_id,
        label=a.label,
        username_hint=a.username_hint(),
        has_credentials=a.has_credentials,
        connected=a.connected,
        is_active=a.is_active,
        realtime_port=a.realtime_port,
        token_expires_at=a.token_expires_at,
        last_login_at_ms=a.last_login_at_ms,
        created_at_ms=a.created_at_ms,
        updated_at_ms=a.updated_at_ms,
    )


def build_client(a: _Account) -> TrueDataHistoricalClient:
    """Construct a TrueDataHistoricalClient from stored account (secrets decrypted in-memory)."""
    return TrueDataHistoricalClient(
        username=a.username,
        password=a.password,
    )


def clear() -> None:
    """Test hook — wipe in-memory state into loaded & empty state."""
    global _loaded
    _credentials.clear()
    _loaded = True
