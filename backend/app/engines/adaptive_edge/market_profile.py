"""Session market profile (TPO / POC / value area) from 1-minute bars.

Research convention: 70% value area around POC. Not a recovered F-10x formula.
Only bars with available_at <= cutoff are used.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def price_bin(price: float, tick_size: float) -> float:
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")
    return round(round(float(price) / tick_size) * tick_size, 10)


def value_area_bounds(
    counts: dict[float, float], *, coverage: float
) -> tuple[float | None, float | None, float | None]:
    if not counts:
        return None, None, None
    poc = max(counts, key=lambda px: (counts[px], -px))
    total = sum(counts.values())
    if total <= 0:
        return poc, poc, poc
    target = total * coverage
    acc = counts[poc]
    low = high = poc
    prices = sorted(counts)
    lo_i = prices.index(low)
    hi_i = prices.index(high)
    while acc < target and (lo_i > 0 or hi_i < len(prices) - 1):
        below = counts[prices[lo_i - 1]] if lo_i > 0 else -1.0
        above = counts[prices[hi_i + 1]] if hi_i < len(prices) - 1 else -1.0
        if above > below:
            hi_i += 1
            acc += counts[prices[hi_i]]
            high = prices[hi_i]
        elif below > above:
            lo_i -= 1
            acc += counts[prices[lo_i]]
            low = prices[lo_i]
        elif hi_i < len(prices) - 1:
            hi_i += 1
            acc += counts[prices[hi_i]]
            high = prices[hi_i]
        else:
            lo_i -= 1
            acc += counts[prices[lo_i]]
            low = prices[lo_i]
    return poc, high, low


@dataclass
class MarketProfileBuilder:
    tick_size: float = 1.0
    value_area_coverage: float = 0.70
    tpo: dict[float, float] = field(default_factory=dict)

    def add_bar(self, high: float, low: float) -> None:
        top = price_bin(high, self.tick_size)
        bot = price_bin(low, self.tick_size)
        if bot > top:
            bot, top = top, bot
        level = bot
        while level <= top + (self.tick_size / 2):
            self.tpo[level] = self.tpo.get(level, 0.0) + 1.0
            level = round(level + self.tick_size, 10)

    def snapshot(self) -> tuple[float | None, float | None, float | None]:
        return value_area_bounds(self.tpo, coverage=self.value_area_coverage)
