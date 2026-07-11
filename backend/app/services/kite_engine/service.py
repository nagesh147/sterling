"""Shared scan orchestration for the Kite engine.

One ``scan_user`` entrypoint used by BOTH the manual ``/scan`` endpoint and the
background auto-scan loop: builds the universe from the live instrument dumps,
runs the scanner, logs activity, updates status, and (when auto-execute is on)
places gated option BUYs through the Kite order path. No other-engine imports.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.logging import get_logger
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.schemas import EngineConfigModel
from app.services import live_safety
from app.services.kite_engine import positions, protective_stop, sizing, state
from app.services.kite_engine import futures as futures_mod
from app.services.kite_engine.greeks import black_scholes_greeks
from app.services.kite_engine.market_hours import is_market_open
from app.services.kite_engine.scanner import option_order_args, scanner
from app.services.kite_engine.strikes import chain_rows_for, pick_by_delta, pick_strikes
from app.services.kite_engine.universe import build_universe, select_scan_universe

_IST = timezone(timedelta(hours=5, minutes=30))

log = get_logger(__name__)

SCAN_INTERVAL_S = 300  # background auto-scan cadence (5 min; 1H bars move slowly)

_auto_running = False
_first_scan_done = False


def is_auto_running() -> bool:
    return _auto_running


def has_scanned() -> bool:
    return _first_scan_done


def _ts_cfg(c: EngineConfigModel) -> SterlingKiteEngineConfig:
    return SterlingKiteEngineConfig(
        trail_target=c.trail_target,
        exit_mode=c.exit_mode,
        hybrid_st_weight=getattr(c, 'hybrid_st_weight', 0.5)
    )


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


@dataclass
class _ResolvedTrade:
    """The instrument the auto-exec should actually trade for the chosen vehicle."""
    symbol: str
    exchange: str
    token: int
    lot_size: int
    entry_px: float            # premium (options) or index price (futures)
    stop_px: float             # premium stop (options) or index-point stop (futures)


async def _resolve_future(client, item, expiry_pref: str) -> Optional[futures_mod.FuturesPick]:
    """Resolve the near/next-month index future for an underlying from the warm
    instrument dump (no extra network round-trip on a warm cache)."""
    exch = item.option_exchange  # NFO / BFO
    try:
        dump = await client.search_instruments("", exch, limit=1_000_000)
    except Exception:  # noqa: BLE001
        return None
    return futures_mod.pick_futures_contract(
        dump, name=item.tradingsymbol, exchange=exch,
        expiry_preference="next" if expiry_pref == "next" else "near",
        today=datetime.now(_IST).date())


async def _resolve_deep_itm(client, item, row, cfg) -> Optional[_ResolvedTrade]:
    """Resolve a deep-ITM (≈delta-0.9) CE/PE for the signal direction, with an
    LTP-based entry premium and a delta-implied premium stop derived from the
    underlying ST trail. Returns None if the strike can't be resolved."""
    exch = item.option_exchange
    try:
        dump = await client.search_instruments("", exch, limit=1_000_000)
    except Exception:  # noqa: BLE001
        return None
    today = datetime.now(_IST).date()
    chain = chain_rows_for(dump, item.tradingsymbol, today)
    if not chain:
        return None
    direction = "long" if getattr(row, "direction", "long") in ("long", "bull", 1) else "short"
    iv = 0.18
    expiry_types = tuple(cfg.scan_expiries or ())
    if cfg.target_delta:
        pick = pick_by_delta(chain, spot=row.spot, direction=direction,
                             target_delta=float(cfg.target_delta), iv=iv,
                             expiry_types=expiry_types, today=today)
    else:
        picks = pick_strikes(chain, spot=row.spot, direction=direction,
                             moneynesses=[cfg.itm_depth or "ITM10"],
                             expiry_types=expiry_types, today=today)
        pick = picks[0][1] if picks else None
    if pick is None or not pick.option_symbol:
        return None

    # entry premium from a single LTP quote (cheap; signals are rare)
    entry_premium = 0.0
    qkey = f"{exch}:{pick.option_symbol}"
    try:
        q = await client.get_ltp([qkey])
        if q and qkey in q:
            entry_premium = float(q[qkey].get("last_price") or 0.0)
    except Exception:  # noqa: BLE001
        pass

    # delta-implied premium stop: a deep-ITM option's premium moves ≈ delta × the
    # underlying's move, so stop_prem ≈ entry_prem − delta × |spot − ST trail|.
    g = black_scholes_greeks(spot=float(row.spot), strike=float(pick.strike),
                             dte_days=max(1.0, float(pick.dte)), iv=iv,
                             option_type=pick.option_type)
    delta = abs(g.delta) or 0.9
    move = abs(float(row.spot) - float(row.stop_loss or row.spot))
    stop_premium = max(0.0, entry_premium - delta * move) if entry_premium > 0 else 0.0
    return _ResolvedTrade(
        symbol=pick.option_symbol, exchange=exch, token=int(pick.token or 0),
        lot_size=int(pick.lot_size or 0), entry_px=entry_premium, stop_px=stop_premium)


