"""Tick-driven session runner for ATM Premium Imbalance.

Deliberately **not** a polling loop. The strategy's whole premise is entering on
the first usable tick after the open -- the recordings show entry decided 1 ms
after the first tick -- and a 1-second poll cannot express that. So this hangs
off the same tick fan-out the Kite exit monitor uses
(:func:`app.services.exchanges.kite.ticker_manager._make_broadcaster`), which is
already wired to run "regardless of whether any UI is listening".

Responsibilities:

* arm once per session: resolve the ATM pair, subscribe both legs
* translate the engine's :class:`Intent` values into broker calls
* enforce one trade per session, market hours, and the per-user lock

The strategy object itself stays pure. Everything that can fail -- network,
broker, clock -- lives here, which is why the golden replays can drive the same
engine with no broker at all.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from app.core.logging import get_logger
from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, ATMPremiumImbalanceStrategy, LegQuote, OptionPairRef,
    OrderReport, OrderStatus,
)

log = get_logger(__name__)
_IST = timezone(timedelta(hours=5, minutes=30))

#: One session object per user. Cleared when the session date rolls over.
_sessions: dict[str, "Session"] = {}
_locks: dict[str, asyncio.Lock] = {}


def _lock_for(user_id: str) -> asyncio.Lock:
    lock = _locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[user_id] = lock
    return lock


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _is_market_open() -> bool:
    """Verified market hours. Fails closed when the calendar is unavailable."""
    try:
        from app.services.navigator.calendar import is_market_open_at
        return bool(is_market_open_at(_now_ms()))
    except Exception:
        return False


@dataclass
class Session:
    """One armed trading session for one user."""

    user_id: str
    cfg: ATMPremiumImbalanceConfig
    pair: OptionPairRef
    strategy: ATMPremiumImbalanceStrategy
    session_date: date
    ce_token: int
    pe_token: int
    finished: bool = False
    released: bool = False
    #: True for a replayed session. Kept on the session rather than in a separate
    #: registry so the board renders it through exactly the same path -- but it
    #: is what stops real ticks driving a simulation, and a simulation from ever
    #: reaching a real broker.
    sim: bool = False
    #: Virtual "now" in epoch ms, set by the simulator before each step. None
    #: means the wall clock, which is what every live session uses.
    clock_ms: Optional[int] = None
    #: Last terminal line written per topic, so a condition that stays true for
    #: thousands of ticks is reported once rather than thousands of times.
    logged: dict = field(default_factory=dict)

    def now_ms(self) -> int:
        """This session's clock: virtual while simulating, wall clock otherwise."""
        return int(self.clock_ms) if self.clock_ms is not None else _now_ms()

    def today(self) -> date:
        """The session's own calendar date, so a simulation is not "yesterday"."""
        return datetime.fromtimestamp(self.now_ms() / 1000, tz=_IST).date()

    def token_leg(self, token: int) -> Optional[str]:
        if token == self.ce_token:
            return "CE"
        if token == self.pe_token:
            return "PE"
        return None


