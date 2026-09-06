"""Telegram Kite desk: text builders, callback separation, and the
two-tap confirm → shared-order-service path. Network TX (_send/_edit) no-ops
without a token, so handlers run safely offline."""
from unittest.mock import AsyncMock, patch

from app.services.notifications import telegram_kite as tk
from app.services.notifications import telegram_bot as tb


def test_signals_text_handles_empty_scan():
    txt = tk.build_kite_signals_text()
    assert "Kite signals" in txt


def test_status_text_reports_mode_and_toggles():
    txt = tk.build_kite_status_text()
    assert "Auto-trade" in txt and "Alerts" in txt


async def test_callbacks_route_to_kite_module():
    """All callbacks are delegated to the Kite command surface.

    Drives `_handle_update`, the actual update-loop entry point. The private
    `_handle_callback` hop this used to call was inlined when the crypto command
    surface was removed — only the Kite namespace is left to route to, so the
    dispatch no longer needs a branch of its own.
    """
    def _cb(data: str) -> dict:
        return {"callback_query": {"id": "cb", "data": data,
                                   "message": {"message_id": 1, "chat": {"id": "1"}}}}

    with patch("app.services.notifications.telegram_kite.handle_kite_callback",
               new=AsyncMock()) as kite_cb:
        await tb._handle_update(_cb("ksig"))
        await tb._handle_update(_cb("menu_kite"))
        await tb._handle_update(_cb("menu_unknown"))
        assert kite_cb.await_count == 3


async def test_order_requires_two_tap_confirm_then_places():
    """Tapping Buy stages a pending order (no placement); only Confirm executes it
    via the shared service."""
    tk._sig_actions.clear()
    tk._pending.clear()
    tk._sig_actions["1"] = {"option_symbol": "NIFTY26JUN25000CE", "exchange": "NFO", "qty": 75}

    placed = AsyncMock(return_value={"status": "ok", "order_id": "X1", "message": "ok"})
    with patch("app.services.kite_engine.service.place_manual_order", new=placed):
        # first tap: stage only — must NOT place yet
        await tk.handle_kite_callback("1", 1, "cb", "kbuy|1")
        assert placed.await_count == 0
        assert len(tk._pending) == 1
        ptok = next(iter(tk._pending))
        # confirm: now it places
        await tk.handle_kite_callback("1", 1, "cb", f"kok|{ptok}")
        assert placed.await_count == 1
        args = placed.await_args.args
        assert "NIFTY26JUN25000CE" in args and "BUY" in args
    # cancel path leaves nothing pending and never places
    tk._pending["zz"] = {"kind": "order", "side": "BUY", "option_symbol": "X", "exchange": "NFO", "qty": 1}
    with patch("app.services.kite_engine.service.place_manual_order", new=AsyncMock()) as p2:
        await tk.handle_kite_callback("1", 1, "cb", "kno|zz")
        assert p2.await_count == 0
        assert "zz" not in tk._pending


async def test_expired_signal_action_does_not_place():
    tk._sig_actions.clear()
    tk._pending.clear()
    with patch("app.services.kite_engine.service.place_manual_order", new=AsyncMock()) as p:
        await tk.handle_kite_callback("1", 1, "cb", "kbuy|999")  # unknown sid
        assert p.await_count == 0
        assert len(tk._pending) == 0
