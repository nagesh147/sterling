"""
Interactive Telegram bot for Sterling.

Long-polls Telegram for commands and serves scalping signals, positions and P&L
with inline-keyboard filters, and pushes signal-detection alerts. Reuses the same
scan / positions logic as the REST API so the bot and UI always agree.

Commands:
  /signals    — current scalping signals (buttons: All / PA / SMC / MA · Ready only)
  /positions  — positions (buttons: All / Open / Closed · P&L)
  /pnl        — portfolio P&L summary
  /alerts     — toggle signal-detection push alerts on/off
  /help       — list commands

Only the configured chat (TELEGRAM_CHAT_ID) is served, so the bot won't respond
to strangers who find it.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from app.services.notifications import telegram as _tg

log = logging.getLogger(__name__)

_API = "https://api.telegram.org"
_STRAT_LABEL = {"all": "All", "price_action": "PA", "smc": "SMC", "ma_crossover": "MA Cross"}

# Push signal alerts on by default; toggled via /alerts. Dedup set of already-alerted
# setups so the same signal isn't re-pushed every scan.
alerts_enabled: bool = True
_alerted: set[str] = set()


# ── Low-level Telegram API ───────────────────────────────────────────────────
async def _api(method: str, payload: dict, timeout: float = 35.0) -> dict:
    if not _tg.TELEGRAM_TOKEN:
        return {}
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{_API}/bot{_tg.TELEGRAM_TOKEN}/{method}", json=payload, timeout=timeout)
        return r.json() if r.status_code == 200 else {}
    except Exception as exc:
        log.debug("telegram_bot _api %s error: %s", method, exc)
        return {}


async def _send(text: str, chat_id: str, reply_markup: Optional[dict] = None) -> dict:
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _api("sendMessage", payload)


async def _edit(chat_id: str, message_id: int, text: str, reply_markup: Optional[dict] = None) -> dict:
    payload: dict = {"chat_id": chat_id, "message_id": message_id, "text": text,
                     "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _api("editMessageText", payload)


async def _answer_cb(cb_id: str, text: str = "") -> None:
    await _api("answerCallbackQuery", {"callback_query_id": cb_id, "text": text})


def _btn(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data}


# ── Inline keyboards ─────────────────────────────────────────────────────────
def _signals_kb(strategy: str, ready_only: bool) -> dict:
    def mk(label: str, strat: str) -> dict:
        return _btn(("● " if strategy == strat else "") + label, f"sig|{strat}|{int(ready_only)}")
    row1 = [mk("All", "all"), mk("PA", "price_action"), mk("SMC", "smc"), mk("MA", "ma_crossover")]
    row2 = [
        _btn(("✓ " if ready_only else "") + "Ready only", f"sig|{strategy}|{0 if ready_only else 1}"),
        _btn("🔄", f"sig|{strategy}|{int(ready_only)}"),
    ]
    return {"inline_keyboard": [row1, row2]}


def _positions_kb(status: str) -> dict:
    def mk(label: str, st: str) -> dict:
        return _btn(("● " if status == st else "") + label, f"pos|{st}")
    return {"inline_keyboard": [
        [mk("All", "all"), mk("Open", "open"), mk("Closed", "closed")],
        [_btn("💰 P&L", "pnl"), _btn("🔄", f"pos|{status}")],
    ]}


# ── Data builders (reuse REST logic) ──────────────────────────────────────────
def _load_cfg():
    from app.engines.sterling_engine.config import default_config
    from app.engines.sterling_engine.config import ScalpingConfig
    from app.services.db import get_config
    # New key, falling back to the legacy "scalping_config" for pre-rename installs.
    raw = get_config("sterling_engine_config") or get_config("scalping_config")
    if raw:
        try:
            return ScalpingConfig.model_validate_json(raw)
        except Exception as _exc:
            log.debug("suppressed: %s", _exc)
    return default_config()


async def _scan():
    from app.api.v1.endpoints.sterling_engine import _scan_all
    from app.services import adapter_manager as _adm
    cfg = _load_cfg()
    try:
        src = _adm.get_data_source()
    except Exception:
        src = ""
    return await asyncio.to_thread(_scan_all, cfg, src)


def _fmt_usd(v: Optional[float]) -> str:
    if v is None or v == 0:
        return "—"
    return f"${v:,.2f}" if abs(v) < 1000 else f"${v:,.0f}"


def _fmt_signed(v: float) -> str:
    return f"{'+' if v >= 0 else '−'}${abs(v):,.2f}"


def build_signals_text(scan, strategy: str, ready_only: bool) -> str:
    sigs = [s for s in scan.signals if s.direction in ("long", "short")]
    if strategy != "all":
        sigs = [s for s in sigs if s.strategy == strategy]
    if ready_only:
        sigs = [s for s in sigs if s.entry_ok]
    sigs = sigs[:20]
    head = f"<b>📡 Scalping Signals</b> · {_STRAT_LABEL.get(strategy, strategy)}"
    head += " · ready" if ready_only else ""
    if not sigs:
        return head + "\n\n<i>No signals match this filter.</i>"
    lines = [head, ""]
    for s in sigs:
        arrow = "🟢▲" if s.direction == "long" else "🔴▼"
        state = "READY" if s.entry_ok else "watch"
        strat = _STRAT_LABEL.get(s.strategy, s.strategy.upper())
        lines.append(
            f"{arrow} <b>{s.underlying}</b> {s.direction.upper()} · {strat} · <i>{state}</i>\n"
            f"   entry {_fmt_usd(s.entry)} · stop {_fmt_usd(s.stop_loss)} · tgt {_fmt_usd(s.take_profit)}"
        )
    return "\n".join(lines)


def build_positions_text(status: str) -> str:
    from app.services import paper_store
    ps = paper_store.list_positions()
    open_p = [p for p in ps if p.status.value in ("open", "partially_closed")]
    closed_p = [p for p in ps if p.status.value == "closed"]
    sel = open_p if status == "open" else closed_p if status == "closed" else (open_p + closed_p)
    sel = sel[:20]
    head = f"<b>📋 Positions</b> · {status} · open {len(open_p)} / closed {len(closed_p)}"
    if not sel:
        return head + "\n\n<i>No positions.</i>"
    lines = [head, ""]
    for p in sel:
        d = p.sized_trade.structure.direction.value if p.sized_trade and p.sized_trade.structure else "?"
        arrow = "▲" if d == "long" else "▼"
        mode = "PAPER" if p.is_paper else "LIVE"
        if p.status.value == "closed":
            pnl = _fmt_signed(p.realized_pnl_usd) if p.realized_pnl_usd is not None else "—"
            lines.append(f"{arrow} <b>{p.underlying}</b> {mode} · CLOSED · {pnl}")
        else:
            lines.append(f"{arrow} <b>{p.underlying}</b> {mode} · OPEN · entry {_fmt_usd(p.entry_spot_price)}")
    return "\n".join(lines)


def build_pnl_text() -> str:
    from app.services import paper_store
    ps = paper_store.list_positions()
    open_p = [p for p in ps if p.status.value in ("open", "partially_closed")]
    closed_p = [p for p in ps if p.status.value == "closed"]
    realized = sum((p.realized_pnl_usd or 0.0) for p in closed_p)
    wins = sum(1 for p in closed_p if (p.realized_pnl_usd or 0.0) > 0)
    losses = sum(1 for p in closed_p if (p.realized_pnl_usd or 0.0) < 0)
    wr = (wins / max(1, wins + losses)) * 100
    return (
        "<b>💰 Portfolio P&L</b>\n\n"
        f"Open positions: <b>{len(open_p)}</b>\n"
        f"Closed: <b>{len(closed_p)}</b>\n"
        f"Realized P&L: <b>{_fmt_signed(realized)}</b>\n"
        f"Win / Loss: <b>{wins} / {losses}</b> ({wr:.0f}% win)"
    )


_HELP = (
    "<b>🤖 Sterling Bot</b>\n\n"
    "<b>📈 Crypto</b>\n"
    "/signals — scalping signals (filter by strategy / ready)\n"
    "/positions — open & closed positions\n"
    "/pnl — portfolio P&L summary\n"
    "/alerts — toggle signal push alerts\n\n"
    "<b>🇮🇳 Kite</b>\n"
    "/kite — Kite desk: signals, positions, P&L, scan, auto-trade, orders\n\n"
    "/help — this message"
)

_TOP_MENU = "<b>🤖 Sterling</b>\nChoose a desk:"


def _top_menu_kb() -> dict:
    return {"inline_keyboard": [[_btn("📈 Crypto", "menu_crypto"), _btn("🇮🇳 Kite", "menu_kite")]]}


# ── Update dispatch ───────────────────────────────────────────────────────────
async def _handle_message(chat_id: str, text: str) -> None:
    cmd = text.strip().split()[0].lower().lstrip("/")
    cmd = cmd.split("@")[0]  # strip @botname
    if cmd == "start":
        await _send(_TOP_MENU, chat_id, _top_menu_kb())
    elif cmd == "help":
        await _send(_HELP, chat_id)
    elif cmd in ("kite", "k"):
        from app.services.notifications import telegram_kite
        await telegram_kite.handle_kite_command(chat_id)
    elif cmd == "signals":
        scan = await _scan()
        await _send(build_signals_text(scan, "all", True), chat_id, _signals_kb("all", True))
    elif cmd == "positions":
        await _send(build_positions_text("all"), chat_id, _positions_kb("all"))
    elif cmd == "pnl":
        await _send(build_pnl_text(), chat_id, _positions_kb("all"))
    elif cmd == "alerts":
        global alerts_enabled
        alerts_enabled = not alerts_enabled
        await _send(f"🔔 Signal alerts <b>{'ON' if alerts_enabled else 'OFF'}</b>.", chat_id)
    else:
        await _send(_HELP, chat_id)


async def _handle_callback(chat_id: str, message_id: int, cb_id: str, data: str) -> None:
    kind = data.split("|")[0]
    # Kite desk owns the `k*` callback namespace + the "Kite" top-menu button.
    if kind.startswith("k") or data == "menu_kite":
        from app.services.notifications import telegram_kite
        await telegram_kite.handle_kite_callback(
            chat_id, message_id, cb_id, "kmenu" if data == "menu_kite" else data)
        return
    await _answer_cb(cb_id)
    parts = data.split("|")
    if kind == "menu_crypto":
        scan = await _scan()
        await _edit(chat_id, message_id, build_signals_text(scan, "all", True), _signals_kb("all", True))
    elif kind == "sig":
        strategy = parts[1] if len(parts) > 1 else "all"
        ready_only = bool(int(parts[2])) if len(parts) > 2 else True
        scan = await _scan()
        await _edit(chat_id, message_id, build_signals_text(scan, strategy, ready_only),
                    _signals_kb(strategy, ready_only))
    elif kind == "pos":
        status = parts[1] if len(parts) > 1 else "all"
        await _edit(chat_id, message_id, build_positions_text(status), _positions_kb(status))
    elif kind == "pnl":
        await _edit(chat_id, message_id, build_pnl_text(), _positions_kb("all"))


async def _handle_update(update: dict) -> None:
    chat_id_cfg = str(_tg.TELEGRAM_CHAT_ID or "")
    if "message" in update:
        msg = update["message"]
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if chat_id_cfg and chat_id != chat_id_cfg:
            return  # only serve the configured chat
        text = msg.get("text") or ""
        if text:
            await _handle_message(chat_id, text)
    elif "callback_query" in update:
        cb = update["callback_query"]
        chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
        if chat_id_cfg and chat_id != chat_id_cfg:
            await _answer_cb(cb.get("id", ""))
            return
        await _handle_callback(chat_id, cb["message"]["message_id"], cb.get("id", ""), cb.get("data", ""))


# ── Signal-detection push alerts ──────────────────────────────────────────────
async def push_signal_alerts() -> None:
    """Scan once and push any NEW ready (entry_ok, long/short) signals. De-duped per
    symbol+strategy+direction so a standing setup isn't re-pushed every cycle."""
    if not (alerts_enabled and _tg.TELEGRAM_TOKEN and _tg.TELEGRAM_CHAT_ID):
        return
    try:
        scan = await _scan()
    except Exception as exc:
        log.debug("signal alert scan failed: %s", exc)
        return
    ready = [s for s in scan.signals if s.entry_ok and s.direction in ("long", "short")]
    live_keys = {f"{s.underlying}|{s.strategy}|{s.direction}" for s in ready}
    # Drop dedup entries whose setup is no longer present, so it can re-alert later.
    _alerted.intersection_update(live_keys)
    fresh = [s for s in ready if f"{s.underlying}|{s.strategy}|{s.direction}" not in _alerted]
    for s in fresh:
        _alerted.add(f"{s.underlying}|{s.strategy}|{s.direction}")
        arrow = "🟢▲ LONG" if s.direction == "long" else "🔴▼ SHORT"
        strat = _STRAT_LABEL.get(s.strategy, s.strategy.upper())
        await _send(
            f"<b>📡 New signal · {s.underlying}</b>\n"
            f"{arrow} · {strat}\n"
            f"entry {_fmt_usd(s.entry)} · stop {_fmt_usd(s.stop_loss)} · tgt {_fmt_usd(s.take_profit)}",
            str(_tg.TELEGRAM_CHAT_ID),
        )


# ── Long-poll loop ────────────────────────────────────────────────────────────
async def poll_loop() -> None:
    """Long-poll getUpdates and dispatch. Safe to run forever; backs off on error."""
    offset = 0
    log.info("Telegram bot poll loop started")
    while True:
        if not _tg.TELEGRAM_TOKEN:
            await asyncio.sleep(15)
            continue
        try:
            resp = await _api("getUpdates", {"offset": offset, "timeout": 30}, timeout=40)
            for upd in resp.get("result", []):
                offset = max(offset, upd.get("update_id", 0) + 1)
                try:
                    await _handle_update(upd)
                except Exception as exc:
                    log.warning("telegram update handler error: %s", exc)
        except Exception as exc:
            log.debug("telegram getUpdates error: %s", exc)
            await asyncio.sleep(5)
