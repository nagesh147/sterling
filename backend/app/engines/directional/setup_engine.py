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
# v4 — Lifted 14 → 15 to compensate for the v4 weight rebase. Pre-v4 a 14
# score required st_flip + RSI + HA + HA-real; post-v4 the same combo still
# scores ~14 but rsi_momentum at the doubled weight (1 → 2) makes hitting 14
# noticeably easier, so the RANGING / VOLATILE confirm gate had to lift to
# keep the same selectivity.
_HIGH_SCORE_CONFIRM = 15.0  # 75% of max-20

# ── W1/W12 promotions ────────────────────────────────────────────────────────
# Mean-reversion in IDLE / RANGING uses RSI extremes + a moderate score gate.
# Volatility breakout in VOLATILE uses a fired squeeze + a strong score gate.
# Numbers come from the v4 spec — engines stay pure; no env reads here.
_MR_RSI_LONG_MAX   = 35.0   # RSI < 35 (tightened from 40) — deeper oversold
_MR_RSI_SHORT_MIN  = 65.0   # RSI > 65 (tightened from 60) — deeper overbought
# v4 — lifted 14 → 15 to match the shifted score distribution under the
# unified weights (see _HIGH_SCORE_CONFIRM note above).
_MR_SCORE_MIN      = 15.0   # 75% of max-20 — kill MR overtrading
_BREAKOUT_SCORE_MIN = 15.0  # same hurdle as _HIGH_SCORE_CONFIRM


def _mean_reversion_setup(
    macro: MacroRegime, signal: SignalResult,
) -> SetupResult | None:
    """
    W1/W12 — promote to CONFIRMED in IDLE/RANGING on an RSI extreme +
    moderate confluence. Pure: only inspects the SignalResult fields.

    Returns a SetupResult when the mean-reversion criteria fire, else None
    so the caller can fall through to its existing branch logic.
    """
    rsi = getattr(signal, "rsi", None)
    if rsi is None:
        return None
    sig_score = float(getattr(signal, "signal_score", 0.0) or 0.0)
    if sig_score < _MR_SCORE_MIN:
        return None
    if float(rsi) < _MR_RSI_LONG_MAX:
        return SetupResult(
            state=TradeState.CONFIRMED_SETUP_ACTIVE,
            direction=Direction.LONG,
            reason=(
                f"{macro.value} regime — mean-reversion long "
                f"(RSI {rsi:.1f} < {_MR_RSI_LONG_MAX:.0f}, "
                f"score {sig_score:.0f}/20 ≥ {_MR_SCORE_MIN:.0f})"
            ),
            macro_regime=macro,
            signal_trend=signal.trend,
        )
    if float(rsi) > _MR_RSI_SHORT_MIN:
        return SetupResult(
            state=TradeState.CONFIRMED_SETUP_ACTIVE,
            direction=Direction.SHORT,
            reason=(
                f"{macro.value} regime — mean-reversion short "
                f"(RSI {rsi:.1f} > {_MR_RSI_SHORT_MIN:.0f}, "
                f"score {sig_score:.0f}/20 ≥ {_MR_SCORE_MIN:.0f})"
            ),
            macro_regime=macro,
            signal_trend=signal.trend,
        )
    return None


def _volatile_breakout_setup(
    macro: MacroRegime, signal: SignalResult,
) -> SetupResult | None:
    """
    W12 — promote to CONFIRMED in VOLATILE when a BB/KC squeeze has fired
    with strong confluence. Direction follows `signal.trend` (no contrarian
    breakouts).
    """
    if not getattr(signal, "squeezed", False):
        return None
    if signal.trend == 0:
        return None
    sig_score = float(getattr(signal, "signal_score", 0.0) or 0.0)
    if sig_score < _BREAKOUT_SCORE_MIN:
        return None
    direction = Direction.LONG if signal.trend == 1 else Direction.SHORT
    return SetupResult(
        state=TradeState.CONFIRMED_SETUP_ACTIVE,
        direction=direction,
        reason=(
            f"{macro.value} regime — squeeze breakout "
            f"({'long' if direction == Direction.LONG else 'short'}, "
            f"score {sig_score:.0f}/20 ≥ {_BREAKOUT_SCORE_MIN:.0f})"
        ),
        macro_regime=macro,
        signal_trend=signal.trend,
    )


_SCALPING_LABEL_TOKENS = ("scalping5m", "scalping15m", "scalping30m")


