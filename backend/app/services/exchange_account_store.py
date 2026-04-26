"""
Exchange account configuration store.
In-memory dict + write-through to SQLite (exchange_configs table).
Pre-populated with Delta Exchange India (dummy credentials, paper mode).
"""
import json
import time
import uuid
from typing import Dict, List, Optional

from app.schemas.exchange_config import ExchangeConfig, ExchangeConfigCreate, SUPPORTED_EXCHANGES
from app.core.logging import get_logger

log = get_logger(__name__)

_configs: Dict[str, ExchangeConfig] = {}
_loaded = False


def _new_id() -> str:
    return uuid.uuid4().hex[:10].upper()


# ─── SQLite persistence ───────────────────────────────────────────────────────

def _init_table() -> None:
    """Ensure exchange_configs table exists. Table is also created in db._create_tables()
    but this is kept as a safety net in case db.init() ran before this module loaded."""
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS exchange_configs (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    api_key     TEXT NOT NULL DEFAULT '',
                    api_secret  TEXT NOT NULL DEFAULT '',
                    is_paper    INTEGER NOT NULL DEFAULT 1,
                    is_active   INTEGER NOT NULL DEFAULT 0,
                    extra       TEXT NOT NULL DEFAULT '{}'
                )
            """)
    except Exception as exc:
        log.warning("exchange_configs table init failed: %s", exc)


def _persist(cfg: ExchangeConfig) -> None:
    from app.services import db
    if not db._available:
        log.warning("DB unavailable — exchange config %s not persisted (in-memory only)", cfg.id)
        return
    try:
        with db._conn() as c:
            c.execute("""
                INSERT OR REPLACE INTO exchange_configs
                    (id, name, display_name, api_key, api_secret, is_paper, is_active, extra)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cfg.id, cfg.name, cfg.display_name,
                cfg.api_key, cfg.api_secret,
                int(cfg.is_paper), int(cfg.is_active),
                json.dumps(cfg.extra),
            ))
        log.debug("exchange_config persisted: %s (%s)", cfg.id, cfg.name)
    except Exception as exc:
        log.warning("exchange_config persist failed for %s: %s", cfg.id, exc)


def _delete_db(config_id: str) -> None:
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("DELETE FROM exchange_configs WHERE id = ?", (config_id,))
    except Exception as exc:
        log.warning("exchange_config delete failed: %s", exc)


def _load_from_db() -> List[ExchangeConfig]:
    from app.services import db
    if not db._available:
        return []
    try:
        with db._conn() as c:
            rows = c.execute("SELECT * FROM exchange_configs").fetchall()
        result = []
        for r in rows:
            try:
                result.append(ExchangeConfig(
                    id=r["id"], name=r["name"], display_name=r["display_name"],
                    api_key=r["api_key"], api_secret=r["api_secret"],
                    is_paper=bool(r["is_paper"]), is_active=bool(r["is_active"]),
                    extra=json.loads(r["extra"] or "{}"),
                ))
            except Exception:
                continue
        return result
    except Exception as exc:
        log.warning("exchange_config load failed: %s", exc)
        return []


# ─── Bootstrap ────────────────────────────────────────────────────────────────

_DEFAULTS = [
    ExchangeConfig(
        id="delta_india_default",
        name="delta_india",
        display_name="Delta Exchange India",
        api_key="DUMMY_API_KEY_REPLACE_WITH_REAL_KEY",
        api_secret="DUMMY_API_SECRET_REPLACE_WITH_REAL_SECRET_00000000000000",
        is_paper=True,
        is_active=True,
        extra={},
    ),
]


def bootstrap() -> None:
    global _loaded
    if _loaded:
        return
    _init_table()
    db_configs = _load_from_db()
    if db_configs:
        for cfg in db_configs:
            _configs[cfg.id] = cfg
        log.info("Loaded %d exchange configs from DB", len(db_configs))
    else:
        for cfg in _DEFAULTS:
            _configs[cfg.id] = cfg
            _persist(cfg)
        log.info("Initialized default exchange configs (Delta India)")
    _loaded = True


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def add_exchange(data: ExchangeConfigCreate) -> ExchangeConfig:
    cfg = ExchangeConfig(
        id=_new_id(),
        name=data.name,
        display_name=data.display_name or SUPPORTED_EXCHANGES.get(data.name, data.name),
        api_key=data.api_key,
        api_secret=data.api_secret,
        is_paper=data.is_paper,
        is_active=False,
        extra=data.extra,
    )
    _configs[cfg.id] = cfg
    _persist(cfg)
    return cfg


def get_exchange(config_id: str) -> Optional[ExchangeConfig]:
    return _configs.get(config_id)


def list_exchanges() -> List[ExchangeConfig]:
    return list(_configs.values())


def update_exchange(config_id: str, **kwargs) -> Optional[ExchangeConfig]:
    cfg = _configs.get(config_id)
    if not cfg:
        return None
    # Apply all provided kwargs (endpoint already filters None-unset fields)
    updated = cfg.model_copy(update=kwargs)
    _configs[config_id] = updated
    _persist(updated)
    return updated


def delete_exchange(config_id: str) -> bool:
    if config_id not in _configs:
        return False
    was_active = _configs[config_id].is_active
    del _configs[config_id]
    _delete_db(config_id)
    if was_active and _configs:
        first = next(iter(_configs.values()))
        _configs[first.id] = first.model_copy(update={"is_active": True})
        _persist(_configs[first.id])
    return True


def set_active(config_id: str) -> Optional[ExchangeConfig]:
    if config_id not in _configs:
        return None
    for cid, cfg in _configs.items():
        is_now_active = (cid == config_id)
        if cfg.is_active != is_now_active:
            updated = cfg.model_copy(update={"is_active": is_now_active})
            _configs[cid] = updated
            _persist(updated)
    return _configs.get(config_id)


def get_active() -> Optional[ExchangeConfig]:
    return next((c for c in _configs.values() if c.is_active), None)
