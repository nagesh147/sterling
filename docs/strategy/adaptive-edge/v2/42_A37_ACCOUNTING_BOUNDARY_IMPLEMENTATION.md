# A37 — Accounting Boundary Implementation

## Status

FRAMEWORK IMPLEMENTED / ECONOMIC SEMANTICS BLOCKED

## Implemented

The implementation now represents the source-defined accounting boundary as explicit records for:

- CashEffect
- ExecutionCost
- ValuationObservation
- RiskReconciliationBoundary

Each record carries identity, provenance, currency/policy information where required, and causal timestamps.

The structural relationship

```text
NetEconomicResult = GrossEconomicResult - ExplicitlyDefinedCosts
```

is implemented only when the caller supplies explicitly defined costs.

## Not invented

The implementation does not define:

- broker accounting
- fee schedules
- contract multipliers
- entry-cost allocation for partial exits
- valuation price policy
- FX conversion
- settlement semantics
- gross P&L formula
- EffectiveRisk
- risk consumption

These remain external or unresolved dependencies exactly as A37 specifies.

## Reconciliation boundary

```text
RiskAuthorization
        |
        v
AuthorizedRiskLedger
        |
        v
ActualPosition / ExecutionState
        |
        v
RiskReconciliation
```

The risk function itself remains blocked by A32.
