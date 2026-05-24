"""STRATEGY STUB — signal weights/thresholds removed in the strategy reset.

Only the `SignalThresholds` container remains (used as an optional type by the
`signal_engine` stub). All V4 tuning constants and the regime-aware weight
helper were removed for the clean-slate reset; the originals are preserved in
git history on the `strategy-v2` branch.

Define the new strategy's weights/thresholds here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SignalThresholds:
    """Placeholder thresholds container — populate when the new signal lands."""
    pass
