import pytest

from app.engines.adaptive_edge.quote_features import mid, quote_features, spread, spread_bps


def test_mid_spread_and_spread_bps():
    assert mid(bid=99.0, ask=101.0) == 100.0
    assert spread(bid=99.0, ask=101.0) == 2.0
    assert spread_bps(bid=99.0, ask=101.0) == 200.0


def test_quote_features_bundle():
    result = quote_features(bid=99.0, ask=101.0)
    assert result.mid == 100.0
    assert result.spread == 2.0
    assert result.spread_bps == 200.0


def test_invalid_prices_are_rejected():
    with pytest.raises(ValueError):
        mid(bid=0.0, ask=101.0)
