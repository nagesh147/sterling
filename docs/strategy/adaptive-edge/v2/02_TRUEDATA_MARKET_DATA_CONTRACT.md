# Adaptive Edge V2 — TrueData Market-Data Contract

**Artifact:** A01
**Version:** 1.0.0-draft
**Status:** SPECIFICATION-DRAFT / PARTIALLY-RESOLVED
**Authority:** TrueData documentation and repository TrueData source-contract reconciliation
**Scope:** Adaptive Edge market/research data only

## 1. Purpose

This artifact binds Adaptive Edge market and research inputs to TrueData. It does not define trading execution. Trading operations, fills, positions, and square-off are owned by the Zerodha Kite contract.

The strategy must not substitute another market-data provider when a required TrueData observation is unavailable.

## 2. Source-of-truth rule

```text
Adaptive Edge market/research data
        |
        v
     TrueData
        |
        v
Canonical Event Contract
        |
        v
State / Features / Probability / Economics
```

Raw TrueData fields are interpreted only by the provider adapter. Mathematical components consume canonical events/state, not vendor-specific fields.

## 3. Source evidence

The repository records the following TrueData capability reconciliation:

- real-time market data for NSE equities, indices, futures and options;
- REST and WebSocket interfaces;
- live Level-one data and option-chain data;
- bid/ask, volume, open interest and market-depth capabilities subject to feed/product entitlement;
- option-chain fields including LTP, bid, bid quantity, ask, ask quantity, volume, OI and OI-change;
- documented default historical availability of tick data for the last 5 trading days, minute bars for the last 6 months, and daily bars for 10+ years;
- historical depth and long-range tick replay are not assumed available under the default entitlement.

The repository's TrueData README points to the TrueData Market Data API documentation as the authoritative external API reference. The exact endpoint/field mapping remains a source-contract task where not explicitly established in repository evidence.

## 4. Source-status vocabulary

Every required variable has one of:

```text
CONFIRMED
DERIVABLE
CONDITIONAL
UNKNOWN
UNAVAILABLE
```

No UNKNOWN value may be replaced by a guessed field, zero, midpoint, stale value, or alternate provider.

## 5. Canonical market variables

| Canonical variable | Status | Source semantics |
|---|---|---|
| InstrumentID | CONFIRMED / mapping TBD | TrueData instrument/symbol identity; canonical internal ID required |
| MarketTimestamp | CONFIRMED / semantics TBD | Provider market timestamp; precision/timezone/order semantics unresolved |
| ReceiptTimestamp | DERIVED | Local system receive time |
| LTP | CONFIRMED | TrueData LAST/LTP capability |
| BestBid | CONFIRMED | TrueData bid capability |
| BestAsk | CONFIRMED | TrueData ask capability |
| BidSize | CONFIRMED | TrueData bid quantity capability |
| AskSize | CONFIRMED | TrueData ask quantity capability |
| TradeQuantity | CONFIRMED / exact stream field TBD | TrueData LTQ/volume capability |
| TotalVolume | CONFIRMED | TrueData volume capability |
| OpenInterest | CONFIRMED | TrueData OI capability |
| OIChange | CONFIRMED for option-chain data | TrueData option-chain OI-change capability |
| Spread | DERIVABLE | `Ask - Bid` |
| Mid | DERIVABLE | `(Bid + Ask) / 2`, non-executable valuation only |
| RelativeSpread | DERIVABLE | `(Ask - Bid) / Mid` when Mid > 0 |
| AggressorSide | UNKNOWN | No authoritative source field established |
| BuyAggressorVolume | UNKNOWN | Depends on validated aggressor classification |
| SellAggressorVolume | UNKNOWN | Depends on validated aggressor classification |
| CumulativeDelta | CONDITIONAL | Requires reliable aggressor classification |
| FlowImbalance | CONDITIONAL | Requires reliable flow classification |
| DepthLevels | CONDITIONAL | Feed/product entitlement and exact NSE/NIFTY coverage unresolved |
| HistoricalDepth | UNKNOWN | Must not be assumed from live depth capability |
| HistoricalTick | LIMITED | Default documented history is 5 trading days |
| HistoricalMinuteBars | LIMITED | Default documented history is 6 months |
| HistoricalDailyBars | CONFIRMED | 10+ years documented |
| OptionChain | CONFIRMED | Real-time/streaming option-chain capability |
| OptionGreeks | CONFIRMED at product level / endpoint TBD | Exact endpoint and field semantics unresolved |
| ImpliedVolatility | CONFIRMED at product level / methodology TBD | Provider value must remain distinct from reconstructed IV |
| ExpiredOptions | CONDITIONAL / current entitlement TBD | Historical expired-option availability must be verified |
| MarketReplay | CONDITIONAL | Exact entitlement and historical coverage unresolved |

