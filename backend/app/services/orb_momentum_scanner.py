"""Realtime scanner for the independent ORB Momentum Options strategy."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Sequence
from app.engines.orb_momentum_options import ORBMomentumConfig, UnderlyingBar, generate_signal, select_option, build_trade_signal, OptionCandidate

@dataclass
class ScannerState:
    signals: list[dict]
    trades_today: int = 0
    signals_today: int = 0
    session_date: date | None = None

class ORBMomentumScanner:
    STRATEGY = "ORB_MOMENTUM_OPTIONS"
    def __init__(self, config: ORBMomentumConfig | None = None):
        self.config = config or ORBMomentumConfig()
        self.state = ScannerState([])

    def evaluate(self, symbol: str, bars: Sequence[UnderlyingBar], contracts: Sequence[OptionCandidate]) -> dict | None:
        if not self.config.enabled or not bars: return None
        today = bars[-1].timestamp.date()
        if self.state.session_date != today: self.state = ScannerState([], 0, 0, today)
        if self.state.signals_today >= self.config.max_signals_per_day: return None
        signal = generate_signal(symbol, bars, self.config)
        if signal.direction == "NONE": return None
        option = select_option(bars[-1].close, signal.direction, contracts, self.config)
        if option is None: return None
        if self.state.trades_today >= self.config.max_trades_per_day: return None
        trade = build_trade_signal(signal, option, self.config)
        payload = trade.to_dict()
        payload.update({"status":"SIGNAL", "strategy":self.STRATEGY, "data_source":self.config.data_source})
        self.state.signals.append(payload); self.state.signals_today += 1
        return payload

    def signals(self) -> list[dict]: return list(reversed(self.state.signals))

    def reset(self) -> None: self.state = ScannerState([])
