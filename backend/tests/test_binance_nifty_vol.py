"""
Tests: Binance adapter, NIFTY/BANKNIFTY registry, volatility scan endpoint.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.market import Candle, OptionSummary
from app.services.exchanges.adapters.binance import BinanceAdapter, _sign, _ts_ms
from app.services.exchanges.instrument_registry import get_instrument, list_instruments
from main import create_app


def _make_candles(n=100):
    return [Candle(timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                   open=40000.0+i*10, high=40050.0+i*10,
                   low=39950.0+i*10, close=40005.0+i*10, volume=100.0) for i in range(n)]


def _make_options():
    now = int(time.time() * 1000)
    opts = []
    for strike, dist in [(42000, 0), (43000, 1), (41000, -1)]:
        for ot in ["call", "put"]:
            opts.append(OptionSummary(
                instrument_name=f"BTC-12JAN25-{strike}-{'C' if ot=='call' else 'P'}",
                underlying="BTC", strike=float(strike), expiry_date="12JAN25", dte=12,
                option_type=ot, bid=400.0, ask=420.0, mark_price=410.0, mid_price=410.0,
                mark_iv=55.0, delta=0.45 if ot=="call" else -0.45,
                open_interest=200.0, volume_24h=30.0, last_updated_ms=now,
            ))
    return opts


def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42100.0)
    a.get_candles = AsyncMock(return_value=_make_candles())
    a.get_option_chain = AsyncMock(return_value=_make_options())
    a.get_dvol = AsyncMock(return_value=None)
    a.get_dvol_history = AsyncMock(return_value=[])
    a.close = AsyncMock(return_value=None)
    return a


@pytest.fixture()
def client():
    app = create_app()
    adapter = _mock_adapter()
    app.state.adapter = adapter
    with TestClient(app) as c:
        c.app.state.adapter = adapter
        yield c


# ─── Binance Helpers ──────────────────────────────────────────────────────────

class TestBinanceHelpers:
    def test_sign_produces_hex(self):
        sig = _sign("secret", "param=value")
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)

    def test_ts_ms_seconds(self):
        assert _ts_ms(1_700_000_000) == 1_700_000_000_000

    def test_ts_ms_milliseconds(self):
        ts = 1_700_000_000_000
        assert _ts_ms(ts) == ts


class TestBinanceAdapterPaper:
    @pytest.mark.asyncio
    async def test_ping_paper(self):
        adapter = BinanceAdapter(is_paper=True)
        adapter._public_get = AsyncMock(return_value={})
        assert await adapter.ping()

    @pytest.mark.asyncio
    async def test_test_connection_paper(self):
        adapter = BinanceAdapter(is_paper=True)
        assert await adapter.test_connection()

    @pytest.mark.asyncio
    async def test_balances_paper(self):
        adapter = BinanceAdapter(is_paper=True)
        bals = await adapter.get_balances()
        assert len(bals) > 0
        assert any(b.asset == "USDT" for b in bals)

    @pytest.mark.asyncio
    async def test_positions_paper_empty(self):
        adapter = BinanceAdapter(is_paper=True)
        assert await adapter.get_positions() == []

    @pytest.mark.asyncio
    async def test_fills_paper_empty(self):
        adapter = BinanceAdapter(is_paper=True)
        assert await adapter.get_fills() == []

    @pytest.mark.asyncio
    async def test_get_candles(self):
        adapter = BinanceAdapter(is_paper=True)
        now = int(time.time() * 1000)
        # Binance klines format: [openTime, open, high, low, close, vol, closeTime, ...]
        adapter._public_get = AsyncMock(return_value=[
            [now - 3600000, "41000", "41500", "40800", "41200", "100", now - 1, "...", "5", "...", "...", "0"],
            [now, "41200", "42000", "41100", "41800", "120", now + 3599999, "...", "6", "...", "...", "0"],
        ])
        candles = await adapter.get_candles(get_instrument("BTC"), "1H", limit=2)
        assert len(candles) == 2
        assert candles[0].close == pytest.approx(41200.0)
        assert candles[1].close == pytest.approx(41800.0)

    @pytest.mark.asyncio
    async def test_get_candles_pagination_large_limit(self):
        """Pagination: limit > 1500 triggers multiple requests."""
        adapter = BinanceAdapter(is_paper=True)
        now = int(time.time() * 1000)
        call_count = [0]

        # Each call returns exactly 1500 rows (max per page)
        def make_rows(count, base_ts):
            return [[base_ts - i * 3600000, "41000", "41500", "40800", "41200", "100"] + ["0"] * 6
                    for i in range(count)]

        async def mock_get(base, path, params=None):
            call_count[0] += 1
            per_page = (params or {}).get("limit", 1500)
            base_ts = (params or {}).get("endTime", now) or now
            rows = make_rows(per_page, base_ts)
            return rows

        adapter._public_get = AsyncMock(side_effect=mock_get)
        candles = await adapter.get_candles(get_instrument("BTC"), "1H", limit=2000)
        # Should have made more than 1 API call (2000 > 1500)
        assert call_count[0] >= 2
        assert len(candles) <= 2000
        # All timestamps should be unique and sorted ascending
        ts_list = [c.timestamp_ms for c in candles]
        assert ts_list == sorted(ts_list)
        assert len(set(ts_list)) == len(ts_list)

    @pytest.mark.asyncio
    async def test_get_candles_stops_when_empty_page(self):
        """Stops pagination when API returns empty list."""
        adapter = BinanceAdapter(is_paper=True)
        now = int(time.time() * 1000)
        call_count = [0]

        async def mock_get(base, path, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: 200 rows (less than limit 1500)
                return [[now - i * 3600000, "41000", "41500", "40800", "41200", "100"] + ["0"] * 6
                        for i in range(200)]
            return []  # No more history

        adapter._public_get = AsyncMock(side_effect=mock_get)
        candles = await adapter.get_candles(get_instrument("BTC"), "1H", limit=2000)
        assert call_count[0] == 1  # Stops after first page (200 < 1500)
        assert len(candles) == 200

    @pytest.mark.asyncio
    async def test_live_mode_requires_credentials(self):
        adapter = BinanceAdapter(is_paper=False, api_key="", api_secret="")
        with pytest.raises(RuntimeError, match="api_key"):
            await adapter.get_balances()

    @pytest.mark.asyncio
    async def test_portfolio_snapshot_paper(self):
        adapter = BinanceAdapter(is_paper=True)
        snap = await adapter.get_portfolio_snapshot()
        assert snap.exchange == "binance"
        assert "USDT" in snap.display_name or "Binance" in snap.display_name
        assert snap.total_balance_usd > 0


class TestBinanceExchangeAPI:
    def test_binance_in_supported(self, client):
        resp = client.get("/api/v1/exchanges/supported")
        names = [e["name"] for e in resp.json()["exchanges"]]
        assert "binance" in names

    def test_add_binance_exchange(self, client):
        resp = client.post("/api/v1/exchanges", json={
            "name": "binance",
            "display_name": "My Binance",
            "api_key": "test_binance_key",
            "api_secret": "test_binance_secret",
            "is_paper": True,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "binance"

    def test_binance_account_paper_summary(self, client):
        # Add and activate Binance
        resp = client.post("/api/v1/exchanges", json={
            "name": "binance", "display_name": "Binance",
            "api_key": "k", "api_secret": "s", "is_paper": True,
        })
        eid = resp.json()["id"]
        client.post(f"/api/v1/exchanges/{eid}/activate")
        data = client.get("/api/v1/account/summary").json()
        assert data["is_paper"] is True
        assert "binance" in data["exchange_name"]


# ─── NIFTY / BANKNIFTY Registry ───────────────────────────────────────────────

class TestNIFTYRegistry:
    def test_nifty_in_registry(self):
        assert get_instrument("NIFTY") is not None

    def test_banknifty_in_registry(self):
        assert get_instrument("BANKNIFTY") is not None

    def test_nifty_has_options(self):
        inst = get_instrument("NIFTY")
        assert inst.has_options is True

    def test_nifty_exchange_is_zerodha(self):
        inst = get_instrument("NIFTY")
        assert inst.exchange == "zerodha"

    def test_nifty_lot_size(self):
        assert get_instrument("NIFTY").contract_multiplier == 50.0
        assert get_instrument("BANKNIFTY").contract_multiplier == 25.0

    def test_nifty_quote_currency_inr(self):
        assert get_instrument("NIFTY").quote_currency == "INR"

    def test_all_instruments_includes_nifty(self):
        underlyings = {i.underlying for i in list_instruments()}
        assert "NIFTY" in underlyings
        assert "BANKNIFTY" in underlyings


# ─── Volatility Scan ──────────────────────────────────────────────────────────

class TestVolatilityScan:
    def test_vol_scan_btc(self, client):
        resp = client.post("/api/v1/directional/volatility-scan?underlying=BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert "structures" in data
        assert "spot_price" in data
        assert "note" in data

    def test_vol_scan_structures_types(self, client):
        data = client.post("/api/v1/directional/volatility-scan?underlying=BTC").json()
        types = {s["structure_type"] for s in data["structures"]}
        # At least straddle should be found (same-strike call+put)
        assert "long_straddle" in types or "long_strangle" in types

    def test_vol_scan_straddle_fields(self, client):
        data = client.post("/api/v1/directional/volatility-scan?underlying=BTC").json()
        straddles = [s for s in data["structures"] if s["structure_type"] == "long_straddle"]
        if straddles:
            s = straddles[0]
            assert "net_debit" in s
            assert "breakeven_up" in s
            assert "breakeven_down" in s
            assert "avg_iv" in s
            assert len(s["legs"]) == 2

    def test_vol_scan_unknown_404(self, client):
        resp = client.post("/api/v1/directional/volatility-scan?underlying=FAKE")
        assert resp.status_code == 404

    def test_vol_scan_xrp_no_options_400(self, client):
        resp = client.post("/api/v1/directional/volatility-scan?underlying=XRP")
        assert resp.status_code == 400

    def test_vol_scan_healthy_candidates_count(self, client):
        data = client.post("/api/v1/directional/volatility-scan?underlying=BTC").json()
        assert "healthy_candidates" in data
        assert data["healthy_candidates"] >= 0
