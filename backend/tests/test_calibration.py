import pytest
from app.services.calibration import CalibrationService


def _make_svc() -> CalibrationService:
    svc = CalibrationService.__new__(CalibrationService)
    from collections import deque
    svc._db_path = ':memory:'
    svc._ivr_history = {}
    svc._closed_trades = deque(maxlen=CalibrationService.WIN_RATE_N)
    return svc


def test_win_rate_fallback():
    svc = _make_svc()
    assert svc.win_rate() == pytest.approx(0.52)


def test_win_rate_adapts():
    svc = _make_svc()
    for _ in range(8):
        svc._closed_trades.append({'pnl': 0.01, 'regime': 'BULL', 'ts': 0})
    for _ in range(2):
        svc._closed_trades.append({'pnl': -0.01, 'regime': 'BULL', 'ts': 0})
    assert svc.win_rate() == pytest.approx(0.8, abs=0.01)


def test_ivr_bands_static_fallback():
    svc = _make_svc()
    buy, sell = svc.ivr_bands('BTC')
    assert buy == pytest.approx(30.0)
    assert sell == pytest.approx(70.0)


def test_ivr_bands_adapt():
    svc = _make_svc()
    from collections import deque
    import numpy as np
    # Push 90 readings: mix of low and high IVR (20–80)
    ivrs = list(np.linspace(10, 90, 90))
    svc._ivr_history['BTC'] = deque(ivrs, maxlen=svc.IVR_WINDOW)
    buy, sell = svc.ivr_bands('BTC')
    # With a 10–90 range: 30th pct ≈ 33.6, 70th pct ≈ 66.4
    assert buy < 40.0
    assert sell > 60.0
