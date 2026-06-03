"""STRATEGY STUB — setup/state-machine evaluation removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. `evaluate_setup` returns a
neutral IDLE setup so the app keeps running with empty states.

Implement the new setup logic here.
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


def evaluate_setup(
    regime: RegimeResult, signal: SignalResult, profile_label: str | None = None
) -> SetupResult:
    """Evaluates setup based on regime and signal alignment."""
    if not regime or not signal:
        return SetupResult(
            state=TradeState.IDLE,
            direction=Direction.NEUTRAL,
            reason="missing regime or signal",
            macro_regime=MacroRegime.IDLE,
            signal_trend=0,
        )

    state = TradeState.IDLE
    direction = Direction.NEUTRAL
    reason = "no alignment"

    if regime.macro_regime == MacroRegime.BULL_TREND and signal.trend == 1:
        state = TradeState.ENTRY_ARMED_PULLBACK
        direction = Direction.LONG
        reason = "bullish alignment"
    elif regime.macro_regime == MacroRegime.BEAR_TREND and signal.trend == -1:
        state = TradeState.ENTRY_ARMED_CONTINUATION
        direction = Direction.SHORT
        reason = "bearish alignment"

    return SetupResult(
        state=state,
        direction=direction,
        reason=reason,
        macro_regime=regime.macro_regime,
        signal_trend=signal.trend,
    )

