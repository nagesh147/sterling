from datetime import datetime, timezone

from app.engines.nifty_orb_options import Bar, StrategyConfig, Signal
from app.services.nifty_orb_scanner import configured_underlyings


def test_configured_underlyings_canonicalizes_index_labels():
    cfg = StrategyConfig(
        scan_indices=("NIFTY 50", "NIFTY BANK"),
        scan_stocks=("RELIANCE", "SBIN"),
        scan_stock_contracts=True,
    )
    assert configured_underlyings(cfg) == ["NIFTY", "BANKNIFTY", "RELIANCE", "SBIN"]


def test_configured_underlyings_drops_stocks_when_stock_contracts_disabled():
    cfg = StrategyConfig(
        scan_indices=("NIFTY 50",),
        scan_stocks=("RELIANCE",),
        scan_stock_contracts=False,
    )
    assert configured_underlyings(cfg) == ["NIFTY"]


def test_signal_schema_keeps_directional_option_mapping():
    signal = Signal(
        direction="LONG",
        regime="TREND",
        timestamp=datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc),
        or_high=100,
        or_low=90,
        vwap=101,
        atr=2,
        breakout_distance=1,
        volume_ratio=1.5,
        confidence=0.8,
        reason="test",
    )
    assert signal.direction == "LONG"
