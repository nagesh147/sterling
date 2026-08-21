"""Replay a real session through the live code path, on a virtual clock.

The point is to let an operator *watch* the strategy work before trusting it with
money. So this drives the same runner, the same strategy object and the same
board payload as a live session — the only differences are where the ticks come
from and what the clock says.

It starts at 09:14 IST on purpose. For that first minute the legs carry the
previous session's closing prices, so the board shows the strategy refusing to
trade on a carried-over quote, and then trading the moment a real session price
arrives. That refusal is the most important thing this strategy does and it is
invisible in a summary.

**This is illustrative, not evidence.** Two reasons, both structural:

* The data is minute bars. Kite publishes no historical option ticks, so the
  intrabar path is unknown: a bar says open/high/low/close but not in which
  order the high and the low happened. Ticks are emitted open, high, low, close
  — the conservative order for a long position with a stop, since it lets the
  peak set the trail before the low tests it — but it is an assumption, and a
  trailing stop's result depends on exactly that ordering.
* Fills are modelled, not real. The simulated broker fills at the limit price,
  which is optimistic: a real marketable order pays the spread and can be
  partially filled.

So the P&L a simulation reports is not a backtest result and must never be
presented as one.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from app.core.logging import get_logger
from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, ATMPremiumImbalanceStrategy, LegQuote, OrderReport,
    OrderStatus, OptionPairRef,
)
from app.engines.atm_premium_imbalance.session import session_open_ms_for

log = get_logger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

#: Where the clock starts. One minute before the bell, so the pre-open refusal
#: is visible rather than something the operator has to be told about.
START_HHMM = "09:14"

#: How many wall-clock milliseconds one simulated minute takes at speed 1.
MINUTE_MS = 60_000

#: Ticks emitted per minute bar, in the order they are emitted.
BAR_PATH = ("open", "high", "low", "close")


@dataclass
class SimState:
    """What the UI needs to know about a running simulation."""

    running: bool = False
    session_date: Optional[date] = None
    speed: float = 60.0
    clock_ms: int = 0
    bars_total: int = 0
    bars_done: int = 0
    note: str = ""
    error: Optional[str] = None
    #: Set when the strategy finished before the bars ran out.
    outcome: Optional[str] = None
    halt_reason: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "running": self.running,
            "session_date": None if self.session_date is None else self.session_date.isoformat(),
            "speed": self.speed,
            "clock_ms": self.clock_ms,
            "clock_ist": (datetime.fromtimestamp(self.clock_ms / 1000, tz=IST).strftime("%H:%M:%S")
                          if self.clock_ms else None),
            "bars_total": self.bars_total,
            "bars_done": self.bars_done,
            "progress": (round(self.bars_done / self.bars_total, 3)
                         if self.bars_total else 0.0),
            "note": self.note,
            "error": self.error,
            "outcome": self.outcome,
            "halt_reason": self.halt_reason,
            # Repeated in the payload so a client cannot render a simulation as
            # a live result by forgetting to check a flag somewhere else.
            "illustrative_only": True,
        }


_states: dict[str, SimState] = {}
_tasks: dict[str, asyncio.Task] = {}


def state(user_id: str) -> Optional[dict]:
    st = _states.get(user_id)
    return None if st is None else st.as_dict()


class SimBroker:
    """Fills at the limit price, immediately.

    Optimistic on purpose and documented as such: a real marketable order pays
    the spread. Modelling slippage here would invent a number that looks like
    evidence.
    """

    def __init__(self) -> None:
        self.placed: list[dict] = []
        self.cancelled: list[str] = []
        self._n = 0

    async def place(self, *, instrument_id: str, side: str, quantity: int,
                    limit_price: float, tag: str) -> tuple[Optional[str], Optional[str]]:
        self._n += 1
        oid = f"SIM{self._n}"
        self.placed.append({"id": oid, "side": side, "qty": quantity,
                            "price": float(limit_price), "tag": tag})
        return oid, None

    async def status(self, order_id: str) -> Optional[OrderReport]:
        rec = next((p for p in self.placed if p["id"] == order_id), None)
        if rec is None:
            return None
        return OrderReport(order_id=order_id, status=OrderStatus.COMPLETE,
                           transaction=rec["side"], average_price=rec["price"],
                           filled_quantity=rec["qty"])

    async def cancel(self, order_id: str) -> bool:
        self.cancelled.append(order_id)
        return True


async def last_traded_day(uid: str, token: int, *, look_back: int = 12) -> Optional[date]:
    """The most recent day this instrument actually has bars for.

    Walks back from today rather than consulting a holiday calendar: "a day Kite
    will give us data for" is the property that matters, and it is the one a
    calendar can be wrong about.
    """
    from app.services.atm_premium_imbalance_replay import kite_minute_bars
    today = datetime.now(IST).date()
    for back in range(0, look_back + 1):
        day = today - timedelta(days=back)
        if day.weekday() >= 5:            # cheap skip; holidays fall out below
            continue
        try:
            bars = await kite_minute_bars(uid, token, day)
        except Exception as exc:          # noqa: BLE001
            log.debug("ATM PI sim: no bars for %s: %s", day, exc)
            continue
        if bars:
            return day
    return None


def _quote(instrument_id: str, price: float, now_ms: int, *,
           traded_ms: int, official_open: Optional[float]) -> LegQuote:
    """One synthetic tick.

    A minute bar has no book, so bid and ask are placed a half-tick either side
    of the price. That is a *model* of a spread, and it is why simulated fills
    are optimistic.
    """
    half = 0.05
    return LegQuote(
        instrument_id=instrument_id,
        ltp=float(price),
        bid=round(float(price) - half, 2),
        ask=round(float(price) + half, 2),
        exchange_ts_ms=int(now_ms),
        received_ts_ms=int(now_ms),
        sequence=int(now_ms),
        last_trade_ts_ms=int(traded_ms),
        official_open=official_open,
    )


async def stop(user_id: str) -> dict:
    """Cancel a running simulation and clear its session."""
    task = _tasks.pop(user_id, None)
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):   # noqa: BLE001
            pass
    st = _states.get(user_id)
    if st is not None:
        st.running = False
        st.note = "stopped"
    from app.services import atm_premium_imbalance_runner as R
    session = R.active_session(user_id)
    if session is not None and session.sim:
        R.forget(user_id)
    return {"ok": True}


async def start(user_id: str, *, speed: float = 60.0, lots: Optional[int] = None,
                overrides: Optional[dict] = None,
                cfg: Optional[ATMPremiumImbalanceConfig] = None) -> dict:
    """Begin a simulation. Refuses rather than competing with a live session."""
    from app.services import atm_premium_imbalance_runner as R
    from app.services.atm_premium_imbalance import get_config, resolve_option_pair

    existing = R.active_session(user_id)
    if existing is not None and not existing.sim and not existing.finished:
        # A live armed session owns the strategy state for this user. Replaying
        # over it would show the operator a fiction while real money is at work.
        return {"status": "live_session_active"}
    await stop(user_id)

    cfg = cfg or get_config()
    if overrides:
        # Try a policy without committing it. Validated through the engine's own
        # config, so a replay cannot run a combination the live path would refuse
        # -- and the stored config is not touched, so experimenting with a stop
        # never changes what a real session would do.
        merged = {**cfg.as_dict(), **{k: v for k, v in overrides.items()
                                      if k in ATMPremiumImbalanceConfig.field_names()}}
        unknown = sorted(set(overrides) - ATMPremiumImbalanceConfig.field_names())
        if unknown:
            return {"status": "error",
                    "message": f"unknown config fields: {', '.join(unknown)}"}
        try:
            cfg = ATMPremiumImbalanceConfig(**merged).validate()
        except (ValueError, TypeError) as exc:
            return {"status": "invalid_overrides", "message": str(exc)}
    speed = max(1.0, min(600.0, float(speed)))
    try:
        pair = await resolve_option_pair(user_id, cfg)
    except Exception as exc:                          # noqa: BLE001
        return {"status": "error", "message": f"could not resolve the ATM pair: {exc}"}

    try:
        ce_token, pe_token = int(pair.ce.instrument_id), int(pair.pe.instrument_id)
    except (TypeError, ValueError):
        return {"status": "error", "message": "instrument ids are not Kite tokens"}

    day = await last_traded_day(user_id, ce_token)
    if day is None:
        return {"status": "no_data",
                "message": "Kite returned no minute bars for the last 12 days"}

    from app.services.atm_premium_imbalance_replay import kite_minute_bars
    ce_bars = await kite_minute_bars(user_id, ce_token, day)
    pe_bars = await kite_minute_bars(user_id, pe_token, day)
    if not ce_bars or not pe_bars:
        return {"status": "no_data", "message": f"one leg has no bars for {day}"}

    # Size: the caller's lots if given, else whatever is configured, else one
    # lot. The override exists so a demo does not require editing the live
    # trading config -- changing a real trade size to make a replay run is the
    # wrong trade-off.
    if lots is not None and int(lots) > 0:
        quantity = int(lots) * pair.ce.lot_size
    elif cfg.size_is_set:
        quantity = cfg.effective_quantity(pair.ce.lot_size)
    else:
        quantity = pair.ce.lot_size

    st = SimState(running=True, session_date=day, speed=speed,
                  bars_total=min(len(ce_bars), len(pe_bars)),
                  note=f"replaying {day.isoformat()} at {speed:g}x")
    _states[user_id] = st

    strategy = ATMPremiumImbalanceStrategy(
        cfg=cfg, pair=pair, quantity=quantity,
        trade_id=f"sim-{user_id}-{day.isoformat()}",
    )
    session = R.Session(user_id=user_id, cfg=cfg, pair=pair, strategy=strategy,
                        session_date=day, ce_token=ce_token, pe_token=pe_token,
                        sim=True, released=True)
    R.register(session)

    _tasks[user_id] = asyncio.create_task(
        _run(user_id, session, st, ce_bars, pe_bars, speed))
    return {"status": "started", "session_date": day.isoformat(), "speed": speed,
            "quantity": quantity, "strike": pair.strike, "expiry": pair.expiry,
            "exit_policy": cfg.exit_policy, "illustrative_only": True}


async def _run(user_id: str, session, st: SimState, ce_bars, pe_bars, speed: float) -> None:
    """Step the clock through the session, feeding one bar at a time."""
    from app.services import atm_premium_imbalance_runner as R

    broker = SimBroker()
    open_ms = session_open_ms_for(
        int(datetime.combine(st.session_date, datetime.min.time(), tzinfo=IST).timestamp() * 1000)
        + 12 * 3600 * 1000,                      # midday, so the date cannot slip
        session.cfg.session_start,
    )
    # The pre-open minute. Both legs carry the previous session's close, which is
    # exactly the quote the strategy must refuse.
    session.clock_ms = open_ms - MINUTE_MS
    prior_ms = open_ms - 12 * 3600 * 1000        # "yesterday", for the trade stamp
    try:
        await _emit(session, broker, [
            (session.pair.ce.instrument_id, ce_bars[0].open),
            (session.pair.pe.instrument_id, pe_bars[0].open),
        ], traded_ms=prior_ms, official_open=None)
        st.clock_ms = session.clock_ms
        st.note = "pre-open: refusing a carried-over quote"
        await asyncio.sleep(MINUTE_MS / 1000.0 / speed)

        pairs = list(zip(ce_bars, pe_bars))
        for i, (ce, pe) in enumerate(pairs):
            if session.finished:
                break
            minute_ms = int(ce.ts.timestamp() * 1000)
            for step, field_name in enumerate(BAR_PATH):
                session.clock_ms = minute_ms + step * 15_000
                await _emit(session, broker, [
                    (session.pair.ce.instrument_id, getattr(ce, field_name)),
                    (session.pair.pe.instrument_id, getattr(pe, field_name)),
                ], traded_ms=session.clock_ms, official_open=ce.open)
                if session.finished:
                    break
            st.clock_ms = session.clock_ms
            st.bars_done = i + 1
            st.note = f"{session.strategy.phase.value} at " \
                      f"{datetime.fromtimestamp(session.clock_ms/1000, tz=IST):%H:%M}"
            await asyncio.sleep(MINUTE_MS / 1000.0 / speed)

        st.outcome = session.strategy.phase.value
        # Carry the halt reason through. "finished: halted" on its own sends the
        # operator to the logs for something the UI already knows.
        reason = session.strategy.halt_reason
        st.note = f"finished: {st.outcome}" + (f" — {reason}" if reason else "")
        st.halt_reason = reason or None
    except asyncio.CancelledError:
        st.note = "cancelled"
        raise
    except Exception as exc:                      # noqa: BLE001
        st.error = str(exc)
        st.note = "failed"
        log.exception("ATM PI simulation failed for %s", user_id)
    finally:
        st.running = False


async def _emit(session, broker: SimBroker, legs, *, traded_ms: int,
                official_open: Optional[float]) -> None:
    """Feed one tick per leg through the strategy and service its intents."""
    from app.services import atm_premium_imbalance_runner as R
    for instrument_id, price in legs:
        if price is None or float(price) <= 0:
            continue
        quote = _quote(instrument_id, float(price), session.clock_ms,
                       traded_ms=traded_ms, official_open=official_open)
        intent = session.strategy.on_option_tick(
            quote, session.clock_ms, session_open=True, risk_authorized=True,
        )
        await R.drive(session, intent, broker)
        if session.finished:
            return
