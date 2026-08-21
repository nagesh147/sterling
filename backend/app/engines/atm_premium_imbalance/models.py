"""Domain models for the ATM Premium Imbalance strategy.

Everything here is pure data. No I/O, no broker, no clock -- so the same objects
flow through live trading and deterministic replay, which is the only way the
golden-trade tests can prove the two agree.

Three ideas in this file carry the whole contract:

* :class:`LegQuote` keeps *both* timestamps and a sequence number. The source
  bot's observable behaviour depends on CE and PE being cached independently, so
  throwing away per-leg timing would erase the thing we are trying to reproduce.
* :class:`PremiumPairView` is the single input the signal engine accepts. The
  three quote modes differ only in how a view is built, never in how it is read.
* :class:`TradeRecord` keeps exit trigger, exit order price and exit fill as
  three separate fields, because in the observed trade they were three different
  numbers (149.10 / 148.70 / 156.85).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Literal, Optional

OptionType = Literal["CE", "PE"]
Side = Literal["BUY", "SELL"]
SignalAction = Literal["BUY_CE", "BUY_PE", "NO_TRADE"]

#: How a :class:`PremiumPairView` was produced. Named modes, not booleans, so a
#: research view can never be mistaken for the compatibility one in a log.
QuoteMode = Literal["COMPATIBILITY", "SYNCHRONIZED", "EXECUTABLE"]
QUOTE_MODES: frozenset[str] = frozenset({"COMPATIBILITY", "SYNCHRONIZED", "EXECUTABLE"})


def q2(value: float) -> float:
    """Round to two decimals, the precision every observed price was printed at.

    Applied at boundaries (differences, order prices, points, P&L) so that float
    representation error never leaks into a number we assert on. ``149.2 - 0.5``
    is ``148.69999999999999`` in binary floating point; the broker was sent
    ``148.7``.
    """
    return round(float(value) + 0.0, 2)


def align_to_tick(price: float, tick: float, *, mode: Literal["up", "down"]) -> float:
    """Snap ``price`` to the instrument tick grid, away from the mid.

    Buys round *up* and sells round *down*, so tick alignment can only ever make
    an order more likely to fill -- never less. An exchange rejects an
    unaligned limit outright, and a rejected entry at the open is a missed trade.
    """
    if tick <= 0:
        return q2(price)
    steps = price / tick
    # Nudge before the floor/ceil so a value already on the grid is not pushed a
    # whole tick by representation error (2974.0000000000005 -> 2975).
    eps = 1e-9
    if mode == "up":
        n = -int(-(steps - eps) // 1)
    else:
        n = int((steps + eps) // 1)
    return q2(n * tick)


@dataclass(frozen=True)
class InstrumentRef:
    """A resolved, tradable option contract.

    ``instrument_id`` is whatever opaque key the broker uses -- Upstox spells it
    ``BSE_FO|1141595``. Strategy code never builds one by string formatting; it
    only ever passes through what the instrument resolver returned.
    """

    instrument_id: str
    tradingsymbol: str
    option_type: OptionType
    strike: float
    expiry: str
    lot_size: int = 1
    tick_size: float = 0.05
    upper_circuit: Optional[float] = None
    lower_circuit: Optional[float] = None
    exchange: str = ""

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("instrument_id is required")
        if self.option_type not in ("CE", "PE"):
            raise ValueError("option_type must be CE or PE")
        if self.lot_size <= 0:
            raise ValueError("lot_size must be positive")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")


@dataclass(frozen=True)
class OptionPairRef:
    """The ATM CE/PE pair the strategy watches, plus the underlying it came from."""

    underlying: str
    expiry: str
    strike: float
    ce: InstrumentRef
    pe: InstrumentRef
    underlying_instrument_id: str = ""

    def __post_init__(self) -> None:
        if self.ce.option_type != "CE" or self.pe.option_type != "PE":
            raise ValueError("OptionPairRef requires a CE leg and a PE leg")
        if self.ce.strike != self.pe.strike:
            raise ValueError("CE and PE must share a strike")
        if self.ce.expiry != self.pe.expiry:
            raise ValueError("CE and PE must share an expiry")

    def leg(self, option_type: OptionType) -> InstrumentRef:
        return self.ce if option_type == "CE" else self.pe


@dataclass(frozen=True)
class LegQuote:
    """One leg's latest tick, with its provenance intact.

    ``exchange_ts_ms`` is the exchange's own stamp and is what SYNCHRONIZED mode
    aligns on. ``received_ts_ms`` is our wall clock and is what freshness gates
    use -- an exchange stamp cannot tell you your feed has stalled.
    """

    instrument_id: str
    ltp: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_qty: int = 0
    ask_qty: int = 0
    exchange_ts_ms: int = 0
    received_ts_ms: int = 0
    sequence: int = 0
    source: str = ""

    #: When the trade behind ``ltp`` actually happened, on the exchange clock.
    #: This -- not receipt time -- is what proves an LTP belongs to this session.
    last_trade_ts_ms: Optional[int] = None
    #: Today's official open, and the previous session's close, as the feed
    #: reports them (Kite's ``ohlc.open`` / ``ohlc.close``).
    official_open: Optional[float] = None
    prev_close: Optional[float] = None
    #: Today's cumulative traded volume. Zero before the session's first trade.
    volume_traded: int = 0

    def age_ms(self, now_ms: int) -> int:
        """Age against our own receipt stamp, floored at zero.

        Deliberately *not* a staleness test for content. A tick carrying
        yesterday's last-traded price and received a millisecond ago has an age
        of zero: receipt freshness and content freshness are different
        properties, and conflating them is what let a day-old price be used as a
        session opening price. See :meth:`is_session_origin`.
        """
        return max(0, int(now_ms) - int(self.received_ts_ms))

    def is_session_origin(self, session_open_ms: int) -> Optional[bool]:
        """Did the trade behind this price happen in *this* session?

        Three-valued on purpose:

        * ``True``  -- the trade is stamped at or after the session open.
        * ``False`` -- the trade is stamped before it. Proven stale.
        * ``None``  -- no trade stamp available, so unknowable. Absence of
          evidence is not evidence of freshness, so this must not collapse to
          ``True``; the caller decides how much it needs to know (live refuses,
          paper may proceed).

        Only ``last_trade_ts_ms`` is consulted. ``exchange_ts_ms`` is
        deliberately *not* used as a fallback: it stamps when the exchange sent
        the packet, not when the price traded, and a carried-over last-traded
        price arrives in a packet with a perfectly current exchange timestamp.
        Falling back to it would mask precisely the fault this method exists to
        catch.

        Kite supplies ``last_trade_time`` only in FULL mode, which is why the
        runner subscribes in that mode and why live refuses undatable quotes.
        """
        if self.last_trade_ts_ms is None:
            return None
        return int(self.last_trade_ts_ms) >= int(session_open_ms)

    def executable_buy_price(self) -> Optional[float]:
        """Ask if we have one. ``None`` means 'not executable', not 'use LTP'."""
        return None if self.ask is None or self.ask <= 0 else float(self.ask)

    def executable_sell_price(self) -> Optional[float]:
        return None if self.bid is None or self.bid <= 0 else float(self.bid)


@dataclass(frozen=True)
class PremiumPairView:
    """The resolved CE/PE pair the signal engine reads. One shape for all modes."""

    mode: QuoteMode
    ce_price: float
    pe_price: float
    ce_ts_ms: int = 0
    pe_ts_ms: int = 0
    ce_age_ms: int = 0
    pe_age_ms: int = 0
    ce_sequence: int = 0
    pe_sequence: int = 0
    #: Carried through so the signal gate can date each leg without the cache
    #: needing to know where a session boundary is.
    ce_last_trade_ts_ms: Optional[int] = None
    pe_last_trade_ts_ms: Optional[int] = None
    ce_official_open: Optional[float] = None
    pe_official_open: Optional[float] = None

    def session_origin(self, session_open_ms: int) -> tuple[Optional[bool], Optional[bool]]:
        """``(ce, pe)`` session-origin verdicts, each True / False / None."""
        def verdict(stamp: Optional[int]) -> Optional[bool]:
            # Trade time only -- see LegQuote.is_session_origin for why the
            # exchange packet timestamp is not a substitute.
            return None if stamp is None else int(stamp) >= int(session_open_ms)
        return verdict(self.ce_last_trade_ts_ms), verdict(self.pe_last_trade_ts_ms)

    @property
    def difference(self) -> float:
        """``|PE - CE|`` -- the absolute gap, as the source bot prints it.

        This was originally implemented as signed ``PE - CE``, because in the
        first four recordings the put was always the dearer leg, which makes the
        two indistinguishable. The 2026-08-21 recording is the first with
        ``CE > PE`` -- ``CE 491.15 | PE 337.15 | Difference : 154.00`` -- and it
        prints a *positive* 154.00. So the quantity is absolute (A231/Q2).

        Direction never came from this sign anyway; it comes from
        :attr:`cheaper_leg`. :attr:`signed_difference` is kept for research.
        """
        return q2(abs(self.pe_price - self.ce_price))

    @property
    def signed_difference(self) -> float:
        """``PE - CE``, keeping the sign. Research/diagnostic only.

        Positive means the put is dearer (so the call is bought). Not what the
        source bot printed, so never used for conformance comparison.
        """
        return q2(self.pe_price - self.ce_price)

    @property
    def cheaper_leg(self) -> Optional[OptionType]:
        if self.ce_price < self.pe_price:
            return "CE"
        if self.pe_price < self.ce_price:
            return "PE"
        return None

    @property
    def skew_ms(self) -> int:
        """Absolute gap between the two legs' exchange stamps."""
        return abs(int(self.ce_ts_ms) - int(self.pe_ts_ms))


