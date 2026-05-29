"""Preview helper: run the selector across many signals and return a
table-row response for the FE Derivatives Candidates table. Pure shim
over `selector.decide` — exists so the /derivatives/candidates endpoint
has a single import.
"""
from __future__ import annotations

from typing import Optional

from app.engines.derivatives.schemas import (
    DerivativesDecision, MarketContext, SignalContext, StrategyDerivativesProfile,
)
from app.engines.derivatives.selector import decide as _decide
from app.schemas.market import OptionSummary


def preview_one(
    *, signal: SignalContext, market: MarketContext,
    chain: Optional[list[OptionSummary]] = None,
    profile_overrides: Optional[dict[str, StrategyDerivativesProfile]] = None,
) -> DerivativesDecision:
    return _decide(
        signal=signal, market=market, chain=chain,
        profile_overrides=profile_overrides,
    )


def preview_many(
    *, signals: list[SignalContext],
    market_by_underlying: dict[str, MarketContext],
    chain_by_underlying: dict[str, list[OptionSummary]],
    profile_overrides: Optional[dict[str, StrategyDerivativesProfile]] = None,
) -> list[DerivativesDecision]:
    out: list[DerivativesDecision] = []
    for sig in signals:
        market = market_by_underlying.get(sig.underlying.upper())
        if market is None:
            continue
        chain = chain_by_underlying.get(sig.underlying.upper())
        out.append(_decide(
            signal=sig, market=market, chain=chain,
            profile_overrides=profile_overrides,
        ))
    return out
