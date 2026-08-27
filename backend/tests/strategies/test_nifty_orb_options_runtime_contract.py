from datetime import datetime

import pytest

from app.engines.nifty_orb_options import Bar, OptionContract, Signal, StrategyConfig, build_trade_plan, select_option
from app.services.nifty_orb_options import get_config, set_config


def test_engine_contract_is_kite_and_strategy_has_no_local_execution_mode():
    cfg = StrategyConfig()
    assert cfg.data_source == "kite"
    assert cfg.execution_broker == "kite"
    assert not hasattr(cfg, "paper_only")
    # Power switch, not a safety device — paper/live is `account.is_paper` and
    # this engine has never carried a copy of it (the assertion above).
    assert cfg.enabled is True
    assert cfg.opening_range_minutes == 15
    assert cfg.interval_minutes == 5
    assert cfg.max_risk_inr == 3000.0
    assert cfg.max_spread_pct == 1.5


def test_runtime_default_is_enabled():
    """Enabled by default, like the other option engines.

    For THIS engine that is a stronger statement than for the others: the runner
    gates on `enabled` and the market clock and then executes, with no
    `auto_execute` check — so `account.is_paper` is the thing standing between it
    and real orders.
    """
    cfg = get_config()
    assert cfg.enabled is True
    assert not hasattr(cfg, "paper_only")
    assert cfg.execution_broker == "kite"


def test_config_rejects_non_kite_execution():
    with pytest.raises(ValueError, match="fixed to 'kite'"):
        set_config({"execution_broker": "truedata"})


def test_config_rejects_invalid_data_source():
    with pytest.raises(ValueError, match="data_source"):
        set_config({"data_source": "unknown"})


def test_config_rejects_legacy_strategy_local_paper_flag():
    with pytest.raises(ValueError, match="paper_only"):
        set_config({"paper_only": True})


def test_config_rejects_quote_freshness_without_ticks():
    with pytest.raises(ValueError, match="requires truedata_use_ticks"):
        set_config({"data_source": "truedata", "truedata_use_ticks": False, "truedata_use_quote_freshness": True})


def test_option_liquidity_gate_rejects_wide_or_thin_contracts():
    cfg = StrategyConfig(max_spread_pct=1.0, min_option_volume=1000, min_open_interest=10000)
    contracts = [OptionContract("NIFTYCE", 25000, "2026-08-20", "CE", ltp=100, bid=90, ask=110, lot_size=75, volume=5000, open_interest=50000)]
    with pytest.raises(ValueError, match="liquid CE"):
        select_option(25000, "LONG", contracts, cfg)


def test_trade_plan_uses_ask_and_creates_premium_protection():
    # 101 x 75 = 7,575 a lot; below that the plan is refused outright and the
    # premium-protection assertions below never run.
    cfg = StrategyConfig(max_risk_inr=25000, min_option_volume=0, min_open_interest=0)
    option = OptionContract("NIFTYCE", 25000, "2026-08-20", "CE", ltp=100, bid=99, ask=101, lot_size=75, delta=0.5, volume=5000, open_interest=50000)
    signal = Signal("LONG", "TREND", datetime(2026, 8, 19, 9, 45), 25000, 24900, 24980, 100, 20, 1.5, 0.8, "test")
    plan = build_trade_plan(signal, option, cfg, spot=25020)
    assert plan.entry_premium == 101
    assert plan.stop_premium < plan.entry_premium
    assert plan.target_premium > plan.entry_premium
    assert plan.quantity % option.lot_size == 0
    assert plan.risk_inr <= cfg.max_risk_inr
