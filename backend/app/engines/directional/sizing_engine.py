from typing import Dict, List, Optional, Tuple

from app.schemas.execution import TradeStructure, SizedTrade
from app.schemas.risk import RiskParams
from app.schemas.directional import MacroRegime
from app.engines.risk.regime_adaptive_sizer import adapt as regime_adapt, AdaptiveSizingConfig

_LEV_SCALE = {50: 0.15, 25: 0.30, 10: 0.50, 5: 0.75, 3: 0.85, 1: 1.0}

# Issue 12 — paper-only cold-start opt-in multiplier (hard-coded so callers
# can't bypass it via a different risk param).
_COLD_START_SIZE_MULT = 0.25
# Issue 5 — early-entry haircut multiplier.
_EARLY_ENTRY_SIZE_MULT = 0.5

# Conviction-fractional size multiplier from signal_score (0-20 scale).
# Maps signal strength to a continuous position-sizing fraction so higher-
# conviction signals get proportionally more capital. This replaces the old
# binary STRONG/SIGNAL/NONE -> same-size approach.
def _conviction_mult(signal_score: float) -> float:
    if signal_score >= 18.0:
        return 1.0
    elif signal_score >= 15.0:
        return 0.85
    elif signal_score >= 12.0:
        return 0.65
    elif signal_score >= 8.0:
        return 0.40
    return 0.0  # setup_engine should filter these before sizing


# Per-regime size multipliers. Calibrated against the 2026-05-18 baseline,
# which showed RANGING was the strategy's most profitable regime (74% WR,
# +0.05% avg) while BULL_TREND was the worst (44% WR, -0.34% avg). The
# legacy non-trending haircut (0.25x on RANGING/IDLE) was inversely
# allocating exposure to where the strategy actually wins. New table:
#   - IDLE: 0.25x (true low-vol, false signals dominate)
#   - VOLATILE: 0.75x (high noise, but real moves)
#   - RANGING / NEUTRAL: 1.0x (preferred — mean-reversion is where edge lives)
#   - BULL_TREND family: 0.5x (penalize until baseline shows profitability)
#   - BEAR_TREND family: 1.0x (close to breakeven; give it room)
#   - default: 1.0x
_REGIME_SIZE_MULT: Dict[MacroRegime, float] = {
    MacroRegime.IDLE:           0.25,
    MacroRegime.CHOPPY:         0.25,
    MacroRegime.VOLATILE:       0.75,
    MacroRegime.RANGING:        1.0,
    MacroRegime.NEUTRAL:        1.0,
    MacroRegime.BULL_TREND:     0.5,
    MacroRegime.BULL_TRENDING:  0.5,
    MacroRegime.BULL_WEAK:      0.5,
    MacroRegime.BULL_RANGING:   1.0,
    MacroRegime.BULLISH:        0.5,
    MacroRegime.BEAR_TREND:     1.0,
    MacroRegime.BEAR_TRENDING:  1.0,
    MacroRegime.BEAR_WEAK:      0.75,
    MacroRegime.BEAR_RANGING:   1.0,
    MacroRegime.BEARISH:        1.0,
}


def _regime_size_mult(macro_regime: Optional[MacroRegime]) -> float:
    """Returns the per-regime size multiplier, defaulting to 1.0."""
    if macro_regime is None:
        return 1.0
    return _REGIME_SIZE_MULT.get(macro_regime, 1.0)


# Tier C #15 — correlation drawdown limiter. If the proposed trade's underlying
# has |corr| > 0.8 against any open position's underlying, scale size by 0.5×.
_CORRELATION_HIGH_THRESHOLD = 0.8
_CORRELATION_HIGH_PENALTY = 0.5

