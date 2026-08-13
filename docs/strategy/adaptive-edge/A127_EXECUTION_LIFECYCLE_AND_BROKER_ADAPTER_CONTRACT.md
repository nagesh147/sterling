# A127 — Execution Lifecycle and Broker Adapter Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.1  
**Scope:** Execution intent, broker order lifecycle, fills, cancellation/modification, reconciliation, execution uncertainty, position truth, execution-market-data boundary, and auditability.

**Depends on:** A126 Adaptive Trade Horizon, Position Protection & Lifecycle Contract and canonical instrument, risk, economics, market-event and decision contracts.

**Selected production adapters:** DhanHQ API v2 for execution; TrueData Market Data API for execution-time market data; NSE official market calendar for NSE session authority.

**Does not define:** signal generation, horizon selection, thesis evaluation, protection thresholds, sizing, profitability logic, or learned trading parameters.

---

## 1. Core boundary

```text
DECISION -> EXECUTION INTENT -> INSTRUCTION -> ORDER -> BROKER EVENT -> FILL -> POSITION EFFECT -> RECONCILIATION
```

These are distinct facts:

```text
INTENT != ORDER
ORDER != ACK
ACK != FILL
FILL != POSITION
POSITION != THESIS
```

A127 translates an already-authorized action and observes what actually happened. It does not decide whether the strategy should trade.

---

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

Every economic action has immutable lineage:

```text
source_decision_id
 -> intent_id
 -> order_id
 -> correlation_id
 -> broker_order_id
 -> exchange_order_id
 -> exchange_trade_id
 -> position_effect
```

Provider identifiers are evidence and lineage; they are not strategy semantics.

---

## 3. Intent contract

Minimum intent semantics:

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
intent_id unique
intent immutable after publication
quantity >= 0
valid_until >= created_at
instrument_id resolves to canonical instrument identity
```

No silent quantity, side, validity, or economic-purpose mutation is permitted.

---

## 4. Execution instruction

Canonical semantics:

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

The adapter must never silently convert order semantics:

```text
LIMIT -> MARKET
STOP -> MARKET
requested quantity -> rounded quantity
```

Any semantic change requires explicit upstream authorization.

---

## 5. DhanHQ v2 execution contract

DhanHQ v2 documents:

```text
POST /orders
PUT /orders/{order-id}
DELETE /orders/{order-id}
GET /orders
GET /orders/{order-id}
GET /orders/external/{correlation-id}
GET /trades
GET /trades/{order-id}
GET /positions
DELETE /positions
```

Documented order types include:

```text
LIMIT
MARKET
STOP_LOSS
STOP_LOSS_MARKET
```

Documented validity includes:

```text
DAY
IOC
```

Dhan also documents order identifiers, exchange order identifiers, correlation IDs, exchange trade IDs, filled quantity, remaining quantity, traded price and average traded price.

Dhan requires static IP for order placement, modification and cancellation. Access tokens are documented as 24-hour tokens; API-key authentication can generate access tokens. These are infrastructure prerequisites, not strategy variables.

Dhan order API limits are documented as 10 requests/sec, 250/min, 1000/hour and 7000/day; modifications are capped at 25 per order.

---

## 6. Dhan state normalization

Dhan-native states include:

```text
TRANSIT
PENDING
REJECTED
CANCELLED
TRADED
EXPIRED
```

Canonical states are:

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

`TRANSIT` is not rejection. It means the order has not yet reached the exchange according to Dhan's documented semantics.

Forbidden ordinary transitions include:

```text
FILLED -> WORKING
CANCELLED -> WORKING
REJECTED -> FILLED
EXPIRED -> PARTIALLY_FILLED
FILLED -> CANCELLED
```

Contradictory later evidence creates reconciliation/correction events; it never overwrites history.

---

## 7. Ambiguous submission and idempotency

```text
submit -> timeout
```

does **not** mean rejection.

Canonical state:

```text
SUBMISSION_UNKNOWN
```

Recovery:

```text
SUBMISSION_UNKNOWN
 -> query order/correlation state
 -> query trade book
 -> query position
 -> reconcile
