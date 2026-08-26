"""Entry pricing and the up-to-three-attempt entry state machine.

Two independent concerns, kept apart:

**Pricing.** Every policy produces a limit deliberately *through* the market so
the order behaves like a market order without being one, then caps the result at
the instrument's upper circuit. The observed bot sent 288.75 against a 167.50
ask; that is a fill-guarantee device, not a price opinion.

**Sequencing.** The state machine's whole purpose is the rule that an
``UNKNOWN`` outcome must be reconciled against the broker before anything is
submitted again. The source bot printed ``Order not found after retries.`` and
carried on, which is exactly how a duplicate position gets opened.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .config import ATMPremiumImbalanceConfig
from .models import (
    EntryAttempt,
    InstrumentRef,
    OrderReport,
    OrderStatus,
    ReconcileState,
    align_to_tick,
    q2,
)


@dataclass(frozen=True)
class PricedEntry:
    """A limit price plus the full story of how it was derived."""

    limit_price: float
    reference_price: float
    reference_kind: str
    raw_price: float
    capped_by_upper_circuit: bool = False
    upper_circuit: Optional[float] = None


class ManualPriceTable:
    """The operator price table the observed bot read as ``strike_prices.txt``.

    Keys look like ``77600CE``. Accepted line forms::

        77600CE 288.75
        77600CE=288.75
        77600CE,288.75

    Blank lines and ``#`` comments are ignored. A malformed line is an error, not
    a skip: silently ignoring one would send an order at a policy fallback price
    the operator never chose.
    """

    def __init__(self, prices: dict[str, float]) -> None:
        self._prices = {str(k).upper().strip(): float(v) for k, v in prices.items()}

    @classmethod
    def parse(cls, text: str) -> "ManualPriceTable":
        out: dict[str, float] = {}
        for lineno, raw in enumerate(text.splitlines(), start=1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            parts = [p for p in line.replace("=", " ").replace(",", " ").split() if p]
            if len(parts) != 2:
                raise ValueError(f"strike price table line {lineno}: expected '<STRIKE><CE|PE> <price>'")
            key, value = parts
            try:
                out[key.upper()] = float(value)
            except ValueError as exc:
                raise ValueError(f"strike price table line {lineno}: '{value}' is not a price") from exc
        return cls(out)

    @staticmethod
    def key_for(strike: float, option_type: str) -> str:
        strike_part = str(int(strike)) if float(strike).is_integer() else str(strike)
        return f"{strike_part}{option_type}".upper()

    def lookup(self, strike: float, option_type: str) -> Optional[float]:
        return self._prices.get(self.key_for(strike, option_type))

    def __len__(self) -> int:
        return len(self._prices)


def price_entry(
    cfg: ATMPremiumImbalanceConfig,
    instrument: InstrumentRef,
    *,
    best_ask: Optional[float],
    last_price: Optional[float] = None,
    first_tick_price: Optional[float] = None,
    manual_table: Optional[ManualPriceTable] = None,
    official_open: Optional[float] = None,
) -> PricedEntry:
    """Compute the entry limit for the configured policy, then cap it.

    Raises when the policy's own reference is unavailable. There is no
    cross-policy fallback: quietly pricing a real buy off a different reference
    than the operator configured is how you get a fill nobody predicted.
    """
    policy = cfg.entry_price_policy

    if policy == "MARKETABLE_ASK":
        if best_ask is None or best_ask <= 0:
            raise ValueError("MARKETABLE_ASK requires a live ask")
        reference, kind = float(best_ask), "best_ask"
        raw = reference + cfg.entry_buffer_points
    elif policy == "PERCENT_THROUGH":
        if best_ask is None or best_ask <= 0:
            raise ValueError("PERCENT_THROUGH requires a live ask")
        reference, kind = float(best_ask), "best_ask"
        raw = reference * (1.0 + cfg.entry_through_pct)
    elif policy == "MANUAL_FILE":
        if manual_table is None:
            raise ValueError("MANUAL_FILE requires a loaded price table")
        manual = manual_table.lookup(instrument.strike, instrument.option_type)
        if manual is None:
            raise ValueError(
                f"no manual price for {ManualPriceTable.key_for(instrument.strike, instrument.option_type)}"
            )
        reference, kind = float(manual), "manual_file"
        raw = reference
    elif policy == "FIRST_TICK_PERCENT":
        # The observed automatic path. 2026-08-20: 102.85 x 1.10 = 113.135 ->
        # printed 113.1. 2026-08-21: 379.0 x 1.10 = 416.90 -> printed 416.9.
        # The bot rounds to ONE decimal, not to the tick grid; one-decimal
        # prices are multiples of 0.10 and so are always tick-valid anyway.
        if cfg.first_tick_source == "OFFICIAL_OPEN":
            # The exchange's own opening price. It still has to be *dated*: a
            # real capture taken after Friday's close reported ohlc.open = 356.70,
            # which was Friday's open rather than the next session's. The caller
            # (PremiumQuoteCache.official_open_for) withholds it until the leg has
            # traded in this session, so reaching here means it is today's.
            if official_open is None or official_open <= 0:
                raise ValueError("first_tick_source=OFFICIAL_OPEN requires the exchange open")
            reference, kind = float(official_open), "official_open"
        else:
            if first_tick_price is None or first_tick_price <= 0:
                raise ValueError("FIRST_TICK_PERCENT requires a first tick price")
            reference, kind = float(first_tick_price), "first_tick"
        raw = round(reference * (1.0 + cfg.entry_through_pct), 1)
    elif policy == "FIRST_TICK_PLUS_BUFFER":
        # The observed automatic path. The 2026-08-20 build prints exactly this
        # arithmetic: First Tick Price 102.85 + Buffer 10.25 -> Order Price 113.1.
        if first_tick_price is None or first_tick_price <= 0:
            raise ValueError("FIRST_TICK_PLUS_BUFFER requires a first tick price")
        reference, kind = float(first_tick_price), "first_tick"
        raw = reference + cfg.entry_buffer_points
    else:
        raise ValueError(f"unknown entry_price_policy: {policy}")

    # FIRST_TICK_PERCENT already carries the source system's one-decimal
    # rounding; q2 preserves it exactly (113.1 -> 113.10).
    raw = q2(raw)
    capped = False
    limit = raw
    uc = instrument.upper_circuit
    if uc is not None and uc > 0 and limit > uc:
        limit, capped = q2(uc), True

    # A buy rounds up: tick alignment must never make a marketable order less
    # likely to fill. Capping at the circuit takes precedence, so re-clamp.
    limit = align_to_tick(limit, instrument.tick_size, mode="up")
    if uc is not None and uc > 0 and limit > uc:
        limit = align_to_tick(q2(uc), instrument.tick_size, mode="down")
        capped = True

    if limit <= 0:
        raise ValueError("computed entry limit is not positive")

    return PricedEntry(
        limit_price=limit,
        reference_price=q2(reference),
        reference_kind=kind,
        raw_price=raw,
        capped_by_upper_circuit=capped,
        upper_circuit=None if uc is None else q2(uc),
    )


class EntryPhase(str, Enum):
    IDLE = "idle"
    AWAITING_SUBMIT = "awaiting_submit"
    AWAITING_STATUS = "awaiting_status"
    NEEDS_RECONCILE = "needs_reconcile"
    FILLED = "filled"
    EXHAUSTED = "exhausted"
    BLOCKED = "blocked"


class ActionKind(str, Enum):
    SUBMIT = "submit"
    AWAIT_STATUS = "await_status"
    RECONCILE = "reconcile"
    DONE_FILLED = "done_filled"
    DONE_EXHAUSTED = "done_exhausted"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class EntryAction:
    kind: ActionKind
    attempt: int = 0
    order_id: Optional[str] = None
    reason: str = ""


@dataclass
class EntryEngine:
    """Drives entry attempts. Pure logic -- the caller performs the I/O.

    Usage: ask :meth:`next_action`, do what it says, report the result back, then
    ask again. The engine never performs a side effect itself, which is what lets
    the duplicate-submission tests be exhaustive.
    """

    cfg: ATMPremiumImbalanceConfig
    phase: EntryPhase = EntryPhase.IDLE
    attempts: list[EntryAttempt] = field(default_factory=list)
    fill_price: Optional[float] = None
    fill_order_id: Optional[str] = None
    filled_quantity: int = 0
    blocked_reason: str = ""
    _pending_order_id: Optional[str] = None

    # ------------------------------------------------------------------ driving

    def next_action(self) -> EntryAction:
        if self.phase is EntryPhase.FILLED:
            return EntryAction(ActionKind.DONE_FILLED, order_id=self.fill_order_id)
        if self.phase is EntryPhase.EXHAUSTED:
            return EntryAction(ActionKind.DONE_EXHAUSTED, reason="max_entry_attempts")
        if self.phase is EntryPhase.BLOCKED:
            return EntryAction(ActionKind.BLOCKED, reason=self.blocked_reason)
        if self.phase is EntryPhase.NEEDS_RECONCILE:
            # The one rule this class exists for.
            return EntryAction(
                ActionKind.RECONCILE,
                attempt=len(self.attempts),
                order_id=self._pending_order_id,
                reason="unknown_order_status",
            )
        if self.phase is EntryPhase.AWAITING_STATUS:
            return EntryAction(
                ActionKind.AWAIT_STATUS, attempt=len(self.attempts), order_id=self._pending_order_id
            )
        if len(self.attempts) >= self.cfg.max_entry_attempts:
            self.phase = EntryPhase.EXHAUSTED
            return EntryAction(ActionKind.DONE_EXHAUSTED, reason="max_entry_attempts")
        return EntryAction(ActionKind.SUBMIT, attempt=len(self.attempts) + 1)

    # ------------------------------------------------------------- transitions

    def record_submit(
        self, priced: PricedEntry, *, order_id: Optional[str], api_time_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record one submission outcome.

        A submit that returns no order id **and** no error is the dangerous case:
        the exchange may still have it. That goes to reconciliation, not retry.
        """
        attempt = EntryAttempt(
            attempt=len(self.attempts) + 1,
            limit_price=priced.limit_price,
            reference_price=priced.reference_price,
            reference_kind=priced.reference_kind,
            capped_by_upper_circuit=priced.capped_by_upper_circuit,
            order_id=order_id,
            status=OrderStatus.PENDING if order_id else OrderStatus.UNKNOWN,
            api_time_ms=api_time_ms,
            reject_reason=error,
        )
        self.attempts.append(attempt)
        self._pending_order_id = order_id
        if order_id:
            self.phase = EntryPhase.AWAITING_STATUS
        elif error:
            # A definite transport-level rejection: nothing reached the exchange.
            self.phase = (
                EntryPhase.EXHAUSTED
                if len(self.attempts) >= self.cfg.max_entry_attempts
                else EntryPhase.IDLE
            )
        else:
            self.phase = EntryPhase.NEEDS_RECONCILE

    def record_status(self, report: Optional[OrderReport]) -> None:
        """Apply a status poll. ``None`` or ``UNKNOWN`` forces reconciliation."""
        if report is None or report.status is OrderStatus.UNKNOWN:
            self.phase = EntryPhase.NEEDS_RECONCILE
            return
        self._stamp(report)
        if report.is_filled:
            self._accept_fill(report)
            return
        if report.status in (OrderStatus.REJECTED, OrderStatus.CANCELLED):
            self.phase = (
                EntryPhase.EXHAUSTED
                if len(self.attempts) >= self.cfg.max_entry_attempts
                else EntryPhase.IDLE
            )
            self._pending_order_id = None
            return
        if report.status is OrderStatus.COMPLETE and not report.is_filled:
            # Broker says complete but gave us no usable average price. Treat as
            # unknown: we must not compute a target from a missing fill.
            self.phase = EntryPhase.NEEDS_RECONCILE
            return
        self.phase = EntryPhase.AWAITING_STATUS

    def record_timeout(self) -> None:
        """An attempt exceeded ``entry_attempt_timeout_ms`` with no resolution."""
        self.phase = EntryPhase.NEEDS_RECONCILE

    def record_reconciliation(
        self, state: ReconcileState, report: Optional[OrderReport] = None
    ) -> None:
        """Resolve the ambiguity a reconciliation was ordered for."""
        if state is ReconcileState.MATCHED and report is not None and report.is_filled:
            self._stamp(report)
            self._accept_fill(report)
            return
        if state is ReconcileState.MATCHED:
            # Broker agrees the order is not filled and not live -> retry is safe.
            self._pending_order_id = None
            self.phase = (
                EntryPhase.EXHAUSTED
                if len(self.attempts) >= self.cfg.max_entry_attempts
                else EntryPhase.IDLE
            )
            return
        if state is ReconcileState.PARTIAL and report is not None and report.filled_quantity > 0:
            self._stamp(report)
            self._accept_fill(report)
            return
        # UNKNOWN or DIVERGED: we still do not know our own position. Blocking is
        # the only safe answer; an operator resolves it.
        self.phase = EntryPhase.BLOCKED
        self.blocked_reason = f"reconciliation_{state.value}"

    # ----------------------------------------------------------------- helpers

    def _stamp(self, report: OrderReport) -> None:
        if not self.attempts:
            return
        last = self.attempts[-1]
        self.attempts[-1] = EntryAttempt(
            attempt=last.attempt,
            limit_price=last.limit_price,
            reference_price=last.reference_price,
            reference_kind=last.reference_kind,
            capped_by_upper_circuit=last.capped_by_upper_circuit,
            order_id=report.order_id or last.order_id,
            status=report.status,
            average_price=report.average_price,
            reject_reason=report.reject_reason,
            api_time_ms=last.api_time_ms,
        )

    def _accept_fill(self, report: OrderReport) -> None:
        self.fill_price = q2(float(report.average_price or 0.0))
        self.fill_order_id = report.order_id
        self.filled_quantity = int(report.filled_quantity)
        self._pending_order_id = None
        self.phase = EntryPhase.FILLED

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def is_terminal(self) -> bool:
        return self.phase in (EntryPhase.FILLED, EntryPhase.EXHAUSTED, EntryPhase.BLOCKED)
