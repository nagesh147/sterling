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
from app.services.kite_engine import monitor, positions, protection, protective_stop, sizing, state
from app.services.kite_engine import futures as futures_mod
from app.services.kite_engine.greeks import black_scholes_greeks, premium_stop_from_move
from app.services.kite_engine import market_hours
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
        exit_aligned_trail=getattr(c, 'exit_aligned_trail', False),
        price_stop_exit=getattr(c, 'price_stop_exit', True),
        hybrid_st_weight=getattr(c, 'hybrid_st_weight', 0.5)
    )


async def place_manual_order(uid: str, option_symbol: str, side: str,
                             quantity: int, exchange: str = "NFO") -> dict:
    """Shared manual BUY/SELL path used by BOTH the detail-panel REST endpoint and
    the Telegram bot, so they apply the identical live-safety gate + idempotency and
    place through the same warm client. Returns a status dict (never raises):
      {status: ok|duplicate|blocked|error, order_id?, message?, reason?, code?,
       protected?, protection?}
    Callers map this to HTTP / chat replies.

    A BUY here is a real position, so — when ``protect_manual_orders`` is on — it is
    registered and armed through the same `protection.arm_position` the auto-exec
    path uses, with the stop read off the board's own plan for that contract. Before
    this, a hand-placed order got no registry entry, no broker stop and no monitor,
    while the board kept showing it an SL, a TSL and a Target. `protected` says which
    of those two worlds the caller is in, so the UI can stop implying a stop that
    does not exist.

    A SELL is an exit, not an entry: if it matches a position we hold, it goes
    through the monitor's exit path so the manual sell and an automatic one cannot
    both fire.
    """
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

    # ── a manual SELL of something we hold is an EXIT ──────────────────────────
    # Routing it through the monitor takes the same `_exiting` claim an automatic
    # exit takes, so the user's sell and a trail/GTT exit cannot both place a SELL
    # for one position — and the registry, realized PnL and guard release all happen
    # exactly once, instead of the position lingering "open" after a manual close.
    if norm == "sell":
        held = positions.get(uid, option_symbol)
        if held is not None and held.status in (positions.OPEN, positions.PENDING):
            # The exit price is only used for the activity line and the realized-PnL
            # figure that feeds the INR daily-loss breaker. Passing the STOP there books
            # every discretionary exit as if it had been stopped out, which is a
            # fabricated number in both directions — so ask for the real one, and fall
            # back to the stop only if the quote fails.
            exit_px = held.stop_premium
            try:
                key = f"{held.exchange}:{held.symbol}"
                q = await client.get_ltp([key])
                exit_px = float((q or {}).get(key, {}).get("last_price") or held.stop_premium)
            except Exception:  # noqa: BLE001
                pass
            exited = await monitor._exit_position(
                client, uid, held, exit_px, reason="manual exit from the board",
                price_stop_exit=False)
            if not exited:
                # `_exit_position` bails without selling when another exit path already
                # holds this position, or when a broker stop it could not cancel may
                # already be selling it. Reporting "closed" here would be a lie the user
                # acts on — and the idempotency key must stay unrecorded, or the retry
                # would come back "Already submitted" for the next 60 seconds.
                state.log(uid, "order_failed",
                          f"⚠ {option_symbol}: manual exit did NOT go through — the position "
                          f"is STILL OPEN. Check Zerodha for a resting or triggered stop.")
                return {"status": "error", "order_id": held.order_id or "",
                        "message": ("Could not close the position — it is still open. A broker "
                                    "stop may already be selling it, or another exit is in "
                                    "flight. Check Zerodha, then retry."),
                        "protected": False, "protection": "position still open"}
            live_safety.record_idempotency(idem, held.order_id or "manual-exit")
            # `_exit_position` always exits the WHOLE tracked position — a GTT-protected
            # holding cannot be part-sold without re-arming the trigger for the remainder,
            # which it does not do. Say so rather than let a smaller requested quantity
            # imply a partial close happened.
            note = ("" if int(quantity) >= int(held.qty or 0) else
                    f" — the whole tracked position ({held.qty} qty) was closed, not the "
                    f"{quantity} requested")
            return {"status": "ok", "order_id": held.order_id or "",
                    "message": f"Position closed at market (manual exit){note}",
                    "protected": False, "protection": "position closed"}

    cfg = state.get_config(uid)
    plan = None
    if norm == "buy" and getattr(cfg, "protect_manual_orders", True):
        plan = protection.plan_for_symbol(uid, option_symbol)

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

    if norm != "buy":
        return {"status": "ok", "order_id": oid, "message": "Order submitted"}

    armed = await arm_manual_option_buy(
        client, uid, option_symbol=option_symbol, exchange=exchange,
        quantity=quantity, order_id=oid, plan=plan)
    return {"status": "ok", "order_id": oid, "message": "Order submitted", **armed}


