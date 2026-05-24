"""STRATEGY STUB — setup/state-machine evaluation removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. `evaluate_setup` returns a
neutral IDLE setup so the app keeps running with empty states.

Implement the new setup logic here.
"""
from __future__ import annotations

from app.schemas.directional import (
    RegimeResult,
    SignalResult,
    SetupResult,
    TradeState,
    Direction,
    MacroRegime,
)


def evaluate_setup(
    regime: RegimeResult, signal: SignalResult, profile_label: str | None = None
) -> SetupResult:
    """Neutral setup: always IDLE / NEUTRAL (no strategy loaded)."""
    return SetupResult(
        state=TradeState.IDLE,
        direction=Direction.NEUTRAL,
        reason="strategy removed — no setup",
        macro_regime=regime.macro_regime if regime is not None else MacroRegime.IDLE,
        signal_trend=0,
    )
