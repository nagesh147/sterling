"""KiteTicker binary protocol decode + subscription/callback behaviour."""
import struct

from app.services.exchanges.kite import constants as K
from app.services.exchanges.kite.ticker import (
    KiteTicker, msg_mode, msg_subscribe, parse_binary, split_packets,
)

# NSE equity token (segment 1 → divisor 100); NSE index token (segment 9)
EQ_TOKEN = 408065        # 408065 & 0xFF == 1
IDX_TOKEN = 256265       # 256265 & 0xFF == 9 (e.g. NIFTY 50)


def _frame(*packets: bytes) -> bytes:
    out = struct.pack(">H", len(packets))
    for p in packets:
        out += struct.pack(">H", len(p)) + p
    return out


def _ltp(token, price_int):
    return struct.pack(">II", token, price_int)


def _quote(token, ltp, ltq, atp, vol, tbq, tsq, o, h, l, c):
    return struct.pack(">11I", token, ltp, ltq, atp, vol, tbq, tsq, o, h, l, c)


def _full(token):
    base = _quote(token, 150050, 10, 150000, 99999, 500, 400, 149000, 151000, 148000, 149500)
    extra = struct.pack(">5I", 123456, 7777, 8000, 6000, 123457)  # ltt, oi, oi_hi, oi_lo, exch_ts
    depth = b""
    for i in range(10):
        depth += struct.pack(">IIHH", 100 + i, 150000 + i * 10, 3 + i, 0)  # qty, price, orders, pad
    return base + extra + depth


def _index_quote(token, ltp, h, l, o, c, change):
    return struct.pack(">7i", token, ltp, h, l, o, c, change)


def test_split_packets_counts_and_slices():
    frame = _frame(_ltp(EQ_TOKEN, 150050), _ltp(5633, 240000))
    packets = split_packets(frame)
    assert len(packets) == 2
    assert len(packets[0]) == 8


def test_parse_ltp_packet():
    ticks = parse_binary(_frame(_ltp(EQ_TOKEN, 150050)))
    assert len(ticks) == 1
    t = ticks[0]
    assert t["instrument_token"] == EQ_TOKEN
    assert t["mode"] == K.MODE_LTP
    assert t["last_price"] == 1500.5


def test_parse_quote_packet():
    pkt = _quote(EQ_TOKEN, 150050, 10, 150000, 99999, 500, 400, 149000, 151000, 148000, 149500)
    assert len(pkt) == K.PACKET_QUOTE
    t = parse_binary(_frame(pkt))[0]
    assert t["mode"] == K.MODE_QUOTE
    assert t["last_price"] == 1500.5
    assert t["volume_traded"] == 99999
    assert t["ohlc"]["open"] == 1490.0
    assert t["ohlc"]["close"] == 1495.0
    assert t["total_buy_quantity"] == 500


def test_parse_full_packet_with_depth_and_oi():
    pkt = _full(EQ_TOKEN)
    assert len(pkt) == K.PACKET_FULL
    t = parse_binary(_frame(pkt))[0]
    assert t["mode"] == K.MODE_FULL
    assert t["oi"] == 7777
    assert len(t["depth"]["buy"]) == 5
    assert len(t["depth"]["sell"]) == 5
    assert t["depth"]["buy"][0]["quantity"] == 100
    assert t["depth"]["buy"][0]["price"] == 1500.0


def test_parse_index_packet():
    pkt = _index_quote(IDX_TOKEN, 2500000, 2510000, 2490000, 2495000, 2498000, 2000)
    assert len(pkt) == K.PACKET_INDEX_QUOTE
    t = parse_binary(_frame(pkt))[0]
    assert t["instrument_token"] == IDX_TOKEN
    assert t["tradable"] is False
    assert t["last_price"] == 25000.0
    assert t["ohlc"]["high"] == 25100.0


def test_subscribe_message_builders():
    assert '"a": "subscribe"' in msg_subscribe([1, 2])
    m = msg_mode("full", [1, 2])
    assert '"full"' in m and "[1, 2]" in m


async def test_ticker_subscribe_tracks_state_when_disconnected():
    t = KiteTicker("ak", "tok")
    await t.subscribe([111, 222], mode="full")
    assert t.status()["subscribed"] == [111, 222]
    assert t.connected is False


