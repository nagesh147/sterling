"""F-101 trial evaluate: A196 robust+tanh on the A206 3-vector.

Does not unlock formula_registry. Does not accept production freeze
unless status is an explicit trial/dev artifact. No DeltaVelocity.
"""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .feature_engine import FeatureInput, FeatureStatus
from .features_f101 import EPSILON, F101_FEATURE_NAMES
from .formula_registry import FormulaStatus, get_formula

CLIP = 4.0
TRIAL_STATUS = "TRIAL_NOT_A197"
TRIAL_IN_SAMPLE_STATUS = "TRIAL_NOT_A197_IN_SAMPLE"
PRODUCTION_STATUSES = frozenset({"FROZEN", "PRODUCTION"})


@dataclass(frozen=True)
class F101Parameters:
    """Parameters required to evaluate F-101. Not a production freeze by default."""

    status: str
    w_short: int
    w_long: int
    med: Mapping[str, float]
    scale: Mapping[str, float]
    weights: Mapping[str, float]
    epsilon: float = EPSILON
    clip: float = CLIP

    def __post_init__(self) -> None:
        if self.w_short < 2 or self.w_short >= self.w_long:
            raise ValueError("A203: W_short >= 2 and W_short < W_long")
        names = set(F101_FEATURE_NAMES)
        if set(self.med) != names or set(self.scale) != names or set(self.weights) != names:
            raise ValueError("parameters must cover exactly the A206 feature names")
        weight_l1 = sum(abs(self.weights[n]) for n in F101_FEATURE_NAMES)
        if abs(weight_l1 - 1.0) > 1e-9:
            raise ValueError("A196: sum |w_i| must equal 1.0")
        object.__setattr__(self, "med", dict(self.med))
        object.__setattr__(self, "scale", dict(self.scale))
        object.__setattr__(self, "weights", dict(self.weights))

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status,
            "not_a197": True,
            "not_production_freeze": True,
            "w_short": self.w_short,
            "w_long": self.w_long,
            "window_label": "TRIAL_PLACEHOLDER_WINDOWS",
            "med": dict(self.med),
            "scale": dict(self.scale),
            "scale_meaning": "IQR (A196); evaluate divides by 1.349",
            "weights": dict(self.weights),
            "weight_label": "TRIAL_EQUAL_WEIGHTS",
            "epsilon": self.epsilon,
            "clip": self.clip,
        }


@dataclass(frozen=True)
class F101Result:
    score: float | None
    z: Mapping[str, float | None]
    status: FeatureStatus
    parameter_status: str


def _robust_z(x: float, med: float, scale: float, epsilon: float, clip: float) -> float:
    denom = max(scale / 1.349, epsilon)
    z = (x - med) / denom
    return max(-clip, min(clip, z))


def evaluate_f101(
    features: Mapping[str, FeatureInput],
    params: F101Parameters,
) -> F101Result:
    """Evaluate the A196 operator. Registry F-101 stays LOCKED."""
    if get_formula("F-101").status is FormulaStatus.IMPLEMENTED:
        raise RuntimeError("unexpected F-101 IMPLEMENTED during trial evaluate")
    if params.status.startswith("PRODUCTION") or params.status == "FROZEN":
        raise RuntimeError("production freeze artifacts are not accepted by trial evaluate")

    z_out: dict[str, float | None] = {}
    for name in F101_FEATURE_NAMES:
        item = features[name]
        if item.status is not FeatureStatus.VALID or item.value is None:
            return F101Result(
                score=None,
                z={n: None for n in F101_FEATURE_NAMES},
                status=FeatureStatus.MISSING,
                parameter_status=params.status,
            )
        z_out[name] = _robust_z(
            item.value,
            params.med[name],
            params.scale[name],
            params.epsilon,
            params.clip,
        )
    acc = sum(params.weights[n] * (z_out[n] or 0.0) for n in F101_FEATURE_NAMES)
    return F101Result(
        score=math.tanh(acc),
        z=z_out,
        status=FeatureStatus.VALID,
        parameter_status=params.status,
    )


def trial_identity_parameters(*, w_short: int, w_long: int) -> F101Parameters:
    """Unit-scale equal-weight trial params. Not learned. Not an A197 freeze."""
    n_features = len(F101_FEATURE_NAMES)
    return F101Parameters(
        status=TRIAL_STATUS,
        w_short=w_short,
        w_long=w_long,
        med={name: 0.0 for name in F101_FEATURE_NAMES},
        scale={name: 1.349 for name in F101_FEATURE_NAMES},
        weights={name: 1.0 / n_features for name in F101_FEATURE_NAMES},
    )


def _iqr(values: Sequence[float]) -> float:
    quantiles = statistics.quantiles(list(values), n=4, method="inclusive")
    return quantiles[2] - quantiles[0]


def estimate_trial_parameters(
    values: Mapping[str, Sequence[float]],
    *,
    w_short: int,
    w_long: int,
) -> F101Parameters:
    """In-sample median/IQR on a trial window. Status is TRIAL_NOT_A197_IN_SAMPLE."""
    if set(values) != set(F101_FEATURE_NAMES):
        raise ValueError("estimate_trial_parameters requires exactly the A206 feature names")
    med: dict[str, float] = {}
    scale: dict[str, float] = {}
    n_features = len(F101_FEATURE_NAMES)
    for name in F101_FEATURE_NAMES:
        series = [float(item) for item in values[name]]
        if len(series) < 4:
            raise ValueError(f"need at least 4 valid {name} observations to estimate trial IQR")
        med[name] = float(statistics.median(series))
        scale[name] = max(_iqr(series), EPSILON * 1.349)
    return F101Parameters(
        status=TRIAL_IN_SAMPLE_STATUS,
        w_short=w_short,
        w_long=w_long,
        med=med,
        scale=scale,
        weights={name: 1.0 / n_features for name in F101_FEATURE_NAMES},
    )


def load_f101_parameters(path: str | Path) -> F101Parameters:
    payload = json.loads(Path(path).read_text())
    status = str(payload.get("status") or "")
    if status in PRODUCTION_STATUSES or status.startswith("PRODUCTION"):
        raise RuntimeError("production freeze artifacts are not accepted by trial evaluate")
    return F101Parameters(
        status=status,
        w_short=int(payload["w_short"]),
        w_long=int(payload["w_long"]),
        med=payload["med"],
        scale=payload["scale"],
        weights=payload["weights"],
        epsilon=float(payload.get("epsilon", EPSILON)),
        clip=float(payload.get("clip", CLIP)),
    )


def dump_f101_parameters(params: F101Parameters, path: str | Path) -> None:
    if params.status in PRODUCTION_STATUSES or params.status.startswith("PRODUCTION"):
        raise RuntimeError("refusing to write a production freeze artifact from the trial path")
    destination = Path(path)
    if destination.name == "f101_parameters_v1.json":
        raise RuntimeError("refusing to write f101_parameters_v1.json from the trial path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(params.to_mapping(), indent=2, sort_keys=True) + "\n")
