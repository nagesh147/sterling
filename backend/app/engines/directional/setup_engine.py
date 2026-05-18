import os
from app.schemas.directional import (
    RegimeResult, SignalResult, SetupResult,
    TradeState, MacroRegime, Direction,
)


def _idle_loose_enabled() -> bool:
    """Issue 4 — operator opt-in to allow CONFIRMED entries in IDLE under
    very strict signal_score (>= 18). Off by default; enabled via env.
    """
    return os.environ.get("STERLING_IDLE_STRICTNESS", "").lower() == "loose"


def _early_entry_enabled() -> bool:
    """Issue 5 — operator opt-in to flag EARLY_SETUP_ACTIVE with signal_score
    in [11, 14] for haircut sizing. Off by default; enabled via env."""
    return os.environ.get("STERLING_ENABLE_EARLY_ENTRY") == "1"


def _maybe_flag_early(setup: SetupResult, signal: SignalResult) -> SetupResult:
    """If EARLY_SETUP_ACTIVE and operator opt-in is on, mark early_entry=True
    so the sizing engine applies the 0.5× haircut. Idempotent."""
    if setup.state != TradeState.EARLY_SETUP_ACTIVE:
        return setup
    if not _early_entry_enabled():
        return setup
    sig_score = float(getattr(signal, "signal_score", 0.0) or 0.0)
    if 11.0 <= sig_score <= 14.0:
        return setup.model_copy(update={"early_entry": True})
    return setup

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
_HIGH_SCORE_CONFIRM = 16.0  # 80% of max-20; stricter than trending (15) — ranging has weaker directional edge


def evaluate_setup(regime: RegimeResult, signal: SignalResult) -> SetupResult:
    setup = _evaluate_setup_inner(regime, signal)
    return _maybe_flag_early(setup, signal)


def _evaluate_setup_inner(regime: RegimeResult, signal: SignalResult) -> SetupResult:
    macro = regime.macro_regime
    trend = signal.trend
    green_count = signal.st_trends.count(1)
    red_count   = signal.st_trends.count(-1)

    # Hard veto: choppy / idle market blocks all entries
    if macro in _VETO_REGIMES:
        # Issue 4 — under STERLING_IDLE_STRICTNESS=loose, allow CONFIRMED in IDLE
        # when signal_score is very high (≥ 18/20) AND all 3 STs agree. The
        # sizer is responsible for dropping the position to 0.25× via
        # regime_adaptive_sizer.adapt(is_idle=True).
        sig_score = float(getattr(signal, "signal_score", 0.0) or 0.0)
        if (
            macro == MacroRegime.IDLE
            and _idle_loose_enabled()
            and sig_score >= 18.0
            and (signal.all_green or signal.all_red)
            and trend != 0
        ):
            return SetupResult(
                state=TradeState.CONFIRMED_SETUP_ACTIVE,
                direction=Direction.LONG if trend == 1 else Direction.SHORT,
                reason=(
                    f"IDLE regime (loose mode) — all STs aligned + high score "
                    f"({sig_score:.0f}/20). Sized down 0.25×."
                ),
                macro_regime=macro,
                signal_trend=trend,
            )
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
    # LONG: outer gate requires 2+ green STs; SHORT allows trend==-1 with 1 red (handled via inner FILTERED fallback)
    elif macro in _RANGING_REGIMES and green_count >= _PARTIAL_ST_MIN and trend == 1:
        sig_score = float(signal.signal_score or 0.0)
        if signal.all_green and sig_score >= _HIGH_SCORE_CONFIRM:
            return SetupResult(
                state=TradeState.CONFIRMED_SETUP_ACTIVE,
                direction=Direction.LONG,
                reason=f"Ranging regime — all STs bullish + high score ({sig_score:.0f}/20)",
                macro_regime=macro,
                signal_trend=trend,
            )
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.LONG,
            reason=f"Ranging regime, {green_count}/3 ST bullish — lower confidence.",
            macro_regime=macro,
            signal_trend=trend,
        )
    elif macro in _RANGING_REGIMES and trend == -1:
        sig_score = float(signal.signal_score or 0.0)
        if signal.all_red and sig_score >= _HIGH_SCORE_CONFIRM:
            return SetupResult(
                state=TradeState.CONFIRMED_SETUP_ACTIVE,
                direction=Direction.SHORT,
                reason=f"Ranging regime — all STs bearish + high score ({sig_score:.0f}/20)",
                macro_regime=macro,
                signal_trend=trend,
            )
        if red_count >= _PARTIAL_ST_MIN:
            return SetupResult(
                state=TradeState.EARLY_SETUP_ACTIVE,
                direction=Direction.SHORT,
                reason=f"Ranging regime, {red_count}/3 ST bearish — lower confidence.",
                macro_regime=macro,
                signal_trend=trend,
            )
        return SetupResult(
            state=TradeState.FILTERED,
            direction=Direction.NEUTRAL,
            reason=f"Ranging regime / short — insufficient ST alignment ({red_count}/3)",
            macro_regime=macro,
            signal_trend=trend,
        )

    # ── Volatile — momentum direction when all STs agree ─────────────────────
    elif macro in _VOLATILE_REGIMES and trend == 1:
        sig_score = float(signal.signal_score or 0.0)
        state = (TradeState.CONFIRMED_SETUP_ACTIVE
                 if signal.all_green and sig_score >= _HIGH_SCORE_CONFIRM
                 else TradeState.EARLY_SETUP_ACTIVE)
        reason = (f"Volatile regime — all STs bullish + high score ({sig_score:.0f}/20)"
                  if state == TradeState.CONFIRMED_SETUP_ACTIVE
                  else "Volatile regime, all STs bullish — momentum long.")
        return SetupResult(state=state, direction=Direction.LONG,
                           reason=reason, macro_regime=macro, signal_trend=trend)
    elif macro in _VOLATILE_REGIMES and trend == -1:
        sig_score = float(signal.signal_score or 0.0)
        state = (TradeState.CONFIRMED_SETUP_ACTIVE
                 if signal.all_red and sig_score >= _HIGH_SCORE_CONFIRM
                 else TradeState.EARLY_SETUP_ACTIVE)
        reason = (f"Volatile regime — all STs bearish + high score ({sig_score:.0f}/20)"
                  if state == TradeState.CONFIRMED_SETUP_ACTIVE
                  else "Volatile regime, all STs bearish — momentum short.")
        return SetupResult(state=state, direction=Direction.SHORT,
                           reason=reason, macro_regime=macro, signal_trend=trend)

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
