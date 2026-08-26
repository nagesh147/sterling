# TRUE DATA SOURCE-CONTRACT RECONCILIATION
## Canonical Data Boundary — Version 1.0

## 1. Reconciliation Principle

The mathematical specification defines what the strategy requires.

TrueData defines what the data source actually provides.

Therefore:

`StrategyRequirement != DataAvailability`

until proven equivalent.

For every required variable:

`RequiredVariable`

must be mapped to:

`SourceField`

with:

`Semantics`

`Timestamp`

`Precision`

`UpdateMode`

`HistoricalAvailability`

`Entitlement`.

Anything not proven is:

`UNKNOWN`.

We do not fill unknowns with assumptions.

---

# 2. Current Public TrueData Capability

TrueData currently advertises real-time market-data APIs covering NSE equities, indices, futures and options, with WebSocket streaming and REST interfaces. Its public API page describes live Level-one data at one-second frequency, live option-chain data, option Greeks, and market-depth availability depending on the feed/product.

TrueData's current public market-data page also describes live tick/minute streaming, bid/ask, volume, open interest, options chains, and Greeks.

However, the default historical API availability currently documented by TrueData is:

`Tick = last 5 trading days`

`1/2/3/5/10/15/30/60-minute bars = last 6 months`

`Daily bars = 10+ years`.

This is a major constraint for our planned walk-forward research.

---

# 3. Critical Consequence

Our earlier idea of:

`5-10 years of tick-by-tick training`

cannot currently be assumed from the standard historical API.

That does NOT invalidate the strategy.

It changes the research architecture.

We must separate:

`Long-history model`

from:

`Short-history microstructure model`.

The long-history layer can use sufficiently available historical data.

The tick-level microstructure layer can only use whatever historical tick/replay entitlement we actually possess.

---

# 4. Source Status Vocabulary

Every variable receives:

`CONFIRMED`

TrueData documentation explicitly supports it.

`DERIVABLE`

Not directly supplied, but can be constructed from confirmed fields.

`CONDITIONAL`

Possible only if a specific subscription/product/endpoint provides it.

`UNKNOWN`

Documentation currently insufficient.

`UNAVAILABLE`

Known not to be available under the relevant entitlement.

---

# 5. Instrument Identity

Required:

`INSTRUMENT_ID`

Status:

`CONFIRMED / SOURCE-CONTRACT DETAIL TBD`.

TrueData supports symbols across NSE equity, indices, futures and options. Its current symbol documentation also specifies formats for options and indices.

Implementation requirement:

We need a canonical internal instrument identifier independent of the provider's symbol string.

---

# 6. Exchange Timestamp

Required:

`MARKET_TIMESTAMP`.

Status:

`CONFIRMED EXISTENCE / SEMANTICS TBD`.

The feed obviously exposes timestamps because TrueData exposes last-traded time and real-time streaming.

For example, its option-chain documentation explicitly lists:

`ltt = last traded time`.

But we still need to establish:

`timestamp precision`

`timezone`

`exchange timestamp vs provider timestamp`

`ordering guarantees`.

These are implementation-critical.

---

# 7. Receive Timestamp

Required:

`INFORMATION_TIMESTAMP`.

Status:

`LOCAL SYSTEM DERIVED`.

This is not a TrueData market field.

Our system records:

`local_receive_timestamp = time(event_received)`.

This variable is mandatory for realistic latency analysis.

---

# 8. Feed Latency

Definition:

`FEED_LATENCY = INFORMATION_TIMESTAMP - MARKET_TIMESTAMP`.

Status:

`DERIVABLE`.

But only after timestamp semantics are verified.

---

# 9. LTP

Required:

`LTP`.

Status:

`CONFIRMED`.

TrueData's Excel integration publicly lists `LAST`, and its option-chain API explicitly provides `ltp`.

This is one of our strongest confirmed variables.

---

# 10. Bid

Required:

`BEST_BID`.

Status:

