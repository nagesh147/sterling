# A127 — Execution Lifecycle and Broker Adapter Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.0  
**Scope:** Translation of an authorized execution intent into broker-native orders; observation and normalization of acknowledgements, order states and fills; cancellation/replacement; execution uncertainty; reconciliation; position/execution lineage; and execution auditability.

**Depends on:** A126 Adaptive Trade Horizon, Position Protection & Lifecycle Contract; canonical market-event, instrument, risk, economics and decision contracts that precede execution.

**Does not define:** signal generation, horizon selection, thesis evaluation, protection thresholds, trading-edge estimation, position-sizing methodology, profitability logic, or learned trading parameters.

---

## 1. Purpose

A127 defines the boundary between the strategy/lifecycle system and external execution infrastructure.

The canonical causal path is:

```text
STRATEGY DECISION
      |
      v
EXECUTION INTENT
      |
      v
EXECUTION INSTRUCTION
      |
      v
ORDER REQUEST
      |
      v
BROKER ORDER
      |
      v
BROKER ACK / ORDER EVENTS
      |
      v
FILL(S)
      |
      v
POSITION EFFECT
      |
      v
RECONCILIATION
```

The system must distinguish:

```text
what the strategy requested
what the system submitted
what the broker accepted
what the broker reports
what actually filled
what exposure actually exists
```

These are different facts and must not be collapsed.

Core invariant:

```text
EXECUTION INTENT != ORDER
ORDER != ACKNOWLEDGEMENT
ACKNOWLEDGEMENT != FILL
FILL != POSITION OBSERVATION
POSITION OBSERVATION != STRATEGY THESIS
```

A broker adapter must never manufacture execution certainty from strategy intent.

---

## 2. Architectural role

A127 is an execution boundary and anti-corruption layer.

```text
Canonical Internal Model
          |
          | canonical execution contract
          v
+-----------------------------+
| Broker Adapter              |
|                             |
| validation                  |
| capability mapping          |
| request translation         |
| response normalization      |
| identity preservation       |
| error classification        |
| reconciliation              |
+-----------------------------+
          |
          v
Broker-specific API
```

Broker-specific semantics must remain inside the adapter unless explicitly promoted into a canonical contract.

Forbidden in strategy/lifecycle code:

```text
if broker == X
if provider_status == "broker-specific-value"
if dhan_order_type == ...
```

A provider-specific mapping is not canonical business logic.

---

## 3. Canonical execution entities

A127 defines these primary entities:

```text
ExecutionIntent
ExecutionInstruction
OrderRequest
Order
OrderEvent
ExecutionFill
ExecutionError
PositionObservation
ReconciliationRecord
```

Their causal relationship is:

```text
ExecutionIntent
      |
      v
ExecutionInstruction
      |
      v
OrderRequest
      |
      v
Order
      +----> OrderEvent*
      +----> ExecutionFill*
                    |
                    v
             Position Effect
```

One intent may produce:

```text
0 fills
1 fill
many fills
partial fills
rejection
cancellation
expiration
ambiguous execution
```

Therefore:

```text
one intent != one fill
one order != one execution event
```

---

## 4. ExecutionIntent

`ExecutionIntent` is the immutable canonical economic instruction emitted by the upstream strategy/lifecycle layer.

It answers:

> What economic action does the internal system want to attempt?

Minimum semantics:

```text
intent_id
position_id
source_decision_id
created_at
side
instrument_id
quantity
execution_policy_reference
urgency_reference
valid_until
risk_context_reference
economics_context_reference
model_version
configuration_version
```

The exact upstream field names are implementation details; the semantics are frozen.

### Invariants

```text
intent_id is unique
intent is immutable after publication
quantity is non-negative
valid_until >= created_at
instrument_id resolves to an authoritative instrument contract
```

A changed economic action requires a new intent or explicitly versioned correction. An existing intent must not be silently mutated after submission.

Forbidden:

```text
reuse intent_id for another economic action
change side after submission
change quantity silently after submission
extend validity without an explicit new authorization
```

---

## 5. ExecutionInstruction

`ExecutionInstruction` is the broker-independent execution representation derived from an authorized intent.

Conceptual semantics:

```text
intent_id
instrument_id
side
quantity
order_type
limit_price?
trigger_price?
time_in_force
execution_constraints
```

An adapter may reject an instruction when the selected broker cannot faithfully represent the required semantics.

It must not silently downgrade semantics.

Example forbidden behavior:

```text
CANONICAL LIMIT ORDER
        |
        +--> broker lacks limit support
        |
        +--> silently convert to MARKET
```

Such a conversion changes economic meaning and requires explicit upstream authorization.

---

## 6. Execution eligibility

Before submission, the execution subsystem must validate the execution-facing conditions that are authoritative at submission time.

Minimum checks:

```text
intent exists
intent is authorized
intent is not expired
instrument is valid and tradable
quantity conforms to instrument contract
requested order semantics are supported
required session state permits execution
required execution data is sufficiently fresh
no conflicting unresolved execution exists
```

A127 does not independently invent risk policy. It consumes the upstream risk/economics authorization and verifies that the execution request remains consistent with that authorization.

Critical distinction:

```text
ENTRY_ELIGIBLE != EXECUTION_ELIGIBLE
```

---

## 7. Order identity and lineage

Every economically meaningful action requires stable identity.

Where available, preserve:

```text
intent_id
order_id
client_order_id
broker_order_id
```

Semantics:

```text
intent_id       = internal economic intent
order_id        = canonical internal order identity
client_order_id = client-generated broker-facing identity
broker_order_id = external broker identity
```

No identifier may be reused for an unrelated economic action.

Canonical lineage:

```text
decision_id
  -> intent_id
      -> order_id
          -> broker_order_id
              -> fill_id(s)
                  -> position effect
```

Loss of lineage is a correctness failure.

---

## 8. Idempotency and ambiguous submission

The execution layer must assume that submission responses can be lost.

Example:

```text
client -> broker: SUBMIT
broker -> client: accepted
network failure
client: no response
```

The client cannot conclude that the order was rejected.

Therefore:

```text
TRANSPORT FAILURE != BUSINESS REJECTION
UNKNOWN RESPONSE != NO ORDER
```

Canonical state:

```text
SUBMISSION_UNKNOWN
```

Required sequence:

```text
SUBMISSION_UNKNOWN
      |
      v
RECONCILE BROKER STATE
      |
      +----> accepted / working
      +----> rejected
      +----> absent
      +----> unresolved
```

Blind resubmission of an economically equivalent order is forbidden while the previous submission remains unresolved.

This is a primary protection against duplicate exposure.

---

## 9. Order lifecycle

Canonical states:

```text
INTENT_CREATED
    |
    v
VALIDATING
    |
    +----> INVALID
    |
    v
SUBMITTING
    |
    +----> SUBMISSION_UNKNOWN
    |
    v
SUBMITTED
    |
    +----> REJECTED
    +----> EXPIRED
    +----> CANCELLED
    |
    v
WORKING
    |
    +----> PARTIALLY_FILLED
    |             |
    |             v
    |           FILLED
    |
    +----> CANCEL_PENDING
    |             |
    |             +----> CANCELLED
    |             +----> FILLED / PARTIALLY_FILLED
    |             +----> UNKNOWN
    |
    +----> EXPIRED
```

Broker-native states may be richer. They must be normalized into canonical states without losing the original broker evidence.

---

## 10. State-transition contract

Every state transition requires:

```text
transition_id
trigger
precondition
prior_state
new_state
event_time
receipt_time
source
```

Postconditions must be mechanically checkable.

Example:

```text
WORKING
  --first execution event-->
PARTIALLY_FILLED
```

requires:

```text
filled_quantity > 0
remaining_quantity >= 0
filled_quantity <= accepted_quantity
```

A complete fill requires:

```text
remaining_quantity = 0
```

---

## 11. Forbidden transitions

The following are invalid as ordinary transitions:

```text
FILLED -> WORKING
CANCELLED -> WORKING
REJECTED -> FILLED
EXPIRED -> PARTIALLY_FILLED
FILLED -> CANCELLED
```

If later evidence contradicts the current derived state, the system must create a reconciliation/correction event rather than overwrite history.

```text
CONTRADICTORY EVIDENCE
        |
        v
RECONCILIATION_REQUIRED
```

---

## 12. Partial fills

Partial fills are first-class execution states and immediately create actual exposure.

For an order, define:

```text
Q_requested
Q_accepted
Q_filled
Q_remaining
```

The canonical accounting relationship is constrained by the broker's documented order semantics. At minimum:

```text
0 <= Q_filled <= Q_accepted <= Q_requested
```

unless an authoritative broker contract explicitly documents a different adjustment mechanism.

A partial fill immediately enters position supervision:

```text
PARTIAL_FILL
      |
      v
ACTUAL_EXPOSURE EXISTS
      |
      v
POSITION SUPERVISION
```

It must not wait for full order completion.

---

## 13. Fill identity and timestamps

Each fill must have a unique canonical `fill_id`.

Where supplied, preserve `broker_fill_id`.

Canonical fill semantics:

```text
fill_id
order_id
broker_fill_id?
instrument_id
side
quantity
price
event_time
receipt_time
source
fees?
```

At minimum distinguish:

```text
decision_time
intent_time
submission_time
ack_time
broker_event_time
receipt_time
fill_time
reconciliation_time
```

When authoritative event time is unavailable:

```text
event_time = UNKNOWN
```

Do not fabricate timestamps from receipt time and label them as broker event time.

When broker event time exists and is trustworthy:

```text
event_time <= receipt_time
```

Network arrival order must not be treated as economic event order.

---

## 14. Execution price

The system must distinguish:

```text
reference_price
observed_executable_price
submitted_price
accepted_price
fill_price
average_fill_price
```

Actual execution economics must use actual fill prices.

For multiple fills:

```text
P_avg = sum(q_i * p_i) / sum(q_i)
```

where `q_i` and `p_i` are canonical filled quantities and fill prices for the aggregation being computed.

LTP, midpoint, signal price, theoretical option value, or another reference price must never be substituted for actual fill price in realized execution accounting.

---

## 15. Slippage boundary

Execution analysis may later decompose execution cost into components such as:

```text
decision-to-submission movement
submission-to-fill movement
spread cost
market impact
```

But these decompositions are not frozen by A127 because their validity depends on market-data timestamp and quote semantics.

Therefore:

```text
UNKNOWN:
authoritative quote source
quote timestamp semantics
bid/ask reconstruction capability
tick/quote availability at decision time
```

No slippage formula may be claimed as canonical until these dependencies are resolved.

---

## 16. Cancellation

Cancellation is asynchronous.

```text
CANCEL_REQUESTED
      |
      v
CANCEL_PENDING
      |
      +----> CANCELLED
      +----> FILLED / PARTIALLY_FILLED
      +----> UNKNOWN
```

Therefore:

```text
cancel_requested != cancelled
```

A fill can occur while cancellation is pending.

The final position must be derived from actual fills and reconciled broker state, not from the cancellation request.

---

## 17. Replacement

Replacement/modification is economically distinct from cancellation.

Original orders remain immutable in history.

Conceptual lineage:

```text
ORDER_001
   |
   +---- REPLACED_BY ----> ORDER_002
```

The replacement must preserve:

```text
parent_order_id
replacement_reason
new order identity
broker mapping
```

A broker capability that cannot guarantee the required semantics must be exposed as unsupported rather than emulated invisibly.

---

## 18. Broker capability contract

Each adapter must expose a capability declaration covering, at minimum:

```text
market_orders
limit_orders
stop/trigger orders
cancel
replace/modify
partial_fills
order_status_query
position_query
fill_query
client_order_id
streaming_events
idempotent_submission
```

The exact supported set is:

```text
TODO / UNKNOWN
```

until verified against the selected broker's authoritative documentation and controlled tests.

Unsupported capability must produce a canonical capability error.

---

## 19. Error taxonomy

Canonical execution errors:

```text
VALIDATION_ERROR
AUTHENTICATION_ERROR
AUTHORIZATION_ERROR
RATE_LIMIT
TRANSPORT_FAILURE
TIMEOUT
BROKER_REJECTION
MARKET_REJECTION
INSTRUMENT_REJECTION
CAPABILITY_ERROR
AMBIGUOUS_RESULT
DATA_UNAVAILABLE
RECONCILIATION_ERROR
UNKNOWN_ERROR
```

Provider-native error code/message must be retained as evidence where available.

Transport failure must never be normalized into business rejection without evidence.

---

## 20. Execution uncertainty

Canonical supervisory states:

```text
EXECUTION_CERTAIN
EXECUTION_UNCERTAIN
RECONCILIATION_REQUIRED
```

Uncertainty occurs when the system cannot establish whether an economically meaningful action occurred.

Examples:

```text
submission timeout
unknown cancellation result
missing fill acknowledgement
conflicting broker responses
broker position query unavailable
```

While an unresolved uncertainty could create duplicate exposure, conflicting new economic execution must be blocked until reconciliation or explicit emergency handling.

---

## 21. Reconciliation

Reconciliation is mandatory because internal state is not authoritative merely because the application believes it is correct.