@dataclass(frozen=True)
class PremiumSignal:
    """A decision. ``NO_TRADE`` carries a reason so a quiet engine is debuggable."""

    action: SignalAction
    view: PremiumPairView
    option_type: Optional[OptionType] = None
    difference: float = 0.0
    reason: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.action in ("BUY_CE", "BUY_PE")


class PositionState(str, Enum):
    FLAT = "flat"
    ENTRY_PENDING = "entry_pending"
    OPEN = "open"
    EXIT_PENDING = "exit_pending"
    CLOSED = "closed"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class OrderStatus(str, Enum):
    """Broker order status, normalised.

    ``UNKNOWN`` is a first-class outcome, not an error to swallow: it is the one
    state in which submitting again can double the position.
    """

    PENDING = "pending"
    OPEN = "open"
    COMPLETE = "complete"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ReconcileState(str, Enum):
    MATCHED = "matched"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    DIVERGED = "diverged"


@dataclass(frozen=True)
class OrderReport:
    """What the broker says about one order."""

    order_id: str
    status: OrderStatus
    transaction: Side
    average_price: Optional[float] = None
    filled_quantity: int = 0
    requested_price: Optional[float] = None
    reject_reason: Optional[str] = None
    exchange_order_id: Optional[str] = None

    @property
    def is_filled(self) -> bool:
        return (
            self.status is OrderStatus.COMPLETE
            and self.filled_quantity > 0
            and self.average_price is not None
            and self.average_price > 0
        )