`CONFIRMED`.

TrueData publicly documents bid data in its live feeds, and its option-chain API lists:

`bid`.

---

# 11. Ask

Required:

`BEST_ASK`.

Status:

`CONFIRMED`.

The option-chain API explicitly provides:

`ask`.

---

# 12. Bid Quantity

Required:

`BID_SIZE`.

Status:

`CONFIRMED`.

TrueData's option-chain API explicitly provides:

`bid qty`.

Its Excel integration also exposes `BIDSIZE`.

---

# 13. Ask Quantity

Required:

`ASK_SIZE`.

Status:

`CONFIRMED`.

TrueData's option-chain API explicitly provides:

`ask qty`.

The Excel integration also exposes `ASKSIZE`.

---

# 14. Spread

Required:

`SPREAD`.

Status:

`DERIVABLE`.

Formula:

`ASK - BID`.

No separate source field is necessary.

---

# 15. Relative Spread

Required:

`RELATIVE_SPREAD`.

Status:

`DERIVABLE`.

Formula:

`(ASK-BID)/MID`.

---

# 16. Trade Quantity

Required:

`TRADE_QUANTITY`.

Status:

`CONFIRMED / EXACT STREAM FIELD TBD`.

TrueData's option-chain documentation provides:

`ltq = last traded quantity`.

Its live data products also advertise volume information.

We need the exact equivalent for the underlying tick stream.

---

# 17. Total Volume

Required:

`TOTAL_VOLUME`.

Status:

`CONFIRMED`.

TrueData's option-chain documentation provides:

`volume`.

Its Excel integration explicitly exposes:

`TRADEVOL`

and:

`TOTALVOL`.

---

# 18. Open Interest

Required:

`OPEN_INTEREST`.

Status:

`CONFIRMED`.

TrueData documents:

`OI`

and:

`oi` for option chains.

---

# 19. OI Change

Required:

`OI_CHANGE`.

Status:

`CONFIRMED FOR OPTION CHAIN`.

TrueData's option-chain documentation explicitly provides:

`OI Change`

and:

`OI Change %`.

---

# 20. Aggressor Classification

Required:

`BUY_AGGRESSOR_VOLUME`

`SELL_AGGRESSOR_VOLUME`.

Status:

`UNKNOWN`.

This is critical.

The currently reviewed public documentation confirms trade quantity, LTP, bid/ask and depth-related information, but we have not established a direct authoritative aggressor-side field.

Therefore we must NOT currently claim:

`TrueData provides true buy/sell aggressor volume`.

---

# 21. Aggressor Classification Fallback

If the feed gives enough information to reconstruct trade side using a validated quote-based classification rule, we may derive:

`AggressorSide`.

But this would be:

`DERIVED`

not:

`OBSERVED`.

And the classification error must be measured.

---

# 22. Delta

Required:

`CUMULATIVE_DELTA`.

Status:

`DERIVABLE ONLY IF AGGRESSOR SIDE IS RELIABLY AVAILABLE`.

Therefore:

`TrueData -> Trade`

does not automatically imply:

`TrueData -> Delta`.

This distinction is now officially recorded.

---

# 23. Flow Imbalance

Required:

`FLOW_IMBALANCE`.

Status:

`DERIVABLE ONLY AFTER VALID FLOW CLASSIFICATION`.

Therefore currently:

`CONDITIONAL`.

---

# 24. Order-Book Depth

Required:

`BID_DEPTH[k]`

`ASK_DEPTH[k]`.

Status:

`CONDITIONAL`.

TrueData's current public documentation says market depth is available where supported and separately describes a Market Depth API with top-five bid/ask levels, quantities and traded volumes.

But we need to establish whether:

`NSE`

and specifically:

`NIFTY / NIFTY options`

are included under our exact subscription.

---

# 25. Historical Order Book

Required for training:

`HistoricalDepth`.

Status:

`UNKNOWN / HIGH-RISK TODO`.

