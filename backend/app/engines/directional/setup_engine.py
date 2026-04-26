from app.schemas.directional import (
    RegimeResult, SignalResult, SetupResult,
    TradeState, MacroRegime, Direction,
)


def evaluate_setup(regime: RegimeResult, signal: SignalResult) -> SetupResult:
    """
    State-machine evaluation for one tick (stateless run-once semantics).
    Returns the highest state reached given current regime + signal.
    """
    macro = regime.macro_regime
    trend = signal.trend

    # Macro filter: direction must align with macro regime
    if macro == MacroRegime.BULLISH and trend == 1:
        direction = Direction.LONG
    elif macro == MacroRegime.BEARISH and trend == -1:
        direction = Direction.SHORT
    else:
        # Misaligned or neutral → FILTERED
        return SetupResult(
            state=TradeState.FILTERED,
            direction=Direction.NEUTRAL,
            reason=f"Macro {macro.value} / signal trend {trend}: misaligned or neutral",
            macro_regime=macro,
            signal_trend=trend,
        )

    # Arrow = setup activation
    has_arrow = signal.green_arrow if direction == Direction.LONG else signal.red_arrow

    if signal.all_green or signal.all_red:
        if has_arrow:
            state = TradeState.CONFIRMED_SETUP_ACTIVE
            reason = "Arrow + confirmed directional alignment"
        else:
            state = TradeState.EARLY_SETUP_ACTIVE
            reason = "All ST aligned, no fresh arrow (continuation in progress)"
    else:
        state = TradeState.IDLE
        reason = "Mixed ST — no setup"
        direction = Direction.NEUTRAL

    return SetupResult(
        state=state,
        direction=direction,
        reason=reason,
        macro_regime=macro,
        signal_trend=trend,
    )
