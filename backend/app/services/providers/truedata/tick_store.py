"""Local TrueData tick-quote cache for LiquidityImbalance acquisition."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence


class TickStore:
    """Local TrueData tick-quote cache that carries provenance with the data.

    Mirrors `BarStore`: `source` and `source_version` round-trip through
    `load()`, and a row that declares its own provenance is never relabeled.
    """

    DEFAULT_SOURCE = "truedata"
    DEFAULT_SOURCE_VERSION = "2.6"

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
                CREATE TABLE IF NOT EXISTS truedata_tick_quotes (
                    symbol TEXT NOT NULL,
                    provider_timestamp TEXT NOT NULL,
                    row_ordinal INTEGER NOT NULL,
                    ltp REAL,
                    volume REAL,
                    oi REAL,
                    bid REAL,
                    bidqty REAL,
                    ask REAL,
                    askqty REAL,
                    request_from TEXT,
                    request_to TEXT,
                    source TEXT NOT NULL DEFAULT 'truedata',
                    source_version TEXT NOT NULL DEFAULT '2.6',
                    PRIMARY KEY (symbol, provider_timestamp, row_ordinal)
                )
                """
            )

    def upsert(
        self,
        symbol: str,
        rows: Sequence[Mapping[str, Any]],
        *,
        request_from: str,
        request_to: str,
    ) -> str:
        with self._connect() as conn:
            for ordinal, row in enumerate(rows):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO truedata_tick_quotes (
                        symbol, provider_timestamp, row_ordinal,
                        ltp, volume, oi, bid, bidqty, ask, askqty,
                        request_from, request_to, source, source_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        str(row.get("timestamp") or row.get("time") or ""),
                        ordinal,
                        _num(row.get("ltp")),
                        _num(row.get("volume")),
                        _num(row.get("oi")),
                        _num(row.get("bid")),
                        _num(row.get("bidqty")),
                        _num(row.get("ask")),
                        _num(row.get("askqty")),
                        request_from,
                        request_to,
                        _provenance(row, "source", self.DEFAULT_SOURCE),
                        _provenance(row, "source_version", self.DEFAULT_SOURCE_VERSION),
                    ),
                )
        return self.dataset_sha256(symbol)

    def load(self, symbol: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT provider_timestamp AS timestamp, row_ordinal,
                       ltp, volume, oi, bid, bidqty, ask, askqty,
                       source, source_version
                FROM truedata_tick_quotes
                WHERE symbol = ?
                ORDER BY provider_timestamp, row_ordinal
                """,
                (symbol,),
            ).fetchall()
        return [dict(row) for row in rows]

    def dataset_sha256(self, symbol: str) -> str:
        rows = self.load(symbol)
        hasher = hashlib.sha256()
        for row in rows:
            hasher.update(json.dumps(row, sort_keys=True, default=str).encode())
        return hasher.hexdigest()


def _provenance(row: Mapping[str, Any], key: str, default: str) -> str:
    """Take the row's own provenance when it states one, else the cache default."""
    value = row.get(key)
    if value is None or value == "":
        return default
    return str(value)


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
