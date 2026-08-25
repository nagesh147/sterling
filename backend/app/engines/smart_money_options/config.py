"""Configuration contract for Smart Money Multi-X Options strategy."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, ClassVar


class StrikeSelectionPolicy(str, Enum):
    ATM = "ATM"
    OTM1 = "OTM1"
    OTM2 = "OTM2"


class ExpiryPolicy(str, Enum):
    NEAREST_MONTHLY = "NEAREST_MONTHLY"
    CURRENT_EXPIRY = "CURRENT_EXPIRY"
    NEXT_EXPIRY = "NEXT_EXPIRY"


class ExecutionMode(str, Enum):
    PAPER = "paper"
    SHADOW = "shadow"
    LIVE = "live"


DEFAULT_UNIVERSE = [
    "ABB",
    "RELIANCE",
    "TATAMOTORS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "NIFTY 50",
    "NIFTY BANK",
]


@dataclass
class SmartMoneyOptionsConfig:
    enabled: bool = False
    execution_mode: str = "paper"
    universe: list[str] = field(default_factory=lambda: list(DEFAULT_UNIVERSE))
    htf_timeframe: str = "1d"  # "1d", "4h", "1h"
    ltf_timeframe: str = "1h"  # "1h", "15m", "5m"
    min_consolidation_bars: int = 8
    max_consolidation_range_pct: float = 8.0
    volume_surge_multiplier: float = 1.8
    min_footprint_score: float = 65.0
    strike_selection: str = "OTM1"
    expiry_policy: str = "NEAREST_MONTHLY"
    target_multiplier_1: float = 2.0
    target_multiplier_2: float = 3.0
    target_multiplier_3: float = 5.0
    stop_loss_pct: float = 35.0
    trailing_stop_activation: float = 2.0
    holding_period_days: int = 5
    max_open_positions: int = 3
    lots_per_trade: int = 1
    data_source: str = "kite"

    VOCABULARIES: ClassVar[dict[str, list[str]]] = {
        "execution_mode": [e.value for e in ExecutionMode],
        "htf_timeframe": ["1d", "4h", "1h"],
        "ltf_timeframe": ["1h", "15m", "5m"],
        "strike_selection": [e.value for e in StrikeSelectionPolicy],
        "expiry_policy": [e.value for e in ExpiryPolicy],
        "data_source": ["kite", "truedata"],
    }

    @classmethod
    def field_names(cls) -> set[str]:
        return {f for f in cls.__dataclass_fields__}

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> "SmartMoneyOptionsConfig":
        if self.execution_mode not in self.VOCABULARIES["execution_mode"]:
            raise ValueError(f"Invalid execution_mode: {self.execution_mode}")
        if self.htf_timeframe not in self.VOCABULARIES["htf_timeframe"]:
            raise ValueError(f"Invalid htf_timeframe: {self.htf_timeframe}")
        if self.ltf_timeframe not in self.VOCABULARIES["ltf_timeframe"]:
            raise ValueError(f"Invalid ltf_timeframe: {self.ltf_timeframe}")
        if self.strike_selection not in self.VOCABULARIES["strike_selection"]:
            raise ValueError(f"Invalid strike_selection: {self.strike_selection}")
        if self.expiry_policy not in self.VOCABULARIES["expiry_policy"]:
            raise ValueError(f"Invalid expiry_policy: {self.expiry_policy}")
        if self.data_source not in self.VOCABULARIES["data_source"]:
            raise ValueError(f"Invalid data_source: {self.data_source}")

        if self.min_consolidation_bars < 3:
            raise ValueError("min_consolidation_bars must be at least 3")
        if self.max_consolidation_range_pct <= 0:
            raise ValueError("max_consolidation_range_pct must be positive")
        if self.volume_surge_multiplier < 1.0:
            raise ValueError("volume_surge_multiplier must be >= 1.0")
        if not (0 <= self.min_footprint_score <= 100):
            raise ValueError("min_footprint_score must be between 0 and 100")
        if not (1.0 < self.target_multiplier_1 < self.target_multiplier_2 < self.target_multiplier_3):
            raise ValueError("Target multipliers must satisfy 1.0 < T1 < T2 < T3")
        if not (0 < self.stop_loss_pct < 100):
            raise ValueError("stop_loss_pct must be between 0 and 100")
        if self.holding_period_days < 1:
            raise ValueError("holding_period_days must be at least 1")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1")
        if self.lots_per_trade < 1:
            raise ValueError("lots_per_trade must be at least 1")
        if not self.universe or not isinstance(self.universe, list):
            raise ValueError("universe must be a non-empty list of symbols")

        return self
