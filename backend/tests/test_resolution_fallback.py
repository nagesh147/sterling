"""
Regression test for the "no signals in any mode" bug introduced by Phase D.

Cause: Phase D started requesting "1m" / "5m" / "D" candles for non-swing
modes, but every adapter only supported "15m / 1H / 4H". Adapter raised
ValueError("Unsupported resolution: 5m"), which propagated into
_compute_signal_item's outer try/except and returned fresh=False — frontend
filtered every entry out and the user saw zero signals.

Fix: when an adapter rejects a mode-specific timeframe, _compute_signal_item
falls back to 4H/1H/15m so signals still flow on legacy adapters; the mode's
*parameters* (stop_mult, rr, macro_filter, st_threshold) are still applied.

Adapter resolution maps were also extended with 1m/5m/D so adapters that
support them get the proper finer-grained candles.
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.endpoints.directional import _compute_signal_item
from app.core.trading_mode import MODES
from app.schemas.market import Candle


def _candle_series(n: int = 200, base: float = 100.0):
    return [
        Candle(
            timestamp_ms=i * 60_000,
            open=base + i * 0.1,
            high=base + i * 0.1 + 0.5,
            low=base + i * 0.1 - 0.5,
            close=base + i * 0.1 + 0.2,
            volume=100.0 + i,
        )
        for i in range(n)
    ]


def _instrument():
    from app.schemas.instruments import InstrumentMeta
    return InstrumentMeta(
        underlying="BTC", tick_size=0.5, strike_step=100.0,
        has_options=True, exchange="deribit", exchange_currency="BTC",
        perp_symbol="BTC-PERPETUAL", index_name="btc_usd", dvol_symbol="BTC_DVOL",
        delta_perp_symbol="BTCUSD",
        min_dte=5, preferred_dte_min=10, preferred_dte_max=21,
    )


class TestUnsupportedResolutionFallback:
    @pytest.mark.asyncio
    async def test_intraday_falls_back_when_adapter_rejects_5m(self):
        """Adapter that only supports 15m/1H/4H must produce a fresh signal
        in intraday mode via the fallback path."""
        a = MagicMock()
        a.get_index_price = AsyncMock(return_value=100.0)
        a.get_dvol = AsyncMock(return_value=None)
        a.get_dvol_history = AsyncMock(return_value=[])
        a.get_option_chain = AsyncMock(return_value=[])

        # Reject 5m but accept 15m/1H/4H — first call (5m) raises, fallback retries
        async def _reject_finegrained(_inst, resolution, limit=200):
            if resolution in ("5m", "1m", "D", "1D"):
                raise ValueError(f"Unsupported resolution: {resolution}")
            return _candle_series()

        a.get_candles = AsyncMock(side_effect=_reject_finegrained)

        out = await _compute_signal_item(
            _instrument(), a,
            macro_filter="adx_4h", st_threshold=2,
            stop_mult=1.5, rr=1.5,
            mode=MODES["intraday"],
        )
        # Fallback succeeded → fresh signal
        assert out is not None
        assert out.get("fresh") is True
        # All three fallback timeframes got hit
        called = [c.args[1] for c in a.get_candles.call_args_list]
        assert "4H" in called and "1H" in called and "15m" in called

    @pytest.mark.asyncio
    async def test_scalping_falls_back_when_1m_rejected(self):
        a = MagicMock()
        a.get_index_price = AsyncMock(return_value=100.0)
        a.get_dvol = AsyncMock(return_value=None)
        a.get_dvol_history = AsyncMock(return_value=[])
        a.get_option_chain = AsyncMock(return_value=[])

        async def _reject_finegrained(_inst, resolution, limit=200):
            if resolution in ("1m", "5m", "D", "1D"):
                raise ValueError(f"Unsupported resolution: {resolution}")
            return _candle_series()

        a.get_candles = AsyncMock(side_effect=_reject_finegrained)

        out = await _compute_signal_item(
            _instrument(), a,
            macro_filter="off", st_threshold=1,
            stop_mult=1.0, rr=1.0,
            mode=MODES["scalping"],
        )
        assert out is not None
        assert out.get("fresh") is True

    @pytest.mark.asyncio
    async def test_swing_works_natively_no_fallback(self):
        """Swing mode (4H/1H/15m) requires no fallback — adapter's first
        attempt should succeed."""
        a = MagicMock()
        a.get_index_price = AsyncMock(return_value=100.0)
        a.get_dvol = AsyncMock(return_value=None)
        a.get_dvol_history = AsyncMock(return_value=[])
        a.get_option_chain = AsyncMock(return_value=[])
        a.get_candles = AsyncMock(return_value=_candle_series())

        out = await _compute_signal_item(
            _instrument(), a,
            macro_filter="adx_4h", st_threshold=3,
            stop_mult=2.0, rr=2.0,
            mode=MODES["swing"],
        )
        assert out is not None
        assert out.get("fresh") is True
        # Exactly 3 candle calls (no retry)
        assert a.get_candles.call_count == 3


class TestResolutionMapExtensions:
    """Adapter _RESOLUTION_MAPs must now cover 1m, 5m, D for finer modes."""

    def test_deribit_supports_finer_resolutions(self):
        from app.services.exchanges.adapters.deribit import _RESOLUTION_MAP
        for tf in ("1m", "5m", "15m", "1H", "4H", "D", "1D"):
            assert tf in _RESOLUTION_MAP, f"Deribit must accept {tf}"

    def test_delta_india_supports_finer_resolutions(self):
        from app.services.exchanges.adapters.delta_india import _RESOLUTION_MAP
        for tf in ("1m", "5m", "15m", "1H", "4H", "D"):
            assert tf in _RESOLUTION_MAP

    def test_okx_supports_finer_resolutions(self):
        from app.services.exchanges.adapters.okx import _RESOLUTION_MAP
        for tf in ("1m", "5m", "15m", "1H", "4H", "D"):
            assert tf in _RESOLUTION_MAP

    def test_binance_supports_finer_resolutions(self):
        from app.services.exchanges.adapters.binance import _INTERVAL_MAP
        for tf in ("1m", "5m", "15m", "1H", "4H", "D"):
            assert tf in _INTERVAL_MAP

    def test_zerodha_supports_finer_resolutions(self):
        from app.services.exchanges.adapters.zerodha import _RESOLUTION_MAP
        for tf in ("1m", "5m", "15m", "1H", "4H", "D"):
            assert tf in _RESOLUTION_MAP
