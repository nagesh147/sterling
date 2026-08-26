"""How large a Gamma Move trade is, and how it shrinks after losses.

The de-scaling ladder is the one risk rule the source actually states: after two
or three losing trades in a row, cut the size, and restore it only once the
trades are working again.
"""
from __future__ import annotations

from typing import Optional

from .config import GammaMoveConfig
from .models import TradeRecord


def risk_multiplier(record: TradeRecord, cfg: GammaMoveConfig) -> float:
    """1.0 normally, ``descale_factor`` while a losing streak is live.

    Restoration is driven by consecutive *wins*, so a single winner inside a bad
    run does not put full size back on. The streak counters live on the record,
    which is also what the board shows -- one source, so the number an operator
    reads is the number the sizer used.
    """
    if record.consecutive_losses >= cfg.descale_after_losses:
        if record.consecutive_wins >= cfg.rescale_after_wins:
            return 1.0
        return cfg.descale_factor
    return 1.0


def lots_for(entry: float, stop: float, lot_size: int, cfg: GammaMoveConfig,
             record: Optional[TradeRecord] = None) -> int:
    """Whole lots, sized so the stop costs about ``risk_per_trade_pct``.

    Three ceilings apply and the tightest wins: the risk budget, the premium
    outlay cap, and the operator's explicit lot count in LOTS mode. Returns 0
    when even one lot breaches a cap -- which is a refusal to trade, not a
    rounding artefact, and the caller must surface it as such.
    """
    lot = max(1, int(lot_size or 1))
    if cfg.sizing_mode == "LOTS":
        lots = max(0, int(cfg.lots))
    else:
        risk_per_unit = float(entry) - float(stop)
        if risk_per_unit <= 0:
            return 0
        mult = risk_multiplier(record, cfg) if record is not None else 1.0
        budget = cfg.capital_inr * (cfg.risk_per_trade_pct / 100.0) * mult
        lots = int(budget // (risk_per_unit * lot))

    if lots <= 0:
        return 0
    # Premium outlay ceiling. A bought option's whole premium is at risk if the
    # stop gaps, so this cap is on the outlay, not on the stop distance.
    if entry > 0 and cfg.max_premium_at_risk_inr > 0:
        max_lots = int(cfg.max_premium_at_risk_inr // (entry * lot))
        lots = min(lots, max_lots)
    return max(0, lots)


def sizing_blocker(entry: float, stop: float, lot_size: int, cfg: GammaMoveConfig,
                   record: Optional[TradeRecord] = None) -> Optional[str]:
    """Why the size came out at zero, naming the constraint that actually bound.

    Three ceilings can each produce zero lots, and "size not set" is the wrong
    answer for two of them. A board row that blames the wrong setting sends the
    operator to change a number that was never the problem.
    """
    lot = max(1, int(lot_size or 1))
    if lots_for(entry, stop, lot_size, cfg, record) > 0:
        return None
    if cfg.sizing_mode == "LOTS" and cfg.lots <= 0:
        return "lots not set"
    outlay = float(entry) * lot
    if cfg.max_premium_at_risk_inr > 0 and outlay > cfg.max_premium_at_risk_inr:
        return (f"one lot costs Rs {outlay:,.0f} in premium, above the "
                f"Rs {cfg.max_premium_at_risk_inr:,.0f} outlay cap")
    risk_per_unit = float(entry) - float(stop)
    if risk_per_unit <= 0:
        return "stop is not below entry"
    mult = risk_multiplier(record, cfg) if record is not None else 1.0
    budget = cfg.capital_inr * (cfg.risk_per_trade_pct / 100.0) * mult
    need = risk_per_unit * lot
    detail = " (halved by the losing streak)" if mult < 1.0 else ""
    return (f"one lot risks Rs {need:,.0f} to the stop, above the "
            f"Rs {budget:,.0f} risk budget{detail}")


def at_risk_inr(entry: float, stop: float, quantity: int) -> float:
    return round(max(0.0, (float(entry) - float(stop))) * int(quantity), 2)


def deployed_inr(entry: float, quantity: int) -> float:
    return round(float(entry) * int(quantity), 2)
