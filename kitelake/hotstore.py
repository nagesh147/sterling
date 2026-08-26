"""Hot data for instant reads: latest state per instrument, plus a short rolling history.

Deliberately in-process memory, not Redis or SQLite. The reader is the same process that
ingests, the working set is a few thousand instruments, and the point is a read that costs
microseconds rather than a query. Adding a network hop to "instant" would be self-defeating —
though note that it also means only *this process* gets the instant read; anything else needs
HTTP and is no longer instant.

Two structures, because two different questions get asked:

- **latest** — one :class:`HotQuote` per token, overwritten in place. Answers "what is
  RELIANCE right now", which is the overwhelming majority of reads.
- **ring** — a fixed-size circular buffer of recent ticks per token. Answers "what has it
  done in the last few seconds" without holding the day in RAM. Fixed capacity is the point:
  an unbounded deque under a full-market subscription is an out-of-memory bug waiting for a
  volatile open.

**Locking.** Ticks arrive on the WebSocket thread while HTTP handlers read from others, so
every mutation takes a lock. It is one lock for the whole store rather than one per token:
per-token locks would mean thousands of lock objects, plus a dictionary lookup under a lock
just to find the lock.

Measured on this machine (200k operations each), so the tradeoffs are visible rather than
assumed:

    spot()      3,500,000/sec    284 ns   <- the option-pricing hot path
    set_spot()  2,490,000/sec    401 ns
    update()      372,000/sec  2,689 ns   <- full quote + ring append
    get()         180,000/sec  5,553 ns   <- returns a copy

All of it is far above any tick rate Kite delivers. ``spot()`` is deliberately the cheapest
call because it runs once per option tick during enrichment, and ``update()`` costs more
because it also appends to the ring.

Reads return copies. Handing out the live object would let a caller observe a quote
half-updated, and worse, keep reading it after the ring had moved on.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

__all__ = ["HotQuote", "HotStore", "DEFAULT_RING"]

#: Ticks kept per instrument. 512 covers roughly the last minute of a briskly-trading
#: option at ~8 ticks/sec, which is what "recent" means for a decision.
DEFAULT_RING = 512


@dataclass
class HotQuote:
    """Latest known state of one instrument, enriched where it is an option."""

    instrument_token: int
    tradingsymbol: str = ""
    exchange: str = ""
    last_price: float = 0.0
    #: Exchange timestamp when supplied, else our receive time. UTC.
    ts: datetime | None = None
    volume_traded: int = 0
    last_traded_quantity: int = 0
    oi: int = 0
    bid: float = 0.0
    ask: float = 0.0
    bid_qty: int = 0
    ask_qty: int = 0
    #: Option analytics — populated only for CE/PE, and only when a spot is known.
    iv: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    #: False when the pricing model could not be evaluated. Distinguishing this from
    #: "delta is genuinely 1.0" is the difference between a hedge and a guess.
    greeks_solved: bool = False
    #: What the greeks were computed against, so a stale spot is visible rather than implied.
    spot_used: float | None = None
    dte_days: float | None = None
    #: Monotonic counter of ticks seen for this instrument.
    ticks: int = 0

    @property
    def mid(self) -> float:
        """Mid price when both sides are quoted, else last traded price."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last_price

    @property
    def spread(self) -> float:
        return self.ask - self.bid if (self.bid > 0 and self.ask > 0) else 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts"] = self.ts.isoformat() if self.ts else None
        d["mid"] = self.mid
        d["spread"] = self.spread
        return d


