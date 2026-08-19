# A216 — F-110 Canonical Order Intent Recovery

**Status:** `[SOURCE-RECOVERED / IMPLEMENTED / GATED]`

F-110 produces the canonical order intent consumed by the execution boundary.

## Contract

A valid intent requires `order_intent_id`, `selection_id`, `instrument_id`, `side`, positive `quantity`, `intent_version`, `idempotency_key`, and `created_at`.

The intent is immutable and fingerprintable. The factory derives deterministic identity from the causal selection, instrument, side, quantity, version, timestamp, and deterministic namespace.

## Boundary

The factory does not authorize or submit execution. `ExecutionGateway.submit()` remains the crossing point and fails closed when required strategy formulas are not authorized.

## Idempotency

Identical causal inputs produce identical identity and fingerprint. Changing a causal input produces a different identity. The downstream execution adapter rejects reuse of an idempotency key with a different intent fingerprint.

## Production status

The contract is implemented and gated. Production execution remains locked until the complete required formula set is promoted.
