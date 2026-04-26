from app.schemas.execution import TradeStructure, SizedTrade
from app.schemas.risk import RiskParams


def size_trade(
    structure: TradeStructure,
    risk_params: RiskParams,
) -> SizedTrade:
    capital = risk_params.capital
    max_risk_pct = risk_params.max_position_pct
    max_risk_usd = capital * max_risk_pct

    leg_premium = structure.net_premium  # cost per contract
    if leg_premium <= 0:
        leg_premium = 1.0

    max_loss_per_contract = structure.max_loss if structure.max_loss else leg_premium
    if max_loss_per_contract <= 0:
        max_loss_per_contract = leg_premium

    raw_contracts = int(max_risk_usd / max_loss_per_contract)
    contracts = max(1, min(raw_contracts, risk_params.max_contracts))

    position_value = contracts * leg_premium
    actual_risk = contracts * max_loss_per_contract

    return SizedTrade(
        structure=structure,
        contracts=contracts,
        position_value=round(position_value, 2),
        max_risk_usd=round(actual_risk, 2),
        capital_at_risk_pct=round(actual_risk / capital * 100, 3),
    )
