"""
Phase D regression test — _compute_signal_item must use the active
TradingModeConfig's macro_tf / signal_tf / execution_tf, not hardcoded
4H / 1H / 15m. Before fix: every mode (scalping, intraday, positional)
silently fell back to swing-mode timeframes.
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.endpoints.directional import _compute_signal_item
from app.core.trading_mode import MODES
from app.schemas.market import Candle


def _candle_series(n: int = 200, base: float = 100.0) -> list:
    """Synthetic candles — enough bars for regime + signal computation."""
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
    """Minimal InstrumentMeta the function needs."""
    from app.schemas.instruments import InstrumentMeta
    return InstrumentMeta(
        underlying="BTC", tick_size=0.5, strike_step=100.0,
        has_options=True, exchange="deribit", exchange_currency="BTC",
        perp_symbol="BTC-PERPETUAL", index_name="btc_usd", dvol_symbol="BTC_DVOL",
        delta_perp_symbol="BTCUSD",
        min_dte=5, preferred_dte_min=10, preferred_dte_max=21,
    )


@pytest.fixture
def mock_adapter():
    a = MagicMock()
    a.get_index_price = AsyncMock(return_value=100.0)
    a.get_candles = AsyncMock(return_value=_candle_series())
    return a


class TestPhaseDTimeframes:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode_name,expected_tfs", [
        ("scalping",   ("15m", "5m",  "1m")),
        ("intraday",   ("1H",  "15m", "5m")),
        ("swing",      ("4H",  "1H",  "15m")),
        ("positional", ("D",   "4H",  "1H")),
    ])
    async def test_each_mode_pulls_its_own_timeframes(
        self, mock_adapter, mode_name, expected_tfs,
    ):
        mode = MODES[mode_name]
        await _compute_signal_item(
            _instrument(), mock_adapter,
            macro_filter=mode.macro_filter,
            st_threshold=mode.st_threshold,
            stop_mult=mode.stop_atr_mult,
            rr=mode.rr_target,
            mode=mode,
        )
        # Three get_candles calls, one per timeframe in (macro, signal, exec)
        # order. Each call's positional arg [1] is the timeframe string.
        called_tfs = tuple(
            c.args[1] for c in mock_adapter.get_candles.call_args_list
        )
        assert called_tfs == expected_tfs, (
            f"{mode_name} should fetch {expected_tfs}, got {called_tfs}"
        )

    @pytest.mark.asyncio
    async def test_no_mode_falls_back_to_swing_4h(self, mock_adapter):
        """Back-compat: callers that don't pass mode get the legacy 4H/1H/15m."""
        await _compute_signal_item(
            _instrument(), mock_adapter,
            macro_filter="adx_4h", st_threshold=3,
            stop_mult=2.0, rr=2.0,
            # mode intentionally omitted
        )
        called_tfs = tuple(
            c.args[1] for c in mock_adapter.get_candles.call_args_list
        )
        assert called_tfs == ("4H", "1H", "15m")
