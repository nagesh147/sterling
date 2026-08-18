"""Provider-neutral live runtime adapter for ORB Momentum Options.

The runtime deliberately consumes canonical bars and option contracts; provider
adapters remain responsible for Kite/TrueData transport and authentication.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from app.engines.orb_momentum_options import UnderlyingBar, OptionCandidate
from app.services.orb_momentum_scanner import ORBMomentumScanner

@dataclass(frozen=True)
class LiveBar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

class ORBMomentumRuntime:
    def __init__(self, scanner: ORBMomentumScanner | None = None):
        self.scanner = scanner or ORBMomentumScanner()
        self._bars: dict[str, list[UnderlyingBar]] = {}

    def on_bar(self, bar: LiveBar, contracts: Iterable[OptionCandidate]) -> dict | None:
        symbol = bar.symbol.upper()
        series = self._bars.setdefault(symbol, [])
        series.append(UnderlyingBar(bar.timestamp, bar.open, bar.high, bar.low, bar.close, bar.volume))
        if len(series) > 300:
            del series[:-300]
        return self.scanner.evaluate(symbol, series, list(contracts))

    def signals(self) -> list[dict]:
        return self.scanner.signals()

    def reset(self) -> None:
        self._bars.clear()
        self.scanner.reset()
