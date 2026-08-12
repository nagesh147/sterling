"""The instrument master: 114k rows of "what exists and what its token is".

Fetched from ``https://api.kite.trade/instruments`` — a **public** endpoint needing no
credentials, which is why every offline-planning command works before you ever log in.

Hard limitation worth internalising: this dump lists **live contracts only**. Expired
options and futures are simply absent, and Kite offers no way to enumerate their tokens.
So "six months of the full option chain" is not obtainable retroactively — only the
contracts trading today, and only back to each contract's own listing date. Futures have
a partial escape hatch (``continuous=1``, which stitches history across expiries).
"""

from __future__ import annotations

import io
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from .config import INSTRUMENTS_URL

__all__ = [
    "INSTRUMENT_SCHEMA",
    "fetch_instrument_master",
    "write_instrument_master",
    "load_instrument_master",
    "sync_instruments",
    "master_age",
]

INSTRUMENT_SCHEMA = pa.schema(
    [
        pa.field("instrument_token", pa.int64()),
        pa.field("exchange_token", pa.int64()),
        pa.field("tradingsymbol", pa.string()),
        pa.field("name", pa.string()),
        pa.field("last_price", pa.float64()),
        pa.field("expiry", pa.date32()),
        pa.field("strike", pa.float64()),
        pa.field("tick_size", pa.float64()),
        pa.field("lot_size", pa.int64()),
        pa.field("instrument_type", pa.string()),
        pa.field("segment", pa.string()),
        pa.field("exchange", pa.string()),
    ]
)

_COLUMN_TYPES = {
    "instrument_token": pa.int64(),
    "exchange_token": pa.int64(),
    "tradingsymbol": pa.string(),
    "name": pa.string(),
    "last_price": pa.float64(),
    "expiry": pa.date32(),
    "strike": pa.float64(),
    "tick_size": pa.float64(),
    "lot_size": pa.int64(),
    "instrument_type": pa.string(),
    "segment": pa.string(),
    "exchange": pa.string(),
}


def _parse_csv(raw: bytes) -> pa.Table:
    """Parse the instrument CSV into :data:`INSTRUMENT_SCHEMA`."""
    table = pacsv.read_csv(
        io.BytesIO(raw),
        convert_options=pacsv.ConvertOptions(
            column_types=_COLUMN_TYPES,
            # Blank expiry/strike are the norm for cash instruments.
            null_values=["", "NA", "null"],
            strings_can_be_null=True,
        ),
    )
    # Reorder/cast to the canonical schema so downstream code never guesses.
    arrays = []
    for field in INSTRUMENT_SCHEMA:
        if field.name in table.column_names:
            arrays.append(table.column(field.name).cast(field.type))
        else:
            arrays.append(pa.nulls(table.num_rows, field.type))
    return pa.Table.from_arrays(arrays, schema=INSTRUMENT_SCHEMA)


async def fetch_instrument_master(client: Any = None) -> pa.Table:
    """Download and parse the live instrument master. No credentials required."""
    import httpx

    own = client is None
    if own:
        client = httpx.AsyncClient(timeout=120.0, follow_redirects=True)
    try:
        resp = await client.get(INSTRUMENTS_URL, headers={"User-Agent": "kitelake/1.0"})
        resp.raise_for_status()
        raw = resp.content
    finally:
        if own:
            await client.aclose()
    if len(raw) < 10_000:
        raise RuntimeError(
            f"instrument master looks truncated ({len(raw)} bytes) — refusing to overwrite "
            "a good copy with a bad one"
        )
    return _parse_csv(raw)


def _atomic_write(table: pa.Table, target: Path, staging: Path) -> Path:
    """Write parquet via staging + os.replace so readers never see a partial file."""
    staging.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = staging / f"{uuid.uuid4().hex}.parquet"
    pq.write_table(table, tmp, compression="zstd", compression_level=9)
    # os.replace is only atomic within one filesystem; staging and target both live
    # inside the lake, so this holds. Assert it rather than trusting the layout.
    if os.stat(tmp).st_dev != os.stat(target.parent).st_dev:
        raise RuntimeError(
            f"staging ({tmp}) and target ({target.parent}) are on different filesystems; "
            "the atomic rename guarantee would be lost"
        )
    os.replace(tmp, target)
    return target


def write_instrument_master(table: pa.Table, *, root: Any = None, on: date | None = None) -> Path:
    """Persist a dated snapshot plus refresh ``latest.parquet``."""
    from .volume import instruments_dir, staging_dir

    # Date the snapshot in IST: a dump pulled at 23:30 IST belongs to that trading day,
    # not to the previous UTC one.
    from .config import IST

    day = (on or datetime.now(IST).date()).isoformat()
    base = instruments_dir(root)
    staging = staging_dir(root)
    dated = _atomic_write(table, base / f"date={day}" / "instruments.parquet", staging)
    _atomic_write(table, base / "latest.parquet", staging)
    return dated


def load_instrument_master(on: date | str | None = None, *, root: Any = None) -> pa.Table:
    """Load the master snapshot. Raises a *useful* error when it has never been synced."""
    from .volume import instruments_dir

    base = instruments_dir(root, create=False)
    path = base / "latest.parquet" if on is None else base / f"date={on}" / "instruments.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"No instrument master at {path}.\n"
            "Fetch it first (this needs no credentials — the endpoint is public):\n"
            "    kitelake instruments"
        )
    return pq.read_table(path)


def master_age(*, root: Any = None) -> float | None:
    """Age of ``latest.parquet`` in hours, or None if absent/unreachable."""
    try:
        from .volume import instruments_dir

        path = instruments_dir(root, create=False) / "latest.parquet"
        mtime = path.stat().st_mtime
    except Exception:
        return None
    return (datetime.now(timezone.utc).timestamp() - mtime) / 3600.0


def sync_instruments(*, root: Any = None) -> dict[str, Any]:
    """Fetch, persist, and index the instrument master. Returns a per-exchange summary."""
    import asyncio
    from collections import Counter

    from .manifest import Manifest

    table = asyncio.run(fetch_instrument_master())
    path = write_instrument_master(table, root=root)

    exchanges = Counter(table.column("exchange").to_pylist())
    segments = Counter(table.column("segment").to_pylist())

    # Index into the ledger so symbol lookups work without re-reading the parquet.
    rows = table.select(
        [
            "instrument_token", "tradingsymbol", "name", "exchange", "segment",
            "instrument_type", "expiry", "strike", "tick_size", "lot_size",
        ]
    ).to_pylist()
    with Manifest(root=root) as man:
        indexed = man.upsert_instruments(rows)

    return {
        "path": str(path),
        "instruments": table.num_rows,
        "indexed": indexed,
        "by_exchange": dict(exchanges.most_common()),
        "by_segment": dict(segments.most_common(12)),
        "indices": int(segments.get("INDICES", 0)),
    }