async def arm_manual_option_buy(client, uid: str, *, option_symbol: str, exchange: str,
                                quantity: int, order_id: str, plan=None) -> dict:
    """Turn a just-placed hand-made option BUY into a protected position.

    Returns ``{"protected": bool, "protection": str}`` — never raises and never unwinds:
    the order is already live at the exchange, so a failure here is reported, not
    thrown at a caller who can no longer undo the trade. An entry we could not protect
    still succeeded as an ORDER; what must not happen is the board rendering an SL, a
    TSL and a Target beside a position that has none.

    Shared by BOTH order paths on purpose. ``/kite/engine/order`` (detail panel,
    Telegram) is not the one the signal board's Buy button reaches — that goes Buy →
    OrderWindow → ``POST /kite/orders`` — so arming only the first left every entry
    clicked from the board unguarded.
    """
    cfg = state.get_config(uid)
    if plan is None and getattr(cfg, "protect_manual_orders", True):
        plan = protection.plan_for_symbol(uid, option_symbol)
    if plan is None:
        reason = ("this contract is not on the current board, so there is no stop to arm"
                  if getattr(cfg, "protect_manual_orders", True)
                  else "automatic protection for manual orders is switched off")
        state.log(uid, "info", f"⚠ {option_symbol} is UNPROTECTED — {reason}")
        return {"protected": False, "protection": reason}
    if not plan.protectable:
        reason = "the signal has no premium stop for this contract, so nothing was armed"
        state.log(uid, "info", f"⚠ {option_symbol} is UNPROTECTED — {reason}")
        return {"protected": False, "protection": reason}

    # A stop that is not below the live premium is not a stop. Arm ZERO rather than
    # skip arming altogether: the registry row, the tick subscription and — the
    # expensive one — the expiry square-off all still apply, so a physically-settled
    # stock option cannot go to delivery just because its stop was unusable.
    stale = await protection.stale_stop_reason(client, plan)
    stop_to_arm = 0.0 if stale else plan.stop_premium

    try:
        armed = await protection.arm_position(
            client, uid, symbol=plan.symbol, exchange=plan.exchange or exchange,
            token=plan.token, qty=quantity, lot_size=plan.lot_size,
            entry_premium=plan.entry_premium, stop_premium=stop_to_arm,
            order_id=order_id, stop_mode=cfg.stop_mode, direction=plan.direction,
            vehicle="otm_options", underlying=plan.underlying, exit_mode=cfg.exit_mode,
            entry_spot=plan.entry_spot, entry_delta=plan.entry_delta,
            strike=plan.strike, expiry=plan.expiry, target_premium=plan.target_premium)
    except Exception as exc:  # noqa: BLE001
        log.warning("manual order arming failed for %s/%s: %s", uid, option_symbol, exc)
        state.log(uid, "order_failed",
                  f"⚠ {option_symbol} filled but could NOT be protected: {exc}")
        return {"protected": False, "protection": f"arming failed: {exc}"}

    if stale:
        state.log(uid, "order_failed",
                  f"⚠ {option_symbol} has NO STOP — {stale}. It is tracked (tick monitor + "
                  f"expiry square-off) but you must set a stop yourself.")
        return {"protected": False, "protection": f"no stop armed — {stale}"}
    state.log(uid, "order_placed", f"{option_symbol} protected — {armed.describe()}")
    return {"protected": armed.protected, "protection": armed.describe()}


async def disarm_for_manual_exit(client, uid: str, option_symbol: str) -> str:
    """Take the broker stop off a position the user is selling by hand. Returns a note
    for the caller, or "".

    A resting GTT plus a hand-placed SELL is the orphan case: once the user's sell
    fills, the trigger has nothing behind it, and if it later fires the account goes
    NAKED SHORT an option. Cancelling first is strictly safer than cancelling after —
    the worst case is a few seconds with only the tick monitor guarding.
    """
    held = positions.get(uid, option_symbol)
    if held is None or held.status not in (positions.OPEN, positions.PENDING) or not held.gtt_id:
        return ""
    outcome = await protective_stop.cancel_stop_result(client, held.gtt_id)
    positions.update_stop(uid, option_symbol, held.stop_premium, gtt_id=0)
    if outcome == protective_stop.CANCELLED:
        state.log(uid, "info",
                  f"{option_symbol}: broker GTT #{held.gtt_id} cancelled for a hand-placed "
                  f"SELL — it would have been a resting order with no position behind it")
        return ""
    state.log(uid, "order_failed",
              f"⚠ {option_symbol}: broker GTT #{held.gtt_id} could NOT be cancelled "
              f"({outcome}) before your SELL — if it fires after you are flat you will be "
              f"SHORT an option. Check Zerodha now.")
    return f"broker stop #{held.gtt_id} could not be cancelled ({outcome}) — check Zerodha"


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


_IV_ASSUMPTION = 0.18  # fixed BS IV for delta translation (matches the study harness)


def _dte_from_expiry(expiry: str, today: Optional[datetime] = None) -> float:
    """Calendar days to an option ``expiry`` ("YYYY-MM-DD…"). Floored at 1 so a
    same-/next-day weekly still prices with non-degenerate greeks. Returns a safe
    default (7) if the string can't be parsed."""
    try:
        d = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").date()
        ref = (today or datetime.now(_IST)).date()
        return float(max(1, (d - ref).days))
    except Exception:  # noqa: BLE001
        return 7.0


def _passes_liquidity(quote, max_spread_pct, min_oi) -> tuple:
    """(_ok, reason) for an option leg's quote against optional spread/OI gates.

    Fail-OPEN on missing data (no quote / no depth / no OI) — a data gap must not
    block a real signal; the protective stop still guards the position. Only an
    explicit breach (spread too wide / OI too thin) rejects the entry."""
    if quote is None:
        return True, ""
    if min_oi is not None:
        oi = float(quote.get("oi") or quote.get("open_interest") or 0.0)
        if oi and oi < float(min_oi):
            return False, f"OI {oi:.0f} < {min_oi}"
    if max_spread_pct is not None:
        depth = quote.get("depth") or {}
        bid = float(((depth.get("buy") or [{}])[0]).get("price") or 0.0)
        ask = float(((depth.get("sell") or [{}])[0]).get("price") or 0.0)
        if bid > 0 and ask > 0:
            mid = 0.5 * (bid + ask)
            spread_pct = (ask - bid) / mid * 100.0 if mid > 0 else 0.0
            if spread_pct > float(max_spread_pct):
                return False, f"spread {spread_pct:.1f}% > {max_spread_pct}%"
    return True, ""


