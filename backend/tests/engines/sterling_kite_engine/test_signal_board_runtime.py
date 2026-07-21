"""Regression coverage for signal-board continuity and confluence bar alignment."""
from datetime import datetime, timezone

from app.domain.models import Candle
from app.engines.sterling_kite_engine.schemas import (
    AlignmentChip,
    EngineSignalRow,
    OptionLeg,
)
from app.services.kite_engine.signal_board_runtime import (
    _option_anchor,
    _trim_to_anchor,
    merge_retained_confluence,
)


def _candle(ts: int) -> Candle:
    return Candle(
        timestamp_ms=ts,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1.0,
    )


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
