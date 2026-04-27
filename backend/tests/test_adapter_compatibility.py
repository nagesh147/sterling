"""
Tests for data source × instrument compatibility logic.
Verifies _adapter_can_serve() returns correct results for all combinations.
"""
import pytest
from app.api.v1.endpoints.directional import _adapter_can_serve
from app.services.exchanges.instrument_registry import get_instrument


class TestAdapterCompatibility:
    # ─── Crypto instruments on delta_india ───────────────────────────────────

    def test_btc_available_on_delta_india(self):
        assert _adapter_can_serve(get_instrument("BTC"), "delta_india")

    def test_eth_available_on_delta_india(self):
        assert _adapter_can_serve(get_instrument("ETH"), "delta_india")

    def test_sol_available_on_delta_india(self):
        assert _adapter_can_serve(get_instrument("SOL"), "delta_india")

    def test_xrp_available_on_delta_india(self):
        assert _adapter_can_serve(get_instrument("XRP"), "delta_india")

    # ─── NSE instruments only on zerodha ─────────────────────────────────────

    def test_nifty_only_on_zerodha(self):
        assert _adapter_can_serve(get_instrument("NIFTY"), "zerodha")
        assert not _adapter_can_serve(get_instrument("NIFTY"), "deribit")
        assert not _adapter_can_serve(get_instrument("NIFTY"), "delta_india")
        assert not _adapter_can_serve(get_instrument("NIFTY"), "binance")
        assert not _adapter_can_serve(get_instrument("NIFTY"), "okx")

    def test_banknifty_only_on_zerodha(self):
        assert _adapter_can_serve(get_instrument("BANKNIFTY"), "zerodha")
        assert not _adapter_can_serve(get_instrument("BANKNIFTY"), "deribit")
        assert not _adapter_can_serve(get_instrument("BANKNIFTY"), "delta_india")

    # ─── OKX compatibility ────────────────────────────────────────────────────

    def test_btc_available_on_okx(self):
        assert _adapter_can_serve(get_instrument("BTC"), "okx")

    def test_sol_available_on_okx(self):
        assert _adapter_can_serve(get_instrument("SOL"), "okx")

    # ─── Binance compatibility ────────────────────────────────────────────────

    def test_btc_available_on_binance(self):
        assert _adapter_can_serve(get_instrument("BTC"), "binance")

    def test_nifty_not_on_binance(self):
        assert not _adapter_can_serve(get_instrument("NIFTY"), "binance")

    # ─── Deribit compatibility ────────────────────────────────────────────────

    def test_btc_available_on_deribit(self):
        assert _adapter_can_serve(get_instrument("BTC"), "deribit")

    def test_nifty_not_on_deribit(self):
        assert not _adapter_can_serve(get_instrument("NIFTY"), "deribit")

    # ─── All crypto instruments available on delta_india ─────────────────────

    def test_all_crypto_instruments_on_delta_india(self):
        from app.services.exchanges.instrument_registry import list_instruments
        crypto_insts = [i for i in list_instruments() if i.exchange != "zerodha"]
        for inst in crypto_insts:
            assert _adapter_can_serve(inst, "delta_india"), \
                f"{inst.underlying} (delta_perp_symbol={inst.delta_perp_symbol}) should be served by delta_india"

    # ─── No instrument on both zerodha AND crypto adapters ───────────────────

    def test_no_overlap_zerodha_vs_delta(self):
        from app.services.exchanges.instrument_registry import list_instruments
        for inst in list_instruments():
            on_zerodha = _adapter_can_serve(inst, "zerodha")
            on_delta = _adapter_can_serve(inst, "delta_india")
            assert not (on_zerodha and on_delta), \
                f"{inst.underlying} should not be on both zerodha and delta_india"


