"""Local cache observation. Bars-only cannot meet A197. No synthesized ticks."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.engines.adaptive_edge.corpus_observation import observe_local_corpus
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.research_pipeline import meets_a197_contract


def _bar_db(path: Path, timestamps: list[str]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE truedata_bars (
            symbol TEXT, interval TEXT, provider_timestamp TEXT,
            PRIMARY KEY (symbol, interval, provider_timestamp)
        )
        """
    )
    conn.executemany(
        "INSERT INTO truedata_bars VALUES ('NIFTY-I', '1min', ?)",
        [(ts,) for ts in timestamps],
    )
    conn.commit()
    conn.close()


def _tick_db(path: Path, rows: list[tuple[str, float, float]]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE truedata_tick_quotes (
            symbol TEXT, provider_timestamp TEXT, bidqty REAL, askqty REAL
        )
        """
    )
    conn.executemany(
        "INSERT INTO truedata_tick_quotes VALUES ('NIFTY-I', ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_missing_stores_are_zero_and_not_a197(tmp_path: Path):
    observed = observe_local_corpus(
        bar_store=tmp_path / "missing_bars.sqlite",
        tick_store=tmp_path / "missing_ticks.sqlite",
    )
    assert observed.bar_rows == 0
    assert observed.tick_li_valid == 0
    assert observed.meets_a197 is False


def test_bars_without_li_cannot_meet_a197(tmp_path: Path):
    bars = tmp_path / "bars.sqlite"
    ticks = tmp_path / "ticks.sqlite"
    _bar_db(bars, [f"2026-02-02T09:{i:02d}:00" for i in range(15, 20)])
    _tick_db(ticks, [])
    observed = observe_local_corpus(bar_store=bars, tick_store=ticks)
    assert observed.bar_rows == 5
    assert observed.bars_on_li_days == 0
    assert observed.meets_a197 is False
    assert meets_a197_contract(
        trading_days=observed.bar_days,
        bar_count=observed.bar_rows,
        li_valid=observed.bars_on_li_days,
    ) is False


def test_li_days_only_count_bars_on_those_days(tmp_path: Path):
    bars = tmp_path / "bars.sqlite"
    ticks = tmp_path / "ticks.sqlite"
    _bar_db(
        bars,
        [
            "2026-02-02T09:15:00",
            "2026-02-02T09:16:00",
            "2026-08-18T09:15:00",
            "2026-08-18T09:16:00",
        ],
    )
    _tick_db(ticks, [("2026-08-18T09:15:01", 10.0, 8.0)])
    observed = observe_local_corpus(bar_store=bars, tick_store=ticks)
    assert observed.tick_li_valid == 1
    assert observed.tick_li_days == 1
    assert observed.bars_on_li_days == 2
    assert observed.meets_a197 is False
    assert FORMULAS["F-101"].status is FormulaStatus.LOCKED
