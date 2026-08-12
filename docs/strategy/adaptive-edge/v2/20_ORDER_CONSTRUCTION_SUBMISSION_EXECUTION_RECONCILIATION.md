# Adaptive Edge V2 — Order Construction, Submission and Execution-Reconciliation State Machine

**Artifact:** A44  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** FRAMEWORK-ONLY

## 1. Purpose

A44 defines the boundary from an authorized order intent to provider submission, provider acknowledgement/rejection, fills, cancellation, uncertainty resolution, and reconciliation.

It does not invent broker behavior, fill guarantees, latency, slippage, order-type semantics, or retry semantics not established by the execution-provider contract.

The canonical boundary is:

```text
Validated OrderIntent
        |
        v
OrderConstruction
        |
        v
SubmissionRequest
        |
        v
Provider Response
        |
        +------> Rejection
        |
        v
SubmissionAccepted
        |
        v
FillEvents / StatusEvents
        |
        v
ExecutionReconciliation
        |
        v
Position / Accounting
```

## 2. Provider boundary

For Adaptive Edge V2:

```text
TrueData
    = market/research observation provider

Zerodha Kite Connect
    = execution provider
```

TrueData observations must not be interpreted as broker acceptance, order status, fill confirmation, or position truth.

Kite provider responses and confirmed execution events must not be substituted for historical market observations used by the research pipeline.

## 3. Order construction

Order construction converts a validated canonical `OrderIntent` into a provider-specific submission request.

Conceptually:

```text
OrderIntent
    -> ProviderOrderRequest
```

The provider request must preserve, where applicable:

```text
intent_id
idempotency identity
instrument identity
direction
quantity
order type
price parameters
validity
authorization reference
strategy/policy versions
submission context
```

Provider-specific fields belong inside the adapter boundary.

The adapter must not alter strategy quantity or direction without producing an explicit canonical event describing the transformation.

## 4. Submission identity

Every submission attempt must have a stable identity sufficient to distinguish:

```text
logical order intent
submission attempt
provider order identity
```

Retries must not create duplicate logical orders.

A provider-specific idempotency mechanism remains external to A44 where the provider does not expose one directly.

The adapter must therefore maintain a canonical submission identity and reconcile uncertain outcomes before allowing another submission for the same logical intent.

## 5. Submission state

Canonical architectural states are:

```text
NOT_SUBMITTED
SUBMISSION_PENDING
SUBMITTED
ACCEPTED
REJECTED
UNKNOWN
CANCEL_PENDING
CANCELLED
EXPIRED
COMPLETED
```

`UNKNOWN` is a first-class state.

An ambiguous network response must not be converted to `REJECTED` merely because no success response was received.

Likewise, absence of a local acknowledgement must not be interpreted as proof that no broker-side order exists.

## 6. Submission timestamps

The system must preserve:

```text
decision_time
order_intent_time
construction_time
submission_attempt_time
provider_receive/acceptance time when available
provider order time when available
fill time
reconciliation time
```

These timestamps must not be collapsed into one execution timestamp.

## 7. Authorization validity at submission

Before submission, the adapter/orchestrator must verify that the order intent references a still-valid authorization under the resolved authorization policy.

Conceptually:

```text
AuthorizationValid(t_submission)
```

If authorization validity cannot be established, submission must fail closed.

A43 does not yet define the exact authorization duration or revalidation interval, so A44 does not invent them.

## 8. Quantity invariant

The provider request must not exceed the canonical authorized/sized quantity.

At minimum:

```text
requested_provider_quantity <= canonical_intent_quantity
```

unless an explicit provider contract defines an equivalent representation that preserves economic quantity.

Provider-side quantity normalization, lot conversion, or rounding must be explicit and auditable.

## 9. Direction invariant

Direction is explicit:

```text
BUY
SELL
```

It must not be inferred from signed quantity, P&L, or position state.

The provider adapter maps canonical direction to provider-specific representation.

## 10. Price semantics

A44 consumes the price semantics resolved by A35.

It does not assume:

```text
last = executable price
mid = fill price
quote = fill
```

For a price-bearing order, the provider request must preserve the canonical price reference, tick semantics, and calculation timestamp required by the execution policy.

If those semantics are unresolved, the order must not be submitted merely by choosing a conventional fallback.

## 11. Market orders

A market order means whatever the provider's authoritative contract defines.

A44 does not claim that a market order has:

```text
zero slippage
fixed execution price
immediate full fill
```

Actual fills remain execution truth.

## 12. Limit and stop orders

For order types requiring prices or triggers, the canonical order must preserve:

```text
order type
trigger/limit value where applicable
price unit
tick/rounding rule
calculation timestamp
validity
```

