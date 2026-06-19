"""
Telegram control surface for the Kite (Zerodha) triple-SuperTrend engine.

Kept SEPARATE from the crypto/scalping bot (telegram_bot.py): its own command
(`/kite`), its own `k*` callback namespace, and its own alert push — the two
streams never mix. Reuses the crypto bot's low-level Telegram transport
(`_send/_edit/_answer_cb/_btn`) so there is still one bot / one token.

Capabilities (acts as the local user ``default`` + its active Kite account):
  • view ready signals, positions, P&L, scan status
  • trigger a scan, toggle auto-trade
  • place option BUY/SELL and square-off positions — every state-changing action
    is gated by a TWO-TAP CONFIRM and runs through the shared, live-safety-gated
    ``service.place_manual_order`` path (identical to the REST/UI order path).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.core.auth import DEFAULT_USER_ID
from app.core.logging import get_logger

from app.services.notifications import telegram as _tg
from app.services.notifications.telegram_bot import _answer_cb, _btn, _edit, _send

log = get_logger(__name__)

UID = DEFAULT_USER_ID

# Kite alert push toggle + dedup of already-pushed signals (token|timestamp).
kite_alerts_enabled: bool = True
_alerted: set = set()

# Short-id maps so inline-button callback_data stays within Telegram's 64-byte
# limit (we can't cram a long option symbol into callback_data). Rebuilt whenever a
# list is rendered; a stale id simply fails the existence check at action time.
_sig_actions: Dict[str, dict] = {}      # sid -> {option_symbol, exchange, qty, side}
_pos_actions: Dict[str, dict] = {}      # pid -> {option_symbol, exchange, qty, side}
_pending: Dict[str, dict] = {}          # ptok -> resolved action to run on confirm
_counter = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return str(_counter)


# ── account / context ─────────────────────────────────────────────────────────
def _active_account():
    from app.services.exchanges.kite import accounts as kite_accounts
    return kite_accounts.get_active(UID)


def _mode_label() -> str:
    acct = _active_account()
    if acct is None:
        return "no account"
    return "PAPER" if acct.is_paper else "LIVE"


# ── keyboards ───────────────────────────────────────────────────────────────
def kite_menu_kb() -> dict:
    return {"inline_keyboard": [
        [_btn("📡 Signals", "ksig"), _btn("📊 Positions", "kpos")],
        [_btn("💰 P&L", "kpnl"), _btn("🔄 Scan now", "kscan")],
        [_btn("⚙️ Auto-trade", "kauto"), _btn("🔔 Alerts", "kalert")],
    ]}


def _back_kb() -> dict:
    return {"inline_keyboard": [[_btn("‹ Kite menu", "kmenu")]]}


def _confirm_kb(ptok: str) -> dict:
    return {"inline_keyboard": [[_btn("✅ Confirm", f"kok|{ptok}"), _btn("✖ Cancel", f"kno|{ptok}")]]}


# ── data access ───────────────────────────────────────────────────────────────
def _snapshot():
    from app.services.kite_engine.scanner import scanner
    return scanner.snapshot(UID)


def _ready_rows() -> list:
    """Active (running/ready) signal rows from the latest scan."""
    rows = getattr(_snapshot(), "rows", []) or []
    return [r for r in rows if getattr(r, "is_active", False)]


def _fmt(v: Optional[float], dp: int = 2) -> str:
    try:
        return f"{float(v):,.{dp}f}"
    except (TypeError, ValueError):
        return "—"


# ── text builders ─────────────────────────────────────────────────────────────
def build_kite_signals_text() -> str:
    rows = _ready_rows()
    if not rows:
        return "<b>🇮🇳 Kite signals</b>\nNo active signals in the latest scan."
    lines = [f"<b>🇮🇳 Kite signals · {len(rows)} active</b>"]
    for r in rows[:20]:
        arrow = "🟢▲" if r.direction == "long" else "🔴▼"
        leg = r.legs[0] if r.legs else None
        legtxt = f" · {leg.moneyness} {leg.option_symbol}" if leg else ""
        lines.append(f"{arrow} <b>{r.underlying}</b> {r.option_type}{legtxt}")
    if len(rows) > 20:
        lines.append(f"… +{len(rows) - 20} more")
    lines.append(f"\n<i>Mode: {_mode_label()}</i>")
    return "\n".join(lines)


def signals_kb() -> dict:
    """One action row per (top) signal: Buy / Sell its primary leg."""
    _sig_actions.clear()
    kb: List[list] = []
    for r in _ready_rows()[:8]:
        leg = r.legs[0] if r.legs else None
        if not leg or not leg.option_symbol:
            continue
        sid = _next_id()
        _sig_actions[sid] = {
            "option_symbol": leg.option_symbol, "exchange": r.exchange,
            "qty": int(leg.lot_size or 1), "underlying": r.underlying,
        }
        short = leg.option_symbol[-12:]
        kb.append([_btn(f"🟢 Buy {short}", f"kbuy|{sid}"),
                   _btn(f"🔴 Sell {short}", f"ksell|{sid}")])
    kb.append([_btn("🔄 Refresh", "ksig"), _btn("‹ Menu", "kmenu")])
    return {"inline_keyboard": kb}


async def build_kite_positions_text() -> str:
    acct = _active_account()
    if acct is None:
        return "<b>📊 Kite positions</b>\nNo active Kite account."
    from app.services.exchanges.kite import accounts as kite_accounts
    try:
        client = await kite_accounts.acquire_client(acct)
        positions = await client.get_positions()
    except Exception as exc:  # noqa: BLE001
        return f"<b>📊 Kite positions</b>\n⚠️ {exc}"
    live = [p for p in positions if getattr(p, "size", 0)]
    if not live:
        return "<b>📊 Kite positions</b>\nNo open positions."
    lines = [f"<b>📊 Kite positions · {len(live)}</b>"]
    for p in live:
        pnl = getattr(p, "unrealized_pnl", 0.0) or 0.0
        sign = "🟢" if pnl >= 0 else "🔴"
        lines.append(f"{sign} <b>{p.symbol}</b> {p.side} {abs(p.size)} · "
                     f"mark {_fmt(getattr(p,'mark_price',None))} · P&L {_fmt(pnl)}")
    return "\n".join(lines)


async def positions_kb() -> dict:
    _pos_actions.clear()
    acct = _active_account()
    kb: List[list] = []
    if acct is not None:
        from app.services.exchanges.kite import accounts as kite_accounts
        try:
            client = await kite_accounts.acquire_client(acct)
            positions = [p for p in await client.get_positions() if getattr(p, "size", 0)]
        except Exception:  # noqa: BLE001
            positions = []
        for p in positions[:8]:
            ex, _, ts = p.symbol.partition(":")
            pid = _next_id()
            _pos_actions[pid] = {
                "option_symbol": ts or p.symbol, "exchange": ex or "NFO",
                "qty": abs(int(p.size)), "side": "SELL" if p.size > 0 else "BUY",
            }
            kb.append([_btn(f"✖ Square off {ts[-12:]}", f"ksq|{pid}")])
    kb.append([_btn("🔄 Refresh", "kpos"), _btn("‹ Menu", "kmenu")])
    return {"inline_keyboard": kb}


async def build_kite_pnl_text() -> str:
    acct = _active_account()
    if acct is None:
        return "<b>💰 Kite P&L</b>\nNo active Kite account."
    from app.services.exchanges.kite import accounts as kite_accounts
    try:
        client = await kite_accounts.acquire_client(acct)
        positions = await client.get_positions()
    except Exception as exc:  # noqa: BLE001
        return f"<b>💰 Kite P&L</b>\n⚠️ {exc}"
    realized = sum((getattr(p, "realized_pnl", 0.0) or 0.0) for p in positions)
    unreal = sum((getattr(p, "unrealized_pnl", 0.0) or 0.0) for p in positions)
    tot = realized + unreal
    sign = "🟢" if tot >= 0 else "🔴"
    return (f"<b>💰 Kite P&L · {_mode_label()}</b>\n"
            f"Realized: {_fmt(realized)}\nUnrealized: {_fmt(unreal)}\n{sign} <b>Total: {_fmt(tot)}</b>")


def build_kite_status_text() -> str:
    from app.services.kite_engine import service, state
    cfg = state.get_config(UID)
    auto = "ON" if getattr(cfg, "auto_execute", False) else "OFF"
    running = "running" if service.is_auto_running() else "idle"
    return (f"<b>🇮🇳 Kite engine</b>\n"
            f"Mode: <b>{_mode_label()}</b>\n"
            f"Auto-trade: <b>{auto}</b> · loop {running}\n"
            f"Alerts: <b>{'ON' if kite_alerts_enabled else 'OFF'}</b>")


# ── confirm flow ──────────────────────────────────────────────────────────────
def _stage(action: dict) -> str:
    """Stash a resolved action; return its confirm token."""
    ptok = _next_id()
    _pending[ptok] = action
    return ptok


def _confirm_text(action: dict) -> str:
    kind = action["kind"]
    if kind == "order":
        return (f"<b>Confirm {action['side']} · {_mode_label()}</b>\n"
                f"{action['qty']} × <b>{action['option_symbol']}</b> ({action['exchange']}) @ market\n\n"
                f"Tap Confirm to place.")
    if kind == "auto":
        return (f"<b>Confirm auto-trade {action['to']}</b>\n"
                f"This {'ENABLES' if action['to'] == 'ON' else 'DISABLES'} automatic "
                f"order execution on {_mode_label()} signals.")
    return "Confirm?"


async def _run_action(action: dict) -> str:
    from app.services.kite_engine import service, state
    kind = action["kind"]
    if kind == "order":
        res = await service.place_manual_order(
            UID, action["option_symbol"], action["side"], action["qty"], action["exchange"])
        st = res.get("status")
        if st == "ok":
            return f"✅ {action['side']} {action['option_symbol']} placed (#{res.get('order_id','')})."
        if st == "duplicate":
            return "ℹ️ Already submitted (duplicate)."
        if st == "blocked":
            return f"🚫 Blocked: {res.get('reason')}"
        return f"⚠️ Failed: {res.get('message')}"
    if kind == "auto":
        cfg = state.get_config(UID)
        cfg.auto_execute = (action["to"] == "ON")
        state.set_config(UID, cfg)
        return f"⚙️ Auto-trade <b>{action['to']}</b>."
    return "Done."


# ── command + callback handlers (called by telegram_bot dispatcher) ───────────
async def handle_kite_command(chat_id: str) -> None:
    await _send(build_kite_status_text(), chat_id, kite_menu_kb())


async def handle_kite_callback(chat_id: str, message_id: int, cb_id: str, data: str) -> None:
    parts = data.split("|")
    kind = parts[0]
    arg = parts[1] if len(parts) > 1 else ""
    await _answer_cb(cb_id)

    if kind == "kmenu":
        await _edit(chat_id, message_id, build_kite_status_text(), kite_menu_kb())
    elif kind == "ksig":
        await _edit(chat_id, message_id, build_kite_signals_text(), signals_kb())
    elif kind == "kpos":
        await _edit(chat_id, message_id, await build_kite_positions_text(), await positions_kb())
    elif kind == "kpnl":
        await _edit(chat_id, message_id, await build_kite_pnl_text(), _back_kb())
    elif kind == "kscan":
        await _edit(chat_id, message_id, "🔄 Scanning…", _back_kb())
        msg = await _run_scan()
        await _edit(chat_id, message_id, msg, kite_menu_kb())
    elif kind == "kalert":
        global kite_alerts_enabled
        kite_alerts_enabled = not kite_alerts_enabled
        await _edit(chat_id, message_id, build_kite_status_text(), kite_menu_kb())
    elif kind == "kauto":
        from app.services.kite_engine import state
        cur = getattr(state.get_config(UID), "auto_execute", False)
        action = {"kind": "auto", "to": "OFF" if cur else "ON"}
        ptok = _stage(action)
        await _edit(chat_id, message_id, _confirm_text(action), _confirm_kb(ptok))
    elif kind in ("kbuy", "ksell"):
        a = _sig_actions.get(arg)
        if not a:
            await _edit(chat_id, message_id, "⚠️ Signal expired — refresh.", _back_kb())
            return
        action = {"kind": "order", "side": "BUY" if kind == "kbuy" else "SELL",
                  "option_symbol": a["option_symbol"], "exchange": a["exchange"], "qty": a["qty"]}
        ptok = _stage(action)
        await _edit(chat_id, message_id, _confirm_text(action), _confirm_kb(ptok))
    elif kind == "ksq":
        a = _pos_actions.get(arg)
        if not a:
            await _edit(chat_id, message_id, "⚠️ Position expired — refresh.", _back_kb())
            return
        action = {"kind": "order", "side": a["side"], "option_symbol": a["option_symbol"],
                  "exchange": a["exchange"], "qty": a["qty"]}
        ptok = _stage(action)
        await _edit(chat_id, message_id, _confirm_text(action), _confirm_kb(ptok))
    elif kind == "kok":
        action = _pending.pop(arg, None)
        if not action:
            await _edit(chat_id, message_id, "⚠️ Expired — try again.", _back_kb())
            return
        result = await _run_action(action)
        await _edit(chat_id, message_id, result, kite_menu_kb())
    elif kind == "kno":
        _pending.pop(arg, None)
        await _edit(chat_id, message_id, "Cancelled.", kite_menu_kb())


async def _run_scan() -> str:
    from app.services.exchanges.kite import accounts as kite_accounts
    from app.services.kite_engine import service
    acct = _active_account()
    if acct is None:
        return "⚠️ No active Kite account."
    try:
        client = await kite_accounts.acquire_client(acct)
        n = await service.scan_user(client, UID)
        return f"✅ Scan complete — {len(_ready_rows())} active signal(s)."
    except Exception as exc:  # noqa: BLE001
        return f"⚠️ Scan failed: {exc}"


# ── alert push (separate channel from the crypto bot) ─────────────────────────
def _alert_html(r) -> str:
    arrow = "🟢▲ LONG" if r.direction == "long" else "🔴▼ SHORT"
    leg = r.legs[0] if r.legs else None
    legtxt = f"\n{leg.moneyness} · {leg.option_symbol}" if leg else ""
    return (f"<b>🇮🇳 Kite signal · {r.underlying}</b>\n{arrow} · {r.option_type}{legtxt}\n"
            f"<i>{_mode_label()}</i>")


async def push_kite_alerts() -> None:
    """Push NEW active Kite signals to every enabled Kite-specific Telegram target
    (per-target bot token + chat). Deduped per token|timestamp so a standing signal
    isn't re-pushed every cycle.

    FALLBACK: if the user has no enabled Kite targets configured, fall back to the
    legacy shared global bot/chat so existing alerts don't silently stop.
    """
    if not kite_alerts_enabled:
        return

    from app.services.notifications import kite_telegram_store as kts
    targets = kts.enabled_targets(UID)
    has_targets = bool(targets)
    legacy_ok = bool(_tg.TELEGRAM_TOKEN and _tg.TELEGRAM_CHAT_ID)
    if not has_targets and not legacy_ok:
        return

    rows = _ready_rows()
    live_keys = {f"{r.token}|{r.timestamp_ms}" for r in rows}
    _alerted.intersection_update(live_keys)
    fresh = [r for r in rows if f"{r.token}|{r.timestamp_ms}" not in _alerted]
    for r in fresh:
        _alerted.add(f"{r.token}|{r.timestamp_ms}")
        html = _alert_html(r)
        if has_targets:
            for t in targets:
                await kts.send_via(t.bot_token, t.chat_id, html)
        elif legacy_ok:
            await _send(html, str(_tg.TELEGRAM_CHAT_ID), kite_menu_kb())