async def test_on_message_updates_cache_and_invokes_callback():
    received = []

    async def cb(ticks):
        received.extend(ticks)

    t = KiteTicker("ak", "tok", on_ticks=cb)
    await t._on_message(_frame(_ltp(EQ_TOKEN, 150050)))
    assert t.snapshot()[0]["last_price"] == 1500.5
    assert received and received[0]["instrument_token"] == EQ_TOKEN
    # 1-byte heartbeat is ignored
    await t._on_message(b"\n")
    assert len(received) == 1


async def test_text_order_update_invokes_order_callback():
    import json
    orders = []

    async def on_order(payload):
        orders.append(payload)

    t = KiteTicker("ak", "tok", on_order_update=on_order)
    frame = json.dumps({"type": "order", "data": {"order_id": "ORD1", "status": "COMPLETE"}})
    await t._on_message(frame)
    assert orders and orders[0]["order_id"] == "ORD1"
    assert orders[0]["status"] == "COMPLETE"


async def test_text_non_order_frames_ignored():
    orders = []

    async def on_order(payload):
        orders.append(payload)

    t = KiteTicker("ak", "tok", on_order_update=on_order)
    import json
    await t._on_message(json.dumps({"type": "message", "data": "market open"}))
    await t._on_message("not json at all")
    assert orders == []


# ─── Liveness: a dead stream must not report itself healthy ──────────────────
#
# `_active` is set by `start()` and cleared only by `stop()` and cancellation, so
# a `_run()` task that dies any other way leaves the flag set. `is_active` used
# to return that flag directly, and `ticker_manager.ensure()` short-circuits on
# it — so a dead ticker was handed back forever, never restarted, while
# `/ticker/status` reported `active: true`.
#
# Observed live: `{"active": true, "connected": false, "subscribed": [...397
# tokens]}`. Every price in the app had silently fallen back to the 30-second
# REST heartbeat, which is why it looked like "values are not updating" rather
# than like a broken feed.

import asyncio

import pytest


def _ticker() -> KiteTicker:
    return KiteTicker(api_key="k", access_token="t", on_ticks=lambda *_: None)


def test_is_active_is_false_before_start():
    assert _ticker().is_active is False


@pytest.mark.asyncio
async def test_a_dead_task_is_not_active():
    t = _ticker()
    t._active = True
    # A task that has finished, standing in for `_run()` having died.
    t._task = asyncio.create_task(asyncio.sleep(0))
    await asyncio.sleep(0.01)
    assert t._task.done()

    assert t.is_active is False, "a finished task must not read as active"
    assert t.died is True, "and must be identifiable as restartable"


@pytest.mark.asyncio
async def test_a_running_task_is_active():
    t = _ticker()
    t._active = True
    t._task = asyncio.create_task(asyncio.sleep(5))
    try:
        assert t.is_active is True
        assert t.died is False, "a running stream is not a dead one"
    finally:
        t._task.cancel()


@pytest.mark.asyncio
async def test_a_stopped_ticker_is_not_reported_as_died():
    # `stop()` clears the flag, so a deliberate shutdown must not look like a
    # crash — otherwise `ensure()` would fight the operator and restart it.
    t = _ticker()
    t._active = False
    t._task = asyncio.create_task(asyncio.sleep(0))
    await asyncio.sleep(0.01)
    assert t.is_active is False
    assert t.died is False


@pytest.mark.asyncio
async def test_status_distinguishes_started_from_running():
    t = _ticker()
    t._active = True
    t._task = asyncio.create_task(asyncio.sleep(0))
    await asyncio.sleep(0.01)

    s = t.status()
    assert s["started"] is True, "the raw flag stays visible"
    assert s["active"] is False, "but `active` means running"
    assert s["died"] is True
    # `last_error` is part of the contract even when nothing has failed yet, so a
    # caller can always ask why rather than only whether.
    assert "last_error" in s


@pytest.mark.asyncio
async def test_start_revives_a_finished_task_and_keeps_subscriptions():
    # The subscription list is why `ensure()` restarts the existing ticker rather
    # than building a fresh one: `_resubscribe_all()` replays it on connect, and a
    # new ticker would come up subscribed to nothing while every caller sat
    # waiting for ticks that were never coming.
    t = _ticker()
    t._subscribed = {123, 456}
    t._active = True
    t._task = asyncio.create_task(asyncio.sleep(0))
    await asyncio.sleep(0.01)
    assert t.died is True

    await t.start()
    try:
        assert t.is_active is True, "start() revives a finished task"
        assert t._subscribed == {123, 456}, "and the subscription list survives"
    finally:
        await t.stop()