Provider-specific restrictions remain adapter concerns, but an unsupported canonical order must fail explicitly rather than silently changing order type.

## 13. Provider acknowledgement

Provider acknowledgement establishes provider-side acceptance/rejection according to the provider contract.

It does not establish a fill.

Therefore:

```text
ACKNOWLEDGED != FILLED
```

A provider order identifier must be recorded when supplied.

## 14. Fill truth

Only confirmed fill events establish executed quantity and execution price.

Conceptually:

```text
OrderIntent
    -> ProviderOrder
    -> FillEvent(q, p, t)
```

The cumulative filled quantity is derived from fill events, subject to the provider/accounting contract.

## 15. Partial fills

A partially filled order remains an open execution process until the remaining quantity is either:

```text
filled
cancelled
expired
otherwise terminal under provider semantics
```

The system must preserve each fill independently.

Example:

```text
requested = Q
fill_1 = q1
fill_2 = q2
...
filled = Σ q_i
```

No unfilled quantity may be represented as executed quantity.

## 16. Cancellation

Cancellation is an order-state action, not a position-state action.

```text
CancelRequest
    -> ProviderCancelResponse
    -> CancellationStatus
```

A cancellation acknowledgement does not erase already-confirmed fills.

If an order is partially filled before cancellation, the resulting position reflects the fills that actually occurred.

## 17. Cancellation uncertainty

If cancellation is submitted but provider state is uncertain, the order remains:

```text
UNKNOWN / CANCEL_PENDING
```

until authoritative reconciliation resolves it.

The system must not assume that cancellation succeeded merely because the cancellation request was sent.

## 18. Network uncertainty

The following sequence is explicitly possible:

```text
client submits
    |
network failure
    |
no response
```

This does not imply:

```text
order rejected
```

The broker may have accepted the request.

Therefore blind retry is forbidden until the logical order state is reconciled according to provider-supported mechanisms.

## 19. Duplicate-order prevention

For a logical intent `I`:

```text
I -> submission attempt A
```

must not become:

```text
I -> A
I -> B
```

merely because A returned an ambiguous result.

The system must first attempt to determine whether A created a provider order.

## 20. Reconciliation

Execution reconciliation compares canonical intent/submission state with authoritative provider execution state.

Conceptually:

```text
Canonical OrderIntent
        |
        +--> Submission Ledger
        |
        v
Provider Order State
        |
        +--> Provider Trade/Fills
        |
        v
Canonical Execution State
```

A mismatch is a reconciliation exception, not a reason to silently mutate the original intent.

## 21. Reconciliation invariants

Subject to provider quantity semantics:

```text
0 <= cumulative_filled_quantity <= requested_quantity
```

and:

```text
position_quantity
    = fill-derived quantity
```

not:

```text
position_quantity = submitted quantity
```

## 22. Provider state versus canonical state

Provider statuses must be mapped into canonical states through a versioned adapter mapping.

Unknown provider statuses must remain explicit:

```text
PROVIDER_STATUS_UNKNOWN
```

rather than being guessed from textual similarity.

Provider corrections must create correction lineage rather than overwrite prior canonical records.

## 23. Execution cost

A44 records execution facts required by A35/A37:

```text
fill price
filled quantity
fill timestamp
provider references
explicit cost records where available
```

It does not infer fees, slippage, taxes, or commissions when provider semantics are unavailable.

## 24. Slippage

Slippage is a derived economic quantity, not an assumed fill property.

If a slippage calculation is later defined, it must reference:

```text
canonical expected/reference price
actual fill price
quantity
instrument/unit semantics
timestamp
policy version
```

A44 does not select the formula.

## 25. Position handoff

After confirmed fills, the execution subsystem emits canonical fill events to the position/accounting subsystem:

```text
FillEvents
    -> PositionLifecycle
    -> Accounting
```

The execution subsystem does not directly fabricate position state.

## 26. Protection handoff

A filled entry may activate downstream protection according to A36.

Execution confirmation does not itself select a stop, target, trailing rule, or exit policy.

Likewise, a protection trigger does not itself establish an exit fill.

## 27. Order completion

An order is execution-complete only when its terminal status and all applicable fill/cancellation information are known under provider semantics.

Possible terminal outcomes include:

```text
FULLY_FILLED
CANCELLED_UNFILLED
CANCELLED_PARTIALLY_FILLED
REJECTED
EXPIRED
```

Exact provider-to-canonical mapping remains provider-defined.

## 28. Failure states

A44 requires explicit reason codes for:

```text
AUTHORIZATION_INVALID
INSTRUMENT_INVALID
QUANTITY_INVALID
ORDER_TYPE_UNSUPPORTED
PRICE_INVALID
PROVIDER_REJECTED
PROVIDER_UNAVAILABLE
SUBMISSION_UNKNOWN
RECONCILIATION_FAILED
DUPLICATE_PREVENTED
CONTRACT_DATA_UNAVAILABLE
POLICY_VERSION_INVALID
```

A generic `NO_TRADE` must not erase an execution-specific failure.

## 29. Causal restrictions

Execution reconciliation must not alter historical pre-trade decisions using information that became available only after submission.

For example:

```text
future fill
-> revise historical authorization
```

is forbidden.

Execution outcomes become later events and may affect future state only through explicit policy transitions.

## 30. Backtest versus live execution

A44 distinguishes:

```text
historical execution model
live broker execution
```

A backtest fill is a modeled event and must not be represented as though a broker actually accepted an order.

A live fill must originate from authoritative provider execution data.

The two domains may share canonical event schemas but not truth provenance.

## 31. Historical replay

Historical replay must preserve the execution model version used to generate modeled fills.

Changing the execution model creates a new evaluation/replay version; it does not rewrite historical fills from a prior model.

## 32. Audit lineage

A complete execution record must permit reconstruction:

```text
Decision
 -> Eligibility
 -> RiskAuthorization
 -> Sizing
 -> OrderIntent
 -> ProviderRequest
 -> ProviderOrder
 -> ProviderStatusEvents
 -> FillEvents
 -> Position
 -> Accounting
```

Every transition requires identifiers, timestamps, versions, and provenance sufficient for deterministic replay.

## 33. Determinism

Given identical:

```text
OrderIntent
provider contract version
provider response/event sequence
adapter mapping version
```

the canonical execution state sequence must be deterministic.

## 34. Adversarial cases

### Ambiguous submission

```text
request sent
response lost
```

Result:

```text
UNKNOWN
```

until reconciled. Never blindly submit a duplicate.

### Partial fill then cancel

```text
requested Q
filled q
cancel remainder
```

Result:

```text
executed = q
remaining = Q-q
```

The position reflects `q`, not `Q`.

### Rejected order

A rejection creates no position unless independent confirmed fills exist.

### Provider correction

A corrected fill creates correction lineage; it does not erase the original event.

### Stale authorization

If authorization validity cannot be established at submission time, execution fails closed.

### Provider unavailable

Provider unavailability does not imply order rejection. The state remains unresolved until the provider state can be determined or the provider contract supplies a definitive failure response.

## 35. Implementation gate

A44 framework code may be implemented now for:

```text
order identity
state transitions
idempotency
canonical event schemas
provider adapter boundary
reconciliation framework
failure/reason codes
lineage
```

Live execution remains blocked until A35 provider semantics and the required Kite contract details are fully resolved.

## 36. Parameter classes

### Frozen architecture

```text
OrderIntent -> provider request separation
submission != acknowledgement != fill
partial-fill preservation
cancellation != position closure
unknown submission state
idempotency
fill-derived position truth
reconciliation boundary
backtest/live provenance separation
append-only correction lineage
fail-closed execution
```

### Source-defined configuration

```text
Kite order types
Kite status mapping
Kite quantity rules
Kite tick rules
Kite cancellation semantics
Kite order/trade identifiers
Kite error semantics
```

### Learned

No learned execution parameter is introduced by A44.

### External UNKNOWN

```text
provider idempotency guarantees
provider latency
provider event ordering guarantees
historical execution records
exact provider status/event completeness
execution-cost semantics
```

## 37. Completion criterion

A44 becomes `RESOLVED` when the system can deterministically reconstruct, for every live or modeled execution:

```text
canonical intent
provider request
submission attempt
provider acknowledgement/rejection
provider order identity
all fills
partial-fill state
cancellation/expiry state
execution cost provenance
reconciliation result
position handoff
```

without duplicate submission or future-information leakage.

## ARCHITECTURE STATUS

**FROZEN:** canonical execution state machine; provider boundary; idempotency; unknown-state handling; fill truth; partial-fill handling; cancellation separation; reconciliation; audit lineage; live/backtest provenance separation; fail-closed behavior.

**UNRESOLVED:** exact Kite status mapping; provider idempotency semantics; order-type restrictions; latency/event guarantees; execution-cost model; exact cancellation/reconciliation API behavior.

**BLOCKERS:** A35 execution semantics and provider-specific contract details remain incomplete. A32/A33 also block risk-authorized sizing from becoming executable.

**NEXT ARTIFACT:** A45 — Data Quality, Staleness and Market-State Validity Contract.
