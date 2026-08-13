# A190 — Adaptive Edge Implementation Conformance Audit

## Status
CANONICAL AUDIT BASELINE

## Purpose
A190 establishes the first implementation-conformance baseline after specification closure. It does not invent strategy mathematics and does not authorize live execution.

## Repository evidence inspected
- `backend/app/engines/adaptive_edge/feature_engine.py`
- `backend/app/engines/adaptive_edge/edge.py`
- `backend/app/engines/adaptive_edge/formula_registry.py`
- `docs/strategy/adaptive-edge/STATUS.md`
- `docs/strategy/adaptive-edge/v2/03_FEATURE_SET.md`
- `adaptive-edge/CANONICAL IMPLEMENTATION CONTRACT AND MODULE BOUNDARY SPECIFICATION.md`

## Conformance principle
```text
specification requirement
        -> implementation mapping
        -> invariant
        -> test
        -> runtime evidence
```

Passing tests alone does not prove semantic conformance. The implementation must be mapped to the canonical contract.

## Findings

### 1. Causal feature boundary
The existing feature layer carries `available_at` and rejects a snapshot when an input claims availability after decision time. This is a valid implementation of the causal boundary, but the full V2 FeatureSnapshot contract is not yet represented: explicit feature-set identity, complete provenance, per-feature status semantics, and all version fields require conformance work.

### 2. Formula registry
The registry correctly prevents strategy formulas F-101..F-114 from becoming executable without explicit implementation status. Their current locked state is intentional and must not be bypassed.

### 3. Edge evaluation
Edge evaluation requires a registered implemented strategy formula and matching formula version. This preserves the implementation-source-of-truth boundary.

### 4. Provider semantics
Provider-specific semantics remain external dependencies. No TrueData field may be promoted into canonical strategy semantics without documented mapping and empirical verification.

### 5. Risk semantics
No unresolved risk formula may be inferred from an existing generic risk calculation. `EffectiveRisk_i` and `EffectiveRiskPerUnit` remain blocked until the authoritative strategy semantics are recovered or a new versioned definition is approved.

## Required conformance work

### A190.1 FeatureSnapshot
Add explicit immutable identity for:
```text
snapshot_id
strategy_version
feature_set_version
decision_time
observation_cutoff_time
feature_values
feature_statuses
source_event_references
instrument_context
provenance
```

Existing fields must not be silently reinterpreted.

### A190.2 Provenance
Every feature used by a consequential decision must retain enough lineage to reconstruct:
```text
source event(s)
-> canonical event/state
-> feature formula/version
-> feature value
-> snapshot
```

### A190.3 Quality states
Represent at minimum:
```text
VALID
MISSING
STALE
INVALID
NOT_APPLICABLE
```

Do not encode these states through sentinel numeric values.

### A190.4 Version lineage
Feature and feature-set versions must be explicit and immutable once a snapshot is used for a decision.

### A190.5 Execution-gate reachability
Every consequential path must pass the canonical execution gate. No signal, feature, prediction, or economic object may bypass risk/execution authorization.

### A190.6 Dependency-direction audit
Verify that infrastructure/data/state/features/models/decision/risk/execution/accounting boundaries do not contain reverse dependencies.

### A190.7 Invariant tests
Add machine-testable tests for:
```text
future availability rejection
missing != zero
stale != current
invalid identity rejection
immutable snapshot identity
formula version mismatch
locked formula rejection
no direct broker path
risk authorization cannot be increased downstream
```

### A190.8 Regression
Existing tests must continue to pass. Conformance changes must not unlock F-101..F-114.

## Explicit non-goals
A190 does not:
- invent F-101..F-114 mathematics;
- select stop-loss/trailing/profit-lock numbers;
- select learned thresholds;
- assume provider field semantics;
- authorize live trading;
- replace Kite or TrueData contracts;
- merge the canonical branch into `main`.

## Adversarial review

### Look-ahead
The current `available_at <= decision_time` guard is necessary but insufficient unless all derived dependencies carry equivalent availability semantics.

### Leakage through normalization
Normalization parameters must be learned inside temporal training boundaries. A runtime feature object must not hide globally fitted parameters.

### Duplicate variables
Feature names must identify semantic definitions rather than aliases of provider fields.

### Impossible states
A snapshot with `VALID` status and no valid source/provenance reference must be rejected.

### Execution bypass
The formula registry lock is necessary but insufficient if another module can construct an executable order independently. Static dependency and runtime-path tests are required.

### Provider assumptions
No provider response is treated as canonical until mapped through an explicit adapter contract.

## Architecture status
```text
ARCHITECTURE STATUS:
COMPLETE

IMPLEMENTATION-CONFORMANCE STATUS:
PARTIAL

FROZEN:
- causal feature boundary
- formula registry authority
- locked strategy mathematics
- execution-gate fail-closed principle
- module dependency direction

UNRESOLVED:
- complete FeatureSnapshot semantic conformance
- complete provenance representation
- complete quality-state representation
- complete runtime path conformance
- provider semantic verification

BLOCKERS:
- strategy-specific mathematics F-101..F-114 remain blocked
- provider documentation/verification remains required
- empirical learned parameters remain unavailable

NEXT ARTIFACT:
A191 — FeatureSnapshot, Provenance & Quality-State Conformance Contract
```
