"""Reading the lake — the fast path, and the graceful path.

Two access patterns, deliberately different implementations:

- **One instrument** (:func:`read_bars`) resolves straight to a single parquet file and
  ``pl.scan_parquet``s it. No glob, no catalog, no DuckDB. This is the hot path for
  backtests and it must stay O(1) in the size of the lake.
- **Many instruments / SQL** (:func:`read_many`, :func:`sql`) go through DuckDB over the
  Hive-partitioned tree, where predicate pushdown on the partition keys and the parquet
  row-group statistics do the pruning.

Prices come back as float rupees by default (``raw=True`` gives the stored int64s), and
timestamps in IST, because that is what every downstream analysis actually wants.

Every entry point tolerates the lake being absent: a missing volume raises
:class:`~kitelake.volume.LakeUnavailable`, which carries user-facing guidance rather than
a stack trace about a missing directory.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import polars as pl

from .config import PRICE_SCALE
from .schema import parse_bar_filename, sanitize_symbol

__all__ = [
    "SymbolNotFound",
    "AmbiguousSymbol",
    "resolve_instrument",
    "read_bars",
    "read_many",
    "resample",
    "sql",
    "available",
]

_PRICE_COLS = ("open", "high", "low", "close")


class SymbolNotFound(LookupError):
    """No instrument matched, with suggestions where possible."""


class AmbiguousSymbol(LookupError):
    """The symbol exists on more than one exchange; qualify it."""


# ─── Resolution ──────────────────────────────────────────────────────────────
def resolve_instrument(
    symbol_or_token: str | int,
    *,
    exchange: str | None = None,
    root: Any = None,
) -> dict[str, Any]:
    """Find one instrument by token, ``EXCHANGE:SYMBOL``, or bare symbol."""
    from .manifest import Manifest

    with Manifest(root=root) as man:
        if isinstance(symbol_or_token, int) or str(symbol_or_token).isdigit():
            row = man.instrument(int(symbol_or_token))
            if row:
                return row
            # A token we have bars for but no master row is still usable.
            return {
                "instrument_token": int(symbol_or_token),
                "tradingsymbol": "",
                "exchange": exchange or "",
                "segment": "",
            }

        text = str(symbol_or_token).strip()
        exch = exchange
        if ":" in text:
            head, _, tail = text.partition(":")
            exch, text = head.upper(), tail
        matches = man.find_instruments(text)
        if exch:
            matches = [m for m in matches if (m.get("exchange") or "").upper() == exch.upper()]
        if not matches:
            raise SymbolNotFound(
                f"No instrument named {symbol_or_token!r}"
                + (f" on {exch}" if exch else "")
                + ".\nRun `kitelake instruments` if the master is stale, or try "
                "EXCHANGE:SYMBOL (e.g. NSE:RELIANCE)."
            )
        if len(matches) > 1:
            # Prefer NSE cash when the same name exists across exchanges — it is what a
            # bare "RELIANCE" almost always means — but never guess between derivatives.
            cash = [
                m
                for m in matches
                if (m.get("segment") or "").upper() in {"NSE", "BSE", "INDICES"}
            ]
            if len(cash) == 1:
                return cash[0]
            listing = ", ".join(
                f"{m.get('exchange')}:{m.get('tradingsymbol')}" for m in matches[:12]
            )
            raise AmbiguousSymbol(
                f"{symbol_or_token!r} matches {len(matches)} instruments: {listing}"
                f"{' …' if len(matches) > 12 else ''}\nQualify it as EXCHANGE:SYMBOL."
            )
        return matches[0]


def _file_for(row: dict[str, Any], interval: str, *, root: Any = None) -> Path:
    from .volume import bars_dir

    base = bars_dir(root, create=False)
    token = int(row["instrument_token"])
    symbol = row.get("tradingsymbol") or ""
    if symbol:
        candidate = (
            base
            / f"interval={interval}"
            / f"exchange={sanitize_symbol(row.get('exchange') or 'UNKNOWN')}"
            / f"segment={sanitize_symbol(row.get('segment') or 'UNKNOWN')}"
            / f"{token}__{sanitize_symbol(symbol)}.parquet"
        )
        if candidate.exists():
            return candidate
    # Fall back to a token-scoped glob (cheap: one directory level per exchange).
    matches = sorted(base.glob(f"interval={interval}/**/{token}__*.parquet"))
    if matches:
        return matches[0]
    raise SymbolNotFound(
        f"No {interval} bars stored for "
        f"{row.get('tradingsymbol') or token} (token {token}).\n"
        f"Download them with:  kitelake download {row.get('exchange','NSE')}:"
        f"{row.get('tradingsymbol') or token} --interval {interval} --from … --to …"
    )


# ─── Reads ───────────────────────────────────────────────────────────────────
def _decode(frame: pl.LazyFrame, *, raw: bool, tz: str | None) -> pl.LazyFrame:
    if not raw:
        frame = frame.with_columns(
            [(pl.col(c) / PRICE_SCALE).alias(c) for c in _PRICE_COLS]
        )
    if tz:
        frame = frame.with_columns(pl.col("ts").dt.convert_time_zone(tz))
    return frame


def _as_datetime(value: Any, tz: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return datetime.fromisoformat(str(value))


def read_bars(
    symbol_or_token: str | int,
    interval: str = "minute",
    frm: date | str | None = None,
    to: date | str | None = None,
    *,
    exchange: str | None = None,
    tz: str | None = "Asia/Kolkata",
    raw: bool = False,
    lazy: bool = False,
    columns: Sequence[str] | None = None,
    root: Any = None,
) -> pl.DataFrame | pl.LazyFrame:
    """Read one instrument's bars. The fast path: one file, one scan.

    ``frm``/``to`` are inclusive dates interpreted in ``tz``.
    """
    row = resolve_instrument(symbol_or_token, exchange=exchange, root=root)
    path = _file_for(row, interval, root=root)

    frame = pl.scan_parquet(path)
    if columns:
        wanted = ["ts", *[c for c in columns if c != "ts"]]
        frame = frame.select(wanted)
    frame = _decode(frame, raw=raw, tz=tz)

    zone = tz or "UTC"
    if frm is not None:
        start = _as_datetime(frm, zone)
        frame = frame.filter(pl.col("ts") >= pl.lit(start).dt.replace_time_zone(zone))
    if to is not None:
        end = _as_datetime(to, zone)
        # Inclusive end date: cover the whole day.
        end = end.replace(hour=23, minute=59, second=59) if end.hour == 0 and end.minute == 0 else end
        frame = frame.filter(pl.col("ts") <= pl.lit(end).dt.replace_time_zone(zone))

    return frame if lazy else frame.collect()


def read_many(
    symbols: Iterable[str | int],
    interval: str = "minute",
    frm: date | str | None = None,
    to: date | str | None = None,
    *,
    columns: Sequence[str] | None = None,
    tz: str | None = "Asia/Kolkata",
    raw: bool = False,
    root: Any = None,
) -> pl.DataFrame:
    """Read several instruments into one long frame with a ``tradingsymbol`` column."""
    frames: list[pl.DataFrame] = []
    errors: list[str] = []
    for item in symbols:
        try:
            frame = read_bars(
                item, interval, frm, to, tz=tz, raw=raw, columns=columns, root=root
            )
        except (SymbolNotFound, AmbiguousSymbol) as exc:
            errors.append(f"{item}: {str(exc).splitlines()[0]}")
            continue
        row = resolve_instrument(item, root=root)
        frames.append(
            frame.with_columns(
                [
                    pl.lit(row.get("tradingsymbol") or str(item)).alias("tradingsymbol"),
                    pl.lit(int(row["instrument_token"])).alias("instrument_token"),
                ]
            )
        )
    if not frames:
        detail = "\n  ".join(errors[:10])
        raise SymbolNotFound(f"None of the requested instruments could be read:\n  {detail}")
    out = pl.concat(frames, how="vertical_relaxed")
    return out.sort(["tradingsymbol", "ts"])


def resample(frame: pl.DataFrame, rule: str, *, by: str | None = None) -> pl.DataFrame:
    """Aggregate bars to a coarser interval.

    Bins are **left-closed, left-labelled**: the 09:15 five-minute bar covers 09:15–09:19
    inclusive. That matches how Kite (and Indian exchanges generally) label intraday
    candles, so a resampled 5-minute bar lines up with a natively-fetched ``5minute`` one.
    """
    aggs = [
        pl.col("open").first().alias("open"),
        pl.col("high").max().alias("high"),
        pl.col("low").min().alias("low"),
        pl.col("close").last().alias("close"),
        pl.col("volume").sum().alias("volume"),
    ]
    if "oi" in frame.columns:
        aggs.append(pl.col("oi").last().alias("oi"))
    group = ["tradingsymbol"] if by is None and "tradingsymbol" in frame.columns else ([by] if by else None)
    out = frame.sort("ts").group_by_dynamic(
        "ts", every=rule, closed="left", label="left", group_by=group
    ).agg(aggs)
    return out


def sql(query: str, *, root: Any = None) -> pl.DataFrame:
    """Run DuckDB SQL against the catalog and return polars."""
    from .catalog import connect

    with connect(root=root, read_only=True) as conn:
        return conn.execute(query).pl()


def available(interval: str | None = None, *, root: Any = None) -> pl.DataFrame:
    """What the lake currently holds, one row per stored instrument."""
    from .manifest import Manifest

    with Manifest(root=root) as man:
        rows = man.symbols(interval)
    if not rows:
        return pl.DataFrame(
            schema={
                "instrument_token": pl.Int64, "tradingsymbol": pl.Utf8, "exchange": pl.Utf8,
                "interval": pl.Utf8, "rows": pl.Int64, "bytes": pl.Int64,
                "first_ts": pl.Utf8, "last_ts": pl.Utf8,
            }
        )
    frame = pl.DataFrame(rows)
    keep = [
        c
        for c in ("instrument_token", "tradingsymbol", "exchange", "segment", "interval",
                  "rows", "bytes", "first_ts", "last_ts")
        if c in frame.columns
    ]
    return frame.select(keep).sort("tradingsymbol")
