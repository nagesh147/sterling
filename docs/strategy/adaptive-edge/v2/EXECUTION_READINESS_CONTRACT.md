# Adaptive Edge V2 — Strategy Execution Readiness Contract

**Status:** FAIL-CLOSED

## Purpose

This boundary prevents the Adaptive Edge execution path from becoming active while required strategy-specific mathematics remains unresolved.

## Required strategy formulas

The executable strategy requires all of:

```text
F-101 Feature normalization / feature score
F-102 Edge / prediction score
F-103 Opportunity eligibility
F-104 Dynamic-mode transition
F-105 Predictive-profit protection
F-106 Dynamic-risk schedule
F-107 Risk-per-unit
F-108 Position sizing
F-109 Instrument / option selection
F-110 Entry trigger
F-111 Exit trigger
F-112 Trailing / protection parameterization
F-113 Re-entry
F-114 Multi-position interaction
```

Every required formula must have registry status `IMPLEMENTED` before strategy readiness can become true.

## Fail-closed rule

If any required formula is missing, locked, anchored, parameterized without an executable source-defined implementation, or otherwise not `IMPLEMENTED`, the strategy is not executable.

No default formula, fallback strategy, or unrelated Sterling strategy may satisfy the gate.

## Scope

This gate does not resolve the missing mathematics. It makes the unresolved state explicit and machine-checkable.

An unlock requires either:

1. recovery of an authoritative original strategy artifact; or
2. approval of a new versioned Adaptive Edge strategy definition with complete mathematical and causal semantics.
