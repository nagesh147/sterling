# A145 — Canonical External Dependency, Environment & Provider Capability Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.0

## Purpose

Define the boundary between Adaptive Edge's frozen internal semantics and external systems whose behavior must be documented, verified, measured, or adapted.

A145 prevents external behavior from being silently promoted into strategy semantics.

It governs:

```text
provider identity
provider capability
provider authority
environment identity
session/calendar dependency
clock dependency
network dependency
credential dependency
provider limits
provider failure semantics
capability verification
adapter conformance
external-data provenance
```

A145 does not invent unavailable provider guarantees and does not redefine A126-A144 business logic.

---

## 1. First principle

External dependencies are not assumed to be correct merely because an API returned successfully.

```text
API RESPONSE
    !=
CANONICAL TRUTH
```

A provider capability becomes usable only when its semantics are explicitly documented or empirically verified to the degree required by the consuming contract.

Unknown capability is represented as unknown.

```text
UNKNOWN != SUPPORTED
UNKNOWN != UNSUPPORTED
UNKNOWN != SAFE
```

---

## 2. Canonical external dependency classes

```text
MARKET_DATA_PROVIDER
EXECUTION_PROVIDER
INSTRUMENT_REFERENCE_PROVIDER
SESSION_CALENDAR_PROVIDER
CLOCK/TIME SOURCE
PERSISTENCE PROVIDER
SECRET/IDENTITY PROVIDER
OBSERVABILITY PROVIDER
NETWORK/TRANSPORT
```

A provider may implement multiple classes only if each capability is independently declared and verified.

---

## 3. Current provider boundary

The current Adaptive Edge architecture uses the following provider roles:

```text
TrueData
    -> market-data / market-observation dependency

Zerodha Kite Connect
    -> execution / broker-state dependency
```

These names identify the architectural roles only.

The following remain external facts requiring provider documentation/verification before implementation relies on them:

```text
exact API endpoint semantics
message/order guarantees
rate limits
latency guarantees
historical-data completeness
timestamp semantics
instrument mapping semantics
session behavior
reconnect behavior
order-state guarantees
fill-report guarantees
position-report guarantees
idempotency guarantees
authentication/session lifetime
provider-side retention
```

No Dhan dependency is introduced by this artifact.

---

## 4. Provider capability record

Every external capability must have a canonical capability record:

```text
provider_id
provider_version
capability_id
capability_class
semantic_description
source_documentation
owner
availability
input_contract
output_contract
timestamp_semantics
update_frequency
rate_limit
failure_modes
retry_semantics
idempotency_semantics
data-retention semantics
authority_scope
verification_status
verified_at
verification_method
adapter_version
```

If a field is not known:

```text
UNKNOWN
```

must be stored rather than inferred.

---

## 5. Capability states

```text
UNKNOWN
DOCUMENTED
VERIFIED
DEGRADED
UNAVAILABLE
REVOKED
```

A capability may only be treated as production-usable when the consuming contract's minimum verification requirement is satisfied.

`DOCUMENTED` and `VERIFIED` are distinct states.

Provider documentation is evidence of stated behavior; verification establishes that the deployed dependency behaves consistently enough for the required contract.

---

## 6. Capability ownership

For every dependency:

```text
source
owner
semantic definition
update frequency
timestamp
allowed consumers
invariants
failure behavior
```

must be explicit.

A consumer may only use capabilities declared in its dependency contract.

A provider cannot become an implicit dependency merely because its data happens to be available in the runtime.

---

## 7. Market-data dependency

TrueData is treated as a source of market observations, not as the owner of Adaptive Edge state.

Canonical flow:

```text
TrueData
   |
   v
Provider Observation
   |
   v
A129 Canonical Market Event
   |
   v
A130+ Internal State
```

Provider-native symbols, timestamps, statuses, and payload formats must be normalized before consumption by canonical domain contracts.

A129 owns the resulting canonical market-event semantics.

---

## 8. Execution-provider dependency

Zerodha Kite Connect is treated as the external execution/broker-state dependency.

Canonical flow:

```text
A135 Order Intent
      |
      v
Kite Adapter
      |
      v
Kite
      |
      +--> order evidence
      +--> trade/fill evidence
      +--> position/account evidence
```

Kite-specific identifiers and statuses remain provider evidence until mapped through the canonical execution contract.

A135 owns execution semantics; A145 owns the external capability boundary.

---

## 9. Provider authority versus internal authority

A provider can be authoritative for a specific external fact without becoming authoritative for the entire domain.

For example:

```text
Kite
    -> authoritative external evidence of broker order/trade state

A135
    -> canonical internal execution lifecycle

A136
    -> canonical position-state representation
```

A mismatch must be represented as a reconciliation condition, not silently resolved by whichever component reads the data last.

---

## 10. Timestamp contract

Every provider observation must preserve, where available:

```text
provider_event_time
provider_sequence/reference
provider_receipt_time
local_receipt_time
canonical_available_at
```

