"""Validate that the configured TrueData entitlement can supply the V2.1 research input.

Usage:
    TRUEDATA_USERNAME=... TRUEDATA_PASSWORD=... \
    python scripts/adaptive_edge/validate_truedata_research_source.py \
      NIFTY 2026-01-01 2026-08-01

This script is read-only. It does not place broker orders.
"""
from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter

from app.services.market_data.truedata import TrueDataHistoricalClient, TrueDataError


async def main() -> int:
    if len(sys.argv) != 4:
        print("usage: validate_truedata_research_source.py SYMBOL START END", file=sys.stderr)
        return 2

    username = os.getenv("TRUEDATA_USERNAME")
    password = os.getenv("TRUEDATA_PASSWORD")
    if not username or not password:
        print("BLOCKED: TRUEDATA_USERNAME and TRUEDATA_PASSWORD are required", file=sys.stderr)
        return 3

    symbol, start, end = sys.argv[1:]
    client = TrueDataHistoricalClient(username, password)
    try:
        bars = await client.get_bars(symbol, start, end, interval="1min", response_format="csv")
    except TrueDataError as exc:
        print(f"BLOCKED: TrueData source validation failed: {exc}", file=sys.stderr)
        return 4
    finally:
        await client.aclose()

    if not bars:
        print("BLOCKED: TrueData returned no 1-minute bars", file=sys.stderr)
        return 5

    required = {"timestamp", "open", "high", "low", "close", "volume", "oi"}
    missing = required.difference(bars[0].keys())
    if missing:
        print(f"BLOCKED: missing canonical bar fields: {sorted(missing)}", file=sys.stderr)
        return 6

    timestamps = [row["timestamp"] for row in bars]
    duplicates = len(timestamps) - len(set(timestamps))
    print(f"bars={len(bars)}")
    print(f"first_timestamp={timestamps[0]}")
    print(f"last_timestamp={timestamps[-1]}")
    print(f"duplicate_timestamps={duplicates}")
    print(f"fields={sorted(bars[0].keys())}")

    if duplicates:
        print("BLOCKED: duplicate timestamps require deterministic source reconciliation")
        return 7

    print("SOURCE_VALIDATION=PASS")
    print("NOTE: timestamp availability semantics and historical entitlement must still be recorded in the dataset manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
