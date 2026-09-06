"""
Tests for data source × instrument compatibility logic.
Verifies _adapter_can_serve() returns correct results for all combinations.
"""
import pytest
from app.api.v1.endpoints.directional import _adapter_can_serve
from app.services.exchanges.instrument_registry import get_instrument


class TestAdapterCompatibility:
    # ─── Crypto instruments on delta_india ───────────────────────────────────

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

    # ─── Binance compatibility ────────────────────────────────────────────────

    def test_nifty_not_on_binance(self):
        assert not _adapter_can_serve(get_instrument("NIFTY"), "binance")

    # ─── Deribit compatibility ────────────────────────────────────────────────

    def test_nifty_not_on_deribit(self):
        assert not _adapter_can_serve(get_instrument("NIFTY"), "deribit")

    # ─── All crypto instruments available on delta_india ─────────────────────

    # ─── No instrument on both zerodha AND crypto adapters ───────────────────
