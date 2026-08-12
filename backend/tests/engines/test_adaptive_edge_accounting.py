from app.engines.adaptive_edge.accounting import profit_giveback, snapshot, update_peak_pnl


def test_peak_pnl_is_monotonic():
    assert update_peak_pnl(None, 10.0) == 10.0
    assert update_peak_pnl(10.0, 8.0) == 10.0
    assert update_peak_pnl(10.0, 12.0) == 12.0


def test_profit_giveback_is_peak_minus_current():
    assert profit_giveback(20.0, 15.0) == 5.0


def test_snapshot_uses_authoritative_current_pnl():
    result = snapshot(10.0, 7.0)
    assert result.current_pnl == 7.0
    assert result.peak_pnl == 10.0
    assert result.profit_giveback == 3.0
