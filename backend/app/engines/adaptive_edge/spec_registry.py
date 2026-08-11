"""Traceability registry for the Master Mathematical Specification v1.0.

The registry deliberately maps implementation concepts to specification
sections rather than pretending that the provisional F-101..F-114 numbering
was present in the original strategy document.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpecAnchor:
    anchor_id: str
    section: int
    name: str
    source_file: str
    implementation_module: str
    status: str


SOURCE = "adaptive-edge/Adaptive Order-Flow Options Scalping and Intraday Strategy.md"

ANCHORS: dict[str, SpecAnchor] = {
    "AE-MATH-PRICE": SpecAnchor("AE-MATH-PRICE", 7, "Price state operators", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-VOLUME": SpecAnchor("AE-MATH-VOLUME", 8, "Trade and incremental volume", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-AGGRESSOR": SpecAnchor("AE-MATH-AGGRESSOR", 9, "Aggressor classification", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-DELTA": SpecAnchor("AE-MATH-DELTA", 10, "Delta operators", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-LIQUIDITY": SpecAnchor("AE-MATH-LIQUIDITY", 11, "Liquidity state", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-VOLUME-INTENSITY": SpecAnchor("AE-MATH-VOLUME-INTENSITY", 12, "Volume intensity", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-VOLATILITY": SpecAnchor("AE-MATH-VOLATILITY", 13, "Volatility normalization", SOURCE, "canonical_math", "parameterized"),
    "AE-MATH-PROFILE": SpecAnchor("AE-MATH-PROFILE", 14, "Volume profile", SOURCE, "profile_engine", "specified"),
    "AE-MATH-FEATURE": SpecAnchor("AE-MATH-FEATURE", 18, "Feature vector", SOURCE, "feature_engine", "specified"),
    "AE-MATH-NORMALIZATION": SpecAnchor("AE-MATH-NORMALIZATION", 19, "Conditional statistical normalization", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-PROBABILITY": SpecAnchor("AE-MATH-PROBABILITY", 20, "Probability state", SOURCE, "probability_engine", "specified"),
    "AE-MATH-LOGISTIC": SpecAnchor("AE-MATH-LOGISTIC", 22, "Regularized multinomial logistic model", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-EMPIRICAL": SpecAnchor("AE-MATH-EMPIRICAL", 23, "Empirical similarity model", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-BAYES": SpecAnchor("AE-MATH-BAYES", 24, "Beta Bayesian state", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-CALIBRATION": SpecAnchor("AE-MATH-CALIBRATION", 25, "Probability calibration", SOURCE, "calibration_engine", "specified"),
    "AE-MATH-HORIZON": SpecAnchor("AE-MATH-HORIZON", 28, "Horizon distribution", SOURCE, "probability_engine", "specified"),
    "AE-MATH-EXECUTION-COST": SpecAnchor("AE-MATH-EXECUTION-COST", 31, "Execution cost", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-OPTION": SpecAnchor("AE-MATH-OPTION", 32, "Option selection", SOURCE, "economic_engine", "specified"),
    "AE-MATH-TARGET-STOP": SpecAnchor("AE-MATH-TARGET-STOP", 33, "Target/stop competition", SOURCE, "economic_engine", "implemented"),
    "AE-MATH-CONSERVATIVE-EV": SpecAnchor("AE-MATH-CONSERVATIVE-EV", 34, "Conservative expected value", SOURCE, "economic_engine", "parameterized"),
    "AE-MATH-RISK": SpecAnchor("AE-MATH-RISK", 36, "Initial risk and position sizing", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-CONTINUATION": SpecAnchor("AE-MATH-CONTINUATION", 39, "Continuation value", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-PROFIT": SpecAnchor("AE-MATH-PROFIT", 40, "Backward profit protection", SOURCE, "canonical_math", "parameterized"),
    "AE-MATH-STOP": SpecAnchor("AE-MATH-STOP", 41, "Monotonic protective stop", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-NO-RISK-EXPANSION": SpecAnchor("AE-MATH-NO-RISK-EXPANSION", 42, "No risk expansion", SOURCE, "canonical_math", "implemented"),
    "AE-MATH-WALK-FORWARD": SpecAnchor("AE-MATH-WALK-FORWARD", 51, "Walk-forward learning", SOURCE, "research", "specified"),
    "AE-MATH-VALIDATION": SpecAnchor("AE-MATH-VALIDATION", 55, "Model validation", SOURCE, "research", "specified"),
}


def get_anchor(anchor_id: str) -> SpecAnchor:
    return ANCHORS[anchor_id]