# Round-trip slippage budget used when wiring slippage into the Kelly-derived
# max_loss_per_contract. Each leg of the trade incurs slippage_bps; we count
# entry + exit (~ 2x bps). Cost is added on top of the structure's max_loss
# so target_risk_pct shrinks proportionally to leverage-tier slippage.
_SLIPPAGE_LEGS = 2


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
    signal_score: float = -1.0,
    early_entry: bool = False,
    min_rr: float = 0.0,  # 0 = no gate; >0 rejects trades below this RR
    atr_percentile: float = 50.0,  # for regime-adaptive sizing
    consecutive_losses: int = 0,  # 0 = no haircut; >0 shrinks size exponentially
    macro_regime: Optional[MacroRegime] = None,
    underlying: Optional[str] = None,
    open_position_assets: Optional[List[str]] = None,
    correlation_matrix: Optional[Dict[Tuple[str, str], float]] = None,
    open_interest: Optional[float] = None,
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

    # Min RR gate: reject trades with unfavourable risk-reward ratio.
    rr = structure.risk_reward if structure.risk_reward and structure.risk_reward > 0 else 1.0
    if min_rr > 0.0 and rr < min_rr:
        return SizedTrade(
            structure=structure, contracts=0,
            position_value=0.0, max_risk_usd=0.0, capital_at_risk_pct=0.0,
            blocked_reason=f"rr_{rr:.2f}_below_min_{min_rr:.2f}",
        )

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

    # Conviction-fractional sizing: higher signal_score → larger position.
    # Only applies when signal_score is explicitly provided (> 0).
    conv = 1.0
    conv_active = False
    if signal_score > 0.0:
        conv = _conviction_mult(signal_score)
        conv_active = conv < 1.0
        if conv < 1.0:
            target_risk_pct *= conv

    # Regime-adaptive ATR-percentile multiplier (compression 0.5× / normal 1.0×
    # / expansion 1.25× / hyper 0.75×). Composable with all other multipliers.
    atr_mult = regime_adapt(atr_percentile)
    if atr_mult < 1.0:
        target_risk_pct *= atr_mult

    # Per-regime size multiplier (replaces the legacy non-trending haircut).
    regime_mult = _regime_size_mult(macro_regime)
    regime_haircut = regime_mult < 1.0
    if regime_mult != 1.0:
        target_risk_pct *= regime_mult

    # Consecutive-loss haircut: 1 loss → 0.7×, 2 → 0.49×, 3 → 0.34×.
    # Compounds with all other multipliers; caller resets this counter on win.
    loss_haircut_active = False
    if consecutive_losses > 0:
        loss_mult = round(0.7 ** consecutive_losses, 4)
        target_risk_pct *= loss_mult
        loss_haircut_active = True

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

    # Wire slippage into the Kelly-derived denominator. Each leg of the trade
    # (entry + exit) pays the tiered slippage from risk.slippage; we lift
    # max_loss_per_contract by that round-trip cost so target_risk_pct is
    # divided over realistic worst-case slippage and we stop oversizing.
    try:
        from app.engines.risk.slippage import slippage_bps as _slippage_bps
        slip_bps = _slippage_bps(float(leverage), open_interest)
        slip_uplift = _SLIPPAGE_LEGS * float(slip_bps) / 10_000.0
        if slip_uplift > 0:
            max_loss_per_contract = max_loss_per_contract * (1.0 + slip_uplift)
    except Exception:
        # Defensive: never fail sizing on a slippage lookup error.
        pass

    raw_contracts = int(max_risk_usd / max_loss_per_contract)
    contracts = max(1, min(raw_contracts, risk_params.max_contracts))

    position_value = contracts * leg_premium
    actual_risk = contracts * max_loss_per_contract

    notes = []
    if cold_start_active:
        notes.append("cold_start_bootstrap_paper")
    if early_entry:
        notes.append("early_entry_haircut")
    if conv_active:
        notes.append(f"conviction_mult={conv:.2f}")
    if atr_mult < 1.0:
        notes.append(f"atr_adapt_mult={atr_mult:.2f}")
    if loss_haircut_active:
        notes.append(f"loss_haircut_{consecutive_losses}loss")
    if regime_haircut:
        notes.append(f"regime_size_mult={regime_mult:.2f}")
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
