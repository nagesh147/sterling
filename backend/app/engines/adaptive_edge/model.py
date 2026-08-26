"""Deprecated compatibility shim for the abandoned reconstructed model.

The previous version of this module contained invented F-101..F-114 equations
(weights, thresholds, ATR multipliers, and option-selection heuristics). Those
are NOT part of the Master Mathematical Specification and must not execute.

Canonical Adaptive Edge mathematics lives in `canonical_math.py` and the
source-traceability document. This shim remains temporarily so stale imports
fail explicitly instead of silently executing provisional strategy logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ProvisionalAdaptiveEdgeModelError(RuntimeError):
    """Raised when deprecated reconstructed strategy logic is invoked."""


def _removed(name: str) -> None:
    raise ProvisionalAdaptiveEdgeModelError(
        f"{name} belongs to the deprecated reconstructed Adaptive Edge model; "
        "use the Master Mathematical Specification / canonical_math pipeline instead"
    )


@dataclass(frozen=True)
class MarketFeatures:
    trend: float
    momentum: float
    relative_volume: float
    volatility_expansion: float
    expected_move: float
    confidence: float
    stale: bool = False
    late_session: bool = False


def f101_feature_score(features: MarketFeatures) -> float:
    _removed("F-101 feature score")
    return 0.0


def f102_edge_score(feature_score: float) -> float:
    _removed("F-102 edge score")
    return 0.0


def f103_opportunity(**kwargs: Any) -> Any:
    _removed("F-103 opportunity")
    return None


def f104_dynamic_mode(**kwargs: Any) -> Any:
    _removed("F-104 dynamic mode")
    return None


def f105_profit_protection(**kwargs: Any) -> Any:
    _removed("F-105 profit protection")
    return None


def f106_dynamic_risk(**kwargs: Any) -> Any:
    _removed("F-106 dynamic risk")
    return None


def f107_risk_per_unit(**kwargs: Any) -> float:
    _removed("F-107 risk per unit")
    return 0.0


def f108_position_size(**kwargs: Any) -> int:
    _removed("F-108 position size")
    return 0


def f109_option_selection(**kwargs: Any) -> Any:
    _removed("F-109 option selection")
    return None


def f110_entry_trigger(**kwargs: Any) -> bool:
    _removed("F-110 entry trigger")
    return False


def f111_exit_trigger(**kwargs: Any) -> bool:
    _removed("F-111 exit trigger")
    return False


def f112_protection_parameters(**kwargs: Any) -> Any:
    _removed("F-112 protection parameters")
    return None


def f113_reentry_trigger(**kwargs: Any) -> bool:
    _removed("F-113 re-entry trigger")
    return False


def f114_position_interaction(**kwargs: Any) -> float:
    _removed("F-114 position interaction")
    return 0.0


def evaluate_reconstructed_model(**kwargs: Any) -> Any:
    _removed("reconstructed Adaptive Edge model")
    return None
