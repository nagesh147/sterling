"""SQLite ledger that makes downloads resumable at chunk granularity.

The ledger lives *inside* the lake (``manifest/coverage.sqlite``) because it describes
that lake's contents — unplug the drive and both travel together.

Why chunk-level and not symbol-level: a 6-month minute-bar pull is 3 requests per
instrument. Recording only "symbol done/not done" would re-fetch two good chunks to
recover one bad one, and at 3 requests/second across 10,000 instruments that waste is
measured in hours.

Status vocabulary, and why the distinction matters:

- ``pending`` — planned, not yet attempted.
- ``done``    — fetched, rows written.
- ``empty``   — fetched successfully, zero candles. A **normal** outcome for an illiquid
                stock or a window before the instrument listed. Never retried.
- ``failed``  — the attempt errored. Retried only with ``retry_failed=True``, so a
                transient outage does not silently become a permanent hole.
- ``skipped`` — deliberately not attempted (e.g. instrument delisted mid-range).
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = ["Manifest", "CHUNK_STATUSES"]

CHUNK_STATUSES = ("pending", "done", "empty", "failed", "skipped")
#: Statuses that mean "no further work required for this chunk".
_SETTLED = ("done", "empty", "skipped")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS instruments (
    instrument_token INTEGER PRIMARY KEY,
    tradingsymbol   TEXT NOT NULL DEFAULT '',
    name            TEXT NOT NULL DEFAULT '',
    exchange        TEXT NOT NULL DEFAULT '',
    segment         TEXT NOT NULL DEFAULT '',
    instrument_type TEXT NOT NULL DEFAULT '',
    expiry          TEXT NOT NULL DEFAULT '',
    strike          REAL NOT NULL DEFAULT 0,
    tick_size       REAL NOT NULL DEFAULT 0,
    lot_size        INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS chunks (
    instrument_token INTEGER NOT NULL,
    interval         TEXT NOT NULL,
    chunk_from       TEXT NOT NULL,
    chunk_to         TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',
    rows             INTEGER NOT NULL DEFAULT 0,
    attempts         INTEGER NOT NULL DEFAULT 0,
    error            TEXT NOT NULL DEFAULT '',
    fetched_at       TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (instrument_token, interval, chunk_from)
);
CREATE INDEX IF NOT EXISTS chunks_pending
    ON chunks (interval, status, instrument_token);
CREATE TABLE IF NOT EXISTS symbols (
    instrument_token INTEGER NOT NULL,
    interval         TEXT NOT NULL,
    tradingsymbol    TEXT NOT NULL DEFAULT '',
    exchange         TEXT NOT NULL DEFAULT '',
    segment          TEXT NOT NULL DEFAULT '',
    path             TEXT NOT NULL DEFAULT '',
    rows             INTEGER NOT NULL DEFAULT 0,
    bytes            INTEGER NOT NULL DEFAULT 0,
    first_ts         TEXT NOT NULL DEFAULT '',
    last_ts          TEXT NOT NULL DEFAULT '',
    sha256           TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT '',
    error            TEXT NOT NULL DEFAULT '',
    updated_at       TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (instrument_token, interval)
);
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    universe    TEXT NOT NULL DEFAULT '',
    interval    TEXT NOT NULL DEFAULT '',
    frm         TEXT NOT NULL DEFAULT '',
    to_         TEXT NOT NULL DEFAULT '',
    requested   INTEGER NOT NULL DEFAULT 0,
    completed   INTEGER NOT NULL DEFAULT 0,
    failed      INTEGER NOT NULL DEFAULT 0,
    empty       INTEGER NOT NULL DEFAULT 0,
    rows        INTEGER NOT NULL DEFAULT 0,
    bytes       INTEGER NOT NULL DEFAULT 0,
    notes       TEXT NOT NULL DEFAULT ''
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _d(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


class Manifest:
    """Coverage ledger. Usable as a context manager; safe to reopen repeatedly."""

    def __init__(self, path: str | Path | None = None, *, root: Any = None) -> None:
        if path is None:
            from .volume import manifest_dir

            path = manifest_dir(root) / "coverage.sqlite"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), timeout=30.0, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self._conn.executescript(_SCHEMA)
        self._conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('created_at', ?)", (_now(),)
        )

    def _configure(self) -> None:
        cur = self._conn
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA foreign_keys=ON")
        # WAL is the right choice on ext4, but it needs shared-memory support that some
        # removable filesystems (exFAT via fuse, NTFS-3G) do not provide. Fall back
        # rather than refusing to open the ledger at all.
        try:
            mode = cur.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                raise sqlite3.DatabaseError(f"journal_mode came back as {mode!r}")
            cur.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError:
            cur.execute("PRAGMA journal_mode=DELETE")
            cur.execute("PRAGMA synchronous=FULL")

    # ─── lifecycle ───────────────────────────────────────────────────────────
    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "Manifest":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ─── instruments ─────────────────────────────────────────────────────────
    def upsert_instruments(self, rows: Iterable[dict[str, Any]]) -> int:
        payload = [
            (
                int(r["instrument_token"]),
                str(r.get("tradingsymbol") or ""),
                str(r.get("name") or ""),
                str(r.get("exchange") or ""),
                str(r.get("segment") or ""),
                str(r.get("instrument_type") or ""),
                _d(r.get("expiry") or ""),
                float(r.get("strike") or 0),
                float(r.get("tick_size") or 0),
                int(r.get("lot_size") or 0),
                _now(),
            )
            for r in rows
            if r.get("instrument_token") is not None
        ]
        if not payload:
            return 0
        with self._tx():
            self._conn.executemany(
                """INSERT INTO instruments (instrument_token, tradingsymbol, name, exchange,
                       segment, instrument_type, expiry, strike, tick_size, lot_size, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(instrument_token) DO UPDATE SET
                       tradingsymbol=excluded.tradingsymbol, name=excluded.name,
                       exchange=excluded.exchange, segment=excluded.segment,
                       instrument_type=excluded.instrument_type, expiry=excluded.expiry,
                       strike=excluded.strike, tick_size=excluded.tick_size,
                       lot_size=excluded.lot_size, updated_at=excluded.updated_at""",
                payload,
            )
        return len(payload)

    def instrument(self, token: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM instruments WHERE instrument_token=?", (int(token),)
        ).fetchone()
        return dict(row) if row else None

    def find_instruments(self, tradingsymbol: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM instruments WHERE tradingsymbol=? COLLATE NOCASE",
            (tradingsymbol,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── chunk planning / resume ─────────────────────────────────────────────
    def plan_chunks(
        self, token: int, interval: str, chunks: Sequence[tuple[date, date]]
    ) -> int:
        """Register chunks as pending. Idempotent: existing rows keep their status."""
        payload = [
            (int(token), interval, _d(a), _d(b), "pending", "")
            for a, b in chunks
        ]
        if not payload:
            return 0
        with self._tx():
            self._conn.executemany(
                """INSERT INTO chunks
                       (instrument_token, interval, chunk_from, chunk_to, status, error)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(instrument_token, interval, chunk_from) DO NOTHING""",
                payload,
            )
        return len(payload)

    def pending_chunks(
        self,
        interval: str,
        tokens: Sequence[int] | None = None,
        *,
        retry_failed: bool = False,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Chunks still needing work, oldest-first within each instrument."""
        wanted = ["pending"] + (["failed"] if retry_failed else [])
        sql = (
            "SELECT instrument_token, interval, chunk_from, chunk_to, status, attempts "
            "FROM chunks WHERE interval=? AND status IN (%s)" % ",".join("?" * len(wanted))
        )
        params: list[Any] = [interval, *wanted]
        if tokens is not None:
            if not tokens:
                return []
            sql += " AND instrument_token IN (%s)" % ",".join("?" * len(tokens))
            params.extend(int(t) for t in tokens)
        sql += " ORDER BY instrument_token, chunk_from"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def mark_chunk(
        self,
        token: int,
        interval: str,
        chunk_from: date | str,
        status: str,
        *,
        rows: int = 0,
        error: str | None = None,
    ) -> None:
        if status not in CHUNK_STATUSES:
            raise ValueError(f"unknown chunk status {status!r}")
        with self._tx():
            self._conn.execute(
                """UPDATE chunks
                      SET status=?, rows=?, error=?, attempts=attempts+1, fetched_at=?
                    WHERE instrument_token=? AND interval=? AND chunk_from=?""",
                (status, int(rows), (error or "")[:500], _now(), int(token), interval, _d(chunk_from)),
            )

    def reset_chunks(self, interval: str, tokens: Sequence[int] | None = None) -> int:
        """Return failed chunks to pending — the recovery path after a dead token."""
        sql = "UPDATE chunks SET status='pending', error='' WHERE interval=? AND status='failed'"
        params: list[Any] = [interval]
        if tokens:
            sql += " AND instrument_token IN (%s)" % ",".join("?" * len(tokens))
            params.extend(int(t) for t in tokens)
        with self._tx():
            cur = self._conn.execute(sql, params)
        return cur.rowcount or 0

    def shortfall(self, interval: str, *, min_missing: int = 1) -> list[dict[str, Any]]:
        """Instruments holding fewer rows than their chunks reported fetching.

        This is the fingerprint of a lost write: the ledger says a chunk completed with N
        rows, but the file does not contain them. It caught a real read-modify-write race
        in the writer that silently discarded 21 million candles across 1,394 instruments
        — the chunks were marked ``done``, so an ordinary resume would never have refetched
        them and the lake would have looked finished.

        A small positive difference is normal: ``candles_to_table`` drops malformed rows
        and de-duplicates timestamps, so ``min_missing`` lets callers ignore noise.
        """
        rows = self._conn.execute(
            """
            SELECT s.instrument_token AS instrument_token,
                   s.tradingsymbol    AS tradingsymbol,
                   s.rows             AS stored_rows,
                   COALESCE(f.fetched, 0) AS fetched_rows,
                   COALESCE(f.fetched, 0) - s.rows AS missing
              FROM symbols s
              LEFT JOIN (SELECT instrument_token, SUM(rows) AS fetched
                           FROM chunks WHERE interval = ? GROUP BY instrument_token) f
                ON f.instrument_token = s.instrument_token
             WHERE s.interval = ? AND s.rows > 0
               AND COALESCE(f.fetched, 0) - s.rows >= ?
             ORDER BY missing DESC
            """,
            (interval, interval, int(min_missing)),
        ).fetchall()
        return [dict(r) for r in rows]

    def reset_instruments(self, interval: str, tokens: Sequence[int]) -> int:
        """Return every chunk of these instruments to ``pending`` so it is refetched.

        The parquet files are left in place on purpose: merge mode de-duplicates on
        timestamp, so refetching converges on the complete series rather than duplicating
        what survived.
        """
        if not tokens:
            return 0
        placeholders = ",".join("?" * len(tokens))
        with self._tx():
            cur = self._conn.execute(
                f"""UPDATE chunks SET status='pending', error='', rows=0
                     WHERE interval=? AND instrument_token IN ({placeholders})""",
                (interval, *(int(t) for t in tokens)),
            )
        return cur.rowcount or 0

    def gaps(self, interval: str, token: int) -> list[tuple[str, str]]:
        """Ranges for this instrument that are not settled."""
        rows = self._conn.execute(
            "SELECT chunk_from, chunk_to FROM chunks "
            "WHERE instrument_token=? AND interval=? AND status NOT IN (%s) "
            "ORDER BY chunk_from" % ",".join("?" * len(_SETTLED)),
            (int(token), interval, *_SETTLED),
        ).fetchall()
        return [(r["chunk_from"], r["chunk_to"]) for r in rows]

    # ─── per-symbol rollup ───────────────────────────────────────────────────
    def upsert_symbol(self, token: int, interval: str, **stats: Any) -> None:
        cols = {
            "tradingsymbol": "", "exchange": "", "segment": "", "path": "",
            "rows": 0, "bytes": 0, "first_ts": "", "last_ts": "", "sha256": "",
            "status": "", "error": "",
        }
        values = {k: stats.get(k, default) for k, default in cols.items()}
        with self._tx():
            self._conn.execute(
                """INSERT INTO symbols (instrument_token, interval, tradingsymbol, exchange,
                       segment, path, rows, bytes, first_ts, last_ts, sha256, status, error,
                       updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(instrument_token, interval) DO UPDATE SET
                       tradingsymbol=excluded.tradingsymbol, exchange=excluded.exchange,
                       segment=excluded.segment, path=excluded.path, rows=excluded.rows,
                       bytes=excluded.bytes, first_ts=excluded.first_ts,
                       last_ts=excluded.last_ts, sha256=excluded.sha256,
                       status=excluded.status, error=excluded.error,
                       updated_at=excluded.updated_at""",
                (
                    int(token), interval, str(values["tradingsymbol"]), str(values["exchange"]),
                    str(values["segment"]), str(values["path"]), int(values["rows"]),
                    int(values["bytes"]), str(values["first_ts"]), str(values["last_ts"]),
                    str(values["sha256"]), str(values["status"]), str(values["error"])[:500],
                    _now(),
                ),
            )

    def symbol_status(self, token: int, interval: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM symbols WHERE instrument_token=? AND interval=?",
            (int(token), interval),
        ).fetchone()
        return dict(row) if row else None

    def symbols(self, interval: str | None = None) -> list[dict[str, Any]]:
        if interval:
            rows = self._conn.execute(
                "SELECT * FROM symbols WHERE interval=? ORDER BY tradingsymbol", (interval,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM symbols ORDER BY interval, tradingsymbol").fetchall()
        return [dict(r) for r in rows]

    # ─── runs ────────────────────────────────────────────────────────────────
    def start_run(self, **kw: Any) -> str:
        run_id = uuid.uuid4().hex[:12]
        with self._tx():
            self._conn.execute(
                """INSERT INTO runs (run_id, started_at, universe, interval, frm, to_, requested, notes)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    run_id, _now(), str(kw.get("universe") or ""), str(kw.get("interval") or ""),
                    _d(kw.get("frm") or ""), _d(kw.get("to") or ""),
                    int(kw.get("requested") or 0), str(kw.get("notes") or ""),
                ),
            )
        return run_id

    def finish_run(self, run_id: str, **kw: Any) -> None:
        fields = ("completed", "failed", "empty", "rows", "bytes")
        sets = ", ".join(f"{f}=?" for f in fields)
        with self._tx():
            self._conn.execute(
                f"UPDATE runs SET finished_at=?, {sets}, notes=? WHERE run_id=?",
                (_now(), *(int(kw.get(f) or 0) for f in fields), str(kw.get("notes") or ""), run_id),
            )

    def runs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (int(limit),)
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── aggregate stats ─────────────────────────────────────────────────────
    def stats(self, interval: str | None = None) -> dict[str, Any]:
        where, params = ("WHERE interval=?", (interval,)) if interval else ("", ())
        by_status = {
            r["status"]: r["n"]
            for r in self._conn.execute(
                f"SELECT status, COUNT(*) AS n FROM chunks {where} GROUP BY status", params
            ).fetchall()
        }
        totals = self._conn.execute(
            f"""SELECT COUNT(*) AS n, COALESCE(SUM(rows),0) AS rows FROM chunks {where}""", params
        ).fetchone()
        sym = self._conn.execute(
            f"""SELECT COUNT(*) AS n, COALESCE(SUM(rows),0) AS rows, COALESCE(SUM(bytes),0) AS bytes
                  FROM symbols {where}""",
            params,
        ).fetchone()
        settled = sum(by_status.get(s, 0) for s in _SETTLED)
        total = int(totals["n"] or 0)
        return {
            "interval": interval or "all",
            "chunks_total": total,
            "chunks_by_status": by_status,
            "chunks_settled": settled,
            "chunks_remaining": total - settled,
            "pct_complete": round(100.0 * settled / total, 2) if total else 0.0,
            "candles": int(totals["rows"] or 0),
            "symbols": int(sym["n"] or 0),
            "symbol_rows": int(sym["rows"] or 0),
            "bytes": int(sym["bytes"] or 0),
            "gib": round(int(sym["bytes"] or 0) / 2**30, 3),
            "instruments_known": int(
                self._conn.execute("SELECT COUNT(*) AS n FROM instruments").fetchone()["n"] or 0
            ),
        }

    # ─── internals ───────────────────────────────────────────────────────────
    def _tx(self):
        """Explicit transaction (isolation_level=None means autocommit otherwise)."""
        return _Tx(self._conn)


class _Tx:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def __enter__(self) -> sqlite3.Connection:
        self._conn.execute("BEGIN IMMEDIATE")
        return self._conn

    def __exit__(self, exc_type: object, *_rest: object) -> None:
        if exc_type is None:
            self._conn.execute("COMMIT")
        else:
            self._conn.execute("ROLLBACK")
