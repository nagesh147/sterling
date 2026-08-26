# Adaptive Edge V2 — Execution Price, Cost and Order Contract

**Artifact:** A35  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** NONE

## Purpose

Define the boundary between a selected instrument and an executable order while separating reference price, expected execution price, submitted order price, fill price, expected cost, and realized cost.

No broker or TrueData behavior is invented.

## Causal dependency

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
OrderSubmission
        |
        v
Fill
```

All pre-trade quantities use only information available at their decision timestamp.

## Price concepts

```text
ReferencePrice
ExpectedExecutionPrice
SubmittedOrderPrice
FillPrice
```

These are distinct. A quote is not a fill.

Every price input must identify:

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

No assumption such as `last = executable price` is permitted.

## Executable price

The exact executable-price rule is UNKNOWN because the execution-provider contract is undocumented. Buy-side ask or sell-side bid behavior may be appropriate, but neither is frozen without provider semantics.

## OrderIntent

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

Direction is explicit `BUY` or `SELL` and is not inferred from signed quantity or P&L.

## Order type

Architectural categories only:

```text
MARKET
LIMIT
STOP
STOP_LIMIT
OTHER_PROVIDER_DEFINED
```

No order type is selected by convention.

If a type requires a price/trigger/limit, its semantic meaning, unit, reference, calculation time, validity, rounding/tick rule, and failure behavior must be defined.

## Quantity

Order quantity must reference validated sizing. Execution cannot silently increase it. Any provider modification is a distinct event and cannot overwrite the original intent.

## Expected execution cost

A35 supplies the provenance boundary for:

```text
ExpectedExecutionCost
```

Potential components such as spread, slippage, fees, commissions, and exchange charges are not automatically included. Each requires its own source, semantics, units, timestamp, and estimation method.

```text
ExpectedExecutionCost != RealizedExecutionCost
```

Realized cost is derived from actual fills and cannot be substituted into the contemporaneous pre-trade decision.

## Fill model

A backtest requires an explicit fill model defining, where applicable:

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

Without these semantics, execution-sensitive performance claims are not production-valid.

## Partial fills and statuses

Partial fills are distinct events:

```text
OrderIntent(Q)
 -> Fill(q1)
 -> Fill(q2)
 -> ...
```

Canonical architectural states include:

```text
SUBMISSION_REJECTED
SUBMITTED
PARTIALLY_FILLED
FILLED
CANCELLED
EXPIRED
```

Provider-specific status mappings remain UNKNOWN.

A cancelled unfilled quantity is not executed quantity.

## Execution timestamps

Keep distinct:

```text
decision_time
order_intent_time
submission_time
acceptance_time
fill_time
```

They must not be collapsed into one timestamp.

No fixed latency value is selected.

## Market-data / execution separation

```text
market quote -> market observation
fill event    -> execution truth
```

A quote cannot be treated as evidence that an order filled at that price.

## Causal restrictions

Pre-trade execution economics cannot use future fill, slippage, cancellation, rejection, or P&L. Learned cost parameters may use prior mature execution observations only through the V2 learning/promotion protocol.

## Units

Expected gross value and expected execution cost must be dimensionally compatible before:

```text
ExpectedNetValue = ExpectedGrossValue - ExpectedExecutionCost
```

Any points-to-currency conversion must be explicitly defined.

## Provider adapter boundary

```text
Strategy OrderIntent
        |
        v
Canonical Execution Adapter
        |
        v
Provider/Broker
```

Provider-specific fields, statuses, authentication, and transport semantics belong inside the adapter.

TrueData remains a market-data dependency; its mapping and semantics are UNKNOWN until documentation arrives. No TrueData execution semantics are assumed.

## Immutability and idempotency

An `OrderIntent` is immutable. Changes create new events/intent versions.

Order submission requires an idempotency identity so retries cannot silently create duplicate orders. The provider-specific mechanism is UNKNOWN.

Blind retry after an uncertain provider response is forbidden.

## Execution attacks

### Stale price

A stale price cannot automatically be treated as executable. Freshness rules must be explicit.

### Spread

A wide spread may destroy economic value. No spread threshold is invented.

### Slippage

Midpoint fills without an explicit fill-model justification may overstate achievable economics.

### Partial fills

Assuming full quantity at one price can produce impossible backtest results when partial fills are possible.

### Duplicate submission

Retrying an uncertain submission without idempotency can create duplicate orders. The adapter must resolve or fail closed.

## Reconciliation invariant

```text
requested_quantity >= cumulative_filled_quantity >= 0
```

subject to any provider-defined quantity representation.

Actual position quantity derives from confirmed fills:

```text
OrderIntent -> FillEvents -> Position
```

not directly from order intent.

## Failure behavior

If required execution semantics are missing, stale, ambiguous, or undocumented:

```text
NO_EXECUTION
+ explicit reason
+ provenance
```

No fallback market order, midpoint fill, zero slippage, or assumed broker behavior is permitted.

## Parameter classes

**Frozen:** price separation, order-intent contract, submission/fill separation, partial-fill architecture, position-from-fill truth, provider adapter boundary, causal timestamps, idempotency, fail-closed execution.

**Source-defined configuration:** order types, tick rules, validity, provider statuses, quantity handling — only after authoritative documentation.

**Learned:** execution-cost/slippage parameters may later be learned from historical execution observations under temporal promotion rules.

**External UNKNOWN:** broker API semantics, provider statuses, idempotency mechanism, TrueData semantics, historical execution records, latency characteristics.

## Implementation gate

A35 cannot become executable until the selected instrument contract, execution provider, order-type semantics, price/tick semantics, fill semantics, and cost model are documented and resolved.

Provider adapters may be scaffolded only as explicit interfaces with unresolved semantics, not invented behavior.

## Completion criterion

A35 becomes `RESOLVED` when an order can be reconstructed as:

```text
market state
 -> order intent
 -> submission
 -> acknowledgement/rejection
 -> fills
 -> realized execution cost
 -> position effect
```

with complete timestamps, quantities, prices, statuses, provenance, and policy versions.

## ARCHITECTURE STATUS

**FROZEN:** price concept separation; order-intent contract; submission/fill separation; partial-fill architecture; position-from-fill truth; execution-provider adapter boundary; causal timestamps; idempotency; fail-closed execution.

**UNRESOLVED:** executable price rule; order-type choice; tick rules; latency model; fill model; provider partial-fill semantics; execution-cost model; broker semantics; TrueData semantics.

**BLOCKERS:** Provider execution documentation and exact cost/fill semantics are unavailable. TrueData documentation is also UNKNOWN. This blocks executable order routing, not the canonical execution architecture.

**NEXT ARTIFACT:** A36 — Position Lifecycle and Protection Contract.
