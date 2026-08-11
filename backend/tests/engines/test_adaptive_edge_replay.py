from app.engines.adaptive_edge.model import MarketFeatures
from app.engines.adaptive_edge.replay import ReplayBar, replay


def test_replay_is_deterministic_and_cost_sensitive():
    bars = [
        ReplayBar(
            timestamp="2026-08-11T10:00:00",
            features=MarketFeatures(0.9, 0.8, 0.7, 0.4, 100, 0.9),
            execution_cost=5,
        ),
        ReplayBar(
            timestamp="2026-08-11T10:01:00",
            features=MarketFeatures(-0.2, -0.1, 0.1, 0.0, 20, 0.5),
            execution_cost=5,
        ),
    ]
    decisions_a, report_a = replay(bars)
    decisions_b, report_b = replay(bars)
    assert decisions_a == decisions_b
    assert report_a == report_b
    assert report_a.bars == 2
    assert report_a.eligible_bars == 1


def test_higher_cost_cannot_improve_expected_net_value():
    features = MarketFeatures(0.9, 0.8, 0.7, 0.4, 100, 0.9)
    _, cheap = replay([ReplayBar("t", features, 1)])
    _, expensive = replay([ReplayBar("t", features, 20)])
    assert expensive.total_expected_net_value <= cheap.total_expected_net_value