The system must not invent exchange/event timestamps from local receipt time.

If the provider supplies no authoritative event timestamp:

```text
provider_event_time = UNKNOWN
```

and the consuming contract decides whether the observation remains usable.

---

## 11. Clock dependency

Time is an explicit dependency.

The runtime must distinguish:

```text
wall_clock
monotonic_clock
provider/exchange time
canonical event time
availability time
processing time
```

Clock synchronization requirements are configuration/operational concerns and must not be guessed.

A clock anomaly must be observable and may block operations whose causal correctness depends on reliable time.

---

## 12. Session/calendar dependency

Trading-session semantics are external domain data.

The runtime must not hard-code exchange holidays, session boundaries, expiry schedules, or cutoff semantics unless they are explicitly versioned configuration backed by an authoritative source.

Canonical dependency:

```text
calendar source
    -> session/contract events
    -> A126/A128 lifecycle semantics
```

Unknown session state must not be treated as an open session.

---

## 13. Instrument mapping dependency

Provider instrument identifiers are mappings, not canonical identities.

Required mapping lineage:

```text
provider_instrument_id
    -> mapping_version
    -> A128 instrument_id
```

A missing, ambiguous, stale, or conflicting mapping blocks operations that require exact contract identity.

No symbol-string heuristic is an acceptable substitute for canonical identity.

---

## 14. Network and transport

Transport state is explicitly represented:

```text
CONNECTED
DEGRADED
DISCONNECTED
UNKNOWN
```

A successful TCP/HTTP/WebSocket connection does not prove semantic availability of the provider capability.

Transport failure must not be translated into domain facts such as:

```text
no position
no order
no market movement
```

---

## 15. Rate limits and quotas

Provider rate limits are external constraints.

Until verified:

```text
rate_limit = UNKNOWN
```

The system must not assume unlimited requests or invent a safe retry frequency.

Rate-limit responses must remain distinguishable from provider outages and invalid requests.

---

## 16. Retry semantics

Retry behavior is capability-specific.

The default architectural rule is:

```text
UNKNOWN outcome
    -> reconcile when state may already have changed
```

Retries are forbidden where repeating the operation could create duplicate exposure and provider idempotency has not been verified.

Examples include order submission and state-changing control operations.

---

## 17. Provider idempotency

For every state-changing provider operation, capability status must explicitly answer:

```text
Does the provider support client-generated idempotency?
What is its scope?
How long is it retained?
What happens after timeout?
Can the same request be safely repeated?
```

If unknown:

```text
blind retry = forbidden
```

A135 reconciliation remains the safety boundary.

---

## 18. Authentication/session dependency

Authentication capabilities are governed by A144.

A145 records provider-specific facts such as:

```text
credential type
session establishment
session expiry
refresh mechanism
reconnect behavior
permission scope
provider-side revocation behavior
```

Until verified, each is `UNKNOWN`.

Authentication success does not imply authorization to perform every provider operation.

---

## 19. Persistence dependency

Persistence technology is not part of canonical semantics.

A145 requires persistence to provide, at minimum:

```text
durability
atomicity where required
version/addressability
ordered lineage
read-after-write behavior where required
recovery semantics
```

Exact database/storage technology remains implementation-specific.

If a required durability or atomicity guarantee cannot be established, the corresponding runtime operation is not production-ready.

---

## 20. Environment identity

A runtime environment must be explicitly identified:

```text
environment_id
build/version
configuration_version
model_version
policy_version
adapter_versions
data-source versions
timezone
calendar version
execution mode
account scope
```

Canonical execution modes:

```text
BACKTEST
REPLAY
SIMULATION
SHADOW
LIVE
```

Cross-environment semantics must remain explicit.

A simulation environment must never accidentally inherit live credentials or live execution authority.

---

## 21. Environment isolation

The following boundaries must be independently controlled:

```text
SIMULATION != LIVE
SHADOW != LIVE
RESEARCH != PRODUCTION
TEST != PRODUCTION
```

A production credential must not be available to a research/test runtime unless an explicit, audited operational policy permits it.

The default is denial.

---

## 22. Provider capability matrix

Before production use, the following capability classes must have explicit status:

```text
Market observation
Historical market data
Instrument reference
Session/calendar
Quote/executable-price semantics
Order submission
Order status
Order cancellation
Order modification
Trade/fill reporting
Position reporting
Account/risk reporting
Authentication
Rate limits
Reconnect behavior
Provider idempotency
Provider retention
```

No capability may be assumed merely because an adjacent capability exists.

For example:

```text
order submission supported
    !=
order idempotency supported
```

---

## 23. External dependency failure state

A dependency can be:

```text
AVAILABLE
DEGRADED
UNAVAILABLE
UNKNOWN
```

A dependency failure propagates only to consumers that actually require that capability.

For example:

```text
market-data unavailable
    -> new signal evaluation blocked

broker execution unavailable
    -> new execution blocked

audit unavailable
    -> normal new exposure blocked per A143/A142
```