TrueData's support site contains a recent question specifically titled:

`order book history`

whose status is shown as under consideration.

Therefore we absolutely cannot assume that historical depth equivalent to live depth exists.

This is one of the most important unresolved source questions.

---

# 26. Historical Tick Data

Required for:

`microstructure model training`.

Default API status:

`LIMITED`.

TrueData currently documents:

`last 5 trading days`

for tick history through its standard historical API.

Therefore:

`5-year tick training`

is NOT currently established.

---

# 27. Full Market Replay

TrueData's current public market-data page advertises:

`Market Replay`.



However, we must establish whether this is:

`included in our subscription`

and:

`historically available for the exact instruments we require`.

Therefore:

`Replay = CONDITIONAL`.

---

# 28. Minute Historical Data

Default documented availability:

`1/2/3/5/10/15/30/60-minute bars`

for:

`last 6 months`.



This is insufficient for our originally envisioned multi-year minute-level walk-forward research unless extended history is part of our entitlement.

TrueData says extended history may be available as an add-on.

---

# 29. Daily Historical Data

Status:

`CONFIRMED`.

TrueData documents:

`10+ years`

of daily bars.

This can support longer-horizon contextual variables.

It cannot substitute for tick-level microstructure history.

---

# 30. Option Chain

Required:

`OPTION_CHAIN`.

Status:

`CONFIRMED`.

TrueData explicitly documents real-time and streaming option-chain functionality.

---

# 31. Option Bid/Ask

Status:

`CONFIRMED`.

The option-chain API explicitly exposes:

`bid`

`bid qty`

`ask`

`ask qty`.

This is sufficient to construct:

`OptionSpread`

`RelativeSpread`

and several execution features.

---

# 32. Option Volume

Status:

`CONFIRMED`.

The option-chain API exposes:

`volume`.



---

# 33. Option Open Interest

Status:

`CONFIRMED`.

The option-chain API exposes:

`oi`.



---

# 34. Option OI Change

Status:

`CONFIRMED`.

The option-chain API provides:

`OI Change`

`OI Change %`.

---

# 35. Option Greeks

TrueData's current API product page advertises:

`IV`

`Delta`

`Theta`

`Vega`

`Gamma`

and additional matrices.

Status:

`CONFIRMED AT PRODUCT LEVEL`.

Exact endpoint/field semantics remain:

`TBD`.

---

# 36. Implied Volatility

Status:

`CONFIRMED AT PRODUCT LEVEL`.

But we must distinguish:

`provider-supplied IV`

from:

`our own reconstructed IV`.

Only one should be canonical for a given model.

If provider IV is used:

its calculation methodology and timestamp semantics should be documented.

---

# 37. Option Greeks Provenance

We will not assume:

`TrueData Delta`

equals:

`our mathematically reconstructed Delta`.

The registry must retain:

`GreekSource = PROVIDER`

or:

`GreekSource = DERIVED`.

This prevents hidden model inconsistency.

---

# 38. Expired Options

TrueData support documentation states that expired-options data was available through the API from:

`February 2020`

in the referenced documentation.

However, this is an older support statement.

Therefore current:

`expired-options retention`

must be reconfirmed against our actual subscription.

---

# 39. Option Historical Reconstruction

This is more important than simply having:

`expired option data`.

For our backtest we need:

`Underlying(t)`

and:

`OptionQuote(t)`

and ideally:

`OptionBidAsk(t)`

for the historical timestamp.

Having an expired option's daily/bar data is not automatically sufficient for tick-level execution simulation.

---

# 40. Execution Cost

Required:

`EXECUTION_COST_DISTRIBUTION`.

Status:

`NOT DIRECTLY PROVIDED`.

It must be constructed from:

`Bid`

`Ask`

`ActualFill`

`Slippage`

`Fees`

`OrderLatency`

and execution history.

---

# 41. Slippage

Required:

`REALIZED_SLIPPAGE`.

Status:

`NOT AVAILABLE FROM MARKET FEED ALONE`.

It requires actual execution records.

Therefore this is a separate:

`BROKER/EXECUTION DATA CONTRACT`.

---

# 42. Fill Probability

Required:

`FILL_PROBABILITY`.

Status:

`LEARNED`.

It cannot be obtained merely from:

`bid`

`ask`.

We need historical order-placement and fill observations.

If we have no such dataset initially:

the model must begin with a conservative execution assumption and later replace it with empirical estimates.

---

# 43. Feed Latency

Required:

`FEED_LATENCY`.

Status:

`DERIVABLE`.

We capture:

`local_receive_time`

and compare it with the event timestamp.

This is essential for the micro-scalping layer.

---

# 44. Event Ordering

Required:

`SEQUENCE_VALID`.

Status:

`UNKNOWN`.

We need documentation or empirical testing to determine:

`Does the WebSocket provide sequence numbers?`

`Are events guaranteed ordered?`

`Can multiple events share timestamps?`

This becomes a source TODO.

---

# 45. Tick Granularity

TrueData advertises real-time tick streaming.

But our specification requires us to distinguish:

`tick event`

from:

`1-second snapshot`.

TrueData's product documentation also describes Level-one data at one-second frequency.

Therefore we must verify that our exact subscription delivers:

`event-level ticks`

rather than only:

`one-second snapshots`.

This is absolutely critical for our intended micro-scalping strategy.

---

# 46. Data Architecture Consequence

We now divide the strategy's data into three tiers.

`TIER A — Long Historical Context`

Potentially:

`daily`

`minute bars`

`expired options`.

Purpose:

`regime`

`seasonality`

`time-of-day`

`volatility distributions`

`broad directional behavior`.

---

`TIER B — Short Historical Microstructure`

Potentially:

`tick`

`quote`

`depth`.

Purpose:

`flow`

`microstructure`

`execution`

`short-horizon reversal`

`short-horizon continuation`.

---

`TIER C — Live State`

Real-time:

`tick`

`quote`

`option chain`

`depth where entitled`.

Purpose:

`current decision`.

---

# 47. Major Architectural Correction

We should NOT train one giant model using:

`10 years of daily`

plus:

`6 months of minute`

plus:

`5 days of tick`

as though they were equivalent observations.

They represent different information resolutions and statistical structures.

Instead:

`Long-Horizon Context Model`

and:

`Microstructure Model`

must remain distinct but composable.

---

# 48. Compositional Model

The architecture becomes:

`LongContextState`

+

`CurrentMarketState`

+

`MicrostructureState`

+

`ExecutionState`

→

`ConditionalProbability`.

This is much more statistically defensible.

---

# 49. Microstructure Evidence Window

Because historical tick availability may be short:

the microstructure model's evidence must be explicitly restricted to its actual historical support.

It cannot claim:

`5 years of tick evidence`.

It can claim only:

`available validated tick history`.

---

# 50. Regime Transfer

The longer historical model can provide:

`PriorDistribution`.

The short-history microstructure model provides:

`CurrentConditionalAdjustment`.

Conceptually:

`Posterior = Prior × MicrostructureEvidence`.

This is an appropriate use of the differing historical resolutions.

---

# 51. Important Statistical Safeguard

The short tick history must not be allowed to completely override the long-history prior merely because it contains many ticks.

Remember:

`1,000,000 ticks != 1,000,000 independent observations`.

The evidence system already accounts for:

`effective sample size`.

---

# 52. Source-Contract Status Matrix

At this stage:

`LTP -> CONFIRMED`

`Bid -> CONFIRMED`

`Ask -> CONFIRMED`

`BidQty -> CONFIRMED`

`AskQty -> CONFIRMED`

`TradeQuantity -> CONFIRMED/field TBD`

`Volume -> CONFIRMED`

`OI -> CONFIRMED`

`OIChange -> CONFIRMED`

`OptionChain -> CONFIRMED`

