"""
Black-Scholes Greeks for options positions. Portfolio delta/vega/theta budget.
"""
import numpy as np
from dataclasses import dataclass
from scipy.stats import norm


@dataclass
class GreeksBudget:
    max_net_delta: float = 0.30
    max_net_vega:  float = 0.15
    max_net_theta: float = -0.02


@dataclass
class PositionGreeks:
    delta: float
    vega:  float
    theta: float


def bsm_greeks(
    S: float, K: float, T: float, r: float, sigma: float, is_call: bool
) -> PositionGreeks:
    """T in years, sigma as decimal (0.80 = 80% IV)."""
    if T <= 0 or sigma <= 0:
        return PositionGreeks(0.0, 0.0, 0.0)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    delta = norm.cdf(d1) if is_call else -norm.cdf(-d1)
    vega  = S * norm.pdf(d1) * np.sqrt(T) / 100
    theta = (
        -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
        - r * K * np.exp(-r * T) * (norm.cdf(d2) if is_call else -norm.cdf(-d2))
    ) / 365
    return PositionGreeks(float(delta), float(vega), float(theta))


class GreeksBudgetChecker:
    def __init__(self, budget: GreeksBudget, portfolio_value: float):
        self.budget = budget
        self.pv = portfolio_value

    def check(
        self,
        open_positions: list,
        new_position_greeks: PositionGreeks,
        new_position_notional: float,
    ) -> tuple:
        """Returns (allowed: bool, reason: str)."""
        net_delta = 0.0
        net_vega  = 0.0
        net_theta = 0.0
        for p in open_positions:
            g = getattr(p, 'greeks', None)
            n = getattr(p, 'notional', 0.0) or 0.0
            if g:
                net_delta += g.delta * n
                net_vega  += g.vega  * n
                net_theta += g.theta * n

        net_delta += new_position_greeks.delta * new_position_notional
        net_vega  += new_position_greeks.vega  * new_position_notional
        net_theta += new_position_greeks.theta * new_position_notional

        if self.pv <= 0:
            return True, "ok"

        if abs(net_delta / self.pv) > self.budget.max_net_delta:
            return False, f"delta_breach:{net_delta/self.pv:.2%}>{self.budget.max_net_delta:.0%}"
        if abs(net_vega / self.pv) > self.budget.max_net_vega:
            return False, f"vega_breach:{net_vega/self.pv:.2%}>{self.budget.max_net_vega:.0%}"
        if net_theta / self.pv < self.budget.max_net_theta:
            return False, f"theta_breach:{net_theta/self.pv:.2%}<{self.budget.max_net_theta:.0%}"

        return True, "ok"
