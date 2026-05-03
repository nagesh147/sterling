from app.schemas.directional import (
    RegimeResult, SignalResult, SetupResult,
    TradeState, MacroRegime, Direction,
)

_BULLISH_REGIMES = {
    MacroRegime.BULLISH,
    MacroRegime.BULL_TRENDING,
    MacroRegime.BULL_WEAK,
    MacroRegime.BULL_RANGING,
}

_BEARISH_REGIMES = {
    MacroRegime.BEARISH,
    MacroRegime.BEAR_TRENDING,
    MacroRegime.BEAR_WEAK,
    MacroRegime.BEAR_RANGING,
}

_VETO_REGIMES = {MacroRegime.CHOPPY}

# Minimum STs that must agree with the regime direction to allow partial alignment.
# Full threshold (3/3) is required for arrows/confirmed state; partial (2/3) allows
# the pipeline to run so candidates are generated with appropriately lower scores.
_PARTIAL_ST_MIN = 2


def evaluate_setup(regime: RegimeResult, signal: SignalResult) -> SetupResult:
    macro = regime.macro_regime
    trend = signal.trend
    green_count = signal.st_trends.count(1)
    red_count   = signal.st_trends.count(-1)

    # Hard veto: choppy market blocks all entries regardless of signal
    if macro in _VETO_REGIMES:
        return SetupResult(
            state=TradeState.FILTERED,
            direction=Direction.NEUTRAL,
            reason="Choppy regime — hard veto",
            macro_regime=macro,
            signal_trend=trend,
        )

    # ── Full alignment (all STs meet threshold) ──────────────────────────────
    if macro in _BULLISH_REGIMES and trend == 1:
        direction = Direction.LONG
    elif macro in _BEARISH_REGIMES and trend == -1:
        direction = Direction.SHORT

    # ── Partial alignment (2/3 STs + strong regime) ──────────────────────────
    # Regime is clearly directional but the signal hasn't hit the full threshold.
    # Return EARLY_SETUP_ACTIVE so the pipeline proceeds and scores structures —
    # the scoring engine penalises lower score_long automatically (66 vs 100).
    elif macro in _BULLISH_REGIMES and green_count >= _PARTIAL_ST_MIN:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.LONG,
            reason=(
                f"Partial bull signal — {green_count}/3 ST aligned, "
                f"regime {macro.value} (score={regime.score:.0f}). "
                f"Waiting for full {signal.st_trends.count(1)+1}/3 confirmation."
            ),
            macro_regime=macro,
            signal_trend=trend,
        )
    elif macro in _BEARISH_REGIMES and red_count >= _PARTIAL_ST_MIN:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.SHORT,
            reason=(
                f"Partial bear signal — {red_count}/3 ST aligned, "
                f"regime {macro.value} (score={regime.score:.0f}). "
                f"Waiting for full {signal.st_trends.count(-1)+1}/3 confirmation."
            ),
            macro_regime=macro,
            signal_trend=trend,
        )

    # ── No alignment ─────────────────────────────────────────────────────────
    else:
        return SetupResult(
            state=TradeState.FILTERED,
            direction=Direction.NEUTRAL,
            reason=f"Macro {macro.value} / signal trend {trend}: misaligned or neutral",
            macro_regime=macro,
            signal_trend=trend,
        )

    # ── Full-alignment: check for arrow confirmation ──────────────────────────
    has_arrow = signal.green_arrow if direction == Direction.LONG else signal.red_arrow

    if signal.all_green or signal.all_red:
        if has_arrow:
            state  = TradeState.CONFIRMED_SETUP_ACTIVE
            reason = "Arrow + confirmed directional alignment"
        else:
            state  = TradeState.EARLY_SETUP_ACTIVE
            reason = "All ST aligned, no fresh arrow (continuation in progress)"
    else:
        state     = TradeState.IDLE
        reason    = "Mixed ST — no setup"
        direction = Direction.NEUTRAL

    return SetupResult(
        state=state,
        direction=direction,
        reason=reason,
        macro_regime=macro,
        signal_trend=trend,
    )
