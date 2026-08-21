"""The strategy orchestrator -- one implementation for live and for replay.

This class holds no clock, no socket and no broker. It consumes ticks and
returns :class:`Intent` values describing what the caller must do; the caller
reports the result back. That is what makes the golden-trade replay a genuine
test of the live code path rather than a parallel reimplementation of it.

Lifecycle::

    IDLE ──first pair──▶ ARMED ──signal──▶ ENTERING ──fill──▶ IN_POSITION
                                              │                    │
                                              │ exhausted          │ target hit
                                              ▼                    ▼
                                            DONE  ◀──fill──── EXITING
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Literal, Optional

from .config import ATMPremiumImbalanceConfig
from .entry import ActionKind, EntryEngine, ManualPriceTable, PricedEntry, price_entry
from .exit import build_exit_event, exit_order_price, should_exit, target_price
from .models import (
    ExitEvent,
    LegQuote,
    OptionPairRef,
    OptionType,
    OrderReport,
    PositionState,
    PremiumSignal,
    ReconcileState,
    TradeRecord,
    q2,
)
from .quote_cache import PremiumQuoteCache
from .signal import evaluate


class Phase(str, Enum):
    IDLE = "idle"
    ARMED = "armed"
    ENTERING = "entering"
    IN_POSITION = "in_position"
    EXITING = "exiting"
    DONE = "done"
    HALTED = "halted"


IntentKind = Literal[
    "none",
    "submit_entry",
    "poll_entry",
    "reconcile_entry",
    "submit_exit",
    "poll_exit",
    "reconcile_exit",
    "complete",
    "halt",
]


@dataclass(frozen=True)
class Intent:
    """An instruction to the caller. Never a side effect performed here."""

    kind: IntentKind
    instrument_id: str = ""
    option_type: Optional[OptionType] = None
    side: Optional[str] = None
    quantity: int = 0
    limit_price: Optional[float] = None
    order_id: Optional[str] = None
    attempt: int = 0
    reason: str = ""
    priced: Optional[PricedEntry] = None


_NONE = Intent(kind="none")


@dataclass
class ATMPremiumImbalanceStrategy:
    """One armed instance: one option pair, one session, at most one trade."""

    cfg: ATMPremiumImbalanceConfig
    pair: OptionPairRef
    quantity: int
    trade_id: str = "apiTrade"
    manual_table: Optional[ManualPriceTable] = None

    phase: Phase = Phase.IDLE
    trades_taken: int = 0
    halt_reason: str = ""

    cache: PremiumQuoteCache = field(init=False)
    entry: Optional[EntryEngine] = None
    signal: Optional[PremiumSignal] = None
    trade: Optional[TradeRecord] = None
    _exit: Optional[ExitEvent] = None
    _exit_order_id: Optional[str] = None
    _entry_ts_ms: Optional[int] = None
    _last_now_ms: int = 0

    def __post_init__(self) -> None:
        self.cfg.validate()
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.quantity > self.cfg.max_quantity:
            raise ValueError("quantity exceeds max_quantity")
        self.cache = PremiumQuoteCache(self.pair)

    # -------------------------------------------------------------- ingestion

    def on_underlying_tick(self, ltp: float, ts_ms: int = 0) -> None:
        self.cache.on_underlying_tick(ltp, ts_ms)

    def on_option_tick(
        self,
        quote: LegQuote,
        now_ms: int,
        *,
        session_open: bool = True,
        risk_authorized: bool = True,
    ) -> Intent:
        """Apply a tick and return what to do next.

        Foreign instruments are ignored outright: a strategy armed on one strike
        must never act on another strike's tick.
        """
        self._last_now_ms = int(now_ms)
        if self.cache.on_option_tick(quote) is None:
            return _NONE
        if self.phase in (Phase.DONE, Phase.HALTED):
            return _NONE

        if self.phase is Phase.IDLE and self.cache.both_legs_present():
            self.phase = Phase.ARMED

        if self.phase is Phase.ARMED:
            return self._try_entry(now_ms, session_open=session_open, risk_authorized=risk_authorized)
        if self.phase is Phase.ENTERING:
            return self._drive_entry()
        if self.phase is Phase.IN_POSITION:
            return self._monitor(now_ms)
        return _NONE

    # ------------------------------------------------------------------- entry

    def _view(self, now_ms: int):
        return self.cache.view(self.cfg.quote_mode, now_ms, max_skew_ms=self.cfg.max_ce_pe_skew_ms)

    def _try_entry(self, now_ms: int, *, session_open: bool, risk_authorized: bool) -> Intent:
        sig = evaluate(
            self._view(now_ms),
            self.cfg,
            session_open=session_open,
            flat=True,
            risk_authorized=risk_authorized,
            trades_taken=self.trades_taken,
        )
        if not sig.is_actionable:
            return _NONE

        self.signal = sig
        leg = self.pair.leg(sig.option_type)  # type: ignore[arg-type]
        first = self.cache.first_option_tick
        self.trade = TradeRecord(
            trade_id=self.trade_id,
            instrument_id=leg.instrument_id,
            tradingsymbol=leg.tradingsymbol,
            option_type=leg.option_type,
            strike=leg.strike,
            expiry=leg.expiry,
            quantity=self.quantity,
            state=PositionState.ENTRY_PENDING,
            first_tick_price=None if first is None else q2(first[1].ltp),
            signal_difference=sig.difference,
            quote_mode=self.cfg.quote_mode,  # type: ignore[arg-type]
        )
        self.entry = EntryEngine(cfg=self.cfg)
        self.phase = Phase.ENTERING
        return self._drive_entry()

    def _drive_entry(self) -> Intent:
        assert self.entry is not None and self.trade is not None
        action = self.entry.next_action()
        leg = self.pair.leg(self.trade.option_type)

        if action.kind is ActionKind.SUBMIT:
            try:
                priced = self._price_entry(leg)
            except ValueError as exc:
                # Cannot price this attempt (e.g. no ask yet). Stay armed to
                # entering and wait for the next tick rather than guessing.
                return Intent(kind="none", reason=f"entry_unpriceable:{exc}")
            return Intent(
                kind="submit_entry",
                instrument_id=leg.instrument_id,
                option_type=leg.option_type,
                side="BUY",
                quantity=self.quantity,
                limit_price=priced.limit_price,
                attempt=action.attempt,
                priced=priced,
            )
        if action.kind is ActionKind.AWAIT_STATUS:
            return Intent(kind="poll_entry", order_id=action.order_id, attempt=action.attempt,
                          instrument_id=leg.instrument_id)
        if action.kind is ActionKind.RECONCILE:
            return Intent(kind="reconcile_entry", order_id=action.order_id, attempt=action.attempt,
                          instrument_id=leg.instrument_id, reason=action.reason)
        if action.kind is ActionKind.DONE_FILLED:
            return self._on_entry_filled()
        if action.kind is ActionKind.DONE_EXHAUSTED:
            self.phase = Phase.DONE
            self.trade = self.trade.with_state(PositionState.CLOSED)
            return Intent(kind="complete", reason="entry_exhausted")
        self.phase = Phase.HALTED
        self.halt_reason = action.reason
        self.trade = self.trade.with_state(PositionState.RECONCILIATION_REQUIRED)
        return Intent(kind="halt", reason=action.reason)

    def _price_entry(self, leg) -> PricedEntry:
        quote = self.cache.ce if leg.option_type == "CE" else self.cache.pe
        first = self.cache.first_option_tick
        return price_entry(
            self.cfg,
            leg,
            best_ask=None if quote is None else quote.executable_buy_price(),
            last_price=None if quote is None else quote.ltp,
            first_tick_price=None if first is None else first[1].ltp,
            manual_table=self.manual_table,
        )

    def record_entry_submit(
        self, priced: PricedEntry, *, order_id: Optional[str],
        api_time_ms: Optional[float] = None, error: Optional[str] = None,
    ) -> Intent:
        assert self.entry is not None and self.trade is not None
        self.entry.record_submit(priced, order_id=order_id, api_time_ms=api_time_ms, error=error)
        self.trade = replace(
            self.trade,
            entry_order_id=order_id or self.trade.entry_order_id,
            entry_order_price=priced.limit_price,
            entry_attempts=tuple(self.entry.attempts),
        )
        return self._drive_entry()

    def record_entry_status(self, report: Optional[OrderReport]) -> Intent:
        assert self.entry is not None
        self.entry.record_status(report)
        self._sync_attempts()
        return self._drive_entry()

    def record_entry_timeout(self) -> Intent:
        assert self.entry is not None
        self.entry.record_timeout()
        return self._drive_entry()

    def record_entry_reconciliation(
        self, state: ReconcileState, report: Optional[OrderReport] = None
    ) -> Intent:
        assert self.entry is not None
        self.entry.record_reconciliation(state, report)
        self._sync_attempts()
        return self._drive_entry()

    def _sync_attempts(self) -> None:
        if self.entry is not None and self.trade is not None:
            self.trade = replace(self.trade, entry_attempts=tuple(self.entry.attempts))

    def _on_entry_filled(self) -> Intent:
        assert self.entry is not None and self.trade is not None
        fill = self.entry.fill_price
        if fill is None or fill <= 0:
            # Defensive: FILLED without a usable price must never reach the
            # target calculation.
            self.phase = Phase.HALTED
            self.halt_reason = "filled_without_price"
            return Intent(kind="halt", reason=self.halt_reason)
        self._entry_ts_ms = self._last_now_ms
        self.trade = replace(
            self.trade,
            entry_price=fill,
            entry_order_id=self.entry.fill_order_id or self.trade.entry_order_id,
            entry_ts_ms=self._last_now_ms,
            target_price=target_price(fill, self.cfg),
            state=PositionState.OPEN,
            entry_attempts=tuple(self.entry.attempts),
        )
        self.phase = Phase.IN_POSITION
        return Intent(kind="none", reason="entry_filled")

    # -------------------------------------------------------------- monitoring

    def _monitor(self, now_ms: int) -> Intent:
        assert self.trade is not None and self.trade.entry_price is not None
        leg_type = self.trade.option_type
        quote = self.cache.ce if leg_type == "CE" else self.cache.pe
        if quote is None:
            return _NONE
        counter = self.cache.pe if leg_type == "CE" else self.cache.ce
        held = 0.0
        if self._entry_ts_ms:
            held = max(0.0, (now_ms - self._entry_ts_ms) / 1000.0)

        hit, reason = should_exit(
            last_price=float(quote.ltp),
            entry_fill=self.trade.entry_price,
            cfg=self.cfg,
            held_seconds=held,
            counter_leg_price=None if counter is None else float(counter.ltp),
        )
        if not hit:
            return _NONE

        leg = self.pair.leg(leg_type)
        self._exit = build_exit_event(
            trigger_price=float(quote.ltp),
            trigger_ts_ms=now_ms,
            entry_fill=self.trade.entry_price,
            cfg=self.cfg,
            best_bid=quote.executable_sell_price(),
            tick_size=leg.tick_size,
            reason=reason,
        )
        self.trade = replace(self.trade, exit=self._exit, state=PositionState.EXIT_PENDING)
        self.phase = Phase.EXITING
        if self._exit.exit_order_price is None:
            self.phase = Phase.HALTED
            self.halt_reason = "no_exit_price"
            return Intent(kind="halt", reason=self.halt_reason)
        return Intent(
            kind="submit_exit",
            instrument_id=leg.instrument_id,
            option_type=leg_type,
            side="SELL",
            quantity=self.quantity,
            limit_price=self._exit.exit_order_price,
            reason=reason,
        )

    def record_exit_submit(self, *, order_id: Optional[str], error: Optional[str] = None) -> Intent:
        assert self.trade is not None and self._exit is not None
        self._exit_order_id = order_id
        self._exit = replace(self._exit, exit_order_id=order_id)
        self.trade = replace(self.trade, exit=self._exit)
        if not order_id:
            # An unacknowledged exit is as dangerous as an unacknowledged entry:
            # we may be flat or may still be long.
            self.phase = Phase.HALTED
            self.halt_reason = error or "exit_submit_unacknowledged"
            self.trade = self.trade.with_state(PositionState.RECONCILIATION_REQUIRED)
            return Intent(kind="halt", reason=self.halt_reason)
        return Intent(kind="poll_exit", order_id=order_id, instrument_id=self.trade.instrument_id)

    def record_exit_status(self, report: Optional[OrderReport]) -> Intent:
        assert self.trade is not None and self._exit is not None
        if report is None or report.status.value == "unknown":
            return Intent(kind="reconcile_exit", order_id=self._exit_order_id,
                          instrument_id=self.trade.instrument_id, reason="unknown_order_status")
        if not report.is_filled:
            return Intent(kind="poll_exit", order_id=self._exit_order_id,
                          instrument_id=self.trade.instrument_id)
        self._exit = replace(
            self._exit,
            exit_fill_price=q2(float(report.average_price or 0.0)),
            exit_fill_ts_ms=self._last_now_ms,
        )
        self.trade = replace(self.trade, exit=self._exit, state=PositionState.CLOSED)
        self.trades_taken += 1
        self.phase = Phase.DONE
        return Intent(kind="complete", reason=self._exit.reason)

    # ------------------------------------------------------------------ report

    def summary(self) -> dict:
        """The observed ``LIVE SELL`` summary block, as data."""
        t = self.trade
        if t is None:
            return {"phase": self.phase.value, "trades_taken": self.trades_taken}
        return {
            "phase": self.phase.value,
            "state": t.state.value,
            "strike": t.strike,
            "option": t.option_type,
            "quantity": t.quantity,
            "entry": t.entry_price,
            "entry_order_price": t.entry_order_price,
            "target": t.target_price,
            "trigger": None if t.exit is None else t.exit.trigger_price,
            "exit_order_price": None if t.exit is None else t.exit.exit_order_price,
            "exit": t.exit_price,
            "points": t.points,
            "pnl": t.pnl,
            "slippage_vs_target": None if t.exit is None else t.exit.slippage_vs_target,
            "attempts": len(t.entry_attempts),
            "quote_mode": t.quote_mode,
            "halt_reason": self.halt_reason or None,
        }
