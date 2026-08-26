"""Conformance reporting: does our replay match what the recording printed?

The golden tests assert equality. This module produces the human-readable
*table* of that comparison -- field by field, with the observed value, the
replayed value and a verdict -- so a conformance report can be regenerated
rather than hand-written and left to rot.

Verdicts are deliberately blunt:

* ``MATCH``      -- replay equals the observed value.
* ``MISMATCH``   -- it does not. A real failure.
* ``UNVERIFIED`` -- the recording never established this field, so there is
  nothing to compare against. **Not** a pass.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from .models import q2

MATCH = "MATCH"
MISMATCH = "MISMATCH"
UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class FieldComparison:
    field: str
    observed: Optional[Any]
    replayed: Optional[Any]
    verdict: str
    evidence: str = ""

    @property
    def ok(self) -> bool:
        return self.verdict == MATCH


def compare(
    field: str,
    observed: Optional[Any],
    replayed: Optional[Any],
    *,
    evidence: str = "",
    tolerance: float = 0.0,
) -> FieldComparison:
    """Compare one field. An absent observation is UNVERIFIED, never a pass."""
    if observed is None:
        return FieldComparison(field, None, replayed, UNVERIFIED, evidence)
    verdict = MISMATCH
    if isinstance(observed, (int, float)) and isinstance(replayed, (int, float)):
        if abs(float(observed) - float(replayed)) <= tolerance:
            verdict = MATCH
    elif observed == replayed:
        verdict = MATCH
    return FieldComparison(field, observed, replayed, verdict, evidence)


#: Which summary key each observed field maps onto, plus its A231 citation.
_FIELD_MAP: tuple[tuple[str, str, str], ...] = (
    ("strike", "strike", "A231/M4"),
    ("option", "option", "A231/M4"),
    ("quantity", "quantity", "A231/X6"),
    ("entry_order_price", "entry_order_price", "A231/E2"),
    ("entry", "entry", "A231/E6"),
    ("target", "target", "A231/X1"),
    ("trigger", "trigger", "A231/X4"),
    ("exit_order_price", "exit_order_price", "A231/X3"),
    ("exit", "exit", "A231/X4"),
    ("points", "points", "A231/X5"),
    ("pnl", "pnl", "A231/X6"),
    ("attempts", "attempts", "A231/E1"),
)


def build_report(
    *,
    case: str,
    observed: dict[str, Any],
    summary: dict[str, Any],
    tolerance: float = 0.0,
) -> dict[str, Any]:
    """Compare a completed replay's ``summary()`` against observed values.

    ``observed`` need only carry the fields the recording actually established.
    Anything absent is reported UNVERIFIED, which is the whole point: a report
    that silently omits what it could not check reads as full coverage.
    """
    rows = [
        compare(field, observed.get(field), summary.get(key), evidence=cite, tolerance=tolerance)
        for field, key, cite in _FIELD_MAP
    ]
    return {
        "case": case,
        "match": sum(1 for r in rows if r.verdict == MATCH),
        "mismatch": sum(1 for r in rows if r.verdict == MISMATCH),
        "unverified": sum(1 for r in rows if r.verdict == UNVERIFIED),
        "conformant": all(r.verdict != MISMATCH for r in rows),
        "rows": [
            {
                "field": r.field, "observed": r.observed, "replayed": r.replayed,
                "verdict": r.verdict, "evidence": r.evidence,
            }
            for r in rows
        ],
    }


def format_report(report: dict[str, Any]) -> str:
    """Render as a markdown table for the validation report."""
    lines = [
        f"### {report['case']}",
        "",
        f"{report['match']} match · {report['mismatch']} mismatch · "
        f"{report['unverified']} unverified · "
        f"conformant: {'yes' if report['conformant'] else 'NO'}",
        "",
        "| Field | Observed | Replayed | Verdict | Evidence |",
        "|---|---|---|---|---|",
    ]
    for row in report["rows"]:
        obs = "—" if row["observed"] is None else row["observed"]
        rep = "—" if row["replayed"] is None else row["replayed"]
        lines.append(
            f"| {row['field']} | {obs} | {rep} | {row['verdict']} | {row['evidence']} |"
        )
    return "\n".join(lines)


def straddle_parity_strike(underlying_ltp: float, ce: float, pe: float) -> float:
    """``K ~= S + (PE - CE)`` -- put-call parity, for same-day expiry.

    A forensic aid only, and an unreliable one at the open: CE and PE
    last-traded prices are independently stale in the first tick after the
    auction, which is why V17's parity estimate (77686) disagrees with its
    printed strike (77600). Never use this to *choose* a strike.
    """
    return q2(float(underlying_ltp) + (float(pe) - float(ce)))