def evaluate_setup(
    regime: RegimeResult, signal: SignalResult, profile_label: str | None = None
) -> SetupResult:
    if profile_label:
        norm = profile_label.lower().replace(" ", "").replace("_", "")
        is_scalping = any(tok in norm for tok in _SCALPING_LABEL_TOKENS)
        if is_scalping:
            # W6 scalping optimizer + extension to 5m/30m: restrict all
            # scalping profiles to trending macro regimes. Baseline shows
            # short-TF in CHOPPY/IDLE/VOLATILE bleeds cost drag faster than
            # the strategy can earn it back; trend-following on a sub-1H
            # signal only works when the HTF regime is itself trending.
            macro = regime.macro_regime
            is_trend = macro in {
                MacroRegime.BULLISH, MacroRegime.BEARISH,
                MacroRegime.BULL_TRENDING, MacroRegime.BEAR_TRENDING,
                MacroRegime.BULL_TREND, MacroRegime.BEAR_TREND
            }
            if not is_trend:
                return SetupResult(
                    state=TradeState.FILTERED,
                    direction=Direction.NEUTRAL,
                    reason=f"{profile_label} restricted to trending macro regimes only to bypass range chop",
                    macro_regime=macro,
                    signal_trend=signal.trend,
                )
            # Hard MTF gate on the scalping path: signal trend must match the
            # higher-TF regime direction. Bull regime + short signal (or
            # vice-versa) is a counter-trend trade on a noisy TF and is
            # systematically unprofitable in our baselines.
            if macro in {MacroRegime.BULLISH, MacroRegime.BULL_TRENDING, MacroRegime.BULL_TREND} and signal.trend == -1:
                return SetupResult(
                    state=TradeState.FILTERED,
                    direction=Direction.NEUTRAL,
                    reason="scalping MTF gate: bull macro + short signal blocked",
                    macro_regime=macro,
                    signal_trend=signal.trend,
                )
            if macro in {MacroRegime.BEARISH, MacroRegime.BEAR_TRENDING, MacroRegime.BEAR_TREND} and signal.trend == 1:
                return SetupResult(
                    state=TradeState.FILTERED,
                    direction=Direction.NEUTRAL,
                    reason="scalping MTF gate: bear macro + long signal blocked",
                    macro_regime=macro,
                    signal_trend=signal.trend,
                )
    setup = _evaluate_setup_inner(regime, signal)
    return _maybe_flag_early(setup, signal)


def _evaluate_setup_inner(regime: RegimeResult, signal: SignalResult) -> SetupResult:
    macro = regime.macro_regime
    trend = signal.trend
    green_count = signal.st_trends.count(1)
    red_count   = signal.st_trends.count(-1)

    # Hard veto: choppy / idle market blocks all entries by default.
    # IDLE MR override was the single biggest losing regime on intraday_1h
    # (BTC -0.20% across 70 trades, ETH -0.21% across 65 trades) but on the
    # 4H profile IDLE bars actually had +0.46% avg. To preserve 4H winners
    # without leaking into 1H, allow IDLE entries only when signal_score is
    # near-max. v4 weight rebase shifted the score distribution upward (rsi
    # weight doubled from the old vectoriser's value), so the IDLE bypass
    # threshold was lifted 17 → 18 to keep the trade count from doubling.
    if macro in _VETO_REGIMES:
        sig_score = float(getattr(signal, "signal_score", 0.0) or 0.0)
        if (
            macro == MacroRegime.IDLE
            and sig_score >= 18.0
            and trend != 0
            and (signal.all_green or signal.all_red)
        ):
            return SetupResult(
                state=TradeState.CONFIRMED_SETUP_ACTIVE,
                direction=Direction.LONG if trend == 1 else Direction.SHORT,
                reason=(
                    f"IDLE regime, near-max confluence "
                    f"({sig_score:.0f}/20) — strict opt-in."
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

    # ── W1/W12: mean-reversion override for RANGING / NEUTRAL ───────────────
    # Runs before the partial-ST branches so an RSI extreme can trigger an
    # entry even when STs are mixed (the whole point of mean-reverting in
    # range-bound conditions).
    elif macro in _RANGING_REGIMES and (mr := _mean_reversion_setup(macro, signal)):
        return mr

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

    # ── W12: squeeze-breakout promotion for VOLATILE ───────────────────────
    # Fires before the legacy all-aligned branches so a squeeze release with
    # strong confluence confirms even when only 2/3 STs are aligned.
    elif macro in _VOLATILE_REGIMES and (br := _volatile_breakout_setup(macro, signal)):
        return br

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

    # Strong confluence can confirm even without a fresh arrow.
    # v4 — lifted 17 → 18 to match the v4 score-distribution shift (see
    # _HIGH_SCORE_CONFIRM comment). At 17 the chase rule was buying every
    # still-aligned bar 5–8 bars after the flip — the worst R:R region of
    # the move. 18 forces near-max confluence to skip the arrow requirement.
    strong_confluence = getattr(signal, 'signal_score', 0) >= 18.0

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
