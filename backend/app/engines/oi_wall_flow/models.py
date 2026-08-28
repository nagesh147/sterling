"""Data the OI Wall Flow engine passes around. No broker, no socket, no clock.

A missing number must reach the board as ``None``. Fabricating ``0`` on a stop
column is a trade-destroying lie, and this codebase has shipped that bug before.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Sequence

OptionType = Literal["CE", "PE"]
Bias = Literal["bullish", "bearish", "neutral"]
FlowKind = Literal[
    "long_buildup",
    "short_covering",
    "short_buildup",
    "long_unwinding",
    "unchanged",
]
SignalState = Literal["watching", "armed", "running", "ended", "error"]


def q2(value: float) -> float:
    """Two decimals. Rupee prices are quoted to paise and compared for equality."""
    return round(float(value) + 0.0, 2)


def align_to_tick(price: float, tick: float) -> float:
    t = float(tick or 0.05) or 0.05
    return q2(int(round(float(price) / t)) * t)


@dataclass(frozen=True)
class ChainRow:
    """One strike on one expiry. OI is lot-count, matching Indian chain UIs."""
    strike: float
    call_oi: int = 0
    call_oi_chg_pct: float = 0.0
    call_ltp: float = 0.0
    call_ltp_chg_pct: float = 0.0
    put_oi: int = 0
    put_oi_chg_pct: float = 0.0
    put_ltp: float = 0.0
    put_ltp_chg_pct: float = 0.0


@dataclass(frozen=True)
class FlowLabel:
    """OI+premium change classified the way Indian F&O desks read a chain."""
    kind: FlowKind
    side: OptionType
    strike: float
    oi: int
    oi_chg_pct: float
    ltp: float
    ltp_chg_pct: float

    @property
    def underlying_bullish(self) -> bool:
        if self.side == "CE":
            return self.kind in ("long_buildup", "short_covering")
        return self.kind in ("short_buildup", "long_unwinding")

    @property
    def underlying_bearish(self) -> bool:
        if self.side == "CE":
            return self.kind in ("short_buildup", "long_unwinding")
        return self.kind in ("long_buildup", "short_covering")


@dataclass(frozen=True)
class Walls:
    put_wall: float
    call_wall: float
    put_wall_oi: int
    call_wall_oi: int


@dataclass(frozen=True)
class ChainMetrics:
    pcr_oi: float
    total_call_oi: int
    total_put_oi: int
    max_pain: float
    walls: Walls
    atm_strike: float
    flows: tuple[FlowLabel, ...]


@dataclass(frozen=True)
class BiasReport:
    bias: Bias
    score: float
    reasons: tuple[str, ...]
    metrics: ChainMetrics

    def as_dict(self) -> dict:
        return {
            "bias": self.bias,
            "score": q2(self.score),
            "reasons": list(self.reasons),
            "pcr_oi": q2(self.metrics.pcr_oi),
            "max_pain": q2(self.metrics.max_pain),
            "put_wall": q2(self.metrics.walls.put_wall),
            "call_wall": q2(self.metrics.walls.call_wall),
            "atm_strike": q2(self.metrics.atm_strike),
        }


@dataclass(frozen=True)
class InstrumentRef:
    instrument_id: str
    tradingsymbol: str
    option_type: OptionType
    strike: float
    expiry: str
    lot_size: int = 1
    tick_size: float = 0.05
    exchange: str = "NFO"


@dataclass(frozen=True)
class TradePlan:
    """What to buy, at what premium, with which stop and target."""
    option_type: OptionType
    strike: float
    entry: float
    stop: float
    target: float
    target_2: Optional[float]
    underlying_invalidation: float
    lot_size: int
    quantity: int
    lots: int
    reason: str
    instrument: Optional[InstrumentRef] = None

    def as_dict(self) -> dict:
        return {
            "option_type": self.option_type,
            "strike": q2(self.strike),
            "entry": self.entry,
            "stop": self.stop,
            "target": self.target,
            "target_2": self.target_2,
            "underlying_invalidation": q2(self.underlying_invalidation),
            "lot_size": self.lot_size,
            "quantity": self.quantity,
            "lots": self.lots,
            "reason": self.reason,
            "tradingsymbol": None if self.instrument is None else self.instrument.tradingsymbol,
        }


@dataclass(frozen=True)
class FlowSignal:
    id: str
    underlying: str
    spot: float
    expiry: str
    bias: BiasReport
    plan: Optional[TradePlan]
    state: SignalState
    at_ms: int
    reason: Optional[str] = None
    days_to_expiry: Optional[int] = None

    def __post_init__(self) -> None:
        if self.state in ("watching", "error") and not self.reason:
            raise ValueError(f"a '{self.state}' signal must carry a reason")

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "state": self.state,
            "at_ms": self.at_ms,
            "underlying": self.underlying,
            "spot": q2(self.spot),
            "expiry": self.expiry,
            "days_to_expiry": self.days_to_expiry,
            "reason": self.reason,
            "bias": self.bias.as_dict(),
            "plan": None if self.plan is None else self.plan.as_dict(),
        }


@dataclass
class PositionState:
    signal_id: str
    option_type: OptionType
    strike: float
    entry: float
    stop: float
    target: float
    quantity: int
    lots: int
    entered_ms: int
    entry_day: str
    underlying_invalidation: float
    tradingsymbol: str = ""
    target_2: Optional[float] = None
    high_water: float = 0.0
    exiting: bool = False

    def __post_init__(self) -> None:
        if self.high_water <= 0:
            self.high_water = self.entry


@dataclass(frozen=True)
class ChainSnapshot:
    """One underlying, one expiry, the whole chain, at one instant."""
    underlying: str
    spot: float
    expiry: str
    rows: Sequence[ChainRow]
    at_ms: int = 0
    days_to_expiry: Optional[int] = None
    lot_size: int = 1
    tick_size: float = 0.05
    exchange: str = "NFO"


@dataclass
class TradeRecord:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    descaled: bool = False
    realised_inr: float = 0.0
    day_realised_inr: float = 0.0
    day: str = ""
    history: list = field(default_factory=list)

    def record(self, pnl_inr: float, day: str, *, descale_after: int = 3,
               rescale_after: int = 2) -> None:
        if day != self.day:
            self.day, self.day_realised_inr = day, 0.0
        self.trades += 1
        self.realised_inr += pnl_inr
        self.day_realised_inr += pnl_inr
        if pnl_inr >= 0:
            self.wins += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.losses += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        if self.consecutive_losses >= descale_after:
            self.descaled = True
        elif self.descaled and self.consecutive_wins >= rescale_after:
            self.descaled = False
        self.history.append({"pnl_inr": q2(pnl_inr), "day": day})
