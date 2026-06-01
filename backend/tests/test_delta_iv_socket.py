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


# --- Task 1: parser + DTE ---
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


# --- Task 2: _handle_message ---
def test_handle_message_stores_latest_tick():
    m = DeltaIVManager(today=dt.date(2025, 6, 20))
    m._handle_message(SAMPLE)
    t = m.get("C-BTC-105000-270625")
    assert t is not None
    assert t.underlying == "BTC" and t.option_type == "call" and t.strike == 105000.0
    assert t.mark_iv == 0.6523 and t.bid_iv == 0.6480 and t.ask_iv == 0.6560
    assert t.delta == 0.42 and t.theta == -45.20 and t.vega == 180.50
    assert t.ts_exchange == 1671867039712836 / 1e6
    assert m.last_update_ts("BTC") == t.ts_local


def test_handle_message_ignores_non_markprice_and_garbage():
    m = DeltaIVManager()
    m._handle_message({"type": "l2_orderbook", "symbol": "BTCUSD"})
    m._handle_message({"type": "mark_price", "symbol": "NONSENSE"})
    assert m.get("BTCUSD") is None
    assert m.chain("BTC") == []


# --- Task 3: atm_iv + is_fresh ---
def _mk(m, sym, iv):
    msg = dict(SAMPLE)
    msg["symbol"] = sym
    msg["implied_volatility"] = str(iv)
    m._handle_message(msg)


def test_atm_iv_picks_nearest_expiry_then_strike():
    m = DeltaIVManager(today=dt.date(2025, 6, 20))
    _mk(m, "C-BTC-100000-270625", 0.50)   # dte 7, strike 100k
    _mk(m, "C-BTC-110000-270625", 0.70)   # dte 7, strike 110k
    _mk(m, "C-BTC-100000-040725", 0.99)   # dte 14, strike 100k
    assert m.atm_iv("BTC", dte=7, spot=101000) == 0.50
    assert m.atm_iv("BTC", dte=13, spot=100000) == 0.99
    assert m.atm_iv("ETH", dte=7, spot=3000) is None


def test_is_fresh():
    m = DeltaIVManager(today=dt.date(2025, 6, 20))
    assert m.is_fresh("BTC") is False
    _mk(m, "C-BTC-100000-270625", 0.50)
    assert m.is_fresh("BTC", max_age_s=10) is True
    m._last_update["BTC"] = _time.time() - 100
    assert m.is_fresh("BTC", max_age_s=10) is False


# --- Task 4: discovery filter ---
def test_subs_from_products_filters_dte_and_dedups():
    today = dt.date(2025, 6, 20)
    products = [
        {"symbol": "C-BTC-100000-270625"},   # dte 7   keep
        {"symbol": "P-BTC-90000-270625"},    # dte 7   keep -> dedup to BTC-270625
        {"symbol": "C-ETH-3000-040725"},     # dte 14  keep
        {"symbol": "C-BTC-100000-200825"},   # dte 61  drop (>45)
        {"symbol": "BTCUSD"},                # not an option  drop
    ]
    subs = _subs_from_products(products, max_dte=45, today=today)
    assert subs == ["BTC-270625", "ETH-040725"]


# --- Task 5: singleton + lifecycle ---
def test_singleton_exists_and_not_started_on_import():
    assert isinstance(iv_manager, DeltaIVManager)
    assert iv_manager._running is False   # import must NOT open a socket


def test_start_stop_toggles_running():
    async def run():
        m = DeltaIVManager()

        async def _noop():
            while m._running:
                await asyncio.sleep(0.01)

        m._listen = _noop
        m.start()
        assert m._running is True
        await asyncio.sleep(0.02)
        m.stop()
        assert m._running is False

    asyncio.run(run())


# --- Task 6: gated lifespan wiring ---
def test_lifespan_starts_iv_stream_only_when_env_set():
    import inspect
    import main as main_mod

    src = inspect.getsource(main_mod.lifespan)
    assert "STERLING_IV_STREAM" in src
    assert "iv_manager.start()" in src
