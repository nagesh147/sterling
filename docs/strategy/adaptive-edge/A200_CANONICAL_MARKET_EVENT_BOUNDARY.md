# A200 — Canonical Market Event Boundary

## Status

IMPLEMENTED

## Contract

```text
provider observation
    -> provider adapter
    -> CanonicalMarketEvent
    -> downstream engine
```

`CanonicalMarketEvent` carries:

```text
record_id
event_type
instrument_id
event_time
available_at
source
source_version
payload
source_timestamp
receipt_timestamp
sequence
provenance
```

The implementation enforces non-empty identity fields, timezone-aware timestamps, `available_at >= event_time`, non-negative sequence values, and immutable payload/provenance mappings.

## E2E integration status

The canonical event is now the first object in the E2E causal chain:

```text
MarketEvent
 -> FeatureSnapshot
 -> PredictionEvidence
 -> [execution gate]
 -> EdgeAssessment
 -> EconomicAssessment
 -> DecisionEligibility
 -> AuthorizedTradeIntent
 -> SelectedInstrument
 -> OrderIntent
 -> ExecutionEvent
 -> PositionState
 -> LifecycleEvaluation
```

The lifecycle boundary is injected and therefore cannot silently invent lifecycle parameters. It is the implementation seam for the authoritative lifecycle/protection contract.

## Causality

`event_time` is the causal market timestamp. `available_at` is the earliest timestamp at which the event may influence downstream computation. Receipt latency remains separate in `receipt_timestamp`.

## Boundary rule

Provider-specific semantics terminate at the external adapter. A200 does not define provider mappings, feature formulas, prediction targets, economic thresholds, risk parameters, option-selection rules, execution semantics, or lifecycle parameters.

## Execution authorization

The E2E orchestrator evaluates the existing strategy execution gate before invoking locked edge mathematics. If required strategy formulas are unresolved, the trace terminates after prediction and records the causal prefix for replay.

This is intentional fail-closed behavior.
