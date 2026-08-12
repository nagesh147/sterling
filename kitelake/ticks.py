"""Recording live ticks — the only route to sub-minute data.

**Read this before expecting second-level history.** Kite's historical API has no interval
below ``minute``, and no endpoint exposes past ticks. Sub-minute data therefore cannot be
backfilled at any price: it only exists if something was listening at the time. That is
what this module does — subscribe to the WebSocket in FULL mode and append every tick to
the lake, so that *from the moment you start it* you accumulate true tick and second-level
history.

If you need second-level data for a period already past, Kite cannot supply it. A vendor
with a tick archive can (TrueData's ``/getticks``, for instance); the lake's schema and
``source`` metadata are deliberately vendor-neutral so such a feed can land alongside.

Buffering: ticks arrive at hundreds per second across a wide subscription. Writing per
tick would spend all its time in parquet overhead, so ticks accumulate in memory and flush
in batches on a row-count or time threshold, and on shutdown.
"""

from __future__ import annotations

import signal
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from .config import IST, PRICE_SCALE, SECOND_INTERVAL, Credentials
from .schema import BAR_SCHEMA, encode_price

__all__ = ["TICK_SCHEMA", "TickRecorder", "aggregate_ticks_to_seconds"]

#: One row per tick. Prices scaled like bars so the two are directly comparable.
TICK_SCHEMA = pa.schema(
    [
        pa.field("ts", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("instrument_token", pa.int64(), nullable=False),
        pa.field("last_price", pa.int64(), nullable=False),
        pa.field("last_traded_quantity", pa.int64()),
        pa.field("volume_traded", pa.int64()),
        pa.field("oi", pa.int64()),
        pa.field("bid_price", pa.int64()),
        pa.field("bid_qty", pa.int64()),
        pa.field("ask_price", pa.int64()),
        pa.field("ask_qty", pa.int64()),
    ]
)


def _tick_path(day: date, exchange: str, *, root: Any = None) -> Path:
    from .volume import ticks_dir

    path = ticks_dir(root) / f"date={day.isoformat()}" / f"{exchange}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class TickRecorder:
    """Streams FULL-mode ticks from Kite and appends them to the lake."""

    #: Flush thresholds — whichever comes first.
    FLUSH_ROWS = 5_000
    FLUSH_SECONDS = 15.0

    def __init__(
        self,
        creds: Credentials,
        tokens: Sequence[int],
        *,
        exchange: str = "NSE",
        root: Any = None,
    ) -> None:
        self._creds = creds
        self._tokens = [int(t) for t in tokens]
        self._exchange = exchange
        self._root = root
        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._last_flush = time.monotonic()
        self._stop = threading.Event()
        self.ticks_seen = 0
        self.rows_written = 0

    # ─── buffering ───────────────────────────────────────────────────────────
    def _row(self, tick: dict[str, Any]) -> dict[str, Any]:
        depth = tick.get("depth") or {}
        buy = (depth.get("buy") or [{}])[0] if depth.get("buy") else {}
        sell = (depth.get("sell") or [{}])[0] if depth.get("sell") else {}
        stamp = tick.get("exchange_timestamp") or tick.get("last_trade_time")
        if isinstance(stamp, datetime):
            # kiteconnect hands back naive IST datetimes.
            moment = stamp if stamp.tzinfo else stamp.replace(tzinfo=IST)
        else:
            moment = datetime.now(timezone.utc)
        return {
            "ts": moment.astimezone(timezone.utc),
            "instrument_token": int(tick.get("instrument_token") or 0),
            "last_price": encode_price(tick.get("last_price") or 0),
            "last_traded_quantity": int(tick.get("last_traded_quantity") or 0),
            "volume_traded": int(tick.get("volume_traded") or tick.get("volume") or 0),
            "oi": int(tick.get("oi") or 0),
            "bid_price": encode_price(buy.get("price") or 0),
            "bid_qty": int(buy.get("quantity") or 0),
            "ask_price": encode_price(sell.get("price") or 0),
            "ask_qty": int(sell.get("quantity") or 0),
        }

    def ingest(self, ticks: Sequence[dict[str, Any]]) -> None:
        """Buffer a batch of ticks; flush when a threshold trips. Safe to call from the WS thread."""
        rows = [self._row(t) for t in ticks]
        with self._lock:
            self._buffer.extend(rows)
            self.ticks_seen += len(rows)
            due = (
                len(self._buffer) >= self.FLUSH_ROWS
                or (time.monotonic() - self._last_flush) >= self.FLUSH_SECONDS
            )
        if due:
            self.flush()

    def flush(self) -> int:
        """Append the buffer to today's tick file. Returns rows written."""
        with self._lock:
            pending, self._buffer = self._buffer, []
            self._last_flush = time.monotonic()
        if not pending:
            return 0
        table = pa.Table.from_pylist(pending, schema=TICK_SCHEMA)
        day = pending[0]["ts"].astimezone(IST).date()
        path = _tick_path(day, self._exchange, root=self._root)
        try:
            if path.exists():
                # Ticks are append-only within a day; concatenating keeps one file per
                # (day, exchange) so reads stay cheap.
                existing = pq.read_table(path)
                table = pa.concat_tables([existing, table])
            pq.write_table(table, path, compression="zstd", compression_level=6)
        except OSError:
            # Drive pulled mid-session: put the rows back so the next flush retries.
            with self._lock:
                self._buffer = pending + self._buffer
            return 0
        self.rows_written += len(pending)
        return len(pending)

    # ─── run loop ────────────────────────────────────────────────────────────
    def run(self) -> None:  # pragma: no cover - needs a live socket
        """Connect and stream until interrupted. Flushes on the way out."""
        try:
            from kiteconnect import KiteTicker
        except ImportError as exc:
            raise RuntimeError("kiteconnect is required for tick recording") from exc

        ticker = KiteTicker(self._creds.api_key, self._creds.access_token)

        def on_connect(ws: Any, _response: Any) -> None:
            ws.subscribe(self._tokens)
            ws.set_mode(ws.MODE_FULL, self._tokens)

        def on_ticks(_ws: Any, ticks: list[dict[str, Any]]) -> None:
            self.ingest(ticks)

        def on_close(_ws: Any, code: Any, reason: Any) -> None:
            self.flush()

        ticker.on_connect = on_connect
        ticker.on_ticks = on_ticks
        ticker.on_close = on_close

        def shutdown(*_args: Any) -> None:
            self._stop.set()
            with __import__("contextlib").suppress(Exception):
                ticker.close()
            written = self.flush()
            print(f"\nstopped: {self.ticks_seen:,} ticks seen, "
                  f"{self.rows_written:,} written (final flush {written:,})")

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)
        ticker.connect(threaded=False)


