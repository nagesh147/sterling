"""Acquire available TrueData tick quotes for LiquidityImbalance.

Read-only REST. Does not unlock F-101 or print secrets.
Uses STERLING_DB_PATH (default backend/sterling_paper.db from repo root).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("STERLING_DB_PATH", str(ROOT / "backend" / "sterling_paper.db"))

from app.engines.adaptive_edge.liquidity_imbalance import liquidity_imbalance_at
from app.services import db
from app.services.providers.truedata import credentials as creds
from app.services.providers.truedata.tick_history import TickHistoryAcquirer, ticks_to_canonical_sequence
from app.services.providers.truedata.tick_store import TickStore

IST = ZoneInfo("Asia/Kolkata")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="NIFTY-I")
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument(
        "--store",
        default=str(ROOT / "backend" / "data" / "truedata_ticks.sqlite"),
    )
    args = parser.parse_args()

    db.init()
    creds.bootstrap()
    acct = creds.get_active("default")
    if not acct or acct.id == "TD-ENV":
        print("FAILURE: No active TrueData credential configured in database.")
        return 1

    print(f"ACCOUNT_ID: {acct.id}")
    print(f"USERNAME_HINT: {acct.username_hint()}")
    print(f"SYMBOL: {args.symbol}")

    end = datetime.now(IST)
    start = end - timedelta(days=args.days)
    client = creds.build_client(acct)
    store = TickStore(args.store)
    acquirer = TickHistoryAcquirer(client, store)
    try:
        result = await acquirer.acquire(args.symbol, start, end)
    finally:
        await client.aclose()

    print(f"ROWS: {result.row_count}")
    print(f"CHUNKS: {result.chunk_count}")
    print(f"DATASET_SHA256: {result.dataset_sha256}")
    print(f"STORE: {args.store}")

    sequence = ticks_to_canonical_sequence(args.symbol, store.load(args.symbol))
    print(f"SEQUENCE_HASH: {sequence.sequence_hash}")
    print(f"SEQUENCE_EVENTS: {len(sequence.events)}")
    if sequence.events:
        last = sequence.events[-1]
        feature = liquidity_imbalance_at(sequence.events, last.available_at)
        print(f"LI_STATUS: {feature.status.value}")
        print(f"LI_VALUE: {feature.value}")
        print(f"LI_AVAILABLE_AT: {feature.available_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