## 6. Timestamp contract

Every canonical observation must preserve:

```text
EventTimestamp
SourceTimestamp
ReceiptTimestamp
ProcessingTimestamp
```

The model's causal timestamp is the market event timestamp once its TrueData semantics are established.

Receipt time is retained separately for latency analysis.

No receipt-time substitution is permitted for historical causality.

## 7. Causal rule

For a decision at time `t`:

```text
all consumed market information must have
information availability <= t
```

A later TrueData event, later reconstruction, later correction, or later aggregate must not influence an earlier decision.

## 8. Market-data tiers

### Tier A — long historical context

Potential inputs:

```text
daily bars
available historical minute bars
validated expired-option history
```

Use:

```text
regime
seasonality
volatility context
broad directional behavior
```

Availability beyond documented entitlement remains UNKNOWN.

### Tier B — historical microstructure

Potential inputs:

```text
ticks
quotes
depth
```

Use:

```text
flow
microstructure
short-horizon behavior
execution-context research
```

The default TrueData historical entitlement does not establish multi-year tick/depth history.

### Tier C — live market state

Potential inputs:

```text
live tick/quote stream
option chain
supported depth
Greeks
```

Exact feed mode and entitlement must be verified before production use.

## 9. Mathematical derivations

Only source-supported deterministic derivations are permitted.

```text
Spread = Ask - Bid

Mid = (Bid + Ask) / 2

RelativeSpread = (Ask - Bid) / Mid
```

These are mathematical transformations, not additional data sources.

`Mid` is not an executable fill price.

## 10. Aggressor-side boundary

The system must not claim TrueData provides true buy/sell aggressor volume until an authoritative field or validated reconstruction method is established.

Therefore:

```text
TrueData trade observation
        !=
true aggressor classification
```

unless the source contract establishes the equivalence.

Any reconstructed aggressor classification must be explicitly marked `DERIVED` and separately validated for classification error.

## 11. Historical availability boundary

The documented default historical availability creates a hard research constraint:

```text
5-10 years of tick-level training = NOT ESTABLISHED
```

Therefore the strategy may not claim multi-year tick-level walk-forward evidence unless an entitled TrueData historical/replay source actually provides it.

Long-history contextual research and short-history microstructure research must remain separate populations.

## 12. Option-data boundary

For an option observation the canonical contract must ultimately identify:

```text
Underlying
Expiry
Strike
OptionType
InstrumentID
Timestamp
LTP
Bid
Ask
BidSize
AskSize
Volume
OI
```

Provider-specific option identifiers must be mapped to the immutable internal instrument identity.

## 13. Greeks boundary

Provider-supplied Greeks and internally reconstructed Greeks are different variables.

```text
GreekSource = PROVIDER
```

or

```text
GreekSource = DERIVED
```

must be explicit.

No provider Greek may silently be replaced by a locally calculated value.

## 14. Missing/stale/invalid data

The following are distinct:

```text
MISSING
UNKNOWN
INVALID
NOT_APPLICABLE
STALE
```

None may be converted to zero implicitly.

If a required market input is unavailable or stale beyond its validated freshness policy:

```text
NO_TRADE / DATA_UNAVAILABLE
```

