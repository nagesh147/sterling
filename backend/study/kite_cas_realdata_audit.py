"""Validate CAS session mechanics against existing broker minute parquet files.

Read-only inputs; no broker requests, synthetic prices, strategy optimization,
or orders. Run from the repo root:
PYTHONPATH=backend backend/.venv/bin/python backend/study/kite_cas_realdata_audit.py
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

from app.services.kite_engine import market_hours

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LAKE = Path("/run/media/nageshmadaram/3f36ac07-fdbe-48c1-9514-ecf65c6619b0/SterlingLake")
IST = ZoneInfo("Asia/Kolkata")
TOKENS = (256265, 2939649, 779521)


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return sha256(source.read()).hexdigest()


def audit(lake: Path) -> dict:
    manifest = lake / "manifest/coverage.sqlite"
    # The immutable URI permits a read-only ext4 mount without creating WAL/SHM.
    connection = sqlite3.connect(f"{manifest.as_uri()}?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        inventory = dict(connection.execute(
            "SELECT count(*) AS symbols,sum(rows) AS rows,max(last_ts) AS last_utc FROM symbols"
        ).fetchone())
        inventory["derivative_bar_symbols"] = connection.execute(
            "SELECT count(*) FROM symbols WHERE segment LIKE '%FUT%' OR segment LIKE '%OPT%'"
        ).fetchone()[0]
        selected = list(connection.execute(
            "SELECT * FROM symbols WHERE interval='minute' AND instrument_token IN (?,?,?)",
            TOKENS,
        ))
    finally:
        connection.close()
    if len(selected) != len(TOKENS):
        raise ValueError("Expected exactly NIFTY 50, LT and SBIN minute datasets")

    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Observed cash/index minute timestamps and OHLC integrity around CAS implementation",
        "policy_version": market_hours.POLICY_VERSION,
        "cas_effective_date": market_hours.CAS_START.isoformat(),
        "lake_root": str(lake),
        "manifest_sha256": digest(manifest),
        "manifest_inventory_not_full_file_verification": inventory,
        "code_sha256": {
            str(path.relative_to(ROOT)): digest(path)
            for path in (Path(__file__).resolve(), Path(market_hours.__file__).resolve())
        },
        "sources": [
            "https://www.nseindia.com/static/products-services/closing-auction-session",
            "https://www.sebi.gov.in/legal/circulars/jan-2026/introduction-of-closing-auction-session-cas-in-the-equity-cash-segment-and-certain-modifications-in-the-pre-open-auction-session_99122.html",
        ],
        "datasets": [],
        "limitations": [
            "Existing lake parquet and acquisition manifest; no independent exchange certification.",
            "Manifest inventory counts are metadata, not a full lake data-quality audit.",
            "Selected observations end August 13, 2026; they contain no September 4 recorded signals.",
            "NIFTY 50 is an index, not an executable contract or a CAS-eligible cash stock.",
            "Cash minute bars do not establish auction fills, derivative liquidity, bid/ask or profitability.",
            "No derivative bar symbols in this manifest; lake ticks directory is empty.",
            "September 7 pre-open rules are future to these data and cannot be empirically validated here.",
        ],
    }
    for row in selected:
        path = Path(row["path"])
        # Resolve manifest paths by their stable lake-relative portion after relocation.
        relative = path.parts[path.parts.index("SterlingLake") + 1:]
        path = lake.joinpath(*relative)
        table = pq.ParquetFile(path).read(columns=["ts", "open", "high", "low", "close", "volume"])
        bars = table.to_pylist()
        sessions = defaultdict(list)
        invalid = 0
        nonincreasing = 0
        previous = None
        for bar in bars:
            ts = bar["ts"].astimezone(IST)
            sessions[ts.date()].append(ts)
            invalid += int(not (
                bar["low"] > 0 and bar["low"] <= min(bar["open"], bar["close"])
                and bar["high"] >= max(bar["open"], bar["close"])
                and bar["volume"] >= 0
            ))
            nonincreasing += int(previous is not None and ts <= previous)
            previous = ts
        cash_stock = row["segment"] == "NSE"
        failures = []
        samples = []
        blocked_index_rows = 0
        phase_counts = Counter()
        for day, stamps in sorted(sessions.items()):
            expected_close = datetime.combine(day, market_hours.continuous_close(
                day, "NSE", cas_eligible=cash_stock), tzinfo=IST)
            expected_open = datetime.combine(day, time(9, 15), tzinfo=IST)
            expected_rows = int((expected_close - expected_open).total_seconds() / 60)
            summary = {
                "date": day.isoformat(), "bars": len(stamps),
                "first_ist": stamps[0].isoformat(), "last_ist": stamps[-1].isoformat(),
                "expected_continuous_close_ist": expected_close.isoformat(),
                "expected_minute_rows": expected_rows,
            }
            if not (stamps[0] == expected_open and stamps[-1] + timedelta(minutes=1) == expected_close
                    and len(stamps) == expected_rows
                    and all(b - a == timedelta(minutes=1) for a, b in zip(stamps, stamps[1:]))):
                failures.append(summary)
            if day >= market_hours.CAS_START or day.isoformat() == "2026-07-31":
                samples.append(summary)
            if day >= market_hours.CAS_START:
                for ts in stamps:
                    phase_counts[market_hours.session_phase(ts, exchange="NSE", cas_eligible=cash_stock)] += 1
                    if not cash_stock and ts.time() >= time(15, 15):
                        blocked_index_rows += int(market_hours.entry_block_reason(
                            ts, exchange="NFO", cash_signal=True) == "cash_signal_auction")
        actual_hash = digest(path)
        report["datasets"].append({
            "instrument": row["tradingsymbol"], "instrument_token": row["instrument_token"],
            "path": str(path), "sha256": actual_hash,
            "manifest_sha256_matches": actual_hash == row["sha256"],
            "bars": len(bars), "manifest_rows_match": len(bars) == row["rows"],
            "first_utc": bars[0]["ts"].isoformat(), "last_utc": bars[-1]["ts"].isoformat(),
            "invalid_ohlc_bars": invalid, "nonincreasing_timestamps": nonincreasing,
            "session_days_checked": len(sessions), "session_boundary_failures": failures,
            "post_cas_bars": sum(len(v) for k, v in sessions.items() if k >= market_hours.CAS_START),
            "post_cas_session_phases": dict(phase_counts),
            "post_cas_index_rows_at_or_after_1515_blocked_for_new_cash_signals": blocked_index_rows,
            "transition_and_post_cas_days": samples,
        })
    report["selected_total_bars"] = sum(x["bars"] for x in report["datasets"])
    report["selected_post_cas_bars"] = sum(x["post_cas_bars"] for x in report["datasets"])
    report["observed_session_validation_passed"] = all(
        x["manifest_sha256_matches"] and x["manifest_rows_match"]
        and not x["invalid_ohlc_bars"] and not x["nonincreasing_timestamps"]
        and not x["session_boundary_failures"] for x in report["datasets"]
    )
    report["live_readiness"] = "NOT_ESTABLISHED_BY_CASH_SESSION_DATA"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", type=Path, default=DEFAULT_LAKE)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/audits/2026-09-06-kite-cas-realdata.json")
    args = parser.parse_args()
    report = audit(args.lake.resolve())
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"artifact": str(args.output), **{k: report[k] for k in (
        "selected_total_bars", "selected_post_cas_bars", "observed_session_validation_passed", "live_readiness"
    )}}))
    if not report["observed_session_validation_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