def _make_place_cb(client, uid: str):
    """Gated auto-exec: risk-sized option BUY (nearest-spot leg) under the same
    live-safety + idempotency checks as manual Kite orders, with a broker-side
    protective stop and tick-monitor registration. Logs every outcome.

    When directional_mode is ON and vehicle is 'futures', dispatches to the
    futures order path instead.  All existing behavior is preserved when
    directional_mode is OFF (default)."""
    async def _cb(row, item) -> None:
        args = option_order_args(row)  # primary (first) leg — existing options behavior
        if not args or not args["option_symbol"] or args["size"] <= 0:
            return
        cfg = state.get_config(uid)
        # One open auto-position per "slot": per underlying for spot signals, per
        # contract for derivatives (so each fired CE/PE strike is independent).
        guard_key = args["option_symbol"] if row.source == "derivatives" else row.underlying
        if state.is_auto_open(uid, guard_key):
            return

        # ── vehicle selection (directional mode; OFF ⇒ existing behavior) ──────
        use_futures = (cfg.directional_mode and cfg.vehicle == "futures"
                       and "futures" in cfg.enabled_vehicles)
        use_deep_itm = (cfg.directional_mode and cfg.vehicle == "deep_itm_options"
                        and "deep_itm_options" in cfg.enabled_vehicles)
        # Label reflects what is ACTUALLY traded — selecting a disabled vehicle
        # falls back to options, so it must not be labelled as that vehicle.
        vehicle_label = "futures" if use_futures else ("deep_itm_options" if use_deep_itm else "otm_options")
        # Signal direction (bull→long / bear→short). OPTIONS are ALWAYS long-premium
        # (we BUY a call for bull, a put for bear), so their stop stays a downside
        # premium stop regardless of bull/bear — only FUTURES carry the signal's
        # direction into a two-sided stop. (This is the P0 fix: previously a bear
        # PE-buy was mislabelled "short", inverting its GTT side + monitor exit.)
        signal_dir = "long" if getattr(row, "direction", "long") in ("long", "bull", 1) else "short"
        pos_direction = signal_dir if use_futures else "long"

        # ── optional entry-quality filters (None ⇒ off; never gate by default) ─
        if cfg.adx_min is not None and row.adx is not None and row.adx < float(cfg.adx_min):
            state.log(uid, "info", f"{row.underlying} entry skipped — ADX {row.adx:.1f} < {cfg.adx_min}")
            return
        if cfg.atr_pct_min is not None and row.atr_pct is not None and row.atr_pct < float(cfg.atr_pct_min):
            state.log(uid, "info", f"{row.underlying} entry skipped — ATR %ile {row.atr_pct:.0f} < {cfg.atr_pct_min}")
            return

        # ── resolve the tradable instrument for the chosen vehicle ─────────────
        # Defaults = the existing options leg (unchanged when directional_mode OFF).
        trade_symbol = args["option_symbol"]
        trade_exchange = args["exchange"]
        trade_token = int(args.get("token") or row.token or 0)
        trade_lot = int(args["lot_size"] or 0)
        entry_px = float(args.get("entry_premium") or 0.0)
        stop_px = float(args.get("stop_premium") or 0.0)

        if use_futures:
            fp = await _resolve_future(client, item, cfg.futures_expiry)
            if fp is None or not fp.tradingsymbol:
                state.log(uid, "order_blocked", f"{row.underlying}: futures contract unresolved — skipped")
                return
            trade_symbol, trade_exchange = fp.tradingsymbol, fp.exchange
            trade_token, trade_lot = int(fp.token or 0), int(fp.lot_size or 0)
            # Futures risk is in INDEX POINTS: entry ≈ spot, stop = the underlying ST trail.
            entry_px = float(row.spot or 0.0)
            stop_px = float(row.stop_loss or 0.0)
        elif use_deep_itm:
            rt = await _resolve_deep_itm(client, item, row, cfg)
            if rt is None or not rt.symbol:
                state.log(uid, "order_blocked", f"{row.underlying}: deep-ITM strike unresolved — skipped")
                return
            trade_symbol, trade_exchange = rt.symbol, rt.exchange
            trade_token, trade_lot = rt.token, rt.lot_size
            entry_px, stop_px = rt.entry_px, rt.stop_px

        # ── risk sizing (the default options branch is byte-identical to before) ─
        qty = int(args["size"])
        lots = 1
        capital = None
        if use_futures:
            if cfg.risk_sizing and entry_px > 0 and stop_px > 0 and trade_lot > 0:
                capital = await available_fo_capital(client)
                sized = sizing.size_future_position(
                    entry_price=entry_px, stop_price=stop_px, lot_size=trade_lot,
                    available_capital=capital, risk_pct=cfg.risk_pct, max_lots=cfg.max_lots)
                if sized.qty > 0:
                    qty, lots = sized.qty, sized.lots
                    state.log(uid, "info", f"futures sizing → {sized.reason}")
            else:
                qty = trade_lot or qty
        elif use_deep_itm:
            qty = trade_lot or qty
            if cfg.risk_sizing and entry_px > 0 and stop_px > 0 and trade_lot > 0:
                capital = await available_fo_capital(client)
                sized = sizing.size_position(
                    entry_premium=entry_px, stop_premium=stop_px, lot_size=trade_lot,
                    available_capital=capital, risk_pct=cfg.risk_pct, max_lots=cfg.max_lots)
                if sized.qty > 0:
                    qty, lots = sized.qty, sized.lots
                    state.log(uid, "info", f"{trade_symbol} sizing → {sized.reason}")
        elif cfg.risk_sizing and args.get("entry_premium") and args.get("stop_premium") is not None:
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

        # ── portfolio drawdown breaker (opt-in; only ever downsizes or halts) ──
        if cfg.wire_risk_infra:
            cap = capital if capital is not None else await available_fo_capital(client)
            mult, brk = state.drawdown_multiplier(uid, cap)
            if mult <= 0.0:
                state.log(uid, "order_blocked",
                          f"{row.underlying}: circuit breaker [{brk}] — new entries halted")
                return
            if mult < 1.0:
                lots = max(1, int(lots * mult))
                qty = lots * trade_lot if trade_lot > 0 else qty
                state.log(uid, "info", f"{row.underlying}: breaker [{brk}] → size ×{mult:.1f} ({lots} lot)")

            # correlation penalty: downsize an entry correlated with an open position
            open_assets = [op.underlying for op in positions.open_positions(uid)
                           if op.underlying and op.underlying != row.underlying]
            cmult = state.correlation_penalty(uid, row.underlying, open_assets)
            if cmult < 1.0:
                lots = max(1, int(lots * cmult))
                qty = lots * trade_lot if trade_lot > 0 else qty
                state.log(uid, "info",
                          f"{row.underlying}: correlation ×{cmult:.1f} vs open {open_assets} ({lots} lot)")

        # ── live safety (Kite is INR; USD daily-loss breaker is crypto-only) ───
        trade_side = "BUY" if (not use_futures or signal_dir == "long") else "SELL"
        idem = live_safety.make_idempotency_key(uid, trade_symbol, trade_side, qty, row.timestamp_ms)
        decision = live_safety.assert_safe_to_trade(
            positions=[], idempotency_key=idem, check_daily_loss=False)
        if not decision.allowed and decision.code != "duplicate_order":
            state.log(uid, "order_blocked", f"{row.underlying} {trade_symbol} blocked: {decision.reason}")
            return
        if live_safety.check_idempotency(idem):
            return  # this signal already executed

        # ── place order ───────────────────────────────────────────────────────
        try:
            if use_futures:
                side = "buy" if signal_dir == "long" else "sell"
                result = await client.place_order_future(
                    trade_symbol, side, qty, exchange=trade_exchange, tag=idem)
            else:
                result = await client.place_order_option(
                    trade_symbol, "buy", qty, exchange=trade_exchange,
                    stop_loss=args["stop_loss"], tag=idem)
        except Exception as exc:  # noqa: BLE001
            state.log(uid, "order_failed", f"{row.underlying} {trade_symbol}: {exc}")
            return
        oid = (result or {}).get("order_id", "")
        if not oid:
            return
        live_safety.record_idempotency(idem, oid)
        state.mark_auto_open(uid, guard_key)  # one-position guard (per slot)

        # ── register position for fill-tracking + tick monitor (E / C / D) ─────
        p = positions.register(positions.OpenPosition(
            uid=uid, symbol=trade_symbol, exchange=trade_exchange,
            token=trade_token, qty=qty, lot_size=trade_lot,
            entry_premium=entry_px, stop_premium=stop_px,
            order_id=oid, status=positions.PENDING,
            stop_mode=cfg.stop_mode, guard_key=guard_key,
            direction=pos_direction, vehicle=vehicle_label, underlying=row.underlying,
            exit_mode=cfg.exit_mode))

        # ── auto-subscribe the position's token to the ticker (tick monitor) ──
        if trade_token and cfg.stop_mode in ("monitor", "both"):
            try:
                from app.services.exchanges.kite import ticker_manager, constants as K
                await ticker_manager.subscribe(uid, [trade_token], mode=K.MODE_LTP)
                state.log(uid, "info",
                          f"Subscribed token {trade_token} ({trade_symbol}) to tick monitor")
            except Exception as _te:  # noqa: BLE001
                log.debug("kite monitor auto-subscribe failed for %s: %s", uid, _te)

        # ── broker-side protective stop (workstream C) ────────────────────────
        if cfg.stop_mode in ("broker", "both") and stop_px > 0:
            gtt_id = await protective_stop.place_stop(
                client, tradingsymbol=trade_symbol, exchange=trade_exchange,
                qty=qty, trigger_premium=stop_px, last_price=entry_px,
                direction=pos_direction)
            if gtt_id:
                positions.update_stop(uid, p.symbol, stop_px, gtt_id=gtt_id)
                state.log(uid, "info",
                          f"Protective GTT #{gtt_id} placed for {p.symbol} @ ₹{stop_px:.2f}")
            elif cfg.stop_mode == "broker":
                state.log(uid, "info",
                          f"⚠ Protective GTT failed for {p.symbol}; no broker stop "
                          f"(enable monitor mode for a server-side backstop)")

        monitor_note = "+monitor" if cfg.stop_mode in ("monitor", "both") else ""
        veh_note = f"{vehicle_label} " if cfg.directional_mode else ""
        dir_note = f" [{pos_direction}]" if cfg.directional_mode else ""
        state.log(uid, "order_placed",
                  f"{trade_side} {qty} ({lots} lot) {trade_symbol} @ market (#{oid}) "
                  f"[{veh_note}{cfg.stop_mode} stop{monitor_note}]{dir_note}")
    return _cb


