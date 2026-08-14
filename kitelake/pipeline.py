"""The plumbing: every tick in, enriched, hot for reads, durable on disk.

    WebSocket thread ──▶ queue ──▶ worker ──┬──▶ HotStore  (instant reads)
       (must never block)                   └──▶ batch ──▶ parquet  (durable)

Four decisions worth stating, because each has a failure mode the obvious version walks
straight into.

**1. The socket thread must never block.** kiteconnect calls ``on_ticks`` on its own thread,
and Kite drops a client that stops draining. So ingest does the minimum — put on a queue —
and every bit of real work happens on a worker thread.

**2. "Process every tick" and "bounded memory" genuinely conflict, so the tradeoff is
explicit and counted.** If the queue fills, something has to give: blocking would stall the
socket and get us disconnected, so the queue sheds instead — and every shed tick is counted
in ``dropped``. That number is always reported, because a pipeline that silently sheds load
looks exactly like one that is keeping up. In practice it should stay zero: enrichment is
microseconds and the durable write is batched off the hot path.

**3. Greeks need a spot the tick does not carry.** An option tick carries its own premium,
not its underlying's price. So the pipeline keeps the latest spot per underlying in the hot
store and resolves option → underlying once, at setup, from the instrument master. An option
whose underlying has not ticked yet is stored *unpriced* rather than priced against a zero —
a confidently wrong greek is worse than a missing one.

**4. Durable writes are batched and off the hot path.** Per-tick parquet would spend all its
time in encoding overhead. Ticks accumulate and flush on a row or time threshold, and a
failed flush puts the rows back rather than dropping them.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Sequence

from .config import IST
from .hotstore import HotQuote, HotStore

__all__ = [
    "InstrumentRef", "PipelineStats", "TickPipeline", "build_refs",
    "run_pipe", "get_pipeline", "set_pipeline",
]


@dataclass(frozen=True)
class InstrumentRef:
    """What the pipeline needs to know about a token in order to enrich its ticks."""

    token: int
    tradingsymbol: str
    exchange: str
    instrument_type: str = ""
    strike: float = 0.0
    expiry: date | None = None
    #: Token of the underlying whose spot prices this option. 0 when unknown or n/a.
    spot_token: int = 0
    lot_size: int = 0

    @property
    def is_option(self) -> bool:
        return self.instrument_type in ("CE", "PE")

    def dte_days(self, now: datetime | None = None) -> float:
        """Calendar days to expiry, in IST because expiry is an IST date.

        Measured to the 15:30 close rather than midnight, and never negative. On expiry day
        an option still trading has hours of life left; returning 0.0 would make the model
        collapse to pure intrinsic and report every greek as flat.
        """
        if self.expiry is None:
            return 0.0
        moment = (now or datetime.now(timezone.utc)).astimezone(IST)
        close = datetime.combine(self.expiry, datetime.min.time(), tzinfo=IST).replace(
            hour=15, minute=30
        )
        return max((close - moment).total_seconds() / 86_400.0, 0.0)


@dataclass
class PipelineStats:
    received: int = 0
    processed: int = 0
    #: Shed under backpressure. Should stay zero; reported loudly when it does not.
    dropped: int = 0
    priced: int = 0
    unpriced_no_spot: int = 0
    iv_unsolved: int = 0
    persisted: int = 0
    flushes: int = 0
    flush_failures: int = 0
    started_at: float = field(default_factory=time.monotonic)

    def to_dict(self) -> dict[str, Any]:
        elapsed = max(time.monotonic() - self.started_at, 1e-9)
        return {
            "received": self.received,
            "processed": self.processed,
            "dropped": self.dropped,
            "priced": self.priced,
            "unpriced_no_spot": self.unpriced_no_spot,
            "iv_unsolved": self.iv_unsolved,
            "persisted": self.persisted,
            "flushes": self.flushes,
            "flush_failures": self.flush_failures,
            "elapsed_s": round(elapsed, 1),
            "ticks_per_s": round(self.processed / elapsed, 1),
            "no_loss": self.dropped == 0,
        }


def build_refs(
    tokens: Sequence[int], *, master: Any = None, root: Any = None
) -> dict[int, InstrumentRef]:
    """Resolve tokens to :class:`InstrumentRef`, wiring each option to its underlying.

    The option → underlying hop is the fiddly part. The instrument master gives an option's
    ``name`` (e.g. "NIFTY"), never its spot token, so this matches that name against index
    and cash instruments. Indices win ties: NIFTY options are priced off the NIFTY 50 index,
    and an equity that happens to share the name must not be picked instead.
    """
    from .instruments import load_instrument_master

    if master is None:
        master = load_instrument_master(root=root)
    rows = master.to_pylist()

    spot_by_name: dict[str, int] = {}
    for row in rows:  # indices first, so they take precedence
        if (row.get("segment") or "") != "INDICES":
            continue
        for key in (row.get("name"), row.get("tradingsymbol")):
            if key:
                spot_by_name.setdefault(str(key).upper(), int(row["instrument_token"]))
    for row in rows:  # then NSE cash
        if (row.get("exchange") or "") != "NSE" or (row.get("segment") or "") != "NSE":
            continue
        symbol = str(row.get("tradingsymbol") or "").upper()
        if symbol:
            spot_by_name.setdefault(symbol, int(row["instrument_token"]))

    wanted = {int(t) for t in tokens}
    refs: dict[int, InstrumentRef] = {}
    for row in rows:
        token = int(row["instrument_token"])
        if token not in wanted:
            continue
        itype = str(row.get("instrument_type") or "")
        name = str(row.get("name") or "").upper()
        refs[token] = InstrumentRef(
            token=token,
            tradingsymbol=str(row.get("tradingsymbol") or ""),
            exchange=str(row.get("exchange") or ""),
            instrument_type=itype,
            strike=float(row.get("strike") or 0.0),
            expiry=row.get("expiry"),
            spot_token=spot_by_name.get(name, 0) if itype in ("CE", "PE") else 0,
            lot_size=int(row.get("lot_size") or 0),
        )
    return refs


class TickPipeline:
    """Ingest → enrich (IV + greeks) → hot store → batched parquet."""

    #: Bounded so a stalled sink cannot exhaust memory. Roughly 30s of a busy full-market
    #: feed, which the worker should never come close to needing.
    QUEUE_MAX = 100_000
    FLUSH_ROWS = 5_000
    FLUSH_SECONDS = 15.0

    def __init__(
        self,
        refs: dict[int, InstrumentRef] | None = None,
        *,
        hot: HotStore | None = None,
        persist: bool = True,
        root: Any = None,
        price_options: bool = True,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.refs = refs or {}
        self.hot = hot or HotStore()
        self.stats = PipelineStats()
        self._persist = persist
        self._root = root
        self._on_event = on_event
        self._queue: queue.Queue[list[dict[str, Any]] | None] = queue.Queue(self.QUEUE_MAX)
        self._buffer: list[dict[str, Any]] = []
        self._buffer_lock = threading.Lock()
        self._last_flush = time.monotonic()
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._price = price_options and self._pricing_ready()

    @staticmethod
    def _pricing_ready() -> bool:
        from .greeks_bridge import greeks_available

        return greeks_available()

    @property
    def pricing_enabled(self) -> bool:
        return self._price

    # ─── lifecycle ───────────────────────────────────────────────────────────
    def start(self) -> "TickPipeline":
        if self._worker and self._worker.is_alive():
            return self
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, name="kitelake-pipeline", daemon=True)
        self._worker.start()
        return self

    def stop(self, *, timeout: float = 10.0) -> dict[str, Any]:
        """Drain what is queued, flush, and stop. Returns final stats."""
        self._stop.set()
        try:
            self._queue.put_nowait(None)  # wake a blocked get()
        except queue.Full:
            pass
        if self._worker:
            self._worker.join(timeout=timeout)
        self._flush(force=True)
        return self.stats.to_dict()

    # ─── ingest: runs on the WebSocket thread, must return immediately ───────
    def submit(self, ticks: Sequence[dict[str, Any]]) -> None:
        """Hand a tick batch to the worker. Never blocks; sheds (counted) when saturated."""
        if not ticks:
            return
        self.stats.received += len(ticks)
        try:
            self._queue.put_nowait(list(ticks))
        except queue.Full:
            # Blocking here would stall the socket thread and Kite would disconnect us, so
            # shedding is the lesser evil — but it is counted, never silent.
            self.stats.dropped += len(ticks)
            self._emit(
                event="backpressure_drop", dropped=self.stats.dropped, queued=self._queue.qsize()
            )

    # ─── worker ──────────────────────────────────────────────────────────────
    def _run(self) -> None:
        while not (self._stop.is_set() and self._queue.empty()):
            try:
                batch = self._queue.get(timeout=0.5)
            except queue.Empty:
                self._flush()
                continue
            if batch is None:
                continue
            for tick in batch:
                try:
                    self._process(tick)
                except Exception as exc:  # one bad tick must not kill the pipeline
                    self._emit(event="tick_error", error=f"{type(exc).__name__}: {exc}"[:200])
            self._flush()
        self._flush(force=True)

    def _process(self, tick: dict[str, Any]) -> None:
        token = int(tick.get("instrument_token") or 0)
        if not token:
            return
        ref = self.refs.get(token)
        depth = tick.get("depth") or {}
        buy = (depth.get("buy") or [{}])[0] if depth.get("buy") else {}
        sell = (depth.get("sell") or [{}])[0] if depth.get("sell") else {}

        stamp = tick.get("exchange_timestamp") or tick.get("last_trade_time")
        if isinstance(stamp, datetime):
            # kiteconnect hands back naive IST datetimes.
            ts = (stamp if stamp.tzinfo else stamp.replace(tzinfo=IST)).astimezone(timezone.utc)
        else:
            ts = datetime.now(timezone.utc)

        quote = HotQuote(
            instrument_token=token,
            tradingsymbol=ref.tradingsymbol if ref else "",
            exchange=ref.exchange if ref else "",
            last_price=float(tick.get("last_price") or 0.0),
            ts=ts,
            volume_traded=int(tick.get("volume_traded") or tick.get("volume") or 0),
            last_traded_quantity=int(tick.get("last_traded_quantity") or 0),
            oi=int(tick.get("oi") or 0),
            bid=float(buy.get("price") or 0.0),
            ask=float(sell.get("price") or 0.0),
            bid_qty=int(buy.get("quantity") or 0),
            ask_qty=int(sell.get("quantity") or 0),
        )

        if ref is not None and ref.is_option and self._price:
            self._enrich(quote, ref)

        self.hot.update(quote)
        self.stats.processed += 1
        if self._persist:
            with self._buffer_lock:
                self._buffer.append(self._row(quote))

    def _enrich(self, quote: HotQuote, ref: InstrumentRef) -> None:
        """Solve IV from the traded premium, then greeks from that IV."""
        from .greeks_bridge import black_scholes_greeks, implied_vol

        spot = self.hot.spot(ref.spot_token) if ref.spot_token else 0.0
        if spot <= 0:
            # Pricing against a zero spot would emit confident nonsense.
            self.stats.unpriced_no_spot += 1
            return
        dte = ref.dte_days()
        # Mid is the better input when both sides are quoted: last-traded can be stale, or
        # printed on the far side of a wide option spread.
        premium = quote.mid or quote.last_price
        iv = implied_vol(
            price=premium, spot=spot, strike=ref.strike, dte_days=dte,
            option_type=ref.instrument_type,
        )
        quote.spot_used = spot
        quote.dte_days = round(dte, 4)
        quote.iv = iv
        if iv <= 0:
            self.stats.iv_unsolved += 1
            return
        g = black_scholes_greeks(
            spot=spot, strike=ref.strike, dte_days=dte, iv=iv,
            option_type=ref.instrument_type,
        )
        quote.delta, quote.gamma, quote.theta, quote.vega = g.delta, g.gamma, g.theta, g.vega
        quote.greeks_solved = bool(getattr(g, "solved", True))
        self.stats.priced += 1

    # ─── durable sink ────────────────────────────────────────────────────────
    @staticmethod
    def _row(q: HotQuote) -> dict[str, Any]:
        from .schema import encode_price

        def scaled(value: float | None) -> int | None:
            return None if value is None else encode_price(value)

        return {
            "ts": q.ts,
            "instrument_token": q.instrument_token,
            "last_price": encode_price(q.last_price),
            "last_traded_quantity": q.last_traded_quantity,
            "volume_traded": q.volume_traded,
            "oi": q.oi,
            "bid_price": encode_price(q.bid),
            "bid_qty": q.bid_qty,
            "ask_price": encode_price(q.ask),
            "ask_qty": q.ask_qty,
            "iv": scaled(q.iv),
            "delta": scaled(q.delta),
            "gamma": scaled(q.gamma),
            "theta": scaled(q.theta),
            "vega": scaled(q.vega),
            "spot_used": scaled(q.spot_used),
        }

    def _flush(self, *, force: bool = False) -> int:
        if not self._persist:
            return 0
        with self._buffer_lock:
            if not self._buffer:
                return 0
            due = (
                force
                or len(self._buffer) >= self.FLUSH_ROWS
                or (time.monotonic() - self._last_flush) >= self.FLUSH_SECONDS
            )
            if not due:
                return 0
            rows, self._buffer = self._buffer, []
            self._last_flush = time.monotonic()
        try:
            written = self._write(rows)
        except Exception as exc:
            # Drive yanked mid-flush: put the rows back so the next attempt keeps them.
            with self._buffer_lock:
                self._buffer = rows + self._buffer
            self.stats.flush_failures += 1
            self._emit(
                event="flush_failed", error=f"{type(exc).__name__}: {exc}"[:200],
                buffered=len(self._buffer),
            )
            return 0
        self.stats.persisted += written
        self.stats.flushes += 1
        return written

    def _write(self, rows: list[dict[str, Any]]) -> int:
        import pyarrow as pa
        import pyarrow.parquet as pq

        from .ticks import ENRICHED_TICK_SCHEMA, enriched_tick_path

        if not rows:
            return 0
        table = pa.Table.from_pylist(rows, schema=ENRICHED_TICK_SCHEMA)
        day = rows[0]["ts"].astimezone(IST).date()
        path = enriched_tick_path(day, root=self._root)
        if path.exists():
            table = pa.concat_tables([pq.read_table(path), table])
        pq.write_table(table, path, compression="zstd", compression_level=6)
        return len(rows)

    def _emit(self, **payload: Any) -> None:
        if self._on_event:
            self._on_event(payload)

    # ─── convenience ─────────────────────────────────────────────────────────
    def snapshot(self, **kw: Any) -> list[dict[str, Any]]:
        return [q.to_dict() for q in self.hot.snapshot(**kw)]

    def status(self) -> dict[str, Any]:
        with self._buffer_lock:
            buffered = len(self._buffer)
        return {
            "pipeline": self.stats.to_dict(),
            "hot": self.hot.stats(),
            "queued": self._queue.qsize(),
            "buffered": buffered,
            "pricing_enabled": self._price,
            "instruments_resolved": len(self.refs),
            "options_wired_to_spot": sum(
                1 for r in self.refs.values() if r.is_option and r.spot_token
            ),
            "options_missing_spot": sum(
                1 for r in self.refs.values() if r.is_option and not r.spot_token
            ),
        }


# ─── process-wide handle ─────────────────────────────────────────────────────
#: The HotStore lives in memory, so "instant read" only means anything to code in the same
#: process. Whoever starts the pipeline registers it here so other parts of that process —
#: an API handler, a strategy — can read it without threading the object through every call
#: site. Cross-process readers need HTTP (see /api/v1/datalake/hot), which is no longer
#: instant, and that is a real limit rather than something to paper over.
_ACTIVE: "TickPipeline | None" = None
_ACTIVE_LOCK = threading.Lock()


def set_pipeline(pipe: "TickPipeline | None") -> None:
    global _ACTIVE
    with _ACTIVE_LOCK:
        _ACTIVE = pipe


def get_pipeline() -> "TickPipeline | None":
    with _ACTIVE_LOCK:
        return _ACTIVE


def run_pipe(
    tokens: Sequence[int],
    *,
    creds: Any = None,
    persist: bool = True,
    price_options: bool = True,
    root: Any = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    mode_full: bool = True,
) -> TickPipeline:
    """Wire a live Kite WebSocket into a pipeline and block until interrupted.

    FULL mode is the default because bid/ask is not a luxury here: the mid is a better IV
    input than last-traded, which on a wide option spread can be minutes stale or printed on
    the wrong side.
    """
    import signal as _signal

    from .config import load_credentials

    try:
        from kiteconnect import KiteTicker
    except ImportError as exc:  # pragma: no cover - needs the optional dep
        raise RuntimeError("kiteconnect is required to run the live pipe") from exc

    creds = creds or load_credentials()
    refs = build_refs(tokens, root=root)
    pipe = TickPipeline(
        refs, persist=persist, root=root, price_options=price_options, on_event=on_event
    ).start()
    set_pipeline(pipe)

    ticker = KiteTicker(creds.api_key, creds.access_token)
    wanted = [int(t) for t in tokens]
    # Options need their underlying's spot, and the underlying is usually not in the
    # requested set. Subscribing to it as well is what makes greeks possible at all.
    spots = sorted({r.spot_token for r in refs.values() if r.spot_token} - set(wanted))
    subscribe = wanted + spots

    def on_connect(ws: Any, _response: Any) -> None:
        ws.subscribe(subscribe)
        ws.set_mode(ws.MODE_FULL if mode_full else ws.MODE_QUOTE, subscribe)
        if on_event:
            on_event({"event": "connected", "subscribed": len(subscribe), "spots_added": len(spots)})

    def on_ticks(_ws: Any, ticks: list[dict[str, Any]]) -> None:
        # Underlyings first: an option enriched in the same batch should see the newest spot,
        # not the previous one.
        for tick in ticks:
            token = int(tick.get("instrument_token") or 0)
            ref = refs.get(token)
            if ref is None or not ref.is_option:
                pipe.hot.set_spot(token, float(tick.get("last_price") or 0.0))
        pipe.submit(ticks)

    def on_close(_ws: Any, _code: Any, _reason: Any) -> None:
        if on_event:
            on_event({"event": "disconnected", **pipe.status()})

    ticker.on_connect = on_connect
    ticker.on_ticks = on_ticks
    ticker.on_close = on_close

    def shutdown(*_a: Any) -> None:
        with __import__("contextlib").suppress(Exception):
            ticker.close()
        final = pipe.stop()
        set_pipeline(None)
        if on_event:
            on_event({"event": "stopped", **final})

    _signal.signal(_signal.SIGINT, shutdown)
    _signal.signal(_signal.SIGTERM, shutdown)
    ticker.connect(threaded=False)
    return pipe
