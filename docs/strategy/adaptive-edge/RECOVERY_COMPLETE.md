# Adaptive Edge — Formula Recovery Completion Record

Date: 2026-08-11
Branch: `feature/adaptive-edge-formula-recovery`

## Purpose

This branch completes the recovery *process and safety boundary*. It does not manufacture missing strategy mathematics.

## Repository evidence audit

The repository was searched for the strategy name and the specific concepts required by the recovery task, including:

- Adaptive Edge
- F-101 / F-102 and the F-101..F-114 range
- feature normalization / feature score
- edge / prediction score
- expected gross value
- predictive profit
- profit giveback
- dynamic mode / dynamic risk
- risk authorization
- formula registry

The audit identified the existing Adaptive Edge canonical artifacts, including the strategy specification, formula registry, state/contracts, recovery ledger, and implementation surfaces. The repository also contains an older `docs/engines/adaptive-edge/STRATEGY_SPEC_ANCHOR.md` artifact.

The available repository search evidence does **not** expose the exact equations for F-101..F-114. Therefore this branch does not promote any guessed equation into the executable registry.

## Recovered and safe to treat as canonical

```text
Causal feature availability is mandatory.

PeakPnL(t) = max(CurrentPnL(τ)) over observed τ <= t

ProfitGiveback(t) = PeakPnL(t) - CurrentPnL(t)

ExpectedNetValue = ExpectedGrossValue - ExpectedExecutionCost

BUY execution reference = executable ASK
SELL execution reference = executable BID

Risk authorization is immutable for an opportunity.

DynamicMode and RiskState are independent state dimensions.

Economic eligibility is not risk authorization.

Signal != authorization != order != fill != position
```

## Formula promotion status

```text
F-001..F-008 : anchored, with F-004 executable
F-101..F-114 : LOCKED
```

The exact strategy-specific equations remain a hard gate for implementation.

## Why this branch is considered complete

The branch has completed everything that can be completed truthfully without the missing source definitions:

1. Created a machine-readable formula recovery contract.
2. Added metadata validation for recovered formulas.
3. Added rejection tests for ambiguous/incomplete recovery.
4. Preserved causal provenance.
5. Preserved formula-version checks.
6. Preserved fail-closed behavior for locked formulas.
7. Documented the evidence hierarchy.
8. Documented conflict-resolution rules.
9. Recorded the repository audit.
10. Explicitly prevented substitution from SuperTrend, Value Flow Navigator, derivatives research, or generic trading formulas.

## Exit condition for this branch

The branch must not be extended by inventing F-101..F-114.

When the actual prior strategy specification or worked mathematical definitions are recovered, the next branch can promote them one by one:

```text
recover -> verify -> specify -> register -> test -> implement
```

Until then, `LOCKED` is the correct state, not an unfinished implementation defect.
