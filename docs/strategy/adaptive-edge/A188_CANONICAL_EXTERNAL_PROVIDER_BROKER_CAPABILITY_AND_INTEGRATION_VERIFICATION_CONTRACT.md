# A188 — Canonical External Provider, Broker Capability & Integration Verification Contract

## Status
CANONICAL

## Purpose
Defines the boundary between frozen Adaptive Edge semantics and external provider behavior. No external guarantee may be invented.

## Provider ownership
```text
TrueData -> market/research data
Kite     -> trading/execution
```
No Dhan dependency exists in the Adaptive Edge architecture.

## Capability record
Each required capability binds:
```text
capability_id
provider
api/version
required_semantics
verification_method
evidence
verified_at
status
revalidation_policy
```
Status:
```text
UNKNOWN | UNVERIFIED | VERIFIED | DEGRADED | REVOKED
```
UNKNOWN/UNVERIFIED cannot satisfy a production gate.

## TrueData boundary
Every consumed field must have verified semantics for timestamp, availability, historical coverage, quote/option contract identity, and liquidity/depth where applicable. Missing fields remain unavailable; they are never fabricated.

## Kite boundary
Execution semantics requiring empirical verification include authentication/session behavior, order submission, acknowledgement, rejection, cancellation, replacement, partial fills, trade identity, position reporting, and reconciliation. Kite fills are execution evidence; Kite positions are broker-position evidence.

## Evidence preservation
Provider evidence is retained separately from canonical interpretation:
```text
provider evidence != canonical interpretation
```
Normalization must not erase the source evidence needed for audit or replay.

## Uncertainty
Timeout, disconnect, malformed response, rate limit, authentication failure, schema change, or ambiguous acknowledgement becomes explicit provider uncertainty/degradation. It cannot silently become an assumed failure, flat position, absent fill, or current quote.

## Retry
A retry is permitted only when the uncertainty/idempotency contract proves that retry cannot duplicate consequential effects.

## Capability drift
A previously verified capability becomes revalidation-required when provider behavior, schema, authentication, or API revision materially changes.

## Verification hierarchy
```text
mock tests
 -> adapter contract tests
 -> sandbox/paper verification where available
 -> controlled provider verification
 -> production monitoring
```
Mocks do not establish provider guarantees.

## Provider separation
TrueData observations cannot establish that a Kite order filled. Kite execution evidence cannot be substituted by a market-data observation.

## Invariants
```text
INV-188-001 provider semantics cannot be invented
INV-188-002 unknown capability cannot satisfy production readiness
INV-188-003 provider evidence remains traceable
INV-188-004 market data cannot establish broker execution
INV-188-005 broker evidence cannot be replaced by model assumptions
INV-188-006 ambiguous submission remains uncertain until reconciled
INV-188-007 retries require idempotency safety
INV-188-008 capability drift can revoke verification
INV-188-009 provider version is part of production evidence
INV-188-010 no silent fallback provider is introduced
```

## Adversarial tests
```text
submit timeout
duplicate response
delayed fill
schema change
timestamp regression
authentication expiry
rate limit
partial fill
cancel/fill race
position mismatch
unknown order status
outage/recovery
```

## Parameter classes
Frozen: provider boundary, evidence preservation, capability status, uncertainty semantics, no silent fallback.

Configuration: retry policy, timeouts, revalidation cadence, rate limits, monitoring thresholds.

Validation-dependent: provider reliability, execution cost, and latency distributions.

## Status
ARCHITECTURE STATUS: COMPLETE
UNRESOLVED: None at architectural-contract level.
UNKNOWN / TODO: exact TrueData field semantics, exact Kite session/order guarantees, API-version behavior, sandbox availability.
BLOCKERS: External provider verification remains required before real-money production.
NEXT ARTIFACT: A189 — Canonical Final Conformance Matrix, Production Readiness Evidence & Architecture Closure Contract
