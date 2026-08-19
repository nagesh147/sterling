# Adaptive Edge — Current Status

## Governing rule

Adaptive Edge is developed as a **versioned, causal, artifact-by-artifact specification**. Before implementation, the source artifact is attacked for provenance, semantics, inputs, units, causal availability, boundaries, parameter methodology, and validation requirements.

See `ARTIFACT_RESOLUTION.md` for the governing recovery and resolution protocol.

## Done

- Canonical strategy folder established.
- Strategy semantics separated from SuperTrend and Value Flow Navigator.
- Machine-readable formula registry established.
- F-001..F-008 anchored; F-004 implemented.
- Causal feature layer implemented and carries formula provenance.
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
- Final execution gate implemented as a machine-testable fail-closed boundary.
- Unknown formula IDs fail closed at the execution gate.
- Edge evaluation now requires the selected strategy formula to be explicitly `IMPLEMENTED`, not merely non-locked.

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

## Completion program (software slice)

Research-path composition is implemented: OrderIntent → Gateway → BrokerEvent → Position, listed F-109 fail-closed, F-110 conjunction with explicit ConservativeEV, T4/T5 identity prediction (no invented F-102 score), replay identity without mutating the registry.

`software_complete` is True. `production_authorized` is False. ExecutionGate stays BLOCKED. F-101..F-114 stay LOCKED.

**A197 remesure 2026-08-19 (`TD-6037DD0DD3`):** bars **50,244 / 134 days** (counts met). LI ticks **53,884 / 9 days** (all `li_valid`). Bars that fall on LI days: **3,374**. Old/boundary `/getticks` still empty (401 after live control). Verdict **R2**. `meets_a197_contract` is False because LI does not cover the bar window. Ticks were not synthesized.

Remaining blockers are not software: A197 LI corpus (~113 more LI trading days), unique F-101..F-106 / F-113 / F-114 mathematics, walk-forward OOS, then unlock.

## Next unlock

Only two events may move a blocked artifact to `RESOLVED`:

1. recovery of an authoritative original strategy artifact; or
2. creation and approval of a new versioned Adaptive Edge strategy definition with complete mathematical and causal semantics.

A mathematically plausible implementation is never an unlock condition.

## Execution gate

`backend/app/engines/adaptive_edge/execution_gate.py` is the final machine-enforced boundary. It requires every F-101..F-114 formula to be explicitly `IMPLEMENTED` before execution can be authorized.

Current expected state:

```text
F-101..F-114
      |
      v
RESOLVED-BLOCKED
      |
      v
ExecutionGateStatus.BLOCKED
      |
      X
Execution / broker boundary
```

No broker/execution adapter may bypass this gate as a workaround for missing strategy semantics.
