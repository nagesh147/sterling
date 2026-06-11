"""Directional setup/arming state machine.

The 4h regime sets DIRECTION (the validated trend-following edge); the 1h signal
sets entry TIMING — it does NOT cast a redundant independent trend vote. So a
confirmed 4h trend arms in its direction unless the 1h actively contradicts it:

  4h BULL_TREND + 1h trend ∈ {long, neutral}  → ARM long
                  1h trend == short            → WATCHING (bias long, 1h opposes)
  4h BEAR_TREND + 1h trend ∈ {short, neutral} → ARM short
                  1h trend == long             → WATCHING (bias short, 1h opposes)
  no 4h trend (RANGING/IDLE/…)                 → IDLE

This fixes the empty-tables root cause: the prior gate required the 1h to
independently re-confirm the trend, which a real (honest) 1h signal rarely does
inside a 4h trend — so nothing ever armed (the old fabricated stub masked this by
always emitting a fake directional trend). The WATCHING tier surfaces the 4h
directional bias even when not armed, so the feed shows the read, not a blank.
"""
from __future__ import annotations

from app.schemas.directional import (
    RegimeResult,
    SignalResult,
    SetupResult,
    TradeState,
    Direction,
    MacroRegime,
)

_TREND_DIR = {MacroRegime.BULL_TREND: 1, MacroRegime.BEAR_TREND: -1}
_MR_OVERSOLD = 35.0      # RSI ≤ this in a range → mean-reversion long (buy the dip)
_MR_OVERBOUGHT = 65.0    # RSI ≥ this in a range → mean-reversion short (fade the rip)


def evaluate_setup(
    regime: RegimeResult, signal: SignalResult, profile_label: str | None = None
) -> SetupResult:
    """Arm in the 4h trend direction with 1h timing; WATCHING when 1h opposes."""
    if not regime or not signal:
        return SetupResult(
            state=TradeState.IDLE, direction=Direction.NEUTRAL,
            reason="missing regime or signal", macro_regime=MacroRegime.IDLE,
            signal_trend=0,
        )

    trend_dir = _TREND_DIR.get(regime.macro_regime, 0)
    if trend_dir == 0:
        # No 4h trend. In a RANGING regime, fade RSI extremes — the validated
        # conviction book's mean-reversion sleeve (oversold → long, overbought →
        # short). Other no-trend regimes (IDLE/insufficient data) stay IDLE.
        if regime.macro_regime == MacroRegime.RANGING:
            rsi = float(getattr(signal, "rsi", 50.0) or 50.0)
            if rsi <= _MR_OVERSOLD:
                return SetupResult(
                    state=TradeState.ENTRY_ARMED_PULLBACK, direction=Direction.LONG,
                    reason=f"range — RSI {rsi:.0f} oversold, mean-reversion long",
                    macro_regime=regime.macro_regime, signal_trend=signal.trend,
                )
            if rsi >= _MR_OVERBOUGHT:
                return SetupResult(
                    state=TradeState.ENTRY_ARMED_PULLBACK, direction=Direction.SHORT,
                    reason=f"range — RSI {rsi:.0f} overbought, mean-reversion short",
                    macro_regime=regime.macro_regime, signal_trend=signal.trend,
                )
        return SetupResult(
            state=TradeState.IDLE, direction=Direction.NEUTRAL,
            reason="no setup (range/idle, RSI neutral)", macro_regime=regime.macro_regime,
            signal_trend=signal.trend,
        )

    direction = Direction.LONG if trend_dir == 1 else Direction.SHORT
    bias = "bullish" if trend_dir == 1 else "bearish"

    if signal.trend == -trend_dir:
        # 1h actively fights the 4h trend → show the bias, don't arm.
        state, reason = TradeState.WATCHING, f"4h {bias} but 1h opposes — watching for re-alignment"
    elif signal.trend == trend_dir:
        state, reason = TradeState.ENTRY_ARMED_CONTINUATION, f"4h {bias} + 1h confirms — continuation"
    else:  # signal.trend == 0 → 1h neutral / pullback within the trend
        state, reason = TradeState.ENTRY_ARMED_PULLBACK, f"4h {bias}, 1h pullback — armed for entry"

    return SetupResult(
        state=state, direction=direction, reason=reason,
        macro_regime=regime.macro_regime, signal_trend=signal.trend,
    )

