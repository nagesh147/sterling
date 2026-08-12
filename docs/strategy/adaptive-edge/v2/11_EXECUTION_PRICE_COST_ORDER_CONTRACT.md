# Adaptive Edge V2 — Execution Price, Cost and Order Contract

**Artifact:** A35
**Version:** 2.0.0-draft
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED
**Market/research data:** TrueData only
**Trading/execution provider:** Zerodha Kite Connect v3 only
**Implementation:** PARTIAL — Kite execution infrastructure exists; Adaptive Edge strategy-specific execution policy remains unresolved

## 1. Purpose

A35 defines the boundary between a selected instrument and an executable order while separating reference price, expected execution price, submitted order price, fill price, expected cost, and realized cost.

```text
TrueData
  -> market/research observation

Adaptive Edge
  -> decision / authorization / order intent

Zerodha Kite
  -> order submission / order status / trades / positions
```

Adaptive Edge does not execute through TrueData.

## 2. Causal dependency

```text
SelectedInstrument(t_d)
        |
        v
ExecutionState(t_d)
        |
        v
ExpectedExecution
        |
        v
OrderIntent
        |
        v
Kite Order Submission
        |
        v
Kite Order Status / Trade
        |
        v
Fill
```

All pre-trade quantities use only information available at their decision timestamp.

## 3. Provider authority

The execution provider is frozen as:

```text
ZERODHA_KITE_CONNECT_V3
```

The repository's Kite integration documents REST trading, order history/trades, positions, GTT and KiteTicker. It also documents live-safety/idempotency controls.

Provider-specific authentication, identifiers, statuses, transport and error semantics remain inside the Kite adapter.

## 4. Price concepts

```text
ReferencePrice
ExpectedExecutionPrice
SubmittedOrderPrice
FillPrice
```

These are distinct.

A TrueData quote is a market observation. A Kite fill is execution truth.

Every price must identify:

```text
instrument
price type
value
observation timestamp
availability timestamp
source
source version
freshness/validity state
```

No `last = executable price` assumption is permitted.

## 5. Executable-price policy

The exact Adaptive Edge executable-price policy is UNKNOWN.

Kite provides market/limit/SL/SL-M order capabilities, but capability does not determine strategy policy.

The strategy must explicitly define the order type and price rule for each order action before live execution is authorized.

## 6. OrderIntent

```text
OrderIntent {
    intent_id
    opportunity_id
    authorization_id
    sizing_id
    instrument_id
    direction
    quantity
    order_type
    price_parameters
    validity
    strategy_version
    execution_policy_version
    decision_time
    provenance
}
```

This represents strategy intent, not broker acceptance.

Direction is explicit `BUY` or `SELL`.

## 7. Order/fill/position separation

The following are distinct:

```text
OrderIntent
KiteOrder
KiteOrderStatus
KiteTrade/Fill
KitePosition
```

Actual position quantity derives from confirmed fills, not from order intent.

```text
OrderIntent -> KiteOrder -> KiteFillEvents -> Position
```

## 8. Order types

Provider capabilities include:

```text
MARKET
LIMIT
SL
SL-M
GTT/protective order
```

These are capabilities, not strategy decisions.

No order type is selected by convention.

## 9. Protective-order constraint

The repository's Kite contract states that Kite does not provide a generic per-order SL/TP bracket. Protective exits therefore require an explicitly supported Kite mechanism such as an SL/SL-M order or GTT, subject to the later position/protection policy.

No stop distance or protective-order trigger is invented here.

## 10. Expected execution cost

Potential components include:

```text
spread
slippage
brokerage
exchange charges
taxes/levies
other documented costs
```

None is automatically included.

Each component requires:

```text
source
semantic definition
unit
timestamp/availability
estimation method
version
```

```text
ExpectedExecutionCost != RealizedExecutionCost
```

Realized cost comes from actual Kite execution/accounting events and cannot be substituted into the contemporaneous pre-trade decision.

## 11. Fill model

A historical simulator requires an explicit fill model covering, where applicable:

```text
order type
price reference
latency
quote availability
partial fills
fill sequencing
cancellation
price improvement
slippage
```

Historical simulated fills must be marked `SIMULATED` and must never be represented as observed Kite fills.

## 12. Partial fills and statuses

```text
OrderIntent(Q)
 -> KiteOrder
 -> Fill(q1)
 -> Fill(q2)
 -> ...
```

Canonical architecture includes:

```text
SUBMISSION_REJECTED
SUBMITTED
PARTIALLY_FILLED
FILLED
CANCELLED
EXPIRED
```

Provider-to-canonical status mapping must be explicit.

## 13. Execution timestamps

Keep distinct:

```text
decision_time
order_intent_time
submission_time
acceptance_time
fill_time
position_observation_time
```

