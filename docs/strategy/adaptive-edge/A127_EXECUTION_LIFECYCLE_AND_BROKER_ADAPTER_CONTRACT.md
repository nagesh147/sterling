# A127 — Execution Lifecycle and Broker Adapter Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.2  
**Depends on:** A126 Adaptive Trade Horizon, Position Protection & Lifecycle Contract; canonical instrument, risk, economics and market-event contracts.  
**Execution integration:** Zerodha Kite Connect v3.  
**Scope:** Execution intent, order lifecycle, fills, cancellation/modification, execution uncertainty, reconciliation, broker position truth, executable-price semantics, session authority, charges/margin, and auditability.

## 1. Purpose

A127 is the boundary between an already-authorized Adaptive Edge decision and external execution.

```text
DECISION
  -> EXECUTION INTENT
  -> EXECUTION INSTRUCTION
  -> KITE ORDER REQUEST
  -> BROKER / EXCHANGE OBSERVATION
  -> FILL(S)
  -> POSITION EFFECT
  -> RECONCILIATION
```

These are distinct facts:

```text
INTENT != ORDER
ORDER ACCEPTED != ORDER EXECUTED
ORDER != FILL
FILL != POSITION SNAPSHOT
POSITION != THESIS
```

A127 does not decide whether the strategy should trade, change horizon, alter protection, or resize an authorized trade.

## 2. Canonical entities

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

Required lineage:

```text
source_decision_id
  -> intent_id
      -> canonical_order_id
          -> kite_order_id
              -> exchange_order_id
                  -> trade_id
                      -> position_effect
```

Kite `order_id`, `exchange_order_id`, `trade_id`, `instrument_token`, and `guid` are preserved as provider/exchange evidence. They do not replace canonical internal identity.

## 3. Immutable execution intent

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

Invariants:

```text
intent_id is unique
intent is immutable after publication
quantity >= 0
valid_until >= created_at
instrument_id resolves uniquely
```

No silent side, quantity, validity, instrument, or economic-purpose mutation is allowed.

## 4. Execution instruction

Canonical broker-independent semantics:

```text
instrument_id
side
quantity
order_type
limit_price?
trigger_price?
time_in_force
execution_constraints
```

The Kite adapter must not silently convert:

```text
LIMIT -> MARKET
SL -> MARKET
requested quantity -> rounded quantity
```

Any economically meaningful change requires a new/explicitly authorized instruction.

## 5. Kite Connect v3 capability contract

Kite Connect v3 documents:

```text
POST /orders/:variety
PUT  /orders/:variety/:order_id
DELETE /orders/:variety/:order_id
GET  /orders
GET  /orders/:order_id
GET  /trades
GET  /orders/:order_id/trades
GET  /portfolio/positions
GET  /portfolio/holdings
POST /margins/orders
POST /margins/basket
POST /charges/orders
GET  /instruments
GET  /quote
GET  /quote/ohlc
GET  /quote/ltp
```

Kite documents regular orders and order modification/cancellation while an order is open/pending. A successful order-placement API response returns an `order_id` but explicitly does **not** guarantee execution; true status must be obtained from order state/history or asynchronous postbacks. citeturn2view2

Therefore the broker contract is now resolved as:

```text
BROKER = ZERODHA KITE CONNECT v3
```

No Dhan-specific semantics are part of Adaptive Edge.

## 6. Authentication/session dependency

Kite Connect requires an API key/secret and access-token session. A `403`/`TokenException` indicates an expired/invalidated session and requires re-login. The exchange-regulated daily login requirement is therefore an operational prerequisite, not a trading parameter. citeturn3search0turn3search5

Canonical behavior:

```text
SESSION_INVALID
    -> trading disabled
    -> no blind authentication retry
    -> operational re-authentication required
```

The execution layer must never interpret session failure as order rejection.

## 7. Order state model

Canonical states:

```text
INTENT_CREATED
VALIDATING
INVALID
SUBMITTING
SUBMISSION_UNKNOWN
SUBMITTED
WORKING
PARTIALLY_FILLED
FILLED
CANCEL_PENDING
CANCELLED
EXPIRED
REJECTED
UNKNOWN
```

Kite documents common statuses including `OPEN`, `COMPLETE`, `CANCELLED`, `REJECTED`, plus transient states such as validation/registration/cancellation pending states. The raw Kite status is retained and mapped to the canonical state. citeturn2view2

