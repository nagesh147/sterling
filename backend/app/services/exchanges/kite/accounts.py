"""
Multi-tenant Kite account store.

Per-user credential + session persistence (SQLite ``kite_accounts`` table,
write-through over an in-memory dict — same proven pattern as
``exchange_account_store``, but scoped by ``user_id`` and with secrets encrypted
at rest via :mod:`app.core.security`).

Secrets (``api_secret``, ``access_token``) are encrypted; ``api_key`` is stored in
the clear (it is semi-public — it appears in the login URL). Responses never leak
raw secrets, only a masked hint.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.core.logging import get_logger
from app.core.security import decrypt, encrypt

from .models import KiteAccountCreate, KiteAccountResponse, KiteAccountUpdate

log = get_logger(__name__)

_accounts: Dict[str, "_Account"] = {}
_loaded = False


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_id() -> str:
    return "KITE-" + uuid.uuid4().hex[:10].upper()


@dataclass
class _Account:
    id: str
    user_id: str
    label: str
    api_key: str = ""
    api_secret_enc: str = ""
    access_token_enc: str = ""
    refresh_token_enc: str = ""
    public_token: str = ""
    kite_user_id: str = ""
    is_paper: bool = True
    is_active: bool = False
    last_login_at_ms: Optional[int] = None
    created_at_ms: int = field(default_factory=_now_ms)
    updated_at_ms: int = field(default_factory=_now_ms)

    # ── derived ──
    @property
    def api_secret(self) -> str:
        return decrypt(self.api_secret_enc)

    @property
    def access_token(self) -> str:
        return decrypt(self.access_token_enc)

    @property
    def refresh_token(self) -> str:
        return decrypt(self.refresh_token_enc)

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key and self.api_secret_enc)

    @property
    def connected(self) -> bool:
        return bool(self.access_token_enc)

    def api_key_hint(self) -> str:
        if not self.api_key or len(self.api_key) < 4:
            return "****"
        return "****" + self.api_key[-4:]


# ─── SQLite persistence ───────────────────────────────────────────────────────
def _init_table() -> None:
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS kite_accounts (
                    id               TEXT PRIMARY KEY,
                    user_id          TEXT NOT NULL,
                    label            TEXT NOT NULL DEFAULT 'My Kite',
                    api_key          TEXT NOT NULL DEFAULT '',
                    api_secret_enc   TEXT NOT NULL DEFAULT '',
                    access_token_enc TEXT NOT NULL DEFAULT '',
                    refresh_token_enc TEXT NOT NULL DEFAULT '',
                    public_token     TEXT NOT NULL DEFAULT '',
                    kite_user_id     TEXT NOT NULL DEFAULT '',
                    is_paper         INTEGER NOT NULL DEFAULT 1,
                    is_active        INTEGER NOT NULL DEFAULT 0,
                    last_login_at_ms INTEGER,
                    created_at_ms    INTEGER NOT NULL,
                    updated_at_ms    INTEGER NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS ix_kite_accounts_user ON kite_accounts(user_id)")
            # Idempotent migration for DBs created before refresh_token persistence.
            try:
                c.execute("ALTER TABLE kite_accounts ADD COLUMN refresh_token_enc TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass  # column already exists
    except Exception as exc:
        log.warning("kite_accounts table init failed: %s", exc)


def _persist(a: _Account) -> None:
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("""
                INSERT OR REPLACE INTO kite_accounts
                    (id, user_id, label, api_key, api_secret_enc, access_token_enc,
                     refresh_token_enc, public_token, kite_user_id, is_paper, is_active,
                     last_login_at_ms, created_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                a.id, a.user_id, a.label, a.api_key, a.api_secret_enc, a.access_token_enc,
                a.refresh_token_enc, a.public_token, a.kite_user_id, int(a.is_paper),
                int(a.is_active), a.last_login_at_ms, a.created_at_ms, a.updated_at_ms,
            ))
    except Exception as exc:
        log.warning("kite_accounts persist failed for %s: %s", a.id, exc)


def _delete_db(account_id: str) -> None:
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("DELETE FROM kite_accounts WHERE id = ?", (account_id,))
    except Exception as exc:
        log.warning("kite_accounts delete failed: %s", exc)


def _load_from_db() -> List[_Account]:
    from app.services import db
    if not db._available:
        return []
    try:
        with db._conn() as c:
            rows = c.execute("SELECT * FROM kite_accounts").fetchall()
        out = []
        for r in rows:
            out.append(_Account(
                id=r["id"], user_id=r["user_id"], label=r["label"], api_key=r["api_key"],
                api_secret_enc=r["api_secret_enc"], access_token_enc=r["access_token_enc"],
                refresh_token_enc=(r["refresh_token_enc"] if "refresh_token_enc" in r.keys() else ""),
                public_token=r["public_token"], kite_user_id=r["kite_user_id"],
                is_paper=bool(r["is_paper"]), is_active=bool(r["is_active"]),
                last_login_at_ms=r["last_login_at_ms"],
                created_at_ms=r["created_at_ms"], updated_at_ms=r["updated_at_ms"],
            ))
        return out
    except Exception as exc:
        log.warning("kite_accounts load failed: %s", exc)
        return []