Compare:

```text
INTERNAL ORDERS
INTERNAL FILLS
INTERNAL POSITION EFFECTS

        vs

BROKER ORDERS
BROKER FILLS
BROKER POSITIONS
```

Canonical reconciliation outcomes:

```text
CONSISTENT
MISSING_INTERNAL_EVENT
MISSING_BROKER_EVENT
QUANTITY_MISMATCH
PRICE_MISMATCH
STATE_MISMATCH
IDENTITY_MISMATCH
AMBIGUOUS
```

A mismatch is an explicit event, not an automatic correction.

---

## 22. Authority model

Authority is domain-specific.

```text
strategy decision history -> internal canonical record
execution intent -> internal canonical record
broker order acceptance -> broker observation
actual external position -> broker observation
actual fills -> broker observation, normalized internally
```

The internal system must not erase a strategy decision because the broker rejected it.

The strategy must not claim an exit occurred because an exit order was submitted.

Therefore:

```text
EXIT_REQUESTED != EXIT_FILLED
```

and:

```text
BROKER_FLAT != STRATEGY_THESIS_INVALID
```

The former is execution truth; the latter is strategy truth.

---

## 23. Position effect

A position effect is derived from actual fills, not merely submitted orders.

Conceptually:

```text
PositionEffect = aggregation of canonical fills
```

For every fill, the system must preserve:

```text
instrument_id
side
quantity
price
fill_time
order lineage
```

Instrument-specific accounting conventions for lot size, contract multipliers, fees, taxes, expiry and corporate actions are dependencies of the instrument/accounting contracts and must not be invented here.

---

## 24. Flatten semantics

`FLATTEN` means reducing actual exposure toward zero. It does not merely mean cancelling orders.

Canonical sequence:

```text
FLATTEN_REQUESTED
      |
      v
cancel conflicting working orders where required
      |
      v
obtain current position truth
      |
      v
submit offsetting instruction
      |
      v
observe fills
      |
      v
reconcile
      |
      v
FLAT_CONFIRMED
```

Therefore:

```text
FLATTEN_REQUESTED != FLAT
```

This distinction is required by A126's 45-minute cutoff and emergency-exit semantics.

---

## 25. Emergency execution

A127 supports execution actions whose purpose is exposure reduction rather than expressing a new trading thesis.

Examples:

```text
HARD_RISK_EXIT
THESIS_INVALIDATION_EXIT
SESSION_CUTOFF_EXIT
EMERGENCY_FLATTEN
RECONCILIATION_FLATTEN
```

Emergency execution may bypass ordinary strategy-entry eligibility, but cannot bypass:

```text
instrument validity
quantity validity
identity integrity
duplicate-submission protection
broker capability validation
```

An emergency request still does not guarantee a fill.

---

## 26. Race conditions

The execution state machine must be correct under concurrent events.

Example:

```text
exit submitted
fill occurs
cancel request sent
cancel acknowledgement arrives
```

Transport order may differ from broker economic order.

Canonical state must therefore be derived from authoritative broker event semantics and reconciliation, not simply from message arrival order.

Invariant:

```text
network arrival order != economic event order
```

---

## 27. Duplicate event handling

Adapters must tolerate duplicate delivery and replay.

Preferred deduplication identities, in order of availability:

```text
broker_event_id
broker_fill_id
broker sequence number
stable broker order/event tuple
```

If the broker supplies no stable event identity:

```text
UNKNOWN
```

and the adapter must document the deterministic deduplication strategy used.

The strategy layer must never depend on duplicate suppression by object identity or process memory alone.

---

## 28. Manual intervention

Manual broker-side action is an execution event.

Examples:

```text
MANUAL_CANCEL
MANUAL_CLOSE
MANUAL_MODIFICATION
BROKER_OPERATOR_ACTION
```

Manual intervention must preserve external evidence and enter reconciliation where it changes exposure.

It must not be represented as system-generated strategy intent.

---

## 29. Recovery from uncertainty

Canonical recovery:

```text
DETECT UNCERTAINTY
      |
      v
BLOCK CONFLICTING NEW EXPOSURE
      |
      v
QUERY AUTHORITATIVE BROKER STATE
      |
      v
RECONSTRUCT MISSING EVENTS
      |
      v
RECONCILE
      |
      +----> CONSISTENT
      |
      +----> UNRESOLVED -> OPERATIONAL ESCALATION
```

Recovery must be idempotent.

