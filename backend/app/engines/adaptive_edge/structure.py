"""Session structure: market profile + volume profile + TBT order flow.

Causal: each snapshot only includes events with available_at <= bar available_at.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from .event_boundary import CanonicalMarketEvent
from .market_profile import MarketProfileBuilder
from .opening_structure import OpeningStructureBuilder, or_location
from .order_flow import CLASSIFIER, NOT_CANONICAL_DV, OrderFlowBuilder
from .research_session import session_date_ist
from .volume_nodes import extract_volume_nodes, nearest_level
from .volume_profile import VolumeProfileBuilder
from .vwap import VwapBuilder, vwap_location


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return parsed


@dataclass(frozen=True)
class StructureSnapshot:
    poc: float | None
    vah: float | None
    val: float | None
    vpoc: float | None
    vp_vah: float | None
    vp_val: float | None
    bar_delta: float
    cvd: float
    buy_volume: float
    sell_volume: float
    li: float | None
    spread: float | None
    location: str
    flow_sign: int
    close: float | None = None
    vwap: float | None = None
    avwap_ib: float | None = None
    session_open: float | None = None
    prior_close: float | None = None
    gap: float | None = None
    ib_high: float | None = None
    ib_low: float | None = None
    ib_complete: bool = False
    or_location: str = "unknown"
    vwap_location: str = "unknown"
    hvn: tuple[float, ...] = ()
    lvn: tuple[float, ...] = ()
    nearest_hvn: float | None = None
    nearest_lvn: float | None = None
    poc_migration: str = "unknown"
    classifier: str = CLASSIFIER
    not_canonical_dv: bool = NOT_CANONICAL_DV

    def inside_value(self, price: float) -> bool:
        if self.val is None or self.vah is None:
            return False
        return self.val <= price <= self.vah


def _location(price: float, val: float | None, vah: float | None) -> str:
    if val is None or vah is None:
        return "unknown"
    if price > vah:
        return "above_value"
    if price < val:
        return "below_value"
    return "inside_value"


def _migration(previous: float | None, current: float | None, tick: float) -> str:
    if previous is None or current is None:
        return "unknown"
    if current > previous + tick / 2:
        return "up"
    if current < previous - tick / 2:
        return "down"
    return "flat"


def build_structure_series(
    bar_events: Sequence[CanonicalMarketEvent],
    tick_events: Sequence[CanonicalMarketEvent],
    *,
    tick_size: float = 1.0,
    value_area_coverage: float = 0.70,
) -> list[StructureSnapshot]:
    bars = sorted(bar_events, key=lambda item: (item.available_at, item.record_id))
    ticks = sorted(
        (item for item in tick_events if item.event_type == "tick"),
        key=lambda item: (item.available_at, item.sequence or 0, item.record_id),
    )
    market = MarketProfileBuilder(tick_size=tick_size, value_area_coverage=value_area_coverage)
    volume = VolumeProfileBuilder(tick_size=tick_size, value_area_coverage=value_area_coverage)
    flow = OrderFlowBuilder()
    vwap = VwapBuilder()
    avwap = VwapBuilder()
    opening = OpeningStructureBuilder()
    cursor = 0
    prev_day: str | None = None
    prev_close: float | None = None
    last_poc: float | None = None
    out: list[StructureSnapshot] = []
    for bar in bars:
        day = session_date_ist(bar.available_at)
        if prev_day is not None and day != prev_day:
            market = MarketProfileBuilder(tick_size=tick_size, value_area_coverage=value_area_coverage)
            volume = VolumeProfileBuilder(tick_size=tick_size, value_area_coverage=value_area_coverage)
            flow = OrderFlowBuilder()
            vwap = VwapBuilder()
            avwap = VwapBuilder()
            opening = OpeningStructureBuilder()
            opening.start_day(prior_close=prev_close)
            last_poc = None
        elif prev_day is None:
            opening.start_day(prior_close=None)
        prev_day = day
        cutoff = _parse(bar.available_at)
        while cursor < len(ticks) and _parse(ticks[cursor].available_at) <= cutoff:
            tick = ticks[cursor]
            payload = tick.payload
            ltp = float(payload.get("ltp") or 0.0)
            vol = float(payload.get("volume") or 0.0)
            flow.add_tick(
                ltp=ltp,
                volume=vol,
                bid=payload.get("bid"),
                ask=payload.get("ask"),
                bidqty=payload.get("bidqty"),
                askqty=payload.get("askqty"),
            )
            if ltp > 0 and vol > 0:
                volume.add_print(ltp, vol)
                vwap.add(ltp, vol)
                if opening.ib_complete:
                    avwap.add(ltp, vol)
            cursor += 1
        high = float(bar.payload.get("high") or bar.payload.get("close") or 0.0)
        low = float(bar.payload.get("low") or bar.payload.get("close") or 0.0)
        close = float(bar.payload.get("close") or 0.0)
        open_px = float(bar.payload.get("open") or close)
        if high > 0 and low > 0:
            market.add_bar(high, low)
            opening.add_bar(
                available_at=cutoff, open_px=open_px, high=high, low=low
            )
        delta, buy, sell = flow.roll_bar()
        poc, vah, val = market.snapshot()
        vpoc, vp_vah, vp_val = volume.snapshot()
        hvn, lvn = extract_volume_nodes(volume.volume)
        if delta > 0:
            sign = 1
        elif delta < 0:
            sign = -1
        else:
            sign = 0
        migration = _migration(last_poc, poc, tick_size)
        last_poc = poc
        if close > 0:
            prev_close = close
        out.append(
            StructureSnapshot(
                poc=poc,
                vah=vah,
                val=val,
                vpoc=vpoc,
                vp_vah=vp_vah,
                vp_val=vp_val,
                bar_delta=delta,
                cvd=flow.cvd,
                buy_volume=buy,
                sell_volume=sell,
                li=flow.last_li,
                spread=flow.last_spread,
                location=_location(close, val, vah),
                flow_sign=sign,
                close=close,
                vwap=vwap.value(),
                avwap_ib=avwap.value() if opening.ib_complete else None,
                session_open=opening.session_open,
                prior_close=opening.prior_close,
                gap=opening.gap,
                ib_high=opening.ib_high,
                ib_low=opening.ib_low,
                ib_complete=opening.ib_complete,
                or_location=or_location(close, opening.ib_high, opening.ib_low, complete=opening.ib_complete),
                vwap_location=vwap_location(close, vwap.value(), tick=tick_size),
                hvn=hvn,
                lvn=lvn,
                nearest_hvn=nearest_level(close, hvn),
                nearest_lvn=nearest_level(close, lvn),
                poc_migration=migration,
            )
        )
    return out
