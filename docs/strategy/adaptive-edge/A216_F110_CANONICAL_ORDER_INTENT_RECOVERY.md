# A216 — F-110 Canonical Order Intent Recovery

**Status:** `[SOURCE-RECOVERED / IMPLEMENTATION RECONCILIATION]`
**Formula:** F-110 / order-construction boundary

## 1. Role

F-110 converts an already authorized instrument and bounded quantity into a canonical order intent. It does not create authorization, select direction, or change risk.

```text
Decision
  -> Economic eligibility
  -> Risk authorization
  -> Instrument
  -> F-110 CanonicalOrderIntent
```

## 2. Required fields

A canonical order intent must contain, at minimum:

```text
order_intent_id
idempotency_key
instrument identifier
side
quantity
order type
creation timestamp
strategy/version identity
causal parent identifiers
```

All quantities must be positive and valid for the selected contract's lot constraints.

## 3. Authorization boundary

F-110 may only construct an executable intent from an explicitly authorized trade state. A direct caller cannot bypass the execution gate by constructing an order intent from a prediction or option candidate alone.

## 4. Idempotency

The idempotency key must be deterministic for a replay of the same canonical decision context and unique across distinct trade intents.

Repeated submission of the same intent must not create an independent economic position.

## 5. Causal timestamp

The intent creation timestamp must be at or after the causal decision point and must not precede its parent decision/input events.

## 6. Risk preservation

F-110 must preserve the quantity and risk authorization established by F-108. It must not increase quantity, widen risk, or replace the selected instrument with a different contract.

## 7. Failure behavior

Invalid authorization, missing instrument identity, non-positive quantity, invalid lot multiple, missing idempotency identity, or causal timestamp violation must fail closed.

## 8. Production status

This artifact establishes the contract. Production execution remains blocked until the complete required formula set is promoted and the execution gate authorizes submission.
