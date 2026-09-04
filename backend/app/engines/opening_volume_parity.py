"""Deterministic multi-session comparison of ORION observations and Sterling scans."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def _time(value: object) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if "T" in text:
        text = text.split("T", 1)[1]
    return text[:5]


def compare_opening_sessions(
    orion_rows: Iterable[dict[str, Any]],
    sterling_rows: Iterable[dict[str, Any]],
    *,
    rvol_tolerance: float = 0.05,
) -> dict[str, Any]:
    """Compare only observable fields; private score parity is never inferred."""

    if rvol_tolerance < 0:
        raise ValueError("rvol_tolerance must be non-negative")
    fields = ("direction", "tier", "signal_time", "orb_break_time", "combo")

    def index(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        out: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            session = str(row.get("session_date") or "")[:10]
            symbol = str(row.get("symbol") or "").strip().upper()
            if not session or not symbol:
                raise ValueError("every comparison row requires session_date and symbol")
            key = (session, symbol)
            if key in out:
                raise ValueError(f"duplicate comparison row: {session}:{symbol}")
            out[key] = row
        return out

    expected = index(orion_rows)
    actual = index(sterling_rows)
    keys = sorted(set(expected) | set(actual))
    by_session: dict[str, dict[str, int]] = defaultdict(
        lambda: {"expected": 0, "matched": 0, "missing": 0, "extra": 0, "mismatched": 0}
    )
    comparisons: list[dict[str, Any]] = []
    for session, symbol in keys:
        left = expected.get((session, symbol))
        right = actual.get((session, symbol))
        metrics = by_session[session]
        if left is None:
            metrics["extra"] += 1
            comparisons.append(
                {
                    "session_date": session,
                    "symbol": symbol,
                    "status": "extra",
                    "mismatches": [],
                }
            )
            continue
        metrics["expected"] += 1
        if right is None:
            metrics["missing"] += 1
            comparisons.append(
                {
                    "session_date": session,
                    "symbol": symbol,
                    "status": "missing",
                    "mismatches": [],
                }
            )
            continue
        mismatches: list[str] = []
        for field in fields:
            left_value = _time(left.get(field)) if field.endswith("_time") else left.get(field)
            right_value = _time(right.get(field)) if field.endswith("_time") else right.get(field)
            if left_value != right_value:
                mismatches.append(field)
        try:
            if abs(float(left.get("rvol")) - float(right.get("rvol"))) > rvol_tolerance:
                mismatches.append("rvol")
        except (TypeError, ValueError):
            mismatches.append("rvol")
        status = "match" if not mismatches else "mismatch"
        metrics["matched" if status == "match" else "mismatched"] += 1
        comparisons.append(
            {
                "session_date": session,
                "symbol": symbol,
                "status": status,
                "mismatches": mismatches,
            }
        )

    expected_count = len(expected)
    matched_count = sum(row["status"] == "match" for row in comparisons)
    missing_count = sum(row["status"] == "missing" for row in comparisons)
    extra_count = sum(row["status"] == "extra" for row in comparisons)
    mismatch_count = sum(row["status"] == "mismatch" for row in comparisons)
    return {
        "sessions": [
            {"session_date": session, **counts}
            for session, counts in sorted(by_session.items())
        ],
        "summary": {
            "session_count": len(by_session),
            "expected_count": expected_count,
            "matched_count": matched_count,
            "missing_count": missing_count,
            "extra_count": extra_count,
            "mismatched_count": mismatch_count,
            "recall_pct": round(matched_count / expected_count * 100.0, 2)
            if expected_count
            else None,
            "exact_match": bool(
                expected_count
                and matched_count == expected_count
                and not extra_count
            ),
        },
        "comparisons": comparisons,
        "scope": "observable fields only; proprietary score and Momentum Lab internals excluded",
    }
