"""STRATEGY STUB — options contract health scoring removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. `assess_contract_health`
maps an option summary into a CandidateContract that is always marked unhealthy
(vetoed) so no contract is selected while the strategy is absent.

Implement the new contract-health logic here.
"""
from __future__ import annotations

from app.schemas.execution import CandidateContract


def assess_contract_health(option, min_dte: int = 5) -> CandidateContract:
    """Neutral: pass the option through but veto it (health checks disabled)."""
    def g(name: str, default: float = 0.0) -> float:
        try:
            return float(getattr(option, name, default) or default)
        except (TypeError, ValueError):
            return default

    return CandidateContract(
        instrument_name=str(
            getattr(option, "instrument_name", "")
            or getattr(option, "symbol", "")
        ),
        underlying=str(getattr(option, "underlying", "")),
        strike=g("strike"),
        expiry_date=str(
            getattr(option, "expiry_date", "") or getattr(option, "expiry", "")
        ),
        dte=int(g("dte")),
        option_type=str(getattr(option, "option_type", "")),
        bid=g("bid"),
        ask=g("ask"),
        mark_price=g("mark_price"),
        mid_price=g("mid_price"),
        mark_iv=g("mark_iv"),
        delta=g("delta"),
        open_interest=g("open_interest"),
        volume_24h=g("volume_24h"),
        spread_pct=g("spread_pct"),
        health_score=0.0,
        healthy=False,
        health_veto_reason="strategy removed — health checks disabled",
    )
