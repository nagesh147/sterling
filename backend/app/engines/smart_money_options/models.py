"""Data models for Smart Money Structure & Multi-X Options strategy."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class StructurePhase(str, Enum):
    CONSOLIDATION = "CONSOLIDATION"
    BREAKOUT_IMMINENT = "BREAKOUT_IMMINENT"
    BREAKOUT_CONFIRMED = "BREAKOUT_CONFIRMED"
    TRENDING = "TRENDING"
    CHOPPY = "CHOPPY"


class SignalAction(str, Enum):
    BUY_CE = "BUY_CE"
    BUY_PE = "BUY_PE"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class Candle:
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    oi: Optional[float] = None


@dataclass(frozen=True)
class LiquidityLevel:
    price: float
    level_type: str  # "BSL" (Buy-side liquidity / resistance) or "SSL" (Sell-side liquidity / support)
    touches: int = 1
    strength: float = 1.0


@dataclass(frozen=True)
class MarketStructure:
    symbol: string if False else str
    timeframe: str
    phase: StructurePhase
    resistance: float
    support: float
    range_pct: float
    swing_high: float
    swing_low: float
    consolidation_bars: int
    is_compressed: bool


@dataclass(frozen=True)
class SmartMoneyMetrics:
    rvol: float
    avg_volume: float
    current_volume: float
    delta_pressure: float  # -1.0 to +1.0 (estimated buying vs selling aggression)
    is_institutional_surge: bool
    footprint_score: float  # 0 to 100


@dataclass(frozen=True)
class MultiXTarget:
    target_1_2x: float
    target_2_3x: float
    target_3_5x: float
    risk_reward_ratio_2x: float = 2.0
    risk_reward_ratio_3x: float = 4.0
    risk_reward_ratio_5x: float = 8.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_1_2x": round(self.target_1_2x, 2),
            "target_2_3x": round(self.target_2_3x, 2),
            "target_3_5x": round(self.target_3_5x, 2),
            "risk_reward_ratio_2x": self.risk_reward_ratio_2x,
            "risk_reward_ratio_3x": self.risk_reward_ratio_3x,
            "risk_reward_ratio_5x": self.risk_reward_ratio_5x,
        }


@dataclass(frozen=True)
class SmartMoneySetup:
    symbol: str
    structure: MarketStructure
    smart_money: SmartMoneyMetrics
    breakout_direction: Optional[str] = None  # "BULLISH" or "BEARISH"
    breakout_level: Optional[float] = None
    is_valid_setup: bool = False
    rejection_reason: Optional[str] = None


@dataclass(frozen=True)
class BreakoutSignal:
    symbol: str
    action: SignalAction
    spot_price: float
    option_type: Optional[str] = None  # "CE" or "PE"
    strike: Optional[float] = None
    expiry: Optional[str] = None
    tradingsymbol: Optional[str] = None
    entry_premium: Optional[float] = None
    stop_loss_premium: Optional[float] = None
    stop_loss_spot: Optional[float] = None
    targets: Optional[MultiXTarget] = None
    holding_period_days: int = 5
    rvol: float = 1.0
    footprint_score: float = 0.0
    structure_phase: StructurePhase = StructurePhase.CHOPPY
    reason: str = ""
    confidence: float = 0.0
    timestamp_ms: int = 0
    status: str = "watching"  # "watching", "armed", "running", "ended"

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action.value,
            "spot_price": round(self.spot_price, 2),
            "option_type": self.option_type,
            "strike": self.strike,
            "expiry": self.expiry,
            "tradingsymbol": self.tradingsymbol,
            "entry_premium": round(self.entry_premium, 2) if self.entry_premium is not None else None,
            "stop_loss_premium": round(self.stop_loss_premium, 2) if self.stop_loss_premium is not None else None,
            "stop_loss_spot": round(self.stop_loss_spot, 2) if self.stop_loss_spot is not None else None,
            "targets": self.targets.as_dict() if self.targets else None,
            "holding_period_days": self.holding_period_days,
            "rvol": round(self.rvol, 2),
            "footprint_score": round(self.footprint_score, 1),
            "structure_phase": self.structure_phase.value,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "timestamp_ms": self.timestamp_ms,
            "status": self.status,
        }
