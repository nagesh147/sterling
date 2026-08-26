"""Runtime plumbing for the Gamma Move strategy.

Config persistence and instrument resolution only. All strategy mathematics lives
in ``app.engines.gamma_move`` and is reachable from here without any broker
object, so replay exercises the same code the live path runs.

Instrument resolution goes through the cached NFO dump and the existing
``chain_rows_for`` mapper rather than building option symbols by string
formatting. A fabricated key is an order that either rejects or hits a contract
nobody chose.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from app.core.logging import get_logger
from app.engines.gamma_move import (CALIBRATION, CALIBRATED_FIELDS, CONTRACT_VERSION,
                                    GammaMoveConfig, InstrumentRef, STRATEGY_ID,
                                    STRATEGY_NAME)

log = get_logger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))
_CONFIG_KEY = "gamma_move_config"

#: The NFO dump is ~32k rows and changes once a day. Refetching it per scan would
#: be the classic hot-path mistake this codebase has already had to fix once.
_DUMP_TTL_S = 900.0
_dump_cache: dict[str, tuple[float, list[dict]]] = {}

INDEX_NAMES = frozenset({"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"})


def ist_today() -> date:
    return datetime.now(_IST).date()


def ist_now_ms() -> int:
    return int(datetime.now(_IST).timestamp() * 1000)


# ------------------------------------------------------------------ config

def get_config() -> GammaMoveConfig:
    """The persisted config, falling back to safe disabled defaults.

    A stored row that no longer validates must never become a trading config: the
    failure would otherwise surface deep inside the engine mid-session. Disabled
    is the safe state, so that is the fallback.
    """
    default = GammaMoveConfig(enabled=False)
    try:
        from app.services import db
        raw = db.get_config(_CONFIG_KEY)
    except Exception:                                              # noqa: BLE001
        return default
    if not raw:
        return default
    try:
        stored = json.loads(raw) if isinstance(raw, str) else raw
        known = GammaMoveConfig.field_names()
        merged = {**default.as_dict(), **{k: v for k, v in dict(stored).items() if k in known}}
        for key in ("scan_stocks", "scan_indices"):
            if isinstance(merged.get(key), list):
                merged[key] = tuple(merged[key])
        return GammaMoveConfig(**merged).validate()
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        log.error("Stored %s config is invalid (%s); falling back to disabled defaults",
                  STRATEGY_ID, exc)
        return default


def set_config(values: dict[str, Any]) -> GammaMoveConfig:
    """Persist a config change. Validation is the engine's, not a second copy."""
    current = get_config().as_dict()
    unknown = sorted(set(values) - set(current))
    if unknown:
        raise ValueError(f"Unknown {STRATEGY_ID} config fields: {', '.join(unknown)}")
    current.update(values)
    for key in ("scan_stocks", "scan_indices"):
        if isinstance(current.get(key), list):
            current[key] = tuple(current[key])
    cfg = GammaMoveConfig(**current).validate()
    from app.services import db
    db.set_config(_CONFIG_KEY, json.dumps(cfg.as_dict(), separators=(",", ":")))
    return cfg


# -------------------------------------------------- instrument resolution

async def nfo_dump(uid: str) -> list[dict]:
    from app.services.exchanges.kite import accounts
    cached = _dump_cache.get(uid)
    now = datetime.now(timezone.utc).timestamp()
    if cached and now - cached[0] < _DUMP_TTL_S:
        return cached[1]
    acct = accounts.get_active(uid)
    if not acct:
        raise RuntimeError("No active Kite account")
    client = await accounts.acquire_client(acct)
    rows = await client.search_instruments("", "NFO", limit=1_000_000)
    _dump_cache[uid] = (now, rows)
    return rows


def to_instrument_ref(row: dict) -> InstrumentRef:
    """Map a raw Kite NFO dump row onto the engine's instrument model."""
    return InstrumentRef(
        instrument_id=str(row.get("instrument_token") or ""),
        tradingsymbol=str(row.get("tradingsymbol") or ""),
        option_type="CE" if str(row.get("instrument_type")) == "CE" else "PE",
        strike=float(row.get("strike") or 0.0),
        expiry=str(row.get("expiry") or "")[:10],
        lot_size=int(row.get("lot_size") or 1) or 1,
        tick_size=float(row.get("tick_size") or 0.05) or 0.05,
        exchange="NFO",
    )


def stock_underlyings(rows: list[dict], cfg: GammaMoveConfig) -> list[str]:
    """Every underlying this config is willing to scan.

    Bounded by the same curated high-liquidity registry every other engine here
    uses, and for the same reason its own docstring gives: arbitrary or thin F&O
    names must not be scannable, through an explicit list or otherwise. This
    replaces an invented `max_universe = 150`, which was both an arbitrary
    number and a way past that boundary.
    """
    from app.services.kite_engine.stock_registry import HIGH_LIQUIDITY_STOCK_NAMES
    eligible = set(HIGH_LIQUIDITY_STOCK_NAMES)

    listed = {str(r.get("name") or "").upper()
              for r in rows if r.get("segment") == "NFO-OPT"}

    names: set[str] = set()
    if cfg.stock_contracts:
        wanted = eligible if cfg.scan_all_stocks else {n.upper() for n in cfg.scan_stocks}
        # Intersecting with the registry a second time is deliberate: validate()
        # already refuses an off-registry name, but a config persisted before a
        # registry change can still hold one, and a stale name must drop out
        # rather than reach the scanner.
        names |= (wanted & eligible & listed)
    names |= ({n.upper() for n in cfg.scan_indices} & listed)
    return sorted(names)