def aggregate_ticks_to_seconds(
    day: date, exchange: str = "NSE", *, root: Any = None
) -> Path | None:
    """Build true one-second OHLCV bars from recorded ticks.

    Returns None when no ticks were recorded for that date — the honest answer, since
    nothing can reconstruct them after the fact.
    """
    import polars as pl

    from .volume import ticks_dir

    src = ticks_dir(root, create=False) / f"date={day.isoformat()}" / f"{exchange}.parquet"
    if not src.exists():
        return None

    frame = pl.read_parquet(src)
    if frame.is_empty():
        return None

    bars = (
        frame.sort("ts")
        .group_by_dynamic("ts", every="1s", closed="left", label="left",
                          group_by="instrument_token")
        .agg(
            [
                pl.col("last_price").first().alias("open"),
                pl.col("last_price").max().alias("high"),
                pl.col("last_price").min().alias("low"),
                pl.col("last_price").last().alias("close"),
                # volume_traded is cumulative for the day, so the per-second traded
                # quantity is the span across the bucket, not a sum of the field.
                (pl.col("volume_traded").max() - pl.col("volume_traded").min()).alias("volume"),
                pl.col("oi").last().alias("oi"),
            ]
        )
    )

    from .universe import Instrument
    from .writer import BarWriter

    writer = BarWriter(root=root)
    last: Path | None = None
    for token, group in bars.group_by("instrument_token"):
        token_id = int(token[0] if isinstance(token, tuple) else token)
        table = (
            group.drop("instrument_token")
            .select(["ts", "open", "high", "low", "close", "volume", "oi"])
            .to_arrow()
            .cast(BAR_SCHEMA)
        )
        inst = Instrument(
            token=token_id, tradingsymbol=str(token_id), exchange=exchange, segment=exchange
        )
        result = writer.write(inst, SECOND_INTERVAL, table, mode="merge")
        if result.get("written"):
            last = Path(result["path"])
    return last
