"""Unit tests for Bear to Bearish strategy engine."""
import pytest
from app.engines.bear_to_bearish.models import BearToBearishConfig, PcrPoint
from app.engines.bear_to_bearish.strategy import evaluate_bear_to_bearish, evaluate_pcr_trend, detect_lower_highs


def test_detect_lower_highs():
    candles = [
        {"open": 100, "high": 110, "low": 95, "close": 105},
        {"open": 105, "high": 120, "low": 100, "close": 108},  # peak 120
        {"open": 108, "high": 102, "low": 90, "close": 95},
        {"open": 95, "high": 112, "low": 92, "close": 100},   # peak 112 (< 120)
        {"open": 100, "high": 98, "low": 85, "close": 90},
    ]
    has_lh, latest, prev = detect_lower_highs(candles)
    assert has_lh is True
    assert latest < prev


def test_evaluate_pcr_trend_bearish():
    pts = [
        PcrPoint(timestamp_ms=1000, pcr=0.80),
        PcrPoint(timestamp_ms=2000, pcr=0.72),
        PcrPoint(timestamp_ms=3000, pcr=0.64),
        PcrPoint(timestamp_ms=4000, pcr=0.56),
    ]
    is_bearish, is_invalidated, pcr_open, pcr_current, pcr_change_5m, reason = evaluate_pcr_trend(pts, pcr_threshold=0.60)
    assert is_bearish is True
    assert is_invalidated is False
    assert pcr_current == 0.56
    assert pcr_open == 0.80


def test_evaluate_pcr_trend_invalidation():
    # PCR jumps +0.25 (0.50 -> 0.75) within short window
    pts = [
        PcrPoint(timestamp_ms=1000, pcr=0.50),
        PcrPoint(timestamp_ms=2000, pcr=0.75),
    ]
    is_bearish, is_invalidated, pcr_open, pcr_current, diff, reason = evaluate_pcr_trend(pts, reversal_jump=0.20)
    assert is_invalidated is True
    assert "Invalidated" in reason


def test_evaluate_bear_to_bearish_armed():
    cfg = BearToBearishConfig(pcr_threshold=0.60, auto_execute=True)
    candles = [
        {"open": 24000, "high": 24100, "low": 23950, "close": 24050},
        {"open": 24050, "high": 24200, "low": 24000, "close": 24100},
        {"open": 24100, "high": 24080, "low": 23900, "close": 23950},
        {"open": 23950, "high": 24120, "low": 23900, "close": 24000},
        {"open": 24000, "high": 23980, "low": 23850, "close": 23880},
    ]
    pts = [
        PcrPoint(timestamp_ms=1000, pcr=0.80),
        PcrPoint(timestamp_ms=2000, pcr=0.58),
    ]
    sig = evaluate_bear_to_bearish("NIFTY", candles, pts, cfg, current_spot=24350.0, now_ms=123456789)
    assert sig.status == "armed"
    assert sig.direction == "short"
    assert sig.option_type == "PE"
    assert sig.strike == 24350.0
    assert sig.spot_price == 24350.0
    assert sig.option_premium > 0 and sig.option_premium < 1000.0
    assert sig.entry_price == sig.option_premium
    assert sig.stop_loss < sig.entry_price
    assert sig.target_price > sig.entry_price
    assert sig.lot_size == 25

def test_atm_strike_steps():
    cfg = BearToBearishConfig()
    pts = [PcrPoint(timestamp_ms=1000, pcr=0.55)]

    # BANKNIFTY 100 step
    bank = evaluate_bear_to_bearish("BANKNIFTY", [], pts, cfg, current_spot=52140.0)
    assert bank.strike == 52100.0
    assert bank.lot_size == 15

    # SENSEX 100 step
    sensex = evaluate_bear_to_bearish("SENSEX", [], pts, cfg, current_spot=80160.0)
    assert sensex.strike == 80200.0
    assert sensex.lot_size == 10


@pytest.mark.asyncio
async def test_bear_to_bearish_market_closed(monkeypatch):
    from app.engines.bear_to_bearish.service import run_scan, get_snapshot

    # Simulate market closed
    monkeypatch.setattr("app.engines.bear_to_bearish.service.is_market_open", lambda: False)

    snap = await run_scan()
    assert snap.market_open is False
    assert snap.scanning_label == "Market closed"
    assert len(snap.rows) == 0

    current = get_snapshot()
    assert current.market_open is False
    assert len(current.rows) == 0