def _new_trail_for_open(p, rows) -> Optional[float]:
    """Given an open position ``p``, find the matching fresh signal row and return
    the updated trail stop price.  Returns None if no match or no improvement.

    - Futures: trail is the underlying ST index level (``row.stop_loss``), and it
      tightens monotonically only for the correct direction:
        long  → trail moves UP   → take max(p.stop_premium, new)
        short → trail moves DOWN → take min(p.stop_premium, new)
    - OTM options (long premium): trail is ``leg.premium_sl`` from the matching
      leg in the signal row — tighter means higher (we take max).
    - Deep-ITM: no intra-scan re-price here (premium_sl is not in the deep-ITM
      row; the tick monitor handles the actual exit granularly).
    """
    for row in rows:
        if row.underlying != p.underlying:
            continue
        if p.vehicle == "futures":
            new_sl = float(row.stop_loss or 0.0)
            if new_sl <= 0:
                return None
            if p.direction == "long":
                return new_sl if new_sl > p.stop_premium else None
            else:
                return new_sl if new_sl < p.stop_premium else None
        elif p.vehicle == "otm_options":
            for leg in row.legs:
                if leg.option_symbol == p.symbol and (leg.premium_sl or 0) > 0:
                    new_sl = float(leg.premium_sl)
                    # OTM option long: stop is a floor price — tighter = higher floor
                    return new_sl if new_sl > p.stop_premium else None
    return None


