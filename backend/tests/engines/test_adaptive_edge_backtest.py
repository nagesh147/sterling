from app.engines.adaptive_edge.backtest import ReplayBar, ReplayConfig, run_replay
from app.engines.adaptive_edge.model import MarketFeatures


def make_bars(direction=1):
    bars = []
    for i in range(20):
        bars.append(
            ReplayBar(
                close=100.0 + direction * i * 0.8,
                spread_bps=4.0,
                atr=1.0,
                features=MarketFeatures(
                    trend=float(direction),
                    momentum=float(direction),
                    relative_volume=0.5,
                    volatility_expansion=0.2,
                    expected_move=2.0,
                    confidence=0.9,
                ),
            )
        )
    return bars


def test_replay_is_deterministic():
    config = ReplayConfig(initial_capital=100_000.0)
    a = run_replay(make_bars(), config)
    b = run_replay(make_bars(), config)
    assert a == b


def test_replay_never_exceeds_initial_capital_on_flat_data():
    bars = [
        ReplayBar(
            close=100.0,
            spread_bps=4.0,
            atr=1.0,
            features=MarketFeatures(
                trend=0.0,
                momentum=0.0,
                relative_volume=0.0,
                volatility_expansion=0.0,
                expected_move=0.0,
                confidence=0.0,
            ),
        )
        for _ in range(20)
    ]
    result = run_replay(bars)
    assert result.final_capital == result.initial_capital
    assert result.trades == ()


def test_adverse_execution_costs_are_accounted_for():
    result = run_replay(make_bars(direction=1), ReplayConfig(fee_rate=0.01, slippage_bps=50.0))
    if result.trades:
        assert all(t.costs > 0 for t in result.trades)
