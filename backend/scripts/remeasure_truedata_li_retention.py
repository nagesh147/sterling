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

from app.engines.adaptive_edge.corpus_observation import observe_local_corpus
from app.engines.adaptive_edge.research_pipeline import A197_MIN_BARS, A197_MIN_TRADING_DAYS, meets_a197_contract
from app.services import db
from app.services.market_data.truedata import TrueDataError, TrueDataNoDataError
from app.services.providers.truedata import credentials as creds

IST = ZoneInfo("Asia/Kolkata")
# Distinguish provider error vs empty history vs live entitlement.
# Old/boundary dates test pre-entitlement depth. Control dates test that the API still works.
PROBES = (
    ("old_2026-07-15", "260715T09:15:00", "260715T09:20:00"),
    ("old_2026-08-01", "260801T09:15:00", "260801T09:20:00"),
    ("boundary_2026-08-05", "260805T09:15:00", "260805T09:20:00"),
    ("control_2026-08-13", "260813T09:15:00", "260813T09:20:00"),
    ("control_2026-08-18", "260818T09:15:00", "260818T09:20:00"),
    ("control_2026-08-19", "260819T09:15:00", "260819T09:20:00"),
)

TICK_STORE = ROOT / "backend" / "data" / "truedata_ticks.sqlite"
BAR_STORE = ROOT / "backend" / "data" / "truedata_bars.sqlite"


def _local_cache_inventory() -> dict[str, object]:
    """Read-only observation of already-acquired caches. Not new ticks."""
    observed = observe_local_corpus(bar_store=BAR_STORE, tick_store=TICK_STORE)
    return {
        "tick_store": observed.tick_store,
        "tick_rows": observed.tick_rows,
        "tick_days": observed.tick_days,
        "tick_first": observed.tick_first,
        "tick_last": observed.tick_last,
        "tick_li_valid": observed.tick_li_valid,
        "tick_li_days": observed.tick_li_days,
        "bar_store": observed.bar_store,
        "bar_rows": observed.bar_rows,
        "bar_days": observed.bar_days,
        "bar_first": observed.bar_first,
        "bar_last": observed.bar_last,
        "bars_on_li_days": observed.bars_on_li_days,
        "meets_a197": observed.meets_a197,
    }


def _verdict(*, old_hits: bool, control_hits: bool, cache: dict[str, object]) -> dict[str, object]:
    """R1 sufficient / R2 insufficient / R3 feature-definition change.

    R3 is not selected here: A206 already chose LI path A (obtain history),
    not C-LI. Short history is an entitlement gap, not a feature rewrite.
    Bars-only coverage cannot become R1.
    """
    bar_days = int(cache.get("bar_days") or 0)
    bar_rows = int(cache.get("bar_rows") or 0)
    li_valid = int(cache.get("bars_on_li_days") or 0)
    if meets_a197_contract(trading_days=bar_days, bar_count=bar_rows, li_valid=li_valid):
        return {
            "code": "R1",
            "reason": "local cache meets A197 bar coverage and LI-on-bar coverage",
        }
    if not control_hits and not old_hits:
        return {
            "code": "R2",
            "reason": "no live or historical LI ticks in probe windows; entitlement or provider path is insufficient",
        }
    return {
        "code": "R2",
        "reason": (
            "live entitlement can return LI ticks, but A197-scale LI history is not present "
            f"(old_date_history={old_hits}, cache_days={bar_days}, cache_bars={bar_rows}, "
            f"li_bars<={li_valid}; need >={A197_MIN_TRADING_DAYS} days and >={A197_MIN_BARS} bars + LI)"
        ),
    }


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
        await client.authenticate()
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
            if error and "No data exists" not in error:
                classification = "provider_error"
            elif len(rows) == 0:
                classification = "empty_historical_response"
            elif has_qty:
                classification = "historical_availability_with_li"
            else:
                classification = "historical_availability_without_li"
            probes.append(
                {
                    "name": name,
                    "from": start,
                    "to": end,
                    "n": len(rows),
                    "has_bidqty_askqty": has_qty,
                    "keys": keys[:16],
                    "error": error,
                    "classification": classification,
                }
            )
            print(
                f"{name}: n={len(rows)} has_qty={has_qty} "
                f"class={classification} error={error}"
            )
    finally:
        await client.aclose()

    # Same client/token can return 401 for dates outside entitlement while
    # later windows succeed. That is not a dead provider; it is no history.
    if any(int(item["n"]) > 0 for item in probes):
        for item in probes:
            if item["classification"] == "provider_error" and item["error"] and "401" in str(item["error"]):
                item["classification"] = "empty_historical_response"
    old_hits = [
        item
        for item in probes
        if item["name"].startswith(("old_", "boundary_")) and int(item["n"]) > 0
    ]
    control_hits = [
        item for item in probes if item["name"].startswith("control_") and int(item["n"]) > 0
    ]
    provider_errors = [item for item in probes if item["classification"] == "provider_error"]
    cache = _local_cache_inventory()
    verdict = _verdict(old_hits=bool(old_hits), control_hits=bool(control_hits), cache=cache)
    payload = {
        "label": "A197_LI_REMEASURE",
        "probed_at": datetime.now(IST).isoformat(),
        "symbol": "NIFTY-I",
        "account_id": account.id,
        "probes": probes,
        "old_date_history_present": bool(old_hits),
        "control_history_present": bool(control_hits),
        "provider_errors": [item["name"] for item in provider_errors],
        "local_cache": cache,
        "verdict": verdict,
        "a197_unblocked": verdict["code"] == "R1",
        "note": (
            "Old-date ticks would be new evidence, not an A197 dataset. "
            "A197 still requires ~120 days / ~45k bars + LI. "
            "Ticks are never synthesized."
        ),
    }
    out = ROOT / "backend" / "data" / "adaptive_edge" / "li_retention_remeasure.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"OLD_DATE_HISTORY_PRESENT: {bool(old_hits)}")
    print(f"CONTROL_HISTORY_PRESENT: {bool(control_hits)}")
    print(f"VERDICT: {verdict['code']} {verdict['reason']}")
    print(f"A197_UNBLOCKED: {payload['a197_unblocked']}")
    print(f"CACHE_TICK_ROWS: {cache['tick_rows']} days={cache['tick_days']} li_valid={cache['tick_li_valid']} li_days={cache['tick_li_days']}")
    print(f"CACHE_BAR_ROWS: {cache['bar_rows']} days={cache['bar_days']} bars_on_li_days={cache['bars_on_li_days']}")
    print(f"OUT: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
