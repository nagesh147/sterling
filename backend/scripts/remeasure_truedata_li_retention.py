"""Probe whether /getticks?bidask=1 returns pre-entitlement history.

Read-only. Does not write the entitled tick cache.
Does not unlock F-101. Does not print secrets.
"""
from __future__ import annotations

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

from app.services import db
from app.services.market_data.truedata import TrueDataError, TrueDataNoDataError
from app.services.providers.truedata import credentials as creds

IST = ZoneInfo("Asia/Kolkata")
PROBES = (
    ("old_2026-07-15", "260715T09:15:00", "260715T09:20:00"),
    ("old_2026-08-01", "260801T09:15:00", "260801T09:20:00"),
    ("control_2026-08-13", "260813T09:15:00", "260813T09:20:00"),
)


async def main() -> int:
    db.init()
    creds.bootstrap()
    account = creds.get_active("default")
    if not account or account.id == "TD-ENV":
        print("FAILURE: No active TrueData credential configured in database.")
        return 1

    print(f"ACCOUNT_ID: {account.id}")
    print(f"USERNAME_HINT: {account.username_hint()}")
    client = creds.build_client(account)
    probes: list[dict[str, object]] = []
    try:
        for name, start, end in PROBES:
            try:
                rows = await client.get_ticks("NIFTY-I", start, end, bidask=1)
                error = None
            except TrueDataNoDataError as exc:
                rows = []
                error = str(exc)
            except TrueDataError as exc:
                rows = []
                error = str(exc)
            keys = sorted({key for row in rows for key in row})
            has_qty = any("bidqty" in row and "askqty" in row for row in rows)
            probes.append(
                {
                    "name": name,
                    "from": start,
                    "to": end,
                    "n": len(rows),
                    "has_bidqty_askqty": has_qty,
                    "keys": keys[:16],
                    "error": error,
                }
            )
            print(f"{name}: n={len(rows)} has_qty={has_qty} error={error}")
    finally:
        await client.aclose()

    old_hits = [item for item in probes if item["name"].startswith("old_") and int(item["n"]) > 0]
    payload = {
        "label": "A197_LI_REMEASURE",
        "probed_at": datetime.now(IST).isoformat(),
        "symbol": "NIFTY-I",
        "account_id": account.id,
        "probes": probes,
        "old_date_history_present": bool(old_hits),
        "a197_unblocked": False,
        "note": (
            "Old-date ticks would be new evidence, not an A197 dataset. "
            "A197 still requires ~120 days / ~45k bars + LI."
        ),
    }
    out = ROOT / "backend" / "data" / "adaptive_edge" / "li_retention_remeasure.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"OLD_DATE_HISTORY_PRESENT: {bool(old_hits)}")
    print(f"OUT: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
