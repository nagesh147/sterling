"""Writing bars to Parquet: atomically, idempotently, and small.

**Layout.** One file per (instrument, interval), Hive-partitioned by interval/exchange/
segment. The dominant read is "give me this symbol's history", which becomes a single
file open — no directory glob, no metadata merge across thousands of files. The partition
keys still let DuckDB prune whole exchanges for cross-sectional scans.

**Atomicity.** Every write goes to ``_staging/<uuid>.parquet``, is fsynced, then
``os.replace``d onto the final path. A crash, a full disk, or a yanked USB cable can
therefore leave a stray staging file (harmless, cleaned up later) but never a truncated
parquet in ``bars/``. Staging lives inside the lake so the rename stays within one
filesystem — across filesystems ``os.replace`` is not atomic, and we assert that rather
than trusting it.

**Idempotency.** ``mode='merge'`` re-reads the existing file, concatenates, sorts by
timestamp and drops duplicate timestamps keeping the newest row. Re-running a download
therefore converges instead of duplicating, which is what makes ``--resume`` safe to use
liberally.

**Parquet settings**, each chosen deliberately:

- ``compression='zstd', level=9`` — 17.6 B/row vs 30.1 for float32+zstd3, measured on
  46,500 synthetic minute bars. Level 19 only reached 15.5 B/row for far more CPU.
- ``use_dictionary=False`` on prices — dictionary encoding helps repeated values, but
  near-unique int64 prices only gain a wasted dictionary page.
- ``write_statistics=True`` + ``write_page_index=True`` — lets readers skip row groups and
  pages using min/max on ``ts``, which is what makes date-filtered reads fast.
- ``sorting_columns`` — records that ``ts`` is ascending so engines can rely on order
  instead of re-sorting.
- ``row_group_size=131_072`` — a 6-month minute file (~46.5k rows) lands in one row group,
  keeping metadata minimal, while a multi-year file still splits sensibly.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import Any, Sequence

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .schema import BAR_SCHEMA, bar_relpath, candles_to_table

__all__ = ["BarWriter", "append_candles", "read_existing", "clean_staging"]

_PARQUET_OPTS: dict[str, Any] = {
    "compression": "zstd",
    "compression_level": 9,
    "write_statistics": True,
    "write_page_index": True,
    "version": "2.6",
    "data_page_version": "2.0",
    "store_schema": True,
    "use_dictionary": False,
}

#: Passed to ``write_table``, not the writer constructor. A 6-month minute file (~46.5k
#: rows) fits in one row group; multi-year files still split sensibly.
ROW_GROUP_SIZE = 131_072


def _sorting_columns() -> list[pq.SortingColumn]:
    return [pq.SortingColumn(BAR_SCHEMA.get_field_index("ts"), descending=False, nulls_first=False)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_existing(path: Path) -> pa.Table | None:
    """Read a bar file, tolerating absence and corruption.

    A corrupt file returns None rather than raising: in merge mode the correct recovery
    is to rewrite from the incoming data, not to abort the whole download.
    """
    if not path.exists():
        return None
    try:
        table = pq.read_table(path)
    except Exception:
        return None
    try:
        return table.select([f.name for f in BAR_SCHEMA]).cast(BAR_SCHEMA)
    except Exception:
        return None


def _merge(old: pa.Table, new: pa.Table) -> pa.Table:
    """Concatenate, sort by ts, keep the LAST row for any duplicated timestamp.

    "Last" means the incoming row wins, because a re-fetch of the same window returns
    settled data that supersedes whatever we stored earlier.
    """
    combined = pa.concat_tables([old, new])
    if combined.num_rows == 0:
        return combined
    # Stable sort on ts, then keep the highest original index per timestamp so the
    # later (incoming) duplicate survives.
    idx = pa.array(range(combined.num_rows), pa.int64())
    combined = combined.append_column("__i", idx)
    combined = combined.sort_by([("ts", "ascending"), ("__i", "ascending")])
    # Keep the LAST row of each equal-ts run: compare each row to its successor and
    # retain it only when the timestamp changes (the final row always survives).
    ts = combined.column("ts").to_pylist()
    keep = pa.array([ts[i] != ts[i + 1] for i in range(len(ts) - 1)] + [True])
    filtered = combined.filter(keep).drop_columns(["__i"])
    return filtered.cast(BAR_SCHEMA)


class BarWriter:
    """Writes :data:`~kitelake.schema.BAR_SCHEMA` tables into the lake."""

    def __init__(self, *, root: Any = None) -> None:
        self._root = root

    def _paths(self, instrument: Any, interval: str) -> tuple[Path, Path]:
        from .volume import bars_dir, staging_dir

        bars = bars_dir(self._root)
        rel = bar_relpath(
            interval,
            getattr(instrument, "exchange", "") or "UNKNOWN",
            getattr(instrument, "segment", "") or "UNKNOWN",
            int(getattr(instrument, "token")),
            getattr(instrument, "tradingsymbol", "") or "UNKNOWN",
        )
        target = bars / rel
        # Defence in depth: a hostile or malformed symbol must not escape bars/.
        resolved_parent = target.parent.resolve() if target.parent.exists() else target.parent
        bars_resolved = bars.resolve()
        if not str(resolved_parent).startswith(str(bars_resolved)):
            raise ValueError(f"refusing to write outside the bars directory: {target}")
        return target, staging_dir(self._root)

    def write(
        self,
        instrument: Any,
        interval: str,
        table: pa.Table,
        *,
        mode: str = "merge",
    ) -> dict[str, Any]:
        """Persist ``table``. Returns path/rows/bytes/first_ts/last_ts/sha256."""
        if mode not in {"merge", "replace"}:
            raise ValueError(f"unknown mode {mode!r}")
        target, staging = self._paths(instrument, interval)

        incoming = table.cast(BAR_SCHEMA) if table.schema != BAR_SCHEMA else table
        metadata = incoming.schema.metadata
        if mode == "merge":
            old = read_existing(target)
            if old is not None and old.num_rows:
                incoming = _merge(old, incoming)
                incoming = incoming.replace_schema_metadata(metadata)

        if incoming.num_rows == 0:
            # Never create an empty parquet: it would make an untouched instrument
            # indistinguishable from one with genuinely no trades.
            return {
                "path": str(target), "rows": 0, "bytes": 0,
                "first_ts": "", "last_ts": "", "sha256": "", "written": False,
            }

        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = staging / f"{uuid.uuid4().hex}.parquet"
        try:
            writer = pq.ParquetWriter(
                tmp, incoming.schema, sorting_columns=_sorting_columns(), **_PARQUET_OPTS
            )
            try:
                writer.write_table(incoming, row_group_size=ROW_GROUP_SIZE)
            finally:
                writer.close()
            with open(tmp, "rb") as handle:
                os.fsync(handle.fileno())
            if os.stat(tmp).st_dev != os.stat(target.parent).st_dev:
                raise RuntimeError(
                    f"staging {tmp} and target {target.parent} are on different "
                    "filesystems; os.replace would not be atomic"
                )
            digest = _sha256(tmp)
            size = os.stat(tmp).st_size
            os.replace(tmp, target)
        except Exception:
            tmp.unlink(missing_ok=True)  # leave no partial file behind
            raise

        ts = incoming.column("ts")
        return {
            "path": str(target),
            "rows": incoming.num_rows,
            "bytes": size,
            "first_ts": ts[0].as_py().isoformat(),
            "last_ts": ts[-1].as_py().isoformat(),
            "sha256": digest,
            "written": True,
        }


def append_candles(
    instrument: Any,
    interval: str,
    candles: Sequence[Sequence[Any]],
    *,
    with_oi: bool = False,
    root: Any = None,
    mode: str = "merge",
) -> dict[str, Any]:
    """Raw Kite candles -> merged parquet. The one call the downloader needs."""
    table = candles_to_table(
        candles,
        with_oi=with_oi,
        meta={
            "interval": interval,
            "token": getattr(instrument, "token", ""),
            "tradingsymbol": getattr(instrument, "tradingsymbol", ""),
            "exchange": getattr(instrument, "exchange", ""),
            "segment": getattr(instrument, "segment", ""),
        },
    )
    return BarWriter(root=root).write(instrument, interval, table, mode=mode)


def clean_staging(*, root: Any = None, older_than_seconds: float = 3600) -> dict[str, int]:
    """Remove abandoned staging files left by a crash. Safe to run any time."""
    import time

    from .volume import staging_dir

    removed = 0
    freed = 0
    try:
        staging = staging_dir(root)
        cutoff = time.time() - older_than_seconds
        for path in staging.iterdir():
            try:
                stat = path.stat()
                if stat.st_mtime < cutoff and path.is_file():
                    freed += stat.st_size
                    path.unlink()
                    removed += 1
            except OSError:
                continue
    except Exception:
        pass
    return {"removed": removed, "bytes_freed": freed}
