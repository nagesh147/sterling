"""
Drawdown circuit breaker. Halts new trade evaluation when DD exceeds thresholds.
"""
from dataclasses import dataclass
from enum import Enum


class BreakerState(Enum):
    CLEAR   = "clear"
    WARNING = "warning"
    HALT    = "halt"
    RESET   = "reset"


@dataclass
class CircuitBreakerConfig:
    warn_dd:  float = 0.05
    halt_dd:  float = 0.10
    reset_dd: float = 0.15


class DrawdownCircuitBreaker:
    """Portfolio drawdown circuit breaker. Separate from the execution-level breaker."""

    def __init__(self, cfg: CircuitBreakerConfig, portfolio_value: float):
        self.cfg = cfg
        self._peak = portfolio_value
        self._state = BreakerState.CLEAR
        self._manual_halt = False

    def update(self, current_value: float) -> BreakerState:
        self._peak = max(self._peak, current_value)
        dd = (current_value - self._peak) / self._peak  # negative

        if self._manual_halt or dd <= -self.cfg.reset_dd:
            self._state = BreakerState.RESET
        elif dd <= -self.cfg.halt_dd:
            self._state = BreakerState.HALT
        elif dd <= -self.cfg.warn_dd:
            self._state = BreakerState.WARNING
        else:
            self._state = BreakerState.CLEAR

        return self._state

    @property
    def state(self) -> BreakerState:
        return self._state

    @property
    def peak(self) -> float:
        return self._peak

    def current_drawdown(self, current_value: float) -> float:
        if self._peak <= 0:
            return 0.0
        return (current_value - self._peak) / self._peak

    def size_multiplier(self) -> float:
        return {
            BreakerState.CLEAR:   1.0,
            BreakerState.WARNING: 0.5,
            BreakerState.HALT:    0.0,
            BreakerState.RESET:   0.0,
        }[self._state]

    def reset(self) -> None:
        """Manual reset endpoint. Clears RESET state → CLEAR."""
        self._manual_halt = False
        self._state = BreakerState.CLEAR