Forbidden ordinary transitions:

```text
FILLED -> WORKING
CANCELLED -> WORKING
REJECTED -> FILLED
EXPIRED -> PARTIALLY_FILLED
```

A contradictory later observation becomes a reconciliation/correction event; historical observations are never overwritten.

## 8. Ambiguous submission / idempotency

Kite explicitly states that successful placement only means the request was registered with its OMS; it does not mean the order reached the exchange or executed. citeturn1search0

Therefore:

```text
API timeout / network failure
        !=
order rejected
```

Canonical state:

```text
SUBMISSION_UNKNOWN
```

Recovery:

```text
SUBMISSION_UNKNOWN
  -> query order book/history
  -> query order trades
  -> query current positions
  -> reconcile
```

Kite's `guid` is explicitly documented as an unusable request identifier to avoid order duplication, so A127 does not depend on it as a broker idempotency guarantee. citeturn1search0

**Frozen safety rule:** no blind resubmission of an economically equivalent action while the previous submission is unresolved.

## 9. Partial fills

Kite order data exposes:

```text
quantity
filled_quantity
pending_quantity
cancelled_quantity
average_price
```

Kite trade data exposes `trade_id`, `order_id`, filled quantity, average price and fill timestamp. citeturn1search0

Canonical invariants:

```text
0 <= filled_quantity <= accepted_quantity <= requested_quantity
pending_quantity >= 0
cancelled_quantity >= 0
```

The exact reconciliation equation must account for modifications and broker order history; it must not be inferred from a single current snapshot when historical events are available.

A first fill creates actual exposure:

```text
PARTIALLY_FILLED
    -> POSITION_SUPERVISION
```

## 10. Cancellation and modification

Kite permits cancellation/modification of open or pending orders. Cancellation is asynchronous and must be treated as a request, not proof of cancellation. citeturn1search0

Canonical lifecycle:

```text
CANCEL_REQUESTED
    -> CANCEL_PENDING
        -> CANCELLED
        -> PARTIALLY_FILLED
        -> FILLED
        -> UNKNOWN
```

Therefore:

```text
cancel_requested != cancelled
cancelled != flat
```

A modification creates an immutable modification event even if Kite retains the same `order_id`.

## 11. Fill identity and timestamps

Preserve:

```text
decision_time
intent_time
submission_time
order_timestamp
exchange_timestamp
exchange_update_timestamp
fill_timestamp
receipt_time
reconciliation_time
```

Kite explicitly exposes order timestamp, exchange timestamp, exchange-update timestamp and trade fill timestamp. citeturn1search0

No timestamp may be relabeled.

Causal rule:

```text
event_time <= receipt_time
```

when authoritative event time exists. If it does not, retain `UNKNOWN`; do not fabricate it.

Network arrival order is not economic event order.

## 12. Executable-price semantics

Kite full quotes provide exchange-timestamped quote snapshots with bid/ask market depth. Kite WebSocket full mode provides five bid and five offer levels and an exchange timestamp. citeturn2view0turn2view1

Canonical execution reference:

```text
BUY  -> best available offer/ask at the observation timestamp
SELL -> best available bid at the observation timestamp
```

For a market order, this is a **reference**, not a guaranteed fill price.

For a limit order, the submitted limit price is the execution constraint; actual fill price remains authoritative.

LTP is never substituted for an unavailable bid/ask when the system is making an executable-price assessment.

If quote data is:

```text
missing
stale
malformed
crossed/invalid
```

then:

```text
DATA_UNCERTAIN
```

must be emitted.

## 13. Quote freshness

The semantic requirement is frozen:

```text
quote_timestamp <= decision_time
quote must satisfy freshness policy
```

The exact freshness threshold remains an operational configuration parameter because it depends on measured provider latency, clock synchronization, network behavior and execution conditions.

It must be selected through operational validation, not optimized against strategy P&L.

## 14. Market-data authority boundary

For execution-time executable quotes, the selected source is Kite market data because Kite exposes exchange-timestamped quote/depth data and the same provider boundary as execution. citeturn2view0turn2view1

Other market-data providers may exist upstream for research/historical data, but A127 does not mix their quote semantics into broker execution truth.

This avoids a hidden cross-provider timestamp/identity dependency.

## 15. Position authority

Kite's positions API exposes current `net` positions and `day` activity. `net` represents the actual current net position portfolio. citeturn1search1

