"""Proving the lake is trustworthy — because silent corruption is the expensive kind.

A backtest cannot tell the difference between "this stock was quiet" and "we lost half
its bars", so the checks here are deliberately mechanical and complete: schema, ordering,
duplicates, OHLC arithmetic, session windows, and interval alignment.

One judgement call worth stating: **low completeness is not a defect.** Kite omits a
candle entirely for any minute with no trade, so an illiquid stock legitimately returns
8% of the theoretical bar count. :func:`coverage_report` therefore reports completeness as
information, while :func:`verify_symbol` only fails on things that are structurally
impossible — a high below a low, a bar at 3am, timestamps going backwards.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .calendar_ import expected_bars, interval_minutes, session_bounds, session_days
from .config import IST
from .schema import BAR_SCHEMA, parse_bar_filename

#: IST is a fixed UTC+5:30 offset and never observes DST, so converting a UTC
#: instant to Indian wall-clock is exact integer arithmetic on epoch seconds.
_IST_OFFSET_SECONDS = 5 * 3600 + 30 * 60


def _mod(values: Any, divisor: int) -> Any:
    """Vectorised integer modulo. pyarrow.compute has no `mod`, so derive it.

    Safe here because every input is a positive epoch-second count (pc.divide truncates
    toward zero, which only differs from floor division for negatives).
    """
    return pc.subtract(values, pc.multiply(pc.divide(values, divisor), divisor))

__all__ = ["CHECKS", "verify_file", "verify_symbol", "verify_lake", "coverage_report", "format_report"]

CHECKS = (
    "schema",
    "ts_sorted",
    "ts_unique",
    "no_nulls",
    "high_ge_low",
    "high_is_max",
    "low_is_min",
    "volume_non_negative",
    "in_session",
    "interval_aligned",
)


def _exchange_from_path(path: Path) -> str:
    for part in path.parts:
        if part.startswith("exchange="):
            return part.split("=", 1)[1]
    return "NSE"


def _interval_from_path(path: Path) -> str:
    for part in path.parts:
        if part.startswith("interval="):
            return part.split("=", 1)[1]
    return "minute"


def verify_file(path: str | Path) -> dict[str, Any]:
    """Run every structural check on one bar file. Never raises."""
    path = Path(path)
    parsed = parse_bar_filename(path.name)
    result: dict[str, Any] = {
        "path": str(path),
        "token": parsed[0] if parsed else 0,
        "tradingsymbol": parsed[1] if parsed else "",
        "exchange": _exchange_from_path(path),
        "interval": _interval_from_path(path),
        "rows": 0,
        "bytes": 0,
        "ok": False,
        "failures": [],
        "first_ts": "",
        "last_ts": "",
        "error": "",
    }
    try:
        result["bytes"] = path.stat().st_size
        # ParquetFile(...).read(), NOT pq.read_table(). The lake stores bars under
        # Hive-style directories (interval=…/exchange=…/segment=…), and read_table
        # infers those keys and APPENDS them as columns — so every real file came
        # back with 10 fields against BAR_SCHEMA's 7 and failed the schema check
        # below. That made `verify` condemn the entire lake, including files it had
        # just written itself. ParquetFile reads the physical file only.
        table = pq.ParquetFile(path).read()
    except Exception as exc:
        result["error"] = f"unreadable: {type(exc).__name__}: {exc}"
        result["failures"] = ["schema"]
        return result

    failures: list[str] = []

    if [f.name for f in table.schema] != [f.name for f in BAR_SCHEMA] or any(
        table.schema.field(f.name).type != f.type for f in BAR_SCHEMA
    ):
        failures.append("schema")
        result["failures"] = failures
        result["rows"] = table.num_rows
        return result

    result["rows"] = table.num_rows
    if table.num_rows == 0:
        # An empty file should never exist; the writer refuses to create one.
        result["failures"] = ["no_nulls"]
        result["error"] = "file contains zero rows"
        return result

    # Work on int64 epoch microseconds rather than materialising Python datetimes.
    # `to_pylist()` on a 96k-row column plus a Python set() of datetimes was the bulk of
    # the remaining cost; the equivalent Arrow kernels are ~10x cheaper and exact.
    ts_col = table.column("ts")
    ts_us = pc.cast(ts_col, pa.int64())
    result["first_ts"] = ts_col[0].as_py().isoformat()
    result["last_ts"] = ts_col[-1].as_py().isoformat()

    if table.num_rows > 1:
        flat = ts_us.combine_chunks() if isinstance(ts_us, pa.ChunkedArray) else ts_us
        deltas = pc.subtract(flat.slice(1), flat.slice(0, len(flat) - 1))
        if pc.min(deltas).as_py() is not None and pc.min(deltas).as_py() < 0:
            failures.append("ts_sorted")
        # Strictly increasing means every delta is > 0; a zero delta is a duplicate.
        if pc.count_distinct(flat).as_py() != table.num_rows:
            failures.append("ts_unique")

    o = table.column("open")
    h = table.column("high")
    lo = table.column("low")
    c = table.column("close")
    v = table.column("volume")

    if any(col.null_count for col in (table.column("ts"), o, h, lo, c, v)):
        failures.append("no_nulls")
    if pc.any(pc.less(h, lo)).as_py():
        failures.append("high_ge_low")
    if pc.any(pc.less(h, pc.max_element_wise(o, c))).as_py():
        failures.append("high_is_max")
    if pc.any(pc.greater(lo, pc.min_element_wise(o, c))).as_py():
        failures.append("low_is_min")
    if pc.any(pc.less(v, 0)).as_py():
        failures.append("volume_non_negative")

    exchange = result["exchange"]
    interval = result["interval"]

    # Session window and grid alignment, VECTORISED.
    #
    # These were per-row Python loops with an .astimezone() call each, which made verify
    # CPU-bound rather than IO-bound: 236 ms for a single 96k-row file, ~29 minutes for the
    # lake, and the thread pool bought almost nothing because the work holds the GIL.
    #
    # IST is a fixed UTC+5:30 offset with no DST, so the conversion is exact arithmetic on
    # epoch seconds — no calendar maths needed.
    epoch = pc.divide(
        pc.cast(table.column("ts"), pa.int64()), 1_000_000
    )  # microseconds -> seconds
    local = pc.add(epoch, _IST_OFFSET_SECONDS)
    into_day = _mod(local, 86_400)

    opened, closed = session_bounds(ts_col[0].as_py().astimezone(IST).date(), exchange)
    open_s = opened.hour * 3600 + opened.minute * 60
    close_s = closed.hour * 3600 + closed.minute * 60
    outside = pc.or_(pc.less(into_day, open_s), pc.greater(into_day, close_s))
    out_of_session = pc.sum(pc.cast(outside, pa.int64())).as_py() or 0
    if out_of_session:
        failures.append("in_session")
        result["out_of_session"] = int(out_of_session)

    if interval != "day":
        step = interval_minutes(interval)
        if step >= 1:
            # Bars must land on whole minutes, and on the interval grid measured from the
            # session open.
            off_minute = _mod(local, 60)
            misaligned_mask = pc.not_equal(off_minute, 0)
            if step > 1:
                grid = _mod(pc.divide(pc.subtract(into_day, open_s), 60), int(step))
                misaligned_mask = pc.or_(misaligned_mask, pc.not_equal(grid, 0))
            misaligned = pc.sum(pc.cast(misaligned_mask, pa.int64())).as_py() or 0
            if misaligned:
                failures.append("interval_aligned")
                result["misaligned"] = int(misaligned)

    result["failures"] = failures
    result["ok"] = not failures
    return result


def verify_symbol(token: int, interval: str = "minute", *, root: Any = None) -> dict[str, Any]:
    """Verify one instrument by token, locating its file via the manifest."""
    from .manifest import Manifest
    from .volume import bars_dir

    with Manifest(root=root) as man:
        row = man.symbol_status(int(token), interval)
        inst = man.instrument(int(token))
    path = ""
    if row and row.get("path"):
        path = str(row["path"])
    if not path or not Path(path).exists():
        matches = list(bars_dir(root, create=False).glob(f"interval={interval}/**/{int(token)}__*.parquet"))
        if not matches:
            return {
                "token": int(token), "interval": interval, "ok": False,
                "failures": ["missing"], "error": "no parquet file found for this instrument",
                "tradingsymbol": (inst or {}).get("tradingsymbol", ""), "rows": 0, "bytes": 0,
            }
        path = str(matches[0])
    return verify_file(path)


def verify_lake(
    interval: str | None = None,
    *,
    sample: int | None = None,
    workers: int = 8,
    root: Any = None,
) -> dict[str, Any]:
    """Sweep the lake. Returns aggregate counts plus the failing files.

    Reports both directions of manifest/disk disagreement, because each means something
    different: a file on disk with no ledger row survived a ledger reset, while a ledger
    row with no file means a write was lost.
    """
    from .manifest import Manifest
    from .volume import bars_dir

    base = bars_dir(root, create=False)
    pattern = f"interval={interval}/**/*.parquet" if interval else "interval=*/**/*.parquet"
    files = sorted(base.glob(pattern))
    if sample:
        step = max(1, len(files) // sample)
        files = files[::step][:sample]

    results: list[dict[str, Any]] = []
    if files:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            results = list(pool.map(verify_file, files))

    by_failure: dict[str, list[str]] = {}
    rows = 0
    size = 0
    for res in results:
        rows += int(res.get("rows") or 0)
        size += int(res.get("bytes") or 0)
        for failure in res.get("failures") or ():
            by_failure.setdefault(failure, []).append(
                res.get("tradingsymbol") or str(res.get("token"))
            )

    on_disk = {parse_bar_filename(p.name)[0] for p in files if parse_bar_filename(p.name)}
    in_manifest: set[int] = set()
    try:
        with Manifest(root=root) as man:
            in_manifest = {
                int(r["instrument_token"])
                for r in man.symbols(interval)
                if int(r.get("rows") or 0) > 0
            }
    except Exception:
        pass

    return {
        "interval": interval or "all",
        "files": len(files),
        "rows": rows,
        "bytes": size,
        "gib": round(size / 2**30, 3),
        "ok": sum(1 for r in results if r.get("ok")),
        "failed": sum(1 for r in results if not r.get("ok")),
        "by_failure": {k: sorted(set(v))[:25] for k, v in by_failure.items()},
        "failure_counts": {k: len(v) for k, v in by_failure.items()},
        "in_manifest_missing_on_disk": sorted(in_manifest - on_disk)[:50],
        "on_disk_missing_from_manifest": sorted(on_disk - in_manifest)[:50],
        "bytes_per_row": round(size / rows, 2) if rows else 0.0,
    }


def coverage_report(
    interval: str,
    frm: date,
    to: date,
    *,
    tokens: Iterable[int] | None = None,
    root: Any = None,
) -> pa.Table:
    """Per-instrument completeness over a date range."""
    from .manifest import Manifest

    with Manifest(root=root) as man:
        symbols = man.symbols(interval)

    wanted = set(int(t) for t in tokens) if tokens is not None else None
    out: dict[str, list[Any]] = {
        k: []
        for k in (
            "instrument_token", "tradingsymbol", "exchange", "rows", "expected",
            "completeness_pct", "days_present", "days_expected", "first_ts", "last_ts",
        )
    }
    for row in symbols:
        token = int(row["instrument_token"])
        if wanted is not None and token not in wanted:
            continue
        exchange = row.get("exchange") or "NSE"
        exp = expected_bars(frm, to, interval, exchange)
        rows_have = int(row.get("rows") or 0)
        days_exp = len(session_days(frm, to, exchange))
        days_have = 0
        if row.get("first_ts") and row.get("last_ts"):
            try:
                a = datetime.fromisoformat(row["first_ts"]).astimezone(IST).date()
                b = datetime.fromisoformat(row["last_ts"]).astimezone(IST).date()
                days_have = len(session_days(max(a, frm), min(b, to), exchange))
            except ValueError:
                days_have = 0
        out["instrument_token"].append(token)
        out["tradingsymbol"].append(row.get("tradingsymbol") or "")
        out["exchange"].append(exchange)
        out["rows"].append(rows_have)
        out["expected"].append(exp)
        out["completeness_pct"].append(round(100.0 * rows_have / exp, 2) if exp else 0.0)
        out["days_present"].append(days_have)
        out["days_expected"].append(days_exp)
        out["first_ts"].append(row.get("first_ts") or "")
        out["last_ts"].append(row.get("last_ts") or "")
    return pa.table(out)


def format_report(report: dict[str, Any]) -> str:
    """Render :func:`verify_lake` output for a terminal."""
    lines = [
        f"Lake verification — interval={report['interval']}",
        f"  files         {report['files']:,}",
        f"  candles       {report['rows']:,}",
        f"  size          {report['gib']} GiB ({report['bytes_per_row']} bytes/row)",
        f"  clean         {report['ok']:,}",
        f"  failing       {report['failed']:,}",
    ]
    if report["failure_counts"]:
        lines.append("  failures by check:")
        for check, count in sorted(report["failure_counts"].items(), key=lambda kv: -kv[1]):
            examples = ", ".join(report["by_failure"].get(check, [])[:6])
            lines.append(f"    {check:22s} {count:6,}   e.g. {examples}")
    else:
        lines.append("  no structural problems found")
    if report["in_manifest_missing_on_disk"]:
        lines.append(
            f"  in ledger but not on disk: {len(report['in_manifest_missing_on_disk'])} "
            f"(e.g. {report['in_manifest_missing_on_disk'][:5]})"
        )
    if report["on_disk_missing_from_manifest"]:
        lines.append(
            f"  on disk but not in ledger: {len(report['on_disk_missing_from_manifest'])} "
            f"(e.g. {report['on_disk_missing_from_manifest'][:5]})"
        )
    return "\n".join(lines)