async def _resolve_premium_stop(
    client, *, exch: str, symbol: str, strike: float, expiry: str,
    option_type: str, spot: float, trail_level: float, iv: float = _IV_ASSUMPTION,
) -> tuple:
    """Fetch an option's LTP and derive a delta-implied premium stop from the
    underlying ST ``trail_level``. Returns ``(entry_premium, stop_premium, delta)``.

    Shared by the OTM (spot-signal) and deep-ITM auto-exec paths so the spot→premium
    stop translation lives in exactly one place. ``entry_premium`` is 0 when the quote
    is unavailable (caller then degrades to single-lot sizing + the tick monitor)."""
    entry_premium = 0.0
    qkey = f"{exch}:{symbol}"
    try:
        q = await client.get_ltp([qkey])
        if q and qkey in q:
            entry_premium = float(q[qkey].get("last_price") or 0.0)
    except Exception as _exc:  # noqa: BLE001
        log.debug("suppressed: %s", _exc)
    dte = _dte_from_expiry(expiry)
    g = black_scholes_greeks(spot=float(spot), strike=float(strike), dte_days=dte,
                             iv=iv, option_type=option_type)
    # SIGNED delta: + for a CE, − for a PE. Falls back to a signed ±0.5 if BS returns
    # a degenerate 0 so the translation still produces a stop on either side.
    delta = g.delta if g.delta != 0.0 else (0.5 if str(option_type).upper().startswith("C") else -0.5)
    stop_premium = premium_stop_from_move(
        entry_premium=entry_premium, delta=delta, spot=float(spot), trail_level=float(trail_level))
    return entry_premium, stop_premium, delta


