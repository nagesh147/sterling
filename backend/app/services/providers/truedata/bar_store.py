"""Local TrueData 1-minute bar cache for trial F-101 feature construction.

Acquisition cache only. Not an A197 calibration dataset.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence


class BarStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS truedata_bars (
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    provider_timestamp TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    oi REAL,
                    request_from TEXT,
                    request_to TEXT,
                    source TEXT NOT NULL DEFAULT 'truedata',
                    source_version TEXT NOT NULL DEFAULT '2.6',
                    PRIMARY KEY (symbol, interval, provider_timestamp)
                )
                """
            )

    def upsert(
        self,
        symbol: str,
        rows: Sequence[Mapping[str, Any]],
        *,
        interval: str,
        request_from: str,
        request_to: str,
    ) -> str:
        with self._connect() as conn:
            for row in rows:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO truedata_bars (
                        symbol, interval, provider_timestamp,
                        open, high, low, close, volume, oi,
                        request_from, request_to
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        interval,
                        str(row.get("timestamp") or row.get("time") or ""),
                        _num(row.get("open")),
                        _num(row.get("high")),
                        _num(row.get("low")),
                        _num(row.get("close")),
                        _num(row.get("volume")),
                        _num(row.get("oi")),
                        request_from,
                        request_to,
                    ),
                )
        return self.dataset_sha256(symbol, interval)

    def load(self, symbol: str, *, interval: str = "1min") -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT provider_timestamp AS timestamp,
                       open, high, low, close, volume, oi
                FROM truedata_bars
                WHERE symbol = ? AND interval = ?
                ORDER BY provider_timestamp
                """,
                (symbol, interval),
            ).fetchall()
        return [dict(row) for row in rows]

    def dataset_sha256(self, symbol: str, interval: str = "1min") -> str:
        rows = self.load(symbol, interval=interval)
        hasher = hashlib.sha256()
        for row in rows:
            hasher.update(json.dumps(row, sort_keys=True, default=str).encode())
        return hasher.hexdigest()


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
