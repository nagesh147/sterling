"""
Regression test for the KeyError('5m') / KeyError('1m') bug in
DeltaIndiaAdapter.get_candles. Phase D extended _RESOLUTION_MAP to cover
1m/5m/D but an inner secs-per-bar dict was only defined for 15m/1h/4h —
the first scalping or intraday candle fetch crashed.
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch

from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
from app.schemas.instruments import InstrumentMeta


def _btc():
    return InstrumentMeta(
        underlying="BTC", tick_size=0.5, strike_step=100.0,
        has_options=True, exchange="delta_india", exchange_currency="BTC",
        perp_symbol="BTC-PERPETUAL", index_name="btc_usd", dvol_symbol="BTC_DVOL",
        delta_perp_symbol="BTCUSD",
        min_dte=5, preferred_dte_min=10, preferred_dte_max=21,
    )


@pytest.fixture
def adapter():
    return DeltaIndiaAdapter(api_key="", api_secret="", is_paper=True)


class TestDeltaCandlesAllResolutions:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("resolution", ["1m", "5m", "15m", "1H", "4H", "D", "1D"])
    async def test_get_candles_does_not_raise_keyerror(self, adapter, resolution):
        """Every supported resolution must reach _public_get — no KeyError
        on the inner secs-per-bar lookup."""
        with patch.object(
            adapter, "_public_get", new=AsyncMock(return_value={"result": []}),
        ) as mock_get:
            result = await adapter.get_candles(_btc(), resolution=resolution, limit=10)
            assert isinstance(result, list)
            mock_get.assert_called_once()
            params = mock_get.call_args.kwargs.get("params") or {}
            # Sanity: the resolution param sent to Delta must match the map
            assert params.get("resolution") in ("1m", "5m", "15m", "1h", "4h", "1d")

    @pytest.mark.asyncio
    async def test_unsupported_resolution_still_raises_valueerror(self, adapter):
        with pytest.raises(ValueError, match="Unsupported"):
            await adapter.get_candles(_btc(), resolution="42m")
