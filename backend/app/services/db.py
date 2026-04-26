"""
Optional SQLite persistence layer for paper positions.
Gracefully degrades to no-op if DB unavailable (in-memory store continues working).
Path configured via STERLING_DB_PATH env var (default: sterling_paper.db).
Set to :memory: for tests (not recommended — use mock instead; see test_persistence.py).
"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import List

from app.core.logging import get_logger

log = get_logger(__name__)

_DB_PATH = os.environ.get("STERLING_DB_PATH", "sterling_paper.db")
_available = False


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id          TEXT    PRIMARY KEY,
            underlying  TEXT    NOT NULL,
            status      TEXT    NOT NULL,
            data        TEXT    NOT NULL,
            entry_ts    INTEGER NOT NULL,
            updated_ts  INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exchange_configs (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            display_name TEXT NOT NULL,
            api_key      TEXT NOT NULL DEFAULT '',
            api_secret   TEXT NOT NULL DEFAULT '',
            is_paper     INTEGER NOT NULL DEFAULT 1,
            is_active    INTEGER NOT NULL DEFAULT 0,
            extra        TEXT NOT NULL DEFAULT '{}'
        )
    """)
    conn.commit()


def init() -> bool:
    global _available
    try:
        conn = sqlite3.connect(_DB_PATH)
        _create_tables(conn)
        conn.close()
        _available = True
        log.info("SQLite positions store: %s", _DB_PATH)
        return True
    except Exception as exc:
        log.warning("SQLite unavailable — running in-memory only: %s", exc)
        _available = False
        return False


@contextmanager
def _conn():
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def upsert(pos_dict: dict) -> None:
    if not _available:
        return
    try:
        with _conn() as c:
            c.execute("""
                INSERT OR REPLACE INTO positions
                    (id, underlying, status, data, entry_ts, updated_ts)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                pos_dict["id"],
                pos_dict["underlying"],
                pos_dict["status"],
                json.dumps(pos_dict),
                pos_dict["entry_timestamp_ms"],
                int(time.time() * 1000),
            ))
    except Exception as exc:
        log.warning("DB upsert failed: %s", exc)


def remove(pos_id: str) -> None:
    if not _available:
        return
    try:
        with _conn() as c:
            c.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
    except Exception as exc:
        log.warning("DB delete failed: %s", exc)


def load_all() -> List[dict]:
    if not _available:
        return []
    try:
        with _conn() as c:
            rows = c.execute("SELECT data FROM positions").fetchall()
        return [json.loads(r["data"]) for r in rows]
    except Exception as exc:
        log.warning("DB load failed: %s", exc)
        return []
