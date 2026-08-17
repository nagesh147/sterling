"""
Unit tests for Zerodha Kite Diagnostics Service.
"""
import pytest
from app.services.providers.kite.diagnostics import (
    KiteDiagnosticSuiteResult,
    run_kite_diagnostics,
    verify_network_connectivity,
    verify_kite_api_reachability,
    verify_kite_session,
    verify_kite_margins,
    verify_kite_instruments,
    verify_kite_historical,
    verify_kite_quotes,
    verify_kite_orders_gtt,
)


@pytest.mark.asyncio
async def test_network_connectivity_check():
    """Verify internet/DNS socket check produces valid results."""
    res = await verify_network_connectivity()
    assert res.id == "internet_network"
    assert res.status in ("PASS", "FAIL")
    assert "internet_status" in res.metrics
    assert len(res.field_checks) == 2


@pytest.mark.asyncio
async def test_kite_api_reachability_check():
    """Verify Kite API gateway reachability check."""
    res = await verify_kite_api_reachability()
    assert res.id == "kite_gateway"
    assert "status_code" in res.metrics


@pytest.mark.asyncio
async def test_kite_session_without_account():
    """Verify session check handles null account gracefully."""
    res = await verify_kite_session(None)
    assert res.id == "kite_session"
    assert res.status == "WARNING"
    assert "None Active" in res.field_checks[0].value


@pytest.mark.asyncio
async def test_kite_margins_without_account():
    """Verify margins check handles null account with simulated fallback."""
    res = await verify_kite_margins(None)
    assert res.id == "kite_margins"
    assert res.status == "WARNING"


@pytest.mark.asyncio
async def test_kite_instruments_check():
    """Verify instruments database resolution check."""
    res = await verify_kite_instruments(None)
    assert res.id == "kite_instruments"
    assert res.status == "PASS"
    assert res.metrics["total_instruments"] > 0


@pytest.mark.asyncio
async def test_kite_historical_fallback():
    """Verify historical candle stream fallback."""
    res = await verify_kite_historical(None)
    assert res.id == "kite_historical"
    assert res.metrics["candles_count"] > 0
    assert res.metrics["last_close"] > 0


@pytest.mark.asyncio
async def test_kite_quotes_fallback():
    """Verify quotes depth fallback."""
    res = await verify_kite_quotes(None)
    assert res.id == "kite_quotes"
    assert res.metrics["ltp"] > 0


@pytest.mark.asyncio
async def test_kite_orders_gtt_fallback():
    """Verify GTT and order routing check."""
    res = await verify_kite_orders_gtt(None)
    assert res.id == "kite_orders_gtt"
    assert "Paper" in res.field_checks[1].value


@pytest.mark.asyncio
async def test_kite_diagnostics_suite_runner():
    """Verify full suite runner runs all categories."""
    suite = await run_kite_diagnostics("test_user_default")
    assert isinstance(suite, KiteDiagnosticSuiteResult)
    assert suite.total_tests == 8
    assert len(suite.categories) == 8
    cat_ids = [c.id for c in suite.categories]
    assert "internet_network" in cat_ids
    assert "kite_gateway" in cat_ids
    assert "kite_session" in cat_ids
    assert "kite_margins" in cat_ids
    assert "kite_instruments" in cat_ids
    assert "kite_historical" in cat_ids
    assert "kite_quotes" in cat_ids
    assert "kite_orders_gtt" in cat_ids


@pytest.mark.asyncio
async def test_kite_authenticated_diagnostics(monkeypatch):
    """Verify diagnostics when user is authenticated with live Kite session."""
    from unittest.mock import AsyncMock, MagicMock
    from app.services.exchanges.kite import accounts as kite_accounts

    mock_acct = MagicMock()
    mock_acct.id = "KITE-TEST01"
    mock_acct.user_id = "test_user_1"
    mock_acct.label = "My Kite"
    mock_acct.api_key = "test_key"
    mock_acct.connected = True
    mock_acct.has_credentials = True
    mock_acct.is_paper = False
    mock_acct.kite_user_id = "AA0595"

    mock_client = MagicMock()
    mock_client.get_profile = AsyncMock(return_value={"user_id": "AA0595", "user_name": "Nagesh Madaram"})
    mock_client.get_margins = AsyncMock(return_value={"equity": {"available": {"cash": 150000.0, "collateral": 25000.0}}})
    mock_client.get_historical = AsyncMock(return_value=[{"close": 24550.0}])
    mock_client.get_quote = AsyncMock(return_value={"NSE:NIFTY 50": {"last_price": 24550.0}})
    mock_client.get_gtts = AsyncMock(return_value=[{"id": 1, "status": "active"}])

    monkeypatch.setattr(kite_accounts, "acquire_client", AsyncMock(return_value=mock_client))

    sess_res = await verify_kite_session(mock_acct)
    assert sess_res.status == "PASS"
    assert "AA0595" in sess_res.summary
    assert "Nagesh Madaram" in sess_res.summary

    margin_res = await verify_kite_margins(mock_acct)
    assert margin_res.status == "PASS"
    assert margin_res.metrics["cash"] == 150000.0

    hist_res = await verify_kite_historical(mock_acct)
    assert hist_res.status == "PASS"
    assert hist_res.metrics["last_close"] == 24550.0

    quote_res = await verify_kite_quotes(mock_acct)
    assert quote_res.status == "PASS"
    assert quote_res.metrics["ltp"] == 24550.0

    gtt_res = await verify_kite_orders_gtt(mock_acct)
    assert gtt_res.status == "PASS"
    assert gtt_res.metrics["gtt_count"] == 1

