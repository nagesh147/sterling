"""Causal walk-forward evaluation boundary operators for Adaptive Edge V2.

Source: A39 — Training / Validation / Test Walk-Forward Evaluation Contract.
Only source-defined temporal invariants are implemented here. Window lengths,
purge/embargo durations, statistical estimators, promotion thresholds, and
other unresolved strategy parameters are intentionally excluded.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class WalkForwardCycle:
    training_boundary: datetime
    validation_boundary: datetime
    promotion_time: datetime
    test_boundary: datetime

    def validate_causal_order(self) -> None:
        """Enforce A39's training < validation < promotion < test ordering."""
        if not (
            self.training_boundary
            < self.validation_boundary
            < self.promotion_time
            < self.test_boundary
        ):
            raise ValueError(
                "A39 causal ordering requires training < validation < promotion < test"
            )


def training_row_is_eligible(*, feature_available_time: datetime, decision_time: datetime, label_maturity_time: datetime, training_cutoff: datetime) -> bool:
    """Apply only the exact A38/A39 causal training predicates."""
    return feature_available_time <= decision_time and label_maturity_time <= training_cutoff


def promotion_is_before_test(*, promotion_time: datetime, test_start: datetime) -> bool:
    """A39: a promoted policy may affect decisions only before the test period."""
    return promotion_time < test_start