@dataclass(frozen=True)
class EntryAttempt:
    """One submission in the up-to-three-attempt entry sequence."""

    attempt: int
    limit_price: float
    reference_price: float
    reference_kind: str
    capped_by_upper_circuit: bool = False
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    average_price: Optional[float] = None
    reject_reason: Optional[str] = None
    api_time_ms: Optional[float] = None


@dataclass(frozen=True)
class ExitEvent:
    """Exit trigger, order and fill kept apart.

    They were 149.10 / 148.70 / 156.85 in the observed trade. Collapsing them
    into one "exit price" makes that trade unrepresentable, and hides the fact
    that a target-based exit can fill far away from its target.
    """

    trigger_price: float
    trigger_ts_ms: int
    target_price: float
    reference_bid: Optional[float] = None
    exit_order_price: Optional[float] = None
    exit_order_id: Optional[str] = None
    exit_fill_price: Optional[float] = None
    exit_fill_ts_ms: Optional[int] = None
    reason: str = "target_hit"

    @property
    def slippage_vs_target(self) -> Optional[float]:
        """Fill minus target. Positive means we did better than the target."""
        if self.exit_fill_price is None:
            return None
        return q2(self.exit_fill_price - self.target_price)


@dataclass(frozen=True)
class TradeRecord:
    """The auditable record of one round trip.

    ``entry_price`` is the broker average fill and nothing else. The requested
    limit is kept beside it as ``entry_order_price`` precisely so the two can be
    compared -- in the observed trade they were 133.40 and 288.75.
    """

    trade_id: str
    instrument_id: str
    tradingsymbol: str
    option_type: OptionType
    strike: float
    expiry: str
    quantity: int
    state: PositionState = PositionState.FLAT

    entry_order_id: Optional[str] = None
    entry_order_price: Optional[float] = None
    entry_price: Optional[float] = None
    entry_ts_ms: Optional[int] = None
    entry_attempts: tuple[EntryAttempt, ...] = ()

    target_price: Optional[float] = None
    stop_price: Optional[float] = None

    exit: Optional[ExitEvent] = None

    first_tick_price: Optional[float] = None
    signal_difference: Optional[float] = None
    quote_mode: QuoteMode = "COMPATIBILITY"
    contract_version: str = "A230.4"

    @property
    def exit_price(self) -> Optional[float]:
        return None if self.exit is None else self.exit.exit_fill_price

    @property
    def points(self) -> Optional[float]:
        """``exit_fill - entry_fill``. Fills only -- never a requested price."""
        if self.entry_price is None or self.exit_price is None:
            return None
        return q2(self.exit_price - self.entry_price)

    @property
    def pnl(self) -> Optional[float]:
        """``points x quantity``.

        ``quantity`` is total contracts, not lots: the observed trade printed
        ``PnL : 469.0`` for 23.45 points, which is 23.45 x 20 contracts (one
        SENSEX lot), not 23.45 x 1 lot.
        """
        pts = self.points
        return None if pts is None else q2(pts * self.quantity)

    def with_state(self, state: PositionState) -> "TradeRecord":
        return replace(self, state=state)
