"""Per-instrument transformation for the SterlingV2 signal display.

Takes one base directional signal (from research.latest_v2_signal) plus a SINGLE
profile and derives spot / futures / options trade setups that genuinely differ:

  - spot     : unleveraged base case (notional, stop-based risk).
  - futures  : same price plan, leverage capped by BOTH the profile and the
               liquidation buffer; margin + margin-relative risk.
  - options  : call/put, strike (ATM, or OTM on high conviction), an ATR-derived
               premium proxy, defined-risk max loss, breakeven and expiry.

A small picker scores the three and flags the best routing for that signal.

This is PRESENTATION/routing only -- it never sizes a real position or calls the
order router. It is pure (no I/O) so it is unit-tested directly.
"""
from __future__ import annotations

import math

# Max leverage allowed per risk profile (the liquidation buffer can lower it).
PROFILE_LEVERAGE_CAP = {
    "Scalping": 3.0,
    "Intraday": 5.0,
    "Intraday_Trailing": 5.0,
    "Aggressive": 10.0,
}
DEFAULT_LEVERAGE_CAP = 5.0
LIQ_BUFFER = 0.005       # keep liquidation this far beyond the stop
MAINT_MARGIN = 0.005     # exchange maintenance margin assumption

EXPECTED_HOLD_BARS = 6   # avg bars-to-resolution proxy for the 4h stack
BAR_HOURS = 4
EXPIRY_SAFETY = 1.5      # need at least ~1.5x the expected hold of calendar room
BARS_PER_DAY = 6         # 24h / 4h, for annualizing per-bar ATR vol

# Liquid crypto option tenors (days). A 4h, 3.5xATR target needs real calendar
# room, so we round the required horizon UP to the nearest LISTED expiry -- a
# weekly is the realistic floor. Sub-week "expiries" priced theta so cheaply that
# the picker routed everything to options.
LISTED_EXPIRY_DAYS = (7.0, 14.0, 30.0)

TREND_STRATS = ("ma_crossover", "breakout", "vwap_cross")


def _nearest_listed_expiry(days_needed: float) -> float:
    """Round the required horizon up to the nearest liquid listed tenor."""
    for t in LISTED_EXPIRY_DAYS:
        if t >= days_needed:
            return t
    return LISTED_EXPIRY_DAYS[-1]


def _option_premium(S: float, strike: float, sigma_annual: float, T_years: float) -> float:
    """ATR-derived long-option premium proxy. ATM ~ 0.4*S*sigma*sqrt(T); the
    moneyness factor exp(-d^2/2) makes OTM strikes cheaper (d = standardized
    distance of the strike from spot)."""
    if S <= 0 or sigma_annual <= 0 or T_years <= 0:
        return 0.0
    atm = 0.4 * S * sigma_annual * math.sqrt(T_years)
    d = abs(strike - S) / (S * sigma_annual * math.sqrt(T_years))
    return atm * math.exp(-0.5 * d * d)


def build_instrument_signals(sig: dict, strat: str, profile: str) -> tuple[list[dict], str]:
    """Return ([spot, futures, options], best_instrument) for one signal + profile.

    Each element is a shallow copy of `sig` with instrument-specific fields added.
    Idle signals (side == 0 / no levels) get three bare copies and default to spot.
    """
    side = sig.get("side", 0)
    S = sig.get("entry", 0.0) or 0.0
    stop = sig.get("stop")
    target = sig.get("target")
    atr = sig.get("atr", 0.0) or 0.0
    conv = min(sig.get("conviction", 0.0) / 40.0, 1.0)

    if side == 0 or S <= 0 or stop is None or target is None:
        bare = []
        for itype in ("spot", "futures", "options"):
            s = sig.copy()
            s["instrument_type"] = itype
            bare.append(s)
        return bare, "spot"

    stop_pct = abs(S - stop) / S
    M = abs(target - S)  # expected move (price units)

    # 1. SPOT -- unleveraged base case
    spot = sig.copy()
    spot["instrument_type"] = "spot"
    spot["leverage"] = 1.0
    spot["margin"] = S          # per-unit notional
    spot["risk_pct"] = stop_pct  # % of notional to the stop

    # 2. FUTURES -- same price plan, leverage capped by profile AND liquidation
    cap = PROFILE_LEVERAGE_CAP.get(profile, DEFAULT_LEVERAGE_CAP)
    denom = stop_pct + LIQ_BUFFER + MAINT_MARGIN
    L_max_liq = 1.0 / denom if denom > 0 else cap
    L = max(1.0, min(L_max_liq, cap))
    fut = sig.copy()
    fut["instrument_type"] = "futures"
    fut["leverage"] = round(L, 1)
    fut["margin"] = S / L
    fut["risk_pct"] = stop_pct * L  # loss as % of margin posted

    # 3. OPTIONS -- defined-risk, convex
    opt = sig.copy()
    opt["instrument_type"] = "options"
    opt["option_type"] = "call" if side == 1 else "put"
    horizon_days = EXPECTED_HOLD_BARS * BAR_HOURS * EXPIRY_SAFETY / 24.0
    T_days = _nearest_listed_expiry(horizon_days)
    opt["expiry_days"] = T_days
    T_years = T_days / 365.0
    sigma_annual = (atr / S) * math.sqrt(BARS_PER_DAY * 365) if S > 0 else 0.0
    # OTM (cheaper, more convex) on high conviction; ATM otherwise. side picks the
    # correct sign: OTM call sits above spot, OTM put below.
    strike = S + 0.5 * atr * side if conv > 0.6 else S
    premium = _option_premium(S, strike, sigma_annual, T_years)
    breakeven_dist = abs(strike - S) + premium  # underlying travel from S to break even
    opt["strike"] = round(strike, 2)
    opt["premium"] = premium
    opt["max_loss"] = premium
    opt["breakeven_pct"] = breakeven_dist / S if S > 0 else 0.0

    # --- picker: score each instrument, flag the best routing ---------------
    trendy = 1 if strat in TREND_STRATS else 0
    reverting = 1 if strat == "bb_rsi_reversion" else 0
    move_be = M / breakeven_dist if breakeven_dist > 0 else 0.0  # exp move / breakeven move
    funding_drag = 0.0001
    liq_penalty = 0.1 if L_max_liq < cap else 0.0  # liquidation is the binding constraint

    score_spot = 0.5 * reverting + 0.3 * (1 - conv) + 0.2 * (1 if breakeven_dist > M else 0)
    score_futures = (0.35 * conv + 0.30 * trendy + 0.20 * (1 - stop_pct)
                     - 0.15 * funding_drag - liq_penalty)
    score_options = (0.35 * min(max(move_be - 1, 0), 2) + 0.25 * conv
                     + 0.20 * (1 if stop_pct > 0.05 else 0) - 0.2 * reverting)

    scores = {"spot": score_spot, "futures": score_futures, "options": score_options}
    best = max(scores, key=scores.get)
    return [spot, fut, opt], best
