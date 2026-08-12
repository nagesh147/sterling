"""A DuckDB catalog over the parquet tree — SQL across the whole lake, zero copies.

DuckDB reads the Hive-partitioned parquet directly, so the catalog is metadata only: no
data is duplicated, and a fresh download is visible to SQL the moment it lands. The views
expose both the raw int64 prices and decoded float rupees, plus ``instrument_token``
recovered from the filename and exchange/segment recovered from the partition keys.

The one place we *do* materialise is :func:`build_catalog`'s ``hot`` option, which copies a
chosen universe into a native DuckDB table ordered by ``(instrument_token, ts)``. Native
storage beats repeated parquet scans for iterative analytics; the tradeoff is disk and
staleness, so it is opt-in.

Operational note: ``temp_directory`` is pinned inside the lake. DuckDB spills large sorts
to disk, and the default would put those spills on the system drive — which on this
machine has ~5 GB free. A big aggregation would fill the root filesystem.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any, Iterator, Sequence

from .config import PRICE_SCALE, VALID_INTERVALS, SECOND_INTERVAL

__all__ = ["catalog_path", "connect", "build_catalog", "catalog_stats", "HOT_TABLE"]

HOT_TABLE = "bars_hot"


def catalog_path(*, root: Any = None) -> Path:
    from .volume import catalog_dir

    return catalog_dir(root) / "lake.duckdb"


def _tune(conn: Any, *, root: Any = None) -> None:
    from .volume import staging_dir

    # 16 cores / 14 GB box: leave headroom for the downloader running concurrently.
    conn.execute("SET threads TO 8")
    conn.execute("SET memory_limit = '4GB'")
    with contextlib.suppress(Exception):
        conn.execute(f"SET temp_directory = '{staging_dir(root)}'")
    with contextlib.suppress(Exception):
        conn.execute("SET preserve_insertion_order = false")


@contextlib.contextmanager
def connect(*, root: Any = None, read_only: bool = False) -> Iterator[Any]:
    """Open the catalog. Creates it on first use unless ``read_only``."""
    import duckdb

    path = catalog_path(root=root)
    if read_only and not path.exists():
        # Nothing to read yet: build a throwaway in-memory catalog so `sql()` still works
        # against the parquet instead of erroring out.
        conn = duckdb.connect(":memory:")
        try:
            _tune(conn, root=root)
            _define_views(conn, root=root)
            yield conn
        finally:
            conn.close()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path), read_only=read_only)
    try:
        _tune(conn, root=root)
        yield conn
    finally:
        conn.close()


def _intervals_present(root: Any = None) -> list[str]:
    from .volume import bars_dir

    base = bars_dir(root, create=False)
    if not base.is_dir():
        return []
    out = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and child.name.startswith("interval="):
            name = child.name.split("=", 1)[1]
            if any(child.rglob("*.parquet")):
                out.append(name)
    return out


def _view_sql(interval: str, glob: str) -> str:
    """One view per interval, decoding prices and recovering identity from the path."""
    return f"""
        SELECT
            regexp_extract(parse_filename(filename), '^([0-9]+)__', 1)::BIGINT
                AS instrument_token,
            regexp_replace(regexp_extract(parse_filename(filename), '__(.*)\\.parquet$', 1),
                           '$', '') AS symbol_file,
            exchange,
            segment,
            ts,
            open  / {PRICE_SCALE}.0 AS open,
            high  / {PRICE_SCALE}.0 AS high,
            low   / {PRICE_SCALE}.0 AS low,
            close / {PRICE_SCALE}.0 AS close,
            volume,
            oi,
            open  AS open_raw,
            high  AS high_raw,
            low   AS low_raw,
            close AS close_raw,
            '{interval}' AS interval
        FROM read_parquet('{glob}', hive_partitioning = true, union_by_name = true,
                          filename = true)
    """


def _define_views(conn: Any, *, root: Any = None) -> list[str]:
    from .volume import bars_dir, instruments_dir

    base = bars_dir(root, create=False)
    created: list[str] = []
    for interval in _intervals_present(root):
        glob = str(base / f"interval={interval}" / "**" / "*.parquet")
        view = f"bars_{interval.replace('minute', 'min')}"
        conn.execute(f"CREATE OR REPLACE VIEW {view} AS {_view_sql(interval, glob)}")
        created.append(view)

    master = instruments_dir(root, create=False) / "latest.parquet"
    if master.exists():
        conn.execute(
            f"CREATE OR REPLACE VIEW instruments AS SELECT * FROM read_parquet('{master}')"
        )
        created.append("instruments")
        # A joined view so users can query by tradingsymbol without knowing tokens.
        if "bars_min" in created:
            conn.execute(
                """CREATE OR REPLACE VIEW bars AS
                   SELECT i.tradingsymbol, i.name, i.instrument_type, b.*
                     FROM bars_min b
                     LEFT JOIN instruments i USING (instrument_token)"""
            )
            created.append("bars")
    return created


def build_catalog(
    *,
    hot_universe: str | None = None,
    interval: str = "minute",
    root: Any = None,
) -> dict[str, Any]:
    """Create/refresh the catalog. Idempotent."""
    result: dict[str, Any] = {
        "path": str(catalog_path(root=root)),
        "views": [],
        "intervals": _intervals_present(root),
        "hot_rows": 0,
        "hot_seconds": 0.0,
        "parquet_seconds": 0.0,
        "speedup": 0.0,
    }
    if not result["intervals"]:
        result["note"] = (
            "No bars in the lake yet — the catalog defines no views. "
            "Run a download first, then `kitelake catalog`."
        )
        return result

    import time

    with connect(root=root) as conn:
        result["views"] = _define_views(conn, root=root)

        if hot_universe:
            from .universe import resolve_universe

            instruments = resolve_universe(hot_universe, root=root)
            tokens = [i.token for i in instruments]
            view = f"bars_{interval.replace('minute', 'min')}"
            if view in result["views"] and tokens:
                token_list = ",".join(str(t) for t in tokens)
                conn.execute(f"DROP TABLE IF EXISTS {HOT_TABLE}")
                conn.execute(
                    f"""CREATE TABLE {HOT_TABLE} AS
                        SELECT * FROM {view}
                         WHERE instrument_token IN ({token_list})
                         ORDER BY instrument_token, ts"""
                )
                result["hot_rows"] = conn.execute(
                    f"SELECT COUNT(*) FROM {HOT_TABLE}"
                ).fetchone()[0]
                result["hot_universe"] = hot_universe
                result["hot_instruments"] = len(tokens)

                if not result["hot_rows"]:
                    # The universe resolved fine but none of it is downloaded yet, so a
                    # timing comparison on an empty table would be meaningless.
                    result["hot_note"] = (
                        f"'{hot_universe}' resolved to {len(tokens):,} instruments but none "
                        f"have {interval} bars in the lake yet — nothing to materialise."
                    )
                else:
                    # Measure rather than assert the speedup.
                    probe = "SELECT instrument_token, COUNT(*), AVG(close) FROM {} GROUP BY 1"
                    t0 = time.perf_counter()
                    conn.execute(probe.format(HOT_TABLE)).fetchall()
                    result["hot_seconds"] = round(time.perf_counter() - t0, 4)
                    t0 = time.perf_counter()
                    conn.execute(
                        f"SELECT instrument_token, COUNT(*), AVG(close) FROM {view} "
                        f"WHERE instrument_token IN ({token_list}) GROUP BY 1"
                    ).fetchall()
                    result["parquet_seconds"] = round(time.perf_counter() - t0, 4)
                    if result["hot_seconds"] > 0:
                        result["speedup"] = round(
                            result["parquet_seconds"] / result["hot_seconds"], 2
                        )

    try:
        result["catalog_bytes"] = catalog_path(root=root).stat().st_size
    except OSError:
        result["catalog_bytes"] = 0
    return result


def catalog_stats(*, root: Any = None) -> dict[str, Any]:
    """Row/instrument counts per interval, straight from the parquet."""
    out: dict[str, Any] = {"intervals": {}, "path": str(catalog_path(root=root))}
    intervals = _intervals_present(root)
    if not intervals:
        out["note"] = "no bars stored yet"
        return out
    with connect(root=root, read_only=False) as conn:
        _define_views(conn, root=root)
        for interval in intervals:
            view = f"bars_{interval.replace('minute', 'min')}"
            try:
                row = conn.execute(
                    f"""SELECT COUNT(*) AS rows,
                               COUNT(DISTINCT instrument_token) AS instruments,
                               MIN(ts) AS first_ts, MAX(ts) AS last_ts
                          FROM {view}"""
                ).fetchone()
            except Exception as exc:
                out["intervals"][interval] = {"error": str(exc)[:200]}
                continue
            out["intervals"][interval] = {
                "rows": row[0],
                "instruments": row[1],
                "first_ts": str(row[2]),
                "last_ts": str(row[3]),
            }
    return out
