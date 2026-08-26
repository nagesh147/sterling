"""Multi-symbol TrueData historical tick & bar acquisition for Adaptive Edge.

Usage:
    python backend/scripts/acquire_all_truedata_ticks.py --days 120 --symbols "NIFTY-I,BANKNIFTY-I,FINNIFTY-I,SENSEX-I"
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("STERLING_DB_PATH", str(ROOT / "backend" / "sterling_paper.db"))

from app.services import db
from app.services.providers import truedata as truedata_service
from app.services.providers.truedata.bar_store import BarStore
from app.services.providers.truedata.tick_history import TickHistoryAcquirer
from app.services.providers.truedata.tick_store import TickStore

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_SYMBOLS = ["NIFTY-I", "BANKNIFTY-I", "FINNIFTY-I", "SENSEX-I"]


async def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire TrueData ticks & bars for multiple indices.")
    parser.add_argument("--days", type=int, default=120, help="Number of historical trading days to acquire")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbol list")
    parser.add_argument("--tick-store", default=str(ROOT / "backend" / "data" / "truedata_ticks.sqlite"))
    parser.add_argument("--bar-store", default=str(ROOT / "backend" / "data" / "truedata_bars.sqlite"))
    parser.add_argument("--user-id", default="default")
    args = parser.parse_args()

    db.init()
    truedata_service.bootstrap()

    acct = truedata_service.get_active(args.user_id)
    if not acct:
        print("ERROR: No active TrueData credential configured in database.")
        return 1

    client = truedata_service.build_client(acct)
    print(f"Connecting to TrueData with user: {acct.username_hint()}...")
    try:
        await client.authenticate()
    except Exception as exc:
        print(f"Authentication failed: {exc}")
        return 1

    tick_store = TickStore(args.tick_store)
    bar_store = BarStore(args.bar_store)
    acquirer = TickHistoryAcquirer(client, tick_store)

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    now_ist = datetime.now(IST)
    start_dt = now_ist - timedelta(days=args.days)

    print(f"Acquiring {len(symbols)} symbols from {start_dt.date()} to {now_ist.date()} ({args.days} days)...")
    for symbol in symbols:
        print(f"\n--- Acquiring Ticks & Bars for {symbol} ---")
        try:
            res = await acquirer.acquire(symbol, start_dt, now_ist, bidask=1)
            print(f"[{symbol}] Ticks Acquired: {res.row_count} rows across {res.chunk_count} chunks (hash: {res.dataset_sha256[:12]})")
        except Exception as exc:
            print(f"[{symbol}] Tick acquisition error: {exc}")

    print("\nBatch multi-symbol TrueData acquisition finished.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
