"""DerivativesSelector schemas — Pydantic models for the inputs the
selector consumes and the outputs every strategy execute callsite reads.

Three groups:
  • Input: `SignalContext` (the bundle a strategy hands to the selector)
    and `MarketContext` (live numbers the selector reads on each call —
    spot, IVR, funding, regime sizing multiplier, CB state).
  • Configuration: `StrategyDerivativesProfile` (per-strategy preferences;
    user-overridable via /derivatives/config) and `LiquidityScore`
    (intermediate composite consumed by the strike picker).
  • Output: `DerivativesCandidate` (one candidate the picker considered)
    and `DerivativesDecision` (the final selector verdict + freeze_token
    + top-3 alternatives the user can swap into via the FE table).
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Profile (configuration) ───────────────────────────────────────────


class InstrumentBias(str, Enum):
    """How aggressively the strategy prefers options vs futures."""
    AUTO       = "auto"        # selector decides via instrument_chooser
    FUTURES    = "futures"     # always futures (e.g. StatArb)
    OPTIONS    = "options"     # always options (asymmetric-payoff strategies)


class StrategyDerivativesProfile(BaseModel):
    """Per-strategy configuration consumed by the selector. Defaults come
    from `profiles.DEFAULT_PROFILES` and can be overridden per-strategy
    via /derivatives/config."""
    strategy: str
    enabled: bool = False                           # Phase 5 flips this on per-strategy

    # Instrument selection
    instrument_bias: InstrumentBias = InstrumentBias.AUTO
    target_delta: float = 0.50                      # ATM by default
    target_delta_tolerance: float = 0.10            # acceptable band around target
    prefer_asymmetry: bool = False                  # OTM lottery-ticket bias when True

    # Expiry selection
    dte_min: int = 0
    dte_preferred: int = 1
    dte_max: int = 7

    # Hold time + tightening
    expected_hold_minutes: int = 75                 # default = scalping 15 × 5m
    expiry_close_minutes_before: int = 120          # overrides MODES default when set
    front_back_iv_diff_max: float = 0.05            # reject if front-month IV > back +5 vol pts

    # Risk / sizing
    leverage_cap: float = 10.0
    max_premium_pct_of_account: float = 0.015       # single-trade premium debit ceiling
    funding_cost_max_pct_of_R: float = 0.25         # funding cost / expected R hard cap

    # Liquidity gates
    min_oi: float = 50.0
    min_volume_24h_x_contract: float = 5.0          # multiple of contract_size
    max_spread_pct: float = 0.05                    # 5% spread cap

    # IVR cap for long-options entries (reject buying expensive vol)
    ivr_pct_naked_max: int = 70

    # Auto-execute toggles — fire automatically when algo_mode is ON.
    # `enabled` gates the selector; these two gate the auto-fire arm.
    # Default OFF so a flip of `enabled` alone NEVER auto-trades — the
    # operator must explicitly opt into auto-execution.
    auto_execute_futures: bool = False
    auto_execute_options: bool = False


# ── Inputs ────────────────────────────────────────────────────────────


class MarketContext(BaseModel):
    """Live market state passed to the selector at decide-time."""
    spot: float
    underlying: str
    ivr_pct: Optional[float] = None                 # current IV rank percentile 0-100
    funding_8h_pct: Optional[float] = None          # perp funding (decimal)
    basis_pct: Optional[float] = None               # (perp − spot) / spot
    atr_percentile: Optional[float] = None          # for regime sizing
    win_rate: Optional[float] = None                # CalibrationService trailing win rate
    avg_R: Optional[float] = None                   # trailing avg-R when known
    cb_size_mult: float = 1.0                       # DrawdownCircuitBreaker.size_multiplier()
    portfolio_value: float = 100_000.0              # NAV for premium-cap and Greeks budget


class SignalContext(BaseModel):
    """Everything a strategy passes to the selector for one signal.
    Strategy fills the fields it knows; rest stay at defaults.

    `expected_hold_minutes` overrides the profile when the signal has a
    tighter target (e.g. SMC pattern with intra-bar target). Most
    strategies leave it None and the profile default wins.
    """
    strategy: str                                   # "scalping/price_action", "triple_st", "statarb", ...
    underlying: str
    direction: str                                  # "long" | "short"
    entry: float                                    # spot anchor
    stop_loss: float                                # spot SL (futures-equivalent)
    take_profit: Optional[float] = None             # may be None for signal-exit strategies
    atr: float = 0.0                                # for SL/TP solver
    rr_target: float = 2.0
    signal_score: float = 0.0                       # 0-100; drives conviction
    signal_strength: str = "SIGNAL"                 # "STRONG"/"SIGNAL"/etc — text label
    expected_hold_minutes: Optional[int] = None     # override profile when set
    mode_name: str = "swing"                        # MODES key — drives DTE bounds, etc.
    presized: bool = False                          # True when entry/SL/TP are already
                                                    # validated (edge feed) — the futures
                                                    # solver passes them through without
                                                    # re-cushioning or re-gating R:R.


# ── Intermediate (liquidity) ──────────────────────────────────────────


class LiquidityScore(BaseModel):
    spread_score: float = 0.0                       # 1 = perfect, 0 = unusable
    oi_score: float = 0.0
    volume_score: float = 0.0
    composite: float = 0.0                          # weighted sum, 0-1
    passes_floor: bool = False                      # all hard floors met
    floor_breach_reason: str = ""


# ── Output ────────────────────────────────────────────────────────────


class DecisionStatus(str, Enum):
    OK         = "ok"           # selector picked a candidate; freeze_token returned
    DEFER      = "defer"        # no candidate fits the budget right now — user can re-poll
    FAIL_OPEN  = "fail_open"    # selector couldn't run (data missing) — caller falls back
    PROFILE_OFF = "profile_off" # profile.enabled=False — caller uses legacy path


class DerivativesCandidate(BaseModel):
    """One contract the picker considered. The selected one is wrapped in
    the DerivativesDecision; the top-3 runners-up ride along so the FE
    table can show alternatives and the user can swap into one via
    `candidate_idx`."""
    rank: int = 0
    instrument_type: str                            # "futures" | "options"
    underlying: str
    option_symbol: Optional[str] = None             # set when options
    option_type: Optional[str] = None               # "call" | "put"
    strike: Optional[float] = None
    expiry: Optional[str] = None                    # DDMMYY when options
    dte: Optional[int] = None

    # Trade economics
    entry_price: float                              # spot anchor
    direction: str
    contracts: float                                # may be fractional (sub-1 lots OK on DEI)
    leverage: float = 1.0                           # always 1 for options; chosen for futures
    notional_usd: float = 0.0
    premium_usd: Optional[float] = None             # entry premium × contracts (options only)

    # SL/TP (spot for futures; premium for options)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    sl_premium: Optional[float] = None              # BSM-priced option SL premium
    tp_premium: Optional[float] = None              # BSM-priced option TP premium

    # Expected R + cost projections
    expected_r: float = 0.0                         # multiple of risk the TP delivers
    projected_funding_cost_usd: float = 0.0
    projected_theta_burn_usd: float = 0.0           # for options: BSM-derived decay over hold

    # Greeks at entry (options only)
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    rho: float = 0.0

    # Health
    liquidity: Optional[LiquidityScore] = None
    spread_pct: float = 0.0
    open_interest: float = 0.0
    mark_iv: float = 0.0

    # Why this rank
    score: float = 0.0
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class DerivativesDecision(BaseModel):
    status: DecisionStatus
    chosen: Optional[DerivativesCandidate] = None
    alternatives: list[DerivativesCandidate] = Field(default_factory=list)
    freeze_token: Optional[str] = None              # UUID; required by /execute
    freeze_token_ttl_ms: int = 0
    reason: str = ""                                # human-readable explanation
    code: str = ""                                  # machine-readable when status ∈ {DEFER, FAIL_OPEN, PROFILE_OFF}
    timestamp_ms: int = 0
    warnings: list[str] = Field(default_factory=list)


class DualDerivativesDecision(BaseModel):
    """Selector output when the caller wants BOTH best-futures and
    best-options candidates side-by-side (so the FE can render two
    parallel tables instead of one mixed table).

    Each leg is an independent `DerivativesDecision` with its own
    freeze_token, so the user can execute futures, options, or both
    without sharing freeze state.

    `profile_off=True` short-circuits the whole pair (the strategy's
    `profile.enabled` is False); both legs will be unset.
    """
    status: DecisionStatus
    futures: Optional[DerivativesDecision] = None
    options: Optional[DerivativesDecision] = None
    reason: str = ""
    code: str = ""
    timestamp_ms: int = 0
    warnings: list[str] = Field(default_factory=list)
