# Adaptive Edge V2.1 — A27 TrueData Field-Level Feature Contract

**Artifact:** A27-TD
**Version:** 2.1.0
**Status:** PROPOSED-RESEARCH-CONTRACT
**Market-data authority:** TrueData only
**Execution authority:** Zerodha Kite only

## Purpose

Freeze the provider-to-canonical feature mapping that is directly established by the repository's TrueData V2.6 adapter and source documentation, while keeping undocumented provider semantics explicitly unresolved.

## Authoritative transport

The existing adapter uses TrueData V2.6 endpoints:

```text
GET /getticks
GET /getbars
GET /getlastnbars
GET /getlastnticks
GET /getAllSymbols
GET /getOptionChain
```

The adapter's documented historical record fields are:

```text
Ticks:
 timestamp, ltp, volume, oi, bid, bidqty, ask, askqty

Bars:
 timestamp, open, high, low, close, volume, oi
```

The adapter supports bar intervals:

```text
1min, 2min, 3min, 5min, 10min, 15min, 30min, 60min
```

and last-N bars for:

```text
1min, 2min, 3min, 5min, 15min, 30min, 60min, eod
```

with documented `n <= 200` for last-N requests.

## Canonical mappings

```text
TrueData timestamp  -> MarketEvent.source_timestamp
TrueData ltp         -> LastPrice
TrueData bid         -> BestBid
TrueData bidqty      -> BidSize
TrueData ask         -> BestAsk
TrueData askqty      -> AskSize
TrueData volume      -> TotalVolume / source-defined volume field
TrueData oi          -> OpenInterest
```

For bars:

```text
open  -> BarOpen
high  -> BarHigh
low   -> BarLow
close -> BarClose
volume -> BarVolume
oi    -> BarOpenInterest
```

The exact semantic meaning of `volume`, `oi`, and timestamp fields remains source-controlled and must not be broadened beyond the TrueData documentation.

## Feature formulas

```text
Mid = (BestBid + BestAsk) / 2
Spread = BestAsk - BestBid
RelativeSpread = Spread / Mid
```

with validity conditions:

```text
BestBid and BestAsk present
Mid > 0 for RelativeSpread
```

A crossed quote is invalid unless the canonical source contract explicitly classifies it otherwise.

## A26 target price

For V2.1 research labels, the canonical terminal outcome is based on a **completed TrueData bar close** for the selected underlying/reference instrument.

The target therefore uses:

```text
P(t)     = close of the completed reference bar containing the decision boundary
P(t+h)   = close of the completed reference bar at the selected horizon boundary
```

The bar interval is a versioned research configuration. No fixed horizon is implied by this artifact.

This choice avoids treating an arbitrary tick received near the target boundary as the terminal observation and makes historical label reconstruction deterministic.

## Causal availability

A completed bar may be used only when its source availability time is at or before the decision time.

A future bar's eventual close cannot be used for an earlier decision.

## Feature classes

### Observed

```text
LastPrice
BestBid
BestAsk
BidSize
AskSize
TotalVolume
OpenInterest
```

### Derived

```text
Mid
Spread
RelativeSpread
```

### Bar-derived

```text
BarOpen
BarHigh
BarLow
BarClose
BarVolume
BarOpenInterest
```

### Research-parameterized

```text
Return(Δ)
RollingReturn(W)
RollingVolatility(W)
RollingVolume(W)
RollingSpread(W)
```

## Aggressor classification

TrueData ticks do not establish a canonical aggressor-side field in the current source contract.

Therefore:

```text
AggressorSide = UNKNOWN
Delta = BLOCKED
BuyAggressorVolume = BLOCKED
SellAggressorVolume = BLOCKED
```

No quote-based classifier is admitted to the production feature set without a separate validated research definition.

## Historical availability

The repository records the default TrueData historical boundaries as:

```text
Tick history       = limited
Minute bars        = approximately six months
Daily bars         = 10+ years
Historical depth   = not established
```

Exact subscription entitlement remains an operational dependency.

A research claim must record the actual dataset coverage used.

## Option data

Option-chain fields available through the TrueData contract include:

```text
instrument identity
expiry
strike
option type
LTP
bid
bid quantity
ask
ask quantity
volume
OI
OI change
```

Provider-supplied Greeks/IV remain separate source variables and are not automatically included in the predictive feature set.

## Missingness

Every feature has an explicit state:

```text
VALID
MISSING
STALE
INVALID
NOT_APPLICABLE
```

No missing feature is converted to zero.

## Dependency rule

```text
TrueData raw event
   -> canonical market event
   -> canonical state
   -> feature
   -> immutable FeatureSnapshot
```

Kite events are forbidden from entering the pre-decision FeatureSnapshot.

## Attack

### Provider-field ambiguity

The adapter mapping is frozen only where the provider field is explicitly present. Semantic interpretation remains limited to documented meaning.

### Look-ahead

Completed future bars cannot enter a snapshot until their availability boundary is satisfied.

### Historical-depth overclaim

Live depth availability cannot be used as evidence of historical depth coverage.

### Tick-history overclaim

The system must not claim multi-year tick-level evidence without an entitled historical source that actually provides it.

### Execution contamination

Kite fill price, position, and realized P&L cannot enter prediction features.

## ARCHITECTURE STATUS

**FROZEN:** TrueData-only feature source; endpoint/field mappings supported by the existing V2.6 adapter; canonical quote formulas; completed-bar target-price convention; causal availability; explicit missingness; Kite exclusion.

**CONFIGURABLE/LEARNED:** bar interval; return lookbacks; rolling windows; volatility estimator; freshness thresholds; final feature subset.

**UNKNOWN:** exact provider timestamp timezone/ordering semantics; account entitlement; aggressor classification; historical depth; exact option Greeks/IV methodology.

**BLOCKERS:** only the UNKNOWN provider semantics block production data authorization; the canonical feature architecture itself is resolved.

**NEXT ARTIFACT:** A28 — Edge / Prediction Contract.