@dataclass
class _ResolvedTrade:
    """The instrument the auto-exec should actually trade for the chosen vehicle."""
    symbol: str
    exchange: str
    token: int
    lot_size: int
    entry_px: float            # premium (options) or index price (futures)
    stop_px: float             # premium stop (options) or index-point stop (futures)
    delta: float = 0.0         # |BS delta| for option vehicles (0 for futures)
    strike: float = 0.0
    expiry: str = ""


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

    # entry premium (single LTP quote) + delta-implied premium stop from the
    # underlying ST trail — the SAME translation used for spot-mode OTM legs.
    entry_premium, stop_premium, delta = await _resolve_premium_stop(
        client, exch=exch, symbol=pick.option_symbol, strike=float(pick.strike),
        expiry=pick.expiry, option_type=pick.option_type,
        spot=float(row.spot), trail_level=float(row.stop_loss or row.spot), iv=iv)
    return _ResolvedTrade(
        symbol=pick.option_symbol, exchange=exch, token=int(pick.token or 0),
        lot_size=int(pick.lot_size or 0), entry_px=entry_premium, stop_px=stop_premium,
        delta=delta, strike=float(pick.strike), expiry=str(pick.expiry))


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

        # ── Sterling Value-Flow Navigator gate (additive; a pass-through
        # unless the user explicitly enabled Navigator in `gate` mode).
        # NOTE: gate mode is reachable in production — promoting a calibration
        # report unlocks it, and a user can then select it. Do not reason about
        # this block as dead code.
        # Reading the config itself is allowed to fail OPEN — a Navigator-
        # side hiccup (its tables not migrated, a transient read error)
        # must never halt the entire unrelated Kite auto-exec engine for
        # users who never touched Navigator. But once the config confirms
        # gate mode is actually active, a subsequent eligibility-check
        # failure fails CLOSED — at that point we cannot prove the user's
        # own explicitly-selected gate isn't being bypassed.
        nav_gate_active = False
        try:
            from app.services.navigator import config_store as navigator_config_store
            nav_record = navigator_config_store.get(uid, default_underlyings=cfg.scan_indices)
            nav_gate_active = nav_record.config.enabled and nav_record.config.operating_mode == "gate"
        except Exception as exc:  # noqa: BLE001
            log.debug("Navigator config unavailable, treating as not-gating for %s: %s", uid, exc)

        if nav_gate_active:
            try:
                from app.services.navigator import service as navigator_service
                nav_eligible, nav_reason = navigator_service.check_execution_eligible(
                    uid, row, default_underlyings=cfg.scan_indices,
                )
            except Exception as exc:  # noqa: BLE001
                log.error("Navigator gate check failed while gate mode is active — failing closed for %s: %s", uid, exc)
                nav_eligible, nav_reason = False, "navigator_check_failed"
            if not nav_eligible:
                state.log(uid, "order_blocked", f"{row.underlying}: entry skipped — Navigator gate ({nav_reason})")
                return

        # One open auto-position per "slot": per underlying for spot signals, per
        # contract for derivatives (so each fired CE/PE strike is independent).
        guard_key = args["option_symbol"] if row.source == "derivatives" else row.underlying
        if state.is_auto_open(uid, guard_key):
            return

        # ── "both"-mode cross guard ────────────────────────────────────────────
        # In scan_source="both", a spot signal and a derivatives signal on the SAME
        # underlying can both fire in one scan (their guard keys differ: underlying
        # vs option symbol). Block the second so one move isn't traded twice.
        if getattr(cfg, "scan_source", "spot") == "both" and any(
                op.underlying == row.underlying for op in positions.open_positions(uid)):
            state.log(uid, "info",
                      f"{row.underlying}: entry skipped — already holding a position on this "
                      f"underlying (both-mode cross guard)")
            return

        # ── session-time gate: no new entries just before the close (opt-in) ────
        blk = int(getattr(cfg, "block_entry_minutes_before_close", 0) or 0)
        if blk > 0:
            mtc = market_hours.minutes_to_close()
            if mtc is not None and mtc < blk:
                state.log(uid, "info",
                          f"{row.underlying}: entry skipped — {mtc:.0f}m to close < {blk}m "
                          f"(overnight-gap guard)")
                return

        # ── INR daily-loss breaker (opt-in): halt new entries after a bad day ───
        if getattr(cfg, "max_daily_loss_pct", None) is not None:
            cap0 = await available_fo_capital(client)
            day_pnl = state.daily_realized_pnl(uid)
            if cap0 > 0 and day_pnl < 0 and (-day_pnl) >= (float(cfg.max_daily_loss_pct) / 100.0) * cap0:
                state.log(uid, "order_blocked",
                          f"{row.underlying}: daily loss ₹{-day_pnl:.0f} ≥ {cfg.max_daily_loss_pct}% of "
                          f"₹{cap0:.0f} — new entries halted for today")
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
        # Only Navigator originations carry a target (from the AVWAP proposal). A
        # SuperTrend row has none by design — it exits on the trail or the red
        # counter — so this stays 0 and the GTT is a plain stop.
        target_px = 0.0
        # Delta-translation context stored on the position so every trailing update can
        # re-price the underlying ST level into a premium stop. Futures leave delta 0
        # (they trail in index points directly).
        pos_entry_spot = float(row.spot or 0.0)
        pos_delta = 0.0
        pos_strike = 0.0
        pos_expiry = ""

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
            pos_delta, pos_strike, pos_expiry = rt.delta, rt.strike, rt.expiry
        else:
            # ── default OTM path ──────────────────────────────────────────────
            # Derivatives rows carry premium_spot/premium_sl → entry_px/stop_px are
            # already set from option_order_args. SPOT-source rows carry NO premium,
            # so their stop_px was 0 → the position was UNPROTECTED (no GTT, monitor
            # exit inert, sizing floored to 1 lot). D1 fix: fetch the leg LTP and derive
            # a delta-implied premium stop from the underlying ST trail (row.stop_loss).
            # Reuse the exact leg selected by option_order_args. Independently
            # resolving against grouped row.spot (zero) could select another strike.
            leg = next((l for l in row.legs if l.option_symbol == trade_symbol), None)
            if leg is None and row.legs:
                reference_spot = float(row.underlying_spot or row.spot or 0.0)
                leg = min(row.legs, key=lambda l: abs(l.strike - reference_spot))
            if leg is not None:
                pos_strike = float(leg.strike or 0.0)
                pos_expiry = str(leg.expiry or "")
                target_px = float(getattr(leg, "premium_target", 0.0) or 0.0)
                if entry_px <= 0 or stop_px <= 0:
                    entry_px, stop_px, pos_delta = await _resolve_premium_stop(
                        client, exch=trade_exchange, symbol=trade_symbol,
                        strike=pos_strike, expiry=pos_expiry, option_type=row.option_type,
                        spot=float(row.spot), trail_level=float(row.stop_loss or row.spot))

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
        elif cfg.risk_sizing and entry_px > 0 and stop_px > 0 and trade_lot > 0:
            # Default OTM sizing. Now keyed off the RESOLVED premium (entry_px/stop_px)
            # rather than args, so spot-source signals (whose args carry no premium) are
            # risk-sized too instead of always defaulting to a single lot.
            capital = await available_fo_capital(client)
            sized = sizing.size_position(
                entry_premium=entry_px,
                stop_premium=stop_px,
                lot_size=trade_lot,
                available_capital=capital,
                risk_pct=cfg.risk_pct,
                max_lots=cfg.max_lots,
            )
            if sized.qty > 0:
                qty, lots = sized.qty, sized.lots
                state.log(uid, "info", f"{trade_symbol} sizing → {sized.reason}")

        # ── option-leg liquidity gate (opt-in): skip thin / wide-spread strikes ─
        if (not use_futures) and (cfg.max_spread_pct is not None or cfg.min_oi is not None):
            try:
                qkey = f"{trade_exchange}:{trade_symbol}"
                q = await client.get_quote([qkey])
                ok, why = _passes_liquidity((q or {}).get(qkey), cfg.max_spread_pct, cfg.min_oi)
            except Exception as _exc:  # noqa: BLE001
                log.debug("suppressed: %s", _exc)
                ok, why = True, ""   # fail-open on a quote error
            if not ok:
                state.log(uid, "info", f"{row.underlying} {trade_symbol} entry skipped — {why}")
                return

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
        # ── no stop, no trade ─────────────────────────────────────────────────
        # An unresolved premium (strike has not traded yet today, quote rate-limited,
        # `_resolve_premium_stop` swallowed an error) leaves stop_px at 0. Everything
        # downstream then degrades silently: place_stop refuses a trigger of 0 so no GTT
        # is armed, positions.should_exit(0, ltp) is False on every tick so the monitor
        # is inert, and _retranslated_stop cannot re-derive a level from an entry premium
        # of 0 — so the stop stays 0 for the life of the position. The result is a real,
        # automatic, unattended BUY with no exit of any kind until the expiry square-off.
        # AUTO-EXEC IS UNATTENDED: a position we cannot protect must not be opened at all.
        # (The manual path deliberately does the opposite — the user asked for the fill,
        # and gets an explicit "UNPROTECTED" warning instead of a refusal.)
        if stop_px <= 0:
            state.log(uid, "order_blocked",
                      f"{row.underlying} {trade_symbol}: NO STOP could be resolved "
                      f"(premium quote unavailable) — auto-entry skipped rather than "
                      f"opened unprotected")
            return

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
                # `stop_px` — not args["stop_loss"] — is the authoritative premium stop:
                # it is what the protective GTT and the tick monitor below use, and for
                # a spot/navigator row it is the only one resolved into the premium
                # domain at all.
                result = await client.place_order_option(
                    trade_symbol, "buy", qty, exchange=trade_exchange,
                    stop_loss=(stop_px if stop_px > 0 else None), tag=idem)
        except Exception as exc:  # noqa: BLE001
            state.log(uid, "order_failed", f"{row.underlying} {trade_symbol}: {exc}")
            return
        oid = (result or {}).get("order_id", "")
        if not oid:
            return
        live_safety.record_idempotency(idem, oid)
        state.mark_auto_open(uid, guard_key)  # one-position guard (per slot)

        # ── register + arm (registry, tick subscription, broker stop/target) ───
        # Shared with the manual order path so a hand-placed entry is protected the
        # same way by the same code — this block used to be inline here, which is
        # how manual orders ended up with no stop at all.
        armed = await protection.arm_position(
            client, uid, symbol=trade_symbol, exchange=trade_exchange,
            token=trade_token, qty=qty, lot_size=trade_lot,
            entry_premium=entry_px, stop_premium=stop_px, order_id=oid,
            stop_mode=cfg.stop_mode, direction=pos_direction,
            # The red counter is defined against the SIGNAL, not the premium side.
            signal_direction=signal_dir, vehicle=vehicle_label,
            underlying=row.underlying, exit_mode=cfg.exit_mode, guard_key=guard_key,
            entry_spot=pos_entry_spot, entry_delta=pos_delta,
            strike=pos_strike, expiry=pos_expiry,
            target_premium=target_px)

        veh_note = f"{vehicle_label} " if cfg.directional_mode else ""
        dir_note = f" [{pos_direction}]" if cfg.directional_mode else ""
        # `armed.describe()`, not cfg.stop_mode: the config is what was ASKED for, and
        # printing it made the terminal claim "[both stop+monitor]" over a position that
        # got neither. This reports what is actually holding the position.
        state.log(uid, "order_placed",
                  f"{trade_side} {qty} ({lots} lot) {trade_symbol} @ market (#{oid}) "
                  f"[{veh_note}{armed.describe()}]{dir_note}")
        if not armed.protected:
            state.log(uid, "order_failed",
                      f"⚠ {trade_symbol} is OPEN and UNPROTECTED — {armed.describe()}. "
                      f"Set a stop in Zerodha now.")
    return _cb


