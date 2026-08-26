from app.engines.adaptive_edge.canonical_math import continuation_exit


def test_negative_conservative_continuation_value_exits():
    assert continuation_exit(-0.01) is True


def test_zero_conservative_continuation_value_exits():
    assert continuation_exit(0.0) is True


def test_positive_conservative_continuation_value_does_not_exit():
    assert continuation_exit(0.01) is False
