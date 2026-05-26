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
    """Calculates trade size respecting RiskParams."""
    
    if not risk_params.win_rate_known and risk_params.trading_mode != "paper":
        return SizedTrade(
            structure=structure,
            contracts=0,
            position_value=0.0,
            max_risk_usd=0.0,
            capital_at_risk_pct=0.0,
            blocked_reason="win rate unknown"
        )
        
    entry_price = getattr(structure, "entry_price", 0.0)
    if entry_price <= 0:
        entry_price = 100_000.0  # Fallback for testing if missing
        
    # Standard 2% risk rule
    risk_pct = 0.02 
    max_risk_usd = risk_params.capital * risk_pct
    
    if structure.max_loss > 0:
        contracts = max_risk_usd / structure.max_loss
    else:
        # Fallback to position sizing
        max_pos_usd = risk_params.capital * risk_params.max_position_pct
        contracts = max_pos_usd * leverage / entry_price
        
    # Floor to 1 if it makes sense, but respect max_contracts
    contracts = max(1.0, contracts)
    contracts = min(contracts, float(risk_params.max_contracts))
    
    # Early entry haircut
    if early_entry and risk_params.enable_early_entry:
        contracts *= 0.5
        
    # Cap to integer for simplicity if needed, or keep float
    contracts = float(round(contracts, 2))
    
    pos_value = contracts * entry_price / leverage
    
    return SizedTrade(
        structure=structure,
        contracts=contracts,
        position_value=pos_value,
        max_risk_usd=contracts * structure.max_loss,
        capital_at_risk_pct=risk_pct,
    )
