# Adaptive Edge — specification vs implementation, 2026-08-27

A167 requires that conformance be established per requirement, not inferred from
a module existing. This is that comparison, run against `main` at `594f232a`.

Corpus: 114 docs in `docs/strategy/adaptive-edge/`, 89 more in `v2/`, and the
66-file authoritative source set in `adaptive-edge/`. Implementation: 147 modules
in `backend/app/engines/adaptive_edge/`, 5 services, 10 routes.

## Summary

| Check | Result |
|---|---|
| Code paths named by docs that exist | 52 / 52 |
| IMPLEMENTATION_ORDER items with a named implementation | 32 / 32 |
| Formula registry owners resolving to real code | 18 / 22 → **fixed, now 22 / 22** |
| Engine modules reachable from the running system | **11 / 147** |

The first three look like a clean bill of health. The fourth is the finding.

## The finding: the strategy is implemented and not connected

Every item in `IMPLEMENTATION_ORDER.md` — all 32, across Phases A to E — has a
module or symbol implementing it. A167 anticipates exactly this and warns
against reading it as conformance:

> The existence of a similarly named module or passing integration test is not
> sufficient for conformance.

Tracing imports from the live runtime path (`adaptive_edge_runner`,
`adaptive_edge_scanner`, `adaptive_edge`, the API endpoints) and following the
intra-package graph transitively gives **11 reachable modules of 147**:

```text
config · execution · execution_gate · formula_registry · option_ladder
production_readiness · promotion · protection · readiness
research_formulas · state_machine
```

Those are configuration, gates, the registry, and the lifecycle table. **None of
the strategy mathematics is among them:**

| Canonical module | On the live path? |
|---|---|
| `canonical_math` | no |
| `feature_engine` | no |
| `probability_engine` | no |
| `master_spec_edge` | no |
| `economic_engine` | no |
| `decision_pipeline` | no |
| `risk_engine` | no |
| `protection_engine` | no |
| `f101_normalization` | no |
| `f110_entry_gate` | no |
| `f111_exit_gate` | no |
| `strategy_v21` | no |

`strategy_pipeline.py` composes the full A→K sequence the specification
describes — causal boundary, feature snapshot, directional hypothesis, adaptive
horizon, edge assessment, F-004 viability, risk authorization and sizing,
instrument selection, order intent, protection envelope, lifecycle termination.
Nothing in `app/services` or `app/api` imports it.

So the honest reading of "32/32 implemented" is: the mathematics exists as
research code, and the thing that runs does not call it. The running engine
scans an option universe, applies liquidity and expiry filters from config, and
records observations. It reaches no directional decision, which is consistent
with — and the mechanical cause of — `entry_ok` being false on every candidate.

This is not a regression. It is the state the engine has been in, now measured.

## What that means for the readiness states

A166 defines the ladder `DESIGN → IMPLEMENTATION → CONFORMANCE → PAPER_READY →
…`. The plumbing is PAPER_READY: it runs, it is safe, it records. The strategy
core is at IMPLEMENTATION and has not reached CONFORMANCE, because conformance
requires the canonical requirement to be reachable from the implementation, and
for the strategy modules it is not.

Calling the engine as a whole PAPER_READY would be true of the harness and false
of the strategy.

## Drift found and fixed

Four formula owners in `formula_registry.py` named code that did not exist. The
owner is part of A167's conformance record, and it fails silently because
nothing dereferences the string.

| Formula | Claimed owner | Actual |
|---|---|---|
| F-005 | `risk` (no such module) | `risk_engine` |
| F-006 | `risk` (no such module) | `risk_engine` |
| F-007 | `execution` (dangling) | `research_references` |
| F-008 | `execution` (dangling) | `research_references` |
| F-113 | `f113_reentry` (no such module) | `strategy_v21` |

F-007/F-008 are the instructive case. `execution` named nothing for as long as
the label existed — until an unrelated `execution.py` was added for order-price
arithmetic on 2026-08-27, at which point a wrong owner silently began resolving
to a module with nothing to do with executable BUY/SELL references. A wrong
owner that resolves is harder to catch than one that does not, which is why
`test_formula_registry_owners.py` now pins that every owner names a real module.

## What was checked and found clean

* Every `backend/`, `frontend/` and `scripts/` path cited across the docs exists.
* `STATUS.md`'s formula disposition, corrected earlier the same day — the
  authoritative source it declared missing is present in `adaptive-edge/`.
* The registry's status vocabulary matches what the gates read.

## Not checked

Semantic conformance of each formula against its specification section — whether
`f105_economics` computes what §33–§34 define, term by term. That needs a reading
of 58 spec sections against 147 modules and is the work A167 actually asks for.
This audit establishes reachability and ownership, which is the layer beneath it:
there is no value in verifying the semantics of code the engine never calls.
