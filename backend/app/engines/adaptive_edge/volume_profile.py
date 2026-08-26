"""Session volume profile from TBT prints (volume at last price).

Research convention: 70% volume area around VPOC. Not a recovered F-10x formula.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .market_profile import price_bin, value_area_bounds


@dataclass
class VolumeProfileBuilder:
    tick_size: float = 1.0
    value_area_coverage: float = 0.70
    volume: dict[float, float] = field(default_factory=dict)

    def add_print(self, price: float, size: float) -> None:
        if size <= 0:
            return
        level = price_bin(price, self.tick_size)
        self.volume[level] = self.volume.get(level, 0.0) + float(size)

    def snapshot(self) -> tuple[float | None, float | None, float | None]:
        return value_area_bounds(self.volume, coverage=self.value_area_coverage)
