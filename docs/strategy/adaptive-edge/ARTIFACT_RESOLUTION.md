# Adaptive Edge — Artifact Resolution Protocol

## Purpose

This document governs resolution of every strategy-specific Adaptive Edge artifact before implementation.

It does not define strategy mathematics. It defines the evidence and resolution procedure required to authorize strategy mathematics.

## Source hierarchy

```text
1. Canonical Adaptive Edge strategy artifacts
2. Strategy tests/contracts
3. Strategy implementation
4. Shared platform contracts
5. Historical reports / exploratory studies
6. Chat history / memory
```

A lower-level source cannot silently override a higher-level strategy definition.

## Resolution states

### UNKNOWN

The artifact has not yet been investigated sufficiently.

### RESOLVED-BLOCKED

The currently available evidence has been exhausted and no authoritative complete definition has been recovered. No substitute is permitted and implementation is forbidden.

### RESOLVED

The artifact has an authoritative definition with complete required-input semantics, causal availability, units, boundaries, parameter status, version, provenance, and testability.

## Required evidence

An artifact cannot become RESOLVED from a mathematically valid equation alone.

The following must be established where applicable:

```text
Artifact ID
Version
Canonical definition
Every required input
Input semantics
Units
Timestamp / availability semantics
Causal boundary
State dependencies
Boundary conditions
Failure conditions
Numerical safeguards
Parameter methodology
External dependencies
Provenance
Tests
```

## Attack procedure

Before RESOLVED status, inspect for:

- look-ahead bias
- information leakage
- circular dependency
- duplicated variables
- undefined inputs
- ambiguous units
- ambiguous timestamps
- impossible states
- accounting inconsistency
- execution impossibility
- unavailable data
- parameter fragility
- selection bias
- survivorship bias
- multiple-testing risk

Use synthetic or adversarial cases where the artifact is sufficiently defined to test them.

## Unlock conditions

A RESOLVED-BLOCKED artifact may become RESOLVED only through one of:

1. Recovery of an authoritative original strategy artifact; or
2. Creation and explicit approval of a new versioned Adaptive Edge strategy definition.

A plausible implementation, another Sterling strategy, a generic trading convention, or an inferred equivalence is not an unlock condition.

## Implementation gate

```text
RESOLVED       -> implementation may proceed
RESOLVED-BLOCKED -> implementation forbidden
UNKNOWN        -> investigation required
```

If a required upstream strategy artifact is RESOLVED-BLOCKED, Adaptive Edge remains non-executable.

## Current blocked set

F-101 through F-114 are RESOLVED-BLOCKED under the current repository evidence. See `STATUS.md`, `RECOVERY.md`, and `FORMULAS.md`.

The blocked set includes, without substituting semantics:

```text
F-101  Feature normalization / feature score
F-102  Edge / prediction score
F-103  Opportunity eligibility
F-104  Dynamic-mode transition
F-105  Predictive-profit protection
F-106  Dynamic-risk schedule
F-107  Risk-per-unit
F-108  Position sizing
F-109  Instrument / option selection
F-110  Entry trigger
F-111  Exit trigger
F-112  Trailing / profit-protection parameterization
F-113  Re-entry
F-114  Multi-position interaction
```

## Risk semantic prohibition

No equivalence may be inferred between:

```text
EffectiveRisk_i
EffectiveRiskPerUnit
RiskPerUnit
GrossRisk
```

unless an authoritative strategy artifact explicitly defines that relationship.

## Required promotion sequence

```text
source artifact
  -> recovery ledger
  -> canonical formula registry
  -> contracts/tests
  -> implementation
  -> traceability
  -> backtest/parity validation
  -> execution authorization
```
