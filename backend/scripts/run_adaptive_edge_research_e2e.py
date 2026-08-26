"""Research E2E on the entitled cache. Not live. Not A197. Not Kite."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("STERLING_DB_PATH", str(ROOT / "backend" / "sterling_paper.db"))

from app.engines.adaptive_edge.execution_gate import evaluate_execution_gate
from app.engines.adaptive_edge.production_readiness import production_readiness
from app.engines.adaptive_edge.f101 import F101Parameters, dump_f101_parameters, trial_identity_parameters
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from datetime import timedelta

from app.engines.adaptive_edge.management import research_management_policy
from app.engines.adaptive_edge.opportunity_mode import research_mode_policy
from app.engines.adaptive_edge.protection import ProtectionPolicy
from app.engines.adaptive_edge.research_e2e import research_sizing_inputs, run_research_session
from app.engines.adaptive_edge.research_pipeline import ResearchWalkForwardSpec
from app.engines.adaptive_edge.research_formulas import research_formula_table
from app.services.providers.truedata.bar_history import bars_to_canonical_sequence
from app.services.providers.truedata.bar_store import BarStore
from app.services.providers.truedata.tick_history import ticks_to_canonical_sequence
from app.services.providers.truedata.tick_store import TickStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="NIFTY-I")
    parser.add_argument(
        "--tick-store",
        default=str(ROOT / "backend" / "data" / "truedata_ticks.sqlite"),
    )
    parser.add_argument(
        "--bar-store",
        default=str(ROOT / "backend" / "data" / "truedata_bars.sqlite"),
    )
    parser.add_argument("--w-short", type=int, default=5)
    parser.add_argument("--w-long", type=int, default=15)
    parser.add_argument(
        "--out",
        default=str(ROOT / "backend" / "data" / "adaptive_edge" / "research_e2e.json"),
    )
    args = parser.parse_args()

    if FORMULAS["F-101"].status is not FormulaStatus.LOCKED:
        raise SystemExit("FAILURE: F-101 is not LOCKED")
    if evaluate_execution_gate().authorized:
        raise SystemExit("FAILURE: production ExecutionGate is unexpectedly authorized")

    ticks = TickStore(args.tick_store).load(args.symbol)
    bars = BarStore(args.bar_store).load(args.symbol, interval="1min")
    if not ticks or not bars:
        raise SystemExit("FAILURE: entitled bar/tick cache missing; research E2E is offline-only")

    tick_seq = ticks_to_canonical_sequence(args.symbol, ticks)
    bar_seq = bars_to_canonical_sequence(args.symbol, bars)
    params = trial_identity_parameters(w_short=args.w_short, w_long=args.w_long)
    result = run_research_session(
        symbol=args.symbol,
        bar_events=bar_seq.events,
        tick_events=tick_seq.events,
        params=params,
        bar_sequence_hash=bar_seq.sequence_hash,
        tick_sequence_hash=tick_seq.sequence_hash,
        walk_forward_spec=ResearchWalkForwardSpec(
            horizon=timedelta(minutes=5),
            purge=timedelta(minutes=5),
            embargo=timedelta(minutes=5),
            train_fraction=0.5,
            validation_fraction=0.2,
            label="RESEARCH_PLACEHOLDER_SPLITS",
        ),
        mode_policy=research_mode_policy(),
        management_policy=research_management_policy(),
        protection_policy=ProtectionPolicy(
            "RESEARCH_NOT_LIVE_EXPLICIT_PROTECTION",
            protective_stop_points=80.0,
            trail_points=40.0,
            profit_lock_activation_points=50.0,
            profit_lock_offset_points=15.0,
        ),
        sizing_inputs=research_sizing_inputs(
            issued_at=bar_seq.events[0].available_at if bar_seq.events else "2026-08-06T03:45:00+00:00"
        ),
    )
    payload = {
        "label": result.label,
        "not_a197": True,
        "not_live": True,
        "entries": result.entries,
        "blocked_pyramid": result.blocked_pyramid,
        "exits": result.exits,
        "reentries": result.reentries,
        "marks": result.marks,
        "peak_pnl": result.last_accounting.peak_pnl if result.last_accounting else None,
        "current_pnl": result.last_accounting.current_pnl if result.last_accounting else None,
        "profit_giveback": result.last_accounting.profit_giveback if result.last_accounting else None,
        "lifecycle_action": result.last_lifecycle_action,
        "last_position_quantity": result.last_position_quantity,
        "exit_fill_price": result.exit_fill_price,
        "audit_stages": result.audit_stages,
        "walk_forward": (
            None
            if result.walk_forward is None
            else {
                "label": result.walk_forward.label,
                "train": result.walk_forward.train,
                "validation": result.walk_forward.validation,
                "test": result.walk_forward.test,
                "ineligible": result.walk_forward.ineligible,
                "train_test_overlap": result.walk_forward.train_test_overlap,
            }
        ),
        "walk_forward_eval": (
            None
            if result.walk_forward_eval is None
            else {
                "reason": result.walk_forward_eval.reason,
                "estimated_from_train_only": result.walk_forward_eval.estimated_from_train_only,
                "train_parameter_status": result.walk_forward_eval.train_parameter_status,
                "test_rescored": result.walk_forward_eval.test_rescored,
                "test_valid": result.walk_forward_eval.test_valid,
                "test_mean_score": result.walk_forward_eval.test_mean_score,
                "validation_rescored": result.walk_forward_eval.validation_rescored,
                "validation_valid": result.walk_forward_eval.validation_valid,
                "validation_mean_score": result.walk_forward_eval.validation_mean_score,
                "train_test_overlap": result.walk_forward_eval.summary.train_test_overlap,
            }
        ),
        "daily": [
            {
                "session_date": day.session_date,
                "entries": day.entries,
                "exits": day.exits,
                "last_quantity": day.last_quantity,
                "flattened": day.flattened,
            }
            for day in result.daily
        ],
        "legs": [
            {
                "session_date": leg.session_date,
                "entry_time": leg.entry_time,
                "exit_time": leg.exit_time,
                "flattened": leg.flattened,
                "quantity": leg.quantity,
                "symbol": leg.symbol,
                "side": leg.side,
                "entry_price": leg.entry_price,
                "exit_price": leg.exit_price,
                "stop_price": leg.stop_price,
                "trail_price": leg.trail_price,
                "lock_price": leg.lock_price,
                "entry_score": leg.entry_score,
                "entry_mode": leg.entry_mode,
                "exit_mode": leg.exit_mode,
                "peak_mode": leg.peak_mode,
                "thesis": leg.thesis,
                "protection_stage": leg.protection_stage,
                "overlays": leg.overlays,
                "operating_mode": leg.operating_mode,
                "horizon": leg.horizon,
                "entry_poc": leg.entry_poc,
                "entry_vwap": leg.entry_vwap,
                "entry_cvd": leg.entry_cvd,
            }
            for leg in result.legs
        ],
        "quality": (
            None
            if result.quality is None
            else {
                "status": result.quality.status,
                "missing_score_rate": result.quality.missing_score_rate,
                "li_valid_rate": result.quality.li_valid_rate,
                "missing_log_return": result.quality.missing_log_return,
                "missing_liquidity_imbalance": result.quality.missing_liquidity_imbalance,
                "missing_volatility_ratio": result.quality.missing_volatility_ratio,
                "bars_outside_session": result.quality.bars_outside_session,
                "bars_after_a126_cutoff": result.quality.bars_after_a126_cutoff,
                "max_li_quote_lag_seconds": result.quality.max_li_quote_lag_seconds,
                "mean_li_quote_lag_seconds": result.quality.mean_li_quote_lag_seconds,
                "meets_a197": result.quality.meets_a197,
            }
        ),
        "last_mode": result.last_mode,
        "last_thesis": result.last_thesis,
        "last_protection_stage": result.last_protection_stage,
        "last_overlays": result.last_overlays,
        "last_operating_mode": result.last_operating_mode,
        "last_horizon": result.last_horizon,
        "last_poc": result.last_poc,
        "last_cvd": result.last_cvd,
        "last_location": result.last_location,
        "last_bar_delta": result.last_bar_delta,
        "last_vwap": result.last_vwap,
        "last_or_location": result.last_or_location,
        "last_poc_migration": result.last_poc_migration,
        "mode_counts": dict(result.mode_counts),
        "mode_transitions": [
            {
                "previous_mode": rec.previous_mode.value,
                "new_mode": rec.new_mode.value,
                "timestamp": rec.timestamp,
                "trigger_reason": rec.trigger_reason,
                "favorable_points": rec.favorable_points,
                "giveback_ratio": rec.giveback_ratio,
                "holding_age_seconds": rec.holding_age_seconds,
                "minutes_to_cutoff": rec.minutes_to_cutoff,
                "persistence_bars": rec.persistence_bars,
            }
            for rec in result.mode_transitions
        ],
        "artifact_digest": result.artifact_digest,
        "holdout": (
            None
            if result.holdout is None
            else {
                "label": result.holdout.label,
                "entries": result.holdout.entries,
                "exits": result.holdout.exits,
                "reentries": result.holdout.reentries,
                "last_position_quantity": result.holdout.last_position_quantity,
                "parameter_status": result.holdout.parameter_status,
                "used_train_params_only": result.holdout.used_train_params_only,
                "test_bar_count": result.holdout.test_bar_count,
                "software_complete": result.holdout.software_complete,
                "incomplete_reasons": result.holdout.incomplete_reasons,
            }
        ),
        "production_gate_authorized": result.production_gate_authorized,
        "software_complete": result.software_complete,
        "incomplete_reasons": result.incomplete_reasons,
        "coverage": result.coverage.__dict__,
        "formula_table": {
            item.formula_id: {"status": item.status, "reason": item.reason}
            for item in research_formula_table().values()
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    trial_path = out.parent / "f101_trial_scores.json"
    trial_hash_match: bool | None = None
    if trial_path.exists():
        trial = json.loads(trial_path.read_text())
        trial_hash_match = (
            trial.get("bar_sequence_hash") == result.coverage.bar_sequence_hash
            and trial.get("tick_sequence_hash") == result.coverage.tick_sequence_hash
        )
    manifest = {
        "label": (
            "RESEARCH_E2E_SOFTWARE_COMPLETE"
            if result.software_complete
            else "RESEARCH_E2E_INCOMPLETE"
        ),
        "software_complete": result.software_complete,
        "incomplete_reasons": result.incomplete_reasons,
        "not_a197": True,
        "not_live": True,
        "production_gate_authorized": result.production_gate_authorized,
        "artifact_digest": result.artifact_digest,
        "bar_sequence_hash": result.coverage.bar_sequence_hash,
        "tick_sequence_hash": result.coverage.tick_sequence_hash,
        "trial_scores_hash_match": trial_hash_match,
        "entries": result.entries,
        "exits": result.exits,
        "daily_days": len(result.daily),
        "holdout_software_complete": (
            None if result.holdout is None else result.holdout.software_complete
        ),
        "meets_a197": result.coverage.meets_a197,
    }
    manifest_path = out.parent / "software_e2e_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"LABEL: {result.label}")
    print(f"ENTRIES: {result.entries}")
    print(f"EXITS: {result.exits}")
    print(f"REENTRIES: {result.reentries}")
    print(f"BLOCKED_PYRAMID: {result.blocked_pyramid}")
    print(f"MARKS: {result.marks}")
    print(f"A197: {result.coverage.meets_a197}")
    print(f"PRODUCTION_GATE: {result.production_gate_authorized}")
    print(f"SOFTWARE_COMPLETE: {result.software_complete}")
    print(f"LAST_MODE: {result.last_mode}")
    print(f"LAST_THESIS: {result.last_thesis}")
    print(f"LAST_PROTECTION: {result.last_protection_stage}")
    print(f"LAST_HORIZON: {result.last_horizon}")
    print(f"LAST_POSTURE: {result.last_operating_mode}")
    print(f"POC: {result.last_poc}")
    print(f"CVD: {result.last_cvd}")
    print(f"LOCATION: {result.last_location}")
    print(f"BAR_DELTA: {result.last_bar_delta}")
    print(f"VWAP: {result.last_vwap}")
    print(f"OR: {result.last_or_location}")
    print(f"POC_MIGRATION: {result.last_poc_migration}")
    print(f"MODE_TRANSITIONS: {len(result.mode_transitions)}")
    for item in production_readiness():
        print(f"READY_{item.name}: {item.ready}")
    print(f"ARTIFACT_DIGEST: {result.artifact_digest}")
    print(f"TRIAL_SCORES_HASH_MATCH: {trial_hash_match}")
    print(f"MANIFEST: {manifest_path}")
    print(f"DAILY: {len(result.daily)}")
    if result.quality is not None:
        print(
            "QUALITY: "
            f"{result.quality.status} li={result.quality.li_valid_rate:.4f} "
            f"missing={result.quality.missing_score_rate:.4f} a197={result.quality.meets_a197}"
        )
    if result.holdout is not None:
        print(
            "HOLDOUT: "
            f"entries={result.holdout.entries} exits={result.holdout.exits} "
            f"train_only={result.holdout.used_train_params_only} "
            f"complete={result.holdout.software_complete}"
        )
    if result.walk_forward_eval is not None:
        print(
            "WF_EVAL: "
            f"{result.walk_forward_eval.reason} "
            f"train_only={result.walk_forward_eval.estimated_from_train_only} "
            f"test_valid={result.walk_forward_eval.test_valid}"
        )
        if result.walk_forward_eval.estimated_from_train_only:
            identity = trial_identity_parameters(w_short=args.w_short, w_long=args.w_long)
            dump_f101_parameters(
                F101Parameters(
                    status="TRIAL_NOT_A197_TRAIN_ONLY",
                    w_short=args.w_short,
                    w_long=args.w_long,
                    med=result.walk_forward_eval.train_med or identity.med,
                    scale=result.walk_forward_eval.train_scale or identity.scale,
                    weights=identity.weights,
                ),
                out.parent / "f101_parameters_trial.json",
            )
    if result.incomplete_reasons:
        print("INCOMPLETE: " + ",".join(result.incomplete_reasons))
    print(f"OUT: {out}")
    if not result.software_complete:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
