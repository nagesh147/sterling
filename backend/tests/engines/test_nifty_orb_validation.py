import pytest
from app.engines.nifty_orb_validation import OPTION_EXECUTION_FIELDS, OPTION_OHLC_FIELDS, OptionTrade, TradingCosts, expiry_metrics, parameter_sensitivity, regime_metrics, require_historical_option_fields, validate_option_trades, walk_forward


def test_costs_reduce_gross_option_pnl():
    result=validate_option_trades([OptionTrade(100,120,75)],TradingCosts(brokerage=20,slippage_per_share=0.10))
    assert result.metrics["net_pnl"] < 1500
    assert result.metrics["gross_profit"] == 1500


def test_option_validation_rejects_selling():
    # Costs are passed so the guard cannot be what raises: this must fail on the
    # direction, which is what the test is named after.
    with pytest.raises(ValueError, match="buying only"):
        validate_option_trades([OptionTrade(100,120,75,direction="SELL")], TradingCosts(slippage_per_share=0.10))


def test_regime_and_expiry_metrics_are_separate():
    trades=[OptionTrade(100,110,75,regime="TREND",expiry_dte=3),OptionTrade(100,90,75,regime="RANGE",expiry_dte=0)]
    assert set(regime_metrics(trades, TradingCosts(slippage_per_share=0.10)))=={"TREND","RANGE"}
    assert set(expiry_metrics(trades, TradingCosts(slippage_per_share=0.10)))=={"expiry_day","non_expiry"}


def test_walk_forward_never_uses_future_test_rows_in_training():
    seen=[]
    def evaluator(train,test):
        seen.append((list(train),list(test))); return {"ok":True}
    out=walk_forward(list(range(10)),evaluator,train_size=4,test_size=2,step=2)
    assert out
    for train,test in seen: assert max(train)<min(test)


def test_walk_forward_rejects_insufficient_data():
    with pytest.raises(ValueError): walk_forward([1,2,3],lambda a,b:{},train_size=3,test_size=2)


def test_parameter_sensitivity_requires_results():
    result=parameter_sensitivity([1,2],[{"orb":15},{"orb":30}],lambda rows,p:{"pf":p["orb"]})
    assert [r["pf"] for r in result]==[15,30]


def test_historical_option_dataset_must_be_real_option_data():
    require_historical_option_fields([dict.fromkeys(OPTION_OHLC_FIELDS|OPTION_EXECUTION_FIELDS)])
    with pytest.raises(ValueError): require_historical_option_fields([{"timestamp":1}])
    with pytest.raises(ValueError, match="empty"): require_historical_option_fields([])


def test_ohlc_alone_cannot_support_an_execution_replay():
    """Missing bid/ask/volume/OI/lot_size makes the replay silently optimistic."""
    ohlc_only=[dict.fromkeys(OPTION_OHLC_FIELDS)]
    with pytest.raises(ValueError) as exc: require_historical_option_fields(ohlc_only)
    assert {"bid","ask","volume","open_interest","lot_size"} <= set(str(exc.value).replace(",","").split())
    # A signal-level study may opt out, but it must say so.
    require_historical_option_fields(ohlc_only,require_execution_fields=False)


# --- the corrected cost model -------------------------------------------------

def test_costing_without_a_stated_slippage_is_refused():
    """The defect this guard exists for: a scalp silently costed at zero slippage.

    All three entry points used to default to ``TradingCosts()``, which meant no
    slippage at all -- and half-spread is the largest single cost term at the open.
    """
    for fn in (validate_option_trades, regime_metrics, expiry_metrics):
        with pytest.raises(ValueError, match="slippage"):
            fn([OptionTrade(100, 120, 75)])


def test_slippage_cannot_be_omitted_from_the_cost_model_itself():
    with pytest.raises(TypeError):
        TradingCosts()                      # type: ignore[call-arg]


def test_the_corrected_rates_cost_far_more_than_the_old_ones():
    """Guards the direction of the fix, not the exact rates.

    The old defaults understated a real SENSEX round trip by roughly six times.
    If someone reverts a rate, this fails.
    """
    buy, sell, qty = 338.10 * 80, 342.44 * 80, 80
    corrected = TradingCosts(slippage_per_share=1.50).round_trip(buy, sell, qty)
    old = TradingCosts(slippage_per_share=0.0, stt_rate=0.000625,
                       exchange_rate=0.0000297).round_trip(buy, sell, qty)
    assert corrected > 4 * old
    # and it must be a material fraction of the observed +15 point target
    assert corrected / qty > 3.0


def test_brokerage_scales_with_orders_so_a_ladder_is_not_undercosted():
    buy, sell, qty = 100.0 * 75, 110.0 * 75, 75
    c = TradingCosts(slippage_per_share=0.10)
    assert c.round_trip(buy, sell, qty, orders=3) > c.round_trip(buy, sell, qty, orders=2)


def test_cost_rates_are_not_stale():
    """Staleness was the cause of all three defects, and none announced itself."""
    from datetime import date
    from app.engines.nifty_orb_validation import RATES_VERIFIED_ON
    checked = date.fromisoformat(RATES_VERIFIED_ON)
    assert (date.today() - checked).days < 400, (
        f"cost rates last verified {RATES_VERIFIED_ON} — re-check them against a "
        "contract note and update RATES_VERIFIED_ON"
    )
