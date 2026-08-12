"""Source-defined temporal guards for Adaptive Edge V2 learning.

Source: A38 — Label Maturity, Outcome Construction and Learning Boundary.
Only exact temporal boundary predicates are implemented here. Target, horizon,
label function, model update policy, purge/embargo policy, and learned
parameters remain outside this module until their source definitions exist.
"""
from __future__ import annotations

from datetime import datetime


def feature_is_causally_available(*, feature_available_time: datetime, decision_time: datetime) -> bool:
    """A38 §11: feature_available_time <= decision_time."""
    return feature_available_time <= decision_time


def label_is_mature_for_training(*, label_maturity_time: datetime, training_cutoff_time: datetime) -> bool:
    """A38 §10/§22: label_maturity_time <= training cutoff."""
    return label_maturity_time <= training_cutoff_time


def training_row_is_causally_eligible(*, feature_available_time: datetime, decision_time: datetime, label_maturity_time: datetime, training_cutoff_time: datetime) -> bool:
    """Apply only the exact A38 temporal predicates."""
    return feature_is_causally_available(feature_available_time=feature_available_time, decision_time=decision_time) and label_is_mature_for_training(label_maturity_time=label_maturity_time, training_cutoff_time=training_cutoff_time)
