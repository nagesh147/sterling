"""Shared scan orchestration for the Kite engine.

One ``scan_user`` entrypoint used by BOTH the manual ``/scan`` endpoint and the
background auto-scan loop: builds the universe from the live instrument dumps,
runs the scanner, logs activity, updates status, and (when auto-execute is on)
places gated option BUYs through the Kite order path. No other-engine imports.
"""
from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.schemas import EngineConfigModel
from app.services import live_safety, paper_store
from app.services.kite_engine import state
from app.services.kite_engine.scanner import option_order_args, scanner
from app.services.kite_engine.universe import build_universe

log = get_logger(__name__)

SCAN_INTERVAL_S = 300  # background auto-scan cadence (5 min; 1H bars move slowly)

_auto_running = False


def is_auto_running() -> bool:
    return _auto_running


def _ts_cfg(c: EngineConfigModel) -> TripleSupertrendConfig:
    return TripleSupertrendConfig(trail_target=c.trail_target, early_lock=c.early_lock)


def _make_place_cb(client, uid: str):
    """Gated auto-exec: 1-lot ATM/ITM (primary leg) option BUY under the same
    live-safety + idempotency checks as manual Kite orders. Logs every outcome."""
    async def _cb(row, item) -> None:
        args = option_order_args(row)  # primary (first) leg
        if not args or not args["option_symbol"] or args["size"] <= 0:
            return
        # One position per underlying: skip if we already hold an auto-exec'd
        # position on this name (a later re-alignment is a new signal otherwise).
        if state.is_auto_open(uid, row.underlying):
            return
        idem = live_safety.make_idempotency_key(
            uid, args["option_symbol"], "BUY", args["size"], row.timestamp_ms)
        positions = paper_store.list_positions() if hasattr(paper_store, "list_positions") else []
        decision = live_safety.assert_safe_to_trade(positions=positions, idempotency_key=idem)
        if not decision.allowed and decision.code != "duplicate_order":
            state.log(uid, "order_blocked",
                      f"{row.underlying} {args['option_symbol']} blocked: {decision.reason}")
            return
        if live_safety.check_idempotency(idem):
            return  # this signal already executed
        try:
            result = await client.place_order_option(
                args["option_symbol"], args["side"], args["size"],
                exchange=args["exchange"], stop_loss=args["stop_loss"], tag=idem)
        except Exception as exc:  # noqa: BLE001
            state.log(uid, "order_failed", f"{row.underlying} {args['option_symbol']}: {exc}")
            return
        oid = (result or {}).get("order_id", "")
        if oid:
            live_safety.record_idempotency(idem, oid)
            state.mark_auto_open(uid, row.underlying)  # one-position guard
            state.log(uid, "order_placed",
                      f"BUY {args['size']} {args['option_symbol']} @ market (#{oid})")
    return _cb


async def scan_user(client, uid: str, *, interval_s: float = SCAN_INTERVAL_S) -> int:
    """Run one full scan for ``uid`` with ``client``. Returns the signal count."""
    cfg_model = state.get_config(uid)
    state.set_scanning(uid, True)
    state.log(uid, "scan_start", "Scanning universe (1H triple-SuperTrend)…")
    try:
        nfo = await client.search_instruments("", "NFO", limit=1_000_000)
        bfo = await client.search_instruments("", "BFO", limit=1_000_000)
        nse = await client.search_instruments("", "NSE", limit=1_000_000)
        bse = await client.search_instruments("", "BSE", limit=1_000_000)
        universe = build_universe(nfo_instruments=nfo, bfo_instruments=bfo, equities=nse + bse)
        place_cb = _make_place_cb(client, uid) if cfg_model.auto_execute else None
        await scanner.scan(
            uid=uid, client=client, universe=universe, nfo_rows=nfo, bfo_rows=bfo,
            cfg=_ts_cfg(cfg_model), moneyness=cfg_model.strike_moneyness, place_cb=place_cb)
        count = len(scanner.snapshot(uid).rows)
        mode = "auto-exec ON" if cfg_model.auto_execute else "advisory"
        state.log(uid, "scan_done",
                  f"Scan complete — {count} ready signal(s) / {len(universe)} instruments ({mode})")
        state.mark_scan_done(uid, signal_count=count, next_in_s=interval_s)
        return count
    except Exception as exc:  # noqa: BLE001
        state.set_scanning(uid, False)
        state.log(uid, "error", f"Scan failed: {exc}")
        log.warning("kite-engine scan_user failed for %s: %s", uid, exc)
        raise


async def _scan_all_connected_once() -> None:
    """One pass over every connected Kite account."""
    from app.services.exchanges.kite import accounts as kite_accounts
    try:
        accts = [a for a in kite_accounts._load_from_db() if a.connected]
    except Exception as exc:  # noqa: BLE001
        log.warning("kite-engine auto-scan: account load failed: %s", exc)
        return
    for acct in accts:
        client = kite_accounts.build_client(acct)
        try:
            await scan_user(client, acct.user_id)
        except Exception:  # noqa: BLE001 — already logged in scan_user
            pass
        finally:
            await client.close()


async def auto_scan_loop(interval_s: float = SCAN_INTERVAL_S) -> None:
    """Background task: periodically scan all connected accounts. Started at app
    startup. Survives per-iteration errors so one bad scan doesn't kill the loop."""
    global _auto_running
    _auto_running = True
    log.info("kite-engine auto-scan loop started (every %ss)", interval_s)
    try:
        while True:
            try:
                await _scan_all_connected_once()
            except Exception as exc:  # noqa: BLE001
                log.warning("kite-engine auto-scan iteration error: %s", exc)
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        log.info("kite-engine auto-scan loop stopped")
        raise
    finally:
        _auto_running = False
