"""Routing-gate audit: replay instrument_chooser over surviving configs.

Answers the over-filtering question with a number: for a set of proven
signals, how often does the routing gate veto options? Tallies DEFER/force-
futures reasons across a grid of IVR levels so we can see exactly where
the gate binds.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from app.engines.derivatives.instrument_chooser import choose
from app.engines.derivatives.profiles import DEFAULT_PROFILES
from app.engines.derivatives.schemas import (
    InstrumentBias, MarketContext, SignalContext, StrategyDerivativesProfile,
)
from study.surface_snapshot import SurfaceSnapshot

log = logging.getLogger(__name__)


def replay_routing_gate(
    survivors: list[dict],                # list of survived config metrics dicts
    ivr_range: tuple[int, int, int] = (10, 90, 5),
    spread_pct: float = 0.013,            # measured live median
    snapshot: SurfaceSnapshot | None = None,
) -> pd.DataFrame:
    """Replay instrument_chooser.choose() over IVR sweep per survivor.

    Each survivor config gets tested at IVR levels from ivr_range[0] to
    ivr_range[1] by step ivr_range[2]. Returns a DataFrame with columns:
        config_id, underlying, strategy, tf, direction, ivr_pct, verdict,
        reason, breakdown_json
    """
    low, high, step = ivr_range
    rows: list[dict] = []

    for surv in survivors:
        config_id = surv.get("config_id", "unknown")
        underlying = surv.get("symbol", "UNKNOWN")
        strategy = surv.get("strategy", surv.get("strategy_label", "edge"))
        tf_label = surv.get("tf", "1h")
        direction = surv.get("direction", "long")
        spot = snapshot.spot if snapshot else 50000.0

        profile = DEFAULT_PROFILES.get(strategy, DEFAULT_PROFILES.get("edge/ma_crossover"))
        if profile is None:
            # Build a minimal default
            profile = StrategyDerivativesProfile(
                strategy=strategy, enabled=True,
                instrument_bias=InstrumentBias.AUTO,
            )

        expected_r = surv.get("sharpe", 0.5)

        for ivr in range(low, high + step, step):
            sig = SignalContext(
                strategy=strategy, underlying=underlying,
                entry=spot, direction=direction,
                stop_loss=spot * 0.95 if direction == "long" else spot * 1.05,
                signal_score=50.0, atr=spot * 0.02,
            )
            market = MarketContext(
                spot=spot, underlying=underlying,
                ivr_pct=float(ivr),
                basis_pct=0.0, portfolio_value=100000.0,
            )
            try:
                decision = choose(
                    signal=sig, profile=profile, market=market,
                    best_option_expected_r=expected_r,
                    best_option_spread=spread_pct,
                    best_option_gamma=None,
                    front_month_iv=None,
                    back_month_iv=None,
                    gex_influence_score=50.0,
                )
            except Exception:
                log.exception("Gate audit: choose() failed for %s at IVR=%d", config_id, ivr)
                verdict = "ERROR"
                reason = "exception"
                breakdown = {}
            else:
                verdict = decision.instrument_type
                reason = decision.reason
                breakdown = decision.breakdown

            rows.append({
                "config_id": config_id,
                "underlying": underlying,
                "strategy": strategy,
                "tf": tf_label,
                "direction": direction,
                "ivr_pct": ivr,
                "verdict": verdict,
                "reason": reason,
            })

    return pd.DataFrame(rows)
