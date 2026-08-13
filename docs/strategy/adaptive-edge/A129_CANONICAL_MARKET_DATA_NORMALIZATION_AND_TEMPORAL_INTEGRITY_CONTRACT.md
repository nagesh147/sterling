# A129 — Canonical Market Data Normalization and Temporal Integrity Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.0  
**Depends on:** A75 canonical market-event semantics; A126 lifecycle contract; A127 execution contract; A128 instrument/contract identity.

## 1. Purpose

A129 defines how raw provider observations become canonical market events that may safely be consumed by strategy, economics, risk, execution, backtesting, and learning.

```text
RAW OBSERVATION
 -> provider validation
 -> canonical identity resolution
 -> timestamp normalization
 -> temporal validation
 -> quality classification
 -> canonical event
 -> causally available snapshot
```

A129 does not create alpha, signals, trading thresholds, or learned parameters.

## 2. Temporal model

Every observation distinguishes:

```text
event_time   = when the market event occurred according to source
receipt_time = when Sterling received/observed it
```

Where available, preserve exchange/provider/bar-start/bar-end/last-trade timestamps separately. Never relabel one timestamp as another.

For causal use:

```text
available_at <= decision_time
```

must hold. `receipt_time` is the minimum defensible availability boundary for live processing unless a stronger source-specific contract is established.

## 3. Canonical MarketEvent

```text
event_id
instrument_id
contract_version
event_type
event_time
receipt_time
source
source_event_id?
sequence_id?
observation_payload
quality_state
source_timestamp_quality
normalization_version
raw_reference
```

Events are immutable. Corrections are new linked events; history is never silently rewritten.

## 4. Event taxonomy

```text
TRADE
QUOTE
DEPTH
BAR
OPEN_INTEREST
AUCTION
CORPORATE_ACTION
SESSION_EVENT
REFERENCE_UPDATE
```

A `QUOTE` is not a `TRADE`; a `BAR` is not an instantaneous observation; OI is not traded quantity.

## 5. Trade

A trade contains, where available:

```text
price
quantity
trade_time
```

Trade price represents an executed transaction, not an executable quote. Aggressor-side inference is a derived feature, not a raw fact unless sourced explicitly.

## 6. Quote and depth

Canonical quote:

```text
bid_price
bid_quantity
ask_price
ask_quantity
quote_time
```

Execution reference:

```text
BUY  -> current valid ask
SELL -> current valid bid
```

Missing, invalid, stale, or unresolved quote data yields uncertainty; LTP is not an executable-price fallback.

Depth is ordered `bid_levels[]` and `ask_levels[]`, with source-supported price/quantity/order-count fields. When both sides are valid:

```text
bid[i].price <= bid[i-1].price
ask[i].price >= ask[i-1].price
best_bid <= best_ask
```

Crossed/invalid books are `DATA_UNCERTAIN`, never silently repaired.

## 7. Bar semantics

A bar represents:

```text
[start_time, end_time)
```

and may contain:

```text
open high low close volume open_interest
```

A bar is not closed until its interval has ended and completion is causally observable.

For a closed trade-derived bar:

```text
open  = first valid trade price
high  = max(valid trade prices)
low   = min(valid trade prices)
close = last valid trade price
```

Volume is summed only when source quantity is explicitly trade volume. OI is not summed. Missing first/last trade means incomplete bar, not fabricated values.

## 8. Resampling and snapshots

Higher-timeframe aggregation may use only events satisfying:

```text
event_time < interval_end
```

A `FeatureSnapshot` may consume only observations whose availability boundary is satisfied:

```text
receipt_time <= snapshot_time
```

and closed-bar features require `bar_end_time <= snapshot_time`.

Historical presence in a database never implies historical availability.

## 9. Ordering, lateness, duplicates

`event_time` is the canonical temporal key but is not assumed to be a total order.

A trustworthy source sequence may break ties. If none exists, conflicting same-time events remain distinct and ordering ambiguity is explicit. Sequence numbers must never be invented.

Late arrival means:

```text
event_time < current_watermark
receipt_time > current_watermark
```

The event is retained historically but cannot rewrite a decision already made.

Duplicates are removed only using documented source identifiers or a documented inferred key. Similar-looking observations are not silently discarded.

## 10. Corrections

```text
ORIGINAL_EVENT
      |
      v
CORRECTION_EVENT
      |
      v
RECONSTRUCTED_STATE
```

Original evidence remains auditable. A correction arriving after a decision cannot retroactively justify that decision.

## 11. Data quality

Canonical states:

```text
VALID
DEGRADED
STALE
MISSING
INVALID
AMBIGUOUS
CORRECTED
```

`VALID` means semantic and temporal validation passed; it does not mean economically favorable.

## 12. Source authority

Authority is field-specific. Each dependency must declare:

```text
source
owner
field
mathematical definition
update frequency
event timestamp
availability timestamp
allowed consumers
invariant
failure behavior
```

No provider is globally authoritative for undocumented facts.

A127 establishes the Kite boundary for execution-time executable pricing. Other strategy-data provider assignments must be explicitly documented before production activation.

## 13. Kite data boundary

Kite documents an instrument master and quote APIs containing instrument identity, quote timestamp, last trade timestamp, LTP, volume, OHLC, OI and bid/ask depth. Kite WebSocket provides realtime quote packets, exchange timestamps and full market depth in full mode. REST quotes are snapshots, not substitutes for the streaming event model. The daily instrument dump is not realtime market data and its `last_price` must not be used as realtime price evidence. citeturn0search0turn0search4

