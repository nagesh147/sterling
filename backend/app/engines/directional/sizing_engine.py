from typing import Dict, List, Optional, Tuple

from app.schemas.execution import TradeStructure, SizedTrade
from app.schemas.risk import RiskParams
from app.schemas.directional import MacroRegime

_LEV_SCALE = {50: 0.15, 25: 0.30, 10: 0.50, 5: 0.75, 3: 0.85, 1: 1.0}

# Issue 12 — paper-only cold-start opt-in multiplier (hard-coded so callers
# can't bypass it via a different risk param).
_COLD_START_SIZE_MULT = 0.25
# Issue 5 — early-entry haircut multiplier.
_EARLY_ENTRY_SIZE_MULT = 0.5

# Tier A #8 — non-trending regime haircut. We recently allowed mean-reversion
# setups in IDLE / RANGING; this caps their notional aggression at 25 % of the
# normal Kelly/leverage-derived sizing.
_NON_TRENDING_REGIME_MULT = 0.25
_NON_TRENDING_REGIMES = frozenset({MacroRegime.IDLE, MacroRegime.RANGING})

# Tier C #15 — correlation drawdown limiter. If the proposed trade's underlying
# has |corr| > 0.8 against any open position's underlying, scale size by 0.5×.
_CORRELATION_HIGH_THRESHOLD = 0.8
_CORRELATION_HIGH_PENALTY = 0.5


def _max_correlation_with_open_positions(
    underlying: Optional[str],
    open_position_assets: Optional[List[str]],
    correlation_matrix: Optional[Dict[Tuple[str, str], float]],
) -> float:
    """
    Look up the largest |correlation| between `underlying` and any of the
    `open_position_assets` in `correlation_matrix`.

    `correlation_matrix` is the dict produced by
    `analytics.correlation.CorrelationTracker.matrix()` — keyed by (asset_a, asset_b)
    with symmetric entries. Returns 0.0 when any input is missing.
    """
    if (
        not underlying
        or not open_position_assets
        or not correlation_matrix
    ):
        return 0.0
    max_abs = 0.0
    for pos in open_position_assets:
        if pos == underlying:
            continue
        c = correlation_matrix.get((underlying, pos))
        if c is None:
            c = correlation_matrix.get((pos, underlying))
        if c is None:
            continue
        abs_c = abs(float(c))
        if abs_c > max_abs:
            max_abs = abs_c
    return max_abs


def _nearest_lev_key(leverage: int) -> int:
    keys = sorted(_LEV_SCALE.keys())
    best = keys[0]
    for k in keys:
        if abs(k - leverage) < abs(best - leverage):
            best = k
    return best


def _fractional_kelly(win_rate: float, rr: float) -> float:
    """25% fractional Kelly criterion."""
    if rr <= 0:
        return 0.0
    kelly = (win_rate * rr - (1 - win_rate)) / rr
    return max(0.0, kelly * 0.25)


