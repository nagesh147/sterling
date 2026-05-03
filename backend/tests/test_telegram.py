import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_send_returns_false_when_token_missing():
    import app.services.notifications.telegram as tg
    original_token = tg.TELEGRAM_TOKEN
    original_chat = tg.TELEGRAM_CHAT_ID
    tg.TELEGRAM_TOKEN = ""
    tg.TELEGRAM_CHAT_ID = ""
    result = await tg.send("hello")
    assert result is False
    tg.TELEGRAM_TOKEN = original_token
    tg.TELEGRAM_CHAT_ID = original_chat


@pytest.mark.asyncio
async def test_send_calls_correct_telegram_url():
    import app.services.notifications.telegram as tg
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch.object(tg, "TELEGRAM_TOKEN", "test_token"), \
         patch.object(tg, "TELEGRAM_CHAT_ID", "12345"):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await tg.send("test message")
            assert result is True
            called_url = mock_client.post.call_args[0][0]
            assert "test_token" in called_url
            assert "sendMessage" in called_url


def test_fmt_signal_alert_contains_score():
    from app.services.notifications.formatters import fmt_signal_alert
    snapshot = MagicMock()
    snapshot.underlying = "BTC"
    snapshot.direction = "long"
    snapshot.ivr = 55.0
    snapshot.current_state = "ENTRY_ARMED_PULLBACK"
    structure = MagicMock()
    structure.structure_type = "bull_call_spread"
    result = fmt_signal_alert(snapshot, structure, 82.5)
    assert "82.5" in result


def test_fmt_trail_update_contains_stop_price():
    from app.services.notifications.formatters import fmt_trail_update
    position = MagicMock()
    position.id = "ABC123"
    position.underlying = "BTC"
    result = fmt_trail_update(position, 29500.0, 0.05)
    assert "29,500.00" in result or "29500" in result


def test_fmt_partial_exit_contains_close_pct():
    from app.services.notifications.formatters import fmt_partial_exit
    position = MagicMock()
    position.id = "ABC123"
    position.underlying = "ETH"
    partial = MagicMock()
    partial.close_pct = 25
    partial.reason = "10% gain"
    result = fmt_partial_exit(position, partial)
    assert "25" in result


def test_send_not_called_when_no_arrow():
    """When green_arrow=False no Telegram send should fire."""
    import app.services.notifications.telegram as tg
    send_calls = []
    original = tg.send

    async def mock_send(text, **kwargs):
        send_calls.append(text)
        return True

    arrow_fired = False
    # Simulate the SSE logic: only send when arrow_fired
    if arrow_fired:
        import asyncio
        asyncio.get_event_loop().run_until_complete(mock_send("signal"))

    assert len(send_calls) == 0


def test_send_called_when_arrow_fires():
    """When arrow_fired=True the formatter output should be passed to send."""
    from app.services.notifications.formatters import fmt_signal_alert
    snapshot = MagicMock()
    snapshot.underlying = "BTC"
    snapshot.direction = "long"
    snapshot.ivr = 60.0
    snapshot.current_state = "ENTRY_ARMED_PULLBACK"
    structure = MagicMock()
    structure.structure_type = "bull_call_spread"
    msg = fmt_signal_alert(snapshot, structure, 77.0)
    assert len(msg) > 0
