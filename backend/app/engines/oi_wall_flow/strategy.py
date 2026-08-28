"""The OI Wall Flow state machine.

Pure: a chain snapshot in, a decision out. Never a broker, a socket, or a
clock of its own. Replay and the live runner share this file.

Gate order is the economics:

    chain present -> DTE window -> bias -> strike -> premium/OI/risk caps
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional

from app.domain.models import Signal

from .bias import decide
from .classify import measure
from .config import OIWallFlowConfig
from .exits import realised_inr, should_exit
from .models import ChainSnapshot, FlowSignal, PositionState, TradeRecord
from .selection import make_plan


class Phase(str, Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    IN_POSITION = "in_position"
    HALTED = "halted"


class Intent(str, Enum):
    NONE = "none"
    ENTER = "enter"
    EXIT = "exit"
    HALT = "halt"


@dataclass
class Decision:
    intent: Intent
    signal: Optional[FlowSignal] = None
    reason: str = ""
    exit_position: Optional[PositionState] = None
    exit_reason: str = ""


@dataclass
class SessionState:
    day: str = ""
    phase: Phase = Phase.IDLE
    trades_today: int = 0
    positions: dict = field(default_factory=dict)
    record: TradeRecord = field(default_factory=TradeRecord)
    halt_reason: str = ""

    def roll(self, today: str) -> None:
        if self.day == today:
            return
        self.day = today
        self.trades_today = 0
        self.halt_reason = ""


class OIWallFlowStrategy:
    """Evaluates a chain into a decision. Holds no I/O."""

    def __init__(self, cfg: OIWallFlowConfig, state: Optional[SessionState] = None):
        self.cfg = cfg.validate()
        self.state = state or SessionState()

    def evaluate(self, snap: ChainSnapshot, *, now_ms: int | None = None,
                 today: date | None = None) -> FlowSignal:
        now = now_ms if now_ms is not None else snap.at_ms
        sid = f"{snap.underlying}:{snap.expiry}"
        dte = snap.days_to_expiry
        metrics = measure(snap.spot, snap.rows, self.cfg)
        report = decide(snap.spot, snap.rows, self.cfg, metrics=metrics)
        base = dict(id=sid, underlying=snap.underlying, spot=snap.spot,
                    expiry=snap.expiry, bias=report, at_ms=now,
                    days_to_expiry=dte)

        if dte is not None:
            if self.cfg.avoid_expiry_day and dte == 0:
                return FlowSignal(**base, plan=None, state="watching",
                                  reason="expiry day excluded")
            if dte < self.cfg.expiry_dte_min or dte > self.cfg.expiry_dte_max:
                return FlowSignal(**base, plan=None, state="watching",
                                  reason=(
                                      f"{dte} days to expiry is outside the "
                                      f"{self.cfg.expiry_dte_min}-{self.cfg.expiry_dte_max} "
                                      f"day window"
                                  ))

        if report.bias == "neutral":
            return FlowSignal(**base, plan=None, state="watching",
                              reason=report.reasons[-1] if report.reasons
                              else "bias is neutral")

        plan, why = make_plan(snap.spot, snap.rows, report, self.cfg,
                              lot_size=snap.lot_size or self.cfg.lot_size)
        if plan is None:
            return FlowSignal(**base, plan=None, state="watching",
                              reason=why or "no trade plan")
        return FlowSignal(**base, plan=plan, state="armed", reason=None)

    def admit(self, signal: FlowSignal, today: str) -> Optional[str]:
        self.state.roll(today)
        if self.state.halt_reason:
            return f"halted: {self.state.halt_reason}"
        if not self.cfg.enabled:
            return "strategy disabled"
        if signal.state != "armed":
            return "signal is not armed"
        key = f"{signal.underlying}:{signal.expiry}"
        if key in self.state.positions:
            return "already holding this chain"
        if len(self.state.positions) >= self.cfg.max_concurrent_positions:
            return (f"already holding {len(self.state.positions)} positions, the cap is "
                    f"{self.cfg.max_concurrent_positions}")
        if self.state.trades_today >= self.cfg.max_new_trades_per_day:
            return f"daily trade limit of {self.cfg.max_new_trades_per_day} reached"
        if self.state.record.day == today and \
                self.state.record.day_realised_inr <= -self.cfg.daily_loss_limit_inr:
            return f"daily loss limit of Rs {self.cfg.daily_loss_limit_inr:,.0f} reached"
        return None

    def on_entry(self, signal: FlowSignal, fill: float, now_ms: int,
                 today: str) -> PositionState:
        assert signal.plan is not None
        plan = signal.plan
        key = f"{signal.underlying}:{signal.expiry}"
        pos = PositionState(
            signal_id=signal.id, option_type=plan.option_type, strike=plan.strike,
            entry=fill, stop=plan.stop, target=plan.target, quantity=plan.quantity,
            lots=plan.lots, entered_ms=now_ms, entry_day=today,
            underlying_invalidation=plan.underlying_invalidation,
            tradingsymbol=("" if plan.instrument is None
                           else plan.instrument.tradingsymbol),
            target_2=plan.target_2,
        )
        self.state.positions[key] = pos
        self.state.trades_today += 1
        self.state.phase = Phase.IN_POSITION
        return pos

    def on_price(self, pos: PositionState, premium: float, spot: float) -> Decision:
        reason = should_exit(pos, premium, spot, self.cfg)
        if reason and not pos.exiting:
            pos.exiting = True
            return Decision(intent=Intent.EXIT, exit_position=pos, exit_reason=reason)
        return Decision(intent=Intent.NONE)

    def on_exit(self, pos: PositionState, price: float, today: str,
                key: str) -> float:
        pnl = realised_inr(pos, price)
        self.state.record.record(pnl, today,
                                 descale_after=self.cfg.descale_after_losses,
                                 rescale_after=self.cfg.rescale_after_wins)
        self.state.positions.pop(key, None)
        if not self.state.positions:
            self.state.phase = Phase.SCANNING
        if self.state.record.day_realised_inr <= -self.cfg.daily_loss_limit_inr:
            self.state.halt_reason = "daily loss limit reached"
            self.state.phase = Phase.HALTED
        return pnl

    def generate(self, snap: ChainSnapshot, *, now_ms: int | None = None) -> List[Signal]:
        """StrategyProtocol surface: chain in, domain Signals out."""
        sig = self.evaluate(snap, now_ms=now_ms)
        if sig.state != "armed" or sig.plan is None:
            return []
        plan = sig.plan
        direction = "long" if plan.option_type == "CE" else "short"
        symbol = None
        if plan.instrument is not None:
            symbol = plan.instrument.tradingsymbol
        else:
            symbol = f"{snap.underlying}{snap.expiry.replace('-', '')}{int(plan.strike)}{plan.option_type}"
        strength = "STRONG" if abs(sig.bias.score) >= self.cfg.min_bias_score + 2 else "SIGNAL"
        return [Signal(
            underlying=snap.underlying,
            direction=direction,
            instrument_type="options",
            score=float(abs(sig.bias.score) * 10.0),
            strength=strength,
            stop_loss=plan.stop,
            take_profit=plan.target,
            size_hint=float(plan.lots),
            option_symbol=symbol,
            source="oi_wall_flow",
            timestamp_ms=sig.at_ms or 0,
        )]
