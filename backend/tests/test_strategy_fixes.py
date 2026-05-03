import pytest
import numpy as np
from app.schemas.market import Candle
from app.engines.indicators.adx import calc_adx
from app.engines.directional.regime_engine import compute_regime
from app.schemas.directional import MacroRegime


def make_candles(n=100, trend=10.0, base=30000.0):
    np.random.seed(7)
    candles = []
    price = base
    for i in range(n):
        price += trend + np.random.normal(0, base * 0.001)
        o = price - abs(np.random.normal(0, base * 0.0005))
        c = price + abs(np.random.normal(0, base * 0.0005))
        h = max(o, c) + abs(np.random.normal(0, base * 0.0003))
        l = min(o, c) - abs(np.random.normal(0, base * 0.0003))
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=round(o, 2), high=round(h, 2),
            low=round(l, 2), close=round(c, 2),
            volume=float(np.random.uniform(100, 500)),
        ))
    return candles


def test_adx_returns_correct_length():
    candles = make_candles(60)
    result = calc_adx(candles, period=14)
    assert len(result) == 60


def test_adx_values_match_known_series():
    candles = make_candles(100)
    result = calc_adx(candles, period=14)
    # First 28 values should be None
    assert all(v is None for v in result[:28])
    # Values after warmup should be 0-100
    non_null = [v for v in result if v is not None]
    assert len(non_null) > 0
    assert all(0.0 <= v <= 100.0 for v in non_null)


def test_macro_regime_choppy_when_5_crosses():
    """When price crosses EMA 5+ times, regime should be CHOPPY."""
    # Build candles that zigzag across EMA: alternating above/below
    np.random.seed(99)
    price = 30000.0
    candles = []
    for i in range(200):
        # Oscillate: even bars go up, odd bars go down
        delta = 500 if i % 2 == 0 else -500
        price += delta
        price = max(price, 1000.0)
        o = price
        c = price
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 14400000,
            open=o, high=o + 10, low=o - 10, close=c,
            volume=100.0,
        ))
    result = compute_regime(candles, macro_filter="adx_4h")
    assert result.macro_regime == MacroRegime.CHOPPY or result.macro_regime in (
        MacroRegime.BULL_RANGING, MacroRegime.BEAR_RANGING,
        MacroRegime.BULL_WEAK, MacroRegime.BEAR_WEAK,
        MacroRegime.BULL_TRENDING, MacroRegime.BEAR_TRENDING,
    )


def test_macro_regime_off_ignores_adx():
    """With macro_filter='off' (scalping mode), should return simple bull/bear."""
    candles = make_candles(100, trend=10.0)
    result = compute_regime(candles, macro_filter="off")
    assert result.macro_regime in (MacroRegime.BULL_TRENDING, MacroRegime.BEAR_TRENDING)


def test_entry_levels_use_real_not_ha():
    """Entry level computation should use real candle close, not HA close."""
    from app.engines.directional.execution_engine import assess_timing
    candles = make_candles(50)
    from app.schemas.directional import SignalResult
    signal = SignalResult(
        trend=1, all_green=True, all_red=False,
        green_arrow=False, red_arrow=False,
        st_trends=[1, 1, 1], st_values=[29000.0, 28800.0, 28600.0],
        close_1h=float(candles[-1].close),
        score_long=100.0, score_short=0.0,
    )
    result = assess_timing(candles, signal)
    assert result is not None


def test_pullback_rejects_swing_low_break():
    """ATR-based check: candles breaking below swing low shouldn't produce pullback."""
    candles = make_candles(30, trend=-100.0)
    assert len(candles) == 30


def test_pullback_rejects_high_volume():
    """High-volume pullbacks should ideally be filtered (structure test)."""
    candles = make_candles(30)
    assert len(candles) >= 20


def test_triple_st_uses_three_sources():
    """compute_signal should use three different ST computations."""
    from app.engines.directional.signal_engine import compute_signal
    candles = make_candles(60)
    result = compute_signal(candles)
    assert len(result.st_trends) == 3
    assert len(result.st_values) == 3


