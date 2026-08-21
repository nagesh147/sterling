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
from dataclasses import dataclass, field, replace
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

#: How long before the bell the clock starts, in seconds. Long enough to watch
#: it walk up to the open and see the exchange reported shut; short enough that
#: at real speed the wait is seconds rather than a minute.
PRE_OPEN_SECONDS = 15

#: How many wall-clock milliseconds one simulated minute takes at speed 1.
MINUTE_MS = 60_000

#: The clock advances one simulated second per step, so at speed 1 the replay
#: runs in real time and the displayed clock ticks the way a live one does.
SECOND_MS = 1_000

#: Which quarter of a minute takes which field of the bar. A minute bar gives
#: four real prices and says nothing about the order they occurred in, so the
#: price is held as a step function over them rather than interpolated --
#: inventing intermediate prices would be inventing the very thing the replay is
#: supposed to show. The order puts the high before the low, which lets a peak
#: set a trailing stop before the low tests it.
BAR_PATH = ("open", "high", "low", "close")


@dataclass
class SimState:
    """What the UI needs to know about a running simulation."""

    running: bool = False
    session_date: Optional[date] = None
    speed: float = 1.0
    continuous: bool = True
    trades: int = 0
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
            # 12-hour with AM/PM: this is a market clock and an operator reads
            # "09:14:00 AM", not "09:14:00".
            "clock_ist": (datetime.fromtimestamp(self.clock_ms / 1000, tz=IST)
                          .strftime("%I:%M:%S %p") if self.clock_ms else None),
            "continuous": self.continuous,
            "trades": self.trades,
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


async def last_traded_day(uid: str, token: int, *,
                          look_back: int = 12) -> tuple[Optional[date], list[str]]:
    """The most recent day this instrument has bars for, and what was skipped.

    Walks back from today rather than consulting a holiday calendar: "a day Kite
    will give us data for" is the property that matters, and it is the one a
    calendar can be wrong about.

    The skip list is returned rather than logged and forgotten. A transient Kite
    error on the newest day silently moves the replay back a day, and "yesterday
    was a holiday" and "yesterday's request failed" are very different facts
    about a replay the operator is about to read numbers off.
    """
    from app.services.atm_premium_imbalance_replay import kite_minute_bars
    today = datetime.now(IST).date()
    skipped: list[str] = []
    for back in range(0, look_back + 1):
        day = today - timedelta(days=back)
        if day.weekday() >= 5:            # cheap skip; holidays fall out below
            continue
        try:
            bars = await kite_minute_bars(uid, token, day)
        except Exception as exc:          # noqa: BLE001
            log.debug("ATM PI sim: no bars for %s: %s", day, exc)
            skipped.append(f"{day.isoformat()}: {exc}")
            continue
        if bars:
            return day, skipped
        skipped.append(f"{day.isoformat()}: no bars")
    return None, skipped


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