async def _update_open_position_trails(client, uid: str) -> None:
    """After each scan, push tightened trail stops to open positions.

    Covers the in-scan trail-update gap: the scanner computes fresh ST levels
    every 5 min but the original entry stop was never updated.  This pass:
      1. Reads the freshly-computed signal rows from the scanner snapshot.
      2. For each open position, computes whether the trail has tightened.
      3. Updates the in-memory stop (positions.update_stop).
      4. Moves the broker GTT if one is registered (protective_stop.move_stop).
      5. Re-subscribes the tick subscription (no-op if already subscribed).
    """
    open_pos = positions.open_positions(uid)
    if not open_pos:
        return
    snap = scanner.snapshot(uid)
    rows = snap.rows
    cfg = state.get_config(uid)
    for p in open_pos:
        if p.status != positions.OPEN:
            continue
        new_sl = _new_trail_for_open(p, rows)
        if new_sl is not None:
            old_sl = p.stop_premium
            positions.update_stop(uid, p.symbol, new_sl)
            state.log(uid, "info",
                      f"Trail updated {p.symbol} ({p.vehicle}): "
                      f"₹{old_sl:.2f} → ₹{new_sl:.2f}")
            if p.gtt_id and cfg.stop_mode in ("broker", "both"):
                try:
                    ltp_key = f"{p.exchange}:{p.symbol}"
                    ltp_data = await client.get_ltp([ltp_key])
                    ltp = float((ltp_data or {}).get(ltp_key, {}).get("last_price") or new_sl)
                except Exception:  # noqa: BLE001
                    ltp = new_sl
                moved = await protective_stop.move_stop(
                    client, trigger_id=p.gtt_id,
                    tradingsymbol=p.symbol, exchange=p.exchange,
                    qty=p.qty, trigger_premium=new_sl, last_price=ltp,
                    direction=p.direction)
                if moved:
                    state.log(uid, "info",
                              f"Broker GTT #{p.gtt_id} trailed to ₹{new_sl:.2f} for {p.symbol}")

        # Wire red-count awareness (scan driven): compute current reds from latest alignment using this position's entry-time exit_mode.
        # The monitor will see the updated current_red_count and can exit on red threshold (in addition to price trail).
        current_reds = 0
        for row in rows:
            if row.underlying != p.underlying:
                continue
            al = getattr(row, 'alignment', None)
            if al:
                trends = [al.fast, al.mid, al.slow]
                want_red = -1 if getattr(p, 'direction', 'long') == "long" else 1
                current_reds = sum(1 for t in trends if t == want_red)
            break
        positions.update_health(uid, p.symbol, current_reds, getattr(p, 'exit_mode', None))
        if current_reds > 0:
            mode = getattr(p, 'exit_mode', 'one_red')
            from app.engines.common.exit_counter import get_exit_threshold
            thresh = get_exit_threshold(mode)
            if current_reds >= thresh:
                state.log(uid, "info", f"Red count hit {current_reds}/{thresh} for open {p.symbol} under {mode} — monitor will consider for exit")


