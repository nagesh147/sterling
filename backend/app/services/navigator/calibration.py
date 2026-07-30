"""Navigator calibration: score the decisions Navigator actually made
against what the market actually did next, then check that record against
the promotion criteria that gate `calibration_readiness` (spec §19.3–19.5).

Three rules this module exists to enforce:

1. **Nothing here ever promotes anything.** `evaluate_criteria` reports
   pass/fail and nothing else. Flipping `calibration_readiness` is a
   separate, explicit, human-triggered action
   (`config_store.promote_calibration`). A report that passes every
   criterion still changes nothing on its own.
2. **No lookahead.** A decision made at `bar_close_ms` is scored only
   against bars that closed STRICTLY AFTER it, and a decision without
   enough forward bars yet is left UNSCORED rather than counted either
   way. `score_decisions` is a pure function so this is directly testable.
3. **The split is chronological and on session boundaries.** The
   evaluation window is untouched by anything the calibration window saw,
   and no single trading session straddles both.

Deliberately NOT implemented (and reported as such rather than faked):
the rest of the §19.4 metric suite — Brier score, MAE/MFE tails, the
ablation ladder, and slippage/cost modelling. Those need the replay
harness and live chain capture, neither of which is wired. **Returns here
are gross**: no brokerage, spread, or slippage is deducted, so expectancy
is an upper bound, and the report says so in `caveats`.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Sequence

from app.core.logging import get_logger
from app.engines.navigator.schemas import canonical_json_hash
from app.services.navigator.calendar import IST

log = get_logger(__name__)

MODEL_VERSION = "navigator_calibration_v1"

#: Bars ahead of the decision bar used to judge "was this right". 6 × 1H ≈
#: one trading session — long enough for a 1H structural read to play out,
#: short enough that a stale call isn't credited with a later unrelated
#: move. CALIBRATION-REQUIRED: revisit once real forward data exists.
DEFAULT_HORIZON_BARS = 6

#: A decision is only a directional CALL when Navigator committed to one.
#: WAIT / NO_DATA / CONFLICT are abstentions — standing aside is the whole
#: point of the gate, and scoring it as "wrong" would punish exactly the
#: behaviour we want. They're counted separately instead.
ACTIONABLE_STATUSES = ("CONFIRMED", "HIGH_CONVICTION")

CAVEATS = [
    "Returns are gross — no brokerage, spread, or slippage is deducted, so "
    "expectancy here is an upper bound.",
    "Scored against the underlying's own forward price move, not against a "
    "realised option fill.",
    "Does not yet include the spec's full metric suite (Brier score, MAE/MFE "
    "tails, component ablations) — those need the replay harness.",
]


@dataclass(frozen=True)
class PricePoint:
    bar_close_ms: int
    close: float


@dataclass
class StatusBreakdown:
    status: str
    count: int = 0
    scored: int = 0
    hits: int = 0
    sum_return_pct: float = 0.0

    @property
    def hit_rate(self) -> Optional[float]:
        return (self.hits / self.scored) if self.scored else None

    @property
    def mean_return_pct(self) -> Optional[float]:
        return (self.sum_return_pct / self.scored) if self.scored else None

    def as_dict(self) -> dict:
        return {
            "status": self.status, "count": self.count, "scored": self.scored,
            "hits": self.hits, "hit_rate": self.hit_rate,
            "mean_return_pct": self.mean_return_pct,
        }


@dataclass
class WindowMetrics:
    """One chronological slice — `calibration` (tuned on) or `evaluation`
    (untouched, and what the promotion criteria actually judge)."""
    label: str
    first_bar_close_ms: Optional[int] = None
    last_bar_close_ms: Optional[int] = None
    session_dates: set = field(default_factory=set)
    total_decisions: int = 0
    actionable: int = 0
    actionable_scored: int = 0
    actionable_hits: int = 0
    actionable_sum_return_pct: float = 0.0
    no_data: int = 0
    unscorable: int = 0
    by_status: dict = field(default_factory=dict)

    @property
    def sessions(self) -> int:
        return len(self.session_dates)

    @property
    def hit_rate(self) -> Optional[float]:
        return (self.actionable_hits / self.actionable_scored) if self.actionable_scored else None

    @property
    def mean_return_pct(self) -> Optional[float]:
        return (self.actionable_sum_return_pct / self.actionable_scored) if self.actionable_scored else None

    @property
    def no_data_rate(self) -> Optional[float]:
        return (self.no_data / self.total_decisions) if self.total_decisions else None

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "first_bar_close_ms": self.first_bar_close_ms,
            "last_bar_close_ms": self.last_bar_close_ms,
            "sessions": self.sessions,
            "session_dates": sorted(self.session_dates),
            "total_decisions": self.total_decisions,
            "actionable": self.actionable,
            "actionable_scored": self.actionable_scored,
            "actionable_hits": self.actionable_hits,
            "hit_rate": self.hit_rate,
            "mean_return_pct": self.mean_return_pct,
            "no_data": self.no_data,
            "no_data_rate": self.no_data_rate,
            "unscorable": self.unscorable,
            "by_status": {k: v.as_dict() for k, v in sorted(self.by_status.items())},
        }


def session_date(bar_close_ms: int) -> str:
    """IST calendar date of a bar close — the unit the spec counts sessions in."""
    return datetime.fromtimestamp(bar_close_ms / 1000, tz=IST).strftime("%Y-%m-%d")


def _index_series(series: Sequence[PricePoint]) -> tuple[dict[int, int], list[PricePoint]]:
    ordered = sorted(series, key=lambda p: p.bar_close_ms)
    return {p.bar_close_ms: i for i, p in enumerate(ordered)}, ordered


def _forward_return(
    index: dict[int, int], ordered: list[PricePoint], bar_close_ms: int, horizon_bars: int,
) -> Optional[float]:
    """Percent move from the decision's own bar to `horizon_bars` later.

    None when the decision genuinely cannot be judged yet — its bar isn't in
    the series, or the market hasn't produced enough bars after it. A
    decision from an hour ago has no verdict, and must never be counted as
    either a hit or a miss. Only bars strictly after the decision bar are
    consulted, so no future information can leak into the entry reference.
    """
    entry_idx = index.get(bar_close_ms)
    if entry_idx is None:
        return None
    exit_idx = entry_idx + horizon_bars
    if exit_idx >= len(ordered):
        return None
    entry = ordered[entry_idx].close
    if entry <= 0:
        return None
    return (ordered[exit_idx].close - entry) / entry * 100.0


def _split_on_session_boundary(ordered: Sequence[dict], split_ratio: float) -> int:
    """Index of the first decision belonging to the evaluation window.

    Splits between SESSIONS, never inside one: a single trading day must not
    contribute to both the tuning window and the supposedly-untouched
    evaluation window. Returns len(ordered) when there aren't at least two
    distinct sessions to split across (everything stays in calibration and
    the evaluation window is honestly empty).
    """
    sessions: list[str] = []
    for d in ordered:
        s = session_date(int(d["bar_close_ms"]))
        if not sessions or sessions[-1] != s:
            sessions.append(s)
    if len(sessions) < 2:
        return len(ordered)
    cutoff_session = sessions[max(1, int(len(sessions) * split_ratio))]
    for i, d in enumerate(ordered):
        if session_date(int(d["bar_close_ms"])) == cutoff_session:
            return i
    return len(ordered)


#: Strength order used to pick the one decision that represents a bar. Higher
#: wins, so a bar Navigator ever called CONFIRMED is scored as a CONFIRMED call
#: even if it later cooled to WATCH — a trader acting on it would have taken
#: the trade, and that is what the hit rate is measuring.
_STATUS_STRENGTH = {
    "NO_DATA": 0, "WAIT": 1, "CONFLICT": 2, "WATCH": 3, "CONFIRMED": 4, "HIGH_CONVICTION": 5,
}


def collapse_to_one_per_opportunity(decisions: Sequence[dict]) -> list[dict]:
    """One decision per (underlying, direction, bar) — the unit of measurement.

    Navigator legitimately writes about the same bar more than once: a WATCH
    that becomes CONFIRMED as later evidence lands, and Structure Radar's own
    read of an instrument alongside Navigator's read of a real SuperTrend row
    on it. Every one of those shares a single forward return, so scoring them
    all counts one market outcome several times — which inflates the sample
    against `MIN_EVALUATION_SCORED` and understates variance in the very gate
    that guards real-money auto-execution.

    Keeps the strongest conclusion reached for each bar, breaking ties on the
    latest `generated_at_ms` and then `decision_id` so the result is stable.
    """
    best: dict[tuple, dict] = {}
    for d in decisions:
        key = (str(d["underlying"]), str(d["direction"]), int(d["bar_close_ms"]))
        rank = (
            _STATUS_STRENGTH.get(str(d["status"]), 0),
            int(d.get("generated_at_ms") or 0),
            str(d["decision_id"]),
        )
        current = best.get(key)
        if current is None or rank > current[0]:
            best[key] = (rank, d)
    return [d for _rank, d in best.values()]


def score_decisions(
    decisions: Sequence[dict],
    price_series: dict[str, Sequence[PricePoint]],
    *,
    horizon_bars: int = DEFAULT_HORIZON_BARS,
    split_ratio: float = 0.7,
) -> dict:
    """Pure: persisted `navigator_signal_events` rows + price history ->
    a calibration report. No I/O, no clock reads beyond the data itself.

    Rows are collapsed to one per (underlying, direction, bar) first — see
    `collapse_to_one_per_opportunity` — so every count below is a count of
    distinct market opportunities, not of times Navigator wrote something down.
    """
    collapsed = collapse_to_one_per_opportunity(decisions)
    ordered = sorted(collapsed, key=lambda d: (int(d["bar_close_ms"]), str(d["decision_id"])))
    split_at = _split_on_session_boundary(ordered, split_ratio)
    indexed = {name: _index_series(s) for name, s in price_series.items()}
    windows = {
        "calibration": WindowMetrics("calibration"),
        "evaluation": WindowMetrics("evaluation"),
    }

    for i, d in enumerate(ordered):
        w = windows["calibration"] if i < split_at else windows["evaluation"]
        bar_close_ms = int(d["bar_close_ms"])
        status = str(d["status"])

        w.total_decisions += 1
        w.session_dates.add(session_date(bar_close_ms))
        if w.first_bar_close_ms is None:
            w.first_bar_close_ms = bar_close_ms
        w.last_bar_close_ms = bar_close_ms

        bucket = w.by_status.setdefault(status, StatusBreakdown(status))
        bucket.count += 1
        if status == "NO_DATA":
            w.no_data += 1
            continue
        if status not in ACTIONABLE_STATUSES:
            continue

        w.actionable += 1
        series = indexed.get(str(d["underlying"]))
        ret = _forward_return(*series, bar_close_ms, horizon_bars) if series else None
        if ret is None:
            w.unscorable += 1
            continue
        # A short call is right when price FELL, so score the move in the
        # direction the decision actually took.
        signed = ret if str(d["direction"]) == "long" else -ret
        w.actionable_scored += 1
        bucket.scored += 1
        w.actionable_sum_return_pct += signed
        bucket.sum_return_pct += signed
        if signed > 0:
            w.actionable_hits += 1
            bucket.hits += 1

    return {
        "model_version": MODEL_VERSION,
        "horizon_bars": horizon_bars,
        "split_ratio": split_ratio,
        "total_decisions": len(ordered),
        "underlyings": sorted(price_series.keys()),
        "caveats": CAVEATS,
        "calibration": windows["calibration"].as_dict(),
        "evaluation": windows["evaluation"].as_dict(),
    }


# ── promotion criteria (spec §19.5) ──────────────────────────────────────

#: §19.3 step 3: "at least 20 trading sessions before the first advisory
#: flow report", and its closing note that 20 is a MINIMUM capture
#: checkpoint, not proof of generalization.
MIN_TOTAL_SESSIONS = 20
#: A scored evaluation set smaller than this can't separate edge from noise.
MIN_EVALUATION_SCORED = 30
#: Beyond this, Navigator abstained so often the sample isn't representative.
MAX_NO_DATA_RATE = 0.35
#: "No material expectancy degradation" — the untouched evaluation window
#: must not be much worse than the window thresholds were tuned against.
MAX_HIT_RATE_DEGRADATION = 0.10
#: A directional call right less than half the time has no edge.
MIN_EVALUATION_HIT_RATE = 0.50


@dataclass(frozen=True)
class Criterion:
    key: str
    label: str
    passed: bool
    detail: str

    def as_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "passed": self.passed, "detail": self.detail}


def evaluate_criteria(report: dict) -> dict:
    """Check a report against the §19.5 promotion criteria.

    Reports only — never promotes. `eligible: True` means a human MAY now
    choose to promote, not that anything has been promoted.
    """
    cal = report.get("calibration", {})
    ev = report.get("evaluation", {})
    total_sessions = len(set(cal.get("session_dates", [])) | set(ev.get("session_dates", [])))
    ev_scored = int(ev.get("actionable_scored", 0))
    ev_hit = ev.get("hit_rate")
    cal_hit = cal.get("hit_rate")
    ev_ret = ev.get("mean_return_pct")
    no_data_rate = ev.get("no_data_rate")
    thin = "not enough scored decisions yet"

    criteria = [
        Criterion(
            "min_sessions", f"At least {MIN_TOTAL_SESSIONS} trading sessions captured",
            total_sessions >= MIN_TOTAL_SESSIONS,
            f"{total_sessions} of {MIN_TOTAL_SESSIONS} sessions",
        ),
        Criterion(
            "min_evaluation_samples",
            f"At least {MIN_EVALUATION_SCORED} scored decisions out-of-sample",
            ev_scored >= MIN_EVALUATION_SCORED,
            f"{ev_scored} of {MIN_EVALUATION_SCORED} scored",
        ),
        Criterion(
            "no_data_rate", f"Missing-data rate under {MAX_NO_DATA_RATE:.0%}",
            no_data_rate is not None and no_data_rate <= MAX_NO_DATA_RATE,
            "no decisions yet" if no_data_rate is None else f"{no_data_rate:.0%} missing data",
        ),
        Criterion(
            "evaluation_hit_rate",
            f"Out-of-sample hit rate at least {MIN_EVALUATION_HIT_RATE:.0%}",
            ev_hit is not None and ev_hit >= MIN_EVALUATION_HIT_RATE,
            thin if ev_hit is None else f"{ev_hit:.0%} hit rate",
        ),
        Criterion(
            "evaluation_expectancy",
            "Out-of-sample expectancy positive (before costs)",
            ev_ret is not None and ev_ret > 0,
            thin if ev_ret is None else f"{ev_ret:+.2f}% average move, gross of costs",
        ),
        Criterion(
            "stable_out_of_sample", "Out-of-sample result holds up vs. the tuning window",
            ev_hit is not None and cal_hit is not None
            and (cal_hit - ev_hit) <= MAX_HIT_RATE_DEGRADATION,
            thin if (ev_hit is None or cal_hit is None)
            else f"{cal_hit:.0%} in-sample vs {ev_hit:.0%} out-of-sample",
        ),
    ]
    return {
        "eligible": all(c.passed for c in criteria),
        "criteria": [c.as_dict() for c in criteria],
    }


def build_calibration_state(uid: str, report: dict, criteria: dict, *, now_ms: Optional[int] = None) -> dict:
    """Shape a report + verdict into a `navigator_calibration_state` row.

    `promotion_state` records only what the evidence supports —
    "eligible"/"not_eligible". It is never "promoted": that word belongs to
    the explicit human action, which writes to the config row instead.
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    payload = {"report": report, "criteria": criteria}
    artifact_hash = canonical_json_hash(payload)
    return {
        "user_id": uid,
        "report_id": f"navcal_{artifact_hash[:20]}",
        "model_version": MODEL_VERSION,
        "cohort": ",".join(report.get("underlyings", [])),
        "train_window_json": json.dumps(report.get("calibration", {})),
        "validation_window_json": json.dumps(report.get("evaluation", {})),
        "sample_count": int(report.get("total_decisions", 0)),
        "metrics_json": json.dumps(payload),
        "artifact_hash": artifact_hash,
        "promotion_state": "eligible" if criteria.get("eligible") else "not_eligible",
        "created_at_ms": now_ms,
    }