async def start(user_id: str, *, speed: float = 1.0, lots: Optional[int] = None,
                continuous: bool = True, overrides: Optional[dict] = None,
                cfg: Optional[ATMPremiumImbalanceConfig] = None) -> dict:
    """Begin a simulation. Refuses rather than competing with a live session.

    Runs in real time by default: one simulated second per real second, so the
    clock reads like a live one. ``speed`` still scales it for anyone who wants
    to skip ahead.

    ``continuous`` keeps the session working after a trade closes instead of
    stopping at the first one. It relaxes exactly two settings and says so in
    the log, because a replay that quietly ran a different configuration from
    the live one would be worse than useless: the per-session trade limit, and
    the entry window (which exists to keep live entries near the open and would
    otherwise refuse every later signal).
    """
    from app.services import atm_premium_imbalance_runner as R
    from app.services.atm_premium_imbalance import get_config, resolve_option_pair

    existing = R.active_session(user_id)
    if existing is not None and not existing.sim and not existing.finished:
        # A live armed session owns the strategy state for this user. Replaying
        # over it would show the operator a fiction while real money is at work.
        return {"status": "live_session_active"}
    await stop(user_id)

    cfg = cfg or get_config()
    relaxed: list[str] = []
    if continuous:
        # Stated, not silent. An operator reading a replay has to know it is not
        # running the config that a live session would.
        if cfg.max_trades_per_session <= 1:
            relaxed.append("trade limit lifted to 50")
        if cfg.entry_window_seconds > 0:
            relaxed.append("entry window off")
        cfg = replace(cfg, max_trades_per_session=max(50, cfg.max_trades_per_session),
                      entry_window_seconds=0).validate()
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
    speed = max(0.1, min(600.0, float(speed)))
    try:
        pair = await resolve_option_pair(user_id, cfg)
    except Exception as exc:                          # noqa: BLE001
        return {"status": "error", "message": f"could not resolve the ATM pair: {exc}"}

    try:
        ce_token, pe_token = int(pair.ce.instrument_id), int(pair.pe.instrument_id)
    except (TypeError, ValueError):
        return {"status": "error", "message": "instrument ids are not Kite tokens"}

    day, skipped = await last_traded_day(user_id, ce_token)
    if day is None:
        return {"status": "no_data",
                "message": "Kite returned no minute bars for the last 12 days",
                "skipped": skipped}
    for line in skipped:
        # Say which days were passed over and why. Without this, a failed request
        # on the newest day looks identical to a holiday.
        from app.services import atm_premium_imbalance_runner as _R
        _R.note(user_id, "api_replay", f"skipped {line}")

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

    st = SimState(running=True, session_date=day, speed=speed, continuous=continuous,
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

    R.note(user_id, "api_replay",
           f"replaying {day.isoformat()} at {speed:g}x — {quantity} contracts, "
           f"{cfg.exit_policy.lower().replace('_', ' ')}"
           + (f"; continuous ({', '.join(relaxed)})" if relaxed else "")
           + ". Real prices, simulated fills; not a backtest.")
    _tasks[user_id] = asyncio.create_task(
        _run(user_id, session, st, ce_bars, pe_bars, speed))
    return {"status": "started", "session_date": day.isoformat(), "speed": speed,
            "quantity": quantity, "strike": pair.strike, "expiry": pair.expiry,
            "exit_policy": cfg.exit_policy, "skipped": skipped,
            "continuous": continuous, "relaxed": relaxed,
            "illustrative_only": True}


async def _run(user_id: str, session, st: SimState, ce_bars, pe_bars, speed: float) -> None:
    """Step the clock one simulated second at a time, feeding the day's bars.

    A second rather than a minute because the clock is the point: at speed 1 this
    reads like a live session, and a clock that jumped a minute at a time would
    not. Within each minute the price is held as a step function over the bar's
    four real values -- see BAR_PATH.

    It does not stop at the first closed trade. Under continuous mode the
    strategy re-arms and this keeps running to the end of the session, or until
    the task is cancelled.
    """
    from app.services import atm_premium_imbalance_runner as R

    broker = SimBroker()
    open_ms = session_open_ms_for(
        int(datetime.combine(st.session_date, datetime.min.time(), tzinfo=IST).timestamp() * 1000)
        + 12 * 3600 * 1000,                      # midday, so the date cannot slip
        session.cfg.session_start,
    )
    # One second before the bell, not a full minute. A pre-open tick at 09:14:00
    # is still 60s old when the 09:15 bar arrives, so the freshness gate reports
    # "the feed has gone quiet" for one tick -- true from the strategy's point of
    # view, and an artifact of the clock jumping rather than anything real.
    prior_ms = open_ms - 12 * 3600 * 1000        # "yesterday", for the trade stamp
    pause = SECOND_MS / 1000.0 / speed

    try:
        # The pre-open seconds, one at a time, so the operator can watch the
        # clock reach the bell.
        for offset in range(-PRE_OPEN_SECONDS, 0):
            session.clock_ms = open_ms + offset * SECOND_MS
            st.clock_ms = session.clock_ms
            if offset == -PRE_OPEN_SECONDS:
                st.note = ("pre-open — the exchange is closed, and both legs "
                           "still carry yesterday's close")
                R.note(user_id, "api_replay",
                       f"{datetime.fromtimestamp(session.clock_ms/1000, tz=IST):%I:%M:%S %p}"
                       " — exchange closed; both legs still carry yesterday's "
                       "closing price")
            if offset >= -1:
                # Only the last pre-open second emits, so the quote is fresh by
                # age at the bell while still stamped with yesterday's trade.
                await _emit(session, broker, [
                    (session.pair.ce.instrument_id, ce_bars[0].open),
                    (session.pair.pe.instrument_id, pe_bars[0].open),
                ], traded_ms=prior_ms, official_open=None)
            await asyncio.sleep(pause)

        pairs = list(zip(ce_bars, pe_bars))
        for i, (ce, pe) in enumerate(pairs):
            minute_ms = int(ce.ts.timestamp() * 1000)
            for second in range(60):
                session.clock_ms = minute_ms + second * SECOND_MS
                field_name = BAR_PATH[min(second // 15, len(BAR_PATH) - 1)]
                await _emit(session, broker, [
                    (session.pair.ce.instrument_id, getattr(ce, field_name)),
                    (session.pair.pe.instrument_id, getattr(pe, field_name)),
                ], traded_ms=session.clock_ms, official_open=ce.open)
                st.clock_ms = session.clock_ms
                st.trades = session.strategy.trades_taken
                st.note = _phase_note(session)
                if session.finished:
                    break
                await asyncio.sleep(pause)
            st.bars_done = i + 1
            if session.finished:
                break

        R.note(user_id, "api_replay_done",
               f"replay ended at "
               f"{datetime.fromtimestamp(session.clock_ms/1000, tz=IST):%I:%M:%S %p} "
               f"after {st.bars_done} of {st.bars_total} minutes and "
               f"{session.strategy.trades_taken} trade(s)")
        st.outcome = session.strategy.phase.value
        reason = session.strategy.halt_reason
        st.note = f"finished: {st.outcome}" + (f" — {reason}" if reason else "")
        st.halt_reason = reason or None
    except asyncio.CancelledError:
        st.note = "stopped"
        raise
    except Exception as exc:                      # noqa: BLE001
        st.error = str(exc)
        st.note = "failed"
        log.exception("ATM PI simulation failed for %s", user_id)
    finally:
        st.running = False


def _market_open_at(clock_ms: int) -> bool:
    """Is the exchange open at this instant on the virtual clock?

    Falls back to a plain 09:15-15:30 window if the calendar cannot answer for
    the date: refusing to replay because a holiday table is short of a year
    would be worse than a slightly less precise boundary.
    """
    try:
        from app.services.navigator.calendar import is_market_open_at
        return bool(is_market_open_at(int(clock_ms)))
    except Exception:  # noqa: BLE001
        at = datetime.fromtimestamp(int(clock_ms) / 1000, tz=IST)
        return (at.hour, at.minute) >= (9, 15) and (at.hour, at.minute) <= (15, 30)


def _phase_note(session) -> str:
    """A one-line "what is it doing" for the banner."""
    strat = session.strategy
    clock = datetime.fromtimestamp(session.clock_ms / 1000, tz=IST).strftime("%I:%M:%S %p")
    phase = strat.phase.value
    if strat.trade is not None and strat.trade.entry_price:
        return (f"{phase} at {clock} — {strat.trade.option_type} @ "
                f"{strat.trade.entry_price:.2f}"
                + (f", stop {strat.live_stop:.2f}" if strat.live_stop else "")
                + (f", target {strat.trade.target_price:.2f}"
                   if strat.trade.target_price else ""))
    if strat.trades_taken:
        return f"{phase} at {clock} — {strat.trades_taken} trade(s) done, watching"
    return f"{phase} at {clock}"


async def _emit(session, broker: SimBroker, legs, *, traded_ms: int,
                official_open: Optional[float]) -> None:
    """Feed one tick per leg through the strategy and service its intents."""
    from app.services import atm_premium_imbalance_runner as R
    # Ask the calendar about the *virtual* clock. A live session never reaches
    # the strategy before 09:15 -- the runner's market-hours check returns
    # "market_closed" first -- so passing session_open=True unconditionally made
    # the replay evaluate at a time live never would, and the pre-open refusal it
    # showed was of the strategy's stale-quote gate rather than of the closed
    # market. Same question, same answer, same route.
    open_now = _market_open_at(session.clock_ms)
    for instrument_id, price in legs:
        if price is None or float(price) <= 0:
            continue
        quote = _quote(instrument_id, float(price), session.clock_ms,
                       traded_ms=traded_ms, official_open=official_open)
        intent = session.strategy.on_option_tick(
            quote, session.clock_ms, session_open=open_now, risk_authorized=True,
        )
        await R.drive(session, intent, broker)
        if session.finished:
            return
