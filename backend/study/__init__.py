"""Study modules — empirical edge study infrastructure.

Phase 1 of the derivatives edge study (spec: docs/superpowers/specs/
2026-06-02-derivatives-edge-study-design.md). These modules produce
real, OOS-robust stats answering what tradeable edge exists per
instrument × symbol × TF × strategy × SL/TP × filter × exit × direction.

Also serves as the shared simulation substrate for the existing
robustness_scan.py (refactored to import from here).
"""
from __future__ import annotations

from study.sim import simulate_idx, sharpe, base_metrics
from study.surface_snapshot import SurfaceSnapshot

# `capture_live` (Delta India chain capture) and the StudyRunner trio went with
# the crypto surface. Re-exporting them here outlived them, so importing ANY
# module in this package raised ModuleNotFoundError at package init -- including
# the seven retained Kite study scripts that only wanted `study.kite_data`.
__all__ = [
    "simulate_idx", "sharpe", "base_metrics",
    "SurfaceSnapshot",
]
