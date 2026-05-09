from app.schemas.directional import (
    RegimeResult, SignalResult, SetupResult,
    TradeState, MacroRegime, Direction,
)

# v1 + v2 bullish regimes — BULL_TREND was added in v2 but not included here (bug fix)
_BULLISH_REGIMES = {
    MacroRegime.BULLISH,
    MacroRegime.BULL_TRENDING,
    MacroRegime.BULL_WEAK,
    MacroRegime.BULL_RANGING,
    MacroRegime.BULL_TREND,      # v2 regime engine output
}

_BEARISH_REGIMES = {
    MacroRegime.BEARISH,
    MacroRegime.BEAR_TRENDING,
    MacroRegime.BEAR_WEAK,
    MacroRegime.BEAR_RANGING,
    MacroRegime.BEAR_TREND,      # v2 regime engine output
}

# Ranging/neutral: allow signals when STs have 2/3 agreement (lower confidence)
_RANGING_REGIMES = {MacroRegime.RANGING, MacroRegime.NEUTRAL}

# Volatile: allow signals in direction of ST majority — volatility favours momentum
_VOLATILE_REGIMES = {MacroRegime.VOLATILE}

_VETO_REGIMES = {MacroRegime.CHOPPY, MacroRegime.IDLE}

_PARTIAL_ST_MIN = 2


def evaluate_setup(regime: RegimeResult, signal: SignalResult) -> SetupResult:
    macro = regime.macro_regime
    trend = signal.trend
    green_count = signal.st_trends.count(1)
    red_count   = signal.st_trends.count(-1)

    # Hard veto: choppy / idle market blocks all entries
    if macro in _VETO_REGIMES:
        return SetupResult(
            state=TradeState.FILTERED,
            direction=Direction.NEUTRAL,
            reason=f"{macro.value} regime — hard veto",
            macro_regime=macro,
            signal_trend=trend,
        )

    # ── Full alignment — trending regime + all STs agree ─────────────────────
    if macro in _BULLISH_REGIMES and trend == 1:
        direction = Direction.LONG
    elif macro in _BEARISH_REGIMES and trend == -1:
        direction = Direction.SHORT

    # ── Partial alignment — trending regime, 2/3 STs agree ───────────────────
    elif macro in _BULLISH_REGIMES and green_count >= _PARTIAL_ST_MIN:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.LONG,
            reason=(
                f"Partial bull — {green_count}/3 ST aligned, "
                f"{macro.value} regime. Awaiting full alignment."
            ),
            macro_regime=macro,
            signal_trend=trend,
        )
    elif macro in _BEARISH_REGIMES and red_count >= _PARTIAL_ST_MIN:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.SHORT,
            reason=(
                f"Partial bear — {red_count}/3 ST aligned, "
                f"{macro.value} regime. Awaiting full alignment."
            ),
            macro_regime=macro,
            signal_trend=trend,
        )

    # ── Ranging — allow when 2/3 STs strongly aligned ────────────────────────
    elif macro in _RANGING_REGIMES and green_count >= _PARTIAL_ST_MIN and trend == 1:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.LONG,
            reason=f"Ranging regime, {green_count}/3 ST bullish — lower confidence.",
            macro_regime=macro,
            signal_trend=trend,
        )
    elif macro in _RANGING_REGIMES and red_count >= _PARTIAL_ST_MIN and trend == -1:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.SHORT,
            reason=f"Ranging regime, {red_count}/3 ST bearish — lower confidence.",
            macro_regime=macro,
            signal_trend=trend,
        )

    # ── Volatile — momentum direction when all STs agree ─────────────────────
    elif macro in _VOLATILE_REGIMES and trend == 1:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.LONG,
            reason="Volatile regime, all STs bullish — momentum long.",
            macro_regime=macro,
            signal_trend=trend,
        )
    elif macro in _VOLATILE_REGIMES and trend == -1:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.SHORT,
            reason="Volatile regime, all STs bearish — momentum short.",
            macro_regime=macro,
            signal_trend=trend,
        )

    # ── No alignment ─────────────────────────────────────────────────────────
    else:
        return SetupResult(
            state=TradeState.FILTERED,
            direction=Direction.NEUTRAL,
            reason=f"Macro {macro.value} / signal trend {trend}: misaligned",
            macro_regime=macro,
            signal_trend=trend,
        )

    # ── Full alignment: check for arrow confirmation ──────────────────────────
    has_arrow = signal.green_arrow if direction == Direction.LONG else signal.red_arrow

    # Strong confluence can confirm even without a fresh arrow:
    # all STs aligned + signal_score >= 15/20 avoids waiting for a flip
    # that may never arrive in strong continuation moves.
    strong_confluence = getattr(signal, 'signal_score', 0) >= 15.0

    if signal.all_green or signal.all_red:
        if has_arrow or strong_confluence:
            state  = TradeState.CONFIRMED_SETUP_ACTIVE
            reason = ("Arrow + alignment" if has_arrow else
                      f"Strong confluence ({signal.signal_score:.0f}/20) — no arrow needed")
        else:
            state  = TradeState.EARLY_SETUP_ACTIVE
            reason = "All ST aligned, awaiting arrow or confluence build-up"
    else:
        state     = TradeState.IDLE
        reason    = "Mixed ST — monitoring"
        direction = Direction.NEUTRAL

    return SetupResult(
        state=state,
        direction=direction,
        reason=reason,
        macro_regime=macro,
        signal_trend=trend,
    )