class _Ring:
    """Fixed-capacity circular buffer of (ts, price, qty). Newest last on read."""

    __slots__ = ("_cap", "_buf", "_n")

    def __init__(self, cap: int) -> None:
        self._cap = cap
        self._buf: list[tuple[float, float, int]] = []
        self._n = 0  # write cursor once full

    def push(self, ts: float, price: float, qty: int) -> None:
        if len(self._buf) < self._cap:
            self._buf.append((ts, price, qty))
        else:
            self._buf[self._n] = (ts, price, qty)
            self._n = (self._n + 1) % self._cap

    def read(self, limit: int | None = None) -> list[tuple[float, float, int]]:
        if len(self._buf) < self._cap:
            out = list(self._buf)
        else:
            out = self._buf[self._n:] + self._buf[: self._n]
        return out[-limit:] if limit else out

    def __len__(self) -> int:
        return len(self._buf)


class HotStore:
    """Thread-safe latest-quote map plus per-instrument ring buffers."""

    def __init__(self, ring_size: int = DEFAULT_RING) -> None:
        self._lock = threading.Lock()
        self._latest: dict[int, HotQuote] = {}
        self._rings: dict[int, _Ring] = {}
        self._ring_size = ring_size
        self.updates = 0

    # ─── writes ──────────────────────────────────────────────────────────────
    def update(self, quote: HotQuote, *, record: bool = True) -> None:
        """Store ``quote`` as the latest for its token and append to its ring."""
        with self._lock:
            token = quote.instrument_token
            prior = self._latest.get(token)
            quote.ticks = (prior.ticks + 1) if prior else 1
            self._latest[token] = quote
            if record and quote.last_price > 0:
                ring = self._rings.get(token)
                if ring is None:
                    ring = self._rings[token] = _Ring(self._ring_size)
                stamp = (quote.ts or datetime.now(timezone.utc)).timestamp()
                ring.push(stamp, quote.last_price, quote.last_traded_quantity)
            self.updates += 1

    def set_spot(self, token: int, price: float) -> None:
        """Fast path for underlyings: only the price matters for pricing options off them."""
        with self._lock:
            existing = self._latest.get(token)
            if existing is None:
                self._latest[token] = HotQuote(instrument_token=token, last_price=price, ticks=1)
            else:
                existing.last_price = price
                existing.ticks += 1
            self.updates += 1

    # ─── reads (always copies) ───────────────────────────────────────────────
    def get(self, token: int) -> HotQuote | None:
        with self._lock:
            quote = self._latest.get(token)
            return replace(quote) if quote else None

    def spot(self, token: int) -> float:
        """Latest price for ``token``, or 0.0 — the shape option pricing wants."""
        with self._lock:
            quote = self._latest.get(token)
            return quote.last_price if quote else 0.0

    def many(self, tokens: Iterable[int]) -> dict[int, HotQuote]:
        with self._lock:
            return {t: replace(self._latest[t]) for t in tokens if t in self._latest}

    def snapshot(self, *, limit: int | None = None, with_greeks_only: bool = False) -> list[HotQuote]:
        with self._lock:
            values = list(self._latest.values())
        if with_greeks_only:
            values = [q for q in values if q.iv is not None]
        values.sort(key=lambda q: q.ticks, reverse=True)
        return [replace(q) for q in (values[:limit] if limit else values)]

    def history(self, token: int, limit: int | None = None) -> list[tuple[float, float, int]]:
        """Recent (epoch_seconds, price, qty) for one instrument, oldest first."""
        with self._lock:
            ring = self._rings.get(token)
            return ring.read(limit) if ring else []

    # ─── introspection ───────────────────────────────────────────────────────
    def stats(self) -> dict[str, Any]:
        with self._lock:
            priced = sum(1 for q in self._latest.values() if q.iv is not None)
            solved = sum(1 for q in self._latest.values() if q.greeks_solved)
            return {
                "instruments": len(self._latest),
                "updates": self.updates,
                "with_iv": priced,
                "greeks_solved": solved,
                "rings": len(self._rings),
                "ring_size": self._ring_size,
                "buffered_ticks": sum(len(r) for r in self._rings.values()),
            }

    def clear(self) -> None:
        with self._lock:
            self._latest.clear()
            self._rings.clear()
            self.updates = 0