async def scan_user(client, uid: str, *, interval_s: float = SCAN_INTERVAL_S) -> int:
    """Run one full scan for ``uid`` with ``client``. Returns the signal count."""
    cfg_model = state.get_config(uid)
    if not cfg_model.engine_enabled:
        return 0  # engine is OFF — preserve existing Kite behaviour, no scanning
    if state.status(uid).scanning:
        state.log(uid, "info", "Scan skipped — another scan is already in progress for this account.")
        return 0
    if state.clear_cooldown(uid):
        state.log(uid, "info", "Scan skipped — cancelled recently (60s cooldown).")
        return 0
    state.set_scanning(uid, True)
    state.log(uid, "scan_start", "Initiating 1H Sterling Kite Engine scan…")
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
            deriv_universe=deriv_universe, log_cb=lambda msg: state.log(uid, "info", msg),
            close_feed=((lambda name, close: state.feed_correlation(uid, name, close))
                        if cfg_model.wire_risk_infra else None))
        snap = scanner.snapshot(uid)
        # The board now retains recently-ended setups too, but the "ready" count, badge
        # and return value should reflect only live (running/just-fired) signals.
        live = sum(1 for r in snap.rows if r.is_active or r.is_fresh)
        ended = len(snap.rows) - live
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
        # Trail-update pass: push tightened stops to open positions.
        if cfg_model.auto_execute:
            await _update_open_position_trails(client, uid)
        board = f"{live} live signal(s)" + (f" + {ended} ended" if ended else "")
        state.log(uid, "scan_done",
                  f"Scan complete — {board} / {len(selected)} instruments "
                  f"[{source}] ({mode}) · {' · '.join(parts)}")
        state.mark_scan_done(uid, signal_count=live, next_in_s=interval_s)
        return live
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
