"""HVN / LVN from a session volume histogram.

Local extrema vs neighbors; HVN must be at/above mean volume.
Research convention, not a recovered F-10x formula.
"""
from __future__ import annotations


def extract_volume_nodes(volume: dict[float, float]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if len(volume) < 3:
        return (), ()
    prices = sorted(volume)
    mean = sum(volume.values()) / len(volume)
    hvn: list[float] = []
    lvn: list[float] = []
    for index, price in enumerate(prices):
        value = volume[price]
        left = volume[prices[index - 1]] if index else value
        right = volume[prices[index + 1]] if index + 1 < len(prices) else value
        if value >= left and value >= right and value >= mean:
            hvn.append(price)
        if value <= left and value <= right and value < mean:
            lvn.append(price)
    return tuple(hvn), tuple(lvn)


def nearest_level(price: float, levels: tuple[float, ...]) -> float | None:
    if not levels:
        return None
    return min(levels, key=lambda level: abs(level - price))