def _is_expiring(expiry: str, today, within_days: int = 1) -> bool:
    """True if an option ``expiry`` ("YYYY-MM-DD…") is within ``within_days`` calendar
    days of ``today`` (or already past). ``within_days <= 0`` disables (always False);
    an empty/unparseable expiry is treated as not-expiring (futures carry none)."""
    if within_days <= 0 or not expiry:
        return False
    try:
        d = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").date()
    except Exception:  # noqa: BLE001
        return False
    return (d - today).days <= within_days


#: A live market order fills in seconds. Past this, a position still PENDING means the
#: postback was lost, not that the order is slow.
_PENDING_GRACE_MS = 90_000


async def _reconcile_pending_positions(client, uid: str) -> None:
    """Resolve positions still PENDING long after their entry order went in.

    Fill confirmation arrives on the WS order postback. When that message is missed — a
    dropped socket, a server restart, a postback that landed while we were down — the
    position stays PENDING forever, and PENDING is invisible to everything that guards
    it: ``on_tick`` returns early, the trail updater skips it, and so do the time stop
    and the expiry square-off. The broker GTT is then the only protection, and under
    ``stop_mode="monitor"`` there is none at all.

    So stop waiting for the message and ask the order book. The reply is fed through the
    same ``on_order_update`` the postback would have hit, so fill / rejection / partial
    all take their normal path, including cancelling a GTT armed against an entry that
    never filled.
    """
    now_ms = int(datetime.now(_IST).timestamp() * 1000)
    for p in positions.open_positions(uid):
        if p.status != positions.PENDING or not p.order_id:
            continue
        if now_ms - int(p.opened_ms or 0) < _PENDING_GRACE_MS:
            continue
        try:
            hist = await client.get_order_history(p.order_id)
        except Exception as exc:  # noqa: BLE001
            log.debug("kite pending reconcile failed for %s/%s: %s", uid, p.symbol, exc)
            continue
        last = (hist or [])[-1] if hist else None
        if not isinstance(last, dict) or not str(last.get("status") or "").strip():
            continue
        # The order book omits the symbol on some venues; on_order_update matches on it.
        last = {**last, "tradingsymbol": last.get("tradingsymbol") or p.symbol,
                "order_id": last.get("order_id") or p.order_id}
        state.log(uid, "info",
                  f"{p.symbol}: fill postback never arrived — reconciling from the order "
                  f"book ({str(last.get('status')).lower()})")
        await monitor.on_order_update(uid, last, client=client)


