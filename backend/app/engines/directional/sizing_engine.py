from app.schemas.execution import TradeStructure, SizedTrade
from app.schemas.risk import RiskParams

_LEV_SCALE = {50: 0.15, 25: 0.30, 10: 0.50, 5: 0.75, 3: 0.85, 1: 1.0}


def _nearest_lev_key(leverage: int) -> int:
    keys = sorted(_LEV_SCALE.keys())
    best = keys[0]
    for k in keys:
        if abs(k - leverage) < abs(best - leverage):
            best = k
    return best


def _fractional_kelly(win_rate: float, rr: float) -> float:
    """25% fractional Kelly criterion."""
    if rr <= 0:
        return 0.0
    kelly = (win_rate * rr - (1 - win_rate)) / rr
    return max(0.0, kelly * 0.25)


def size_trade(
    structure: TradeStructure,
    risk_params: RiskParams,
    leverage: int = 1,
) -> SizedTrade:
    capital = risk_params.capital
    win_rate = getattr(risk_params, "win_rate", 0.52)

    rr = structure.risk_reward if structure.risk_reward and structure.risk_reward > 0 else 1.0
    frac_kelly = _fractional_kelly(win_rate, rr)

    # Base per-trade cap by instrument type
    struct_type = structure.structure_type
    if struct_type in ("bear_call_spread", "bull_put_spread", "naked_short"):
        base_cap = 0.010  # option_short: 1%
    elif struct_type == "futures":
        base_cap = 0.020  # futures: 2%
    else:
        base_cap = 0.015  # option_long: 1.5%

    lev_key = _nearest_lev_key(leverage)
    lev_factor = _LEV_SCALE.get(lev_key, 1.0)
    max_per = base_cap * lev_factor

    target_risk_pct = min(
        frac_kelly,
        max_per,
        getattr(risk_params, "max_position_pct", 0.05),
    )
    max_risk_usd = capital * target_risk_pct

    leg_premium = structure.net_premium
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
