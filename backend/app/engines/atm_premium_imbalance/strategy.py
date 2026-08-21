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
from .exit import (build_exit_event, exit_order_price, optional_target_price,
                   should_exit, target_price, trailing_stop_price)
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
from .protection import (
    ProtectionOrder, ProtectionState, plan_protection, requires_cancel_before_exit,
)
from .quote_cache import PremiumQuoteCache
from .session import session_close_ms_for, session_open_ms_for
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
    "place_protection",
    "cancel_protection",
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
    protection: Optional[ProtectionOrder] = None


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
    #: Realised P&L booked this session, in rupees. Drives the daily loss limit,
    #: which is why it accumulates across trades rather than describing the last
    #: one -- a limit that resets per trade would never stop anything.
    realised_pnl: float = 0.0
    halt_reason: str = ""

    cache: PremiumQuoteCache = field(init=False)
    entry: Optional[EntryEngine] = None
    signal: Optional[PremiumSignal] = None
    trade: Optional[TradeRecord] = None
    _exit: Optional[ExitEvent] = None
    _exit_order_id: Optional[str] = None
    protection: Optional[ProtectionOrder] = None
    _pending_exit_intent: Optional[Intent] = None
    _entry_ts_ms: Optional[int] = None
    #: The most recently closed trade, kept so its result survives a re-arm.
    last_closed_trade: Optional[TradeRecord] = None
    #: Best price seen since entry. Owned here rather than derived in the exit
    #: policy because it is a fact about this position's history, and a trail
    #: computed from the latest price instead would never actually trail.
    _high_water: Optional[float] = None
    _last_now_ms: int = 0
    #: Session open on the exchange clock. Derived from ``cfg.session_start`` for
    #: the day the first tick arrives, so a stale quote can be dated.
    session_open_ms: Optional[int] = None
    #: End of the trading window on the same day. A position must not outlive it.
    session_close_ms: Optional[int] = None

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
        if self.session_open_ms is None:
            self.session_open_ms = session_open_ms_for(now_ms, self.cfg.session_start)
            self.session_close_ms = session_close_ms_for(now_ms, self.cfg.session_end)
        if self.cache.on_option_tick(quote) is None:
            return _NONE
        if self.phase in (Phase.DONE, Phase.HALTED):
            return _NONE

        if self.phase is Phase.IDLE and self.cache.both_legs_present():
            self.phase = Phase.ARMED

        if self.phase is Phase.ARMED:
            # "At the open" is part of what this strategy is. Without a window it
            # would enter on the first valid tick pair after arming, whenever
            # that happened to be.
            window = int(self.cfg.entry_window_seconds)
            if (window > 0 and self.session_open_ms is not None
                    and now_ms - self.session_open_ms > window * 1000):
                return Intent(kind="none", reason="entry_window_closed")
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
            session_open_ms=self.session_open_ms,
            realised_pnl=self.realised_pnl,
        )
        # Record the refusal too, not just the decision. The reason a strategy is
        # doing nothing is the thing an operator actually needs, and dropping it
        # here left both the board and the terminal with nothing to say.
        self.signal = sig
        if not sig.is_actionable:
            return _NONE

        leg = self.pair.leg(sig.option_type)  # type: ignore[arg-type]
        self.trade = TradeRecord(
            trade_id=self.trade_id,
            instrument_id=leg.instrument_id,
            tradingsymbol=leg.tradingsymbol,
            option_type=leg.option_type,
            strike=leg.strike,
            expiry=leg.expiry,
            quantity=self.quantity,
            state=PositionState.ENTRY_PENDING,
            first_tick_price=(lambda v: None if v is None else q2(v))(
                self._pricing_reference(sig.option_type)  # type: ignore[arg-type]
            ),
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
            # The money at risk is only knowable here: it is the limit price
            # times the quantity, and the limit price is decided per attempt.
            # A bought option can lose all of its premium, so the outlay *is*
            # the risk -- there is nothing further to subtract.
            outlay = float(priced.limit_price) * float(self.quantity)
            cap = float(self.cfg.max_premium_at_risk_inr)
            if cap > 0 and outlay > cap:
                self.phase = Phase.HALTED
                self.halt_reason = (
                    f"premium_at_risk_exceeded: ₹{outlay:.2f} over the ₹{cap:.2f} ceiling"
                )
                return Intent(kind="halt", reason=self.halt_reason)
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
        return price_entry(
            self.cfg,
            leg,
            best_ask=None if quote is None else quote.executable_buy_price(),
            last_price=None if quote is None else quote.ltp,
            # The SELECTED leg's first price, which is what the source bot prints
            # as both `Premium` and `First Tick Price` -- but only counting ticks
            # proven to belong to this session when the gate is on, so a
            # carried-over price cannot become an opening price.
            first_tick_price=self._pricing_reference(leg.option_type),
            official_open=self.cache.official_open_for(
                leg.option_type, self.session_open_ms,
                require_proof=self.cfg.execution_mode == "live",
            ),
            manual_table=self.manual_table,
        )

    def _pricing_reference(self, option_type) -> Optional[float]:
        """The first price this leg may be priced from.

        Mirrors the signal gate exactly: a proven previous-session price is never
        used; an undatable one is used only outside live mode.
        """
        if self.cfg.require_session_origin_tick and self.session_open_ms is not None:
            return self.cache.first_session_price_for(
                option_type, self.session_open_ms,
                require_proof=self.cfg.execution_mode == "live",
            )
        return self.cache.first_price_for(option_type)

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
        # The fill itself is the first high-water mark: at entry there is no gain
        # yet, so a trail must not already be in front of the price.
        self._high_water = float(fill)
        self.trade = replace(
            self.trade,
            entry_price=fill,
            entry_order_id=self.entry.fill_order_id or self.trade.entry_order_id,
            entry_ts_ms=self._last_now_ms,
            target_price=optional_target_price(fill, self.cfg),
            state=PositionState.OPEN,
            entry_attempts=tuple(self.entry.attempts),
        )
        self.phase = Phase.IN_POSITION

        # Park a protective exit at the exchange before anything else happens,
        # so a crash from here on does not leave the position unwatched.
        leg = self.pair.leg(self.trade.option_type)
        planned = plan_protection(
            self.cfg,
            instrument_id=leg.instrument_id,
            option_type=leg.option_type,
            quantity=self.quantity,
            entry_fill=fill,
            target_price=self.trade.target_price or target_price(fill, self.cfg),
            tick_size=leg.tick_size,
        )
        if planned is not None:
            self.protection = planned
            return Intent(
                kind="place_protection",
                instrument_id=leg.instrument_id,
                option_type=leg.option_type,
                side="SELL",
                quantity=self.quantity,
                limit_price=planned.limit_price,
                protection=planned,
                reason="protect_open_position",
            )
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

        # Ratchet the high-water mark before asking, so the trail can only ever
        # move up. The mark is taken from the traded price, not the bid: a bid
        # that momentarily widens is not a price the position achieved.
        price = float(quote.ltp)
        self._high_water = price if self._high_water is None else max(self._high_water, price)

        # Session end wins over every policy. A target that has not been reached
        # by the close is not going to be, and holding a bought option past the
        # session -- to expiry, on expiry day -- risks the whole premium.
        if (self.cfg.close_at_session_end and self.session_close_ms is not None
                and now_ms >= self.session_close_ms):
            hit, reason = True, "session_end"
        else:
            hit, reason = should_exit(
                last_price=price,
                entry_fill=self.trade.entry_price,
                cfg=self.cfg,
                held_seconds=held,
                counter_leg_price=None if counter is None else float(counter.ltp),
                high_water=self._high_water,
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
        exit_intent = Intent(
            kind="submit_exit",
            instrument_id=leg.instrument_id,
            option_type=leg_type,
            side="SELL",
            quantity=self.quantity,
            limit_price=self._exit.exit_order_price,
            reason=reason,
        )
        if requires_cancel_before_exit(self.protection):
            # Cancel first, then exit. Two live sells on one long position is a
            # short position waiting to happen.
            self.protection = replace(self.protection, state=ProtectionState.CANCEL_PENDING)
            self._pending_exit_intent = exit_intent
            return Intent(
                kind="cancel_protection",
                instrument_id=leg.instrument_id,
                order_id=self.protection.order_id,
                reason="cancel_before_exit",
            )
        return exit_intent

    def record_protection_submit(
        self, *, order_id: Optional[str], error: Optional[str] = None
    ) -> Intent:
        """Record the protective order's acknowledgement.

        A protective order we cannot confirm is worse than none, because the
        exit path would then have to guess whether a resting sell exists. So an
        unacknowledged protection halts rather than proceeding unprotected while
        believing itself protected.
        """
        if self.protection is None:
            return _NONE
        if not order_id:
            self.protection = replace(self.protection, state=ProtectionState.FAILED)
            self.phase = Phase.HALTED
            self.halt_reason = error or "protection_unacknowledged"
            if self.trade is not None:
                self.trade = self.trade.with_state(PositionState.RECONCILIATION_REQUIRED)
            return Intent(kind="halt", reason=self.halt_reason)
        self.protection = replace(self.protection, order_id=order_id, state=ProtectionState.ACTIVE)
        return Intent(kind="none", reason="protection_active")

    def record_protection_filled(self, fill_price: float) -> Intent:
        """The protective order filled -- the exchange closed us out.

        This is a legitimate exit, not an error: it is exactly what protection
        is for. The trade closes on the protective fill.
        """
        if self.trade is None or self.protection is None:
            return _NONE
        self.protection = replace(self.protection, state=ProtectionState.FILLED)
        ev = self._exit or build_exit_event(
            trigger_price=fill_price, trigger_ts_ms=self._last_now_ms,
            entry_fill=self.trade.entry_price or fill_price, cfg=self.cfg,
            best_bid=None, reason="protection_filled",
        )
        ev = replace(ev, exit_fill_price=q2(fill_price), exit_fill_ts_ms=self._last_now_ms,
                     exit_order_id=self.protection.order_id, reason="protection_filled")
        self._exit = ev
        self.trade = replace(self.trade, exit=ev, state=PositionState.CLOSED)
        self.trades_taken += 1
        self.realised_pnl += float(self.trade.pnl or 0.0)
        self.phase = self._settle_after_close()
        return Intent(kind="complete", reason="protection_filled")

    def record_protection_cancelled(self, *, ok: bool) -> Intent:
        """Resolve the cancel we asked for before sending our own exit."""
        if self.protection is None:
            return _NONE
        if not ok:
            # A live resting sell plus a second sell turns one long into a short.
            self.phase = Phase.HALTED
            self.halt_reason = "protection_cancel_failed"
            if self.trade is not None:
                self.trade = self.trade.with_state(PositionState.RECONCILIATION_REQUIRED)
            return Intent(kind="halt", reason=self.halt_reason)
        self.protection = replace(self.protection, state=ProtectionState.CANCELLED)
        pending, self._pending_exit_intent = self._pending_exit_intent, None
        return pending or _NONE

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
        self.realised_pnl += float(self.trade.pnl or 0.0)
        reason = self._exit.reason
        self.phase = self._settle_after_close()
        return Intent(kind="complete", reason=reason)

    # ------------------------------------------------------------------ report

    def adopt_open_position(self, *, option_type: OptionType, entry_fill: float,
                            quantity: int, now_ms: int) -> None:
        """Take charge of a position that already exists at the broker.

        After a restart the strategy's state is gone but the position is not.
        Adopting it puts the stop and the target back to work; the alternative is
        a bought option with nothing watching it.

        Deliberately incomplete, and honest about it. The high-water mark is
        seeded from the entry fill because the peak since entry is unknowable
        after the fact -- so a trail resumes from scratch rather than from an
        invented peak, which would place the stop somewhere the price never
        actually reached. ``first_tick_price`` stays None for the same reason:
        the reference this position was priced from is gone.
        """
        if quantity <= 0 or entry_fill <= 0:
            raise ValueError("adopting a position needs a positive size and fill")
        leg = self.pair.leg(option_type)
        self.quantity = int(quantity)
        self.trade = TradeRecord(
            trade_id=self.trade_id,
            instrument_id=leg.instrument_id,
            tradingsymbol=leg.tradingsymbol,
            option_type=leg.option_type,
            strike=leg.strike,
            expiry=leg.expiry,
            quantity=int(quantity),
            state=PositionState.OPEN,
            entry_price=q2(entry_fill),
            entry_order_price=None,
            first_tick_price=None,
            target_price=optional_target_price(entry_fill, self.cfg),
            quote_mode=self.cfg.quote_mode,  # type: ignore[arg-type]
            adopted=True,
        )
        self._entry_ts_ms = int(now_ms)
        self._high_water = float(entry_fill)
        self._last_now_ms = int(now_ms)
        self.phase = Phase.IN_POSITION

    def _settle_after_close(self) -> Phase:
        """Where the strategy goes once a trade is closed.

        ``max_trades_per_session`` implied more than one trade was possible, but
        every close went to DONE regardless, so a limit above 1 could never take
        effect -- the gate existed and the phase machine forbade reaching it.

        Re-arming resets only the per-trade state. ``trades_taken`` and
        ``realised_pnl`` deliberately survive, because the trade limit and the
        daily loss limit are session facts and a reset would make both
        unenforceable.
        """
        # Keep the closed trade reachable. Re-arming clears `trade` for the next
        # one, and anything reporting the result -- the log line, the board --
        # runs after that, so without this a re-armed session silently loses the
        # outcome of the trade it just finished.
        self.last_closed_trade = self.trade
        if self.trades_taken >= self.cfg.max_trades_per_session:
            return Phase.DONE
        self.trade = None
        self.signal = None
        self.entry = None
        self.protection = None
        self._exit = None
        self._exit_order_id = None
        self._entry_ts_ms = None
        self._high_water = None
        return Phase.ARMED if self.cache.both_legs_present() else Phase.IDLE

    @property
    def live_stop(self) -> Optional[float]:
        """The stop price in force right now, or ``None`` if there is no stop."""
        if self.trade is None or self.trade.entry_price is None:
            return None
        peak = self._high_water if self._high_water is not None else self.trade.entry_price
        return trailing_stop_price(self.trade.entry_price, peak, self.cfg)

    def summary(self) -> dict:
        """The observed ``LIVE SELL`` summary block, as data."""
        t = self.trade
        if t is None:
            return {"phase": self.phase.value, "trades_taken": self.trades_taken,
                    "realised_pnl": self.realised_pnl}
        return {
            "phase": self.phase.value,
            "state": t.state.value,
            "strike": t.strike,
            "option": t.option_type,
            "quantity": t.quantity,
            "entry": t.entry_price,
            "entry_order_price": t.entry_order_price,
            # The reference the order price was derived from. Exposed because
            # this is the field the stale-tick fault lived in: an order price
            # alone cannot show whether it came from a session price.
            "first_tick_price": t.first_tick_price,
            "target": t.target_price,
            # Where the stop sits *now*. The operator watching a trailing stop
            # needs the current level, not the one it started at.
            "stop": self.live_stop,
            "high_water": self._high_water,
            "trigger": None if t.exit is None else t.exit.trigger_price,
            "exit_order_price": None if t.exit is None else t.exit.exit_order_price,
            "exit": t.exit_price,
            "points": t.points,
            "pnl": t.pnl,
            "slippage_vs_target": None if t.exit is None else t.exit.slippage_vs_target,
            "attempts": len(t.entry_attempts),
            "realised_pnl": self.realised_pnl,
            "quote_mode": t.quote_mode,
            "protection": None if self.protection is None else {
                "kind": self.protection.kind, "state": self.protection.state.value,
                "limit_price": self.protection.limit_price,
                "order_id": self.protection.order_id,
            },
            "halt_reason": self.halt_reason or None,
        }
