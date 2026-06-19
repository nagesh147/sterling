"""Shared scan orchestration for the Kite engine.

One ``scan_user`` entrypoint used by BOTH the manual ``/scan`` endpoint and the
background auto-scan loop: builds the universe from the live instrument dumps,
runs the scanner, logs activity, updates status, and (when auto-execute is on)
places gated option BUYs through the Kite order path. No other-engine imports.
"""
from __future__ import annotations

import asyncio
import re

from app.core.logging import get_logger
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.schemas import EngineConfigModel
from app.services import live_safety
from app.services.kite_engine import positions, protective_stop, sizing, state
from app.services.kite_engine.market_hours import is_market_open
from app.services.kite_engine.scanner import option_order_args, scanner
from app.services.kite_engine.universe import build_universe, select_scan_universe

log = get_logger(__name__)

SCAN_INTERVAL_S = 300  # background auto-scan cadence (5 min; 1H bars move slowly)

_auto_running = False
_first_scan_done = False


def is_auto_running() -> bool:
    return _auto_running


def has_scanned() -> bool:
    return _first_scan_done


def _ts_cfg(c: EngineConfigModel) -> TripleSupertrendConfig:
    return TripleSupertrendConfig(trail_target=c.trail_target, early_lock=c.early_lock)


async def place_manual_order(uid: str, option_symbol: str, side: str,
                             quantity: int, exchange: str = "NFO") -> dict:
    """Shared manual BUY/SELL path used by BOTH the detail-panel REST endpoint and
    the Telegram bot, so they apply the identical live-safety gate + idempotency and
    place through the same warm client. Returns a status dict (never raises):
      {status: ok|duplicate|blocked|error, order_id?, message?, reason?, code?}
    Callers map this to HTTP / chat replies."""
    from app.services.exchanges.kite import accounts as kite_accounts
    from app.services.exchanges.kite.errors import KiteError

    norm = "buy" if side.upper() == "BUY" else "sell"
    idem = live_safety.make_idempotency_key(uid, option_symbol, side.upper(), quantity)
    # Kite is INR; the USD daily-loss breaker is crypto-only (kill-switch + idempotency still apply).
    decision = live_safety.assert_safe_to_trade(
        positions=[], idempotency_key=idem, check_daily_loss=False)
    if not decision.allowed and decision.code != "duplicate_order":
        state.log(uid, "order_blocked", f"{side} {option_symbol} blocked: {decision.reason}")
        return {"status": "blocked", "reason": decision.reason, "code": decision.code}
    prior = live_safety.check_idempotency(idem)
    if prior:
        return {"status": "duplicate", "order_id": prior, "message": "Already submitted"}

    acct = kite_accounts.get_active(uid)
    if not acct:
        return {"status": "error", "message": "No active Kite account."}
    client = await kite_accounts.acquire_client(acct)
    try:
        result = await client.place_order_option(
            option_symbol, norm, quantity, exchange=exchange, tag=idem)
    except KiteError as exc:
        state.log(uid, "order_failed", f"{side} {option_symbol}: {exc}")
        return {"status": "error", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        state.log(uid, "order_failed", f"{side} {option_symbol}: {exc}")
        return {"status": "error", "message": str(exc)}

    oid = (result or {}).get("order_id", "")
    if oid:
        live_safety.record_idempotency(idem, oid)
    state.log(uid, "order_placed", f"{side} {quantity} {option_symbol} (#{oid})")
    return {"status": "ok", "order_id": oid, "message": "Order submitted"}


async def available_fo_capital(client) -> float:
    """Available F&O-segment capital (INR) for risk sizing. Falls back to 0 on
    error — sizing then floors to 1 lot."""
    try:
        margins = await client.get_margins("equity")
        # Kite nests available cash under available.live_balance / available.cash.
        avail = (margins or {}).get("available", {}) if isinstance(margins, dict) else {}
        return float(avail.get("live_balance") or avail.get("cash") or 0.0)
    except Exception:  # noqa: BLE001
        return 0.0


def _make_place_cb(client, uid: str):
    """Gated auto-exec: risk-sized option BUY (nearest-spot leg) under the same
    live-safety + idempotency checks as manual Kite orders, with a broker-side
    protective stop and tick-monitor registration. Logs every outcome."""
    async def _cb(row, item) -> None:
        args = option_order_args(row)  # primary (first) leg
        if not args or not args["option_symbol"] or args["size"] <= 0:
            return
        cfg = state.get_config(uid)
        # One open auto-position per "slot": per underlying for spot signals, per
        # contract for derivatives (so each fired CE/PE strike is independent).
        guard_key = args["option_symbol"] if row.source == "derivatives" else row.underlying
        if state.is_auto_open(uid, guard_key):
            return

        # ── risk sizing (workstream F) ────────────────────────────────────────
        qty = int(args["size"])
        lots = 1
        if cfg.risk_sizing and args.get("entry_premium") and args.get("stop_premium") is not None:
            capital = await available_fo_capital(client)
            sized = sizing.size_position(
                entry_premium=float(args["entry_premium"]),
                stop_premium=float(args["stop_premium"]),
                lot_size=int(args["lot_size"] or 0),
                available_capital=capital,
                risk_pct=cfg.risk_pct,
                max_lots=cfg.max_lots,
            )
            if sized.qty > 0:
                qty, lots = sized.qty, sized.lots
                state.log(uid, "info", f"{args['option_symbol']} sizing → {sized.reason}")

        idem = live_safety.make_idempotency_key(
            uid, args["option_symbol"], "BUY", qty, row.timestamp_ms)
        # Kite is INR; the USD daily-loss breaker is crypto-only (kill-switch + idempotency still apply).
        decision = live_safety.assert_safe_to_trade(
            positions=[], idempotency_key=idem, check_daily_loss=False)
        if not decision.allowed and decision.code != "duplicate_order":
            state.log(uid, "order_blocked",
                      f"{row.underlying} {args['option_symbol']} blocked: {decision.reason}")
            return
        if live_safety.check_idempotency(idem):
            return  # this signal already executed
        try:
            result = await client.place_order_option(
                args["option_symbol"], args["side"], qty,
                exchange=args["exchange"], stop_loss=args["stop_loss"], tag=idem)
        except Exception as exc:  # noqa: BLE001
            state.log(uid, "order_failed", f"{row.underlying} {args['option_symbol']}: {exc}")
            return
        oid = (result or {}).get("order_id", "")
        if not oid:
            return
        live_safety.record_idempotency(idem, oid)
        state.mark_auto_open(uid, guard_key)  # one-position guard (per slot)

        # ── register position for fill-tracking + tick monitor (E / C / D) ─────
        entry_px = float(args.get("entry_premium") or 0.0)
        stop_px = float(args.get("stop_premium") or 0.0)
        p = positions.register(positions.OpenPosition(
            uid=uid, symbol=args["option_symbol"], exchange=args["exchange"],
            token=int(args.get("token") or row.token or 0),
            qty=qty, lot_size=int(args["lot_size"] or 0),
            entry_premium=entry_px, stop_premium=stop_px,
            order_id=oid, status=positions.PENDING,
            stop_mode=cfg.stop_mode, guard_key=guard_key))

        # ── broker-side protective stop (workstream C) ────────────────────────
        if cfg.stop_mode in ("broker", "both") and stop_px > 0:
            gtt_id = await protective_stop.place_stop(
                client, tradingsymbol=args["option_symbol"], exchange=args["exchange"],
                qty=qty, trigger_premium=stop_px, last_price=entry_px)
            if gtt_id:
                positions.update_stop(uid, p.symbol, stop_px, gtt_id=gtt_id)
                state.log(uid, "info",
                          f"Protective GTT #{gtt_id} placed for {p.symbol} @ ₹{stop_px:.2f}")
            elif cfg.stop_mode == "broker":
                state.log(uid, "info",
                          f"⚠ Protective GTT failed for {p.symbol}; no broker stop "
                          f"(enable monitor mode for a server-side backstop)")

        monitor_note = "+monitor" if cfg.stop_mode in ("monitor", "both") else ""
        state.log(uid, "order_placed",
                  f"BUY {qty} ({lots} lot) {args['option_symbol']} @ market (#{oid}) "
                  f"[{cfg.stop_mode} stop{monitor_note}]")
    return _cb


async def scan_user(client, uid: str, *, interval_s: float = SCAN_INTERVAL_S) -> int:
    """Run one full scan for ``uid`` with ``client``. Returns the signal count."""
    cfg_model = state.get_config(uid)
    if state.status(uid).scanning:
        state.log(uid, "info", "Scan skipped — another scan is already in progress for this account.")
        return 0
    if state.clear_cooldown(uid):
        state.log(uid, "info", "Scan skipped — cancelled recently (60s cooldown).")
        return 0
    state.set_scanning(uid, True)
    state.log(uid, "scan_start", f"Initiating 1H triple-SuperTrend scan…")
    try:
        # Fetch the four exchange dumps concurrently (warm cache → instant; cold →
        # parallel downloads instead of ~1s of sequential round-trips).
        nfo, bfo, nse, bse = await asyncio.gather(
            client.search_instruments("", "NFO", limit=1_000_000),
            client.search_instruments("", "BFO", limit=1_000_000),
            client.search_instruments("", "NSE", limit=1_000_000),
            client.search_instruments("", "BSE", limit=1_000_000),
        )
        full_universe = build_universe(nfo_instruments=nfo, bfo_instruments=bfo, equities=nse + bse)
        source = cfg_model.scan_source
        # Granular selection applies to BOTH scans.
        selected = select_scan_universe(
            full_universe, indices=cfg_model.scan_indices,
            stocks=cfg_model.scan_stocks, all_stocks=cfg_model.scan_all_stocks)
        spot_universe = selected if source in ("spot", "both") else []
        deriv_universe = selected if source in ("derivatives", "both") else None
        state.log(uid, "info", f"Scan plan: Scanning {len(selected)} instruments using '{source}' source.")
        
        # Auto-exec is universal — it fires on both spot and derivatives signals.
        place_cb = _make_place_cb(client, uid) if cfg_model.auto_execute else None
        await scanner.scan(
            uid=uid, client=client, universe=spot_universe, nfo_rows=nfo, bfo_rows=bfo,
            cfg=_ts_cfg(cfg_model), moneyness=cfg_model.strike_moneyness,
            expiry_types=cfg_model.scan_expiries,
            expiry_types_indices=cfg_model.scan_expiries_indices,
            expiry_types_stocks=cfg_model.scan_expiries_stocks,
            place_cb=place_cb,
            deriv_universe=deriv_universe, log_cb=lambda msg: state.log(uid, "info", msg))
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
            if d.deriv_no_spot:
                dv += f", {d.deriv_no_spot} no-spot (underlying price unavailable)"
            if d.deriv_resolved == 0 and d.deriv_no_spot == 0:
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


def _broker_open_slots(positions_net: list) -> set:
    """Build the set of auto-open guard slots from raw broker positions.

    The guard key is the option tradingsymbol for derivatives slots and the
    underlying name for spot slots, so we emit BOTH for every position with a
    non-zero net quantity: the full tradingsymbol and its leading alpha prefix
    (e.g. ``NIFTY24JUN24000CE`` → ``NIFTY``). Reconcile intersects the persisted
    guard with this set, so an unmatched key is *cleared* (re-entry allowed) —
    we err toward emitting more candidate keys to avoid clearing a live slot.
    """
    slots: set = set()
    for p in positions_net or []:
        try:
            if int(p.get("quantity", 0) or 0) == 0:
                continue
            ts = str(p.get("tradingsymbol", "")).strip()
            if not ts:
                continue
            slots.add(ts)
            prefix = re.match(r"^[A-Z&-]+", ts.upper())
            if prefix:
                slots.add(prefix.group(0))
        except Exception:
            continue
    return slots


async def reconcile_user_auto_open(client, uid: str) -> None:
    """Sync ``uid``'s auto-open guard to the broker's real open positions.

    Called on startup before the scan loop: a server restart loses nothing
    (the guard is DB-persisted) but the persisted guard may be stale (positions
    closed / expired while we were down). Fetching ``GET /positions`` and
    intersecting prevents both a forever-blocked slot and a double-entry.
    """
    try:
        raw = await client.get_positions_raw()
        broker_slots = _broker_open_slots((raw or {}).get("net", []))
        before = state.auto_open_underlyings(uid)
        after = state.reconcile_auto_open(uid, broker_slots)
        dropped = before - after
        if dropped:
            state.log(uid, "info",
                      f"Auto-open guard reconciled against broker: cleared {len(dropped)} "
                      f"stale slot(s) ({', '.join(sorted(dropped))}); {len(after)} still open.")
    except Exception as exc:  # noqa: BLE001
        log.warning("kite-engine auto-open reconcile failed for %s: %s", uid, exc)


async def reconcile_all_auto_open() -> None:
    """Reconcile every connected account's auto-open guard on startup."""
    from app.services.exchanges.kite import accounts as kite_accounts
    from app.services.exchanges.kite.errors import KiteTokenError
    try:
        accts = [a for a in kite_accounts._load_from_db() if a.connected]
    except Exception as exc:  # noqa: BLE001
        log.warning("kite-engine auto-open reconcile: account load failed: %s", exc)
        return
    for acct in accts:
        try:
            client = await kite_accounts.acquire_client(acct)
            await reconcile_user_auto_open(client, acct.user_id)
        except KiteTokenError:
            continue
        except Exception:  # noqa: BLE001
            continue


async def _scan_all_connected_once() -> None:
    """One pass over every connected Kite account."""
    global _first_scan_done
    from app.services.exchanges.kite import accounts as kite_accounts
    from app.services.exchanges.kite.errors import KiteTokenError
    try:
        accts = [a for a in kite_accounts._load_from_db() if a.connected]
    except Exception as exc:  # noqa: BLE001
        log.warning("kite-engine auto-scan: account load failed: %s", exc)
        return
    scanned = False
    for acct in accts:
        # Warm cached client — keeps the instrument dump (1h TTL) hot across scan
        # cycles instead of re-downloading all four exchange dumps every interval.
        client = await kite_accounts.acquire_client(acct)
        try:
            try:
                await client.get_profile()
            except KiteTokenError:
                kite_accounts.clear_session(acct.user_id, acct.id)
                await kite_accounts.release_client(acct.id)
                state.log(acct.user_id, "info",
                          "Kite session expired — auto-disconnected; re-login required.")
                continue
            await scan_user(client, acct.user_id)
            scanned = True
        except Exception:
            pass
    if scanned:
        _first_scan_done = True


async def auto_scan_loop(interval_s: float = SCAN_INTERVAL_S) -> None:
    """Background task: scan all connected accounts every ``interval_s`` seconds.
    Runs one initial scan regardless of market hours (to seed the DB cache), then
    gates subsequent iterations on market-open only."""
    global _auto_running
    _auto_running = True
    log.info("kite-engine auto-scan loop started (every %ss)", interval_s)
    try:
        while True:
            try:
                if _first_scan_done and not is_market_open():
                    await asyncio.sleep(30)  # check market hours every 30s when closed
                    continue
                await _scan_all_connected_once()
            except Exception as exc:  # noqa: BLE001
                log.warning("kite-engine auto-scan iteration error: %s", exc)
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        log.info("kite-engine auto-scan loop stopped")
        raise
    finally:
        _auto_running = False
