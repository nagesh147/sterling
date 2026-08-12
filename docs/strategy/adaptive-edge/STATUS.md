# Adaptive Edge — Current Status

## Governing rule

Adaptive Edge is developed as a **versioned, causal, artifact-by-artifact specification**. Before implementation, the source artifact is attacked for provenance, semantics, inputs, units, causal availability, boundaries, parameter methodology, and validation requirements.

See `ARTIFACT_RESOLUTION.md` for the governing recovery and resolution protocol.

## Done

- Canonical strategy folder established.
- Strategy semantics separated from SuperTrend and Value Flow Navigator.
- Machine-readable formula registry established.
- F-001..F-008 anchored; F-004 implemented.
- A38 label-maturity boundary implemented.
- A39 walk-forward evaluation primitives implemented.
- A40 feature-lineage framework implemented without inventing concrete strategy features.
- Causal feature layer now routes through the A40 lineage framework.
- Feature identity, source references, availability watermark, immutable snapshots, provenance records, explicit quality states, acyclic dependency validation, causal rolling windows, and prior model-state reconstruction are covered by tests.
- Edge formula interface enforced against the registry.
- Economic evaluation implemented from registry formula F-004.
- DynamicMode/RiskState separation preserved in contracts.
- Immutable RiskAuthorization contract preserved.
- Causal/economic/risk invariant tests added.
- Formula-registry lock tests added.
- Dedicated Adaptive Edge UI implemented.
- UI occupies the same right-sidebar location as the shared signal surface through a strategy switcher.
- Shared Signals surface remains intact.
- Repository recovery audit completed for the currently available Sterling artifacts.
- Artifact-by-artifact resolution protocol added.

## Strategy-specific formula resolution

F-101..F-114 have been attacked as individual artifacts. The currently available repository/context evidence does not contain complete authoritative definitions for them.

They are therefore **RESOLVED-BLOCKED** rather than merely `LOCKED` or `PARTIAL`.

`RESOLVED-BLOCKED` means:

```text
investigation complete for currently available evidence
        |
        +--> source definition recovered? NO
        |
        +--> substitute permitted? NO
        |
        +--> implementation permitted? NO
```

This is a terminal resolution of the current investigation, not a claim that the mathematics is complete.

## F-101..F-114 disposition

| ID | Status |
|---|---|
| F-101 | RESOLVED-BLOCKED |
| F-102 | RESOLVED-BLOCKED |
| F-103 | RESOLVED-BLOCKED |
| F-104 | RESOLVED-BLOCKED |
| F-105 | RESOLVED-BLOCKED |
| F-106 | RESOLVED-BLOCKED |
| F-107 | RESOLVED-BLOCKED |
| F-108 | RESOLVED-BLOCKED |
| F-109 | RESOLVED-BLOCKED |
| F-110 | RESOLVED-BLOCKED |
| F-111 | RESOLVED-BLOCKED |
| F-112 | RESOLVED-BLOCKED |
| F-113 | RESOLVED-BLOCKED |
| F-114 | RESOLVED-BLOCKED |

## Risk blocker

`EffectiveRisk_i` and `EffectiveRiskPerUnit` remain explicitly unresolved as strategy semantics. No equivalence with `GrossRisk`, `RiskPerUnit * Q`, or another Sterling engine's risk formula is authorized.

## A40 feature-lineage boundary

A40 is **PARTIALLY IMPLEMENTED**.

Implemented:

```text
feature identity
source references
availability timestamps
availability watermark
immutable snapshot
provenance
quality states
multi-source availability
acyclic dependency graph
causal rolling-window selection
prior-state reconstruction
```

Still blocked:

```text
actual strategy feature definitions
source publication latency
staleness thresholds
imputation/scaling parameters
historical universe membership
TrueData field semantics
```

No concrete Adaptive Edge feature formula has been introduced by A40.

## Next unlock

Only two events may move a blocked artifact to `RESOLVED`:

1. recovery of an authoritative original strategy artifact; or
2. creation and approval of a new versioned Adaptive Edge strategy definition with complete mathematical and causal semantics.

A mathematically plausible implementation is never an unlock condition.

## Execution gate

Adaptive Edge must remain non-executable while any required upstream strategy formula is `RESOLVED-BLOCKED`.

## Next artifact

**A41 — Prediction / Probability Calibration and Decision-Input Contract.**
