import pytest
from app.services.providers.truedata.diagnostics import (
    DiagnosticCategoryResult,
    DiagnosticFieldCheck,
    DiagnosticSuiteResult,
    run_truedata_diagnostics,
    verify_truedata_auth,
    verify_indices_feed,
    verify_equity_spot_feed,
    verify_futures_feed,
    verify_options_chain_feed,
    verify_volume_tape_feed,
    verify_options_greeks_engine,
    verify_market_profile_engine,
    verify_volume_profile_engine,
    verify_delta_orderflow_engine,
)


@pytest.mark.asyncio
async def test_diagnostics_suite_runner_mock_user():
    """Verify running the full diagnostics suite produces all 10 categories with valid metrics."""
    result = await run_truedata_diagnostics("test_user_default")
    assert isinstance(result, DiagnosticSuiteResult)
    assert result.total_tests == 10
    assert result.passed_count >= 8
    assert result.overall_status in ("PASS", "WARNING", "PARTIAL")
    assert len(result.categories) == 10

    cat_ids = [c.id for c in result.categories]
    assert "truedata_auth" in cat_ids
    assert "indices" in cat_ids
    assert "equity_spot" in cat_ids
    assert "futures" in cat_ids
    assert "options_chain" in cat_ids
    assert "volume_tape" in cat_ids
    assert "options_greeks" in cat_ids
    assert "market_profile" in cat_ids
    assert "volume_profile" in cat_ids
    assert "delta_orderflow" in cat_ids


@pytest.mark.asyncio
async def test_truedata_auth_check_without_account():
    """Verify TrueData auth check handles unconfigured account gracefully."""
    res = await verify_truedata_auth(None)
    assert res.id == "truedata_auth"
    assert res.status == "WARNING"
    assert "Not Configured" in res.field_checks[0].value


@pytest.mark.asyncio
async def test_single_category_runner():
    """Verify running a single category test works cleanly."""
    result = await run_truedata_diagnostics("test_user_default", category_id="options_greeks")
    assert result.total_tests == 1
    assert len(result.categories) == 1
    greeks_cat = result.categories[0]
    assert greeks_cat.id == "options_greeks"
    assert greeks_cat.status == "PASS"
    assert "call_delta" in greeks_cat.metrics
    assert "call_theta_day" in greeks_cat.metrics


@pytest.mark.asyncio
async def test_options_greeks_field_checks():
    """Verify Black-Scholes Greeks field validations."""
    res = await verify_options_greeks_engine()
    assert res.status == "PASS"
    assert res.metrics["call_delta"] > 0
    assert res.metrics["put_delta"] < 0
    assert len(res.field_checks) == 4
    for check in res.field_checks:
        assert check.status == "PASS"


@pytest.mark.asyncio
async def test_market_profile_field_checks():
    """Verify Market Profile TPO structure calculations."""
    res = await verify_market_profile_engine()
    assert res.status == "PASS"
    assert "poc" in res.metrics
    assert "vah" in res.metrics
    assert "val" in res.metrics
    assert res.metrics["vah"] >= res.metrics["val"]


@pytest.mark.asyncio
async def test_volume_profile_field_checks():
    """Verify Volume Profile and Buy/Sell distribution."""
    res = await verify_volume_profile_engine()
    assert res.status == "PASS"
    assert res.metrics["buy_ratio_pct"] + res.metrics["sell_ratio_pct"] == 100.0
    assert "vpoc" in res.metrics


@pytest.mark.asyncio
async def test_delta_orderflow_field_checks():
    """Verify Cumulative Volume Delta and Flow Sign."""
    res = await verify_delta_orderflow_engine()
    assert res.status == "PASS"
    assert res.metrics["flow_sign"] in (+1, -1, 0)
    assert res.metrics["cvd"] != 0

