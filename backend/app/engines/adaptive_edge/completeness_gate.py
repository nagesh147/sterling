"""Fail-closed readiness gate for the complete Adaptive Edge pipeline.

The gate distinguishes implementation completeness from source-semantic
completeness and promotion. It never upgrades an unresolved mathematical or
provider dependency merely because an implementation exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .promotion import is_promoted


class CompletenessGateError(RuntimeError):
    """Raised when a pipeline asks to cross an unresolved boundary."""


class Readiness(str, Enum):
    RESEARCH_ONLY = "research_only"
    PRODUCTION = "production"


@dataclass(frozen=True)
class BoundaryStatus:
    boundary_id: str
    implemented: bool
    semantics_resolved: bool
    source_defined: bool
    blocker: str | None = None

    @property
    def closed(self) -> bool:
        return self.implemented and self.semantics_resolved and self.source_defined


REQUIRED_BOUNDARIES: tuple[BoundaryStatus, ...] = (
    BoundaryStatus("A37", True, False, True, "provider/accounting semantics remain unresolved"),
    BoundaryStatus("A38", True, False, True, "target/horizon label semantics remain unresolved"),
    BoundaryStatus("A39", True, True, True),
    BoundaryStatus("A40", True, True, True),
    BoundaryStatus("A41", True, True, True),
    BoundaryStatus("A42", True, True, True),
    BoundaryStatus("A43", True, True, True),
    BoundaryStatus("A44", True, True, True),
    BoundaryStatus("A45", True, False, True, "provider accounting semantics remain unresolved"),
    BoundaryStatus("A46", True, True, True),
    BoundaryStatus("A47", True, True, True),
    BoundaryStatus("A48", True, True, True),
    BoundaryStatus("A49", True, True, True),
    BoundaryStatus("A50", True, True, True),
    BoundaryStatus("A51", True, True, True),
    BoundaryStatus("A52", True, True, True),
    BoundaryStatus("A53", True, True, True),
    BoundaryStatus("A54", True, True, True),
    BoundaryStatus("A55", True, True, True),
    BoundaryStatus("A56", True, True, True),
    BoundaryStatus("A57", True, True, True),
    BoundaryStatus("A58", True, True, True),
    BoundaryStatus("A59", True, True, True),
    BoundaryStatus("A60", True, True, True),
    BoundaryStatus("A61", True, False, True, "execution/accounting provider semantics remain unresolved"),
)


def unresolved_boundaries(
    boundaries: Iterable[BoundaryStatus] = REQUIRED_BOUNDARIES,
) -> tuple[BoundaryStatus, ...]:
    return tuple(boundary for boundary in boundaries if not boundary.closed)


def readiness(
    strategy_version: str,
    boundaries: Iterable[BoundaryStatus] = REQUIRED_BOUNDARIES,
) -> Readiness:
    unresolved = unresolved_boundaries(boundaries)
    if unresolved or not is_promoted(strategy_version):
        return Readiness.RESEARCH_ONLY
    return Readiness.PRODUCTION


def require_production_readiness(
    strategy_version: str,
    boundaries: Iterable[BoundaryStatus] = REQUIRED_BOUNDARIES,
) -> None:
    unresolved = unresolved_boundaries(boundaries)
    if unresolved:
        details = "; ".join(
            f"{item.boundary_id}: {item.blocker or 'unresolved'}"
            for item in unresolved
        )
        raise CompletenessGateError(f"Adaptive Edge remains research-only: {details}")
    if not is_promoted(strategy_version):
        raise CompletenessGateError(
            f"strategy {strategy_version} is not production-promoted"
        )