# ------------------------------------------------------------------ status

def descriptor() -> dict:
    """Static identity, mirroring the contract. No live state."""
    return {
        "id": STRATEGY_ID,
        "name": STRATEGY_NAME,
        "contract_version": CONTRACT_VERSION,
        "tagline": "Buys the option that writers are covering at a level.",
        "how_it_works": (
            "Finds F&O stocks trading at a support or resistance level, picks the strike "
            "carrying the most open interest there, and buys it when open interest falls, "
            "volume spikes and the premium rises together on the same 15-minute bar — the "
            "signature of option writers covering. Holds one to two sessions."
        ),
        "provenance": "Transcribed from a public podcast walkthrough; see docs/strategy/gamma-move/",
        # There is no `live_ready` flag and no paper-only lock.
        #
        # Paper vs live is `account.is_paper`, and blocking live from inside a
        # strategy config was a second switch for a thing that already has one.
        # What this engine owes the operator instead is that the case against
        # trading it is impossible to miss -- which is what `headline_finding`
        # and the snapshot warnings are for. Whether to trade an unproven edge
        # is their call, and it should be an informed one, not one we pretend to
        # make for them by flipping a flag they can flip back.
        "validated": False,
        # Published rather than hidden: the entry triple on its own did not beat
        # the unconditional population, and an operator reading this engine's
        # settings should see that before they change a threshold.
        "calibration": CALIBRATION,
        "calibrated_fields": sorted(CALIBRATED_FIELDS),
        "headline_finding": (
            "The entry triple alone did not separate from baseline (24.7% [20.9,28.9] vs "
            "21.7% [21.5,21.9] reaching +30% within two sessions). The measured edge is "
            "the level filter: 46.2% [31.6,61.4] when spot sits within 1% of a level."
        ),
    }


async def snapshot(uid: str) -> dict:
    """Operator view: config, what the scan found, and why nothing is armed."""
    cfg = get_config()
    from app.services.gamma_move_runner import session_status, scan_state
    from app.services.gamma_move_sim import state as _sim_state

    out: dict[str, Any] = {
        "strategy": {**descriptor(), "enabled": cfg.enabled},
        "config": cfg.as_dict(),
        "scan": scan_state(uid),
        "session": session_status(uid),
        "simulation": _sim_state(uid),
        "candidates": [],
        "positions": [],
        "record": {"trades": 0, "verdict": "no realised trades yet"},
        "orphan_positions": [],
        "blockers": [],
    }
    session = session_status(uid) or {}
    out["candidates"] = session.get("candidates") or []
    out["positions"] = session.get("positions") or []
    out["record"] = session.get("record") or out["record"]

    from app.services.gamma_move_runner import auto_execute, is_paper
    paper, auto = is_paper(uid), auto_execute(uid)
    # Read, never stored: these are the account's and the engine's settings, and
    # a copy here would be a claim about them rather than the thing itself.
    out["mode"] = {
        "is_paper": paper,
        "auto_execute": auto,
        "note": ("Paper/live is the account's Trading Mode setting and manual/auto is the "
                 "engine's — both shared with every Kite strategy, neither stored here."),
    }
    if not cfg.enabled:
        out["blockers"].append("strategy disabled")
    # Warnings are configured risks, not failures, so they read as sentences.
    out["warnings"] = list(cfg.warnings())
    out["warnings"].append(
        "not validated: in calibration the entry trigger alone showed no edge — the "
        "measured edge is the level filter. See docs/strategy/gamma-move/VALIDATION_REPORT.md")
    if not paper:
        out["warnings"].append(
            "LIVE: this account places real orders. Every entry carries a stop and, "
            f"under stop_mode={cfg.stop_mode}, a broker-side GTT.")

    try:
        rows = await nfo_dump(uid)
        names = stock_underlyings(rows, cfg)
        out["universe"] = {"underlyings": len(names), "sample": names[:10]}
    except Exception as exc:                                       # noqa: BLE001
        out["blockers"].append(f"instrument dump unavailable: {exc}")
        out["universe"] = {"underlyings": 0, "sample": []}

    try:
        from app.services.gamma_move_runner import orphan_positions
        orphans = await orphan_positions(uid, cfg)
    except Exception as exc:                                       # noqa: BLE001
        orphans = []
        log.debug("Gamma Move orphan check failed for %s: %s", uid, exc)
    out["orphan_positions"] = orphans
    for o in orphans:
        out["blockers"].append(
            f"open position {o['symbol']} ({o['quantity']} @ {o['entry_price']}) "
            f"is not accounted for — adopt or close it")
    return out
