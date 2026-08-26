# A59 — Execution Boundary Contract

**Status:** FRAMEWORK IMPLEMENTED / PROVIDER SEMANTICS BLOCKED

## Purpose

A59 freezes the boundary between an authorized trading decision and an actual execution event.

```text
Decision
  -> Authorization
  -> OrderIntent
  -> Submission
  -> Acceptance / Rejection
  -> Fill events
  -> Position effect
```

These are distinct causal events.

## OrderIntent

The immutable order intent contains:

```text
intent_id
opportunity_id
authorization_id
sizing_id
instrument_id
direction
quantity
order_type
decision_time
strategy_version
execution_policy_version
```

The intent is not a broker acknowledgement and not a fill.

## Lifecycle separation

```text
AUTHORIZED
    |
    +--> SUBMISSION_REJECTED
    |
    v
SUBMITTED
    |
    +--> PARTIALLY_FILLED --> FILLED
    |
    +--> CANCELLED
    |
    +--> EXPIRED
```

Only confirmed fills contribute to cumulative executed quantity.

## Required invariants

```text
authorization identity == OrderIntent.authorization_id

cumulative_filled_quantity <= requested_quantity

fill_time >= submission_time

rejection != execution

order intent != fill
```

A rejected submission cannot be treated as an executed order. A partially filled order cannot be treated as fully filled.

## Timestamp separation

The architecture preserves:

```text
decision_time
order_intent_time
submission_time
acceptance_time
fill_time
```

The implementation does not assign a fixed latency or collapse these events.

## Provider boundary

```text
Adaptive Edge
    |
    v
Canonical Execution Boundary
    |
    v
Provider Adapter
    |
    v
Broker / Execution Venue
```

Provider-specific authentication, statuses, idempotency mechanisms, order types, tick rules, price semantics, latency and fill semantics remain outside this framework until authoritative provider documentation resolves them.

TrueData remains a market-data provider and does not supply execution semantics for this contract.

## Fail-closed rule

If required execution semantics are unknown, ambiguous, stale, or unavailable:

```text
NO EXECUTION
+ explicit reason
+ provenance
```

No midpoint fill, zero-slippage assumption, fallback market order, or invented provider behavior is permitted.

## Relationship to A58

A58 records why authorization existed. A59 records the boundary after authorization and prevents authorization from being conflated with submission, acceptance, or fill.

## Relationship to A45

A45 derives accounting truth from confirmed execution events. A59 therefore does not directly mutate position or P&L state from an order intent.

## Implementation boundary

The current framework intentionally does not implement live order routing. It establishes canonical intent and lifecycle invariants so a future provider adapter can be added without changing strategy semantics.
