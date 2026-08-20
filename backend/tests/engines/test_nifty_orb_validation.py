import pytest
from app.engines.nifty_orb_validation import OPTION_EXECUTION_FIELDS, OPTION_OHLC_FIELDS, OptionTrade, TradingCosts, expiry_metrics, parameter_sensitivity, regime_metrics, require_historical_option_fields, validate_option_trades, walk_forward


def test_costs_reduce_gross_option_pnl():
    result=validate_option_trades([OptionTrade(100,120,75)],TradingCosts(brokerage=20,slippage_per_share=0.10))
    assert result.metrics["net_pnl"] < 1500
    assert result.metrics["gross_profit"] == 1500


def test_option_validation_rejects_selling():
    with pytest.raises(ValueError): validate_option_trades([OptionTrade(100,120,75,direction="SELL")])


def test_regime_and_expiry_metrics_are_separate():
    trades=[OptionTrade(100,110,75,regime="TREND",expiry_dte=3),OptionTrade(100,90,75,regime="RANGE",expiry_dte=0)]
    assert set(regime_metrics(trades))=={"TREND","RANGE"}
    assert set(expiry_metrics(trades))=={"expiry_day","non_expiry"}


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
