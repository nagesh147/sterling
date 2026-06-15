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
from app.services.kite_engine.universe import build_universe, select_scan_universe

log = get_logger(__name__)

SCAN_INTERVAL_S = 300  # background auto-scan cadence (5 min; 1H bars move slowly)

_auto_running = False


def is_auto_running() -> bool:
    return _auto_running


def _ts_cfg(c: EngineConfigModel) -> TripleSupertrendConfig:
    return TripleSupertrendConfig(trail_target=c.trail_target, early_lock=c.early_lock)


def _make_place_cb(client, uid: str):
    """Gated auto-exec: 1-lot at-the-money (nearest-spot leg) option BUY under the
    same live-safety + idempotency checks as manual Kite orders. Logs every outcome."""
    async def _cb(row, item) -> None:
        args = option_order_args(row)  # primary (first) leg
        if not args or not args["option_symbol"] or args["size"] <= 0:
            return
        # One open auto-position per "slot": per underlying for spot signals, per
        # contract for derivatives (so each fired CE/PE strike is independent).
        guard_key = args["option_symbol"] if row.source == "derivatives" else row.underlying
        if state.is_auto_open(uid, guard_key):
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
            state.mark_auto_open(uid, guard_key)  # one-position guard (per slot)
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
        full_universe = build_universe(nfo_instruments=nfo, bfo_instruments=bfo, equities=nse + bse)
        source = cfg_model.scan_source
        # Granular selection applies to BOTH scans.
        selected = select_scan_universe(
            full_universe, indices=cfg_model.scan_indices,
            stocks=cfg_model.scan_stocks, all_stocks=cfg_model.scan_all_stocks)
        spot_universe = selected if source in ("spot", "both") else []
        deriv_universe = selected if source in ("derivatives", "both") else None
        # Auto-exec is universal — it fires on both spot and derivatives signals.
        place_cb = _make_place_cb(client, uid) if cfg_model.auto_execute else None
        await scanner.scan(
            uid=uid, client=client, universe=spot_universe, nfo_rows=nfo, bfo_rows=bfo,
            cfg=_ts_cfg(cfg_model), moneyness=cfg_model.strike_moneyness, place_cb=place_cb,
            deriv_universe=deriv_universe)
        snap = scanner.snapshot(uid)
        count = len(snap.rows)
        d = snap.diag
        mode = "auto-exec ON" if place_cb else "advisory"
        parts = []
        if source in ("spot", "both"):
            # Index breakdown makes the 'no index signals' case visible: if indices
            # have 0 with data, the live index candle fetch is coming back empty.
            ix = f"indices {d.index_fired} fired, {d.index_evaluated}/{d.indices} with data"
            if d.indices and d.index_evaluated == 0:
                ix += " — index candle fetch returned nothing"
            parts.append(ix)
        if source in ("derivatives", "both"):
            # Per-stage so a zero-signal scan is self-explaining:
            #   resolved 0           → chains/strikes didn't resolve (config/expiry)
            #   resolved N, charts 0 → premium fetch returned nothing
            #   charts N, fired 0    → scanning fine; no fresh BUY this bar (base rate)
            dv = (f"deriv {d.deriv_fired} fired / {d.deriv_charts} charts "
                  f"(resolved {d.deriv_resolved}, bars {d.deriv_min_bars}–{d.deriv_max_bars})")
            if d.deriv_no_data:
                dv += f", {d.deriv_no_data} no-data"
            if d.deriv_resolved == 0:
                dv += " — no option contracts resolved from chains"
            parts.append(dv)
        state.log(uid, "scan_done",
                  f"Scan complete — {count} ready signal(s) / {len(selected)} instruments "
                  f"[{source}] ({mode}) · {' · '.join(parts)}")
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
    from app.services.exchanges.kite.errors import KiteTokenError
    try:
        accts = [a for a in kite_accounts._load_from_db() if a.connected]
    except Exception as exc:  # noqa: BLE001
        log.warning("kite-engine auto-scan: account load failed: %s", exc)
        return
    for acct in accts:
        client = kite_accounts.build_client(acct)
        try:
            try:
                await client.get_profile()  # cheap token-validity probe
            except KiteTokenError:
                # Auto-expire: clear the stale token so the UI flips to disconnected.
                kite_accounts.clear_session(acct.user_id, acct.id)
                state.log(acct.user_id, "info",
                          "Kite session expired — auto-disconnected; re-login required.")
                continue
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
