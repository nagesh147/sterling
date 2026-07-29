"""Low-level, transactional SQLite access for Navigator's own tables
(`navigator_configs`, `navigator_config_audit`, `navigator_option_snapshots`,
`navigator_feature_snapshots`, `navigator_signal_events`,
`navigator_calibration_state` — see `app.services.db._create_tables`).

Unlike most of `app.services.db`, every function here RAISES on failure
instead of silently swallowing it. Navigator config persistence must
"validate before writing; write transactionally; ... return a visible API
error; never silently force a user-disabled setting back on" (spec §3.2.C) —
that is only possible if failures are never swallowed at the storage layer.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from app.core.logging import get_logger
from app.services import db

log = get_logger(__name__)


class NavigatorStorageError(RuntimeError):
    """Raised on any Navigator persistence failure. Callers must surface
    this as a visible error and leave prior in-memory/served state
    untouched — never catch-and-continue."""


class RevisionConflict(NavigatorStorageError):
    """Optimistic-concurrency conflict: `expected_revision` did not match
    the currently stored row. `current` carries the row as it actually
    stands so the caller (an HTTP 409 handler) can show/merge it."""

    def __init__(self, message: str, current: Optional[dict]):
        super().__init__(message)
        self.current = current


def _require_available() -> None:
    if not db.is_available():
        raise NavigatorStorageError("SQLite store is not available")


# ── navigator_configs / navigator_config_audit ──────────────────────────

def fetch_config_row(user_id: str) -> Optional[dict]:
    _require_available()
    try:
        with db.connection() as c:
            row = c.execute(
                "SELECT * FROM navigator_configs WHERE user_id=?", (user_id,)
            ).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to read config for {user_id}: {exc}") from exc


def insert_default_config_if_absent(
    user_id: str,
    *,
    schema_version: int,
    payload_json: str,
    activation_watermark_ms: int,
    calibration_readiness: str,
    now_ms: int,
) -> dict:
    """Idempotent: creates revision=1 the first time this user is seen, and
    is a no-op (returning the existing row unchanged) on every call after."""
    _require_available()
    try:
        with db.connection() as c:
            c.execute(
                """
                INSERT OR IGNORE INTO navigator_configs
                    (user_id, schema_version, revision, payload_json,
                     activation_watermark_ms, calibration_readiness,
                     calibration_report_id, created_at_ms, updated_at_ms)
                VALUES (?, ?, 1, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    user_id, schema_version, payload_json,
                    activation_watermark_ms, calibration_readiness,
                    now_ms, now_ms,
                ),
            )
            row = c.execute(
                "SELECT * FROM navigator_configs WHERE user_id=?", (user_id,)
            ).fetchone()
        if row is None:
            raise NavigatorStorageError(f"failed to materialize default config for {user_id}")
        return dict(row)
    except sqlite3.Error as exc:
        raise NavigatorStorageError(
            f"failed to create default config for {user_id}: {exc}"
        ) from exc


