"""Chronological walk-forward splitter with purge and embargo.

This module only defines dataset partitioning. Model fitting and promotion are
separate concerns, so a backtest cannot accidentally train on its holdout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .research_dataset import ResearchRow, validate_dataset


@dataclass(frozen=True)
class WalkForwardFold:
    fold_id: int
    train: tuple[ResearchRow, ...]
    validation: tuple[ResearchRow, ...]
    holdout: tuple[ResearchRow, ...]


def build_folds(
    rows: Sequence[ResearchRow],
    *,
    train_size: int,
    validation_size: int,
    holdout_size: int,
    step_size: int | None = None,
    purge_rows: int = 0,
    embargo_rows: int = 0,
) -> tuple[WalkForwardFold, ...]:
    dataset = validate_dataset(rows)
    if min(train_size, validation_size, holdout_size) <= 0:
        raise ValueError("window sizes must be positive")
    if min(purge_rows, embargo_rows) < 0:
        raise ValueError("purge and embargo cannot be negative")

    step = step_size or holdout_size
    if step <= 0:
        raise ValueError("step_size must be positive")

    folds: list[WalkForwardFold] = []
    start = 0
    fold_id = 0
    n = len(dataset)
    while True:
        train_end = start + train_size
        validation_start = train_end + purge_rows
        validation_end = validation_start + validation_size
        holdout_start = validation_end + purge_rows + embargo_rows
        holdout_end = holdout_start + holdout_size
        if holdout_end > n:
            break

        train = dataset[start:train_end]
        validation = dataset[validation_start:validation_end]
        holdout = dataset[holdout_start:holdout_end]
        folds.append(WalkForwardFold(fold_id, train, validation, holdout))
        fold_id += 1
        start += step

    return tuple(folds)