is the default fail-closed outcome until a downstream artifact defines a more specific state transition.

## 15. Historical versus live data

Historical data used for research must retain its source and source-version provenance.

Live data must retain receipt timestamps and feed identity.

A live observation cannot be backfilled into historical training without explicit dataset/version provenance.

## 16. Execution separation

TrueData does not establish our execution.

```text
TrueData market trade
    !=
Zerodha Kite fill
```

```text
TrueData bid/ask
    !=
actual execution price
```

unless a separate execution contract establishes an equivalence for a specific simulation assumption.

## 17. Failure conditions

The market-data boundary fails closed on:

```text
unknown instrument mapping
invalid timestamp
unresolvable ordering
required field missing
stale required quote
source disconnect
entitlement mismatch
unsupported historical range
ambiguous provider semantics
```

The system must record the failure as a data-quality event rather than silently fabricating the missing value.

## 18. Frozen architecture

```text
Adaptive Edge market/research source = TrueData only

Canonical model input = provider-neutral canonical events/state

TrueData adapter = sole vendor-semantic translation boundary

No alternate market-data provider fallback

Observed market data != our execution

Provider data != internally derived variables

Unknown data remains UNKNOWN
```

## 19. Configurable / learned

Not frozen here:

```text
quote freshness threshold
sampling interval
feature lookback lengths
minimum history
aggressor classification rule, if adopted
model parameters
probability thresholds
execution-cost parameters
```

These belong to later research artifacts and require causal walk-forward validation.

## 20. External TODO / UNKNOWN

```text
TODO: exact TrueData endpoint/field mapping for every canonical variable
TODO: exact timestamp precision/timezone semantics
TODO: sequence/order guarantees
TODO: exact live tick versus one-second snapshot semantics under our entitlement
TODO: exact depth entitlement for NIFTY and NIFTY options
TODO: historical depth availability
TODO: historical tick/replay entitlement
TODO: expired-option historical coverage under our subscription
TODO: exact Greeks endpoint and field semantics
TODO: provider IV methodology/provenance
TODO: source-specific rate limits and reconnect semantics
```

## 21. Adversarial review

### Look-ahead

Prevented architecturally by event-time causal filtering, but exact provider timestamp semantics remain a blocker.

### Survivorship bias

Instrument identity and historical contract validity must be preserved. Delisted/expired instruments must not disappear from the historical population merely because they are unavailable today.

### Selection bias

The research population must not be restricted to observations where all desired TrueData fields happened to be available unless that restriction is itself part of the declared eligibility rule.

### Historical-depth illusion

Live depth capability must not be treated as evidence of historical depth availability.

### Tick-history illusion

Five trading days of default tick history cannot support a multi-year tick-level claim.

### Execution illusion

A TrueData LTP/bid/ask observation cannot be represented as a Kite fill.

### Provider-field ambiguity

Any undocumented provider field remains UNKNOWN until source documentation establishes its semantics.

## 22. Completeness test

This artifact is complete only when every market input required by a downstream artifact has one of:

```text
CONFIRMED
DERIVABLE
CONDITIONALLY AVAILABLE with explicit entitlement
```

and every UNKNOWN is either removed by authoritative documentation or explicitly excluded from the strategy.

## ARCHITECTURE STATUS

TrueData is frozen as the sole Adaptive Edge market/research source.
Canonical event translation is frozen.
Fail-closed behavior is frozen.
Historical and live data populations are explicitly separated.

## UNRESOLVED

Provider-specific endpoint/field mappings and entitlement-dependent capabilities listed above.

## BLOCKERS

The exact TrueData subscription/entitlement and timestamp/feed semantics must be verified before claiming the affected data capabilities are production-ready.

## NEXT ARTIFACT

**A02 — Strategy Opportunity, Prediction Target, Horizon and Label Contract (A26 resolution).**

This artifact must define what Adaptive Edge is predicting before probability, calibration, walk-forward learning, and label maturity can be considered complete.