```

Dhan's `correlationId` is frozen as a lineage/query identifier, **not** as an assumed broker-side idempotency guarantee.

Blind resubmission while an economically equivalent action is unresolved is forbidden.

---

## 8. Partial fills

Dhan exposes total quantity, traded/fill quantity, remaining quantity, traded price and average traded price.

Canonical invariants:

```text
0 <= filled_quantity <= accepted_quantity <= requested_quantity
remaining_quantity >= 0
filled_quantity + remaining_quantity = accepted_quantity
```

A first fill creates actual exposure immediately.

```text
PARTIAL_FILL -> POSITION_SUPERVISION
```

A partial fill is never treated as merely an incomplete signal.

---

## 9. Cancellation and modification

Cancellation is asynchronous:

```text
CANCEL_REQUESTED -> CANCEL_PENDING -> CANCELLED
                              \-> PARTIALLY_FILLED
                              \-> FILLED
                              \-> UNKNOWN
```

Therefore:

```text
cancel_requested != cancelled
cancelled != flat
```

Dhan supports modification of pending orders. A modification is recorded as an immutable event even when the broker retains the same order ID.

```text
original order state
 -> MODIFICATION_EVENT
 -> new effective order state
```

The historical order state is never erased.

---

## 10. Execution timestamps

Preserve distinct timestamps:

```text
decision_time
intent_time
submission_time
broker_create_time
exchange_time
broker_update_time
fill_time
receipt_time
reconciliation_time
```

Dhan exposes create/update/exchange timestamps; TrueData exposes market-event timestamps.

No timestamp may be relabeled. Missing authoritative timestamps remain `UNKNOWN`.

Network arrival order is not economic event order.

---

## 11. Executable-price contract

TrueData real-time tick streaming documents:

```text
timestamp
LTP
LTQ
OI
Bid
Bid Qty
Ask
Ask Qty
```

Therefore canonical executable references are:

```text
BUY -> ask
SELL -> bid
```

when the quote is present, valid and within the configured freshness policy.

LTP is **not** a fallback for canonical executable-price decisions.

Missing/stale/invalid quote state produces:

```text
DATA_UNCERTAIN
```

rather than an invented price.

The numerical freshness threshold remains operational configuration and must be validated independently of trading P&L.

---

## 12. TrueData market-data boundary

TrueData is the selected execution-time market-data source. Its documented real-time stream supplies L1 bid/ask and timestamp fields; its one-minute stream supplies timestamped OHLC/volume/OI; its option-chain capabilities include real-time chain and Greeks.

A127 consumes only observations available at or before the decision time:

```text
event_timestamp <= decision_time
```

Future bars, future quotes, future OI, future Greeks, future fills and future outcomes are forbidden inputs to earlier decisions.

---

## 13. Position authority

For strategy history:

```text
internal canonical decision = authority
```

For actual external exposure:

```text
Dhan broker position = authority
```

Position effect is derived from actual fills, then reconciled against the broker position.

```text
EXIT_REQUESTED != EXIT_FILLED
FLATTEN_REQUESTED != FLAT_CONFIRMED
```

---

## 14. Reconciliation

Mandatory comparison:

```text
internal orders
internal fills
internal position effects

vs

Dhan order book
Dhan trade book
Dhan positions
```

Outcomes:

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

The stream is a low-latency observation channel. REST order/trade/position queries are the reconciliation mechanism. No event channel is treated as infallible.

---

## 15. Flatten and emergency execution

`FLATTEN` means reducing actual exposure toward zero.

Canonical sequence:

```text
FLATTEN_REQUESTED
 -> cancel conflicting working orders where required
 -> obtain broker position
 -> submit offsetting order
 -> observe fills
 -> reconcile
 -> FLAT_CONFIRMED
