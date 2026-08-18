from app.engines.nifty_orb_options import StrategyConfig
from app.services.nifty_orb_options import set_config


def test_default_strategy_contract_is_kite_and_paper_only():
    cfg = StrategyConfig()
    assert cfg.data_source == "kite"
    assert cfg.execution_broker == "kite"
    assert cfg.paper_only is True
    assert cfg.opening_range_minutes == 15
    assert cfg.interval_minutes == 5
    assert cfg.max_risk_inr == 3000.0


def test_config_rejects_non_kite_execution():
    try:
        set_config({"execution_broker": "truedata"})
    except ValueError as exc:
        assert "fixed to 'kite'" in str(exc)
    else:
        raise AssertionError("non-Kite execution must be rejected")


def test_config_rejects_invalid_data_source():
    try:
        set_config({"data_source": "unknown"})
    except ValueError as exc:
        assert "data_source" in str(exc)
    else:
        raise AssertionError("unknown data source must be rejected")
