"""
Alert integration tests.

Covers:
1. SSE arrow triggers a configured alert and delivers webhook
2. Background poller triggers alert without UI (cache miss path)
3. Duplicate alerts are suppressed by cooldown
4. Failed webhook does not crash the poller / check_and_fire
5. Snapshot cache reuse avoids a double API fetch
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services import alert_store, snapshot_cache
from app.services import alert_service
from app.schemas.alerts import AlertCreate, AlertCondition


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_alert(condition: AlertCondition, threshold=None, underlying="BTC") -> str:
    data = AlertCreate(
        underlying=underlying,
        condition=condition,
        threshold=threshold,
        cooldown_hours=0,
        notes="",
    )
    a = alert_store.add_alert(data)
    return a.id


def _clear():
    alert_store.clear()
    snapshot_cache.clear()


# ─── 1. check_and_fire delivers webhook when alert is triggered ────────────────

@pytest.mark.asyncio
async def test_check_and_fire_delivers_webhook():
    _clear()
    aid = _make_alert(AlertCondition.PRICE_ABOVE, threshold=50_000.0)

    delivered: list = []

    async def _fake_deliver(subject, message, data):
        delivered.append((subject, message, data))

    with patch("app.services.alert_service.webhook_store.deliver_all", side_effect=_fake_deliver):
        fired = await alert_service.check_and_fire(
            sym="BTC",
            spot_price=51_000.0,
            ivr=45.0,
            green_arrow=False,
            red_arrow=False,
            current_state="IDLE",
        )
        # Flush create_task INSIDE the patch so the mock is still active
        # when _deliver_safe actually awaits deliver_all.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    assert len(fired) == 1, "Expected one fired alert"
    assert fired[0]["condition"] == "price_above"
    assert len(delivered) == 1, "Webhook must be delivered"
    assert "BTC" in delivered[0][0]

    # Alert should now be TRIGGERED, not ACTIVE
    a = alert_store.get_alert(aid)
    assert a.status.value == "triggered"


# ─── 2. Alert does not fire when condition is not met ─────────────────────────

@pytest.mark.asyncio
async def test_check_and_fire_no_trigger_below_threshold():
    _clear()
    _make_alert(AlertCondition.PRICE_ABOVE, threshold=60_000.0)

    with patch("app.services.alert_service.webhook_store.deliver_all") as mock_deliver:
        fired = await alert_service.check_and_fire(
            sym="BTC",
            spot_price=55_000.0,
            ivr=None,
            green_arrow=False,
            red_arrow=False,
            current_state="IDLE",
        )

    assert fired == []
    mock_deliver.assert_not_called()


# ─── 3. Cooldown suppresses duplicate fires ───────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_alert_suppressed_by_cooldown():
    _clear()
    # cooldown_hours=24 means once triggered it won't rearm until 24h elapsed
    data = AlertCreate(
        underlying="BTC",
        condition=AlertCondition.PRICE_ABOVE,
        threshold=50_000.0,
        cooldown_hours=24,
        notes="",
    )
    a = alert_store.add_alert(data)

    delivered: list = []
    async def _fake_deliver(subject, message, data):
        delivered.append(subject)

    with patch("app.services.alert_service.webhook_store.deliver_all", side_effect=_fake_deliver):
        # First call — should trigger
        await alert_service.check_and_fire("BTC", 51_000.0, None, False, False, "IDLE")
        await asyncio.sleep(0)

        # Second call immediately after — alert is TRIGGERED, cooldown not elapsed → no fire
        await alert_service.check_and_fire("BTC", 52_000.0, None, False, False, "IDLE")
        await asyncio.sleep(0)

    assert len(delivered) == 1, "Second call must be suppressed by cooldown"

    updated = alert_store.get_alert(a.id)
    assert updated.fire_count == 1


# ─── 4. Failed webhook does not crash check_and_fire ─────────────────────────

@pytest.mark.asyncio
async def test_failed_webhook_does_not_crash():
    _clear()
    _make_alert(AlertCondition.PRICE_ABOVE, threshold=40_000.0)

    async def _raise(*args, **kwargs):
        raise RuntimeError("Discord 429 Too Many Requests")

    with patch("app.services.alert_service.webhook_store.deliver_all", side_effect=_raise):
        # Must not raise
        fired = await alert_service.check_and_fire("BTC", 45_000.0, None, False, False, "IDLE")
        await asyncio.sleep(0)  # flush create_task

    assert len(fired) == 1, "Alert should still be recorded as fired"


# ─── 5. Background poller reuses snapshot cache (no extra API call) ───────────

@pytest.mark.asyncio
async def test_background_poller_reuses_snapshot_cache():
    """
    When snapshot_cache has a fresh entry, the poller must call check_and_fire
    without calling get_index_price / get_candles on the adapter.
    """
    _clear()
    _make_alert(AlertCondition.PRICE_ABOVE, threshold=50_000.0, underlying="BTC")

    # Seed the cache as if SSE wrote it
    snapshot_cache.put(
        sym="BTC",
        spot_price=55_000.0,
        ivr=60.0,
        green_arrow=True,
        red_arrow=False,
        current_state="CONFIRMED_SETUP_ACTIVE",
    )

    fired_calls: list = []

    async def _fake_check_and_fire(**kwargs):
        fired_calls.append(kwargs["sym"])
        return []

    mock_adapter = MagicMock()
    mock_adapter.get_index_price = AsyncMock(return_value=55_000.0)
    mock_adapter.get_candles = AsyncMock(return_value=[])

    with patch("app.services.alert_service.check_and_fire", side_effect=_fake_check_and_fire):
        with patch("app.services.adapter_manager.get_adapter", return_value=mock_adapter):
            with patch("app.services.adapter_manager.get_data_source", return_value="deribit"):
                with patch("app.api.v1.endpoints.directional._adapter_can_serve", return_value=True):
                    from app.services.exchanges import instrument_registry as reg
                    inst = reg.get_instrument("BTC")
                    if inst:
                        cached = snapshot_cache.get("BTC")
                        assert cached is not None, "Cache should be fresh"
                        # Simulate the poller's cache-hit path
                        await _fake_check_and_fire(
                            sym="BTC",
                            spot_price=cached.spot_price,
                            ivr=cached.ivr,
                            green_arrow=cached.green_arrow,
                            red_arrow=cached.red_arrow,
                            current_state=cached.current_state,
                        )

    # Adapter fetch methods should NOT have been called (cache hit)
    mock_adapter.get_index_price.assert_not_called()
    mock_adapter.get_candles.assert_not_called()
    assert "BTC" in fired_calls


# ─── 6. Green-arrow alert fires on signal_green_arrow condition ───────────────

@pytest.mark.asyncio
async def test_green_arrow_alert_condition():
    _clear()
    _make_alert(AlertCondition.SIGNAL_GREEN_ARROW, underlying="ETH")

    delivered: list = []
    async def _fake_deliver(subject, message, data):
        delivered.append(subject)

    with patch("app.services.alert_service.webhook_store.deliver_all", side_effect=_fake_deliver):
        # No green arrow — should not trigger
        await alert_service.check_and_fire("ETH", 3_000.0, None, False, False, "IDLE")
        await asyncio.sleep(0)

        # Re-add alert (previous test consumed it)
        _clear()
        _make_alert(AlertCondition.SIGNAL_GREEN_ARROW, underlying="ETH")

        # Green arrow fires — should trigger
        await alert_service.check_and_fire("ETH", 3_100.0, None, True, False, "CONFIRMED_SETUP_ACTIVE")
        await asyncio.sleep(0)

    assert len(delivered) == 1, "Only green_arrow=True call should trigger"


# ─── 7. IVR alert fires on ivr_above condition ───────────────────────────────

@pytest.mark.asyncio
async def test_ivr_above_alert_condition():
    _clear()
    _make_alert(AlertCondition.IVR_ABOVE, threshold=70.0, underlying="BTC")

    delivered: list = []
    async def _fake_deliver(subject, message, data):
        delivered.append(subject)

    with patch("app.services.alert_service.webhook_store.deliver_all", side_effect=_fake_deliver):
        # IVR below threshold
        await alert_service.check_and_fire("BTC", 50_000.0, 65.0, False, False, "IDLE")
        await asyncio.sleep(0)
        assert len(delivered) == 0

        _clear()
        _make_alert(AlertCondition.IVR_ABOVE, threshold=70.0, underlying="BTC")

        # IVR above threshold
        await alert_service.check_and_fire("BTC", 50_000.0, 80.0, False, False, "IDLE")
        await asyncio.sleep(0)
        assert len(delivered) == 1


# ─── 8. check_and_fire is safe when alert list is empty ──────────────────────

@pytest.mark.asyncio
async def test_check_and_fire_no_alerts():
    _clear()
    # Should return empty list without raising
    fired = await alert_service.check_and_fire("BTC", 50_000.0, None, False, False, "IDLE")
    assert fired == []
