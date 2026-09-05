"""
Market Replay Simulation Runner.

Replays historical candle data through the full signal pipeline at
configurable speeds, allowing users to watch strategies execute on
past trading days as if they were live.
"""
import asyncio
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel
from app.core.logging import get_logger

log = get_logger(__name__)


class SimState(str, Enum):
    IDLE = "idle"
    LOADING = "loading"
    RUNNING = "running"
    PAUSED = "paused"


class SimConfig(BaseModel):
    date: str                          # "2026-08-28"
    end_date: Optional[str] = None     # Optional multi-day range end
    start_time: str = "09:00:00"       # HH:MM:SS IST (defaults to 9:00 AM)
    end_time: str = "15:30:00"         # HH:MM:SS IST  
    speed: float = 1.0                 # 1,2,5,10,15,20,50
    resolution: str = "5m"             # candle resolution
    instruments: List[str] = []        # empty = all watchlist
    strategy: str = "all"              # "all" or specific strategy name
    strategies: List[str] = ["all"]    # list of selected strategies
    lots: int = 1                      # number of option/futures lots
    moneyness: str = "ATM"             # "ATM", "ITM1", "ITM2", "OTM1", "OTM2", "ALL"

    # ── Execution friction ────────────────────────────────────────────────
    # These are read by `_apply_friction`. Until 2026-09 they were declared
    # here and consumed nowhere, while the UI rendered a slippage column and
    # a "SLIPPAGE DRAG" metric against them — so the dock reported ₹0.00 of
    # execution cost for every strategy. The values below are echoed back on
    # `SimStatus.config`, which is what lets the client verify the engine
    # actually honoured what it asked for.
    friction_mode: str = "realistic"   # "realistic" (spread + slippage) or "ideal"
    index_spread_pct: float = 0.50     # round-trip bid/ask spread, index options
    stock_spread_pct: float = 1.50     # round-trip bid/ask spread, stock options
    slippage_pct: float = 0.25         # additional adverse fill, each leg


class SimSignalEvent(BaseModel):
    time_iso: str
    timestamp_ms: int = 0
    strategy: str
    instrument: str
    direction: str
    strength: str
    entry: float
    stop: float
    target: float
    # The option leg this signal would be expressed through. `None` for a pure
    # spot signal; the UI falls back to `instrument` in that case.
    contract: Optional[str] = None
    spot: Optional[float] = None
    strike: Optional[float] = None
    opt_type: Optional[str] = None


class SimTradeEvent(BaseModel):
    trade_id: str
    entry_time_iso: str
    exit_time_iso: str = "OPEN"
    timestamp_ms: int = 0
    strategy: str
    symbol: str
    underlying: str
    direction: str
    opt_type: str
    strike: float
    lots: int
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    stop_loss: float
    target_price: float
    status: str = "OPEN"
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    duration_mins: int = 0
    # Theoretical prices before execution friction. `None` when the replay ran
    # in "ideal" mode — which is not the same as zero, and the UI renders the
    # difference (an em dash vs a ₹0.00).
    raw_entry: Optional[float] = None
    raw_exit: Optional[float] = None
    slippage: Optional[float] = None
    # The UNDERLYING levels this position is judged against. Carried on the
    # trade so a later bar can settle it, rather than the outcome being decided
    # from future bars at the moment of entry.
    spot_entry: Optional[float] = None
    spot_stop: Optional[float] = None
    spot_target: Optional[float] = None
    bars_held: int = 0


class SimStats(BaseModel):
    signals_fired: int = 0
    trades_entered: int = 0
    wins: int = 0
    losses: int = 0
    pnl: float = 0.0
    events: List[SimSignalEvent] = []
    trades: List[SimTradeEvent] = []
    # Total INR drag across all trades. `None` means friction was not modelled
    # at all; 0.0 would mean it was modelled and happened to be free.
    slippage_total: Optional[float] = None


class SimEvent(BaseModel):
    """One server-sent event.

    `kind` becomes the SSE `event:` name, so the client can register a handler
    per kind rather than sniffing the payload.
    """
    kind: str          # "state" | "frame" | "signal" | "trade"
    data: Dict[str, Any] = {}


class SimCapabilities(BaseModel):
    """What this build of the runner can actually do.

    The client renders optional columns, sections and controls off this rather
    than off whether a sampled row happened to carry a value. That inversion is
    the structural fix for a whole class of defect where the UI advertised a
    capability the engine did not have.
    """
    friction: bool = True
    contract_on_signal: bool = True
    absolute_seek: bool = True
    stream: bool = True
    delta_status: bool = True
    multi_day: bool = False
    resolutions: List[str] = ["1m", "5m", "15m"]


class SimStatus(BaseModel):
    state: SimState = SimState.IDLE
    config: Optional[SimConfig] = None
    # A finished session's ledger is worth keeping for review, but the client
    # has to be able to tell it apart from one that is still running. Without
    # this the dock showed a completed session's trades before you pressed play.
    session_id: Optional[str] = None
    session_complete: bool = False
    current_time_iso: str = ""
    progress_pct: float = 0.0
    bars_played: int = 0
    bars_total: int = 0
    stats: SimStats = SimStats()
    elapsed_real_s: float = 0.0
    status_message: str = ""
    last_signal: Optional[SimSignalEvent] = None
    capabilities: SimCapabilities = SimCapabilities()
    events_total: int = 0
    trades_total: int = 0
    open_positions: int = 0
    unrealised_pnl: float = 0.0


INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX"}

# Strike step per underlying. Anything not listed falls back to a percentage of
# spot, rounded to a sane increment.
STRIKE_STEP = {
    "NIFTY": 50.0, "BANKNIFTY": 100.0, "FINNIFTY": 50.0,
    "MIDCPNIFTY": 25.0, "SENSEX": 100.0, "BANKEX": 100.0,
}

# How far each moneyness label sits from ATM, in strike steps. Positive moves
# the strike in the direction that makes a CE cheaper (further out of the money).
MONEYNESS_OFFSET = {"ATM": 0, "ITM1": -1, "ITM2": -2, "OTM1": 1, "OTM2": 2}


def _is_index(symbol: str) -> bool:
    return symbol.upper() in INDEX_SYMBOLS


def _strike_step(symbol: str, spot: float) -> float:
    step = STRIKE_STEP.get(symbol.upper())
    if step:
        return step
    # Stocks: ~1% of spot, snapped to a familiar increment.
    for candidate in (2.5, 5.0, 10.0, 20.0, 50.0, 100.0):
        if spot * 0.01 <= candidate:
            return candidate
    return 100.0


def _pick_moneyness(config: Optional["SimConfig"]) -> str:
    """The first concrete leg the user asked for.

    `moneyness` may be "ALL" or a comma-joined list; a contract has to be one
    strike, so take the first concrete entry and fall back to ATM.
    """
    raw = (config.moneyness if config else "ATM") or "ATM"
    for part in str(raw).split(","):
        key = part.strip().upper()
        if key in MONEYNESS_OFFSET:
            return key
    return "ATM"


def _option_contract(
    symbol: str,
    spot: float,
    direction: str,
    config: Optional["SimConfig"] = None,
) -> Dict[str, Any]:
    """Resolve the option leg a signal on `symbol` at `spot` would be taken through.

    Returns the tradeable name, its strike, CE/PE, the lot size and an
    approximate premium. Used for BOTH the signal event and the trade, so the
    contract a user sees in the signals feed is the one the trade reports.
    """
    opt_type = "CE" if direction in ("BULLISH", "LONG") else "PE"
    step = _strike_step(symbol, spot)
    atm = round(spot / step) * step

    # An OTM call is a HIGHER strike; an OTM put is a LOWER one.
    offset = MONEYNESS_OFFSET.get(_pick_moneyness(config), 0)
    signed = offset if opt_type == "CE" else -offset
    strike = max(step, atm + signed * step)

    lot_size = 25 if _is_index(symbol) else 15
    # Rough premium: ~2% of spot at ATM, decaying as the strike moves away.
    intrinsic = max(0.0, (spot - strike) if opt_type == "CE" else (strike - spot))
    extrinsic = max(0.05, spot * 0.02 - abs(strike - atm) * 0.35)
    premium = round(intrinsic + extrinsic, 2)

    return {
        "contract": f"{symbol.upper()}26AUG{int(strike)}{opt_type}",
        "strike": float(strike),
        "opt_type": opt_type,
        "lot_size": lot_size,
        "premium": premium,
    }


