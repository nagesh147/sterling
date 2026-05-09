"""
Adaptive calibration service. Persisted to SQLite.
Updated on every evaluate() call for IVR; updated on every position close for win_rate.
"""
import json
import sqlite3
import time
from collections import deque

import numpy as np

from app.core.logging import get_logger

log = get_logger(__name__)

_DB_PATH_DEFAULT = "sterling_paper.db"


class CalibrationService:
    IVR_WINDOW  = 90
    WIN_RATE_N  = 50

    def __init__(self, db_path: str = _DB_PATH_DEFAULT):
        self._db_path = db_path
        self._ivr_history: dict = {}
        self._closed_trades: deque = deque(maxlen=self.WIN_RATE_N)
        self._load_from_db()

    # ── IVR percentile ──────────────────────────────────────────────────
    def record_ivr(self, underlying: str, ivr: float) -> None:
        if underlying not in self._ivr_history:
            self._ivr_history[underlying] = deque(maxlen=self.IVR_WINDOW)
        self._ivr_history[underlying].append(ivr)
        self._persist_ivr(underlying)

    def ivr_bands(self, underlying: str) -> tuple:
        """Returns (buy_threshold, sell_threshold). Falls back to (30, 70) if < 20 readings."""
        hist = list(self._ivr_history.get(underlying, []))
        if len(hist) < 20:
            return 30.0, 70.0
        return float(np.percentile(hist, 30)), float(np.percentile(hist, 70))

    # ── Adaptive win-rate ────────────────────────────────────────────────
    def record_trade(self, pnl_pct: float, regime: str) -> None:
        self._closed_trades.append({'pnl': pnl_pct, 'regime': regime, 'ts': time.time()})
        self._persist_trade(pnl_pct, regime)

    def win_rate(self, regime: str | None = None) -> float:
        """
        Trailing win rate from last WIN_RATE_N trades.
        Regime-specific if provided (min 10 trades). Falls back to 0.52.
        """
        trades = list(self._closed_trades)
        if regime:
            trades = [t for t in trades if t['regime'] == regime]
        if len(trades) < 10:
            return 0.52
        return float(np.mean([t['pnl'] > 0 for t in trades]))

    def trade_count(self) -> int:
        return len(self._closed_trades)

    def ivr_readings_count(self, underlying: str) -> int:
        return len(self._ivr_history.get(underlying, []))

    # ── Persistence ──────────────────────────────────────────────────────
    def _conn(self):
        c = sqlite3.connect(self._db_path)
        c.row_factory = sqlite3.Row
        return c

    def _persist_ivr(self, underlying: str) -> None:
        try:
            hist = list(self._ivr_history.get(underlying, []))
            with self._conn() as c:
                c.execute(
                    "INSERT OR REPLACE INTO calibration_state (underlying, ivr_history_json, updated_at)"
                    " VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (underlying, json.dumps(hist)),
                )
        except Exception as exc:
            log.warning("calibration_state persist failed: %s", exc)

    def _persist_trade(self, pnl_pct: float, regime: str) -> None:
        try:
            with self._conn() as c:
                c.execute(
                    "INSERT INTO calibration_trades (pnl_pct, regime) VALUES (?, ?)",
                    (pnl_pct, regime),
                )
        except Exception as exc:
            log.warning("calibration_trades persist failed: %s", exc)

    def _load_from_db(self) -> None:
        try:
            with self._conn() as c:
                rows = c.execute("SELECT underlying, ivr_history_json FROM calibration_state").fetchall()
                for row in rows:
                    hist = json.loads(row["ivr_history_json"] or "[]")
                    self._ivr_history[row["underlying"]] = deque(hist, maxlen=self.IVR_WINDOW)

                trades = c.execute(
                    "SELECT pnl_pct, regime FROM calibration_trades ORDER BY id DESC LIMIT ?",
                    (self.WIN_RATE_N,),
                ).fetchall()
                for t in reversed(trades):
                    self._closed_trades.append({'pnl': t["pnl_pct"], 'regime': t["regime"], 'ts': 0})
        except Exception as exc:
            log.debug("calibration load from db (expected on first run): %s", exc)
