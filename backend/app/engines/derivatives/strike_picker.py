"""Greeks-aware strike selection across a single-expiry contract list.

For each candidate at the chosen expiry:
  1. Enrich Greeks (BSM-fill via option_pricing.enrich_with_greeks).
  2. Score liquidity; drop the contract on any hard-floor breach.
  3. Score delta proximity to profile.target_delta within tolerance band.
  4. Score gamma magnitude (favoured for scalping ATM, penalised for swing).
  5. BSM-revalue at expected-exit T (time_shifted_revaluation) for
     expected_R + theta_burn — drop contracts with veto_reason set.
  6. Compute composite rank score using dynamic timeframe weights; return ranked candidates.

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
    moneyness: float
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


def _get_timeframe(hold_days: float) -> str:
    if hold_days < 2 / 24:
        return "scalping"
    elif hold_days < 8 / 24:
        return "intraday"
    elif hold_days < 1.0:
        return "overnight"
    elif hold_days < 7.0:
        return "positional"
    else:
        return "swing"


def _get_weights(timeframe: str) -> dict[str, float]:
    """Dynamic weights table for crypto option strike selection."""
    if timeframe == "scalping":
        return {"delta": 0.20, "gamma": 0.25, "theta": 0.10, "vega": 0.15, "liquidity": 0.20, "skew": 0.10}
    elif timeframe == "intraday":
        return {"delta": 0.25, "gamma": 0.20, "theta": 0.15, "vega": 0.15, "liquidity": 0.15, "skew": 0.10}
    elif timeframe == "overnight":
        return {"delta": 0.25, "gamma": 0.15, "theta": 0.20, "vega": 0.15, "liquidity": 0.15, "skew": 0.10}
    elif timeframe == "positional":
        return {"delta": 0.30, "gamma": 0.10, "theta": 0.20, "vega": 0.15, "liquidity": 0.10, "skew": 0.15}
    else:  # swing
        return {"delta": 0.30, "gamma": 0.05, "theta": 0.25, "vega": 0.15, "liquidity": 0.10, "skew": 0.15}


def _skew_edge(contract: OptionSummary, spot: float) -> float:
    """Basic skew edge estimator. Crypto often has steep put skew.
    We grant a small bonus to calls over puts to offset natural skew premium."""
    if contract.option_type == "call":
        return 0.6  # Natural edge vs overpriced puts
    return 0.4


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
    
    # ── GEX & Market Setup ──────────────────────────────────────────────────
    gex_prof = None
    if full_chain:
        from app.engines.derivatives.gex_engine import calculate_gex_profile
        gex_prof = calculate_gex_profile(full_chain, spot)

    # ATM IV Baseline
    atm_opt = min(candidates, key=lambda o: abs(o.strike - spot)) if candidates else None
    atm_iv = (atm_opt.mark_iv / 100.0) if atm_opt and atm_opt.mark_iv > 5.0 else (atm_opt.mark_iv if atm_opt else 0.0)
    
    timeframe = _get_timeframe(expected_hold_days)
    weights = _get_weights(timeframe)

    # ── per-contract scoring ──────────────────────────────────────────
    for opt in candidates:
        enriched = enrich_with_greeks(opt, spot=spot)

        liq = liquidity_score(enriched, profile, expected_hold_days)
        if not liq.passes_floor:
            scored.append(ScoredStrike(
                option=enriched, liquidity=liq,
                expected_r=0, theta_burn_pct=0,
                premium_at_tp=0, premium_at_sl=0,
                delta_proximity_score=0, gamma_score=0,
                moneyness=0,
                composite=0, breakdown={},
                drop_reason=f"liquidity:{liq.floor_breach_reason}",
            ))
            continue

        # Moneyness calculated strictly from spot
        moneyness = abs(enriched.strike - spot) / spot

        # IVR cap — adapter ships IV as percent; normalise to decimal
        iv = enriched.mark_iv
        if iv > 5.0:
            iv = iv / 100.0
            
        # Proxy IVR: treat raw IV mapped to historical bands.
        # Until CalibrationService IVR is ready, we use absolute IV vs 40% (0.40) as baseline.
        ivr_proxy = min(100.0, (iv / 0.80) * 100) # 80% absolute IV = 100 IVR roughly for BTC
        
        proxy_iv_cap = max(0.20, profile.ivr_pct_naked_max / 100.0 * 1.5)
        if iv > proxy_iv_cap:
            scored.append(ScoredStrike(
                option=enriched, liquidity=liq,
                expected_r=0, theta_burn_pct=0,
                premium_at_tp=0, premium_at_sl=0,
                delta_proximity_score=0, gamma_score=0,
                moneyness=moneyness,
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
                moneyness=moneyness,
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
                moneyness=moneyness,
                composite=0, breakdown={},
                drop_reason=reval.veto_reason,
            ))
            continue

        delta_score = _delta_proximity_score(
            enriched.delta, profile.target_delta, profile.target_delta_tolerance,
        )
        
        # Gamma vs Theta dynamically weighted by timeframe
        gamma_s = _gamma_score(enriched.gamma)
        gamma_weight = weights["gamma"]
        
        theta_burn = abs(enriched.theta) * enriched.dte
        theta_s = max(0.0, 1.0 - reval.theta_burn_pct)  # Reval accurately measures true burn
        theta_weight = weights["theta"]
        
        # Vega/IV
        vega_s = enriched.vega * (1.0 if ivr_proxy < 70 else max(0, 1.3 - ivr_proxy / 100))
        vega_s_norm = min(1.0, vega_s / 0.10) # Normalize
        vega_weight = weights["vega"]
        
        # Liquidity (Vol/OI/Spread)
        # Assuming liq.composite encapsulates spread, OI, and depth
        liq_s = liq.composite
        liq_weight = weights["liquidity"]
        
        # Skew Correction: Penalize strikes where local IV deviates >15% from ATM IV
        skew_s = _skew_edge(enriched, spot)
        if atm_iv > 0:
            iv_deviation = abs(iv - atm_iv) / atm_iv
            if iv_deviation > 0.15:
                skew_s *= max(0.2, 1.0 - (iv_deviation - 0.15) * 2) # steep penalty
        skew_weight = weights["skew"]
        
        # Expected R contribution (bonus)
        r_score = min(1.0, max(0.0, reval.expected_r / 3.0))

        # GEX Influence Bonus/Veto
        gex_score_bonus = 0.0
        if gex_prof:
            total_gex = gex_prof.get("total_gex", 0.0)
            # Boost if near high positive gamma node
            if total_gex > 50_000 and abs(enriched.strike - gex_prof.get("call_wall", spot)) / spot < 0.05:
                gex_score_bonus = 0.15
            # Veto deep negative gamma zones for long holds
            if total_gex < -50_000 and expected_hold_days > 1.0:
                scored.append(ScoredStrike(
                    option=enriched, liquidity=liq,
                    expected_r=reval.expected_r, theta_burn_pct=reval.theta_burn_pct,
                    premium_at_tp=reval.premium_at_tp, premium_at_sl=reval.premium_at_sl,
                    delta_proximity_score=0, gamma_score=0,
                    moneyness=moneyness,
                    composite=0, breakdown={},
                    drop_reason="veto:negative_gex_for_long_hold",
                ))
                continue

        # Core weighted composite
        composite = (
            weights["delta"] * delta_score
            + gamma_weight * gamma_s
            + theta_weight * theta_s
            + vega_weight * vega_s_norm
            + liq_weight * liq_s
            + skew_weight * skew_s
            + 0.10 * r_score # R score remains a universal additive bonus
            + gex_score_bonus
        )

        scored.append(ScoredStrike(
            option=enriched, liquidity=liq,
            expected_r=reval.expected_r, theta_burn_pct=reval.theta_burn_pct,
            premium_at_tp=reval.premium_at_tp, premium_at_sl=reval.premium_at_sl,
            delta_proximity_score=delta_score, gamma_score=gamma_s,
            moneyness=moneyness,
            composite=composite, breakdown={
                "delta": delta_score, "gamma": gamma_s,
                "theta": theta_s, "vega": vega_s_norm,
                "liquidity": liq_s, "skew": skew_s, "expected_r": r_score,
            },
        ))

    # Sort: kept (drop_reason empty) by composite desc, then dropped at the end.
    kept = [s for s in scored if not s.drop_reason]
    dropped = [s for s in scored if s.drop_reason]
    kept.sort(key=lambda s: s.composite, reverse=True)
    return kept + dropped