def _apply_friction(
    raw_entry: float,
    raw_exit: float,
    symbol: str,
    config: Optional["SimConfig"],
) -> Tuple[float, float, str]:
    """Fill prices after bid/ask spread and slippage.

    You buy at the ask and sell at the bid, and each leg suffers an additional
    adverse slippage. Returns `(fill_entry, fill_exit, mode)`.

    In "ideal" mode the fills ARE the theoretical prices — that is a modelled
    zero, and the caller distinguishes it from "not modelled" by whether
    friction ran at all.
    """
    mode = (config.friction_mode if config else "realistic") or "realistic"
    if mode == "ideal":
        return raw_entry, raw_exit, "ideal"

    spread_pct = (config.index_spread_pct if config else 0.50) if _is_index(symbol) \
        else (config.stock_spread_pct if config else 1.50)
    slip_pct = (config.slippage_pct if config else 0.25)

    half_spread = spread_pct / 200.0     # round-trip pct → one-sided fraction
    slip = slip_pct / 100.0
    adverse = half_spread + slip

    fill_entry = round(raw_entry * (1.0 + adverse), 2)
    # A fill can be pushed to zero but never below it.
    fill_exit = round(max(0.05, raw_exit * (1.0 - adverse)), 2)
    return fill_entry, fill_exit, "realistic"


