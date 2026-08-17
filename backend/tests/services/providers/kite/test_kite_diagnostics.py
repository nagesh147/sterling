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
    assert suite.total_tests == 7
    assert len(suite.categories) == 7
    cat_ids = [c.id for c in suite.categories]
    assert "internet_network" in cat_ids
    assert "kite_gateway" in cat_ids
    assert "kite_session" in cat_ids
    assert "kite_margins" in cat_ids
    assert "kite_historical" in cat_ids
    assert "kite_quotes" in cat_ids
    assert "kite_orders_gtt" in cat_ids
