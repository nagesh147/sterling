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

**Superseded 2026-08-27.** This section previously recorded F-101..F-114 as
`RESOLVED-BLOCKED` on the finding that "the currently available
repository/context evidence does not contain complete authoritative definitions
for them". That finding was correct when written and is no longer true.

The authoritative source is in the repository. `ORIGINAL_SOURCE_MANIFEST.md`
names it: commit `38f44f09` ("adaptive edge files uploaded", 2026-08-11) added
`adaptive-edge/`, 66 files, including

    adaptive-edge/Adaptive Order-Flow Options Scalping and Intraday Strategy.md

the **Master Mathematical Specification, Version 1.0** — 2,052 lines across 58
sections covering the event model, feature state, probability state, economic
evaluation, option selection, risk, position management, walk-forward learning
and validation. That directory is present in the working tree today.

So unlock condition (1) below — "recovery of an authoritative original strategy
artifact" — is **satisfied**. The blocked disposition is lifted.

## What the source does and does not give

This matters more than the unlock, because it is what still gates production.

The specification defines **structure**: which gates exist, what must hold, the
invariants, the state machine, and the causal rules. It deliberately does **not**
define numeric thresholds. §19:

    No fixed universal threshold ... is used unless that threshold survives
    walk-forward validation and is demonstrably robust.

and §51-§55 place every numeric parameter under walk-forward learning rather than
under specification.

The consequence:

```text
structure          -> RECOVERED from an authoritative source
numeric parameters -> NOT SPECIFIED, by design; must be calibrated
```

Implementing the structure is therefore authorized. Choosing the numbers is not
something the source can authorize, and a plausible number remains exactly what
the protocol has always said it is — not an unlock.

## Current disposition

| ID | Structure | Parameters | Production |
|---|---|---|---|
| F-101..F-114 | SOURCE-RECOVERED | UNCALIBRATED | LOCKED |

`backend/app/engines/adaptive_edge/config.py` holds every parameter explicitly,
with `CALIBRATED_FIELDS` empty and `PARAMETER_PROVENANCE` recording "research
default" against each one. Nothing in the engine treats any of them as measured,
and the API publishes that so the UI cannot present a placeholder as a finding.

## Risk blocker

`EffectiveRisk_i` and `EffectiveRiskPerUnit` remain explicitly unresolved as strategy semantics. No equivalence with `GrossRisk`, `RiskPerUnit * Q`, or another Sterling engine's risk formula is authorized.

## Next unlock

Only two events may move a blocked artifact to `RESOLVED`:

1. recovery of an authoritative original strategy artifact; or
2. creation and approval of a new versioned Adaptive Edge strategy definition with complete mathematical and causal semantics.

A mathematically plausible implementation is never an unlock condition.

## Execution gate

`backend/app/engines/adaptive_edge/execution_gate.py` is the final machine-enforced boundary. It requires every F-101..F-114 formula to be explicitly `IMPLEMENTED` before execution can be authorized.

Current expected state — two independent gates, both closed:

```text
F-101..F-114                    strategy promotion
      |                                |
      v                                v
   LOCKED                        RESEARCH_ONLY
      |                                |
      v                                v
ExecutionGateStatus.BLOCKED    promotion gate BLOCKED
      |                                |
      +----------------+---------------+
                       X
          Execution / broker boundary
```

The promotion gate is the one that matters now. Implementing the mathematics and
being authorized to risk money on it are different claims, and the engine has
only the first. A166 makes `research_validation_complete` a mandatory term for
production readiness, and that is precisely the calibration §19 requires.

The engine therefore ships **enabled, on auto, and paper-only**: it scans and
paper-trades so the calibration can be collected, and cannot reach real money
until somebody promotes it deliberately.

No broker/execution adapter may bypass this gate as a workaround for missing strategy semantics.