```

Dhan also exposes an Exit All Positions API. It is an emergency capability, not a substitute for canonical execution lineage.

Emergency exits may bypass ordinary strategy-generation gates but never bypass:

```text
identity validation
instrument validation
broker capability validation
duplicate-submission protection
fill observation
reconciliation
```

---

## 16. Instrument dependency resolution

A127 consumes canonical instrument identity rather than a raw symbol string.

Required contract fields are:

```text
exchange
segment
security_id
instrument_type
underlying_security_id
underlying_symbol
trading_symbol
lot_size
expiry_date
strike_price
option_type
tick_size
expiry_flag
buy_sell_indicator
```

Dhan's instrument master documents these fields and provides Security IDs plus derivative attributes. The provider trading symbol is therefore a mapping, not canonical identity.

This dependency is resolved for A127; A128 will define the canonical instrument contract itself.

---

## 17. Options execution

For an option order, the execution identity must preserve:

```text
underlying
expiry
strike
CE/PE
lot_size
quantity
tick_size
security_id
```

Dhan order updates/instrument master expose these contract attributes. Dhan option-chain data exposes security ID, bid/ask, quantities, volume, OI and Greeks.

Greeks and option-chain state are upstream economic observations. Actual fill price remains the execution truth.

---

## 18. Charges and realized economics

No arbitrary brokerage/tax formulas are frozen in A127.

Dhan trade-history/statement data documents actual recorded fields for:

```text
SEBI tax
STT
brokerage
service tax / applicable tax field
exchange transaction charges
stamp duty
```

Therefore:

```text
REALIZED_EXECUTION_COST = broker-recorded final charges
```

Pre-trade margin/brokerage estimates may be used for eligibility/economics, but never replace final recorded charges.

---

## 19. Funds and margin

Dhan exposes fund limits and a margin calculator. These are execution-eligibility observations, not alpha inputs.

Insufficient funds/margin may reject execution. The adapter must not silently reduce quantity; resizing requires explicit upstream authorization.

---

## 20. Session authority and cutoff

NSE's official market-timing documentation specifies normal equity-derivatives trading from 09:15 to 15:30.

A126 remains authoritative:

```text
NORMAL_TRADING_CUTOFF = authoritative_session_close - 45 minutes
```

For the normal NSE equity-derivatives session this evaluates to 14:45, but implementation must derive the value from the session calendar.

At cutoff:

```text
new entries = forbidden
new additions = forbidden
horizon upgrades = forbidden
normal strategy exposure = targeted to flat
```

Emergency exits remain permitted after cutoff.

---

## 21. Error taxonomy

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

Provider-native codes/messages are retained as evidence.

Transport failure is never silently converted to business rejection.

---

## 22. Audit contract

Every execution event records, where applicable:

```text
audit_id
intent_id
order_id
broker_order_id
exchange_order_id
exchange_trade_id
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

Credentials, access tokens and secrets are never persisted in audit data.

---

## 23. Frozen architecture analysis

Frozen and internally consistent:

```text
intent/order/fill/position separation
immutable intent
stable lineage
broker anti-corruption boundary
DhanHQ v2 execution adapter
TrueData execution-market-data adapter
NSE session authority
bid/ask executable-price semantics
no LTP fallback for executable-price decisions
partial-fill exposure
asynchronous cancel
immutable event history
stream + REST reconciliation
broker position authority for external exposure
emergency flatten path
actual broker-recorded charges
causal timestamp rules
no future-data consumption
no blind retry
```

No frozen item creates a circular dependency with A126. A127 observes execution; A126 owns lifecycle/thesis/protection decisions.

---

## 24. Operational configuration vs learned parameters

Operational configuration, deliberately not learned from trading P&L:

```text
quote freshness threshold
network timeout
bounded retry/backoff
stream reconnect policy
REST reconciliation cadence
```

Trading parameters remain outside A127:

```text
stop distance
trailing formula
promotion/downgrade thresholds
profit-lock thresholds
maximum holding duration
continuation-edge thresholds
```

No arbitrary numerical trading value is introduced here.

---

## 25. Final hostile attack

The architecture must survive:

```text
submit -> timeout -> broker accepted
cancel -> fill -> cancel acknowledgement
partial fill -> strategy exit
stream disconnect -> missing event
REST unavailable -> uncertain broker state
broker position != internal position
exit rejected
cutoff reached with residual position
provider quote stale
provider quote missing
provider symbol changed
duplicate event
out-of-order event
future timestamp supplied to earlier decision
invalid lot/tick/expiry
rate limit during emergency
```

Required behavior in every case is explicit uncertainty, reconciliation, or emergency execution. No case permits the system to invent a fill, invent a flat position, silently mutate an intent, or use future information.

---

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- execution lifecycle
- intent/order/fill/position separation
- DhanHQ v2 execution boundary
- TrueData L1 execution-data boundary
- NSE session authority
- broker/exchange identity lineage
- partial-fill accounting
- cancellation/modification semantics
- ambiguous-submission protection
- reconciliation architecture
- broker position authority
- executable bid/ask semantics
- actual recorded execution charges
- causal timestamps and data ordering
- emergency flatten semantics
- provider isolation

UNRESOLVED:
None at architectural-contract level.

INTENTIONALLY UNFROZEN:
- numerical quote freshness threshold
- infrastructure timeout/backoff/reconnect values
- all strategy-owned numerical trading parameters

BLOCKERS:
None for specification work.

IMPLEMENTATION GATE:
Before live-money activation, controlled integration tests must verify documented Dhan/TrueData behavior and every hostile scenario above. This is verification of a complete contract, not an unresolved architectural dependency.

NEXT ARTIFACT:
A128 — Instrument & Contract Identity Specification
```