async def _square_off_expiring(client, uid: str) -> None:
    """Market-exit auto-exec option positions inside the configured expiry window.

    Without this, a held weekly can settle at/after expiry with no managed exit (the
    ST signal exit + premium stop both assume a live, tradable contract). Runs only
    during market hours (an exit order off-hours is pointless) and reuses the tick
    monitor's exit path (correct side, GTT cancel, guard release, unsubscribe)."""
    cfg = state.get_config(uid)
    days = int(getattr(cfg, "expiry_square_off_days", 1) or 0)
    if days <= 0 or not is_market_open():
        return
    today = datetime.now(_IST).date()
    for p in positions.open_positions(uid):
        if p.status != positions.OPEN or not _is_expiring(p.expiry, today, days):
            continue
        try:
            key = f"{p.exchange}:{p.symbol}"
            q = await client.get_ltp([key])
            ltp = float((q or {}).get(key, {}).get("last_price") or p.stop_premium)
        except Exception:  # noqa: BLE001
            ltp = p.stop_premium
        # NOT a price-stop exit: no broker GTT will ever square off a position for
        # expiry, so this must place its own SELL even when the GTT cancel could not be
        # confirmed. On a physically-settled stock option, skipping it means taking
        # delivery — lakhs per lot.
        await monitor._exit_position(
            client, uid, p, ltp, price_stop_exit=False,
            reason=f"expiry square-off (T-{days}, exp {str(p.expiry)[:10]})")


async def _time_stop_positions(client, uid: str) -> None:
    """Square off auto-exec positions held beyond ``time_stop_bars`` 1H bars (opt-in).

    The exit-mechanics sweep's one robust, cross-lens finding: a hold cap curbs theta
    bleed on long-option positions. Off unless configured; market-hours gated; reuses
    the tick-monitor exit path (correct side, GTT cancel, guard release, unsubscribe)."""
    cfg = state.get_config(uid)
    bars = int(getattr(cfg, "time_stop_bars", 0) or 0)
    if bars <= 0 or not is_market_open():
        return
    now_ms = int(datetime.now(_IST).timestamp() * 1000)
    for p in positions.open_positions(uid):
        if p.status != positions.OPEN or not p.opened_ms:
            continue
        held = (now_ms - int(p.opened_ms)) // 3_600_000
        if held < bars:
            continue
        try:
            key = f"{p.exchange}:{p.symbol}"
            q = await client.get_ltp([key])
            ltp = float((q or {}).get(key, {}).get("last_price") or p.stop_premium)
        except Exception:  # noqa: BLE001
            ltp = p.stop_premium
        await monitor._exit_position(
            client, uid, p, ltp, price_stop_exit=False,
            reason=f"time stop ({held}≥{bars} bars held)")