def _epoch_ms(value: Any) -> Optional[int]:
    """Normalise a Kite timestamp to epoch milliseconds.

    Kite's binary ticker emits ``last_trade_time`` and ``exchange_timestamp`` as
    u32 **epoch seconds** (see ``exchanges/kite/ticker.parse_packet``), while the
    REST/pykiteconnect paths hand back ``datetime``. Both are accepted, and a
    value already in milliseconds is passed through: epoch seconds are ~1.8e9 and
    epoch milliseconds ~1.8e12, so 1e11 separates them unambiguously for any date
    this software will see.

    Returning ``None`` for a missing or zero stamp is deliberate. The previous
    implementation substituted the receipt time here, which silently destroyed the
    only evidence that could date a price -- and so let a previous session's
    last-traded price be used as an opening price.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return None
    if raw <= 0:
        return None
    return int(raw if raw > 1e11 else raw * 1000)


def _tick_to_quote(instrument_id: str, tick: dict, now_ms: int) -> LegQuote:
    """Normalise a Kite tick, preserving everything needed to date the price.

    Depth is read from the L1 book rather than synthesised from LTP: the entry
    prices off the ask and the exit off the bid, and inventing them from the last
    trade would silently change both.
    """
    depth = (tick.get("depth") or {}) if isinstance(tick.get("depth"), dict) else {}
    buy = (depth.get("buy") or [{}])[0] if depth.get("buy") else {}
    sell = (depth.get("sell") or [{}])[0] if depth.get("sell") else {}
    ohlc = tick.get("ohlc") if isinstance(tick.get("ohlc"), dict) else {}

    last_trade_ms = _epoch_ms(tick.get("last_trade_time"))
    exchange_ms = _epoch_ms(tick.get("exchange_timestamp"))

    official_open = float(ohlc.get("open") or 0.0) or None
    prev_close = float(ohlc.get("close") or 0.0) or None

    return LegQuote(
        instrument_id=instrument_id,
        ltp=float(tick.get("last_price") or 0.0),
        bid=float(buy.get("price") or 0.0) or None,
        ask=float(sell.get("price") or 0.0) or None,
        bid_qty=int(buy.get("quantity") or 0),
        ask_qty=int(sell.get("quantity") or 0),
        # Keep the exchange's own stamp when it sent one; fall back to receipt
        # time only for the *packet* clock, never for the trade clock.
        exchange_ts_ms=exchange_ms if exchange_ms is not None else now_ms,
        received_ts_ms=now_ms,
        sequence=now_ms,
        source="kite_ticker",
        last_trade_ts_ms=last_trade_ms,
        official_open=official_open,
        prev_close=prev_close,
        volume_traded=int(tick.get("volume_traded") or 0),
    )


class BrokerPort:
    """The narrow broker surface the runner needs.

    An explicit port rather than the whole Kite client, so the runner is
    testable and so it is obvious exactly which broker powers this strategy has.
    """

    async def place(self, *, instrument_id: str, side: str, quantity: int,
                    limit_price: float, tag: str) -> tuple[Optional[str], Optional[str]]:
        raise NotImplementedError

    async def status(self, order_id: str) -> Optional[OrderReport]:
        raise NotImplementedError

    async def cancel(self, order_id: str) -> bool:
        raise NotImplementedError


class KiteBrokerPort(BrokerPort):
    """:class:`BrokerPort` backed by the Kite client.

    Translates the engine's opaque ``instrument_id`` (a Kite token) into the
    ``EXCHANGE:TRADINGSYMBOL`` the client wants, using the resolved pair -- the
    strategy never builds a broker symbol itself.
    """

    def __init__(self, client: Any, pair: OptionPairRef) -> None:
        self._client = client
        self._by_id = {
            pair.ce.instrument_id: (pair.ce.exchange or "BFO", pair.ce.tradingsymbol),
            pair.pe.instrument_id: (pair.pe.exchange or "BFO", pair.pe.tradingsymbol),
        }

    def _symbol(self, instrument_id: str) -> str:
        try:
            exchange, tradingsymbol = self._by_id[instrument_id]
        except KeyError as exc:
            raise ValueError(f"unknown instrument_id {instrument_id}") from exc
        return f"{exchange}:{tradingsymbol}"

    async def place(self, *, instrument_id, side, quantity, limit_price, tag):
        try:
            res = await self._client.place_order(
                self._symbol(instrument_id), side, float(quantity),
                order_type="limit_order", limit_price=float(limit_price), tag=tag,
            )
        except Exception as exc:
            log.error("ATM PI order placement failed (%s %s): %s", side, tag, exc)
            return None, str(exc)
        oid = None
        if isinstance(res, dict):
            oid = res.get("order_id") or (res.get("data") or {}).get("order_id")
        # No id and no exception is the dangerous case; the engine reconciles it.
        return (str(oid) if oid else None), None

    async def status(self, order_id):
        try:
            history = await self._client.get_order_history(order_id)
        except Exception as exc:
            log.warning("ATM PI order status unavailable for %s: %s", order_id, exc)
            return None
        if not history:
            return None
        last = history[-1] if isinstance(history, list) else history
        raw = str(last.get("status", "")).upper()
        mapping = {"COMPLETE": OrderStatus.COMPLETE, "REJECTED": OrderStatus.REJECTED,
                   "CANCELLED": OrderStatus.CANCELLED, "OPEN": OrderStatus.OPEN,
                   "TRIGGER PENDING": OrderStatus.OPEN, "PUT ORDER REQ RECEIVED": OrderStatus.PENDING,
                   "VALIDATION PENDING": OrderStatus.PENDING, "OPEN PENDING": OrderStatus.PENDING}
        return OrderReport(
            order_id=str(order_id), status=mapping.get(raw, OrderStatus.UNKNOWN),
            transaction="SELL" if str(last.get("transaction_type", "")).upper() == "SELL" else "BUY",
            average_price=float(last.get("average_price") or 0.0) or None,
            filled_quantity=int(last.get("filled_quantity") or 0),
            reject_reason=last.get("status_message") or None,
        )

    async def cancel(self, order_id):
        try:
            await self._client.cancel_order(str(order_id))
            return True
        except Exception as exc:
            log.error("ATM PI protection cancel failed for %s: %s", order_id, exc)
            return False


async def drive(session: Session, intent, broker: BrokerPort, *, max_steps: int = 24) -> str:
    """Service intents until the engine needs another tick.

    Bounded: a runaway intent loop against a live broker is worse than a missed
    trade, so it stops and halts rather than spinning.
    """
    s = session.strategy
    steps = 0
    while intent.kind not in ("none", "complete", "halt"):
        steps += 1
        if steps > max_steps:
            log.error("ATM PI intent loop did not settle for %s (last=%s)", session.user_id, intent.kind)
            return "intent_loop_unsettled"
        k = intent.kind
        if k == "submit_entry":
            view = s.signal.view if s.signal is not None else None
            if view is not None:
                note(session.user_id, "api_signal",
                     f"CE {view.ce_price:.2f} | PE {view.pe_price:.2f} | "
                     f"diff {abs(view.pe_price - view.ce_price):.2f} → buy the "
                     f"{intent.option_type}")
            note(session.user_id, "api_entry",
                 f"BUY {intent.quantity} {intent.option_type} @ limit "
                 f"{intent.limit_price:.2f} (attempt {intent.attempt})")
            oid, err = await broker.place(instrument_id=intent.instrument_id, side="BUY",
                                          quantity=intent.quantity, limit_price=intent.limit_price,
                                          tag="api-entry")
            if err:
                note(session.user_id, "api_order_failed", f"entry rejected: {err}")
            intent = s.record_entry_submit(intent.priced, order_id=oid, error=err)
        elif k == "poll_entry":
            intent = s.record_entry_status(await broker.status(intent.order_id))
        elif k == "reconcile_entry":
            from app.engines.atm_premium_imbalance import ReconcileState
            report = await broker.status(intent.order_id) if intent.order_id else None
            state = ReconcileState.MATCHED if report is not None else ReconcileState.UNKNOWN
            intent = s.record_entry_reconciliation(state, report)
        elif k == "place_protection":
            oid, err = await broker.place(instrument_id=intent.instrument_id, side="SELL",
                                          quantity=intent.quantity, limit_price=intent.limit_price,
                                          tag="api-protect")
            intent = s.record_protection_submit(order_id=oid, error=err)
        elif k == "cancel_protection":
            ok = await broker.cancel(intent.order_id) if intent.order_id else False
            intent = s.record_protection_cancelled(ok=ok)
        elif k == "submit_exit":
            ev = s.trade.exit if s.trade is not None else None
            note(session.user_id, "api_exit",
                 f"SELL {intent.quantity} {intent.option_type} @ limit "
                 f"{intent.limit_price:.2f}"
                 + (f" — {ev.reason}" if ev is not None and ev.reason else ""))
            oid, err = await broker.place(instrument_id=intent.instrument_id, side="SELL",
                                          quantity=intent.quantity, limit_price=intent.limit_price,
                                          tag="api-exit")
            if err:
                note(session.user_id, "api_order_failed", f"exit rejected: {err}")
            intent = s.record_exit_submit(order_id=oid, error=err)
        elif k == "poll_exit":
            intent = s.record_exit_status(await broker.status(intent.order_id))
        elif k == "reconcile_exit":
            log.error("ATM PI exit status unknown for %s order=%s", session.user_id, intent.order_id)
            return "exit_reconciliation_required"
        else:
            log.error("ATM PI unhandled intent %s for %s", k, session.user_id)
            return f"unhandled_intent:{k}"

        # The fill becomes known on a poll, not on the submit, so this is checked
        # once per pass rather than in the submit branch where it is always None.
        if s.trade is not None and s.trade.entry_price:
            _note_once(session, "fill", "api_filled",
                       f"filled {s.trade.quantity} {s.trade.option_type} @ "
                       f"{s.trade.entry_price:.2f} — target "
                       f"{(s.trade.target_price or 0):.2f}"
                       + (f", stop {s.live_stop:.2f}" if s.live_stop else ""))
    if intent.kind == "halt":
        log.error("ATM PI halted for %s: %s", session.user_id, intent.reason)
        note(session.user_id, "api_halt", f"halted — {intent.reason}")
        session.finished = True
        await release_subscriptions(session)
        return f"halt:{intent.reason}"
    if intent.kind == "complete":
        session.finished = True
        log.info("ATM PI trade complete for %s: %s", session.user_id, s.summary())
        t = s.trade
        if t is not None and t.exit_price is not None:
            note(session.user_id, "api_done",
                 f"closed {t.option_type} {t.quantity} @ {t.exit_price:.2f} — "
                 f"{(t.points or 0.0):+.2f} pts, P&L ₹{(t.pnl or 0.0):+.2f}"
                 + (f" ({t.exit.reason})" if t.exit is not None and t.exit.reason else ""))
        elif t is not None:
            # A session can complete without a fill -- a broker that never
            # accepted the order, for instance. Saying "closed @ None" would be
            # worse than saying what actually happened.
            note(session.user_id, "api_done",
                 f"finished with no position — {intent.reason or 'no reason given'}")
        await release_subscriptions(session)
        return "complete"

    # Nothing to do this tick. Two things are still worth saying once: why a
    # signal is being refused, and where a trailing stop has moved to.
    if s.signal is not None and s.signal.action == "NO_TRADE" and s.trade is None:
        _note_once(session, "refusal", "api_waiting",
                   f"no trade — {_refusal_text(s.signal.reason)}")
    if s.trade is not None and s.live_stop is not None and s.trade.exit is None:
        _note_once(session, "stop", "api_stop",
                   f"stop {s.live_stop:.2f} (peak {s._high_water:.2f}, "
                   f"entry {s.trade.entry_price:.2f})")
    return "idle"


#: Refusal reasons in the operator's language. Anything unmapped falls through
#: as-is rather than being swallowed, so a new reason is visible immediately.
_REFUSAL_TEXT = {
    "stale_session_quote": "a quote traded before today's open",
    "undatable_quote": "a quote with no trade time",
    "equal_premiums": "CE and PE are equal",
    "entry_window_closed": "too long after the open",
    "daily_loss_limit_reached": "the daily loss limit is reached",
    "session_trade_limit_reached": "already traded this session",
    "below_minimum_difference": "the CE/PE gap is below the minimum",
    "below_minimum_difference_percent": "the CE/PE gap is below the minimum percent",
    "stale_quote": "the feed has gone quiet",
    "no_quote_pair": "one leg has not quoted yet",
    "invalid_quote": "a leg quoted zero",
}


def _refusal_text(reason: Optional[str]) -> str:
    return _REFUSAL_TEXT.get(str(reason or ""), str(reason or "no reason given"))


async def on_ticks(user_id: str, ticks: list[dict], broker: Optional[BrokerPort] = None) -> str:
    """Entry point from the Kite tick fan-out.

    Returns a short status string; never raises into the tick loop.
    """
    session = _sessions.get(user_id)
    if session is None or session.finished:
        return "inactive"
    if session.sim:
        # A simulation is driven by its own replay loop on its own clock. Letting
        # today's live ticks in would mix two timelines in one position.
        return "simulated"
    if session.session_date != session.today():
        # Release before dropping the session: it holds the only record of which
        # tokens were ours, so discarding it first leaks them until a restart.
        await release_subscriptions(session)
        _sessions.pop(user_id, None)
        return "session_rolled"
    if not _is_market_open():
        return "market_closed"
    if broker is None:
        return "no_broker"

    lock = _lock_for(user_id)
    if lock.locked():
        # A tick arriving mid-order must not start a second order.
        return "busy"
    async with lock:
        now = session.now_ms()
        status = "idle"
        for tick in ticks:
            token = int(tick.get("instrument_token") or 0)
            leg = session.token_leg(token)
            if leg is None:
                continue
            iid = (session.pair.ce if leg == "CE" else session.pair.pe).instrument_id
            quote = _tick_to_quote(iid, tick, now)
            if quote.ltp <= 0:
                continue
            intent = session.strategy.on_option_tick(
                quote, now, session_open=True, risk_authorized=True,
            )
            status = await drive(session, intent, broker)
            if session.finished:
                break
        return status


def active_session(user_id: str) -> Optional[Session]:
    return _sessions.get(user_id)


def _leg_state(session: "Session", option_type: str) -> Optional[dict]:
    """One leg's live quote, including whether it can be traded on.

    ``session_origin`` is surfaced rather than kept internal because it is the
    difference between "no signal yet" and "refusing a carried-over price", and an
    operator staring at a board needs to be able to tell those apart.
    """
    ref = session.pair.ce if option_type == "CE" else session.pair.pe
    q = session.strategy.cache.ce if option_type == "CE" else session.strategy.cache.pe
    out = {
        "instrument_id": ref.instrument_id,
        "tradingsymbol": ref.tradingsymbol,
        "option_type": option_type,
        "lot_size": ref.lot_size,
        "ltp": None, "bid": None, "ask": None,
        "last_trade_ts_ms": None, "session_origin": None, "age_ms": None,
        "official_open": None,
    }
    if q is None:
        return out
    # The session's clock, not the wall clock: a replayed quote is not stale
    # merely because the replay is of an earlier day.
    now = session.now_ms()
    open_ms = session.strategy.session_open_ms
    out.update({
        "ltp": q.ltp, "bid": q.bid, "ask": q.ask,
        "last_trade_ts_ms": q.last_trade_ts_ms,
        "session_origin": None if open_ms is None else q.is_session_origin(open_ms),
        "age_ms": q.age_ms(now),
        "official_open": q.official_open,
    })
    return out


def session_status(user_id: str) -> Optional[dict]:
    """Everything a board needs to render this strategy, or ``None`` if unarmed.

    Deliberately includes the *reason* the strategy is doing nothing. A surface
    that shows a quiet engine without saying why is the recurring complaint about
    this codebase's panels.
    """
    session = _sessions.get(user_id)
    if session is None:
        return None
    strat = session.strategy
    cfg = session.cfg
    view = None
    if strat.session_open_ms is not None:
        view = strat.cache.view(cfg.quote_mode, session.now_ms(),
                                max_skew_ms=cfg.max_ce_pe_skew_ms)

    sig = strat.signal
    return {
        "armed": not session.finished,
        "finished": session.finished,
        "session_date": session.session_date.isoformat(),
        "session_open_ms": strat.session_open_ms,
        "phase": strat.phase.value,
        "halt_reason": strat.halt_reason or None,
        "underlying": session.pair.underlying,
        "expiry": session.pair.expiry,
        "strike": session.pair.strike,
        "quantity": session.strategy.quantity,
        "execution_mode": cfg.execution_mode,
        "quote_mode": cfg.quote_mode,
        "protection_mode": cfg.protection_mode,
        "trades_taken": strat.trades_taken,
        "legs": {"CE": _leg_state(session, "CE"), "PE": _leg_state(session, "PE")},
        "difference": None if view is None else view.difference,
        "cheaper_leg": None if view is None else view.cheaper_leg,
        "signal": {
            "action": None if sig is None else sig.action,
            "reason": None if sig is None else sig.reason,
            "option_type": None if sig is None else sig.option_type,
        },
        "trade": strat.summary() if strat.trade is not None else None,
    }


def clear(user_id: Optional[str] = None) -> None:
    if user_id is None:
        _sessions.clear()
    else:
        _sessions.pop(user_id, None)


def note(user_id: str, kind: str, message: str) -> None:
    """Write one line to the operator's terminal. Never raises.

    The terminal is where an operator watches this strategy think, so the lines
    are transitions, not ticks: premiums update dozens of times a second and a
    log that repeated them would bury the four moments that matter.
    """
    try:
        from app.services.kite_engine import state
        state.log(user_id, kind, message)
    except Exception:  # noqa: BLE001
        pass          # a log line is never worth breaking a trade over


def _note_once(session: "Session", key: str, kind: str, message: str) -> None:
    """Log only when the message for ``key`` has changed.

    A refusal reason is true on every tick until it stops being true. Printed
    each time it would drown out everything else; printed never, the operator
    cannot see why nothing is happening.
    """
    if session.logged.get(key) == message:
        return
    session.logged[key] = message
    note(session.user_id, kind, message)


# Claims this strategy's tick subscriptions so they can be released when the
# session ends. Without an owner tag the release would have to unsubscribe
# blindly, which could pull ticks out from under the protection monitor.
TICKER_OWNER = "atm_premium_imbalance"


async def release_subscriptions(session: Session) -> None:
    """Give back the session's two legs. Safe to call more than once.

    A finished session must not keep the ticker busy: subscriptions are one
    shared set per account with a hard broker cap, and a strategy that arms on a
    new strike every morning would otherwise accumulate a dead pair per day.
    Nothing here may raise -- this runs from the tick loop and from arm().
    """
    if session.released:
        return
    session.released = True
    try:
        from app.services.exchanges.kite import ticker_manager
        await ticker_manager.release(
            session.user_id, [session.ce_token, session.pe_token], TICKER_OWNER,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("ATM PI could not release subscriptions for %s: %s",
                    session.user_id, exc)


def register(session: Session) -> None:
    _sessions[session.user_id] = session


def forget(user_id: str) -> None:
    """Drop a session without touching subscriptions.

    For the simulator, which never subscribed anything: calling the release path
    would hand back tokens a live session might be holding.
    """
    _sessions.pop(user_id, None)


async def orphan_positions(user_id: str,
                           cfg: Optional[ATMPremiumImbalanceConfig] = None) -> list[dict]:
    """Open option positions in this underlying that no session explains.

    After a restart the strategy's state is gone but a position is not. Arming
    fresh on top of one would double the exposure, and never finding it leaves a
    bought option with nothing watching its stop.

    Reported rather than adopted automatically: a long option on this underlying
    might be something the operator placed by hand, and quietly taking control of
    somebody else's trade is worse than telling them about it.
    """
    from app.services.atm_premium_imbalance import get_config
    cfg = cfg or get_config()
    session = _sessions.get(user_id)
    if session is not None and not session.finished and not session.sim:
        return []
    try:
        from app.services.exchanges.kite import accounts
        acct = accounts.get_active(user_id)
        if not acct or not acct.connected:
            return []
        client = await accounts.acquire_client(acct)
        positions = await client.get_positions()
    except Exception as exc:  # noqa: BLE001
        log.debug("ATM PI could not read positions for %s: %s", user_id, exc)
        return []

    want = str(cfg.underlying).upper()
    out: list[dict] = []
    for pos in positions or []:
        symbol = str(getattr(pos, "symbol", "") or "").upper()
        size = float(getattr(pos, "size", 0) or 0)
        if size <= 0 or not symbol.startswith(want):
            continue
        if not (symbol.endswith("CE") or symbol.endswith("PE")):
            continue
        out.append({
            "symbol": symbol,
            "option_type": symbol[-2:],
            "quantity": int(abs(size)),
            "entry_price": float(getattr(pos, "entry_price", 0) or 0),
            "mark_price": float(getattr(pos, "mark_price", 0) or 0),
            "unrealized_pnl": float(getattr(pos, "unrealized_pnl", 0) or 0),
        })
    return out


async def adopt(user_id: str, symbol: str,
                cfg: Optional[ATMPremiumImbalanceConfig] = None) -> dict:
    """Take charge of one orphaned position, by name.

    Requires the symbol so this cannot be a blanket "adopt whatever you find":
    the operator is confirming which position is the strategy's.
    """
    from app.services.atm_premium_imbalance import get_config, resolve_option_pair
    cfg = cfg or get_config()
    orphans = await orphan_positions(user_id, cfg)
    match = next((o for o in orphans if o["symbol"] == str(symbol).upper()), None)
    if match is None:
        return {"status": "not_found", "message": f"no open position named {symbol}"}

    pair = await resolve_option_pair(user_id, cfg)
    leg = pair.ce if match["option_type"] == "CE" else pair.pe
    if leg.tradingsymbol.upper() != match["symbol"]:
        # The resolved ATM pair has moved on. Adopting against the wrong contract
        # would watch one option's price to exit a different one.
        return {"status": "contract_mismatch",
                "message": f"the open position is {match['symbol']} but the ATM "
                           f"{match['option_type']} is now {leg.tradingsymbol}"}

    today = datetime.now(_IST).date()
    strategy = ATMPremiumImbalanceStrategy(
        cfg=cfg, pair=pair, quantity=match["quantity"],
        trade_id=f"adopted-{user_id}-{today.isoformat()}",
    )
    strategy.adopt_open_position(
        option_type=match["option_type"], entry_fill=match["entry_price"],
        quantity=match["quantity"], now_ms=_now_ms(),
    )
    try:
        ce_token, pe_token = int(pair.ce.instrument_id), int(pair.pe.instrument_id)
    except (TypeError, ValueError):
        return {"status": "error", "message": "instrument ids are not Kite tokens"}

    from app.services.exchanges.kite import ticker_manager
    await ticker_manager.subscribe(user_id, [ce_token, pe_token], "full",
                                   owner=TICKER_OWNER)
    register(Session(user_id=user_id, cfg=cfg, pair=pair, strategy=strategy,
                     session_date=today, ce_token=ce_token, pe_token=pe_token))
    log.warning("ATM PI adopted %s for %s: %s x %s @ %s", match["symbol"], user_id,
                match["option_type"], match["quantity"], match["entry_price"])
    note(user_id, "api_adopted",
         f"took charge of {match['symbol']} — {match['quantity']} @ "
         f"{match['entry_price']:.2f}; peak since entry is unknown, so the trail "
         f"restarts from the entry")
    return {"status": "adopted", **match,
            "target": strategy.trade.target_price,
            "stop": strategy.live_stop,
            "peak_unknown": True}


async def arm(user_id: str, cfg: Optional[ATMPremiumImbalanceConfig] = None) -> dict:
    """Resolve the ATM pair, subscribe both legs, and arm the strategy.

    Refuses rather than guessing: disabled config, no quantity, a closed market
    or an unresolvable pair all return a reason instead of a half-armed session.
    """
    from app.services.atm_premium_imbalance import get_config, resolve_option_pair
    cfg = cfg or get_config()
    if not cfg.enabled:
        return {"status": "disabled"}
    if not cfg.size_is_set:
        return {"status": "no_quantity"}
    if not _is_market_open():
        return {"status": "market_closed"}

    orphans = await orphan_positions(user_id, cfg)
    if orphans:
        # Arming on top of an existing position doubles the exposure, and the
        # strategy would then exit a size it did not open.
        note(user_id, "api_blocked",
             f"refusing to arm — {orphans[0]['symbol']} is open and unaccounted for")
        return {"status": "open_position_unaccounted",
                "message": "an open position exists that no session explains; "
                           "adopt or close it first",
                "positions": orphans}

    existing = _sessions.get(user_id)
    today = datetime.now(_IST).date()
    if existing and existing.session_date == today and not existing.finished:
        return {"status": "already_armed", "strike": existing.pair.strike}

    pair = await resolve_option_pair(user_id, cfg)
    try:
        ce_token, pe_token = int(pair.ce.instrument_id), int(pair.pe.instrument_id)
    except (TypeError, ValueError):
        return {"status": "error", "message": "instrument ids are not Kite tokens"}

    # Settle the size now rather than at the open. The lot size is only known
    # once the pair resolves, which is why this is not a plain config rule, and
    # the rule itself lives on the config so the board cannot disagree with it.
    lot = int(pair.ce.lot_size or 0)
    blocker = cfg.sizing_blocker(lot)
    if blocker:
        return {"status": "invalid_size", "message": blocker}
    quantity = cfg.effective_quantity(lot)

    strategy = ATMPremiumImbalanceStrategy(
        cfg=cfg, pair=pair, quantity=quantity,
        trade_id=f"api-{user_id}-{today.isoformat()}",
    )
    from app.services.exchanges.kite import ticker_manager

    # Re-arming replaces the outgoing session, so give back the legs it held --
    # except any the new pair reuses. The claim is per token and this strategy
    # holds one owner tag, so releasing a carried-over token would revoke the
    # claim the new session is about to depend on. Marking the old session
    # released stops a later stray release from doing exactly that.
    if existing is not None:
        stale = [t for t in (existing.ce_token, existing.pe_token)
                 if t not in (ce_token, pe_token)]
        existing.released = True
        if stale:
            try:
                await ticker_manager.release(user_id, stale, TICKER_OWNER)
            except Exception as exc:  # noqa: BLE001
                log.warning("ATM PI could not release stale legs for %s: %s", user_id, exc)

    await ticker_manager.subscribe(user_id, [ce_token, pe_token], "full",
                                   owner=TICKER_OWNER)

    register(Session(user_id=user_id, cfg=cfg, pair=pair, strategy=strategy,
                     session_date=today, ce_token=ce_token, pe_token=pe_token))
    log.info("ATM PI armed for %s: %s %s strike=%s", user_id, pair.underlying, pair.expiry, pair.strike)
    note(user_id, "api_armed",
         f"{pair.underlying} {pair.strike:g} {pair.expiry} — {quantity} "
         f"({quantity // max(1, lot)} lot{'s' if quantity // max(1, lot) != 1 else ''}), "
         f"{cfg.exit_policy.lower().replace('_', ' ')}, {cfg.execution_mode}")
    return {
        "status": "armed", "underlying": pair.underlying, "expiry": pair.expiry,
        "strike": pair.strike, "quantity": quantity, "lots": quantity // max(1, lot),
        "protection_mode": cfg.protection_mode, "execution_mode": cfg.execution_mode,
    }
