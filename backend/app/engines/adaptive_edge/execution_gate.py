"""Final execution gate for Adaptive Edge.

The gate is intentionally independent from broker/execution adapters. Its only
job is to determine whether a strategy decision is authorized to cross into an
execution boundary.

Adaptive Edge remains non-executable while any required strategy-specific
formula is unresolved. This module makes that invariant executable and
machine-testable instead of relying on callers to remember the policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .formula_registry import FormulaStatus, get_formula


REQUIRED_STRATEGY_FORMULAS: tuple[str, ...] = tuple(
    f"F-{number:03d}" for number in range(101, 115)
)


class ExecutionGateStatus(str, Enum):
    AUTHORIZED = "authorized"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ExecutionGateDecision:
    status: ExecutionGateStatus
    required_formulas: tuple[str, ...]
    blocking_formulas: tuple[str, ...]
    reason: str | None = None

    @property
    def authorized(self) -> bool:
        return self.status is ExecutionGateStatus.AUTHORIZED


def evaluate_execution_gate(
    formula_ids: Iterable[str] = REQUIRED_STRATEGY_FORMULAS,
) -> ExecutionGateDecision:
    """Evaluate the final strategy execution gate.

    Every required formula must be explicitly IMPLEMENTED. Unknown formula IDs
    are treated as blocking rather than ignored. This guarantees fail-closed
    behavior when the registry and caller disagree.
    """
    required = tuple(formula_ids)
    blocking: list[str] = []

    for formula_id in required:
        try:
            definition = get_formula(formula_id)
        except KeyError:
            blocking.append(formula_id)
            continue
        if definition.status is not FormulaStatus.IMPLEMENTED:
            blocking.append(formula_id)

    if blocking:
        return ExecutionGateDecision(
            status=ExecutionGateStatus.BLOCKED,
            required_formulas=required,
            blocking_formulas=tuple(blocking),
            reason="required_strategy_formula_not_implemented",
        )

    return ExecutionGateDecision(
        status=ExecutionGateStatus.AUTHORIZED,
        required_formulas=required,
        blocking_formulas=(),
        reason=None,
    )


def require_execution_authorized(
    formula_ids: Iterable[str] = REQUIRED_STRATEGY_FORMULAS,
) -> ExecutionGateDecision:
    """Return the authorized decision or raise a deterministic gate error."""
    decision = evaluate_execution_gate(formula_ids)
    if not decision.authorized:
        raise ExecutionBlockedError(decision)
    return decision


class ExecutionBlockedError(RuntimeError):
    """Raised when strategy execution crosses an unresolved formula boundary."""

    def __init__(self, decision: ExecutionGateDecision) -> None:
        self.decision = decision
        super().__init__(
            "Adaptive Edge execution blocked: "
            + ", ".join(decision.blocking_formulas)
            + " require authoritative resolution before execution"
        )


@dataclass(frozen=True)
class FrictionExpectancyDecision:
    authorized: bool
    expected_gain_inr: float
    estimated_friction_inr: float
    friction_ratio: float
    reason: str | None = None


def evaluate_friction_expectancy_gate(
    *,
    entry_price: float,
    target_price: float,
    lot_size: int,
    estimated_friction_inr: float = 60.0,
    min_friction_multiplier: float = 4.0,
) -> FrictionExpectancyDecision:
    """Validate that expected trade gain exceeds minimum friction multiplier threshold.

    Guards against retail micro-churn where STT and transaction taxes consume alpha.
    """
    points_gain = max(0.0, abs(target_price - entry_price))
    expected_gain = points_gain * max(1, lot_size)
    min_required = estimated_friction_inr * min_friction_multiplier
    if expected_gain < min_required:
        return FrictionExpectancyDecision(
            authorized=False,
            expected_gain_inr=round(expected_gain, 2),
            estimated_friction_inr=round(estimated_friction_inr, 2),
            friction_ratio=round(expected_gain / max(1.0, estimated_friction_inr), 2),
            reason=f"expected_gain_below_friction_threshold ({expected_gain:.2f} < {min_required:.2f})",
        )
    return FrictionExpectancyDecision(
        authorized=True,
        expected_gain_inr=round(expected_gain, 2),
        estimated_friction_inr=round(estimated_friction_inr, 2),
        friction_ratio=round(expected_gain / max(1.0, estimated_friction_inr), 2),
        reason=None,
    )


@dataclass(frozen=True)
class SpreadLiquidityDecision:
    authorized: bool
    spread_pts: float
    spread_pct: float
    reason: str | None = None


def evaluate_bid_ask_spread_gate(
    *,
    bid: float,
    ask: float,
    max_spread_pct: float = 3.0,
    max_spread_pts: float = 3.0,
) -> SpreadLiquidityDecision:
    """Guards against transaction cost guillotine: wide bid/ask spreads sweeping thin depths."""
    if bid <= 0 or ask <= 0 or ask < bid:
        return SpreadLiquidityDecision(
            authorized=False,
            spread_pts=0.0,
            spread_pct=0.0,
            reason="invalid_or_missing_depth_quotes",
        )
    spread = ask - bid
    mid = (bid + ask) / 2.0
    pct = (spread / mid) * 100.0 if mid > 0 else 0.0

    if spread > max_spread_pts and pct > max_spread_pct:
        return SpreadLiquidityDecision(
            authorized=False,
            spread_pts=round(spread, 2),
            spread_pct=round(pct, 2),
            reason=f"wide_bid_ask_spread_slippage_risk ({spread:.2f} pts / {pct:.1f}%)",
        )
    return SpreadLiquidityDecision(
        authorized=True,
        spread_pts=round(spread, 2),
        spread_pct=round(pct, 2),
        reason=None,
    )


@dataclass(frozen=True)
class VegaIvDecision:
    authorized: bool
    iv_rank: float
    is_high_vega_risk: bool
    recommended_structure: str
    reason: str | None = None


def evaluate_vega_iv_gate(
    *,
    iv_rank: float,
    max_naked_iv_rank: float = 75.0,
) -> VegaIvDecision:
    """Guards against Theta-Vega Volatility Inversion: buying calls/puts during morning IV spikes."""
    if iv_rank > max_naked_iv_rank:
        return VegaIvDecision(
            authorized=False,
            iv_rank=round(iv_rank, 1),
            is_high_vega_risk=True,
            recommended_structure="VERTICAL_SPREAD",
            reason=f"extreme_iv_rank_vega_crush_risk (IVR={iv_rank:.1f} > {max_naked_iv_rank:.1f})",
        )
    return VegaIvDecision(
        authorized=True,
        iv_rank=round(iv_rank, 1),
        is_high_vega_risk=False,
        recommended_structure="NAKED_OPTION",
        reason=None,
    )


@dataclass(frozen=True)
class AntiChaseDecision:
    authorized: bool
    distance_pts: float
    atr_ratio: float
    reason: str | None = None


def evaluate_anti_chase_gate(
    *,
    current_price: float,
    anchor_price: float,
    atr: float,
    max_atr_dist: float = 1.5,
) -> AntiChaseDecision:
    """Guards against co-location latency deficits: buying the top of an HFT CVD liquidity sweep."""
    if atr <= 0 or current_price <= 0 or anchor_price <= 0:
        return AntiChaseDecision(
            authorized=True,
            distance_pts=0.0,
            atr_ratio=0.0,
            reason=None,
        )
    dist = abs(current_price - anchor_price)
    ratio = dist / atr
    if ratio > max_atr_dist:
        return AntiChaseDecision(
            authorized=False,
            distance_pts=round(dist, 2),
            atr_ratio=round(ratio, 2),
            reason=f"chase_extended_pullback_required ({ratio:.2f} ATR > {max_atr_dist:.2f} max limit)",
        )
    return AntiChaseDecision(
        authorized=True,
        distance_pts=round(dist, 2),
        atr_ratio=round(ratio, 2),
        reason=None,
    )


@dataclass(frozen=True)
class DteGammaDecision:
    authorized: bool
    dte: int
    moneyness: str
    is_expiry_day: bool
    reason: str | None = None


def evaluate_dte_gamma_gate(
    *,
    dte: int,
    moneyness: str,
    delta: float | None = None,
) -> DteGammaDecision:
    """Guards against 0/1 DTE Gamma Inversion & Theta Burn: prevents fragile OTM on expiry day."""
    is_expiry = dte <= 1
    m = moneyness.upper()
    if is_expiry:
        # On expiry day, OTM legs suffer violent gamma noise stop-outs
        if m in ("OTM1", "OTM2", "OTM3", "FAR_OTM"):
            return DteGammaDecision(
                authorized=False,
                dte=dte,
                moneyness=moneyness,
                is_expiry_day=True,
                reason="0_or_1_dte_otm_gamma_whipsaw_blocked (use ATM or ITM on expiry day)",
            )
        if delta is not None and abs(delta) < 0.45:
            return DteGammaDecision(
                authorized=False,
                dte=dte,
                moneyness=moneyness,
                is_expiry_day=True,
                reason="low_delta_gamma_vulnerability_on_expiry_day",
            )
    return DteGammaDecision(
        authorized=True,
        dte=dte,
        moneyness=moneyness,
        is_expiry_day=is_expiry,
        reason=None,
    )

