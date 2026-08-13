# A128 — Instrument & Contract Identity Specification

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.0  
**Depends on:** A75 canonical market events; A127 execution lifecycle and broker adapter contract.

## 1. Purpose

A128 defines exactly what an instrument/contract is. A display or provider symbol is never sufficient identity.

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

Venue and segment are mandatory. The initial execution scope is NSE equity/derivatives.

The same display symbol can represent different instruments across venues or segments; therefore symbol-only identity is invalid.

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

## 6. Provider mapping

```text
Canonical Instrument
        |
        +--> Dhan security_id
        +--> Dhan trading_symbol
        +--> TrueData symbol / symbol_id
        +--> NSE exchange symbol
```

Mappings are effective-dated. Provider identifier changes cannot mutate canonical identity.

Dhan's documented instrument master supplies Security IDs and fields including exchange, segment, underlying, trading symbol, lot size, expiry, strike, option type, tick size and buy/sell indicator. These are provider facts mapped into the canonical contract.

## 7. Authority precedence

For NSE derivatives:

```text
NSE contract rules
    >
Dhan provider metadata
    >
provider display/trading symbol
```

A conflict between exchange contract rules and provider metadata blocks the affected instrument until reconciled.

NSE publishes contract information, permitted lot sizes and quantity-freeze information. These are external facts, not learned parameters.

## 8. Lot size

Lot size is dynamic contract metadata, never a permanent strategy constant.

```text
lot_size = effective contract metadata at execution time
```

No automatic quantity rounding is permitted.

NSE periodically revises derivative market lots. Therefore a value observed today must not be hard-coded as the permanent lot size of an underlying.

## 9. Tick size

Tick size is the minimum permitted price increment of the effective contract.

Invalid price increments are rejected rather than silently rounded.

Exchange contract rules are authoritative; broker metadata is a provider mapping.

## 10. Quantity constraints

The registry distinguishes:

```text
lot_size
quantity_step
quantity_freeze
```

They are not interchangeable.

If quantity violates the effective contract constraint:

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

Provider forms such as CALL/PUT are adapter mappings.

Therefore:

```text
NIFTY 25000 CE != NIFTY 25100 CE
NIFTY 25000 CE != NIFTY 25000 PE
```

Strike and option type are identity components, not merely descriptive fields.

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

Failure blocks execution. The adapter must not invent or silently repair contract semantics.

## 18. Dependency contract

| Dependency | Authority | Consumer | Failure |
|---|---|---|---|
| Contract definition | NSE | contract registry | block affected instrument |
| Lot size | NSE effective contract | risk/execution | reject quantity |
| Tick size | NSE contract rules | execution | reject price |
| Tradability | exchange/broker | execution | unknown/block |
| Dhan Security ID | Dhan | broker adapter | mapping failure |
| Dhan trading symbol | Dhan | broker adapter | mapping failure |
| TrueData symbol ID | TrueData | data adapter | data unavailable |
| Underlying mapping | NSE/Dhan | all consumers | ambiguous identity |

## 19. Frozen vs dynamic

Frozen architecture:

```text
identity is explicit
identity is time-effective
provider identifiers are mappings
exchange rules outrank provider display metadata
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
provider symbol change
stale instrument master
invalid strike
expired option
future contract metadata leaking into history
invalid tick increment
quantity above freeze
provider/exchange contradiction
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
- provider mapping boundary
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
- provider Security IDs
- provider symbol mappings

BLOCKERS:
None.

NEXT ARTIFACT:
A129 — Canonical Market Data Normalization and Temporal Integrity Contract
```