def size_trade(
    structure: TradeStructure,
    risk_params: RiskParams,
    leverage: int = 1,
    *,
    early_entry: bool = False,
    macro_regime: Optional[MacroRegime] = None,
    underlying: Optional[str] = None,
    open_position_assets: Optional[List[str]] = None,
    correlation_matrix: Optional[Dict[Tuple[str, str], float]] = None,
) -> SizedTrade:
    """
    Risk-based sizing with Kelly, leverage scaling, and regime/correlation
    overlays.

    New keyword args:
      * macro_regime          — Tier A #8: when IDLE/RANGING, target risk %
                                scaled by 0.25× (mean-reversion gets a small
                                fraction of the trend-aligned sizing).
      * underlying            — Tier C #15: this trade's underlying symbol
                                (e.g. "BTC"). Required for the correlation
                                penalty; without it the penalty is skipped.
      * open_position_assets  — list of underlyings already open in the book.
      * correlation_matrix    — dict from CorrelationTracker.matrix(); if any
                                |corr| with an open position exceeds 0.8, the
                                target risk % is scaled by 0.5×.
    """
    capital = risk_params.capital
    win_rate = getattr(risk_params, "win_rate", None)
    win_rate_known = bool(getattr(risk_params, "win_rate_known", True))
    cold_start_wr = getattr(risk_params, "cold_start_default_win_rate", None)
    trading_mode = getattr(risk_params, "trading_mode", None)

    # Issue 12 — cold-start opt-in (paper mode only).
    cold_start_active = False
    if not win_rate_known or win_rate is None:
        if (
            cold_start_wr is not None
            and trading_mode == "paper"
            and 0.0 < float(cold_start_wr) < 1.0
        ):
            win_rate = float(cold_start_wr)
            cold_start_active = True
        else:
            return SizedTrade(
                structure=structure, contracts=0,
                position_value=0.0, max_risk_usd=0.0, capital_at_risk_pct=0.0,
                blocked_reason="cold_start_win_rate_unknown",
            )

    rr = structure.risk_reward if structure.risk_reward and structure.risk_reward > 0 else 1.0
    frac_kelly = _fractional_kelly(win_rate, rr)

    # TTACE Phase 3: weak/negative calibrated edge → refuse to size.
    if frac_kelly <= 0.0:
        return SizedTrade(
            structure=structure, contracts=0,
            position_value=0.0, max_risk_usd=0.0, capital_at_risk_pct=0.0,
            blocked_reason="non_positive_kelly_edge",
        )

    # Base per-trade cap by instrument type
    struct_type = structure.structure_type
    if struct_type in ("bear_call_spread", "bull_put_spread", "naked_short"):
        base_cap = 0.010  # option_short: 1%
    elif struct_type == "futures":
        base_cap = 0.020  # futures: 2%
    else:
        base_cap = 0.015  # option_long: 1.5%

    lev_key = _nearest_lev_key(leverage)
    lev_factor = _LEV_SCALE.get(lev_key, 1.0)
    max_per = base_cap * lev_factor

    # Scalp leverage (≥ 50×): hard 0.5% risk ceiling regardless of Kelly or base_cap
    if leverage >= 50:
        max_per = min(max_per, 0.005)

    target_risk_pct = min(
        frac_kelly,
        max_per,
        getattr(risk_params, "max_position_pct", 0.05),
    )
    # Issue 12 — paper-bootstrap cold-start always sizes at 0.25× of normal.
    if cold_start_active:
        target_risk_pct *= _COLD_START_SIZE_MULT
    # Issue 5 — early-entry haircut.
    if early_entry:
        target_risk_pct *= _EARLY_ENTRY_SIZE_MULT

    # Tier A #8 — non-trending regime haircut.
    non_trending_haircut = (
        macro_regime is not None and macro_regime in _NON_TRENDING_REGIMES
    )
    if non_trending_haircut:
        target_risk_pct *= _NON_TRENDING_REGIME_MULT

    # Tier C #15 — multi-asset correlation drawdown limiter.
    max_open_corr = _max_correlation_with_open_positions(
        underlying, open_position_assets, correlation_matrix,
    )
    correlation_haircut = max_open_corr > _CORRELATION_HIGH_THRESHOLD
    if correlation_haircut:
        target_risk_pct *= _CORRELATION_HIGH_PENALTY

    max_risk_usd = capital * target_risk_pct

    leg_premium = structure.net_premium
    if leg_premium <= 0:
        leg_premium = 1.0

    max_loss_per_contract = structure.max_loss if structure.max_loss else leg_premium
    if max_loss_per_contract <= 0:
        max_loss_per_contract = leg_premium

    raw_contracts = int(max_risk_usd / max_loss_per_contract)
    contracts = max(1, min(raw_contracts, risk_params.max_contracts))

    position_value = contracts * leg_premium
    actual_risk = contracts * max_loss_per_contract

    notes = []
    if cold_start_active:
        notes.append("cold_start_bootstrap_paper")
    if early_entry:
        notes.append("early_entry_haircut")
    if non_trending_haircut:
        notes.append("non_trending_regime_haircut")
    if correlation_haircut:
        notes.append(f"correlation_haircut(|r|>{_CORRELATION_HIGH_THRESHOLD:.1f})")
    sized = SizedTrade(
        structure=structure,
        contracts=contracts,
        position_value=round(position_value, 2),
        max_risk_usd=round(actual_risk, 2),
        capital_at_risk_pct=round(actual_risk / capital * 100, 3),
    )
    if notes:
        # SizedTrade.blocked_reason is optional and used here as an info channel
        # for the UI when the trade was sized under an opt-in flag.
        sized = sized.model_copy(update={"blocked_reason": ",".join(notes)})
    return sized