def _new_trail_for_open(p, rows) -> Optional[float]:
    """Given an open position ``p``, find the matching fresh signal row and return
    the updated trail stop price.  Returns None if no match or no improvement.

    - Futures: trail is the underlying ST index level (``row.stop_loss``), and it
      tightens monotonically only for the correct direction:
        long  → trail moves UP   → take max(p.stop_premium, new)
        short → trail moves DOWN → take min(p.stop_premium, new)
    - OTM options (long premium): if the matching leg carries ``premium_sl`` (a
      derivatives-mode row), trail to it. Otherwise (a spot-mode leg — whose
      option_symbol drifts as the ATM re-picks) re-derive the premium stop from the
      fresh underlying ST level via the stored entry delta.
    - Deep-ITM: always re-translate the fresh underlying ST level via the stored
      delta (D3 — previously deep-ITM never trailed after entry).

    Re-translation trails INTO profit as the ST ratchets past the entry spot, and
    ratchets monotonically (only returns a value that tightens the current stop).
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
            # spot-mode leg (no premium_sl / symbol drifted): delta re-translation
            new_sl = _retranslated_stop(p, row)
            if new_sl is not None:
                return new_sl
        elif p.vehicle == "deep_itm_options":
            new_sl = _retranslated_stop(p, row)
            if new_sl is not None:
                return new_sl
    return None


def _retranslated_stop(p, row) -> Optional[float]:
    """Re-derive a long-option premium stop from the fresh underlying ST level using
    the stored entry delta, returning it only if it TIGHTENS the current stop (higher
    for a long premium). Needs the delta-translation context captured at entry."""
    if not (p.entry_delta and p.entry_spot and (row.stop_loss or 0) > 0):
        return None
    new_sl = premium_stop_from_move(
        entry_premium=p.entry_premium, delta=p.entry_delta,
        spot=p.entry_spot, trail_level=float(row.stop_loss))
    return new_sl if (new_sl > p.stop_premium and new_sl > 0) else None


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
                    direction=p.direction,
                    # Carried on every move: a GTT modify rewrites the whole trigger,
                    # so omitting the target would quietly turn the OCO into a bare
                    # stop the first time the trail ratcheted.
                    target_premium=float(getattr(p, "target_premium", 0.0) or 0.0))
                if moved:
                    state.log(uid, "info",
                              f"Broker GTT #{p.gtt_id} trailed to ₹{new_sl:.2f} for {p.symbol}")
                else:
                    # The registry now says ₹new_sl while the broker still holds ₹old_sl.
                    # The tick monitor enforces the tighter one, so the position is not
                    # unguarded — but a silent failure here is how the two drift apart.
                    state.log(uid, "order_failed",
                              f"⚠ {p.symbol}: broker GTT #{p.gtt_id} could NOT be trailed to "
                              f"₹{new_sl:.2f} — the stop at Zerodha is still ₹{old_sl:.2f}; "
                              f"only the tick monitor is enforcing the tighter level")

        # ── red-count awareness (scan driven) ─────────────────────────────────
        # The monitor exits on current_red_count >= the exit_mode threshold, so what is
        # written here is a market SELL waiting to happen. Two things it must get right:
        #
        #   1. WHICH ROW. Match on the SIGNAL direction, not just the underlying. With
        #      scan_source="both" one underlying yields a bull row AND a bear row, and
        #      taking whichever came first (the old `break`) read the counter of the
        #      opposite trade.
        #   2. WHICH BAR. `row.current_reds` is computed at the LATEST bar. The old code
        #      read `row.alignment`, which is frozen at the ENTRY bar, and counted it
        #      against `p.direction` — "long" for every option, CE and PE alike. So a PE
        #      opened on an all-red bear signal scored 3-of-3 against itself immediately
        #      and was market-sold on the very next tick, with the SuperTrend still
        #      perfectly aligned in its favour.
        #
        # No matching row → leave the last known count alone. Writing 0 would silently
        # disarm the red exit for a position whose underlying simply dropped out of this
        # scan's universe.
        want_dir = getattr(p, "signal_direction", "") or p.direction
        match = next((r for r in rows
                      if r.underlying == p.underlying and r.direction == want_dir), None)
        if match is not None:
            current_reds = int(getattr(match, "current_reds", 0) or 0)
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
        # Confluence runs its own pass (underlying regime + per-leg premium confirmation),
        # so it uses neither the plain spot nor the plain deriv universe.
        confluence_universe = selected if source == "confluence" else None
        state.log(uid, "info", f"Scan plan: Scanning {len(selected)} instruments using '{source}' source.")

        # Auto-exec is universal — it fires on spot, derivatives, and confluence signals.
        place_cb = _make_place_cb(client, uid) if cfg_model.auto_execute else None
        await scanner.scan(
            uid=uid, client=client, universe=spot_universe, nfo_rows=nfo, bfo_rows=bfo,
            cfg=_ts_cfg(cfg_model), moneyness=cfg_model.strike_moneyness,
            expiry_types=cfg_model.scan_expiries,
            expiry_types_indices=cfg_model.scan_expiries_indices,
            expiry_types_stocks=cfg_model.scan_expiries_stocks,
            place_cb=place_cb,
            deriv_universe=deriv_universe, confluence_universe=confluence_universe,
            log_cb=lambda msg: state.log(uid, "info", msg),
            close_feed=((lambda name, close: state.feed_correlation(uid, name, close))
                        if cfg_model.wire_risk_infra else None))
        snap = scanner.snapshot(uid)
        # Sterling Value-Flow Navigator: CONFIRMATION ONLY here. Navigator
        # evaluates each of this engine's rows against its own fresh candle
        # fetch, then joins the resulting evidence back on synchronously from
        # cache. Both steps are a complete no-op — zero extra broker calls —
        # unless the user has explicitly enabled Navigator (disabled by
        # default for everyone).
        #
        # Structure Radar and Signal Origination are deliberately NOT run from
        # here (`include_origination=False`). Navigator is a peer engine with
        # its own scan loop (`services/navigator/runtime.py`), and that loop
        # owns origination: it fetches the candles, writes the shared decision
        # cache, and is the single place a Navigator-originated order can be
        # submitted. Running origination from both loops would double the
        # broker calls and, once calibration is promoted, could place the same
        # originated order twice.
        #
        # Navigator still either shares this engine's universe or resolves its
        # own. Re-selecting from the SAME already-built `full_universe` is a
        # pure in-memory filter — the four exchange dumps behind it are cached
        # for an hour, so a custom scope costs no extra broker round-trips.
        nav_universe = selected
        try:
            from app.services.navigator import service as navigator_service
            from app.services.navigator import config_store as navigator_config_store

            try:
                nav_cfg = navigator_config_store.get(
                    uid, default_underlyings=cfg_model.scan_indices).config
                if nav_cfg.scan_scope_mode == "custom":
                    nav_universe = select_scan_universe(
                        full_universe, indices=nav_cfg.scan_indices,
                        stocks=nav_cfg.scan_stocks, all_stocks=nav_cfg.scan_all_stocks)
                    if nav_cfg.enabled:
                        state.log(uid, "info",
                                  f"Navigator scan plan: {len(nav_universe)} instruments "
                                  f"using its own '{nav_cfg.scan_source}' source.")
            except Exception as exc:  # noqa: BLE001
                # A Navigator-side config hiccup must never change what the
                # base engine already decided to scan — fall back to shared.
                log.warning("Navigator scope resolve failed, using shared universe for %s: %s", uid, exc)

            snap.rows = await navigator_service.run_navigator_pass(
                client, uid, snap.rows, engine_config_payload=cfg_model.model_dump(mode="json"),
                default_underlyings=cfg_model.scan_indices,
                underlying_tokens={u.name: u.token for u in nav_universe},
                universe=nav_universe, nfo_rows=nfo, bfo_rows=bfo, moneyness=cfg_model.strike_moneyness,
                expiry_types=cfg_model.scan_expiries, expiry_types_indices=cfg_model.scan_expiries_indices,
                expiry_types_stocks=cfg_model.scan_expiries_stocks,
                include_origination=False,
            )
            snap.rows = navigator_service.attach_to_rows(uid, snap.rows, default_underlyings=cfg_model.scan_indices)
        except Exception as exc:  # noqa: BLE001
            log.warning("Navigator row-attach failed (non-fatal) for %s: %s", uid, exc)

        # No Navigator-originated auto-exec here. Originated rows are produced
        # and submitted by Navigator's own runtime loop, which additionally
        # re-checks `check_originated_execution_eligible` and the entry delay
        # per row. Keeping the single submission path there is what makes
        # "the same originated setup can only be ordered once" true by
        # construction rather than by timing luck.

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
        if source == "confluence":
            # Merged rows where the underlying AND a leg's own premium both fired.
            # deriv_charts here counts the candidate premiums checked for confirmation.
            cf = (f"confluence {d.confluence_fired} fired (spot+premium), "
                  f"{d.deriv_charts} premiums checked (bars {d.deriv_min_bars}–{d.deriv_max_bars})")
            parts.append(cf)
        if d.premium_missing:
            # Blank Entry/SL/TSL cells were previously indistinguishable from "no
            # signal". Name the count so a rate-limited option-history fetch is
            # visible instead of being read as a data-less contract.
            parts.append(
                f"⚠ {d.premium_missing}/{d.premium_ok + d.premium_missing} candidate legs "
                f"have no entry premium (option history empty and the signal is too old "
                f"to use today's LTP) — their Entry/SL/TSL show “—”"
            )
        # Maintenance of ALREADY-OPEN positions: ratchet their stops to the freshly
        # computed trail, square off anything near expiry, apply time stops.
        #
        # This used to be gated on `auto_execute`, which is the switch for OPENING new
        # positions. Turning AUTO off left every open position frozen on the stop it was
        # entered with — the trail stopped ratcheting, the broker GTT stopped moving, and
        # expiry/time stops stopped running — on exactly the positions the engine had
        # already committed real money to. Maintaining a position you hold is not the
        # same decision as opening a new one.
        # Reconcile FIRST: everything below skips a position that is still PENDING, so a
        # lost fill postback would otherwise hide it from all of them.
        await _reconcile_pending_positions(client, uid)
        await _reconcile_orphan_stops(client, uid)
        await _update_open_position_trails(client, uid)
        await _square_off_expiring(client, uid)
        await _time_stop_positions(client, uid)
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


#: Orphan-stop warnings already issued, per (uid, trigger_id). The sweep runs every
#: scan; without this it would repeat the same alarm every few minutes until the user
#: acts, and an alert that cries every scan stops being read.
_orphan_warned: set = set()


async def _reconcile_orphan_stops(client, uid: str) -> None:
    """Find protective triggers resting at Zerodha with NO position behind them.

    Every live path that can orphan a trigger is now closed at the point it happens — a
    rejected entry cancels its GTT, an exit filled outside the engine cancels it, an
    unconfirmed cancel is chased after the sell. What none of them covers is a trigger
    that was ALREADY orphaned: the process restarted while one was armed, or a cancel
    failed and only logged "check Zerodha for a resting SELL" before the position left
    the registry. Nothing ever looked again. A resting SELL with nothing behind it opens
    a naked short the moment it fires.

    Reports, never cancels. We cannot tell our own abandoned trigger from a stop the
    user placed by hand in the Kite app, and silently deleting the second would remove
    the protection they were relying on — the same class of harm, pointed the other way.
    The broker's own net quantity is the discriminator that makes the warning safe: a
    trigger over a holding they actually have is legitimate whoever placed it, so only a
    trigger with NO underlying holding is reported.
    """
    try:
        triggers = await client.get_gtts()
        raw = await client.get_positions_raw()
    except Exception as exc:  # noqa: BLE001
        log.debug("kite orphan-stop sweep skipped for %s: %s", uid, exc)
        return
    if not isinstance(triggers, list) or not triggers:
        return
    held = {str(p.get("tradingsymbol", "")).strip().upper()
            for p in ((raw or {}).get("net") or [])
            if int(p.get("quantity", 0) or 0) != 0}
    live = {p.symbol.upper() for p in positions.open_positions(uid)
            if p.status in (positions.PENDING, positions.OPEN)}
    for t in triggers:
        if not isinstance(t, dict):
            continue
        if str(t.get("status") or "").strip().lower() != "active":
            continue  # only a RESTING trigger can still fire
        tid = int(t.get("id") or t.get("trigger_id") or 0)
        if not tid or (uid, tid) in _orphan_warned:
            continue
        cond = t.get("condition") if isinstance(t.get("condition"), dict) else {}
        sym = str(cond.get("tradingsymbol") or "").strip().upper()
        if not sym or sym in held or sym in live:
            continue
        _orphan_warned.add((uid, tid))
        state.log(uid, "order_failed",
                  f"⚠ ORPHANED STOP: GTT #{tid} is resting at Zerodha for {sym}, but you "
                  f"hold no {sym} and the engine has no open position in it. If it "
                  f"triggers it will SELL something you do not own — cancel it in Kite.")


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
        except Exception as _exc:
            log.debug("suppressed: %s", _exc)
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
