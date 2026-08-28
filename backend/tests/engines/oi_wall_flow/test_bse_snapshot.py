"""The screenshot is the contract: this chain must arm 3500 CE, never a PE."""
from app.engines.oi_wall_flow import Intent, OIWallFlowStrategy, measure


def test_near_atm_calls_are_short_covering(bse_rows, cfg):
    m = measure(3392.50, bse_rows, cfg)
    by = {(f.side, f.strike): f.kind for f in m.flows}
    assert by[("CE", 3300)] == "short_covering"
    assert by[("CE", 3400)] == "short_covering"
    assert by[("CE", 3500)] == "short_covering"
    assert by[("PE", 3300)] == "short_buildup"
    assert by[("PE", 3400)] == "short_buildup"
    assert by[("PE", 3500)] == "long_unwinding"
    assert by[("CE", 3600)] == "long_buildup"
    assert by[("CE", 3800)] == "long_buildup"


def test_bse_chain_buys_3500_ce_not_the_put(bse_snap, cfg):
    sig = OIWallFlowStrategy(cfg).evaluate(bse_snap)
    assert sig.state == "armed"
    assert sig.plan is not None
    assert sig.plan.option_type == "CE"
    assert sig.plan.strike == 3500
    assert sig.plan.entry == 84.15
    assert sig.plan.stop == 50.49          # 40% premium stop
    assert sig.plan.target == 126.23       # +50%
    assert sig.plan.target_2 == 168.30     # +100%
    assert sig.plan.underlying_invalidation == 3300
    assert sig.plan.quantity == 200
    assert sig.bias.bias == "bullish"
    assert "call wall 3500" in sig.plan.reason


def test_generate_emits_a_long_options_signal(bse_snap, cfg):
    signals = OIWallFlowStrategy(cfg).generate(bse_snap)
    assert len(signals) == 1
    s = signals[0]
    assert s.underlying == "BSE"
    assert s.direction == "long"
    assert s.instrument_type == "options"
    assert s.source == "oi_wall_flow"
    assert s.stop_loss == 50.49
    assert s.take_profit == 126.23
    assert "3500CE" in (s.option_symbol or "")


def test_put_wall_break_exits_even_if_premium_has_not(bse_snap, cfg):
    strat = OIWallFlowStrategy(cfg)
    sig = strat.evaluate(bse_snap)
    pos = strat.on_entry(sig, 84.15, bse_snap.at_ms, "2026-08-28")
    still = strat.on_price(pos, premium=70.0, spot=3390.0)
    assert still.intent == Intent.NONE
    dead = strat.on_price(pos, premium=70.0, spot=3299.0)
    assert dead.intent == Intent.EXIT
    assert dead.exit_reason == "put_wall_broken"


def test_premium_stop_fires(bse_snap, cfg):
    strat = OIWallFlowStrategy(cfg)
    sig = strat.evaluate(bse_snap)
    pos = strat.on_entry(sig, 84.15, bse_snap.at_ms, "2026-08-28")
    hit = strat.on_price(pos, premium=50.49, spot=3390.0)
    assert hit.intent == Intent.EXIT and hit.exit_reason == "stop"
