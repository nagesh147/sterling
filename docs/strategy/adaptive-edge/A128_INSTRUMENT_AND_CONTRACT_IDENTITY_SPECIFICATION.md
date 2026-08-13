# A128 — Instrument & Contract Identity Specification

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.1  
**Depends on:** A75 canonical market events; A127 Execution Lifecycle and Broker Adapter Contract.

## 1. Purpose

A128 defines exactly what an instrument/contract is. A display or provider symbol is never sufficient canonical identity.

```text
CANONICAL CONTRACT
= VENUE + SEGMENT + INSTRUMENT TYPE + CONTRACT ATTRIBUTES + EFFECTIVE VERSION
```

The contract must resolve uniquely at a specific event/execution timestamp.

## 2. Canonical identity

Required semantics:

```text
instrument_id
venue
segment
instrument_class
instrument_type
canonical_symbol
underlying_instrument_id?
expiry_date?
strike_price?
option_type?
contract_multiplier?
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

`instrument_id` is immutable. A change in economic contract meaning creates a new effective version rather than rewriting history.

## 3. Identity invariant

```text
resolve(instrument_id, event_time) -> exactly one contract or explicit failure
```

Forbidden:

```text
one identity -> two different contracts at the same time
latest_metadata() used for historical events
provider symbol used as canonical primary key
current contract metadata applied to old fills
```

## 4. Venue and segment

Venue and segment are mandatory. Initial execution scope is NSE equity/derivatives.

The same display symbol can represent different instruments across venues or segments; symbol-only identity is invalid.

## 5. Effective dating and causality

Every contract record is time-effective:

```text
valid_from
valid_to
source_timestamp
contract_version
```

Historical resolution is:

```text
contract = resolve(instrument_id, event_timestamp)
```

Never use the newest contract master to reinterpret historical events. This prevents look-ahead and historical contract corruption.

## 6. Kite instrument mapping

Kite Connect's instrument dump provides:

```text
instrument_token
exchange_token
tradingsymbol
name
expiry
strike
tick_size
lot_size
instrument_type
segment
exchange
```

Kite explicitly recommends `exchange + tradingsymbol` as the storage key rather than relying on `instrument_token`, because instrument tokens can be reused for different derivative instruments after expiry. citeturn2view0

Therefore:

```text
canonical instrument_id
        |
        +--> Kite exchange
        +--> Kite tradingsymbol
        +--> Kite instrument_token
```

Kite identifiers are provider/exchange mappings, not the canonical identity.

## 7. Authority precedence

For NSE contracts:

```text
NSE effective contract rules
    >
Kite instrument metadata
    >
provider/display symbol parsing
```

A conflict between authoritative exchange contract rules and Kite metadata blocks the affected instrument until reconciled.

## 8. Lot size

Lot size is dynamic contract metadata, never a permanent strategy constant.

```text
lot_size = effective contract metadata at execution time
```

No automatic quantity rounding is permitted.

Historical events retain the lot size effective for their contract version.

## 9. Tick size

Tick size is the minimum permitted price increment of the effective contract.

Invalid price increments are rejected rather than silently rounded.

Exchange rules are authoritative; Kite provides the execution mapping.

## 10. Quantity constraints

The registry distinguishes:

```text
lot_size
quantity_step
quantity_freeze
```

They are not interchangeable.

If quantity violates an effective contract/exchange constraint:

```text
EXECUTION_INELIGIBLE
```

No silent resizing or slicing occurs at the identity layer.

## 11. Option identity

Canonical option identity requires:

```text
underlying_instrument_id
expiry_date
strike_price
option_type
venue
segment
contract_version
```

Canonical option type:

```text
CE
PE
```

Therefore:

```text
NIFTY 25000 CE != NIFTY 25100 CE
NIFTY 25000 CE != NIFTY 25000 PE
```

Strike and option type are identity components, not descriptive fields.

## 12. Expiry

Store the actual expiry date.

```text
weekly/monthly/near/far = classification
expiry_date = identity
```

Do not infer expiry from display-symbol parsing when authoritative metadata exists.

## 13. Contract version

Create a new effective version when economic interpretation changes, including:

```text
lot-size revision
tick-size revision
expiry-rule revision
strike-scheme revision
settlement-rule revision
tradability eligibility change
```

Historical orders, fills and labels remain attached to the contract version applicable at their event time.

## 14. Tradability state

Canonical states:

```text
TRADABLE
NOT_TRADABLE
SUSPENDED
EXPIRED
UNKNOWN
```

Only `TRADABLE` permits execution.

Forbidden:

```text
EXPIRED -> TRADABLE
UNKNOWN -> TRADABLE without authoritative evidence
```

## 15. Buy/sell permission

Preserve venue/provider restrictions where available:

```text
BUY_ALLOWED
SELL_ALLOWED
BOTH_ALLOWED
NEITHER_ALLOWED
UNKNOWN
```

A strategy cannot override a venue prohibition.

## 16. Instrument lifecycle

```text
UNRESOLVED
   |
   v
