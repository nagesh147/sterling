"""Classify a chain: flow labels, walls, PCR, max pain.

Pure functions. The four flow labels are the Indian F&O desk vocabulary:

    premium up  + OI up   -> long buildup
    premium up  + OI down -> short covering
    premium down + OI up  -> short buildup
    premium down + OI down -> long unwinding

For calls, long buildup / short covering is bullish for the underlying.
For puts, short buildup (put writing) / long unwinding is bullish for the
underlying. The inverse is bearish. Deadband changes are ``unchanged``.
"""
from __future__ import annotations

from typing import Sequence

from .config import OIWallFlowConfig
from .models import ChainMetrics, ChainRow, FlowKind, FlowLabel, Walls, q2


def classify_side(oi_chg_pct: float, ltp_chg_pct: float, cfg: OIWallFlowConfig) -> FlowKind:
    oi_dead = cfg.oi_chg_deadband_pct
    px_dead = cfg.ltp_chg_deadband_pct
    oi_up = oi_chg_pct > oi_dead
    oi_down = oi_chg_pct < -oi_dead
    px_up = ltp_chg_pct > px_dead
    px_down = ltp_chg_pct < -px_dead
    if not (oi_up or oi_down) or not (px_up or px_down):
        return "unchanged"
    if px_up and oi_up:
        return "long_buildup"
    if px_up and oi_down:
        return "short_covering"
    if px_down and oi_up:
        return "short_buildup"
    return "long_unwinding"


def label_row(row: ChainRow, cfg: OIWallFlowConfig) -> tuple[FlowLabel, FlowLabel]:
    call = FlowLabel(
        kind=classify_side(row.call_oi_chg_pct, row.call_ltp_chg_pct, cfg),
        side="CE", strike=row.strike, oi=row.call_oi,
        oi_chg_pct=row.call_oi_chg_pct, ltp=row.call_ltp,
        ltp_chg_pct=row.call_ltp_chg_pct,
    )
    put = FlowLabel(
        kind=classify_side(row.put_oi_chg_pct, row.put_ltp_chg_pct, cfg),
        side="PE", strike=row.strike, oi=row.put_oi,
        oi_chg_pct=row.put_oi_chg_pct, ltp=row.put_ltp,
        ltp_chg_pct=row.put_ltp_chg_pct,
    )
    return call, put


def atm_strike(spot: float, rows: Sequence[ChainRow]) -> float:
    if not rows:
        raise ValueError("chain is empty")
    return min(rows, key=lambda r: abs(r.strike - spot)).strike


def walls_of(rows: Sequence[ChainRow]) -> Walls:
    if not rows:
        raise ValueError("chain is empty")
    put = max(rows, key=lambda r: r.put_oi)
    call = max(rows, key=lambda r: r.call_oi)
    return Walls(put_wall=put.strike, call_wall=call.strike,
                 put_wall_oi=put.put_oi, call_wall_oi=call.call_oi)


def pcr_oi(rows: Sequence[ChainRow]) -> tuple[float, int, int]:
    ce = sum(r.call_oi for r in rows)
    pe = sum(r.put_oi for r in rows)
    if ce <= 0:
        return float("inf") if pe > 0 else 0.0, ce, pe
    return pe / ce, ce, pe


def max_pain(rows: Sequence[ChainRow]) -> float:
    """Strike that minimises combined writer payout if spot pins there.

    Uses lot-count OI. Absolute scale cancels; only relative OI matters.
    """
    if not rows:
        raise ValueError("chain is empty")
    strikes = [r.strike for r in rows]
    best_k, best_pain = strikes[0], float("inf")
    for pin in strikes:
        pain = 0.0
        for r in rows:
            if pin > r.strike:
                pain += r.call_oi * (pin - r.strike)
            elif pin < r.strike:
                pain += r.put_oi * (r.strike - pin)
        if pain < best_pain:
            best_k, best_pain = pin, pain
    return best_k


def measure(spot: float, rows: Sequence[ChainRow], cfg: OIWallFlowConfig) -> ChainMetrics:
    if not rows:
        raise ValueError("chain is empty")
    ordered = tuple(sorted(rows, key=lambda r: r.strike))
    flows: list[FlowLabel] = []
    for row in ordered:
        call, put = label_row(row, cfg)
        flows.append(call)
        flows.append(put)
    ratio, ce, pe = pcr_oi(ordered)
    return ChainMetrics(
        pcr_oi=q2(ratio) if ratio != float("inf") else ratio,
        total_call_oi=ce,
        total_put_oi=pe,
        max_pain=max_pain(ordered),
        walls=walls_of(ordered),
        atm_strike=atm_strike(spot, ordered),
        flows=tuple(flows),
    )