An unrelated capability must not be falsely marked unavailable.

---

## 24. Capability verification lifecycle

```text
IDENTIFIED
    |
    v
DOCUMENTED
    |
    v
TESTED
    |
    v
VERIFIED
    |
    +--> DEGRADED
    +--> REVOKED
```

Verification must record:

```text
capability_id
provider_version
test/version context
verification date
verification evidence
known limitations
review owner
```

Provider upgrades may invalidate previous verification.

---

## 25. Provider upgrade rule

A provider version change is not automatically backward-compatible.

```text
Provider V1 verified
       |
       v
Provider V2
       |
       v
verification required
```

The adapter may reject a provider version for which required capabilities have not been verified.

Historical records continue to reference the provider/adapter version that generated them.

---

## 26. Dependency substitution

Replacing a provider requires an explicit compatibility assessment.

```text
Provider A
    -> capability contract

Provider B
    -> capability contract

A == B
```

is not assumed merely because both expose an API with similar names.

A substitution requires semantic equivalence or explicit downstream adaptation.

---

## 27. Unknown external dependency

Unknowns are first-class:

```text
UNKNOWN
    |
    v
capability cannot be consumed where its semantics are mandatory
```

The correct response to an unknown external guarantee is:

```text
adapter constraint
or
runtime degradation/block
or
verification task
```

Never:

```text
reasonable assumption
```

---

## 28. Hostile scenarios

### Provider returns stale data

```text
provider response = success
freshness = invalid
```

Result:

```text
capability = DEGRADED/UNAVAILABLE
```

not valid market evidence.

### Provider reconnects

Reconnect does not automatically prove missed events were recovered.

The adapter must reconcile according to the provider capability contract.

### Order timeout

```text
timeout
    -> UNKNOWN
    -> reconcile
```

not automatic retry.

### Provider changes instrument identifiers

Existing canonical identity remains stable; mapping version changes and must be verified.

### Calendar provider unavailable

Session state becomes unknown unless another explicitly authorized source supplies equivalent evidence.

### Provider version upgrade

Capabilities revert to unverified until compatibility is established.

### Environment misconfiguration

If live mode cannot prove the correct account, credentials, provider, configuration, and model versions, normal new exposure is blocked.

### Data provider says "no data"

This is not equivalent to a market observation of zero volume, zero price movement, or no position.

---

## 29. Frozen architecture

```text
external dependency boundary
provider capability records
provider versus internal authority
explicit provider roles
unknown capability semantics
capability verification lifecycle
environment identity
environment isolation
timestamp preservation
clock/session dependency boundaries
instrument mapping boundary
transport failure semantics
rate-limit boundary
retry/reconciliation boundary
provider idempotency boundary
provider upgrade verification
provider substitution assessment
fail-closed mandatory unknowns
```

## 30. Configuration to validate

```text
provider endpoints
provider versions
rate limits
retry/backoff policies
clock synchronization tolerance
session/calendar source
instrument mapping refresh policy
capability verification cadence
provider health thresholds
environment isolation policy
credential/session configuration
persistence durability settings
```

No numerical value is frozen merely because it appears operationally reasonable.

## 31. UNKNOWN / TODO

The following remain explicitly external until documented/verified:

```text
TrueData exact endpoint and subscription semantics
TrueData historical-data completeness and timestamp guarantees
TrueData reconnect/stream recovery semantics
Kite Connect exact order-state/fill-state guarantees
Kite Connect authentication/session lifecycle details
Kite Connect rate limits and retry guarantees
Kite Connect idempotency guarantees
Kite Connect position/account freshness semantics
canonical session/calendar provider
canonical instrument-reference provider
runtime clock synchronization provider
persistence technology and concrete durability guarantees
identity/secret/key-management technologies from A144
```

These are not architectural blockers because the adapter contracts can be designed around explicit capability interfaces.

They become implementation/release blockers when a specific capability is required for live operation and remains unverified.

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- external dependency boundary
- provider capability contract
- provider/internal authority separation
- explicit TrueData market-data role
- explicit Zerodha Kite execution role
- unknown-capability semantics
- capability verification lifecycle
- environment identity and isolation
- timestamp/clock/session boundaries
- instrument mapping boundary
- transport/rate-limit/retry boundaries
- provider idempotency boundary
- provider upgrade verification
- provider substitution assessment
- fail-closed mandatory unknowns

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- exact provider endpoint semantics
- exact provider guarantees
- session/calendar source
- instrument-reference source
- clock synchronization source
- concrete persistence technology
- concrete identity/secret/key-management technology

CONFIGURATION TO VALIDATE:
- provider endpoints and versions
- rate limits
- retry/backoff policies
- clock synchronization tolerance
- calendar/instrument refresh policy
- capability verification cadence
- environment isolation
- provider health thresholds

LEARNED / VALIDATION-DEPENDENT:
None.

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A146 — Canonical Deployment, Environment Promotion & Release-Gating Contract
```