`OptionIV -> CONFIRMED at product level`

`Greeks -> CONFIRMED at product level`

`AggressorSide -> UNKNOWN`

`Delta -> CONDITIONAL`

`FlowImbalance -> CONDITIONAL`

`Depth -> CONDITIONAL`

`HistoricalDepth -> UNKNOWN`

`HistoricalTick -> LIMITED`

`HistoricalMinute -> LIMITED`

`HistoricalDaily -> CONFIRMED`

`MarketReplay -> CONDITIONAL`

`FillProbability -> LEARNED`

`Slippage -> BROKER/EXECUTION`

`FeedLatency -> DERIVABLE`

`SequenceGuarantee -> UNKNOWN`.

---

# 53. What This Means for the Strategy

We can already implement the mathematical architecture without waiting for documentation.

But we cannot yet claim:

"All of our desired microstructure variables are available."

The correct statement is:

`The architecture supports them; source availability remains conditional for several variables.`

That is exactly how the design should behave.

---

# 54. Highest-Priority Source TODOs

The remaining source questions are now sharply defined.

`TODO-001`

Does our exact TrueData subscription provide true event-level tick streaming or one-second snapshots?

`TODO-002`

What are the exact tick fields?

`TODO-003`

What are their timestamp semantics and precision?

`TODO-004`

Are sequence identifiers provided?

`TODO-005`

Is historical tick data beyond five trading days included in our entitlement?

`TODO-006`

Is historical depth available?

`TODO-007`

How many depth levels are available?

`TODO-008`

Are historical option bid/ask ticks available?

`TODO-009`

What is the exact expired-option historical coverage?

`TODO-010`

What are the exact option Greek field semantics?

`TODO-011`

Can aggressor side be reconstructed reliably?

`TODO-012`

What execution/fill data will we obtain from the broker?

`TODO-013`

What are actual brokerage, taxes and transaction-cost rules for our execution path?

---

# 55. Current Verdict

The source reconciliation gives us a very useful result:

The strategy does NOT depend on every desired data source being available.

Instead, the system can degrade gracefully.

For example:

`Depth unavailable`

does not mean:

`system broken`.

It means:

`DepthFeatures = unavailable`.

The model must then use the validated feature subset whose evidence remains sufficient.

But:

`required feature unavailable`

must never become:

`feature = 0`.

---

# 56. Data Capability State

We therefore introduce:

`DATA_CAPABILITY_STATE`.

For each feature domain:

`AVAILABLE`

`PARTIAL`

`UNAVAILABLE`.

The predictive model receives the capability state.

This prevents the model from interpreting missing information as neutral information.

---

# 57. Final Data Boundary

The production pipeline now becomes:

```text
TRUE DATA SOURCE
      |
      v
SOURCE CONTRACT
      |
      v
RAW EVENT
      |
      v
DATA VALIDATION
      |
      v
CANONICAL EVENT
      |
      v
STATE TRANSFORMATION
      |
      v
FEATURE VECTOR
      |
      v
CAPABILITY MASK
      |
      v
PROBABILITY MODEL
      |
      v
EVIDENCE
      |
      v
ECONOMIC DECISION
```

The new:

`CAPABILITY_MASK`

is important.

It tells the statistical layer:

"Which information domains actually exist right now?"

---

# 58. Next Step

We have now reached the point where another theoretical layer would be inefficient.

The next artifact should be the:

# DATA CAPABILITY AND MODEL DEGRADATION SPECIFICATION

That specification will answer a difficult practical question:

Suppose we expect:

`Price + Flow + Depth + Options + IV`

but at some timestamp we only have:

`Price + Options + IV`.

Exactly what does the model do?

We will define:

`feature availability`

`feature dependency`

`minimum viable feature set`

`model fallback hierarchy`

`evidence degradation`

`trade disabling`

and:

`NO_TRADE conditions`.

That will make the strategy robust to real-world feed degradation instead of assuming the ideal data stream exists continuously.