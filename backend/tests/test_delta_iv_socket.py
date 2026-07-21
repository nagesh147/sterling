import asyncio
import datetime as dt
import time as _time

from app.services.delta_iv_socket import (
    DeltaIVManager,
    ParsedSym,
    _dte,
    _parse_symbol,
    _subs_from_products,
    iv_manager,
)

SAMPLE = {
    "type": "mark_price",
    "symbol": "MARK:C-BTC-105000-270625",
    "price": "3910.088012",
    "implied_volatility": "0.6523",
    "bid_iv": "0.6480",
    "ask_iv": "0.6560",
    "best_bid": "3890.00",
    "best_ask": "3930.00",
    "delta": "0.42",
    "gamma": "0.0003",
    "theta": "-45.20",
    "vega": "180.50",
    "rho": "12.30",
    "timestamp": 1671867039712836,
}


def test_parse_symbol_call_and_put():
    assert _parse_symbol("C-BTC-105000-270625") == ParsedSym("call", "BTC", 105000.0, "270625")
    assert _parse_symbol("P-ETH-3200-280625") == ParsedSym("put", "ETH", 3200.0, "280625")
    assert _parse_symbol("MARK:C-BTC-105000-270625") == ParsedSym("call", "BTC", 105000.0, "270625")


def test_parse_symbol_rejects_bad():
    assert _parse_symbol("BTCUSD") is None
    assert _parse_symbol("X-BTC-100-270625") is None
    assert _parse_symbol("") is None


def test_dte_ddmmyy():
    ref = dt.date(2025, 6, 20)
    assert _dte("270625", today=ref) == 7
    assert _dte("200625", today=ref) == 0
    assert _dte("130625", today=ref) == -7


def test_handle_message_stores_latest_tick():
    manager = DeltaIVManager(today=dt.date(2025, 6, 20))
    manager._handle_message(SAMPLE)
    tick = manager.get("C-BTC-105000-270625")
    assert tick is not None
    assert tick.underlying == "BTC" and tick.option_type == "call" and tick.strike == 105000.0
    assert tick.mark_iv == 0.6523 and tick.bid_iv == 0.6480 and tick.ask_iv == 0.6560
    assert tick.delta == 0.42 and tick.theta == -45.20 and tick.vega == 180.50
    assert tick.ts_exchange == 1671867039712836 / 1e6
    assert manager.last_update_ts("BTC") == tick.ts_local


def test_handle_message_ignores_non_markprice_and_garbage():
    manager = DeltaIVManager()
    manager._handle_message({"type": "l2_orderbook", "symbol": "BTCUSD"})
    manager._handle_message({"type": "mark_price", "symbol": "NONSENSE"})
    assert manager.get("BTCUSD") is None
    assert manager.chain("BTC") == []


def _mk(manager, symbol, iv):
    message = dict(SAMPLE)
    message["symbol"] = symbol
    message["implied_volatility"] = str(iv)
    manager._handle_message(message)


def test_atm_iv_picks_nearest_expiry_then_strike():
    manager = DeltaIVManager(today=dt.date(2025, 6, 20))
    _mk(manager, "C-BTC-100000-270625", 0.50)
    _mk(manager, "C-BTC-110000-270625", 0.70)
    _mk(manager, "C-BTC-100000-040725", 0.99)
    assert manager.atm_iv("BTC", dte=7, spot=101000) == 0.50
    assert manager.atm_iv("BTC", dte=13, spot=100000) == 0.99
    assert manager.atm_iv("ETH", dte=7, spot=3000) is None


def test_is_fresh():
    manager = DeltaIVManager(today=dt.date(2025, 6, 20))
    assert manager.is_fresh("BTC") is False
    _mk(manager, "C-BTC-100000-270625", 0.50)
    assert manager.is_fresh("BTC", max_age_s=10) is True
    manager._last_update["BTC"] = _time.time() - 100
    assert manager.is_fresh("BTC", max_age_s=10) is False


def test_subs_from_products_filters_dte_and_dedups():
    today = dt.date(2025, 6, 20)
    products = [
        {"symbol": "C-BTC-100000-270625"},
        {"symbol": "P-BTC-90000-270625"},
        {"symbol": "C-ETH-3000-040725"},
        {"symbol": "C-BTC-100000-200825"},
        {"symbol": "BTCUSD"},
    ]
    subscriptions = _subs_from_products(products, max_dte=45, today=today)
    assert subscriptions == ["BTC-270625", "ETH-040725"]


def test_singleton_exists_and_not_started_on_import():
    assert isinstance(iv_manager, DeltaIVManager)
    assert iv_manager._running is False


def test_start_stop_toggles_running():
    async def run():
        manager = DeltaIVManager()

        async def _noop():
            while manager._running:
                await asyncio.sleep(0.01)

        manager._listen = _noop
        manager.start()
        assert manager._running is True
        await asyncio.sleep(0.02)
        manager.stop()
        assert manager._running is False

    asyncio.run(run())


def test_application_lifespan_is_an_async_context_manager():
    """Verify startup exposes the lifecycle contract without inspecting source text."""
    import main as main_mod

    context = main_mod.lifespan(main_mod.create_app())
    assert hasattr(context, "__aenter__")
    assert hasattr(context, "__aexit__")
