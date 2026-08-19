# A216 — F-110 Canonical Order Intent Recovery

**Status:** `[SOURCE-RECOVERED / IMPLEMENTED / GATED]`

F-110 produces the canonical order intent consumed by the execution boundary.

## Contract

A valid intent requires:

```text
order_intent_id
selection_id
instrument_id
side ∈ {BUY, SELL}
quantity > 0
intent_version
idempotency_key
created_at
```

The intent is immutable and fingerprintable. The factory derives deterministic identity from the causal selection, instrument, side, quantity, version, timestamp, and deterministic namespace.

## Boundary

The factory does not authorize or submit execution.

```text
Decision
  -> Risk
  -> Instrument
  -> OrderIntentFactory
  -> CanonicalOrderIntent
  -> ExecutionGateway
  -> require_execution_authorized()
  -> broker
```

This preserves the execution governance boundary. `ExecutionGateway.submit()` remains the crossing point and fails closed when required strategy formulas are not authorized.

## Idempotency

Identical causal inputs produce identical `order_intent_id`, `idempotency_key`, and fingerprint. Changing a causal input such as quantity produces a different identity.

The downstream `ExecutionAdapter` additionally rejects reuse of an idempotency key with a different intent fingerprint.

## Resolution

```text
Canonical fields       RECOVERED
Deterministic identity  IMPLEMENTED
Idempotency             IMPLEMENTED
Validation              IMPLEMENTED
Execution authorization GATED
Production promotion    LOCKED
```
