"""Turn chain metrics into a directional vote.

Near-ATM flow is weighted more than far OTM lottery prints. Walls and max pain
are confirmation, not the vote themselves -- a wall without flow is just OI.
"""
from __future__ import annotations

from typing import Sequence

from .classify import measure
from .config import OIWallFlowConfig
from .models import Bias, BiasReport, ChainMetrics, ChainRow, FlowLabel


def _near_atm(flow: FlowLabel, atm: float, rows: Sequence[ChainRow], window: int) -> bool:
    ordered = sorted({r.strike for r in rows})
    try:
        i = ordered.index(atm)
    except ValueError:
        return abs(flow.strike - atm) / atm <= 0.03 if atm else False
    lo = max(0, i - window)
    hi = min(len(ordered) - 1, i + window)
    return ordered[lo] <= flow.strike <= ordered[hi]


def score_flow(flow: FlowLabel, *, near: bool) -> tuple[float, str | None]:
    """Signed contribution to the underlying: + bullish, - bearish."""
    if flow.kind == "unchanged":
        return 0.0, None
    weight = 1.5 if near else 0.5
    # Far OTM CE long buildup is a lottery ticket; keep it, but cheaper.
    if flow.side == "CE" and flow.kind == "long_buildup" and not near:
        weight = 0.35
    mag = weight
    if flow.underlying_bullish:
        label = f"{flow.side} {int(flow.strike)} {flow.kind.replace('_', ' ')}"
        return mag, ("bullish: " + label)
    if flow.underlying_bearish:
        label = f"{flow.side} {int(flow.strike)} {flow.kind.replace('_', ' ')}"
        return -mag, ("bearish: " + label)
    return 0.0, None


def decide(spot: float, rows: Sequence[ChainRow], cfg: OIWallFlowConfig,
           metrics: ChainMetrics | None = None) -> BiasReport:
    metrics = metrics or measure(spot, rows, cfg)
    reasons: list[str] = []
    total = 0.0
    for flow in metrics.flows:
        near = _near_atm(flow, metrics.atm_strike, rows, cfg.atm_window_strikes)
        delta, reason = score_flow(flow, near=near)
        total += delta
        if reason and near:
            reasons.append(reason)

    walls = metrics.walls
    if walls.put_wall < spot < walls.call_wall:
        reasons.append(
            f"spot {spot:.2f} sits between put wall {walls.put_wall:.0f} "
            f"and call wall {walls.call_wall:.0f}"
        )
        # Closer to the put wall with room up to the call wall is a long tilt.
        up_room = walls.call_wall - spot
        down_room = spot - walls.put_wall
        if up_room > down_room:
            total += 0.5
            reasons.append("more room to the call wall than to the put wall")
        elif down_room > up_room:
            total -= 0.5
            reasons.append("more room to the put wall than to the call wall")

    if metrics.max_pain > spot:
        total += 0.4
        reasons.append(f"max pain {metrics.max_pain:.0f} is above spot (upward pin)")
    elif metrics.max_pain < spot:
        total -= 0.4
        reasons.append(f"max pain {metrics.max_pain:.0f} is below spot (downward pin)")

    # PCR is not directional on its own. Sub-1 PCR means more calls outstanding,
    # typically a resistance ceiling, not a short. Record it, do not vote it.
    reasons.append(f"PCR OI {metrics.pcr_oi:.2f}")

    if total >= cfg.min_bias_score:
        bias: Bias = "bullish"
    elif total <= -cfg.min_bias_score:
        bias = "bearish"
    else:
        bias = "neutral"
        reasons.append(
            f"score {total:.2f} is inside ±{cfg.min_bias_score} — no trade"
        )
    return BiasReport(bias=bias, score=total, reasons=tuple(reasons), metrics=metrics)