def compare_and_swap_config(
    user_id: str,
    *,
    expected_revision: int,
    new_revision: int,
    schema_version: int,
    payload_json: str,
    activation_watermark_ms: int,
    calibration_readiness: str,
    calibration_report_id: Optional[str],
    now_ms: int,
    previous_hash: Optional[str],
    new_hash: str,
) -> dict:
    """Atomically update iff the stored revision still equals
    `expected_revision`; raises `RevisionConflict` otherwise. The single
    `UPDATE ... WHERE user_id=? AND revision=?` statement IS the compare-
    and-swap — SQLite serializes writers at the file level, so no extra
    locking is needed for this to be a true CAS."""
    _require_available()
    try:
        with db.connection() as c:
            cur = c.execute(
                """
                UPDATE navigator_configs
                SET schema_version=?, revision=?, payload_json=?,
                    activation_watermark_ms=?, calibration_readiness=?,
                    calibration_report_id=?, updated_at_ms=?
                WHERE user_id=? AND revision=?
                """,
                (
                    schema_version, new_revision, payload_json,
                    activation_watermark_ms, calibration_readiness,
                    calibration_report_id, now_ms,
                    user_id, expected_revision,
                ),
            )
            if cur.rowcount != 1:
                current = c.execute(
                    "SELECT * FROM navigator_configs WHERE user_id=?", (user_id,)
                ).fetchone()
                raise RevisionConflict(
                    f"expected_revision={expected_revision} does not match the "
                    "currently stored config for this user",
                    dict(current) if current else None,
                )
            c.execute(
                """
                INSERT INTO navigator_config_audit
                    (user_id, revision, changed_at_ms, previous_hash, new_hash, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, new_revision, now_ms, previous_hash, new_hash, payload_json),
            )
            row = c.execute(
                "SELECT * FROM navigator_configs WHERE user_id=?", (user_id,)
            ).fetchone()
        return dict(row)
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to save config for {user_id}: {exc}") from exc


def fetch_config_audit(user_id: str, limit: int = 50) -> list[dict]:
    _require_available()
    try:
        with db.connection() as c:
            rows = c.execute(
                "SELECT * FROM navigator_config_audit WHERE user_id=? "
                "ORDER BY revision DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to read config audit for {user_id}: {exc}") from exc


# ── navigator_option_snapshots (Phase 3) ────────────────────────────────

def insert_option_snapshot(snapshot: dict) -> bool:
    """Insert one contract sample. Returns False (not an error) when the
    row already exists for `(account_scope, instrument_token,
    sample_bucket_ms)` — the sampler is expected to retry/resume without
    ever producing a duplicate sample."""
    _require_available()
    cols = (
        "account_scope", "underlying", "spot_token", "spot", "exchange",
        "expiry", "instrument_token", "tradingsymbol", "option_type",
        "strike", "lot_size", "tick_size", "bid", "ask", "last_price",
        "mid", "implied_volatility", "open_interest", "cumulative_volume",
        "exchange_timestamp_ms", "received_at_ms", "sample_bucket_ms",
        "quote_quality", "config_revision",
    )
    placeholders = ", ".join("?" for _ in cols)
    try:
        with db.connection() as c:
            cur = c.execute(
                f"INSERT OR IGNORE INTO navigator_option_snapshots "
                f"({', '.join(cols)}) VALUES ({placeholders})",
                tuple(snapshot.get(col) for col in cols),
            )
        return cur.rowcount == 1
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to insert option snapshot: {exc}") from exc


def fetch_option_snapshots(
    account_scope: str, underlying: str, expiry: str, since_bucket_ms: int, limit: int = 5000
) -> list[dict]:
    _require_available()
    try:
        with db.connection() as c:
            rows = c.execute(
                "SELECT * FROM navigator_option_snapshots "
                "WHERE account_scope=? AND underlying=? AND expiry=? AND sample_bucket_ms>=? "
                "ORDER BY sample_bucket_ms ASC LIMIT ?",
                (account_scope, underlying, expiry, since_bucket_ms, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to read option snapshots: {exc}") from exc


def fetch_latest_option_snapshots(
    account_scope: str, underlying: str, *, since_bucket_ms: int, limit: int = 5000
) -> list[dict]:
    """Read recent chain samples across expiries for one underlying, oldest
    first. Used by the live Navigator evaluator; unlike the request-facing
    endpoints, this is outside the hot request path and bounded."""
    _require_available()
    try:
        with db.connection() as c:
            rows = c.execute(
                "SELECT * FROM navigator_option_snapshots "
                "WHERE account_scope=? AND underlying=? AND sample_bucket_ms>=? "
                "ORDER BY sample_bucket_ms ASC, instrument_token ASC LIMIT ?",
                (account_scope, underlying, since_bucket_ms, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to read recent option snapshots: {exc}") from exc


def delete_old_option_snapshots(cutoff_ms: int) -> int:
    _require_available()
    try:
        with db.connection() as c:
            cur = c.execute("DELETE FROM navigator_option_snapshots WHERE sample_bucket_ms<?", (cutoff_ms,))
            return int(cur.rowcount or 0)
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to delete old option snapshots: {exc}") from exc


def delete_old_feature_snapshots(cutoff_ms: int) -> int:
    _require_available()
    try:
        with db.connection() as c:
            cur = c.execute("DELETE FROM navigator_feature_snapshots WHERE observed_at_ms<?", (cutoff_ms,))
            return int(cur.rowcount or 0)
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to delete old feature snapshots: {exc}") from exc


# ── navigator_feature_snapshots (Phase 2/4) ─────────────────────────────

def insert_feature_snapshot(snapshot: dict) -> bool:
    """Idempotent by `(user_id, underlying, timeframe, bar_close_ms,
    config_revision, input_hash)` — replaying the same inputs never creates
    a duplicate row."""
    _require_available()
    cols = (
        "user_id", "underlying", "timeframe", "bar_close_ms", "observed_at_ms",
        "config_revision", "model_versions_json", "quality", "avwap_json",
        "range_json", "volatility_json", "flow_json", "gamma_json", "input_hash",
    )
    placeholders = ", ".join("?" for _ in cols)
    try:
        with db.connection() as c:
            cur = c.execute(
                f"INSERT OR IGNORE INTO navigator_feature_snapshots "
                f"({', '.join(cols)}) VALUES ({placeholders})",
                tuple(snapshot.get(col) for col in cols),
            )
        return cur.rowcount == 1
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to insert feature snapshot: {exc}") from exc


# ── navigator_signal_events (Phase 4/5) ─────────────────────────────────

def insert_signal_event(event: dict) -> bool:
    """Immutable insert keyed on `decision_id`. Returns False (not an error)
    if this decision was already stored — duplicate replay must never create
    a duplicate event."""
    _require_available()
    cols = (
        "decision_id", "user_id", "underlying", "bar_close_ms", "generated_at_ms",
        "direction", "status", "effective_score", "execution_eligible",
        "config_revision", "payload_json",
    )
    placeholders = ", ".join("?" for _ in cols)
    try:
        with db.connection() as c:
            cur = c.execute(
                f"INSERT OR IGNORE INTO navigator_signal_events "
                f"({', '.join(cols)}) VALUES ({placeholders})",
                tuple(event.get(col) for col in cols),
            )
        return cur.rowcount == 1
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to insert signal event: {exc}") from exc


def fetch_signal_event(decision_id: str) -> Optional[dict]:
    _require_available()
    try:
        with db.connection() as c:
            row = c.execute(
                "SELECT * FROM navigator_signal_events WHERE decision_id=?", (decision_id,)
            ).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to read signal event {decision_id}: {exc}") from exc


def fetch_signal_events_page(
    user_id: str,
    *,
    underlying: Optional[str] = None,
    before_generated_at_ms: Optional[int] = None,
    before_decision_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Cursor-paginated, newest-first, tie-safe on
    (generated_at_ms, decision_id) — a whole scan's worth of decisions can
    legitimately share one `generated_at_ms`, so ordering/paging on that
    column alone can silently skip the rest of a tied group when a page
    boundary lands inside it. Pass the last row's `generated_at_ms` AND
    `decision_id` back in as the next page's cursor."""
    _require_available()
    clauses = ["user_id=?"]
    params: list = [user_id]
    if underlying:
        clauses.append("underlying=?")
        params.append(underlying)
    if before_generated_at_ms is not None and before_decision_id is not None:
        clauses.append("(generated_at_ms < ? OR (generated_at_ms = ? AND decision_id < ?))")
        params.extend([before_generated_at_ms, before_generated_at_ms, before_decision_id])
    elif before_generated_at_ms is not None:
        clauses.append("generated_at_ms<?")
        params.append(before_generated_at_ms)
    where = " AND ".join(clauses)
    params.append(limit)
    try:
        with db.connection() as c:
            rows = c.execute(
                f"SELECT * FROM navigator_signal_events WHERE {where} "
                f"ORDER BY generated_at_ms DESC, decision_id DESC LIMIT ?",
                tuple(params),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to page signal events: {exc}") from exc


def fetch_all_signal_events(user_id: str, *, limit: int = 5000) -> list[dict]:
    """Every decision this user has accumulated, OLDEST first — the input to
    calibration scoring, which needs the full chronological record rather
    than the newest-first page `fetch_signal_events_page` serves the UI.
    Bounded by `limit` so a very long history can't blow up memory; the
    oldest decisions are the ones kept, since a chronological train/eval
    split is meaningless without them."""
    _require_available()
    try:
        with db.connection() as c:
            rows = c.execute(
                "SELECT * FROM navigator_signal_events WHERE user_id=? "
                "ORDER BY bar_close_ms ASC, decision_id ASC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to read signal events for {user_id}: {exc}") from exc


# ── navigator_calibration_state (Phase 7/8) ─────────────────────────────

def insert_calibration_state(state: dict) -> None:
    _require_available()
    cols = (
        "user_id", "report_id", "model_version", "cohort", "train_window_json",
        "validation_window_json", "sample_count", "metrics_json", "artifact_hash",
        "promotion_state", "created_at_ms",
    )
    placeholders = ", ".join("?" for _ in cols)
    try:
        with db.connection() as c:
            c.execute(
                f"INSERT INTO navigator_calibration_state ({', '.join(cols)}) "
                f"VALUES ({placeholders})",
                tuple(state.get(col) for col in cols),
            )
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to insert calibration state: {exc}") from exc


def fetch_latest_calibration_state(user_id: str) -> Optional[dict]:
    _require_available()
    try:
        with db.connection() as c:
            row = c.execute(
                "SELECT * FROM navigator_calibration_state WHERE user_id=? "
                "ORDER BY created_at_ms DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"failed to read calibration state: {exc}") from exc


# ── retention (spec §14.7) ───────────────────────────────────────────────

@dataclass(frozen=True)
class RetentionResult:
    option_snapshots_deleted: int
    feature_snapshots_deleted: int
    oldest_option_snapshot_ms: Optional[int]
    oldest_feature_snapshot_ms: Optional[int]
    database_bytes: Optional[int]


def _delete_in_batches(c, table: str, ts_column: str, cutoff_ms: int, batch_size: int) -> int:
    """Small indexed batches, never a single unbounded DELETE — this always
    runs off the request thread (called from a background job, see
    spec §14.7 'never on the request thread')."""
    deleted = 0
    while True:
        cur = c.execute(
            f"DELETE FROM {table} WHERE rowid IN "
            f"(SELECT rowid FROM {table} WHERE {ts_column} < ? LIMIT ?)",
            (cutoff_ms, batch_size),
        )
        deleted += cur.rowcount
        if cur.rowcount < batch_size:
            break
    return deleted


def run_retention(*, raw_days: int, feature_days: int, now_ms: int, batch_size: int = 500) -> RetentionResult:
    """Deletes option snapshots older than `raw_days` and feature/signal
    rows older than `feature_days`, in bounded batches. Raw snapshots are
    only ever this old once their derived feature snapshot (computed within
    seconds of sampling) has long since been persisted — retention never
    races feature computation in practice, since `raw_days` covers many
    sampling cycles."""
    _require_available()
    raw_cutoff_ms = now_ms - raw_days * 86_400_000
    feature_cutoff_ms = now_ms - feature_days * 86_400_000
    try:
        with db.connection() as c:
            option_deleted = _delete_in_batches(c, "navigator_option_snapshots", "sample_bucket_ms", raw_cutoff_ms, batch_size)
            feature_deleted = _delete_in_batches(c, "navigator_feature_snapshots", "bar_close_ms", feature_cutoff_ms, batch_size)
            oldest_option = c.execute("SELECT MIN(sample_bucket_ms) AS m FROM navigator_option_snapshots").fetchone()
            oldest_feature = c.execute("SELECT MIN(bar_close_ms) AS m FROM navigator_feature_snapshots").fetchone()
            page_count = c.execute("PRAGMA page_count").fetchone()
            page_size = c.execute("PRAGMA page_size").fetchone()
        db_bytes = int(page_count[0]) * int(page_size[0]) if page_count and page_size else None
        result = RetentionResult(
            option_snapshots_deleted=option_deleted, feature_snapshots_deleted=feature_deleted,
            oldest_option_snapshot_ms=oldest_option["m"] if oldest_option else None,
            oldest_feature_snapshot_ms=oldest_feature["m"] if oldest_feature else None,
            database_bytes=db_bytes,
        )
        log.info(
            "navigator.retention.completed option_deleted=%s feature_deleted=%s db_bytes=%s",
            result.option_snapshots_deleted, result.feature_snapshots_deleted, result.database_bytes,
        )
        return result
    except sqlite3.Error as exc:
        raise NavigatorStorageError(f"retention run failed: {exc}") from exc
