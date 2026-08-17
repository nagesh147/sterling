"""Run the trial F-101 E2E path on the entitled bars+ticks window.

Does not unlock F-101. Does not write f101_parameters_v1.json.
Does not authorize ExecutionGate or connect Kite.
Output is labeled TRIAL_NOT_A197 and is not an A197 calibration.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("STERLING_DB_PATH", str(ROOT / "backend" / "sterling_paper.db"))

from app.engines.adaptive_edge.f101 import (
    TRIAL_STATUS,
    dump_f101_parameters,
    estimate_trial_parameters,
    load_f101_parameters,
    trial_identity_parameters,
)
from app.engines.adaptive_edge.feature_engine import FeatureStatus
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.trial_dataset import collect_valid_feature_values, score_trial_bars
from app.services.providers.truedata.bar_history import BarHistoryAcquirer, bars_to_canonical_sequence
from app.services.providers.truedata.bar_store import BarStore
from app.services.providers.truedata.tick_history import ticks_to_canonical_sequence
from app.services.providers.truedata.tick_store import TickStore

IST = ZoneInfo("Asia/Kolkata")


def _parse_provider_ts(value: str) -> datetime:
    text = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=IST)
        except ValueError:
            continue
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)
    return parsed


def _tick_span(store: TickStore, symbol: str) -> tuple[datetime, datetime]:
    rows = store.load(symbol)
    if not rows:
        raise SystemExit(f"FAILURE: no ticks for {symbol} in tick store")
    times = [_parse_provider_ts(str(row["timestamp"])) for row in rows if row.get("timestamp")]
    return min(times), max(times)


async def _maybe_fetch_bars(args: argparse.Namespace, start: datetime, end: datetime) -> None:
    if not args.fetch_bars:
        return
    from app.services import db
    from app.services.providers.truedata import credentials as creds

    db.init()
    creds.bootstrap()
    account = creds.get_active("default")
    if not account or account.id == "TD-ENV":
        raise SystemExit("FAILURE: No active TrueData credential configured in database.")
    print(f"ACCOUNT_ID: {account.id}")
    print(f"USERNAME_HINT: {account.username_hint()}")
    client = creds.build_client(account)
    store = BarStore(args.bar_store)
    acquirer = BarHistoryAcquirer(client, store)
    try:
        result = await acquirer.acquire(args.symbol, start, end)
    finally:
        await client.aclose()
    print(f"BARS_FETCHED: {result.row_count}")
    print(f"BAR_CHUNKS: {result.chunk_count}")
    print(f"BAR_EMPTY_CHUNKS: {result.empty_chunks}")
    print(f"BAR_DATASET_SHA256: {result.dataset_sha256}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="NIFTY-I")
    parser.add_argument(
        "--tick-store",
        default=str(ROOT / "backend" / "data" / "truedata_ticks.sqlite"),
    )
    parser.add_argument(
        "--bar-store",
        default=str(ROOT / "backend" / "data" / "truedata_bars.sqlite"),
    )
    parser.add_argument("--fetch-bars", action="store_true")
    parser.add_argument("--w-short", type=int, default=5)
    parser.add_argument("--w-long", type=int, default=15)
    parser.add_argument("--params")
    parser.add_argument("--estimate-params", action="store_true")
    parser.add_argument(
        "--write-params",
        default=str(ROOT / "backend" / "data" / "adaptive_edge" / "f101_parameters_trial.json"),
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "backend" / "data" / "adaptive_edge" / "f101_trial_scores.json"),
    )
    args = parser.parse_args()

    if FORMULAS["F-101"].status is not FormulaStatus.LOCKED:
        raise SystemExit("FAILURE: F-101 registry is not LOCKED")

    tick_store = TickStore(args.tick_store)
    start, end = _tick_span(tick_store, args.symbol)
    print(f"SYMBOL: {args.symbol}")
    print(f"TICK_WINDOW_IST: {start.isoformat()} .. {end.isoformat()}")
    print("LABEL: TRIAL_NOT_A197")
    print("NOT_A197_CALIBRATION: true")
    print("EXECUTION_GATE: BLOCKED")

    asyncio.run(_maybe_fetch_bars(args, start, end))

    bar_store = BarStore(args.bar_store)
    bar_rows = bar_store.load(args.symbol, interval="1min")
    if not bar_rows:
        raise SystemExit("FAILURE: no 1-min bars in bar store; rerun with --fetch-bars")

    tick_sequence = ticks_to_canonical_sequence(args.symbol, tick_store.load(args.symbol))
    bar_sequence = bars_to_canonical_sequence(args.symbol, bar_rows)
    print(f"BAR_EVENTS: {len(bar_sequence.events)}")
    print(f"TICK_EVENTS: {len(tick_sequence.events)}")
    print(f"BAR_SEQUENCE_HASH: {bar_sequence.sequence_hash}")
    print(f"TICK_SEQUENCE_HASH: {tick_sequence.sequence_hash}")

    if args.params:
        params = load_f101_parameters(args.params)
    else:
        params = trial_identity_parameters(w_short=args.w_short, w_long=args.w_long)

    observations = score_trial_bars(
        bar_events=bar_sequence.events,
        tick_events=tick_sequence.events,
        params=params,
    )
    if args.estimate_params:
        values = collect_valid_feature_values(observations)
        params = estimate_trial_parameters(
            values, w_short=params.w_short, w_long=params.w_long
        )
        observations = score_trial_bars(
            bar_events=bar_sequence.events,
            tick_events=tick_sequence.events,
            params=params,
        )

    dump_f101_parameters(params, args.write_params)
    valid = sum(1 for item in observations if item.result.status is FeatureStatus.VALID)
    missing = sum(1 for item in observations if item.result.status is FeatureStatus.MISSING)
    payload = {
        "status": TRIAL_STATUS,
        "not_a197": True,
        "not_production_freeze": True,
        "symbol": args.symbol,
        "parameter_status": params.status,
        "w_short": params.w_short,
        "w_long": params.w_long,
        "window_label": "TRIAL_PLACEHOLDER_WINDOWS",
        "bar_events": len(bar_sequence.events),
        "tick_events": len(tick_sequence.events),
        "bar_sequence_hash": bar_sequence.sequence_hash,
        "tick_sequence_hash": tick_sequence.sequence_hash,
        "observations": len(observations),
        "valid_scores": valid,
        "missing_scores": missing,
        "f101_registry": FORMULAS["F-101"].status.value,
        "rows": [
            {
                "bar_index": item.bar_index,
                "bar_record_id": item.bar_record_id,
                "decision_time": item.decision_time,
                "status": item.result.status.value,
                "score": item.result.score,
                "z": item.result.z,
                "values": dict(item.snapshot.values),
                "feature_statuses": {k: v.value for k, v in item.snapshot.statuses.items()},
            }
            for item in observations
            if item.result.status is FeatureStatus.VALID
        ],
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"PARAMS: {args.write_params}")
    print(f"PARAM_STATUS: {params.status}")
    print(f"VALID_SCORES: {valid}")
    print(f"MISSING_SCORES: {missing}")
    print(f"OUT: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
