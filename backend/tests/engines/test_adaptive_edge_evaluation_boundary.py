from datetime import datetime, timezone

from app.engines.adaptive_edge.evaluation_boundary import WalkForwardCycle, promotion_is_before_test, training_row_is_eligible

UTC = timezone.utc


def test_walk_forward_cycle_requires_causal_order():
    cycle = WalkForwardCycle(
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 2, 1, tzinfo=UTC),
        datetime(2026, 2, 2, tzinfo=UTC),
        datetime(2026, 3, 1, tzinfo=UTC),
    )
    cycle.validate_causal_order()


def test_training_row_requires_feature_and_label_causality():
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    assert training_row_is_eligible(
        feature_available_time=datetime(2026, 1, 2, tzinfo=UTC),
        decision_time=datetime(2026, 1, 3, tzinfo=UTC),
        label_maturity_time=datetime(2026, 1, 31, tzinfo=UTC),
        training_cutoff=cutoff,
    )


def test_promotion_must_precede_test():
    assert promotion_is_before_test(
        promotion_time=datetime(2026, 2, 2, tzinfo=UTC),
        test_start=datetime(2026, 3, 1, tzinfo=UTC),
    )
