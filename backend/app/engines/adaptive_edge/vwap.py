"""Session VWAP and anchored VWAP from TBT prints.

Research convention, not a recovered F-10x formula. Reset each IST session.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VwapBuilder:
    price_volume: float = 0.0
    volume: float = 0.0

    def add(self, price: float, size: float) -> None:
        if price <= 0 or size <= 0:
            return
        self.price_volume += float(price) * float(size)
        self.volume += float(size)

    def value(self) -> float | None:
        if self.volume <= 0:
            return None
        return self.price_volume / self.volume


def vwap_location(price: float, vwap: float | None, *, tick: float = 1.0) -> str:
    if vwap is None:
        return "unknown"
    if price > vwap + tick / 2:
        return "above_vwap"
    if price < vwap - tick / 2:
        return "below_vwap"
    return "at_vwap"
