"""Regression coverage for signal-board continuity and confluence bar alignment."""
from datetime import datetime, timezone

import numpy as np
import pytest

from app.domain.models import Candle
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.schemas import (
    AlignmentChip,
    EngineSignalRow,
    OptionLeg,
)
from app.services.kite_engine.scanner import KiteEngineScanner
from app.services.kite_engine.signal_board_runtime import (
    _option_anchor,
    _trim_to_anchor,
    merge_retained_confluence,
)
from app.services.kite_engine.universe import UniverseItem


def _candle(ts: int) -> Candle:
    return Candle(
        timestamp_ms=ts,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1.0,
    )


def _candles(close_path, *, start_ms: int = 1_700_000_000_000) -> list[Candle]:
    close = np.asarray(close_path, dtype=float)
    open_ = np.concatenate([[close[0]], close[:-1]])
    return [
        Candle(
            timestamp_ms=start_ms + i * 3_600_000,
            open=float(open_[i]),
            high=float(max(open_[i], close[i]) + 1.0),
            low=float(min(open_[i], close[i]) - 1.0),
            close=float(close[i]),
            volume=1.0,
        )
        for i in range(len(close))
    ]


def _row(ts: int, *, active: bool = True, fresh: bool = True) -> EngineSignalRow:
    return EngineSignalRow(
        underlying="NIFTY 50",
        token=256265,
        exchange="NFO",
        regime="BULL",
        alignment=AlignmentChip(fast=1, mid=1, slow=1),
        direction="long",
        option_type="CE",
        legs=[OptionLeg(
            moneyness="ATM",
            option_type="CE",
            option_symbol="NIFTY_TEST_CE",
            strike=25000.0,
            expiry="2026-07-28",
            token=1,
            is_active=active,
        )],
        spot=25000.0,
        stop_loss=24900.0,
        score=85.0,
        timestamp_ms=ts,
        source="confluence",
        is_active=active,
        is_fresh=fresh,
    )


def test_option_history_is_trimmed_to_latest_underlying_closed_bar():
    anchors = {"NIFTY": 7_200_000, "NIFTYNXT50": 10_800_000}
    assert _option_anchor("NIFTY2672825000CE", anchors) == 7_200_000
    assert _option_anchor("NIFTYNXT502672868000CE", anchors) == 10_800_000

    option_history = [_candle(3_600_000), _candle(7_200_000), _candle(10_800_000)]
    trimmed = _trim_to_anchor(option_history, 7_200_000)
    assert [bar.timestamp_ms for bar in trimmed] == [3_600_000, 7_200_000]


def test_empty_followup_scan_does_not_erase_recent_confluence_event():
    ts = 1_700_000_000_000
    merged = merge_retained_confluence([], [_row(ts)], now_ms=ts + 3_600_000)
    assert len(merged) == 1
    assert merged[0].timestamp_ms == ts
    assert merged[0].source == "confluence"
    assert not merged[0].is_active
    assert not merged[0].is_fresh
    assert all(not leg.is_active for leg in merged[0].legs)


def test_new_confluence_event_replaces_older_same_underlying_event():
    old_ts = 1_700_000_000_000
    new_ts = old_ts + 3_600_000
    current = _row(new_ts)
    merged = merge_retained_confluence([current], [_row(old_ts)], now_ms=new_ts)
    assert [row.timestamp_ms for row in merged] == [new_ts]


def test_confluence_event_expires_after_board_retention_window():
    ts = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
    sixteen_days_ms = 16 * 24 * 60 * 60 * 1000
    assert merge_retained_confluence([], [_row(ts)], now_ms=ts + sixteen_days_ms) == []


@pytest.mark.asyncio
async def test_cold_cache_scan_rebuilds_active_confluence_without_replaying_order():
    """A cache reset must not require a brand-new arrow on the latest 1H bar.

    The underlying transitions first, the option premium transitions several bars
    later, and both remain aligned through the latest closed bar. A new scanner with
    no cached rows must reconstruct the active confluence setup from broker history,
    while the historical event must not invoke the auto-execution callback again.
    """
    cfg = SterlingKiteEngineConfig()
    underlying = _candles(
        list(np.linspace(300, 150, 60)) + list(np.linspace(150, 600, 80))
    )
    premium = _candles(
        list(np.linspace(260, 140, 82)) + list(np.linspace(140, 520, 58))
    )
    flat = _candles(list(np.linspace(100, 101, 140)))

    nfo = []
    for strike in range(100, 701, 50):
        nfo.extend([
            {
                "name": "ACME",
                "tradingsymbol": f"ACME99DEC{strike}CE",
                "instrument_type": "CE",
                "strike": strike,
                "expiry": "2099-12-31",
                "instrument_token": 7000 + strike,
                "lot_size": 50,
            },
            {
                "name": "ACME",
                "tradingsymbol": f"ACME99DEC{strike}PE",
                "instrument_type": "PE",
                "strike": strike,
                "expiry": "2099-12-31",
                "instrument_token": 8000 + strike,
                "lot_size": 50,
            },
        ])

    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            if inst.zerodha_token == 100:
                return underlying
            if 7000 <= inst.zerodha_token < 8000:
                return premium
            return flat

    placed = []

    async def place_cb(row, item):
        placed.append((row.underlying, row.timestamp_ms))

    scanner = KiteEngineScanner()
    item = UniverseItem("ACME", "ACME", 100, "NSE", "NFO", is_index=False)
    await scanner.scan(
        uid="cold-cache-user",
        client=FakeClient(),
        universe=[],
        nfo_rows=nfo,
        bfo_rows=[],
        cfg=cfg,
        moneyness=["ATM"],
        expiry_types=("monthly",),
        expiry_types_stocks=("monthly",),
        confluence_universe=[item],
        place_cb=place_cb,
    )

    rows = [row for row in scanner.snapshot("cold-cache-user").rows if row.source == "confluence"]
    assert len(rows) == 1
    row = rows[0]
    assert row.is_active is True
    assert row.is_fresh is False
    assert row.timestamp_ms < underlying[-1].timestamp_ms
    assert row.legs and row.legs[0].is_active is True
    assert row.legs[0].premium_spot > 0
    assert row.legs[0].premium_sl > 0
    assert placed == []

    # A startup scan sees the persisted board as a warm cache. It must revalidate
    # the same retained setup instead of treating the cached row as authoritative
    # coverage and converting it to an ended row.
    await scanner.scan(
        uid="cold-cache-user",
        client=FakeClient(),
        universe=[],
        nfo_rows=nfo,
        bfo_rows=[],
        cfg=cfg,
        moneyness=["ATM"],
        expiry_types=("monthly",),
        expiry_types_stocks=("monthly",),
        confluence_universe=[item],
        place_cb=place_cb,
    )

    warm_rows = [
        value
        for value in scanner.snapshot("cold-cache-user").rows
        if value.source == "confluence"
    ]
    assert len(warm_rows) == 1
    assert warm_rows[0].is_active is True
    assert warm_rows[0].is_fresh is False
    assert warm_rows[0].legs and warm_rows[0].legs[0].is_active is True
    assert placed == []
