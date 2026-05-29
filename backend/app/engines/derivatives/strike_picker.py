"""Greeks-aware strike selection across a single-expiry contract list.

For each candidate at the chosen expiry:
  1. Enrich Greeks (BSM-fill via option_pricing.enrich_with_greeks).
  2. Score liquidity; drop the contract on any hard-floor breach.
  3. Score delta proximity to profile.target_delta within tolerance band.
  4. Score gamma magnitude (favoured for scalping ATM, penalised for swing).
  5. BSM-revalue at expected-exit T (time_shifted_revaluation) for
     expected_R + theta_burn — drop contracts with veto_reason set.
  6. Compute composite rank score; return ranked candidates.

The picker does NOT make the final futures-vs-options choice — that's
instrument_chooser. By the time picker runs, we already decided to look
at the option chain.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.engines.derivatives.liquidity_score import score as liquidity_score
from app.engines.derivatives.schemas import StrategyDerivativesProfile, LiquidityScore
from app.engines.derivatives.time_shifted_revaluation import revalue
from app.engines.risk.option_pricing import enrich_with_greeks
from app.schemas.market import OptionSummary


@dataclass
class ScoredStrike:
    option: OptionSummary
    liquidity: LiquidityScore
    expected_r: float
    theta_burn_pct: float
    premium_at_tp: float
    premium_at_sl: float
    delta_proximity_score: float
    gamma_score: float
    composite: float
    breakdown: dict[str, float]
    drop_reason: str = ""


def _delta_proximity_score(delta: float, target: float, tol: float) -> float:
    """1.0 at exact match; linearly decays to 0 outside the tolerance band."""
    if tol <= 0:
        return 1.0 if abs(delta - target) < 1e-9 else 0.0
    distance = abs(abs(delta) - abs(target))
    if distance >= 2 * tol:
        return 0.0
    return max(0.0, 1.0 - distance / (2 * tol))


def _gamma_score(gamma: float, scaled_max: float = 1e-3) -> float:
    """Gamma's tiny natural scale → normalise into [0, 1] via min(g, max)/max.
    `scaled_max` ≈ 1e-3 is roughly the max gamma seen for short-DTE crypto
    options around BTC scale — anything above is treated as saturated."""
    if gamma <= 0:
        return 0.0
    return min(1.0, gamma / scaled_max)


def pick(
    *,
    candidates: list[OptionSummary],
    profile: StrategyDerivativesProfile,
    spot: float,
    spot_tp: float,
    spot_sl: float,
    expected_hold_days: float,
    prefer_gamma: bool,
    full_chain: Optional[list[OptionSummary]] = None,
) -> list[ScoredStrike]:
    """Score every contract in `candidates`; return list sorted desc by
    composite. Dropped contracts come last with `drop_reason` set."""
    full_chain = full_chain or candidates
    scored: list[ScoredStrike] = []

    # ── per-contract scoring ──────────────────────────────────────────
    for opt in candidates:
        enriched = enrich_with_greeks(opt, spot=spot)

        liq = liquidity_score(enriched, profile)
        if not liq.passes_floor:
            scored.append(ScoredStrike(
                option=enriched, liquidity=liq,
                expected_r=0, theta_burn_pct=0,
                premium_at_tp=0, premium_at_sl=0,
                delta_proximity_score=0, gamma_score=0,
                composite=0, breakdown={},
                drop_reason=f"liquidity:{liq.floor_breach_reason}",
            ))
            continue

        # IVR cap — adapter ships IV as percent; normalise to decimal
        iv = enriched.mark_iv
        if iv > 5.0:
            iv = iv / 100.0
        # We treat profile.ivr_pct_naked_max as "max acceptable IV percentile"
        # but at the chain level we can only see absolute IV. As a proxy
        # we cap absolute IV at ivr_pct_naked_max / 100 × 1.5 (75% IV cap
        # for triple_st with ivr_pct_naked_max=40). Imperfect; Phase 1 of
        # the selector should consult CalibrationService.ivr_bands().
        proxy_iv_cap = max(0.20, profile.ivr_pct_naked_max / 100.0 * 1.5)
        if iv > proxy_iv_cap:
            scored.append(ScoredStrike(
                option=enriched, liquidity=liq,
                expected_r=0, theta_burn_pct=0,
                premium_at_tp=0, premium_at_sl=0,
                delta_proximity_score=0, gamma_score=0,
                composite=0, breakdown={},
                drop_reason=f"iv_too_high:{iv:.2%}>{proxy_iv_cap:.0%}",
            ))
            continue

        reval = revalue(
            spot_now=spot, spot_tp=spot_tp, spot_sl=spot_sl,
            strike=enriched.strike, dte_now=enriched.dte,
            expected_hold_days=expected_hold_days, iv=iv,
            is_call=enriched.option_type == "call",
        )
        if reval is None:
            scored.append(ScoredStrike(
                option=enriched, liquidity=liq,
                expected_r=0, theta_burn_pct=0,
                premium_at_tp=0, premium_at_sl=0,
                delta_proximity_score=0, gamma_score=0,
                composite=0, breakdown={},
                drop_reason="bsm_degenerate",
            ))
            continue
        if reval.veto_reason:
            scored.append(ScoredStrike(
                option=enriched, liquidity=liq,
                expected_r=reval.expected_r, theta_burn_pct=reval.theta_burn_pct,
                premium_at_tp=reval.premium_at_tp, premium_at_sl=reval.premium_at_sl,
                delta_proximity_score=0, gamma_score=0,
                composite=0, breakdown={},
                drop_reason=reval.veto_reason,
            ))
            continue

        delta_score = _delta_proximity_score(
            enriched.delta, profile.target_delta, profile.target_delta_tolerance,
        )
        gamma_score = _gamma_score(enriched.gamma)

        # Composite weights tuned for "Greeks-aware":
        #   0.30 delta proximity, 0.25 liquidity, 0.20 expected R,
        #   0.15 gamma (when prefer_gamma) or theta-friendliness (when not), 0.10 spread
        gamma_weight = 0.15 if prefer_gamma else 0.0
        theta_weight = 0.15 if not prefer_gamma else 0.0
        theta_friend = max(0.0, 1.0 - reval.theta_burn_pct)        # 1 = no theta drag

        # Expected R contribution: saturate at 3R (anything above is rare and noise-prone)
        r_score = min(1.0, max(0.0, reval.expected_r / 3.0))

        composite = (
            0.30 * delta_score
            + 0.25 * liq.composite
            + 0.20 * r_score
            + gamma_weight * gamma_score
            + theta_weight * theta_friend
            + 0.10 * liq.spread_score
        )

        scored.append(ScoredStrike(
            option=enriched, liquidity=liq,
            expected_r=reval.expected_r, theta_burn_pct=reval.theta_burn_pct,
            premium_at_tp=reval.premium_at_tp, premium_at_sl=reval.premium_at_sl,
            delta_proximity_score=delta_score, gamma_score=gamma_score,
            composite=composite, breakdown={
                "delta": delta_score, "liquidity": liq.composite,
                "expected_r": r_score, "gamma": gamma_score,
                "theta_friend": theta_friend, "spread": liq.spread_score,
            },
        ))

    # Sort: kept (drop_reason empty) by composite desc, then dropped at the end.
    kept = [s for s in scored if not s.drop_reason]
    dropped = [s for s in scored if s.drop_reason]
    kept.sort(key=lambda s: s.composite, reverse=True)
    return kept + dropped
