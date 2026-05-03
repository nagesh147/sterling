import pytest
from tests.conftest import make_candles, make_bearish_candles
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.setup_engine import evaluate_setup
from app.engines.directional.policy_engine import apply_policy
from app.schemas.directional import (
    MacroRegime, TradeState, Direction, IVRBand,
)
from app.schemas.instruments import InstrumentMeta


_INST = InstrumentMeta(
    underlying="BTC",
    tick_size=0.5,
    strike_step=1000.0,
    exchange="deribit",
    exchange_currency="BTC",
    perp_symbol="BTC-PERPETUAL",
    index_name="btc_usd",
    dvol_symbol="BTC-DVOL",
)


class TestRegimeEngine:
    def test_bullish_regime(self):
        candles = make_candles(100, base=30000.0, trend=100.0)
        regime = compute_regime(candles)
        assert regime.macro_regime in (
            MacroRegime.BULLISH, MacroRegime.BULL_TRENDING,
            MacroRegime.BULL_WEAK, MacroRegime.BULL_RANGING,
        )
        assert regime.close_4h > regime.ema50

    def test_bearish_regime(self):
        candles = make_bearish_candles(100, base=50000.0)
        regime = compute_regime(candles)
        assert regime.macro_regime in (
            MacroRegime.BEARISH, MacroRegime.BEAR_TRENDING,
            MacroRegime.BEAR_WEAK, MacroRegime.BEAR_RANGING, MacroRegime.CHOPPY,
        )

    def test_insufficient_data_returns_neutral(self):
        regime = compute_regime([])
        assert regime.macro_regime == MacroRegime.NEUTRAL

    def test_score_range(self):
        candles = make_candles(100)
        regime = compute_regime(candles)
        assert 0.0 <= regime.score <= 100.0


class TestSignalEngine:
    def test_output_fields(self):
        candles = make_candles(200)
        signal = compute_signal(candles)
        assert isinstance(signal.all_green, bool)
        assert isinstance(signal.all_red, bool)
        assert isinstance(signal.green_arrow, bool)
        assert signal.trend in (-1, 0, 1)
        assert len(signal.st_trends) == 3

    def test_score_range(self):
        candles = make_candles(200)
        signal = compute_signal(candles)
        assert 0.0 <= signal.score_long <= 100.0
        assert 0.0 <= signal.score_short <= 100.0

    def test_all_green_and_all_red_mutually_exclusive(self):
        candles = make_candles(200)
        signal = compute_signal(candles)
        assert not (signal.all_green and signal.all_red)

    def test_short_candles_returns_neutral(self):
        candles = make_candles(10)
        signal = compute_signal(candles)
        assert signal.trend == 0


class TestSetupEngine:
    def test_bullish_aligned_produces_setup(self):
        from app.schemas.directional import RegimeResult, SignalResult
        regime = RegimeResult(
            macro_regime=MacroRegime.BULLISH, ema50=29000.0, close_4h=31000.0, score=70.0
        )
        signal = SignalResult(
            trend=1, all_green=True, all_red=False,
            green_arrow=True, red_arrow=False,
            st_trends=[1, 1, 1], st_values=[0.0, 0.0, 0.0],
            close_1h=31000.0, score_long=100.0, score_short=0.0,
        )
        setup = evaluate_setup(regime, signal)
        assert setup.direction == Direction.LONG
        assert setup.state == TradeState.CONFIRMED_SETUP_ACTIVE

    def test_misaligned_produces_filtered(self):
        from app.schemas.directional import RegimeResult, SignalResult
        regime = RegimeResult(
            macro_regime=MacroRegime.BEARISH, ema50=32000.0, close_4h=30000.0, score=30.0
        )
        signal = SignalResult(
            trend=1, all_green=True, all_red=False,
            green_arrow=True, red_arrow=False,
            st_trends=[1, 1, 1], st_values=[0.0, 0.0, 0.0],
            close_1h=30000.0, score_long=100.0, score_short=0.0,
        )
        setup = evaluate_setup(regime, signal)
        assert setup.state == TradeState.FILTERED
        assert setup.direction == Direction.NEUTRAL


class TestPolicyEngine:
    def test_low_ivr_allows_naked(self):
        policy = apply_policy(Direction.LONG, _INST, ivr=30.0)
        assert policy.naked_allowed
        assert "naked_call" in policy.allowed_structures

    def test_high_ivr_avoids_long_premium(self):
        policy = apply_policy(Direction.LONG, _INST, ivr=85.0)
        assert policy.avoid_long_premium
        assert policy.ivr_band == IVRBand.HIGH

    def test_elevated_ivr_prefers_debit(self):
        policy = apply_policy(Direction.SHORT, _INST, ivr=65.0)
        assert policy.debit_preferred

    def test_none_ivr_defaults_elevated(self):
        """Unknown IV is treated as ELEVATED (fail-closed) so naked options are excluded."""
        policy = apply_policy(Direction.LONG, _INST, ivr=None)
        assert policy.ivr_band == IVRBand.ELEVATED
        assert not policy.naked_allowed   # fail-closed: don't allow naked when IV unknown
        assert policy.debit_preferred     # prefer defined-risk spreads
