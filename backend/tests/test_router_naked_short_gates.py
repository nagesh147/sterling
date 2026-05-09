import pytest
from app.engines.directional.structure_selector import route_by_ivr


def test_naked_short_blocked_if_oi_less_than_200():
    """OI < 200 → no naked short, falls back to credit_spread or no_trade."""
    result = route_by_ivr(ivr=80.0, score=95.0, signal_strength="STRONG", oi=150.0, spread_pct=0.02)
    assert result != "naked_short"


def test_naked_short_blocked_if_spread_above_3pct():
    """spread > 3% → no naked short."""
    result = route_by_ivr(ivr=80.0, score=95.0, signal_strength="STRONG", oi=250.0, spread_pct=0.04)
    assert result != "naked_short"


def test_naked_short_blocked_if_score_below_90():
    """score < 90 → no naked short."""
    result = route_by_ivr(ivr=80.0, score=88.0, signal_strength="STRONG", oi=250.0, spread_pct=0.02)
    assert result != "naked_short"


def test_naked_short_allowed_when_all_gates_pass():
    """OI > 200, spread < 3%, score >= 90, IVR > 70 → naked_short."""
    result = route_by_ivr(ivr=80.0, score=92.0, signal_strength="STRONG", oi=250.0, spread_pct=0.02)
    assert result == "naked_short"


def test_low_oi_falls_back_to_futures():
    """OI < 100 in high IVR zone → futures fallback."""
    result = route_by_ivr(ivr=80.0, score=90.0, signal_strength="STRONG", oi=50.0, spread_pct=0.02)
    assert result == "futures"


def test_undefined_ivr_gives_futures():
    """IVR undefined → futures path."""
    result = route_by_ivr(ivr=None, score=95.0, signal_strength="STRONG", oi=500.0, spread_pct=0.01)
    assert result == "futures"