A recovery process must not itself create duplicate economic exposure.

---

## 30. Audit contract

Every economically meaningful execution event must be auditable.

Minimum semantics:

```text
audit_id
timestamp
actor
source_decision_id?
intent_id?
order_id?
broker_order_id?
fill_id?
event_type
previous_state
new_state
reason_code
configuration_version
adapter_version
```

Payload hashes/references may be stored where useful.

Credentials, authentication tokens and secrets must never enter audit records.

---

## 31. Reproducibility

Given the same canonical execution inputs and immutable external observations, execution state reconstruction must be deterministic.

Execution state must not depend on hidden:

```text
mutable global state
unversioned configuration
manual undocumented edits
non-deterministic transformations
```

where those affect economic state.

---

## 32. Causal ordering and learning boundary

Execution outcomes are observations of what happened after a decision.

They must never become inputs to an earlier decision.

Canonical lineage:

```text
raw market data
    -> canonical event
    -> strategy state
    -> feature
    -> probability/economics
    -> decision
    -> execution intent
    -> order
    -> fill
    -> position
    -> outcome
    -> label
    -> future learning
```

Execution data may be used for later evaluation and labeling only after the relevant observation horizon has matured.

A127 therefore has no authority to retroactively alter earlier decision state.

---

## 33. Configuration and learned parameters

A127 contains no trading-edge parameters.

Potential operational configuration includes:

```text
request timeout
reconciliation cadence
polling cadence
transport backoff
order validity duration
operational retry limits
```

These are operational parameters, not strategy parameters.

Potential execution-optimization parameters such as:

```text
limit-price offsets
quote aggressiveness
execution slicing
retry timing
cancel/replace behavior
```

must not be optimized for profitability until the baseline execution contract is independently validated.

Any parameter that changes economic semantics requires explicit specification and validation before implementation.

---

## 34. External dependencies

The following are explicitly unresolved:

```text
TODO / UNKNOWN:

1. Selected broker/API and exact order semantics.
2. Broker acknowledgement semantics.
3. Broker event ordering guarantees.
4. Broker fill-event identity guarantees.
5. Broker timestamp semantics.
6. Broker position-query consistency guarantees.
7. Supported order types.
8. Cancel/replace semantics.
9. Idempotency guarantees.
10. Client-order-ID guarantees.
11. Rate limits and throttling behavior.
12. Authoritative exchange/session calendar.
13. Instrument contract/lot/tick/expiry rules.
14. Option contract and expiry semantics.
15. Fee/tax/charge representation.
16. Market-data quote source and freshness semantics.
17. Real-time availability of required execution inputs.
```

No implementation may silently promote an unresolved dependency into a fact.

---

# 35. Hostile review

A127 was attacked against the following failure classes.

### 35.1 Lost acknowledgement

```text
submit -> broker accepts -> response lost
```

Resolution:

```text
SUBMISSION_UNKNOWN -> reconciliation
```

Blind retry is forbidden.

### 35.2 Partial fill during cancellation

```text
cancel requested
remaining quantity fills
cancel acknowledgement arrives
```

Resolution:

Actual fills determine exposure. Cancellation status alone is insufficient.

### 35.3 Duplicate fill

The fill identity/deduplication contract prevents double application where stable broker identity exists. Where it does not, the adapter must use an explicit deterministic strategy and mark the limitation.

### 35.4 Out-of-order delivery

Arrival order is not economic order. Event timestamps/sequences and reconciliation govern reconstruction.

### 35.5 Broker position mismatch

Internal position and broker position are not silently reconciled by preference. The mismatch becomes `RECONCILIATION_REQUIRED`.

### 35.6 Exit rejection

```text
THESIS_INVALID
exit order rejected
```

The position remains exposed. The system must continue risk-reduction handling; it cannot mark the position closed.

### 35.7 Cutoff failure

A126 requires normal flattening by cutoff. If the exit fails, A127 keeps emergency execution available. `FLATTEN_REQUESTED` never becomes `FLAT` without evidence.

### 35.8 Broker outage

No broker response does not imply no exposure.

### 35.9 Duplicate intent

A stable intent/order/client identity and unresolved-submission state prevent blind duplicate economic actions.

### 35.10 Provider semantic leakage

Provider-native statuses and fields remain inside the adapter mapping and are retained only as evidence outside it.

### 35.11 Future-information leakage

Execution outcomes, later fills, later broker state and realized slippage cannot influence the earlier decision that created the intent.

### 35.12 Impossible accounting