class SimulationRunner:
    """Singleton service that replays historical bars through the signal pipeline."""

    def __init__(self):
        self._state = SimState.IDLE
        self._config: Optional[SimConfig] = None
        self._task: Optional[asyncio.Task] = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # not paused initially
        self._stop_requested = False
        self._speed: float = 1.0
        self._stats = SimStats()
        self._current_time_iso = ""
        self._progress = 0.0
        self._bars_played = 0
        self._bars_total = 0
        self._start_real = 0.0
        self._candles: List[Dict] = []
        self._status_message = "Ready for simulation"
        self._last_signal: Optional[SimSignalEvent] = None
        self._current_sim_epoch: float = 0.0
        self._start_epoch: int = 0
        self._end_epoch: int = 0
        self._seek_requested_epoch: Optional[float] = None
        self._last_fired: Dict[Tuple[str, str], Tuple[str, int]] = {}
        # Fan-out to SSE subscribers. Bounded, and `_publish` drops FRAMES
        # under back-pressure but never a signal, trade or state change: a
        # dropped frame costs a progress tick, a dropped signal corrupts the
        # ledger the client is accumulating.
        self._subscribers: "List[asyncio.Queue[SimEvent]]" = []
        self._last_frame_at: float = 0.0
        # Positions currently open, per underlying. A replay that decides a
        # trade's outcome the instant it opens is not a replay.
        self._open_by_symbol: Dict[str, List[SimTradeEvent]] = {}
        self._session_id: Optional[str] = None
        self._session_complete: bool = False

    # ── SSE fan-out ─────────────────────────────────────────────────────

    def _publish(self, kind: str, data: Dict[str, Any]) -> None:
        if not self._subscribers:
            return
        event = SimEvent(kind=kind, data=data)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Only a frame may be dropped. For anything else, make room by
                # discarding the OLDEST frame still queued.
                if kind == "frame":
                    continue
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass

    def _publish_state(self) -> None:
        self._publish("state", {
            "state": self._state.value if hasattr(self._state, "value") else str(self._state),
            "status_message": self._status_message,
            "config": self._config.model_dump() if self._config else None,
            "bars_total": self._bars_total,
        })

    def _publish_frame(self, force: bool = False) -> None:
        """Throttled progress tick.

        10 Hz normally, 2 Hz once the replay is fast enough that a frame per
        update would be pure noise — at 5000x the clock advances hours per
        second and nobody can read it anyway.
        """
        now = time.monotonic()
        min_gap = 0.5 if self._speed >= 100 else 0.1
        if not force and (now - self._last_frame_at) < min_gap:
            return
        self._last_frame_at = now
        self._publish("frame", {
            "t": self._current_time_iso,
            "pct": self._progress,
            "bars_played": self._bars_played,
            "bars_total": self._bars_total,
            "elapsed_real_s": round(time.monotonic() - self._start_real, 1) if self._start_real else 0,
            "pnl": self._stats.pnl,
            "wins": self._stats.wins,
            "losses": self._stats.losses,
            "signals_fired": self._stats.signals_fired,
            "slippage_total": self._stats.slippage_total,
        })

    async def subscribe(self):
        """Yield events until the caller stops iterating."""
        q: "asyncio.Queue[SimEvent]" = asyncio.Queue(maxsize=512)
        self._subscribers.append(q)
        # Open with the current state so a client that connects mid-session is
        # not left blank until the next transition.
        try:
            q.put_nowait(SimEvent(kind="state", data={
                "state": self._state.value if hasattr(self._state, "value") else str(self._state),
                "status_message": self._status_message,
                "config": self._config.model_dump() if self._config else None,
                "bars_total": self._bars_total,
            }))
        except asyncio.QueueFull:
            pass
        try:
            while True:
                yield await q.get()
        finally:
            if q in self._subscribers:
                self._subscribers.remove(q)

    # ── Open book ───────────────────────────────────────────────────────

    MAX_HOLD_BARS = 30

    def _premium_for_spot(self, trade: SimTradeEvent, spot: float) -> float:
        """Option premium at `spot`, by the same delta approximation used at entry.

        ~50% of the underlying's move passes into the premium, floored just
        above zero — an option can expire worthless but cannot go negative.
        """
        entry_spot = trade.spot_entry if trade.spot_entry is not None else spot
        move = (spot - entry_spot) if trade.opt_type == "CE" else (entry_spot - spot)
        base = trade.raw_entry if trade.raw_entry is not None else trade.entry_price
        return round(max(0.05, base + move * 0.50), 2)

    def _settle_open_positions(self, bar: Dict[str, Any], bar_dt) -> None:
        """Advance every open position on this symbol by one bar.

        A position closes when THIS bar's range reaches its stop or target, or
        when it has been held too long — never from a bar the replay clock has
        not reached yet.
        """
        sym = bar.get("symbol")
        book = self._open_by_symbol.get(sym)
        if not book:
            return

        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        still_open: List[SimTradeEvent] = []

        for trade in book:
            trade.bars_held += 1
            bullish = trade.opt_type == "CE"
            stop = trade.spot_stop
            target = trade.spot_target

            exit_spot: Optional[float] = None
            if stop is not None and target is not None:
                if bullish:
                    # Stop first: the pessimistic read when one bar spans both,
                    # because a bar's high and low carry no ordering.
                    if low <= stop:
                        exit_spot = stop
                    elif high >= target:
                        exit_spot = target
                else:
                    if high >= stop:
                        exit_spot = stop
                    elif low <= target:
                        exit_spot = target

            timed_out = exit_spot is None and trade.bars_held >= self.MAX_HOLD_BARS
            if timed_out:
                exit_spot = close

            if exit_spot is None:
                # Still open — mark it to this bar so unrealised P&L moves.
                mark = self._premium_for_spot(trade, close)
                trade.pnl_usd = round((mark - trade.entry_price) * trade.quantity, 2)
                trade.pnl_pct = round(
                    ((mark - trade.entry_price) / trade.entry_price) * 100.0, 2
                ) if trade.entry_price > 0 else 0.0
                trade.duration_mins = trade.bars_held * self._bar_minutes()
                still_open.append(trade)
                continue

            self._close_position(trade, exit_spot, bar_dt)

        if still_open:
            self._open_by_symbol[sym] = still_open
        else:
            self._open_by_symbol.pop(sym, None)

    def _bar_minutes(self) -> int:
        from app.services.ohlcv_store import RESOLUTION_SECONDS
        res = self._config.resolution if self._config else "5m"
        return max(1, RESOLUTION_SECONDS.get(res, 300) // 60)

    def _close_position(self, trade: SimTradeEvent, exit_spot: float, bar_dt) -> None:
        raw_exit = self._premium_for_spot(trade, exit_spot)
        _, fill_exit, friction_mode = _apply_friction(
            trade.raw_entry if trade.raw_entry is not None else trade.entry_price,
            raw_exit,
            trade.underlying,
            self._config,
        )

        trade.exit_price = fill_exit
        trade.exit_time_iso = bar_dt.strftime("%H:%M:%S")
        trade.duration_mins = trade.bars_held * self._bar_minutes()
        trade.pnl_usd = round((fill_exit - trade.entry_price) * trade.quantity, 2)
        trade.pnl_pct = round(
            ((fill_exit - trade.entry_price) / trade.entry_price) * 100.0, 2
        ) if trade.entry_price > 0 else 0.0
        # Status follows the money actually made, so the win rate and the P&L
        # cannot disagree.
        trade.status = "WIN" if trade.pnl_usd > 0 else "LOSS"

        if friction_mode == "ideal":
            trade.raw_exit = None
        else:
            trade.raw_exit = raw_exit
            entry_slip = (trade.entry_price - (trade.raw_entry or trade.entry_price)) * trade.quantity
            exit_slip = (raw_exit - fill_exit) * trade.quantity
            trade.slippage = round(max(0.0, entry_slip + exit_slip), 2)

        self._recompute_totals()
        self._publish("trade", trade.model_dump())

    def _close_all_open(self, reason: str = "session end") -> None:
        """Leave end-of-session positions OPEN rather than inventing an exit.

        Force-closing them at the last close would book a fill the market never
        offered; the honest report is that the session ended with them open.
        """
        count = sum(len(v) for v in self._open_by_symbol.values())
        if count:
            log.info("Replay ended with %d position(s) still open (%s).", count, reason)
        self._open_by_symbol = {}

    def _recompute_totals(self) -> None:
        """Re-derive every aggregate from the trade ledger.

        Called after appending a trade and after a seek truncates the ledger, so
        the two paths can never drift. `slippage_total` stays `None` when no
        trade carried friction — "not modelled" and "modelled as zero" are
        different answers and the UI renders them differently.
        """
        trades = self._stats.trades
        self._stats.signals_fired = len(self._stats.events)
        self._stats.trades_entered = len(trades)
        self._stats.wins = len([tr for tr in trades if tr.status == "WIN"])
        self._stats.losses = len([tr for tr in trades if tr.status == "LOSS"])
        closed = [tr for tr in trades if tr.status in ("WIN", "LOSS")]
        # Realised only. Folding an open position's mark-to-market into the
        # headline number would label an unbooked gain as realised.
        self._stats.pnl = round(sum(tr.pnl_usd for tr in closed), 2)
        drag = [tr.slippage for tr in trades if tr.slippage is not None]
        self._stats.slippage_total = round(sum(drag), 2) if drag else None

    def _get_sim_now_ms(self) -> int:
        if self._current_sim_epoch > 0:
            return int(self._current_sim_epoch * 1000)
        return int(time.time() * 1000)

    @property
    def status(self) -> SimStatus:
        return self.status_since()

    def status_since(
        self,
        since_events: Optional[int] = None,
        since_trades: Optional[int] = None,
    ) -> SimStatus:
        """Current status, optionally carrying only rows the client has not seen.

        The full payload is O(session): a day of replay re-sends every signal and
        every trade on every poll. With offsets the client appends instead, and
        `events_total` / `trades_total` let it notice a reset (a seek truncates
        the ledger, so a total that went DOWN means "discard and refetch").
        """
        stats = self._stats
        if since_events is None and since_trades is None:
            payload = stats
        else:
            ev_from = max(0, since_events or 0)
            tr_from = max(0, since_trades or 0)
            # A truncation (seek/restart) invalidates the client's offsets.
            if ev_from > len(stats.events) or tr_from > len(stats.trades):
                ev_from = tr_from = 0
            payload = SimStats(
                signals_fired=stats.signals_fired,
                trades_entered=stats.trades_entered,
                wins=stats.wins,
                losses=stats.losses,
                pnl=stats.pnl,
                events=stats.events[ev_from:],
                trades=stats.trades[tr_from:],
                slippage_total=stats.slippage_total,
            )

        return SimStatus(
            state=self._state,
            config=self._config,
            current_time_iso=self._current_time_iso,
            progress_pct=self._progress,
            bars_played=self._bars_played,
            bars_total=self._bars_total,
            stats=payload,
            elapsed_real_s=round(time.monotonic() - self._start_real, 1) if self._start_real else 0,
            status_message=self._status_message,
            last_signal=self._last_signal,
            capabilities=self.capabilities,
            events_total=len(stats.events),
            trades_total=len(stats.trades),
            session_id=self._session_id,
            session_complete=self._session_complete,
            open_positions=sum(len(v) for v in self._open_by_symbol.values()),
            unrealised_pnl=round(
                sum(tr.pnl_usd for tr in stats.trades if tr.status == "OPEN"), 2
            ),
        )

    @property
    def capabilities(self) -> SimCapabilities:
        return SimCapabilities()

    async def start(self, config: SimConfig) -> SimStatus:
        if self._state in (SimState.RUNNING, SimState.LOADING, SimState.PAUSED):
            log.info("Simulation already running/paused. Stopping prior session before starting new one.")
            await self.stop()
        
        reset_all_engine_signals()
        self._config = config
        self._speed = config.speed
        self._state = SimState.LOADING
        self._stop_requested = False
        self._pause_event.set()
        self._stats = SimStats()
        self._bar_history = {}
        self._last_fired = {}
        self._open_by_symbol = {}
        self._session_id = f"{config.date}-{int(time.time())}"
        self._session_complete = False
        self._bars_played = 0
        self._seek_requested_epoch = None
        self._start_real = time.monotonic()
        self._task = asyncio.create_task(self._run_loop())
        return self.status

    async def stop(self) -> SimStatus:
        self._stop_requested = True
        self._pause_event.set()  # unblock if paused
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._state = SimState.IDLE
        self._task = None
        self._close_all_open("stopped")
        # The ledger survives for review, but it is now explicitly a FINISHED
        # session. Without this flag an idle runner handed every client a
        # completed session's signals and trades, which the dock rendered as
        # though the replay were live — results before you pressed play.
        self._session_complete = bool(self._stats.events or self._stats.trades)
        self._publish_state()
        return self.status

    def clear(self) -> SimStatus:
        """Discard a finished session's ledger. Refuses while one is running."""
        if self._state != SimState.IDLE:
            return self.status
        self._stats = SimStats()
        self._open_by_symbol = {}
        self._last_signal = None
        self._session_complete = False
        self._session_id = None
        self._current_time_iso = ""
        self._progress = 0.0
        self._bars_played = 0
        self._publish_state()
        return self.status

    async def pause(self) -> SimStatus:
        if self._state == SimState.RUNNING:
            self._state = SimState.PAUSED
            self._pause_event.clear()
            self._publish_state()
        return self.status

    async def resume(self) -> SimStatus:
        if self._state == SimState.PAUSED:
            self._state = SimState.RUNNING
            self._pause_event.set()
            self._publish_state()
        return self.status

    def set_speed(self, speed: float) -> SimStatus:
        self._speed = max(0.5, min(speed, 5000.0))
        return self.status

    def step_bars(self, count: int) -> SimStatus:
        from app.services.ohlcv_store import RESOLUTION_SECONDS
        if self._state == SimState.IDLE:
            return self.status
        res = self._config.resolution if self._config else "5m"
        res_sec = RESOLUTION_SECONDS.get(res, 300)
        target = self._current_sim_epoch + (count * res_sec)
        target = max(float(self._start_epoch), min(float(self._end_epoch), target))
        self._seek_requested_epoch = target
        return self.status

    def seek_to(
        self,
        bar_index: Optional[int] = None,
        to_pct: Optional[float] = None,
        to_time: Optional[str] = None,
    ) -> SimStatus:
        """Absolute seek, so a timeline drag commits as ONE request.

        A relative `bars_offset` forces the client either to issue a request per
        pointer move or to compute an offset from a `bars_played` that is moving
        underneath it. All three forms below clamp into the session.
        """
        if self._state == SimState.IDLE or self._end_epoch <= self._start_epoch:
            return self.status

        span = float(self._end_epoch - self._start_epoch)
        target: Optional[float] = None

        if bar_index is not None and self._candles:
            idx = max(0, min(len(self._candles) - 1, int(bar_index)))
            target = float(self._candles[idx]["time"])
        elif to_pct is not None:
            pct = max(0.0, min(100.0, float(to_pct)))
            target = self._start_epoch + span * (pct / 100.0)
        elif to_time is not None:
            parts = [int(x) for x in str(to_time).split(":")]
            while len(parts) < 3:
                parts.append(0)
            from datetime import datetime, timezone, timedelta
            try:
                from zoneinfo import ZoneInfo
                ist = ZoneInfo("Asia/Kolkata")
            except ImportError:
                ist = timezone(timedelta(hours=5, minutes=30))
            base = datetime.fromtimestamp(self._start_epoch, tz=ist)
            target = datetime(
                base.year, base.month, base.day,
                parts[0], parts[1], parts[2], tzinfo=ist,
            ).timestamp()

        if target is None:
            return self.status

        self._seek_requested_epoch = max(
            float(self._start_epoch), min(float(self._end_epoch), target)
        )
        return self.status

    def jump_start(self) -> SimStatus:
        if self._start_epoch > 0:
            self._seek_requested_epoch = float(self._start_epoch)
            self._stats = SimStats()
            self._last_signal = None
            self._last_fired.clear()
        return self.status

    def jump_end(self) -> SimStatus:
        if self._end_epoch > 0:
            self._seek_requested_epoch = float(self._end_epoch)
        return self.status

    async def _run_loop(self):
        """Main replay loop — fetch candles, then step through them."""
        from app.services.ohlcv_store import get_candles as ohlcv_get, RESOLUTION_SECONDS
        from datetime import datetime, timezone, timedelta
        try:
            from zoneinfo import ZoneInfo
            ist = ZoneInfo("Asia/Kolkata")
        except ImportError:
            ist = timezone(timedelta(hours=5, minutes=30))

        cfg = self._config
        if not cfg:
            self._state = SimState.IDLE
            return

        try:
            day = datetime.strptime(cfg.date, "%Y-%m-%d")
        except ValueError:
            log.error("Invalid simulation date: %s", cfg.date)
            self._status_message = f"Invalid session date: {cfg.date}"
            self._state = SimState.IDLE
            return

        # The loop derives start/end from `cfg.date` alone, so a differing
        # `end_date` would silently replay one day while the UI claimed a range.
        # Refuse it out loud instead; `capabilities.multi_day` advertises this.
        if cfg.end_date and cfg.end_date != cfg.date:
            log.warning(
                "Multi-day replay requested (%s..%s) but the runner replays a single session.",
                cfg.date, cfg.end_date,
            )
            self._status_message = (
                f"Multi-day ranges are not supported yet ({cfg.date} to {cfg.end_date}). "
                "Replay one session at a time."
            )
            self._state = SimState.IDLE
            return

        # Build start/end timestamps in IST
        start_parts = [int(x) for x in cfg.start_time.split(":")]
        end_parts = [int(x) for x in cfg.end_time.split(":")]
        start_dt = datetime(day.year, day.month, day.day, start_parts[0], start_parts[1], start_parts[2] if len(start_parts) > 2 else 0, tzinfo=ist)
        end_dt = datetime(day.year, day.month, day.day, end_parts[0], end_parts[1], end_parts[2] if len(end_parts) > 2 else 0, tzinfo=ist)
        start_epoch = int(start_dt.timestamp())
        end_epoch = int(end_dt.timestamp())

        res = cfg.resolution or "5m"
        res_sec = RESOLUTION_SECONDS.get(res, 300)

        # Determine instruments (NSE Indian Markets only)
        default_inst = [
            "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX",
            "HDFCBANK", "ICICIBANK", "SBIN", "RELIANCE", "BHARTIARTL",
            "AXISBANK", "KOTAKBANK", "INFY", "BAJFINANCE", "ADANIENT",
            "LT", "TCS", "BAJAJFINSV", "ADANIPORTS", "TATASTEEL"
        ]
        instruments = cfg.instruments if cfg.instruments else default_inst

        self._status_message = f"⚡ Fetching historical candles for {cfg.date} from Zerodha Kite API..."
        warmup_start = start_epoch - 5 * 86400
        await _hydrate_missing_candles(instruments, res, warmup_start, end_epoch)

        # Pre-seed indicator history with pre-session bars so indicators are ready at 09:15 AM
        self._bar_history = {}
        for sym in instruments:
            prior_candles = ohlcv_get(sym, res, limit=50, since=warmup_start)
            p_bars = [{**c, "symbol": sym, "resolution": res} for c in prior_candles if c["time"] < start_epoch]
            if len(p_bars) < 20:
                p_bars = _generate_warmup_candles(sym, res, start_epoch, count=20, res_sec=res_sec) + p_bars
            self._bar_history[sym] = p_bars[-50:]

        # Fetch candles for each instrument from local store
        all_bars: List[Dict[str, Any]] = []
        for sym in instruments:
            candles = ohlcv_get(sym, res, limit=5000, since=start_epoch)
            for c in candles:
                if start_epoch <= c["time"] <= end_epoch:
                    all_bars.append({**c, "symbol": sym, "resolution": res})

        # Sort by time
        all_bars.sort(key=lambda b: b["time"])

        if not all_bars:
            self._status_message = f"Generating session candles for {cfg.date}..."
            log.info("No remote or local candles found for simulation date %s; generating session candles...", cfg.date)
            for sym in instruments:
                all_bars.extend(_generate_synthetic_candles(sym, res, start_epoch, end_epoch, res_sec))
            all_bars.sort(key=lambda b: b["time"])

        if not all_bars:
            log.warning("No candles available for simulation date %s", cfg.date)
            self._status_message = f"No candles available for {cfg.date}"
            self._state = SimState.IDLE
            return

        self._candles = all_bars
        self._bars_total = len(all_bars)
        self._state = SimState.RUNNING
        self._publish_state()
        self._status_message = f"Playing {cfg.date} ({len(all_bars)} bars)..."
        log.info("Simulation started: %s, %d bars, speed %.1fx", cfg.date, self._bars_total, self._speed)

        self._start_epoch = start_epoch
        self._end_epoch = end_epoch
        self._current_sim_epoch = float(start_epoch)

        try:
            total_sim_seconds = float(max(1, end_epoch - start_epoch))
            bar_idx = 0

            while self._current_sim_epoch <= end_epoch and not self._stop_requested:
                await self._pause_event.wait()
                if self._stop_requested:
                    break

                # Handle seek/rewind requests
                if self._seek_requested_epoch is not None:
                    target = self._seek_requested_epoch
                    self._seek_requested_epoch = None
                    self._current_sim_epoch = target
                    # Reset bar pointer to match target epoch
                    bar_idx = 0
                    while bar_idx < len(all_bars) and all_bars[bar_idx]["time"] <= target:
                        bar_idx += 1
                    self._bars_played = bar_idx
                    # Filter event stats & trades up to seek target
                    target_ms = int(target * 1000)
                    self._stats.events = [ev for ev in self._stats.events if ev.timestamp_ms <= target_ms]
                    self._stats.trades = [tr for tr in self._stats.trades if tr.timestamp_ms <= target_ms]
                    # Rebuild the open book from what survived, or a position
                    # seeked past would keep settling against bars that no
                    # longer follow it.
                    self._open_by_symbol = {}
                    for tr in self._stats.trades:
                        if tr.status == "OPEN":
                            self._open_by_symbol.setdefault(tr.underlying, []).append(tr)
                    self._recompute_totals()
                    self._last_signal = self._stats.events[-1] if self._stats.events else None
                    # Reset bar history and dedup state for clean indicator recalculation
                    self._bar_history = {}
                    self._last_fired = {}

                # Dynamic update tick interval (30ms for >=500x, 50ms for >=50x, 100ms otherwise)
                dt = 0.03 if self._speed >= 500 else (0.05 if self._speed >= 50 else 0.1)

                # Dynamic second-by-second clock & progress update
                bar_dt = datetime.fromtimestamp(self._current_sim_epoch, tz=ist)
                self._current_time_iso = bar_dt.strftime("%H:%M:%S")
                self._progress = round(min(100.0, max(0.0, (self._current_sim_epoch - start_epoch) / total_sim_seconds * 100.0)), 1)
                self._publish_frame()

                # Process bars up to current simulated timestamp
                while bar_idx < len(all_bars) and self._current_sim_epoch >= all_bars[bar_idx]["time"]:
                    bar = all_bars[bar_idx]
                    self._bars_played = bar_idx + 1
                    self._evaluate_bar(bar, datetime.fromtimestamp(bar["time"], tz=ist))
                    bar_idx += 1

                # Advance simulated clock by speed * dt
                self._current_sim_epoch += self._speed * dt

                # Real-time sleep step
                await asyncio.sleep(dt)

        except asyncio.CancelledError:
            log.info("Simulation cancelled")
        except Exception as exc:
            log.error("Simulation error: %s", exc, exc_info=True)
        finally:
            if not self._stop_requested:
                self._state = SimState.IDLE
                self._close_all_open("reached session end")
                self._session_complete = bool(self._stats.events or self._stats.trades)
                self._publish_frame(force=True)
                self._publish_state()
                log.info(
                    "Simulation complete: %d bars, %d signals, P&L %.2f",
                    self._bars_played, self._stats.signals_fired, self._stats.pnl,
                )

    def get_directional_signals_response(self) -> Dict[str, Any]:
        """Return signals formatted for /api/v1/directional/signals matching the active simulation date."""
        cfg = self._config
        sim_date = cfg.date if cfg else "2026-08-28"
        now_ms = self._get_sim_now_ms()

        signals = []
        current_events = [ev for ev in self._stats.events if ev.timestamp_ms <= now_ms or ev.timestamp_ms == 0]
        for ev in current_events:
            signals.append({
                "underlying": ev.instrument,
                "has_options": True,
                "spot_price": ev.entry,
                "ivr": 25.0,
                "green_arrow": ev.direction == "BULLISH",
                "red_arrow": ev.direction == "BEARISH",
                "state": "ENTRY_ARMED" if ev.strength == "STRONG" else "SETUP_ACTIVE",
                "direction": ev.direction.lower(),
                "regime": "SIMULATION_REPLAY",
                "score_long": 85.0 if ev.direction == "BULLISH" else 15.0,
                "score_short": 85.0 if ev.direction == "BEARISH" else 15.0,
                "exec_mode": "paper",
                "exec_confidence": 0.88,
                "signal_score": 90.0 if ev.strength == "STRONG" else 65.0,
                "signal_strength": ev.strength,
                "track": "vcp" if ev.strategy == "vcp" else ("mean_reversion" if ev.strategy == "adaptive_edge" else "trend_following"),
                "strategy": ev.strategy,
                "regime_score": 15.0,
                "stop_price": ev.stop,
                "target_price": ev.target,
                "atr": round(abs(ev.target - ev.entry) / 3.0, 2),
                "adx": 32.5,
                "atr_percentile": 65.0,
                "rsi": 58.0,
                "squeezed": False,
                "rec_leverage": 10,
                "futures_symbol": f"{ev.instrument}FUT",
                "fresh": True,
                "timestamp_ms": ev.timestamp_ms if ev.timestamp_ms > 0 else now_ms,
                "simulated_date": sim_date,
                "simulated_time": ev.time_iso,
            })

        return {
            "signals": signals,
            "count": len(signals),
            "timestamp": int(now_ms / 1000),
            "mode": "simulation",
            "simulated_date": sim_date,
        }

    def get_kite_signals_response(self) -> Dict[str, Any]:
        """Return signals formatted for Kite Engine signal responses during simulation."""
        now_ms = self._get_sim_now_ms()
        KITE_TOKENS: Dict[str, int] = {
            "NIFTY": 256265,
            "BANKNIFTY": 260101,
            "FINNIFTY": 257001,
            "MIDCPNIFTY": 288001,
            "SENSEX": 265,
            "RELIANCE": 738561,
            "TATASTEEL": 895745,
            "HDFCBANK": 341249,
            "ICICIBANK": 12705,
            "SBIN": 779521,
            "BHARTIARTL": 2714625,
            "AXISBANK": 1510401,
            "KOTAKBANK": 492033,
            "INFY": 408065,
            "BAJFINANCE": 81153,
            "ADANIENT": 6401,
            "LT": 2939649,
            "TCS": 2953217,
            "BAJAJFINSV": 4267265,
            "ADANIPORTS": 3861249,
        }
        cfg_lots = max(1, self._config.lots) if self._config else 1
        cfg_money = (self._config.moneyness if self._config and self._config.moneyness else "ATM").upper()
        sim_date = self._config.date if self._config else "2026-08-28"

        rows = []
        current_events = [ev for ev in self._stats.events if ev.timestamp_ms <= now_ms or ev.timestamp_ms == 0]
        for ev in current_events:
            ev_ms = ev.timestamp_ms if ev.timestamp_ms > 0 else now_ms
            is_long = ev.direction.upper() in ("BULLISH", "LONG", "BUY")
            direction_str = "long" if is_long else "short"
            regime_str = "BULL" if is_long else "BEAR"
            opt_type = "CE" if is_long else "PE"
            token_val = KITE_TOKENS.get(ev.instrument.upper(), 256265)
            atm_strike = round(ev.entry / 50.0) * 50.0

            moneyness_types = ["ITM1", "ATM", "OTM1"] if cfg_money == "ALL" else [cfg_money]
            legs = []

            for m_type in moneyness_types:
                strike_offset = 0.0
                if m_type == "ITM1":
                    strike_offset = -50.0 if is_long else 50.0
                elif m_type == "ITM2":
                    strike_offset = -100.0 if is_long else 100.0
                elif m_type == "OTM1":
                    strike_offset = 50.0 if is_long else -50.0
                elif m_type == "OTM2":
                    strike_offset = 100.0 if is_long else -100.0

                s_val = atm_strike + strike_offset
                legs.append({
                    "moneyness": m_type,
                    "option_type": opt_type,
                    "option_symbol": f"{ev.instrument}26AUG{int(s_val)}{opt_type}",
                    "strike": s_val,
                    "expiry": sim_date,
                    "premium_spot": round(ev.entry * 0.02, 2),
                    "premium_sl": round(ev.entry * 0.015, 2),
                    "entry_sl": round(ev.entry * 0.01, 2),
                    "lots": cfg_lots,
                    "is_active": True,
                    "signal_timestamp_ms": ev_ms,
                    "entry_timestamp_ms": ev_ms,
                })

            rows.append({
                "underlying": ev.instrument,
                "token": token_val,
                "exchange": "NSE",
                "regime": regime_str,
                "alignment": {"fast": 1 if is_long else -1, "mid": 1 if is_long else -1, "slow": 1 if is_long else -1},
                "direction": direction_str,
                "option_type": opt_type,
                "legs": legs,
                "spot": ev.entry,
                "underlying_spot": ev.entry,
                "stop_loss": ev.stop,
                "entry_sl": ev.stop,
                "target": ev.target,
                "score": 90.0 if ev.strength == "STRONG" else 65.0,
                "timestamp_ms": ev_ms,
                "is_active": True,
                "is_fresh": True,
                "source": "spot",
            })

        return {
            "generated_ms": now_ms,
            "scanning": False,
            "scanning_label": "SIMULATION_REPLAY",
            "rows": rows,
            "next_scan_ms": 0,
            "auto_scan": False,
            "market_open": True,
        }

    def get_scalping_signals_response(self) -> Dict[str, Any]:
        """Return signals formatted for /api/v1/sterling-engine/signals during simulation."""
        now_ms = self._get_sim_now_ms()
        signals = []
        current_events = [ev for ev in self._stats.events if ev.timestamp_ms <= now_ms or ev.timestamp_ms == 0]
        for ev in current_events:
            ev_ms = ev.timestamp_ms if ev.timestamp_ms > 0 else now_ms
            signals.append({
                "signal_id": f"sim_{ev.instrument}_{ev.time_iso}",
                "symbol": ev.instrument,
                "strategy": ev.strategy,
                "direction": ev.direction,
                "state": "ARMED" if ev.strength == "STRONG" else "ACTIVE",
                "entry_price": ev.entry,
                "stop_loss": ev.stop,
                "take_profit": ev.target,
                "confidence": 0.88,
                "timestamp_ms": ev_ms,
            })
        return {
            "signals": signals,
            "armed_count": len([s for s in signals if s["state"] == "ARMED"]),
            "total_signals": len(signals),
        }

    def get_v2_signals_response(self) -> Dict[str, Any]:
        """Return signals formatted for /api/v1/sterling-v2/signals during simulation."""
        now_ms = self._get_sim_now_ms()
        signals = []
        current_events = [ev for ev in self._stats.events if ev.timestamp_ms <= now_ms or ev.timestamp_ms == 0]
        for ev in current_events:
            ev_ms = ev.timestamp_ms if ev.timestamp_ms > 0 else now_ms
            signals.append({
                "id": f"sim_v2_{ev.instrument}_{ev.time_iso}",
                "symbol": ev.instrument,
                "track": ev.strategy,
                "direction": ev.direction.lower(),
                "entry": ev.entry,
                "stop": ev.stop,
                "target": ev.target,
                "confidence": 0.90,
                "timestamp_ms": ev_ms,
            })
        return {"signals": signals, "total": len(signals)}

    def get_navigator_signals_response(self) -> Dict[str, Any]:
        """Return signals formatted for /api/v1/navigator/signals during simulation."""
        now_ms = self._get_sim_now_ms()
        items = []
        current_events = [ev for ev in self._stats.events if ev.timestamp_ms <= now_ms or ev.timestamp_ms == 0]
        for ev in current_events:
            ev_ms = ev.timestamp_ms if ev.timestamp_ms > 0 else now_ms
            items.append({
                "event_id": f"nav_sim_{ev.instrument}_{ev.time_iso}",
                "underlying": ev.instrument,
                "strategy": ev.strategy,
                "direction": ev.direction,
                "generated_at_ms": ev_ms,
                "spot_price": ev.entry,
                "score": 88.0,
                "armed": ev.strength == "STRONG",
            })
        return {"items": items, "next_cursor": None, "has_more": False, "simulated": True}

    def get_adaptive_edge_snapshot(self) -> Dict[str, Any]:
        """Return snapshot for Adaptive Edge UI during simulation."""
        now_ms = self._get_sim_now_ms()
        candidates = []
        current_events = [ev for ev in self._stats.events if ev.timestamp_ms <= now_ms or ev.timestamp_ms == 0]
        for ev in current_events:
            ev_ms = ev.timestamp_ms if ev.timestamp_ms > 0 else now_ms
            is_long = ev.direction.upper() in ("BULLISH", "LONG", "BUY")
            opt_type = "CE" if is_long else "PE"
            strike_val = round(ev.entry / 50.0) * 50.0
            candidates.append({
                "symbol": f"{ev.instrument}26AUG{int(strike_val)}{opt_type}",
                "underlying": ev.instrument,
                "direction": ev.direction.lower(),
                "entry_price": ev.entry,
                "stop_loss": ev.stop,
                "take_profit": ev.target,
                "score": 0.88,
                "armed": ev.strength == "STRONG",
                "timestamp_ms": ev_ms,
            })
        return {
            "readiness": {
                "executable": True,
                "reason": None,
                "promotion_gate_reason": None,
            },
            "scan": {
                "underlyings": len(set(ev.instrument for ev in current_events)) or 1,
                "chains_read": 8,
                "listed": 40,
                "tradeable": 25,
                "candidates": candidates,
                "signals": candidates,
                "skipped": {},
                "dropped": {},
                "errors": [],
            },
            "session": {
                "entries": len(candidates),
                "win_rate": 0.62,
                "realised_pnl_today": self._stats.pnl,
            },
            "warnings": [],
        }

    def get_atm_imbalance_snapshot(self) -> Dict[str, Any]:
        """Return snapshot for ATM Premium Imbalance strategy during simulation."""
        now_ms = self._get_sim_now_ms()
        current_events = [ev for ev in self._stats.events if ev.timestamp_ms <= now_ms or ev.timestamp_ms == 0]
        first_event = current_events[0] if current_events else None
        sym = first_event.instrument if first_event else "NIFTY"
        price = first_event.entry if first_event else 24175.0
        strike_val = round(price / 50.0) * 50.0

        return {
            "strategy": {
                "id": "atm_premium_imbalance",
                "name": "ATM Premium Imbalance",
                "contract_version": "v1",
                "tagline": "Exploits institutional ATM CE/PE premium skew",
                "how_it_works": "Monitors ATM CE vs PE premium divergence during market replay.",
                "provenance": "Sterling Quantitative Research",
                "live_ready": True,
                "enabled": True,
            },
            "config": {
                "enabled": True,
                "underlying": sym,
                "expiry_policy": "SAME_DAY",
                "explicit_expiry": self._config.date if self._config else "2026-08-28",
                "strike_policy": "ATM",
                "session_start": "09:15:00",
                "session_end": "15:30:00",
                "quote_mode": "SYNCHRONIZED",
                "sizing_mode": "LOTS",
                "lots": 1,
                "stop_basis": "PERCENT",
                "stop_percent": 15.0,
                "signal_mode": "SKEW_BREAKOUT",
                "minimum_difference": 10.0,
                "data_source": "kite",
                "execution_mode": "paper",
            },
            "defaults": {},
            "vocabularies": {},
            "research_only": {"entry_price_policy": [], "exit_policy": []},
            "live_blockers": [],
            "session": {
                "armed": True,
                "finished": False,
                "session_date": self._config.date if self._config else "2026-08-28",
                "session_open_ms": now_ms - 3600000,
                "phase": "ARMED",
                "halt_reason": None,
                "underlying": sym,
                "expiry": self._config.date if self._config else "2026-08-28",
                "strike": strike_val,
                "quantity": 25,
                "execution_mode": "paper",
                "quote_mode": "SYNCHRONIZED",
                "protection_mode": "RESTING_TARGET_LIMIT",
                "trades_taken": len(current_events),
                "legs": {
                    "CE": {
                        "instrument_id": f"NSE:{sym}26AUG{int(strike_val)}CE",
                        "tradingsymbol": f"{sym}26AUG{int(strike_val)}CE",
                        "option_type": "CE",
                        "lot_size": 25,
                        "ltp": round(price * 0.02, 2),
                        "bid": round(price * 0.019, 2),
                        "ask": round(price * 0.021, 2),
                        "last_trade_ts_ms": now_ms,
                        "session_origin": True,
                        "age_ms": 100,
                        "official_open": round(price * 0.02, 2),
                    },
                    "PE": {
                        "instrument_id": f"NSE:{sym}26AUG{int(strike_val)}PE",
                        "tradingsymbol": f"{sym}26AUG{int(strike_val)}PE",
                        "option_type": "PE",
                        "lot_size": 25,
                        "ltp": round(price * 0.015, 2),
                        "bid": round(price * 0.014, 2),
                        "ask": round(price * 0.016, 2),
                        "last_trade_ts_ms": now_ms,
                        "session_origin": True,
                        "age_ms": 100,
                        "official_open": round(price * 0.015, 2),
                    },
                },
                "difference": round(price * 0.005, 2),
                "cheaper_leg": "PE",
                "signal": {
                    "action": "BUY_CE" if (first_event and first_event.direction == "BULLISH") else "BUY_PE",
                    "reason": "Premium skew divergence exceeds minimum threshold",
                    "option_type": "CE" if (first_event and first_event.direction == "BULLISH") else "PE",
                },
                "trade": None,
            },
        }

    def get_bear_to_bearish_snapshot(self) -> Dict[str, Any]:
        """Return snapshot for Bear to Bearish Strategy during simulation."""
        now_ms = self._get_sim_now_ms()
        rows = []
        current_events = [ev for ev in self._stats.events if ev.timestamp_ms <= now_ms or ev.timestamp_ms == 0]
        for ev in current_events:
            if ev.direction.upper() in ("BEARISH", "SHORT", "SELL") or ev.strategy == "bear_to_bearish":
                ev_ms = ev.timestamp_ms if ev.timestamp_ms > 0 else now_ms
                strike_val = round(ev.entry / 50.0) * 50.0
                rows.append({
                    "id": f"bear_sim_{ev.instrument}_{ev.time_iso}",
                    "underlying": ev.instrument,
                    "symbol": f"{ev.instrument}26AUG{int(strike_val)}PE",
                    "exchange": "NFO",
                    "direction": "BEARISH",
                    "status": "ARMED" if ev.strength == "STRONG" else "ACTIVE",
                    "timestamp_ms": ev_ms,
                    "pcr_open": 1.15,
                    "pcr_current": 0.72,
                    "pcr_change_5m": -0.08,
                    "lower_high_price": round(ev.entry * 1.005, 2),
                    "spot_price": ev.entry,
                    "spot_sl": ev.stop,
                    "spot_target": ev.target,
                    "option_premium": round(ev.entry * 0.02, 2),
                    "entry_price": ev.entry,
                    "stop_loss": ev.stop,
                    "target_price": ev.target,
                    "score": 92 if ev.strength == "STRONG" else 75,
                    "reason": "PCR breakdown below 0.80 + Lower-high structure breach",
                    "option_type": "PE",
                    "strike": strike_val,
                    "expiry": self._config.date if self._config else "2026-08-28",
                    "lot_size": 25 if ev.instrument == "NIFTY" else 15,
                    "quote_key": f"NSE:{ev.instrument}",
                })
        return {
            "generated_ms": now_ms,
            "scanning": False,
            "scanning_label": "SIMULATION_REPLAY",
            "rows": rows,
            "pcr_history": [{"timestamp_ms": now_ms - 300000, "pcr": 0.85}, {"timestamp_ms": now_ms, "pcr": 0.72}],
            "config": {
                "pcr_threshold": 0.80,
                "auto_execute": False,
            },
            "next_scan_ms": 0,
            "auto_scan": False,
            "market_open": True,
            "is_paper": True,
            "auto_execute": False,
        }

    def get_nifty_orb_signals_response(self) -> Dict[str, Any]:
        """Return signals formatted for /api/v1/nifty-orb-options/scan during simulation."""
        now_ms = self._get_sim_now_ms()
        signals = []
        current_events = [ev for ev in self._stats.events if ev.timestamp_ms <= now_ms or ev.timestamp_ms == 0]
        for ev in current_events:
            ev_ms = ev.timestamp_ms if ev.timestamp_ms > 0 else now_ms
            signals.append({
                "symbol": ev.instrument,
                "kind": "INDEX" if "NIFTY" in ev.instrument else "EQUITY",
                "direction": ev.direction,
                "regime": "ORB_EXPANSION",
                "confidence": 0.88,
                "timestamp_ms": ev_ms,
                "or_high": round(ev.entry * 1.005, 2),
                "or_low": round(ev.entry * 0.995, 2),
                "vwap": round(ev.entry * 0.998, 2),
                "atr": round(ev.entry * 0.01, 2),
            })
        return {
            "count": len(signals),
            "signals": signals,
        }


    def _evaluate_bar(self, bar: Dict, bar_dt):
        """Evaluate strategy signals on every replay bar.
        
        Triggers SuperTrend crossovers, VCP squeeze breakouts, Adaptive Edge
        reversals, and Bear to Bearish breakdowns across instruments.
        """
        # Advance the open book first: a position opened earlier can close on
        # THIS bar, and it must do so before a new signal is considered.
        self._settle_open_positions(bar, bar_dt)

        import random
        from datetime import timedelta

        if not hasattr(self, '_bar_history'):
            self._bar_history: Dict[str, List[Dict]] = {}

        sym = bar.get("symbol", "UNKNOWN")
        if sym not in self._bar_history:
            self._bar_history[sym] = []
        self._bar_history[sym].append(bar)

        # Keep last 50 bars per instrument
        if len(self._bar_history[sym]) > 50:
            self._bar_history[sym] = self._bar_history[sym][-50:]

        history = self._bar_history[sym]

        close = float(bar["close"])
        high = float(bar["high"])
        low = float(bar["low"])
        opens = float(bar["open"])

        if len(history) < 2:
            return

        prev_bar = history[-2]
        prev_close = float(prev_bar["close"])

        closes = [float(b["close"]) for b in history]
        sma5 = sum(closes[-5:]) / min(len(closes), 5)
        sma20 = sum(closes[-20:]) / min(len(closes), 20)

        # Simple ATR estimate
        highs = [float(b["high"]) for b in history[-14:]]
        lows = [float(b["low"]) for b in history[-14:]]
        ranges = [h - l for h, l in zip(highs, lows)]
        atr = sum(ranges) / len(ranges) if ranges else max(0.01, close * 0.005)

        # Simple RSI calculation
        gains = []
        losses = []
        for j in range(1, min(len(closes), 15)):
            diff = closes[-j] - closes[-j-1] if j+1 <= len(closes) else 0
            if diff > 0:
                gains.append(diff)
            else:
                losses.append(abs(diff))
        avg_gain = sum(gains) / max(len(gains), 1)
        avg_loss = sum(losses) / max(len(losses), 1)
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = 100 - (100 / (1 + rs))

        signals_to_fire = []

        # 1. SuperTrend (Trend crossover / expansion)
        if (sma5 > sma20 and (close >= float(prev_bar["high"]) or (close > opens and close > sma5))):
            signals_to_fire.append({
                "strategy": "supertrend",
                "direction": "BULLISH",
                "strength": "STRONG" if (close - opens) >= 0.5 * atr else "MODERATE",
            })
        elif (sma5 < sma20 and (close <= float(prev_bar["low"]) or (close < opens and close < sma5))):
            signals_to_fire.append({
                "strategy": "supertrend",
                "direction": "BEARISH",
                "strength": "STRONG" if (opens - close) >= 0.5 * atr else "MODERATE",
            })

        # 2. VCP Squeeze Breakout (Range expansion after contraction)
        prev_range = float(prev_bar["high"]) - float(prev_bar["low"])
        if len(history) >= 4 and prev_range < 0.8 * atr and abs(close - opens) > 1.0 * atr:
            signals_to_fire.append({
                "strategy": "vcp",
                "direction": "BULLISH" if close >= opens else "BEARISH",
                "strength": "STRONG",
            })

        # 3. Adaptive Edge (RSI Extreme Reversals)
        if rsi < 35 and close > opens:
            signals_to_fire.append({
                "strategy": "adaptive_edge",
                "direction": "BULLISH",
                "strength": "STRONG" if rsi < 25 else "MODERATE",
            })
        elif rsi > 65 and close < opens:
            signals_to_fire.append({
                "strategy": "adaptive_edge",
                "direction": "BEARISH",
                "strength": "STRONG" if rsi > 75 else "MODERATE",
            })

        # 4. Bear to Bearish Breakdown
        if sma5 < sma20 and close < float(prev_bar["low"]) and close < opens and rsi < 45:
            signals_to_fire.append({
                "strategy": "bear_to_bearish",
                "direction": "BEARISH",
                "strength": "STRONG",
            })

        # 5. ATM Premium Imbalance (Institutional Skew Expansion)
        if len(history) >= 3 and abs(close - opens) > 1.2 * atr:
            signals_to_fire.append({
                "strategy": "atm_imbalance",
                "direction": "BULLISH" if close >= opens else "BEARISH",
                "strength": "STRONG",
            })

        # 6. Navigator (AVWAP & Volatility Trend)
        if len(history) >= 5 and sma5 > sma20 and close > sma5 and rsi > 52:
            signals_to_fire.append({
                "strategy": "navigator",
                "direction": "BULLISH",
                "strength": "STRONG",
            })
        elif len(history) >= 5 and sma5 < sma20 and close < sma5 and rsi < 48:
            signals_to_fire.append({
                "strategy": "navigator",
                "direction": "BEARISH",
                "strength": "STRONG",
            })

        # 7. Nifty ORB Options (Opening Range Breakout after 09:30 IST)
        if len(history) >= 4:
            first_bars = history[:3]
            or_high = max(float(b["high"]) for b in first_bars)
            or_low = min(float(b["low"]) for b in first_bars)
            if close > or_high and close > opens:
                signals_to_fire.append({
                    "strategy": "nifty_orb",
                    "direction": "BULLISH",
                    "strength": "STRONG",
                })
            elif close < or_low and close < opens:
                signals_to_fire.append({
                    "strategy": "nifty_orb",
                    "direction": "BEARISH",
                    "strength": "STRONG",
                })

        # Track recent signals per (symbol, strategy) to prevent flood
        if not hasattr(self, '_last_fired'):
            self._last_fired: Dict[Tuple[str, str], Tuple[str, int]] = {}
        # Fan-out to SSE subscribers. Bounded, and `_publish` drops FRAMES
        # under back-pressure but never a signal, trade or state change: a
        # dropped frame costs a progress tick, a dropped signal corrupts the
        # ledger the client is accumulating.
        self._subscribers: "List[asyncio.Queue[SimEvent]]" = []
        self._last_frame_at: float = 0.0

        current_bar_idx = self._bars_played

        # Emit all generated strategy signals for this bar (or filter by selected strategies)
        cfg_strats = [s.lower() for s in (self._config.strategies if self._config and self._config.strategies else [self._config.strategy if self._config else "all"])]
        allow_all = "all" in cfg_strats or "*" in cfg_strats or not cfg_strats

        for sdef in signals_to_fire:
            strategy = sdef["strategy"]
            if not allow_all and strategy.lower() not in cfg_strats:
                continue
            direction = sdef["direction"]
            strength = sdef["strength"]

            key = (sym, strategy)
            last_dir, last_idx = self._last_fired.get(key, ("", -1))
            # De-duplicate: do not re-emit identical direction within 6 bars (30 minutes)
            if last_dir == direction and (current_bar_idx - last_idx) < 6:
                continue

            self._last_fired[key] = (direction, current_bar_idx)

            if direction == "BULLISH":
                stop = round(close - 1.5 * atr, 2)
                target = round(close + 2.5 * atr, 2)
            else:
                stop = round(close + 1.5 * atr, 2)
                target = round(close - 2.5 * atr, 2)

            leg = _option_contract(sym, close, direction, self._config)
            event = SimSignalEvent(
                time_iso=bar_dt.strftime("%H:%M:%S"),
                timestamp_ms=int(bar_dt.timestamp() * 1000),
                strategy=strategy,
                instrument=sym,
                direction=direction,
                strength=strength,
                entry=round(close, 2),
                stop=stop,
                target=target,
                contract=leg["contract"],
                spot=round(close, 2),
                strike=leg["strike"],
                opt_type=leg["opt_type"],
            )
            self._stats.signals_fired += 1
            self._stats.events.append(event)
            self._last_signal = event
            self._publish("signal", event.model_dump())

            if strength == "STRONG":
                # OPEN the position. Its outcome is decided by later bars, in
                # `_settle_open_positions`, as the simulated clock reaches them.
                # This used to scan up to 30 FUTURE bars right here and write
                # the exit price, exit time and WIN/LOSS in one go — so every
                # trade appeared already finished, with an exit timestamped
                # minutes ahead of the replay clock.
                cfg_lots = max(1, self._config.lots) if self._config else 1
                lot_size = leg["lot_size"]
                qty = cfg_lots * lot_size
                raw_entry_p = leg["premium"]
                entry_p, _, friction_mode = _apply_friction(
                    raw_entry_p, raw_entry_p, sym, self._config
                )
                entry_slip = round((entry_p - raw_entry_p) * qty, 2)

                trade = SimTradeEvent(
                    trade_id=f"TRD-{1000 + len(self._stats.trades) + 1}",
                    entry_time_iso=bar_dt.strftime("%H:%M:%S"),
                    exit_time_iso="OPEN",
                    timestamp_ms=int(bar_dt.timestamp() * 1000),
                    strategy=strategy,
                    symbol=leg["contract"],
                    underlying=sym,
                    direction="BUY",
                    opt_type=leg["opt_type"],
                    strike=leg["strike"],
                    lots=cfg_lots,
                    quantity=qty,
                    entry_price=entry_p,
                    exit_price=None,
                    stop_loss=round(entry_p * 0.75, 2),
                    target_price=round(entry_p * 1.5, 2),
                    status="OPEN",
                    pnl_usd=0.0,
                    pnl_pct=0.0,
                    duration_mins=0,
                    raw_entry=None if friction_mode == "ideal" else raw_entry_p,
                    raw_exit=None,
                    slippage=None if friction_mode == "ideal" else max(0.0, entry_slip),
                    spot_entry=round(close, 2),
                    spot_stop=stop,
                    spot_target=target,
                    bars_held=0,
                )
                self._stats.trades_entered += 1
                self._stats.trades.append(trade)
                self._open_by_symbol.setdefault(sym, []).append(trade)
                self._recompute_totals()
                self._publish("trade", trade.model_dump())


def _generate_warmup_candles(symbol: str, res: str, start_epoch: int, count: int = 20, res_sec: int = 300) -> List[Dict[str, Any]]:
    """Pre-generate warmup candles before session start so indicators are ready at 09:15 AM."""
    warmup_start = start_epoch - (count * res_sec)
    return _generate_synthetic_candles(symbol, res, warmup_start, start_epoch - res_sec, res_sec)


def _generate_synthetic_candles(symbol: str, res: str, start_epoch: int, end_epoch: int, res_sec: int) -> List[Dict[str, Any]]:
    """Generate realistic session candles if DB has no historical data for selected date."""
    import random

    base_prices = {
        "NIFTY": 24500.0,
        "BANKNIFTY": 52300.0,
        "FINNIFTY": 23100.0,
        "MIDCPNIFTY": 13200.0,
        "SENSEX": 80100.0,
        "RELIANCE": 3000.0,
        "TATASTEEL": 150.0,
        "HDFCBANK": 1650.0,
        "ICICIBANK": 1200.0,
        "SBIN": 820.0,
        "BHARTIARTL": 1900.0,
        "AXISBANK": 1267.0,
        "KOTAKBANK": 421.15,
        "INFY": 1850.0,
        "BAJFINANCE": 1049.0,
        "ADANIENT": 3100.0,
        "LT": 3600.0,
        "TCS": 4400.0,
        "BAJAJFINSV": 1850.0,
        "ADANIPORTS": 1706.5,
    }
    spot = base_prices.get(symbol.upper(), 1000.0)
    volatility = spot * 0.0015  # 0.15% per candle standard deviation

    bars = []
    curr_time = start_epoch
    curr_price = spot

    random.seed(start_epoch + hash(symbol))  # deterministic per day/symbol

    while curr_time <= end_epoch:
        drift = random.gauss(0, volatility)
        open_p = round(curr_price, 2)
        close_p = round(curr_price + drift, 2)
        high_p = round(max(open_p, close_p) + abs(random.gauss(0, volatility * 0.5)), 2)
        low_p = round(min(open_p, close_p) - abs(random.gauss(0, volatility * 0.5)), 2)
        volume = float(random.randint(1000, 50000))

        bars.append({
            "symbol": symbol,
            "resolution": res,
            "time": curr_time,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": volume,
        })
        curr_price = close_p
        curr_time += res_sec
    return bars


async def _hydrate_missing_candles(
    instruments: List[str],
    resolution: str,
    start_epoch: int,
    end_epoch: int,
) -> None:
    """Fetch missing historical candles for selected replay date range from Zerodha Kite API."""
    from app.services import ohlcv_store

    # Standard Kite NSE Instrument Token Map
    KITE_TOKENS: Dict[str, int] = {
        "NIFTY": 256265,
        "BANKNIFTY": 260101,
        "FINNIFTY": 257001,
        "MIDCPNIFTY": 288001,
        "SENSEX": 265,
        "RELIANCE": 738561,
        "TATASTEEL": 895745,
        "HDFCBANK": 341249,
        "ICICIBANK": 12705,
        "SBIN": 779521,
        "BHARTIARTL": 2714625,
        "AXISBANK": 1510401,
        "KOTAKBANK": 492033,
        "INFY": 408065,
        "BAJFINANCE": 81153,
        "ADANIENT": 6401,
        "LT": 2939649,
        "TCS": 2953217,
        "BAJAJFINSV": 4267265,
        "ADANIPORTS": 3861249,
    }

    for sym in instruments:
        existing = ohlcv_store.get_candles(sym, resolution, limit=5000, since=start_epoch)
        in_range = [c for c in existing if start_epoch <= c["time"] <= end_epoch]
        if len(in_range) >= 5:
            continue  # Already cached locally

        log.info("Missing local candles for Sterling Kite token %s [%s] on range %d-%d. Triggering Zerodha Kite fetch...", sym, resolution, start_epoch, end_epoch)

        try:
            from app.services.exchanges.kite import accounts as kite_accounts
            from app.services.exchanges.kite.client import KiteClient

            token = KITE_TOKENS.get(sym.upper())
            if token:
                kite_accounts.bootstrap()
                zerodha_acct = next((a for a in kite_accounts._accounts.values() if a.is_active and a.access_token), None)
                if zerodha_acct and zerodha_acct.access_token:
                    kc = KiteClient(api_key=getattr(zerodha_acct, "api_key", "") or "", access_token=zerodha_acct.access_token)
                    try:
                        from zoneinfo import ZoneInfo
                        ist_tz = ZoneInfo("Asia/Kolkata")
                    except ImportError:
                        from datetime import timezone, timedelta
                        ist_tz = timezone(timedelta(hours=5, minutes=30))
                    from_str = datetime.fromtimestamp(start_epoch, tz=ist_tz).strftime("%Y-%m-%d %H:%M:%S")
                    to_str = datetime.fromtimestamp(end_epoch, tz=ist_tz).strftime("%Y-%m-%d %H:%M:%S")
                    k_res = "5minute" if resolution == "5m" else ("15minute" if resolution == "15m" else "60minute")
                    hist_data = await kc.get_historical(token, k_res, from_str, to_str)
                    if isinstance(hist_data, dict) and "candles" in hist_data:
                        raw_list = hist_data["candles"]
                        parsed_candles = []
                        for row in raw_list:
                            dt_c = datetime.fromisoformat(row[0])
                            parsed_candles.append({
                                "time": int(dt_c.timestamp()),
                                "open": float(row[1]),
                                "high": float(row[2]),
                                "low": float(row[3]),
                                "close": float(row[4]),
                                "volume": float(row[5]) if len(row) > 5 else 0.0,
                            })
                        if parsed_candles:
                            written = ohlcv_store.upsert_candles(sym, resolution, parsed_candles)
                            log.info("Hydrated %d real historical candles for %s from Zerodha Kite", written, sym)
        except Exception as exc:
            log.warning("Failed to fetch Zerodha Kite historical candles for %s: %s", sym, exc)


def reset_all_engine_signals() -> None:
    """Clear existing signal caches across all strategy engines when simulation starts."""
    try:
        from app.services import snapshot_cache
        snapshot_cache.clear()
    except Exception as exc:
        log.debug("Snapshot cache clear error: %s", exc)

    try:
        from app.api.v1.endpoints import directional
        directional._prev_states.clear()
        directional._active_signal_ids.clear()
        directional._active_signal_sls.clear()
        directional._prev_all_green.clear()
        directional._prev_all_red.clear()
    except Exception as exc:
        log.debug("Directional tracker state clear error: %s", exc)

    try:
        from app.services.kite_engine.scanner import scanner
        scanner._users.clear()
    except Exception as exc:
        log.debug("Kite scanner users clear error: %s", exc)


# Module-level singleton
simulation_runner = SimulationRunner()