Authority is domain-specific:

```text
strategy decision/history -> internal canonical system
actual broker exposure   -> Kite position state
execution event          -> canonical event derived from provider evidence
```

A local position projection can never override confirmed broker exposure.

## 16. Reconciliation

Mandatory comparison:

```text
internal intents
internal orders
internal fills
internal position effects

vs

Kite order book
Kite order history
Kite trade book
Kite positions
```

Canonical outcomes:

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

Kite order history is explicitly transient/day-scoped, so reconciliation records must be persisted internally during the session; the system must not assume the broker retains an indefinitely queryable historical order book. citeturn1search0

Live order postbacks/WebSocket order messages are low-latency observations. REST queries are used for reconciliation. Kite documents both asynchronous postbacks and REST order/trade retrieval. citeturn0search2turn2view1

## 17. Flatten semantics

Kite does not provide a magic "make this strategy flat" semantic that can replace canonical execution. Exiting a position is done by placing the opposite order with the same product as the existing position. citeturn1search1

Canonical sequence:

```text
FLATTEN_REQUESTED
  -> identify actual broker position
  -> cancel conflicting working orders where required
  -> submit offsetting order with correct product
  -> observe fills
  -> reconcile
  -> FLAT_CONFIRMED
```

Therefore:

```text
FLATTEN_REQUESTED != FLAT
```

Emergency flattening remains permitted after the A126 cutoff.

## 18. Product consistency

Kite documents that a position has a margin product and that an exit order with a different product can be treated as a new position rather than an exit. citeturn1search1

Therefore `position_product` is an execution-critical field.

Invariant:

```text
EXIT_ORDER.product == POSITION.product
```

unless an explicit product-conversion operation has been authorized.

This is now frozen and is not left to implementation convention.

## 19. Options execution

A127 consumes the canonical instrument identity from the instrument contract layer.

For an option, execution must preserve:

```text
venue
segment
underlying
expiry
strike
CE/PE
lot_size
tick_size
quantity
provider instrument identity
```

Kite's instrument master provides `instrument_token`, `tradingsymbol`, `expiry`, `strike`, `tick_size`, `lot_size`, `instrument_type`, `segment` and `exchange`. citeturn2view0

No option contract may be inferred from a display string when authoritative instrument metadata is available.

## 20. Instrument identity boundary

A127 does not own canonical instrument identity; it consumes it.

The broker adapter maps the canonical instrument to Kite's required:

```text
exchange
tradingsymbol
instrument_token
```

Kite itself recommends `exchange + tradingsymbol` as the storage key rather than relying on `instrument_token`, because exchange instrument tokens can be reused for different derivative instruments after expiry. citeturn2view0

This creates an explicit dependency on A128 without making A127 responsible for defining A128.

## 21. Session authority and cutoff

NSE documents equity-derivatives normal market hours as:

```text
09:15 -> 15:30
```

and trade modification end time as 16:15. citeturn1search6

A126 remains authoritative for the Adaptive Edge cutoff:

```text
strategy_cutoff = authoritative_session_close - 45 minutes
```

For the normal NSE equity-derivatives session this evaluates to 14:45.

The implementation must derive this from a session-calendar contract rather than hard-code 14:45 globally.

At cutoff:

```text
new entries       = forbidden
new additions     = forbidden
horizon upgrades  = forbidden
normal exposure   = targeted toward flat
```

Emergency exits remain permitted where the market and broker permit them.

## 22. Charges and realized execution economics

Kite provides order-wise charge calculation and documents charge components including:

```text
transaction tax
exchange turnover charge
SEBI turnover charge
brokerage
stamp duty
GST
```

The charge API can calculate order-wise charges, while final realized accounting must use the authoritative recorded trade/contract-note/statement data available to the account. citeturn2view4

A127 therefore freezes:

```text
REALIZED_EXECUTION_COST = authoritative recorded broker charges
```

No arbitrary tax or brokerage formula is embedded in strategy logic.

## 23. Funds and margin

Kite exposes order and basket margin calculation, including margin components and estimated order charges. citeturn0search0

These are execution-eligibility observations, not alpha inputs.

Insufficient margin/funds may prevent execution. The adapter must not silently reduce quantity. Any resizing requires an explicit upstream execution policy.

## 24. Authentication, transport and error taxonomy

Canonical errors:

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