Negative quantities, filled quantity exceeding accepted quantity, or contradictory state transitions become validation/reconciliation failures rather than silently normalized values.

---

## 36. Adversarial test requirements

Before implementation can be considered complete, tests must include at minimum:

```text
clean full fill
clean partial fill
multi-fill completion
rejection
timeout after accepted submission
timeout after rejected submission
duplicate acknowledgement
duplicate fill
out-of-order events
cancellation before fill
cancellation after partial fill
cancellation racing with fill
replacement
replacement rejection
broker position mismatch
missing fill history
broker outage
stale intent
invalid instrument
invalid quantity
emergency flatten
cutoff flatten
residual position after flatten
manual intervention
reconciliation recovery
```

Each scenario must assert both:

```text
state-machine correctness
accounting/exposure correctness
```

---

## 37. Contradictions and resolutions

### Contradiction A — A126 requires positions flattened by cutoff

A127 cannot guarantee broker execution. It can guarantee that a flatten instruction is generated, submitted, observed, and reconciled according to the execution contract.

Therefore:

```text
A126 = policy requirement
A127 = execution mechanism and truth observation
```

### Contradiction B — Broker is authoritative

The broker is authoritative for actual external exposure and broker-observed execution. It is not authoritative for the strategy's historical decision semantics.

Authority is therefore domain-specific.

### Contradiction C — Executable price required by A126

A127 cannot define executable quote semantics without an authoritative market-data contract. The dependency remains unresolved rather than being filled with LTP or midpoint assumptions.

### Contradiction D — Options

A127 can execute an option contract but cannot determine whether the option economics justify the trade. That belongs to upstream economics/strategy contracts.

### Contradiction E — Retry

A generic retry mechanism is unsafe for economically meaningful order submission. Retry is therefore not an automatic transport primitive for submission. It is conditional on idempotency or reconciliation evidence.

---

# 38. Architecture invariants

The following are frozen:

```text
1. Intent, instruction, order, acknowledgement, fill and position are distinct.
2. Execution identity is stable and lineage-preserving.
3. Partial fills create immediate actual exposure.
4. Cancellation is asynchronous.
5. Replacement preserves immutable order lineage.
6. Submission uncertainty is a first-class state.
7. Blind resubmission during unresolved execution is forbidden.
8. Broker-native semantics are isolated behind an adapter.
9. Broker state is reconciled rather than blindly trusted or ignored.
10. Actual position is derived from actual fills and broker observation.
11. Flatten requested is not equivalent to flat.
12. Emergency execution exists independently of normal strategy entry eligibility.
13. Execution timestamps preserve causal ordering.
14. Network arrival order is not economic event order.
15. Contradictory evidence creates reconciliation/correction records; it does not erase history.
16. Execution outcomes cannot leak backward into earlier decisions.
17. Secrets cannot enter canonical execution/audit records.
18. Unknown external semantics remain explicitly UNKNOWN/TODO.
```

---

# 39. Implementation source-of-truth rule

A127 is the canonical source of truth for:

```text
execution lifecycle
broker interaction semantics
order/fill identity
partial-fill handling
submission uncertainty
cancellation
replacement lineage
reconciliation
execution audit
```

If implementation, configuration, or another document contradicts A127, implementation must stop at the contradiction until the specification is reconciled.

No hidden execution business logic may be added in code or configuration.

Any new execution requirement must update A127 before implementation changes are accepted.

---

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- execution intent/order/fill/position separation
- immutable economic intent
- stable execution identity and lineage
- partial-fill semantics
- ambiguous submission handling
- cancellation/replacement lifecycle
- broker adapter anti-corruption boundary
- canonical error taxonomy
- execution uncertainty state
- reconciliation requirement
- domain-specific authority model
- flatten semantics
- emergency execution path
- causal timestamp model
- audit and reproducibility requirements
- no backward leakage from execution outcomes

UNRESOLVED:
- selected broker/API
- exact broker order/fill semantics
- event ordering guarantees
- fill identity guarantees
- timestamp guarantees
- supported order types
- cancel/replace capabilities
- idempotency guarantees
- rate limits
- authoritative session calendar
- authoritative instrument contract
- option contract semantics
- fee/tax representation
- executable quote source/freshness

BLOCKERS:
None for further specification.

Production execution implementation remains blocked until the unresolved broker, instrument, session and market-data dependencies are documented and verified.

NEXT ARTIFACT:
A128 — Instrument & Contract Identity Specification
```
