"""Arrow schema, fixed-point price encoding, and on-disk path layout.

Design decisions worth knowing before you change anything here:

**Prices are int64, not float.** Stored as ``round(rupees * 10_000)``. Floats make
exact equality and de-duplication unreliable, and a float64 OHLCV parquet measured 30.1
bytes/row against 17.6 for int64 — a 1.7x storage difference across ~10k instruments.
Four decimal places (not two) because CDS currency pairs quote to 4dp.

**Timestamps are UTC instants.** Kite sends ``2026-02-03T09:15:00+0530``; we store the
equivalent UTC instant (``03:45:00Z``) and convert back to IST at read time. Storing
naive IST would silently mis-order any future cross-market join.

**One parquet file per (instrument, interval).** The dominant query is "give me this
symbol's history", which becomes a single file open — no globbing, no metadata merge.
Files are named by ``instrument_token`` first because tokens are always filesystem-safe
integers; the symbol suffix exists purely so humans can browse the directory.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

import pyarrow as pa

from .config import PRICE_SCALE, SECOND_INTERVAL, VALID_INTERVALS

__all__ = [
    "BAR_SCHEMA",
    "BAR_COLUMNS",
    "encode_price",
    "decode_price",
    "sanitize_symbol",
    "candles_to_table",
    "bar_path",
    "bar_relpath",
    "parse_bar_filename",
]

BAR_COLUMNS = ("ts", "open", "high", "low", "close", "volume", "oi")

#: The canonical bar schema. ``oi`` is nullable: equities and indices have no open
#: interest, and writing 0 there would be a lie (0 is a meaningful OI for a contract).
BAR_SCHEMA = pa.schema(
    [
        pa.field("ts", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("open", pa.int64(), nullable=False),
        pa.field("high", pa.int64(), nullable=False),
        pa.field("low", pa.int64(), nullable=False),
        pa.field("close", pa.int64(), nullable=False),
        pa.field("volume", pa.int64(), nullable=False),
        pa.field("oi", pa.int64(), nullable=True),
    ]
)


# ─── Price fixed-point ───────────────────────────────────────────────────────
def encode_price(value: float | int) -> int:
    """Rupees -> scaled int64. Half-up at the 4th decimal."""
    # round() alone uses banker's rounding, which would map 0.00005 inconsistently.
    scaled = float(value) * PRICE_SCALE
    return int(scaled + 0.5) if scaled >= 0 else -int(-scaled + 0.5)


def decode_price(value: int | float) -> float:
    """Scaled int64 -> rupees."""
    return float(value) / PRICE_SCALE


# ─── Filesystem-safe symbol names ────────────────────────────────────────────
#: NTFS forbids \ / : * ? " < > | ; we also treat control chars and whitespace runs.
#: Note this is deliberately lossy — two distinct symbols could sanitize to the same
#: string, which is exactly why the instrument_token prefixes every filename.
_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_RUNS = re.compile(r"_{2,}")
_MAX_NAME = 64


def sanitize_symbol(symbol: str) -> str:
    """Return a deterministic, filesystem-safe rendering of a trading symbol.

    >>> sanitize_symbol("M&M")
    'M&M'
    >>> sanitize_symbol("NIFTY 50")
    'NIFTY_50'
    >>> sanitize_symbol("A/B*C")
    'A_B_C'
    """
    text = (symbol or "").strip()
    if not text:
        return "UNKNOWN"
    text = _UNSAFE.sub("_", text)
    text = text.replace(" ", "_")
    text = _RUNS.sub("_", text)
    # Windows also rejects names ending in a dot or space. A *leading* dot is legal but
    # would make the file hidden on Unix, so strip both ends.
    text = text.strip(". ")
    if not text:
        return "UNKNOWN"
    return text[:_MAX_NAME]


# ─── Candle parsing ──────────────────────────────────────────────────────────
def _parse_ts(raw: Any) -> int | None:
    """Kite candle timestamp -> epoch microseconds (UTC). None if unparseable."""
    if isinstance(raw, datetime):
        dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1_000_000)
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    # Kite emits "+0530" (no colon); fromisoformat handles both forms on 3.11+, but be
    # explicit so a future format tweak fails loudly here rather than silently shifting.
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None  # refuse to guess a zone; a naive candle is a protocol change
    return int(dt.astimezone(timezone.utc).timestamp() * 1_000_000)


def candles_to_table(
    candles: Sequence[Sequence[Any]],
    *,
    with_oi: bool = False,
    meta: dict[str, Any] | None = None,
) -> pa.Table:
    """Convert Kite's ``[[ts,o,h,l,c,v(,oi)], ...]`` into a :data:`BAR_SCHEMA` table.

    Malformed rows are dropped rather than poisoning the file. Rows are sorted by
    timestamp and de-duplicated keeping the **last** occurrence, because when the API
    returns a repeated timestamp the later element is the corrected/settled one.
    """
    ts_list: list[int] = []
    o: list[int] = []
    h: list[int] = []
    lo: list[int] = []
    c: list[int] = []
    v: list[int] = []
    oi: list[int | None] = []

    for row in candles or ():
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            continue
        micros = _parse_ts(row[0])
        if micros is None:
            continue
        try:
            _o = encode_price(row[1])
            _h = encode_price(row[2])
            _l = encode_price(row[3])
            _c = encode_price(row[4])
            _v = int(row[5] or 0)
        except (TypeError, ValueError):
            continue
        _oi: int | None = None
        if with_oi and len(row) >= 7 and row[6] is not None:
            try:
                _oi = int(row[6])
            except (TypeError, ValueError):
                _oi = None
        ts_list.append(micros)
        o.append(_o)
        h.append(_h)
        lo.append(_l)
        c.append(_c)
        v.append(_v)
        oi.append(_oi)

    # Sort by ts, last-wins on duplicates. Doing it in Python on the (already small)
    # per-chunk list is cheaper than an Arrow sort + group for these sizes.
    if ts_list:
        order = sorted(range(len(ts_list)), key=lambda i: (ts_list[i], i))
        dedup: dict[int, int] = {}
        for idx in order:
            dedup[ts_list[idx]] = idx  # later index overwrites -> last wins
        keep = [dedup[t] for t in sorted(dedup)]
        ts_list = [ts_list[i] for i in keep]
        o = [o[i] for i in keep]
        h = [h[i] for i in keep]
        lo = [lo[i] for i in keep]
        c = [c[i] for i in keep]
        v = [v[i] for i in keep]
        oi = [oi[i] for i in keep]

    table = pa.table(
        {
            "ts": pa.array(ts_list, pa.timestamp("us", tz="UTC")),
            "open": pa.array(o, pa.int64()),
            "high": pa.array(h, pa.int64()),
            "low": pa.array(lo, pa.int64()),
            "close": pa.array(c, pa.int64()),
            "volume": pa.array(v, pa.int64()),
            "oi": pa.array(oi, pa.int64()),
        },
        schema=BAR_SCHEMA,
    )
    return table.replace_schema_metadata(_metadata(meta))


def _metadata(meta: dict[str, Any] | None) -> dict[bytes, bytes]:
    from . import __version__

    base: dict[str, Any] = {
        "price_scale": str(PRICE_SCALE),
        "kitelake_version": __version__,
        "source": "kite-connect-v3",
        "tz": "UTC",
    }
    for key, value in (meta or {}).items():
        # Credentials must never reach file metadata.
        if key in {"api_key", "access_token", "api_secret"}:
            continue
        if value is None:
            continue
        base[str(key)] = str(value)
    return {k.encode(): v.encode() for k, v in base.items()}


# ─── Paths ───────────────────────────────────────────────────────────────────
def bar_relpath(
    interval: str, exchange: str, segment: str, token: int, tradingsymbol: str
) -> str:
    """Hive-partitioned path *relative to* the bars directory."""
    if interval not in VALID_INTERVALS and interval != SECOND_INTERVAL:
        raise ValueError(
            f"invalid interval {interval!r}; expected one of "
            f"{', '.join((*VALID_INTERVALS, SECOND_INTERVAL))}"
        )
    exch = sanitize_symbol(exchange or "UNKNOWN")
    seg = sanitize_symbol(segment or "UNKNOWN")
    name = f"{int(token)}__{sanitize_symbol(tradingsymbol)}.parquet"
    return f"interval={interval}/exchange={exch}/segment={seg}/{name}"


def bar_path(
    interval: str,
    exchange: str,
    segment: str,
    token: int,
    tradingsymbol: str,
    *,
    root: Any = None,
):
    """Absolute path to one instrument's parquet file for one interval."""
    from .volume import bars_dir

    return bars_dir(root) / bar_relpath(interval, exchange, segment, token, tradingsymbol)


_FILENAME = re.compile(r"^(?P<token>\d+)__(?P<symbol>.+)\.parquet$")


def parse_bar_filename(name: str) -> tuple[int, str] | None:
    """Inverse of the filename convention: ``"738561__RELIANCE.parquet"`` -> (738561, 'RELIANCE')."""
    match = _FILENAME.match(name)
    if not match:
        return None
    return int(match.group("token")), match.group("symbol")
