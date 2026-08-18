# A217 — F-111 Canonical Execution Event Recovery

**Status:** `[SOURCE-RECOVERED / EXISTING IMPLEMENTATION RECONCILED]`
**Formula:** F-111 / broker execution normalization boundary

## 1. Role

F-111 converts an external broker/provider execution notification into the canonical execution-event model used by Adaptive Edge state projection.

It does not infer fills, manufacture broker references, or turn an order acknowledgement into a fill.

## 2. Canonical event

Required identity:

```text
execution_event_id
order_intent_id
event_type
event_time
```

Observed broker reference is retained where available.

Fill events additionally require:

```text
filled_quantity > 0
fill_price is present
```

Non-fill events must not carry fill quantity or price.

The existing canonical execution adapter already enforces these invariants. fileciteturn93file0L2-L6

## 3. Evidence classification

Execution evidence must preserve whether the event is:

```text
OBSERVED
RECONSTRUCTED
MODELED
ASSUMED
UNKNOWN
```

An inferred historical fill must not be represented as an observed broker event.

## 4. Causality

The broker event's `event_time` is the economic occurrence time. Receipt time is separate metadata:

```text
event_time <= receipt_time
```

when both are available.

Historical replay must preserve the original event time and deterministic ordering. Receipt latency must not be substituted for economic event time.

## 5. Fill semantics

```text
SUBMITTED / ACKNOWLEDGED
    -> no fill data

PARTIALLY_FILLED
    -> positive filled quantity + fill price

FILLED
    -> positive filled quantity + fill price

REJECTED / CANCELLED / EXPIRED
    -> no fill data
```

A partial fill remains a partial fill; it cannot be promoted to `FILLED` merely because the requested quantity was expected to execute.

## 6. Idempotency

Repeated delivery of the same broker event must not create duplicate position transitions. Event identity and parent order identity are preserved for downstream projection.

## 7. Failure behavior

Reject:

```text
missing execution identity
missing order parent
missing event time
negative filled quantity
fill without price
non-fill carrying fill data
unknown evidence class
```

## 8. Resolution

The existing `CanonicalExecutionEvent` and normalization boundary already implement the required structural validation. fileciteturn93file0L2-L6

F-111 therefore requires integration/replay validation rather than a second execution-event data model.

## 9. Production boundary

Canonical event normalization does not authorize execution. The execution gate remains the sole production authorization boundary.