Kite documents `TokenException`, `OrderException`, `InputException`, `MarginException`, `HoldingException`, `NetworkException`, `DataException` and `GeneralException`, plus HTTP 400/403/404/429/5xx behaviors. citeturn3search0

Provider errors are preserved as evidence and mapped into canonical categories.

Transport failure is never silently mapped to order rejection.

## 25. Rate limits

Kite documents:

```text
quote API       1 request/sec
historical      3 requests/sec
order placement 10 requests/sec
other endpoints 10 requests/sec
400 orders/minute
10 orders/sec
5000 orders/day/user/API key
25 modifications/order
```

These are infrastructure constraints, not strategy parameters. citeturn3search0

Emergency execution must not enter an uncontrolled retry loop under rate limiting.

## 26. Audit contract

Every economically meaningful execution event records, where applicable:

```text
audit_id
source_decision_id
intent_id
canonical_order_id
kite_order_id
exchange_order_id
trade_id
event_type
previous_state
new_state
event_time
receipt_time
source
reason_code
adapter_version
configuration_version
provider_reference
```

Secrets, API keys, access tokens and authentication material are never persisted in execution audit records.

## 27. Causal integrity

For a decision at time `t`:

```text
only observations available at or before t may influence it
```

Forbidden inputs to an earlier decision include:

```text
future quote
future order state
future fill
future position
future contract metadata
future session state
future outcome
```

Execution timestamps are observations; they cannot be used retrospectively to make an earlier decision appear valid.

## 28. Frozen architecture review

The following are now frozen and mutually consistent:

```text
execution intent/order/fill/position separation
immutable intent
stable execution lineage
Kite Connect v3 broker adapter boundary
Kite execution-time quote/depth boundary
partial-fill semantics
ambiguous submission handling
cancellation/modification lifecycle
product-consistent exits
broker position authority
stream + REST reconciliation
flatten semantics
emergency execution
NSE session authority
actual recorded execution charges
causal timestamps
reproducible audit trail
no backward information leakage
provider-specific isolation
```

No Dhan, TrueData, or other broker-specific execution semantics are part of A127.

## 29. Intentionally configurable, not learned

These remain operational configuration:

```text
quote freshness threshold
network timeout
bounded retry/backoff
WebSocket reconnect policy
REST reconciliation cadence
health/recovery thresholds
```

They must be validated for reliability/safety, not selected by maximizing strategy P&L.

Trading parameters remain upstream and unfrozen:

```text
stop distance
trailing logic
horizon thresholds
promotion/downgrade thresholds
profit-lock thresholds
continuation thresholds
```

## 30. Hostile review

A127 must survive:

```text
order request accepted by OMS but response lost
order accepted but not sent to exchange
partial fill during cancellation
fill arriving after cancellation request
duplicate postback
out-of-order postback
WebSocket disconnect
REST outage
broker position != internal projection
exit order uses wrong product
session expires during execution
rate limit during emergency exit
market quote becomes stale
instrument token reused after derivative expiry
provider symbol mismatch
future timestamp supplied to earlier decision
```

Required result is explicit uncertainty, reconciliation, or emergency handling.

Never:

```text
invent a fill
invent a flat position
blindly resubmit an unresolved order
silently resize
silently change order type
use future information
```

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- execution intent/order/fill/position separation
- stable execution identity and lineage
- Zerodha Kite Connect v3 execution boundary
- Kite order/trade/position reconciliation
- partial-fill semantics
- ambiguous submission handling
- cancellation/replacement lifecycle
- product-consistent exits
- broker position authority
- Kite executable bid/ask semantics
- session/calendar authority boundary
- flatten semantics
- emergency execution
- actual recorded execution charges
- causal timestamps
- audit/reproducibility
- no backward information leakage
- broker-specific adapter isolation

UNRESOLVED:
None at architectural-contract level.

INTENTIONALLY UNFROZEN:
- numerical quote freshness threshold
- infrastructure timeout/backoff/reconnect values
- strategy-owned numerical parameters

BLOCKERS:
None for specification work.

PRODUCTION IMPLEMENTATION GATE:
The architectural contract is complete. Live-money activation still requires controlled Kite integration tests, session/authentication tests, order/fill race tests, reconciliation tests, rate-limit tests, and emergency-exit tests. These are verification gates for a complete specification, not unresolved dependencies.

NEXT ARTIFACT:
A128 — Instrument & Contract Identity Specification
```
