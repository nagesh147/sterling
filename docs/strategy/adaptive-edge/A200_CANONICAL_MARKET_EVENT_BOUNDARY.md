# A200 — Canonical Market Event Boundary

## Status

IMPLEMENTATION IN PROGRESS

## Contract

The external data boundary is:

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

## Causality

`event_time` is the causal market timestamp. `available_at` is the earliest timestamp at which the event may influence downstream computation. Receipt latency remains separate in `receipt_timestamp`.

## Boundary rule

Provider-specific semantics terminate at the external adapter. A200 does not define TrueData mappings and does not invent feature formulas, prediction targets, economic thresholds, risk parameters, option-selection rules, or execution semantics.

## Next

A201 connects canonical events to the existing causal FeatureSnapshot boundary.
