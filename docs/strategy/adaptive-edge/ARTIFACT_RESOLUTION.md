# Adaptive Edge — Artifact Resolution Protocol

## Purpose

This document governs resolution of every strategy-specific Adaptive Edge artifact before implementation. It does not define strategy mathematics; it defines the evidence and resolution procedure required to authorize strategy mathematics.

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
Artifact has not been investigated sufficiently.

### SOURCE-RECOVERED
An authoritative strategy source has been located, but the formula still requires complete input semantics, units, causal boundaries, parameter status, tests, and provenance before promotion.

### RESOLVED-BLOCKED
The authoritative source has been inspected but a required semantic or mathematical element remains unresolved. No substitute is permitted.

### RESOLVED
The artifact has an authoritative definition with complete required-input semantics, causal availability, units, boundaries, parameter status, version, provenance, and testability.

## Current state

The original V1.0 master strategy specification was recovered at immutable commit `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1` and is recorded by A208/A224.

Therefore F-101..F-114 are no longer correctly described as having **no authoritative source**. They are `SOURCE-RECOVERED` and remain production-locked pending canonicalization/promotion.

```text
SOURCE-RECOVERED
      |
      +--> complete contract + tests + calibration --> RESOLVED
      |
      +--> unresolved semantic/math element -------> RESOLVED-BLOCKED
```

## Required evidence

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

## Implementation gate

```text
RESOLVED                  -> implementation may proceed
SOURCE-RECOVERED          -> research implementation may proceed; production remains locked
RESOLVED-BLOCKED          -> implementation forbidden
UNKNOWN                   -> investigation required
```

## Formula disposition

```text
F-101..F-113 = SOURCE-RECOVERED / REGISTRY-LOCKED
F-114        = SOURCE-RECOVERED / PORTFOLIO AGGREGATION UNRESOLVED
```

F-114 is not blocked because the master source is missing. The source defines the canonical decision function using MarketState, ProbabilityState, CapitalState, ExecutionState, and PositionState, but does not provide a uniquely specified multi-position portfolio-risk aggregation equation.

## Risk semantic prohibition

No equivalence may be inferred between:

```text
EffectiveRisk_i
EffectiveRiskPerUnit
RiskPerUnit
GrossRisk
```

unless the authoritative strategy artifact explicitly defines that relationship.

## Required promotion sequence

```text
source artifact
  -> recovery ledger
  -> canonical formula registry
  -> contracts/tests
  -> implementation
  -> traceability
  -> calibration
  -> backtest/parity validation
  -> execution authorization
```
