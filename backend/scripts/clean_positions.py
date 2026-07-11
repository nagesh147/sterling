"""
Issue 17 — audit script for corrupt rows in the `positions` table.

Read-only by default — prints the row IDs whose `entry_spot_price` is 0,
NULL, or non-numeric. Several pre-TTACE seed rows have `entry_spot_price=0`
which fabricates fake "wins" through the analytics aggregations. Run this
script to discover them, then DELETE them manually if you trust the audit.

Usage:
    python scripts/clean_positions.py [--db <path>] [--delete]

`--delete` is opt-in. The default mode never mutates the database — it just
prints the offending IDs and the row count so you can see what would be
removed before doing so.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path


_DEFAULT_DB = Path(__file__).resolve().parent.parent / "sterling_paper.db"


def _audit(db_path: Path) -> list[dict]:
    if not db_path.exists():
        print(f"[clean_positions] db not found: {db_path}", file=sys.stderr)
        return []
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, data FROM positions").fetchall()
        bad: list[dict] = []
        for r in rows:
            try:
                d = json.loads(r["data"]) if r["data"] else {}
            except (TypeError, ValueError):
                d = {}
            esp = d.get("entry_spot_price")
            try:
                esp_v = float(esp) if esp is not None else 0.0
            except (TypeError, ValueError):
                esp_v = 0.0
            if esp_v <= 0:
                bad.append({
                    "id":               r["id"],
                    "entry_spot_price": esp,
                    "underlying":       d.get("underlying"),
                    "entry_ts_ms":      d.get("entry_timestamp_ms"),
                    "status":           d.get("status"),
                    "realized_pnl_usd": d.get("realized_pnl_usd"),
                })
        return bad


def _delete(db_path: Path, ids: list[str]) -> int:
    if not ids:
        return 0
    # Placeholders are only "?" markers (not user data); ids are bound as params.
    placeholders = ",".join("?" for _ in ids)
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.execute(
            f"DELETE FROM positions WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()
        return cur.rowcount or 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Audit positions table for corrupt rows")
    ap.add_argument("--db", default=str(_DEFAULT_DB), help="Path to sterling_paper.db")
    ap.add_argument("--delete", action="store_true",
                    help="Actually delete the corrupt rows (read-only by default)")
    args = ap.parse_args(argv)
    db_path = Path(args.db)
    bad = _audit(db_path)
    if not bad:
        print(f"[clean_positions] no corrupt rows in {db_path}")
        return 0
    print(f"[clean_positions] found {len(bad)} corrupt rows in {db_path}:")
    for row in bad:
        print(" ", json.dumps(row, default=str))
    if args.delete:
        n = _delete(db_path, [r["id"] for r in bad])
        print(f"[clean_positions] deleted {n} rows")
    else:
        print("[clean_positions] dry-run only (pass --delete to apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
