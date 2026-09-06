"""Does the lake hold price history for the contracts this strategy actually trades?

Release gate P0-5 asks for a real EXECUTABLE-contract dataset. The engine buys
NFO/BFO options and futures, so cash and index bars — however many of them there
are — cannot answer it. This audit reads the lake's own coverage manifest and
reports, per exchange and segment, what has bars versus what is merely catalogued
in the instrument master.

Read-only: the manifest is copied to a temporary file and opened from there, so a
lake mounted read-only (which it should be) is never written to, not even by
SQLite's own locking.

    python study/kite_derivative_coverage_audit.py --lake <path> --out report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any, Dict

DEFAULT_LAKE = Path("/run/media/nageshmadaram/3f36ac07-fdbe-48c1-9514-ecf65c6619b0/SterlingLake")

#: Segments whose instruments are executable by this strategy. Anything outside
#: this set is context for a signal, never the thing an order is placed against.
DERIVATIVE_SEGMENTS = ("NFO-OPT", "NFO-FUT", "BFO-OPT", "BFO-FUT")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(lake: Path) -> Dict[str, Any]:
    manifest = lake / "manifest" / "coverage.sqlite"
    if not manifest.exists():
        raise SystemExit(f"no coverage manifest at {manifest}")
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "coverage.sqlite"
        shutil.copy2(manifest, local)
        conn = sqlite3.connect(local)
        conn.row_factory = sqlite3.Row

        bars = [dict(r) for r in conn.execute(
            """SELECT exchange, segment, COUNT(*) AS symbols, SUM(rows) AS rows,
                      MIN(first_ts) AS first_ts, MAX(last_ts) AS last_ts
                 FROM symbols GROUP BY exchange, segment ORDER BY symbols DESC""")]
        master = [dict(r) for r in conn.execute(
            """SELECT exchange, segment, instrument_type, COUNT(*) AS instruments
                 FROM instruments GROUP BY exchange, segment, instrument_type
                ORDER BY instruments DESC""")]
        placeholders = ",".join("?" * len(DERIVATIVE_SEGMENTS))
        derivative_bars = [dict(r) for r in conn.execute(
            f"""SELECT exchange, segment, COUNT(*) AS symbols, SUM(rows) AS rows
                  FROM symbols WHERE segment IN ({placeholders})
                 GROUP BY exchange, segment""", DERIVATIVE_SEGMENTS)]
        expiries = [dict(r) for r in conn.execute(
            f"""SELECT segment, MIN(expiry) AS earliest_expiry,
                       MAX(expiry) AS latest_expiry, COUNT(*) AS instruments,
                       MAX(updated_at) AS master_snapshot
                  FROM instruments WHERE segment IN ({placeholders})
                 GROUP BY segment""", DERIVATIVE_SEGMENTS)]
        totals = conn.execute(
            "SELECT COUNT(*) AS symbols, SUM(rows) AS rows FROM symbols").fetchone()

    derivative_rows = sum(int(r["rows"] or 0) for r in derivative_bars)
    return {
        "lake": str(lake),
        "manifest_sha256": _sha256(manifest),
        "lake_id": json.loads((lake / "LAKE_ID.json").read_text())
                   if (lake / "LAKE_ID.json").exists() else None,
        "total_symbols_with_bars": int(totals["symbols"] or 0),
        "total_bar_rows": int(totals["rows"] or 0),
        "bars_by_exchange_segment": bars,
        "instrument_master_by_segment": master,
        "derivative_bars": derivative_bars,
        "derivative_bar_rows": derivative_rows,
        "derivative_master_expiries": expiries,
        # The instrument master lists LIVE contracts only. An option that has
        # already expired is not in it, so its instrument_token — the key Kite's
        # historical endpoint is addressed by — is not discoverable any more.
        # Option history therefore cannot be back-filled through the supported
        # API; it has to be accumulated forward, or bought from a vendor.
        "executable_contract_dataset_present": derivative_rows > 0,
        "verdict": ("EXECUTABLE_CONTRACT_HISTORY_PRESENT" if derivative_rows > 0
                    else "NO_EXECUTABLE_CONTRACT_HISTORY"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", type=Path, default=DEFAULT_LAKE)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = audit(args.lake)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        report = {**report, "artifact": str(args.out)}
    print(json.dumps({k: report[k] for k in (
        "total_symbols_with_bars", "total_bar_rows", "derivative_bar_rows",
        "executable_contract_dataset_present", "verdict")}))


if __name__ == "__main__":
    main()