def bootstrap() -> None:
    global _loaded
    if _loaded:
        return
    _init_table()
    for a in _load_from_db():
        _accounts[a.id] = a
    _loaded = True


# ─── CRUD (user-scoped) ───────────────────────────────────────────────────────
def add(user_id: str, data: KiteAccountCreate) -> _Account:
    first_for_user = not any(a.user_id == user_id for a in _accounts.values())
    a = _Account(
        id=_new_id(), user_id=user_id, label=data.label or "My Kite",
        api_key=data.api_key, api_secret_enc=encrypt(data.api_secret),
        is_paper=data.is_paper, is_active=first_for_user,  # first account auto-active
    )
    _accounts[a.id] = a
    _persist(a)
    return a


def get(user_id: str, account_id: str) -> Optional[_Account]:
    a = _accounts.get(account_id)
    return a if a and a.user_id == user_id else None


def list_accounts(user_id: str) -> List[_Account]:
    return [a for a in _accounts.values() if a.user_id == user_id]


def update(user_id: str, account_id: str, data: KiteAccountUpdate) -> Optional[_Account]:
    a = get(user_id, account_id)
    if not a:
        return None
    if data.label is not None:
        a.label = data.label
    if data.api_key is not None:
        a.api_key = data.api_key
    if data.api_secret is not None:
        a.api_secret_enc = encrypt(data.api_secret)
    if data.is_paper is not None:
        a.is_paper = data.is_paper
    a.updated_at_ms = _now_ms()
    _persist(a)
    return a


def delete(user_id: str, account_id: str) -> bool:
    a = get(user_id, account_id)
    if not a:
        return False
    was_active = a.is_active
    del _accounts[account_id]
    _delete_db(account_id)
    if was_active:
        remaining = list_accounts(user_id)
        if remaining:
            remaining[0].is_active = True
            remaining[0].updated_at_ms = _now_ms()
            _persist(remaining[0])
    return True


def set_active(user_id: str, account_id: str) -> Optional[_Account]:
    target = get(user_id, account_id)
    if not target:
        return None
    for a in list_accounts(user_id):
        want = (a.id == account_id)
        if a.is_active != want:
            a.is_active = want
            a.updated_at_ms = _now_ms()
            _persist(a)
    return get(user_id, account_id)


def get_active(user_id: str) -> Optional[_Account]:
    return next((a for a in _accounts.values() if a.user_id == user_id and a.is_active), None)


def find_by_kite_user_id(kite_user_id: str) -> Optional[_Account]:
    """Resolve a Zerodha user id (carried in order postbacks) → stored account.

    Order postbacks identify the trader by their Kite ``user_id``, not our app
    ``user_id``; this maps it back so the update can be routed to the right tenant.
    """
    if not kite_user_id:
        return None
    return next((a for a in _accounts.values() if a.kite_user_id == kite_user_id), None)


def save_session(user_id: str, account_id: str, *, access_token: str,
                 refresh_token: str = "", public_token: str = "",
                 kite_user_id: str = "") -> Optional[_Account]:
    a = get(user_id, account_id)
    if not a:
        return None
    a.access_token_enc = encrypt(access_token)
    # Keep the existing refresh_token if the caller didn't supply a new one (a
    # token refresh may not return one); only re-encrypt when present.
    if refresh_token:
        a.refresh_token_enc = encrypt(refresh_token)
    a.public_token = public_token
    a.kite_user_id = kite_user_id or a.kite_user_id
    a.last_login_at_ms = _now_ms()
    a.updated_at_ms = a.last_login_at_ms
    _persist(a)
    return a


def clear_session(user_id: str, account_id: str) -> Optional[_Account]:
    a = get(user_id, account_id)
    if not a:
        return None
    a.access_token_enc = ""
    a.public_token = ""
    a.updated_at_ms = _now_ms()
    _persist(a)
    return a


def to_response(a: _Account) -> KiteAccountResponse:
    return KiteAccountResponse(
        id=a.id, user_id=a.user_id, label=a.label, api_key_hint=a.api_key_hint(),
        has_credentials=a.has_credentials, is_paper=a.is_paper, is_active=a.is_active,
        connected=a.connected, kite_user_id=a.kite_user_id or None,
        last_login_at_ms=a.last_login_at_ms,
        created_at_ms=a.created_at_ms, updated_at_ms=a.updated_at_ms,
    )


def build_client(a: _Account):
    """Construct a KiteClient from a stored account (secrets decrypted in-memory)."""
    from .client import KiteClient
    return KiteClient(
        api_key=a.api_key, api_secret=a.api_secret, access_token=a.access_token,
        is_paper=a.is_paper,
    )


def clear() -> None:
    """Test hook — wipe in-memory state into a 'loaded & empty' state.

    Sets ``_loaded=True`` so a subsequent app-startup ``bootstrap()`` is a no-op and
    never reloads stale rows from a shared test DB (kite has no default account to
    seed, so there is nothing to bootstrap in tests). Keeps the suite deterministic
    regardless of whether another test has flipped ``db._available`` on."""
    global _loaded
    _accounts.clear()
    _loaded = True