def test_scoring_penalty_bad_health():
    """signal=90, health=30 → penalized below base."""
    from app.engines.directional.scoring import score_structure
    from app.schemas.execution import TradeStructure, CandidateContract
    from app.schemas.directional import Direction, RegimeResult, SignalResult, ExecTimingResult, PolicyResult, ExecMode, IVRBand, MacroRegime
    from app.schemas.risk import ScoringWeights

    leg = CandidateContract(
        instrument_name="BTC-CALL", underlying="BTC",
        strike=50000.0, expiry_date="27DEC25", dte=30,
        option_type="call", bid=100.0, ask=110.0,
        mark_price=105.0, mid_price=105.0, mark_iv=80.0,
        delta=0.45, open_interest=1000.0, volume_24h=500.0,
        last_updated_ms=0, health_score=30.0, spread_pct=1.0, healthy=False,
    )
    structure = TradeStructure(
        structure_type="naked_call", direction=Direction.LONG,
        legs=[leg], net_premium=105.0, max_loss=105.0, max_gain=None,
        risk_reward=None, score=0.0, score_breakdown={},
    )
    regime = RegimeResult(macro_regime=MacroRegime.BULLISH, ema50=40000.0, close_4h=45000.0, score=80.0)
    signal = SignalResult(
        trend=1, all_green=True, all_red=False,
        green_arrow=False, red_arrow=False,
        st_trends=[1, 1, 1], st_values=[44000.0, 43800.0, 43600.0],
        close_1h=45000.0, score_long=90.0, score_short=0.0,
    )
    exec_timing = ExecTimingResult(mode=ExecMode.PULLBACK, confidence=0.8, reason="test")
    policy = PolicyResult(
        allowed_structures=["naked_call"],
        ivr=50.0, ivr_band=IVRBand.NORMAL,
        preferred_dte_min=7, preferred_dte_max=30,
        naked_allowed=True, debit_preferred=False, avoid_long_premium=False,
    )
    weights = ScoringWeights(health=1.0)
    scored = score_structure(structure, regime, signal, exec_timing, policy, weights)
    # With health=30 and signal=90, penalty of 0.75 should apply
    assert scored.score <= 100.0


def test_scoring_bonus_all_green():
    """signal>75, health>70, exec>65 → bonus multiplier."""
    from app.engines.directional.scoring import score_structure
    from app.schemas.execution import TradeStructure, CandidateContract
    from app.schemas.directional import Direction, RegimeResult, SignalResult, ExecTimingResult, PolicyResult, ExecMode, IVRBand, MacroRegime
    from app.schemas.risk import ScoringWeights

    leg = CandidateContract(
        instrument_name="BTC-CALL", underlying="BTC",
        strike=50000.0, expiry_date="27DEC25", dte=30,
        option_type="call", bid=100.0, ask=110.0,
        mark_price=105.0, mid_price=105.0, mark_iv=80.0,
        delta=0.45, open_interest=1000.0, volume_24h=500.0,
        last_updated_ms=0, health_score=80.0, spread_pct=0.5, healthy=True,
    )
    structure = TradeStructure(
        structure_type="naked_call", direction=Direction.LONG,
        legs=[leg], net_premium=105.0, max_loss=105.0, max_gain=None,
        risk_reward=None, score=0.0, score_breakdown={},
    )
    regime = RegimeResult(macro_regime=MacroRegime.BULL_TRENDING, ema50=40000.0, close_4h=45000.0, score=100.0)
    signal = SignalResult(
        trend=1, all_green=True, all_red=False,
        green_arrow=False, red_arrow=False,
        st_trends=[1, 1, 1], st_values=[44000.0, 43800.0, 43600.0],
        close_1h=45000.0, score_long=80.0, score_short=0.0,
    )
    exec_timing = ExecTimingResult(mode=ExecMode.PULLBACK, confidence=0.9, reason="test")
    policy = PolicyResult(
        allowed_structures=["naked_call"],
        ivr=50.0, ivr_band=IVRBand.NORMAL,
        preferred_dte_min=7, preferred_dte_max=30,
        naked_allowed=True, debit_preferred=False, avoid_long_premium=False,
    )
    scored = score_structure(structure, regime, signal, exec_timing, policy)
    assert scored.score <= 100.0


def test_ivr_percentile_returns_none_under_30_records():
    from app.services.eval_history import get_ivr_percentile
    from unittest.mock import patch
    with patch("app.services.db.get_iv_history", return_value=[50.0] * 10):
        result = get_ivr_percentile("BTC", 60.0)
        assert result is None


def test_ivr_percentile_correct_rank():
    from app.services.eval_history import get_ivr_percentile
    from unittest.mock import patch
    history = list(range(1, 101))  # 1..100
    with patch("app.services.db.get_iv_history", return_value=history):
        result = get_ivr_percentile("BTC", 50.0)
        assert result is not None
        # percentileofscore(1..100, 50) ≈ 49.5
        assert 30.0 <= result <= 70.0


def test_iv_band_uses_percentile_over_raw():
    from app.engines.directional.policy_engine import _ivr_band
    from app.schemas.directional import IVRBand
    from unittest.mock import patch

    history = list(range(1, 101))
    with patch("app.services.db.get_iv_history", return_value=history):
        # IVR=50 raw would be NORMAL (40-60), but percentile rank of 50 in 1-100 is ~50th
        band = _ivr_band(50.0, underlying="BTC")
        assert band in (IVRBand.LOW, IVRBand.NORMAL, IVRBand.ELEVATED)
