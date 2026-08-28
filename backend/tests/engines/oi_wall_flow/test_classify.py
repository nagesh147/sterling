from app.engines.oi_wall_flow import OIWallFlowConfig, classify_side, max_pain, measure, walls_of


def test_four_flow_labels():
    cfg = OIWallFlowConfig()
    assert classify_side(10, 10, cfg) == "long_buildup"
    assert classify_side(-10, 10, cfg) == "short_covering"
    assert classify_side(10, -10, cfg) == "short_buildup"
    assert classify_side(-10, -10, cfg) == "long_unwinding"


def test_deadband_is_unchanged():
    cfg = OIWallFlowConfig(oi_chg_deadband_pct=0.5, ltp_chg_deadband_pct=0.5)
    assert classify_side(0.0, 25.0, cfg) == "unchanged"
    assert classify_side(-8.0, 0.2, cfg) == "unchanged"


def test_bse_walls_and_atm(bse_rows):
    walls = walls_of(bse_rows)
    assert walls.call_wall == 3500
    assert walls.put_wall == 3300
    m = measure(3392.50, bse_rows, OIWallFlowConfig())
    assert m.atm_strike == 3400
    assert m.total_call_oi > m.total_put_oi
    assert 0 < m.pcr_oi < 1


def test_bse_max_pain_is_a_listed_strike(bse_rows):
    pin = max_pain(bse_rows)
    assert pin in {r.strike for r in bse_rows}


def test_empty_chain_is_refused():
    import pytest
    with pytest.raises(ValueError, match="empty"):
        measure(100, [], OIWallFlowConfig())
