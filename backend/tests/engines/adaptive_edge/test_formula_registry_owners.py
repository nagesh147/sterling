"""Every formula's declared owner must resolve to real code.

A167 makes the implementation owner part of the conformance record, so an owner
that names nothing is a false claim of implementation — and it fails quietly,
because nothing dereferences the string.

It fails worse than quietly. "execution" was a dangling owner for F-007/F-008
until an unrelated execution.py was added for order-price arithmetic, at which
point the stale label started resolving to a module that has nothing to do with
executable BUY/SELL references. A wrong owner that resolves is harder to spot
than one that does not.
"""
from __future__ import annotations

import pathlib

import pytest

from app.engines.adaptive_edge.formula_registry import FORMULAS

_ROOT = pathlib.Path(__file__).resolve().parents[3] / "app" / "engines" / "adaptive_edge"


def _modules() -> set[str]:
    return {p.stem for p in _ROOT.glob("*.py")}


@pytest.mark.parametrize("formula_id", sorted(FORMULAS))
def test_every_owner_names_a_module_in_this_package(formula_id):
    owner = FORMULAS[formula_id].owner
    assert owner, f"{formula_id} has no owner"
    assert owner in _modules(), (
        f"{formula_id} claims owner {owner!r}, which is not a module in "
        f"app/engines/adaptive_edge. An owner that names nothing is a false "
        f"claim of implementation."
    )


# A second test tried to check that the owner module shows some *trace* of the
# formula it owns — the id, an f1xx symbol, or a word from the canonical name.
# It is not here because it could not be made to mean anything. Whole words gave
# false positives (risk_engine states F-006's invariant as "independent" where
# the name says "independence"); word stems gave false negatives (accounting.py
# contains "author", from "authoritative", so it passes as the owner of "Risk
# authorization immutability"). A check that cannot separate a correct owner
# from a wrong one is worse than no check, because it reads as coverage.
#
# What actually catches this is the test above plus review: an owner has to name
# a real module, and whether it names the RIGHT one is a judgement a person makes
# when they change the mapping.
