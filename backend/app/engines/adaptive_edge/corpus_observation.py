"""Read-only observation of local TrueData caches.

Not an A197 promotion. Does not synthesize ticks. Does not unlock F-101.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .liquidity_imbalance import compute_liquidity_imbalance
from .feature_engine import FeatureStatus
from .research_pipeline import meets_a197_contract


DEFAULT_TICK_STORE = Path(__file__).resolve().parents[3] / "data" / "truedata_ticks.sqlite"
DEFAULT_BAR_STORE = Path(__file__).resolve().parents[3] / "data" / "truedata_bars.sqlite"


@dataclass(frozen=True)
class LocalCorpusObservation:
    bar_rows: int
    bar_days: int
    bar_first: str | None
    bar_last: str | None
    tick_rows: int
    tick_days: int
    tick_first: str | None
    tick_last: str | None
    tick_li_valid: int
    tick_li_days: int
    bars_on_li_days: int
    bar_store: str
    tick_store: str

    @property
    def meets_a197(self) -> bool:
        return meets_a197_contract(
            trading_days=self.bar_days,
            bar_count=self.bar_rows,
            li_valid=self.bars_on_li_days,
        )


def _connect_ro(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _day(ts: str) -> str:
    return ts[:10] if ts else ""


def observe_local_corpus(
    *,
    bar_store: Path | str = DEFAULT_BAR_STORE,
    tick_store: Path | str = DEFAULT_TICK_STORE,
    symbol: str = "NIFTY-I",
    interval: str = "1min",
) -> LocalCorpusObservation:
    bar_path = Path(bar_store)
    tick_path = Path(tick_store)
    bar_rows = 0
    bar_days: set[str] = set()
    bar_first = bar_last = None
    conn = _connect_ro(bar_path)
    if conn is not None:
        try:
            rows = conn.execute(
                """
                SELECT provider_timestamp
                FROM truedata_bars
                WHERE symbol = ? AND interval = ?
                ORDER BY provider_timestamp
                """,
                (symbol, interval),
            ).fetchall()
        finally:
            conn.close()
        bar_rows = len(rows)
        for (ts,) in rows:
            day = _day(str(ts or ""))
            if not day:
                continue
            bar_days.add(day)
            bar_first = str(ts) if bar_first is None else min(bar_first, str(ts))
            bar_last = str(ts) if bar_last is None else max(bar_last, str(ts))

    tick_rows = 0
    tick_days: set[str] = set()
    tick_first = tick_last = None
    tick_li_valid = 0
    li_days: set[str] = set()
    conn = _connect_ro(tick_path)
    if conn is not None:
        try:
            ticks = conn.execute(
                """
                SELECT provider_timestamp, bidqty, askqty
                FROM truedata_tick_quotes
                WHERE symbol = ?
                ORDER BY provider_timestamp
                """,
                (symbol,),
            ).fetchall()
        finally:
            conn.close()
        tick_rows = len(ticks)
        for ts, bidqty, askqty in ticks:
            stamp = str(ts or "")
            day = _day(stamp)
            if day:
                tick_days.add(day)
                tick_first = stamp if tick_first is None else min(tick_first, stamp)
                tick_last = stamp if tick_last is None else max(tick_last, stamp)
            _value, status = compute_liquidity_imbalance(bidqty, askqty)
            if status is FeatureStatus.VALID and day:
                tick_li_valid += 1
                li_days.add(day)

    bars_on_li_days = 0
    if li_days and bar_days:
        conn = _connect_ro(bar_path)
        if conn is not None:
            try:
                rows = conn.execute(
                    """
                    SELECT provider_timestamp
                    FROM truedata_bars
                    WHERE symbol = ? AND interval = ?
                    """,
                    (symbol, interval),
                ).fetchall()
            finally:
                conn.close()
            bars_on_li_days = sum(1 for (ts,) in rows if _day(str(ts or "")) in li_days)

    return LocalCorpusObservation(
        bar_rows=bar_rows,
        bar_days=len(bar_days),
        bar_first=bar_first,
        bar_last=bar_last,
        tick_rows=tick_rows,
        tick_days=len(tick_days),
        tick_first=tick_first,
        tick_last=tick_last,
        tick_li_valid=tick_li_valid,
        tick_li_days=len(li_days),
        bars_on_li_days=bars_on_li_days,
        bar_store=str(bar_path),
        tick_store=str(tick_path),
    )
