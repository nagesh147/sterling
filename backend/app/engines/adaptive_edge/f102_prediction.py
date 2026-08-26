"""Research-only F-102 multinomial directional probability evaluator."""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite
from types import MappingProxyType
from typing import Mapping, Sequence

from .feature_engine import FeatureSnapshot, FeatureStatus


CLASSES = ("UP", "DOWN", "NEUTRAL")


@dataclass(frozen=True)
class F102Prediction:
    formula_id: str
    formula_version: str
    probabilities: Mapping[str, float]
    directional_edge: float
    preferred_direction: str


@dataclass(frozen=True)
class F102MultinomialModel:
    """Frozen coefficient set for a research-time V1 baseline model."""

    formula_id: str
    formula_version: str
    feature_names: tuple[str, ...]
    coefficients: Mapping[str, tuple[float, ...]]
    intercepts: Mapping[str, float]

    def __post_init__(self) -> None:
        if self.formula_id != "F-102":
            raise ValueError("F-102 model requires formula_id F-102")
        if len(self.feature_names) == 0:
            raise ValueError("F-102 requires at least one feature")
        for class_name in CLASSES:
            row = self.coefficients.get(class_name)
            if row is None or len(row) != len(self.feature_names):
                raise ValueError(f"invalid coefficient vector for {class_name}")
            if any(not isfinite(v) for v in row):
                raise ValueError(f"non-finite coefficient for {class_name}")
            intercept = self.intercepts.get(class_name)
            if intercept is None or not isfinite(intercept):
                raise ValueError(f"invalid intercept for {class_name}")
        object.__setattr__(self, "coefficients", MappingProxyType(dict(self.coefficients)))
        object.__setattr__(self, "intercepts", MappingProxyType(dict(self.intercepts)))

    def predict(self, snapshot: FeatureSnapshot) -> F102Prediction:
        snapshot.assert_causal(snapshot.decision_time)
        x: list[float] = []
        for name in self.feature_names:
            if name not in snapshot.values:
                raise ValueError(f"missing F-102 feature: {name}")
            if snapshot.statuses[name] is not FeatureStatus.VALID:
                raise ValueError(f"invalid F-102 feature status: {name}")
            value = snapshot.values[name]
            if value is None or not isfinite(value):
                raise ValueError(f"invalid F-102 feature value: {name}")
            x.append(value)

        logits = {
            class_name: self.intercepts[class_name]
            + sum(weight * value for weight, value in zip(self.coefficients[class_name], x))
            for class_name in CLASSES
        }
        max_logit = max(logits.values())
        exponentials = {name: exp(value - max_logit) for name, value in logits.items()}
        denominator = sum(exponentials.values())
        probabilities = {name: exponentials[name] / denominator for name in CLASSES}

        up = probabilities["UP"]
        down = probabilities["DOWN"]
        neutral = probabilities["NEUTRAL"]
        edge = max(up, down) - neutral
        direction = "UP" if up > down else "DOWN" if down > up else "NONE"

        return F102Prediction(
            formula_id=self.formula_id,
            formula_version=self.formula_version,
            probabilities=MappingProxyType(probabilities),
            directional_edge=edge,
            preferred_direction=direction,
        )


def build_f102_model(
    feature_names: Sequence[str],
    coefficients: Mapping[str, Sequence[float]],
    intercepts: Mapping[str, float],
    *,
    formula_version: str = "1.0-research",
) -> F102MultinomialModel:
    """Build a frozen research model; coefficients must come from training."""
    return F102MultinomialModel(
        formula_id="F-102",
        formula_version=formula_version,
        feature_names=tuple(feature_names),
        coefficients={name: tuple(values) for name, values in coefficients.items()},
        intercepts=dict(intercepts),
    )
