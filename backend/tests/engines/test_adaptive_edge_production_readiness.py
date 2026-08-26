from __future__ import annotations

from app.engines.adaptive_edge.production_readiness import production_readiness


def test_production_readiness_exposes_unresolved_f114() -> None:
    items = {item.name: item for item in production_readiness()}
    assert "f114_portfolio_model" in items
    assert items["f114_portfolio_model"].ready is False
    assert "unresolved" in items["f114_portfolio_model"].detail.lower()


def test_locked_formula_registry_cannot_be_reported_as_implemented() -> None:
    items = {item.name: item for item in production_readiness()}
    assert items["formula_registry_implemented"].ready is False
