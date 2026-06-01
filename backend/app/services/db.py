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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS webhooks (
            id               TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            webhook_type     TEXT NOT NULL,
            url              TEXT NOT NULL,
            extra            TEXT NOT NULL DEFAULT '{}',
            active           INTEGER NOT NULL DEFAULT 1,
            created_at_ms    INTEGER NOT NULL,
            last_triggered_ms INTEGER,
            trigger_count    INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id               TEXT PRIMARY KEY,
            underlying       TEXT NOT NULL,
            condition        TEXT NOT NULL,
            threshold        REAL,
            target_state     TEXT,
            cooldown_hours   REAL NOT NULL DEFAULT 0,
            notes            TEXT NOT NULL DEFAULT '',
            status           TEXT NOT NULL DEFAULT 'active',
            triggered_at_ms  INTEGER,
            trigger_value    REAL,
            created_at_ms    INTEGER NOT NULL,
            fire_count       INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signal_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            underlying  TEXT NOT NULL,
            data        TEXT NOT NULL,
            timestamp_ms INTEGER NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_signal_history_underlying ON signal_history(underlying)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS arrows (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            underlying   TEXT    NOT NULL,
            arrow_type   TEXT    NOT NULL,
            spot_price   REAL    NOT NULL,
            direction    TEXT    NOT NULL,
            state        TEXT    NOT NULL,
            source       TEXT    NOT NULL,
            timestamp_ms INTEGER NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_arrows_und ON arrows(underlying, timestamp_ms)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.execute("INSERT OR IGNORE INTO system_config VALUES ('trading_mode', 'swing')")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS iv_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            underlying TEXT NOT NULL,
            ivr        REAL NOT NULL,
            ts         REAL NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_iv_history_und ON iv_history(underlying, ts)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS option_iv_ticks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            underlying TEXT NOT NULL,
            expiry     TEXT NOT NULL,
            strike     REAL NOT NULL,
            opt_type   TEXT NOT NULL,
            mark_iv    REAL,
            bid_iv     REAL,
            ask_iv     REAL,
            delta      REAL,
            gamma      REAL,
            theta      REAL,
            vega       REAL,
            rho        REAL,
            ts         REAL NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_option_iv_ticks_und_ts ON option_iv_ticks(underlying, ts)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_option_iv_ticks_expiry ON option_iv_ticks(expiry)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS iv_surface_params (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            underlying TEXT NOT NULL,
            c0         REAL NOT NULL,
            c1         REAL NOT NULL,
            c2         REAL NOT NULL,
            c3         REAL NOT NULL,
            c4         REAL NOT NULL,
            ts         REAL NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_iv_surface_params_und_ts ON iv_surface_params(underlying, ts)"
    )
    # Add trail stop columns to positions (idempotent)
    for stmt in [
        "ALTER TABLE positions ADD COLUMN trail_stop_json TEXT",
        "ALTER TABLE positions ADD COLUMN trail_mode TEXT",
        "ALTER TABLE positions ADD COLUMN entry_price_real REAL",
    ]:
        try:
            conn.execute(stmt)
        except Exception:
            pass
    # v3 tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wf_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            underlying TEXT NOT NULL,
            run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            config_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            recommended_threshold REAL,
            oos_sharpe REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parameter_sensitivity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            underlying TEXT NOT NULL,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            results_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calibration_state (
            underlying TEXT PRIMARY KEY,
            ivr_history_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calibration_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pnl_pct REAL NOT NULL,
            regime TEXT,
            closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS equity_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_value REAL NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            drawdown REAL,
            circuit_breaker_state TEXT
        )
    """)
    for stmt in [
        "ALTER TABLE positions ADD COLUMN greeks_json TEXT",
        "ALTER TABLE positions ADD COLUMN notional REAL",
        "ALTER TABLE positions ADD COLUMN slippage_bps REAL",
    ]:
        try:
            conn.execute(stmt)
        except Exception:
            pass
    conn.commit()


def _configure(conn: sqlite3.Connection) -> None:
    """Apply concurrency pragmas. WAL lets readers and a writer coexist (the
    server runs ~10 background loops against this DB); busy_timeout makes a
    blocked writer WAIT instead of failing instantly with 'database is locked'
    (the cause of dropped config/position/state writes on the 2.8GB store)."""
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass


def init() -> bool:
    global _available
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
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
    c = sqlite3.connect(_DB_PATH, timeout=30.0)
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    _configure(c)
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


def get_trading_mode() -> str:
    if not _available:
        return "swing"
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT value FROM system_config WHERE key='trading_mode'"
            ).fetchone()
        return row["value"] if row else "swing"
    except Exception:
        return "swing"


def get_config(key: str, default: str = "") -> str:
    if not _available:
        return default
    try:
        with _conn() as c:
            row = c.execute("SELECT value FROM system_config WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default
    except Exception:
        return default


def set_config(key: str, value: str) -> None:
    if not _available:
        return
    try:
        with _conn() as c:
            c.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (key, value))
    except Exception as exc:
        log.warning("DB set_config failed for %s: %s", key, exc)


def set_trading_mode(name: str) -> None:
    if not _available:
        return
    try:
        with _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO system_config (key, value) VALUES ('trading_mode', ?)",
                (name,),
            )
    except Exception as exc:
        log.warning("DB set_trading_mode failed: %s", exc)


def record_iv(underlying: str, ivr: float) -> None:
    if not _available:
        return
    import time
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO iv_history (underlying, ivr, ts) VALUES (?, ?, ?)",
                (underlying, ivr, time.time()),
            )
    except Exception as exc:
        log.warning("DB record_iv failed: %s", exc)


def record_option_ticks(ticks_data: list[tuple]) -> None:
    if not _available or not ticks_data:
        return
    try:
        with _conn() as c:
            c.executemany(
                """INSERT INTO option_iv_ticks 
                   (underlying, expiry, strike, opt_type, mark_iv, bid_iv, ask_iv, delta, gamma, theta, vega, rho, ts) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ticks_data
            )
    except Exception as exc:
        log.warning("DB record_option_ticks failed: %s", exc)


def record_surface_params(underlying: str, coeffs: list[float], ts: float) -> None:
    if not _available or len(coeffs) != 5:
        return
    try:
        with _conn() as c:
            c.execute(
                """INSERT INTO iv_surface_params 
                   (underlying, c0, c1, c2, c3, c4, ts) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (underlying, coeffs[0], coeffs[1], coeffs[2], coeffs[3], coeffs[4], ts)
            )
    except Exception as exc:
        log.warning("DB record_surface_params failed: %s", exc)


def get_iv_history(underlying: str, limit: int = 252) -> list:
    if not _available:
        return []
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT ivr FROM iv_history WHERE underlying=? ORDER BY ts DESC LIMIT ?",
                (underlying, limit),
            ).fetchall()
        return [r["ivr"] for r in rows]
    except Exception:
        return []


def persist_arrow(
    underlying: str,
    arrow_type: str,
    spot_price: float,
    direction: str,
    state: str,
    source: str,
    timestamp_ms: int,
) -> None:
    if not _available:
        return
    try:
        with _conn() as c:
            c.execute(
                """INSERT INTO arrows
                   (underlying, arrow_type, spot_price, direction, state, source, timestamp_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (underlying, arrow_type, spot_price, direction, state, source, timestamp_ms),
            )
    except Exception as exc:
        log.warning("DB persist_arrow failed: %s", exc)


def load_arrows(underlying: str | None = None, limit: int = 500, ttl_hours: int = 168) -> list:
    if not _available:
        return []
    import time as _time
    cutoff_ms = int((_time.time() - ttl_hours * 3600) * 1000)
    try:
        with _conn() as c:
            if underlying:
                rows = c.execute(
                    "SELECT * FROM arrows WHERE underlying=? AND timestamp_ms >= ?"
                    " ORDER BY timestamp_ms DESC LIMIT ?",
                    (underlying, cutoff_ms, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM arrows WHERE timestamp_ms >= ?"
                    " ORDER BY timestamp_ms DESC LIMIT ?",
                    (cutoff_ms, limit),
                ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("DB load_arrows failed: %s", exc)
        return []


def get_recent_closed_trades(n: int = 5) -> list:
    if not _available:
        return []
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT data FROM positions WHERE status='closed' ORDER BY updated_ts DESC LIMIT ?",
                (n,),
            ).fetchall()
        import json as _json
        return [_json.loads(r["data"]) for r in rows]
    except Exception:
        return []


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


def record_equity_snapshot(portfolio_value: float, drawdown: float | None = None, cb_state: str | None = None) -> None:
    if not _available:
        return
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO equity_snapshots (portfolio_value, drawdown, circuit_breaker_state) VALUES (?, ?, ?)",
                (portfolio_value, drawdown, cb_state),
            )
    except Exception as exc:
        log.warning("record_equity_snapshot failed: %s", exc)


def save_wf_result(underlying: str, config_json: str, result_json: str, rec_threshold: float, oos_sharpe: float) -> None:
    if not _available:
        return
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO wf_results (underlying, config_json, result_json, recommended_threshold, oos_sharpe)"
                " VALUES (?, ?, ?, ?, ?)",
                (underlying, config_json, result_json, rec_threshold, oos_sharpe),
            )
    except Exception as exc:
        log.warning("save_wf_result failed: %s", exc)


def get_latest_wf_result(underlying: str) -> dict | None:
    if not _available:
        return None
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT * FROM wf_results WHERE underlying=? ORDER BY run_at DESC LIMIT 1",
                (underlying,),
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def save_sensitivity(underlying: str, results_json: str) -> None:
    if not _available:
        return
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO parameter_sensitivity (underlying, results_json) VALUES (?, ?)",
                (underlying, results_json),
            )
    except Exception as exc:
        log.warning("save_sensitivity failed: %s", exc)


def get_latest_sensitivity(underlying: str) -> dict | None:
    if not _available:
        return None
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT * FROM parameter_sensitivity WHERE underlying=? ORDER BY computed_at DESC LIMIT 1",
                (underlying,),
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def get_closed_positions_for(underlying: str | None = None) -> list:
    if not _available:
        return []
    try:
        with _conn() as c:
            if underlying:
                rows = c.execute(
                    "SELECT data FROM positions WHERE status='closed' AND underlying=? ORDER BY updated_ts DESC",
                    (underlying,),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT data FROM positions WHERE status='closed' ORDER BY updated_ts DESC"
                ).fetchall()
        return [json.loads(r["data"]) for r in rows]
    except Exception:
        return []


def get_equity_snapshots(limit: int = 500) -> list:
    if not _available:
        return []
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT portfolio_value, drawdown, circuit_breaker_state, recorded_at"
                " FROM equity_snapshots ORDER BY recorded_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