IDENTIFIED
   |
   +--> INVALID
   |
   v
TRADABLE
   |
   +--> SUSPENDED
   +--> EXPIRED
```

Transitions require authoritative evidence and timestamps.

## 17. Execution validation

Before execution:

```text
identity resolves uniquely
venue/segment match
contract effective at execution time
tradability == TRADABLE
expiry valid
option type valid where applicable
strike valid where applicable
quantity respects lot/step
price respects tick size
requested side permitted
contract version recorded
```

Failure blocks execution. No provider adapter may invent or silently repair contract semantics.

## 18. Dependency contract

| Dependency | Authority | Consumer | Failure |
|---|---|---|---|
| NSE contract definition | NSE | contract registry | block affected instrument |
| Lot size | NSE effective contract | risk/execution | reject quantity |
| Tick size | NSE contract rules | execution | reject price |
| Tradability | exchange/Kite | execution | unknown/block |
| Kite instrument mapping | Kite instrument dump | broker adapter | mapping failure |
| Kite instrument token | Kite | market-data adapter | mapping failure |
| Underlying mapping | NSE/Kite | all consumers | ambiguous identity |

Kite's instrument dump is generated daily, so it is a reference-data input rather than a realtime tradability guarantee. citeturn2view0

## 19. Frozen vs dynamic

Frozen architecture:

```text
identity is explicit
identity is time-effective
provider identifiers are mappings
exchange rules outrank provider metadata
lot/tick/expiry are metadata, not strategy constants
historical events use historical contract versions
unknown contract state blocks execution
contract changes create versions
```

Not learned:

```text
instrument identity
lot size
expiry
strike
option type
tick size
```

These are external facts, not statistical parameters.

## 20. Hostile review

The contract must survive:

```text
symbol collision across venues
expiry rollover
lot-size revision
Kite instrument-token reuse
stale daily instrument dump
invalid strike
expired option
future contract metadata leaking into history
invalid tick increment
quantity above freeze
NSE/Kite metadata contradiction
```

Required result is explicit resolution failure or execution block. Silent substitution is forbidden.

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- canonical instrument identity
- venue/segment identity
- effective-dated contract resolution
- derivative/option identity
- Kite provider mapping boundary
- exchange-over-provider precedence
- lot/tick/quantity validation semantics
- tradability state
- contract versioning
- historical metadata causality
- execution blocking on unresolved identity

UNRESOLVED:
None at architectural-contract level.

INTENTIONALLY DYNAMIC:
- effective lot sizes
- effective tick sizes
- active expiries
- tradability
- Kite instrument tokens
- Kite trading-symbol mappings

BLOCKERS:
None.

NEXT ARTIFACT:
A129 — Canonical Market Data Normalization and Temporal Integrity Contract
```
