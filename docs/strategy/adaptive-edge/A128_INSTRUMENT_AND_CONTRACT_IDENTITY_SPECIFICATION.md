# A128 — Instrument & Contract Identity Specification

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH
**Version:** 1.0

## Purpose
Define the immutable, venue-specific, time-effective identity of every tradable instrument and derivative contract.

## Core invariant

```text
resolve(instrument_id, event_time) -> exactly one contract or explicit failure
```

A provider symbol is never canonical identity.

## Canonical identity

```text
instrument_id
venue
segment
instrument_type
underlying_instrument_id?
expiry_date?
strike_price?
option_type?
lot_size
tick_size
quantity_step
quantity_freeze?
tradability_status
valid_from
valid_to?
contract_version
source
source_timestamp
```

Option identity requires underlying + expiry + strike + option type + venue/segment + contract version.

## Authority

```text
NSE contract rules > Dhan provider metadata > display/trading symbol
```

Dhan Security IDs and trading symbols are provider mappings. TrueData symbol IDs are provider mappings.

## Causality

Historical events resolve against metadata effective at the event timestamp. Current metadata must never be applied retrospectively.

## Validation

Execution requires unique identity, effective contract, tradable state, valid expiry/strike/option type, valid lot/quantity, valid tick/price, and permitted side.

No automatic rounding or silent contract substitution is permitted.

## Dynamic facts

Lot size, tick size, active expiries, tradability and provider identifiers are dynamic external facts, not learned strategy parameters.

## Architecture status

```text
COMPLETE
UNRESOLVED: none at architectural-contract level
BLOCKERS: none
NEXT: A129 — Canonical Market Data Normalization and Temporal Integrity Contract
```
