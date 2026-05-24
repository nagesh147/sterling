"""STRATEGY STUB — position sizing (Kelly / risk) removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. `size_trade` fails closed:
it returns a SizedTrade with zero contracts and a `blocked_reason`, so no orders
are ever sized while the strategy is absent.

Implement the new sizing logic here.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.schemas.execution import TradeStructure, SizedTrade
from app.schemas.risk import RiskParams
from app.schemas.directional import MacroRegime


def size_trade(
    structure: TradeStructure,
    risk_params: RiskParams,
    leverage: int = 1,
    *,
    signal_score: float = -1.0,
    early_entry: bool = False,
    min_rr: float = 0.0,
    atr_percentile: float = 50.0,
    consecutive_losses: int = 0,
    macro_regime: Optional[MacroRegime] = None,
    underlying: Optional[str] = None,
    open_position_assets: Optional[List[str]] = None,
    correlation_matrix: Optional[Dict[Tuple[str, str], float]] = None,
    open_interest: Optional[float] = None,
) -> SizedTrade:
    """Fail closed: zero size while no strategy is loaded."""
    return SizedTrade(
        structure=structure,
        contracts=0,
        position_value=0.0,
        max_risk_usd=0.0,
        capital_at_risk_pct=0.0,
        blocked_reason="strategy removed — sizing disabled",
    )
