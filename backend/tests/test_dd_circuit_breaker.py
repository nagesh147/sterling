import pytest
from app.engines.risk.circuit_breaker import DrawdownCircuitBreaker, CircuitBreakerConfig, BreakerState


def _breaker(peak: float = 100_000.0) -> DrawdownCircuitBreaker:
    cfg = CircuitBreakerConfig(warn_dd=0.05, halt_dd=0.10, reset_dd=0.15)
    return DrawdownCircuitBreaker(cfg, portfolio_value=peak)


def test_clear_state_below_warn():
    b = _breaker()
    state = b.update(97_000.0)  # 3% DD
    assert state == BreakerState.CLEAR


def test_warning_state():
    b = _breaker()
    state = b.update(93_000.0)  # 7% DD
    assert state == BreakerState.WARNING
    assert b.size_multiplier() == pytest.approx(0.5)


def test_halt_state():
    b = _breaker()
    state = b.update(88_000.0)  # 12% DD
    assert state == BreakerState.HALT
    assert b.size_multiplier() == pytest.approx(0.0)


def test_reset_required_at_15pct():
    b = _breaker()
    state = b.update(84_000.0)  # 16% DD
    assert state == BreakerState.RESET


def test_manual_reset():
    b = _breaker()
    b.update(84_000.0)  # → RESET
    b.reset()
    assert b.state == BreakerState.CLEAR


def test_peak_tracking():
    b = _breaker(100_000.0)
    b.update(110_000.0)  # value rises → peak updates
    assert b.peak == pytest.approx(110_000.0)
    state = b.update(100_000.0)  # only 9.1% from new peak
    assert state == BreakerState.WARNING  # 100k/110k = 9.1% DD