Kite order postbacks also distinguish order timestamp, exchange timestamp and exchange update timestamp, reinforcing that provider timestamps must remain distinct. citeturn0search3

## 14. Clock and session

Canonical internal representation is an unambiguous instant plus source timezone metadata where supplied. An ambiguous timestamp is:

```text
INVALID_FOR_CAUSAL_DECISION
```

Session state comes from the authoritative exchange calendar, not from absence of ticks. Missing data during an open session is data absence, not automatic market closure.

## 15. Missingness and cross-source joins

Missing values remain:

```text
MISSING
```

not zero, previous value, or interpolation unless a feature contract explicitly authorizes the transformation.

For a decision at `t`:

```text
observation_A.available_at <= t
observation_B.available_at <= t
```

Nearest-time joins are forbidden unless a documented causal tolerance exists. A future observation may never be selected because it is numerically closer.

## 16. Corporate actions and price basis

Raw and adjusted prices are distinct:

```text
price_basis = RAW | ADJUSTED | UNKNOWN
```

Mixing adjusted research prices with raw execution prices without an explicit transformation is forbidden.

Corporate-action authority remains `TODO` until the historical universe and source are formally selected.

## 17. Options

Every option event retains A128 contract identity. Expiry, strike, option type and lot size are never inferred from LTP.

Greeks and IV are timestamped provider/derived observations, not immutable contract facts. A later option-chain snapshot cannot reconstruct an earlier decision unless the source guarantees historical availability at that time.

## 18. Feature boundary

A129 stops at normalized observations:

```text
canonical events
 -> feature formula
 -> feature value
```

Every feature must retain:

```text
feature_id
formula_id
formula_version
input_event_ids
input availability boundaries
computed_at
```

Precomputed datasets cannot hide future dependencies.

## 19. Learning boundary

Training examples consume only information available at the feature/decision timestamp. For a label with future horizon `H`:

```text
feature_time < label_maturity_time
```

Labels cannot enter feature generation before maturity. Train/validation/test partitions are chronological; random row splitting is not sufficient for temporally dependent market data.

## 20. Dependency matrix

| Dependency | Source/owner | Update | Consumer | Invariant | Failure |
|---|---|---|---|---|---|
| Instrument identity | A128 registry | contract/event driven | all | unique effective identity | reject |
| Realtime quote | Kite | streaming/snapshot | execution/economics | valid timestamps/quote | uncertain |
| Realtime trade | provider-specific | event driven | features | valid trade semantics | reject/degrade |
| Bars | source/provider | interval driven | features | closed interval | incomplete |
| Session calendar | exchange authority | calendar/version driven | temporal consumers | explicit boundaries | block |
| Historical data | selected provider | dataset/version driven | backtest/learning | causal availability | reject/unknown |
| Corporate actions | selected authority | event driven | historical features | explicit price basis | block affected study |
| Greeks/IV | provider/calculation source | event driven | economics/features | timestamped provenance | uncertain |

## 21. Frozen architecture

```text
immutable canonical events
explicit event types
A128 instrument identity
event_time != receipt_time
causal availability boundary
closed-bar rule
explicit missingness
explicit quality states
out-of-order/correction lineage
source-specific authority
causal cross-source joins
session-calendar authority
raw/adjusted price separation
feature provenance boundary
chronological learning boundary
explicit uncertainty/failure states
```

## 22. Unfrozen/configurable

```text
quote freshness threshold
bar lateness/watermark tolerance
reconnect timing
provider retry policy
historical dataset selection
corporate-action provider
Greek/IV calculation method
cross-source join tolerance
```

These cannot be optimized merely for backtest P&L.

## 23. Learned parameters

A129 defines no learned trading parameter. Any future learned quantity must specify population, label, observation horizon, maturity, train/validation/test boundaries, update cadence and promotion rule.

## 24. Hostile review

The architecture must reject or explicitly classify:

```text
future database records used in historical replay
incomplete bars consumed as closed
late events rewriting past decisions
duplicate packets without evidence
crossed books
missing bid with LTP fallback
ambiguous clock interpretation
current contract metadata applied historically
adjusted prices mixed with raw execution prices
future option-chain snapshots used for earlier IV/Greeks
nearest-time joins that cross the causal boundary
```

Required outcome is uncertainty, rejection, or explicit correction lineage. No future information may become valid merely because it is available now.

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- immutable canonical event envelope
- event vs receipt time distinction
- causal availability boundary
- market-event taxonomy
- quote/depth/trade/bar semantic separation
- closed-bar rule
- missingness semantics
- out-of-order/correction lineage
- source-specific authority model
- session-calendar dependency
- causal cross-source joins
- raw/adjusted price distinction
- feature provenance boundary
- chronological learning boundary
- explicit uncertainty/failure states

UNRESOLVED:
None at architectural-contract level.

INTENTIONALLY UNKNOWN / TODO:
- final historical dataset/provider for every research universe
- corporate-action authority
- option Greek/IV calculation authority
- historical completeness/survivorship characteristics of any not-yet-selected dataset

CONFIGURATION TO VALIDATE:
- quote freshness threshold
- lateness/watermark tolerance
- cross-source join tolerance
- reconnect/retry timing

BLOCKERS:
None for specification work.

IMPLEMENTATION GATE:
Provider adapters must prove timestamp, packet, identity and missing-data semantics before live use. This verifies the frozen contract; it does not permit invented semantics.

NEXT ARTIFACT:
A130 — Canonical Feature and State Snapshot Contract
```
