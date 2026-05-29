"""Per-strategy DerivativesProfile defaults.

Sourced from the plan file and the Plan-agent's defensible-defaults pass.
Strategy code never reads these directly — the selector resolves the
profile by `signal.strategy` via `get_profile()`, with /derivatives/config
overrides applied on top.

Profile keys match the strategy slug passed in `SignalContext.strategy`:
  • "scalping/price_action", "scalping/smc", "scalping/mean_reversion",
    "scalping/ma_crossover" — futures-bias, near-ATM, short hold.
  • "scalping/breakout", "scalping/delta_gamma" — options-bias for
    asymmetric payoff in low-IV regimes.
  • "triple_st" — Triple-ST RSI(2) daily mean-reversion. Swing hold.
  • "statarb" — futures-only, per-leg leverage cap, basis-aware.
  • "directional" — placeholder for when directional engines return.
"""
from __future__ import annotations

from app.engines.derivatives.schemas import InstrumentBias, StrategyDerivativesProfile


def _scalping_grind(strategy: str) -> StrategyDerivativesProfile:
    """Scalping PA/SMC/MR/MA — short-hold, near-ATM, futures preferred."""
    return StrategyDerivativesProfile(
        strategy=strategy,
        instrument_bias=InstrumentBias.AUTO,
        target_delta=0.50,
        target_delta_tolerance=0.05,
        prefer_asymmetry=False,
        dte_min=0,
        dte_preferred=1,
        dte_max=3,
        expected_hold_minutes=75,         # 15 × 5m, matches MODES["scalping"].max_hold_bars
        expiry_close_minutes_before=120,
        leverage_cap=25.0,
        max_premium_pct_of_account=0.015,
        funding_cost_max_pct_of_R=0.25,
        min_oi=50.0,
        max_spread_pct=0.05,
        ivr_pct_naked_max=85,
    )


def _scalping_breakout(strategy: str) -> StrategyDerivativesProfile:
    """Scalping Breakout/DeltaGamma — options preferred for asymmetric R."""
    p = _scalping_grind(strategy)
    p.instrument_bias = InstrumentBias.OPTIONS
    p.target_delta = 0.40                  # OTM lottery-ticket bias
    p.prefer_asymmetry = True
    p.leverage_cap = 15.0
    return p


DEFAULT_PROFILES: dict[str, StrategyDerivativesProfile] = {
    # Scalping
    "scalping/price_action":   _scalping_grind("scalping/price_action"),
    "scalping/smc":            _scalping_grind("scalping/smc"),
    "scalping/mean_reversion": _scalping_grind("scalping/mean_reversion"),
    "scalping/ma_crossover":   _scalping_grind("scalping/ma_crossover"),
    "scalping/breakout":       _scalping_breakout("scalping/breakout"),
    "scalping/delta_gamma":    _scalping_breakout("scalping/delta_gamma"),

    # Triple-ST RSI(2)
    "triple_st": StrategyDerivativesProfile(
        strategy="triple_st",
        instrument_bias=InstrumentBias.AUTO,
        target_delta=0.575,                # 0.55-0.60 band ITM
        target_delta_tolerance=0.075,
        dte_min=10,
        dte_preferred=14,
        dte_max=21,
        expected_hold_minutes=5 * 24 * 60, # 5 days
        expiry_close_minutes_before=120,
        leverage_cap=10.0,
        max_premium_pct_of_account=0.015,
        funding_cost_max_pct_of_R=0.25,
        min_oi=100.0,
        max_spread_pct=0.04,
        ivr_pct_naked_max=40,              # tighter — swing options need cheap IV
    ),

    # StatArb — futures-only, per-leg leverage capped, basis-aware
    "statarb": StrategyDerivativesProfile(
        strategy="statarb",
        instrument_bias=InstrumentBias.FUTURES,
        dte_min=0, dte_preferred=0, dte_max=0,
        expected_hold_minutes=60 * 24,     # 1 day median spread hold
        leverage_cap=5.0,                  # per leg; basis exposure capped 2× elsewhere
        max_premium_pct_of_account=0.02,
        funding_cost_max_pct_of_R=0.25,
        ivr_pct_naked_max=100,             # n/a for futures-only
    ),

    # Directional / Hybrid VCP — placeholder, lights up when engines return
    "directional": StrategyDerivativesProfile(
        strategy="directional",
        instrument_bias=InstrumentBias.AUTO,
        target_delta=0.60,
        target_delta_tolerance=0.05,
        dte_min=14,
        dte_preferred=21,
        dte_max=45,
        expected_hold_minutes=10 * 24 * 60,
        expiry_close_minutes_before=120,
        leverage_cap=8.0,
        max_premium_pct_of_account=0.02,
        funding_cost_max_pct_of_R=0.25,
        min_oi=80.0,
        max_spread_pct=0.04,
        ivr_pct_naked_max=50,
    ),
}


def get_profile(strategy: str, overrides: dict[str, StrategyDerivativesProfile] | None = None) -> StrategyDerivativesProfile:
    """Resolve the profile for `strategy`. Order of precedence:
       1. exact-match override
       2. exact-match default
       3. prefix-match default (e.g. "scalping/<unknown>" → falls back to scalping_grind)
       4. fully-defaulted profile (everything OFF)
    """
    if overrides and strategy in overrides:
        return overrides[strategy]
    if strategy in DEFAULT_PROFILES:
        return DEFAULT_PROFILES[strategy]
    # Prefix match — "scalping/<x>" → scalping_grind
    if "/" in strategy:
        prefix = strategy.split("/", 1)[0]
        for k, p in DEFAULT_PROFILES.items():
            if k.startswith(prefix + "/"):
                # Clone with this strategy slug
                return p.model_copy(update={"strategy": strategy})
    return StrategyDerivativesProfile(strategy=strategy, enabled=False)
