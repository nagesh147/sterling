import pytest

from app.engines.adaptive_edge.completeness_gate import (
    CompletenessGateError,
    REQUIRED_BOUNDARIES,
    Readiness,
    readiness,
    require_production_readiness,
    unresolved_boundaries,
)


def test_current_pipeline_is_research_only_for_explicit_unresolved_boundaries():
    unresolved = unresolved_boundaries()
    assert {item.boundary_id for item in unresolved} == {"A37", "A38", "A45", "A61"}
    assert readiness("2.1.0-proposed") is Readiness.RESEARCH_ONLY


def test_resolved_boundaries_still_require_explicit_promotion():
    resolved = tuple(
        item.__class__(item.boundary_id, True, True, True)
        for item in REQUIRED_BOUNDARIES
    )
    assert readiness("2.1.0-proposed", resolved) is Readiness.RESEARCH_ONLY
    with pytest.raises(CompletenessGateError, match="not production-promoted"):
        require_production_readiness("2.1.0-proposed", resolved)


def test_unresolved_boundary_fails_closed_even_if_strategy_is_named():
    with pytest.raises(CompletenessGateError, match="A37"):
        require_production_readiness("2.1.0-proposed")