class TestDeltaAdapterDataFlow:
    """Tests for Delta India adapter public data methods (mocked HTTP)."""

    @pytest.mark.asyncio
    async def test_get_candles_object_format(self):
        """Delta returns object-format candles: [{time, open, high, low, close, volume}]."""
        from unittest.mock import AsyncMock
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        adapter = DeltaIndiaAdapter()
        adapter._public_get = AsyncMock(return_value={
            "success": True,
            "result": [
                {"time": 1700000000, "open": "43000", "high": "44000",
                 "low": "42000", "close": "43500", "volume": "100"},
                {"time": 1700003600, "open": "43500", "high": "45000",
                 "low": "43000", "close": "44800", "volume": "150"},
            ]
        })
        inst = next(i for i in __import__(
            'app.services.exchanges.instrument_registry', fromlist=['list_instruments']
        ).list_instruments() if i.underlying == "BTC")
        candles = await adapter.get_candles(inst, "1H", limit=200)
        assert len(candles) == 2
        assert candles[0].close == 43500.0
        assert candles[1].close == 44800.0
        assert candles[0].timestamp_ms == 1700000000 * 1000  # seconds → ms

    @pytest.mark.asyncio
    async def test_get_candles_array_format(self):
        """Delta may also return array-format candles: [[ts, o, h, l, c, v]]."""
        from unittest.mock import AsyncMock
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        adapter = DeltaIndiaAdapter()
        adapter._public_get = AsyncMock(return_value={
            "success": True,
            "result": [
                [1700000000, "43000", "44000", "42000", "43500", "100"],
                [1700003600, "43500", "45000", "43000", "44800", "150"],
            ]
        })
        from app.services.exchanges.instrument_registry import get_instrument
        inst = get_instrument("BTC")
        candles = await adapter.get_candles(inst, "1H", limit=200)
        assert len(candles) == 2
        assert candles[0].open == 43000.0

    @pytest.mark.asyncio
    async def test_get_index_price_spot_price_field(self):
        """Delta ticker uses spot_price for the underlying index price."""
        from unittest.mock import AsyncMock
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        from app.services.exchanges.instrument_registry import get_instrument
        adapter = DeltaIndiaAdapter()
        adapter._public_get = AsyncMock(return_value={
            "success": True, "result": {"spot_price": "43000.5", "mark_price": "43010.0"}
        })
        price = await adapter.get_index_price(get_instrument("BTC"))
        assert price == pytest.approx(43000.5)

    @pytest.mark.asyncio
    async def test_get_index_price_fallback_mark_price(self):
        """Falls back to mark_price when spot_price absent."""
        from unittest.mock import AsyncMock
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        from app.services.exchanges.instrument_registry import get_instrument
        adapter = DeltaIndiaAdapter()
        adapter._public_get = AsyncMock(return_value={
            "success": True, "result": {"mark_price": "43010.0"}
        })
        price = await adapter.get_index_price(get_instrument("BTC"))
        assert price == pytest.approx(43010.0)

    @pytest.mark.asyncio
    async def test_option_chain_greeks_nested(self):
        """Option chain with greeks in nested dict."""
        from unittest.mock import AsyncMock
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        from app.services.exchanges.instrument_registry import get_instrument
        adapter = DeltaIndiaAdapter()
        adapter._public_get = AsyncMock(return_value={
            "success": True,
            "result": [{
                "symbol": "C-BTC-43000-27DEC26",
                "bid": "500", "ask": "520", "mark_price": "510",
                "oi": "200", "volume": "50",
                "greeks": {"delta": "0.45", "iv": "0.65"},
            }]
        })
        chain = await adapter.get_option_chain(get_instrument("BTC"))
        assert len(chain) == 1
        assert chain[0].delta == pytest.approx(0.45)
        assert chain[0].mark_iv == pytest.approx(0.65)
        assert chain[0].option_type == "call"
        assert chain[0].strike == 43000.0

    @pytest.mark.asyncio
    async def test_option_chain_flat_greeks(self):
        """Option chain with greeks directly on item (flat structure)."""
        from unittest.mock import AsyncMock
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        from app.services.exchanges.instrument_registry import get_instrument
        adapter = DeltaIndiaAdapter()
        adapter._public_get = AsyncMock(return_value={
            "success": True,
            "result": [{
                "symbol": "P-ETH-2800-31DEC26",
                "bid": "100", "ask": "110", "mark_price": "105",
                "mark_iv": "0.70", "delta": "-0.38",
                "oi": "150", "volume": "30",
            }]
        })
        chain = await adapter.get_option_chain(get_instrument("ETH"))
        assert len(chain) == 1
        assert chain[0].option_type == "put"
        assert chain[0].delta == pytest.approx(-0.38)
        assert chain[0].mark_iv == pytest.approx(0.70)

    @pytest.mark.asyncio
    async def test_option_chain_fallback_to_tickers(self):
        """When /v2/options/chain fails, falls back to /v2/tickers."""
        from unittest.mock import AsyncMock
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        from app.services.exchanges.instrument_registry import get_instrument
        import httpx

        adapter = DeltaIndiaAdapter()
        call_count = [0]

        async def mock_get(path, params=None):
            call_count[0] += 1
            if "/v2/options/chain" in path:
                raise httpx.HTTPStatusError("404", request=None, response=None)
            # call_options returns one call; put_options returns empty
            params_list = list(params) if isinstance(params, list) else []
            is_put = any("put_options" in str(v) for _, v in params_list)
            if is_put:
                return {"success": True, "result": []}
            return {
                "success": True,
                "result": [{
                    "symbol": "C-BTC-43000-27DEC26",
                    "bid": "500", "ask": "520", "mark_price": "510",
                    "oi": "200", "volume": "50",
                    "product": {"underlying_asset": {"symbol": "BTC"}},
                    "greeks": {"delta": "0.45", "iv": "0.65"},
                }]
            }

        adapter._public_get = AsyncMock(side_effect=mock_get)
        chain = await adapter.get_option_chain(get_instrument("BTC"))
        assert len(chain) == 1
        assert call_count[0] >= 2  # tried options/chain + at least one tickers call

    @pytest.mark.asyncio
    async def test_ping_uses_time_endpoint(self):
        from unittest.mock import AsyncMock
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        adapter = DeltaIndiaAdapter()
        calls = []

        async def mock_get(path, params=None):
            calls.append(path)
            return {"success": True, "result": {}}

        adapter._public_get = AsyncMock(side_effect=mock_get)
        result = await adapter.ping()
        assert result is True
        assert any("/v2/time" in c for c in calls)