No fixed latency value is selected.

## 14. Market-data / execution separation

```text
TrueData quote -> market observation
Kite trade/fill -> execution truth
Kite position   -> broker position truth
```

A quote cannot prove that an order filled at that price.

A Kite position cannot replace the TrueData market observation used by an earlier decision.

## 15. Causal restrictions

Pre-trade execution economics cannot use future:

```text
fill
slippage
cancellation
rejection
P&L
```

Learned cost parameters may use prior mature Kite execution observations only through the V2 temporal learning/promotion protocol.

## 16. Units

Expected gross value and expected execution cost must be dimensionally compatible before:

```text
ExpectedNetValue = ExpectedGrossValue - ExpectedExecutionCost
```

Any points-to-currency or contract-multiplier conversion must be explicitly defined by the instrument/economic contract.

## 17. Idempotency

An `OrderIntent` is immutable. Changes create new events/intent versions.

Order submission must have an idempotency identity so uncertain retries cannot silently create duplicate orders.

The repository already documents Kite-side live-safety idempotency deduplication. The exact Adaptive Edge intent-to-provider-key mapping remains unresolved.

Blind retry after an uncertain provider response is forbidden.

## 18. Kite operational constraints

The existing repository documents:

```text
Kite Connect v3 access tokens expire daily
no refresh token
historical API requires the paid Historical Data add-on
Kite order/GTT writes are form-encoded
Kite margin calculators are JSON
quote requests have tighter rate limits than general requests
```

These are provider constraints and must be represented by operational readiness checks, not hidden strategy parameters.

## 19. Execution attacks

### Stale TrueData price

A stale TrueData quote cannot automatically be treated as a current execution reference.

### Midpoint fill

A midpoint fill without explicit fill-model evidence may overstate achievable economics.

### Partial fill

Assuming the complete requested quantity filled at one price may create impossible historical results.

### Duplicate submission

Retrying an uncertain Kite submission without idempotency/reconciliation can create duplicate exposure.

### Session expiry

Expired Kite authentication must block new live orders. There is no fallback execution provider.

### Rate limiting

A Kite rate-limit response must not be silently ignored. If delay makes the market state stale, execution must fail closed or follow an explicitly versioned recovery policy.

## 20. Reconciliation invariant

```text
requested_quantity >= cumulative_confirmed_fill_quantity >= 0
```

subject to provider quantity semantics.

The final position is reconstructed from confirmed fills.

## 21. Failure behavior

If required Kite execution semantics are missing, stale, ambiguous, unauthorized, or unavailable:

```text
NO_EXECUTION
+ explicit reason
+ provenance
```

No fallback broker, midpoint fill, zero slippage, or assumed execution behavior is permitted.

## 22. Parameter classes

**Frozen:**

```text
TrueData/Kite separation
price-concept separation
OrderIntent contract
submission/fill separation
partial-fill architecture
position-from-fill truth
Kite provider boundary
causal timestamps
idempotency
fail-closed execution
```

**Source-defined configuration:**

```text
Kite order types
validity
provider statuses
tick rules
quantity handling
GTT semantics
```

**Learned:** execution-cost/slippage parameters may later be learned from prior Kite execution observations under temporal promotion rules.

**External UNKNOWN:** exact strategy order-type policy, executable-price rule, fill model, latency model, cost model, protective-exit policy, intent-to-Kite idempotency mapping.

## 23. Implementation gate

A35 cannot become live-executable until:

```text
selected instrument contract = resolved
Kite order-type semantics = resolved
execution price policy = resolved
fill semantics = resolved
protection mechanism = resolved
cost model = resolved
authorization-to-order mapping = resolved
```

Provider interfaces may exist before these are resolved, but unresolved semantics must remain explicit.

## 24. Completion criterion

A35 becomes RESOLVED when an order can be reconstructed as:

```text
TrueData market state
 -> Adaptive Edge order intent
 -> Kite submission
 -> Kite acknowledgement/rejection
 -> Kite fills
 -> realized execution cost
 -> Kite position effect
```

with complete timestamps, quantities, prices, statuses, provenance, and policy versions.

## ARCHITECTURE STATUS

**FROZEN:** TrueData market authority; Kite execution authority; price concept separation; OrderIntent contract; submission/fill separation; partial-fill architecture; position-from-fill truth; Kite adapter boundary; causal timestamps; idempotency; fail-closed execution.

**UNRESOLVED:** strategy order-type policy; executable-price policy; historical fill model; latency model; execution-cost model; protective-exit policy; authorization-to-order mapping.

**BLOCKERS:** Strategy-specific execution semantics remain unresolved. This blocks live order routing, not the execution architecture.

## NEXT ARTIFACT

**A36 — Position Lifecycle and Protection Contract.**
