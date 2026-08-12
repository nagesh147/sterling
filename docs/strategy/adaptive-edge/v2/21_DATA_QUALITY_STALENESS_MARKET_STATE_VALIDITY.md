# Adaptive Edge V2 — Data Quality, Staleness and Market-State Validity Contract

**Artifact:** A45  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** FRAMEWORK-ONLY

## 1. Purpose

A45 defines when market observations and derived state are sufficiently valid for use by Adaptive Edge.

The purpose is to prevent missing, stale, malformed, contradictory, delayed, out-of-order, or causally unavailable data from silently becoming valid strategy inputs.

A45 does not invent provider-specific freshness thresholds or trading-session rules.

## 2. Canonical validity chain

```text
Provider Observation
        |
        v
Transport Validation
        |
        v
Schema Validation
        |
        v
Temporal Validation
        |
        v
Semantic Validation
        |
        v
Market-State Snapshot
        |
        v
Feature / Decision Eligibility
```

A record may pass one validation layer and fail another.

## 3. Quality states

Canonical quality states are:

```text
UNKNOWN
VALID
STALE
MISSING
INVALID
AMBIGUOUS
OUT_OF_ORDER
CORRECTED
UNAVAILABLE
```

The states are explicit and must not be collapsed into a Boolean `valid` flag where doing so loses important semantics.

## 4. Observation identity

Every canonical market observation must retain enough identity to distinguish:

```text
provider
instrument
observation type
observation timestamp
availability timestamp where applicable
sequence/provider event identity where available
source version
quality state
```

A duplicate observation must be detectable without relying solely on arrival time.

## 5. Observation time versus arrival time

These timestamps are distinct:

```text
observation_time
provider_time
arrival_time
availability_time
processing_time
```

A value arriving late may still represent an earlier market event.

Arrival time must not silently replace observation time.

## 6. Availability

For causal decisions:

```text
availability_time <= decision_time
```

must hold for every required input.

A value with an earlier observation timestamp but later availability cannot be used as though it were known at the earlier time.

## 7. Staleness

A value is stale only relative to an explicit freshness policy.

A staleness policy must define:

```text
reference timestamp
maximum tolerated age
measurement unit
instrument/data type scope
session/calendar assumptions
failure behavior
policy version
```

A45 does not select a universal number of seconds or milliseconds.

## 8. Different data types require different freshness semantics

Freshness must not be treated as one global threshold for:

```text
LTP
bid/ask
volume
open interest
option chain
instrument metadata
corporate/contract metadata
derived features
```

The appropriate validity interval is source- and semantic-dependent.

## 9. Bid/ask validity

Bid and ask are separate observations.

The system must preserve:

```text
bid
bid quantity
ask
ask quantity
timestamp
source
```

A missing bid must not be synthesized from last price or mid.

A missing ask must not be synthesized from last price or bid.

## 10. Spread validity

A spread is valid only when both required price sides are valid and temporally compatible under the feature/execution policy.

Conceptually:

```text
Spread = Ask - Bid
```

but A45 does not authorize a spread-derived feature unless the underlying bid/ask semantics are valid.

## 11. Mid validity

A midpoint requires valid bid and ask observations:

```text
Mid = (Bid + Ask) / 2
```

The formula is structural only.

It does not establish that mid is executable.

## 12. LTP validity

LTP is a provider observation, not necessarily an executable price.

An LTP may be valid as a market observation while simultaneously being unsuitable as an execution reference.

Those decisions belong to downstream feature/execution policies.

## 13. Volume and OI validity

Volume and open interest must preserve their provider semantics and observation interval.

A value cannot be interpreted as:

```text
per-tick volume
per-bar volume
cumulative volume
incremental volume
```

without the source definition establishing which it is.

Likewise, OI must not be treated as an instantaneous economic flow merely because it changes between observations.

## 14. Option-chain validity

An option-chain snapshot must identify:

```text
underlying
expiry context
observation time
availability time
candidate contract identities
quote/metadata quality
source/version
```

A partial chain must not be represented as a complete universe.

Missing contracts must remain distinguishable from contracts that were genuinely absent.

## 15. Instrument metadata validity

Instrument metadata is time-dependent where contract terms can change.

Historical replay must use metadata valid for the simulated time.

Current lot size, expiry, multiplier, symbol mapping, or contract state must not be applied retrospectively when historical terms differ.

## 16. Sequence ordering

If provider sequence numbers or event ordering metadata exist, canonical ingestion must preserve and validate them.

An event arriving after a later event is not automatically a newer market state.

Out-of-order events must be explicitly classified and handled according to policy.

## 17. Duplicate events

Duplicate provider observations must not produce duplicate economic effects.

Canonical deduplication must use stable provider/event identity where available and an explicitly versioned fallback identity where necessary.

Deduplication must not accidentally remove two genuinely distinct observations that happen to share a timestamp and value.

## 18. Corrections

If a provider corrects a historical observation:

```text
original observation
        +
correction event
```

must preserve lineage.

The corrected value must not silently overwrite the originally available value when evaluating historical causal knowledge.

## 19. Missingness

Missing data must remain explicit.

The following substitutions are forbidden unless a versioned policy explicitly authorizes them:

```text
missing -> 0
missing -> previous value
missing -> current value
missing -> mean
missing -> false
missing -> neutral
```

## 20. Contradictory observations

If simultaneously available source records contradict one another, the system must not silently choose one merely because it is convenient.

The canonical state becomes:

```text
AMBIGUOUS
```

unless an authoritative source-precedence policy resolves the conflict.

## 21. Cross-source reconciliation

When multiple providers describe the same market state, equality must not be assumed merely because symbols appear equivalent.

Cross-source reconciliation requires explicit:

```text
instrument mapping
field semantics
timestamp semantics
venue semantics
corporate/contract mapping
source precedence
```

Adaptive Edge V2 does not use cross-provider market data to silently repair TrueData observations.

## 22. Session boundaries

Data validity can depend on the trading session.

A45 does not assume universal:

```text
24/7 trading
continuous session
fixed opening time
fixed closing time
```

Session calendars must come from an authoritative market/instrument contract.

## 23. Session gaps

A large elapsed time between observations does not automatically mean the latest observation is stale if the market was legitimately closed.

Staleness policy must therefore distinguish elapsed wall-clock time from valid market-state continuity where required.

## 24. Market halt / suspension

A lack of new prices may represent:

```text
no update
market halt
instrument suspension
provider outage
```

These states are semantically different.

The system must not infer one from silence alone.

## 25. Provider outage

If the market-data provider becomes unavailable:

```text
market state = UNKNOWN / UNAVAILABLE
```

unless another explicitly authorized source can provide a causally valid replacement.

A provider outage must not automatically become `last known price = current price`.

## 26. Data recovery

After an outage, recovered historical events must retain their original event/observation timestamps.

Recovery arrival time must not cause the recovered data to appear as though it was available during the outage.

## 27. Watermarks

A streaming pipeline may maintain a causal watermark:

```text
latest state known complete enough for policy P
```

The watermark is policy-specific and must not be confused with wall-clock time.

## 28. Feature propagation

A feature depending on invalid/stale/ambiguous required inputs cannot become valid merely because its arithmetic produces a number.

Conceptually:

```text
invalid dependency
    -> invalid/blocked feature
```

unless the feature policy explicitly defines an allowed degraded state.

## 29. Decision gating

A decision must be blocked when any mandatory input is:

```text
MISSING
STALE
INVALID
AMBIGUOUS
OUT_OF_ORDER
UNAVAILABLE
causally unavailable
```

unless an explicit policy defines a safe degraded mode.

The degraded mode itself must be versioned.

## 30. Risk propagation

A stale or invalid risk input must not become zero risk.

Therefore:

```text
risk input invalid
    -> risk authorization blocked
```

subject to the explicit A31/A32 policy once resolved.

## 31. Execution propagation

A stale executable-price input must not become a market order fallback merely because execution is desired.

If required execution semantics are unavailable, A44 requires fail-closed behavior.

## 32. Historical replay quality

Historical replay must distinguish at least:

```text
value that existed historically
value that was available historically
value corrected later
value reconstructed retrospectively
```

Only the first two are sufficient for causal replay when the evaluation asks what the strategy could actually have known.

## 33. Backfill leakage

A later historical backfill must not be injected into an earlier decision as though the data had been available then.

Example:

```text
2026 decision
2028 provider correction/backfill

2028 value != automatically valid 2026 input
```

The dataset version and availability policy determine whether it is usable.

## 34. Quality metrics

The data-quality subsystem should retain measurable diagnostics such as:

```text
missing rate
stale rate
duplicate rate
out-of-order rate
correction rate
latency distribution
invalid-record count
ambiguous-record count
provider availability
```

These diagnostics are evidence about data quality, not strategy performance metrics.

No numerical acceptance threshold is selected here.

## 35. Quality does not imply profitability

A dataset can be high quality while the strategy has no edge.

Conversely, a profitable backtest can still be invalid if it depends on causally unavailable or corrupted data.

Data-quality validity is a prerequisite, not evidence of economic value.

## 36. Provenance

Every accepted market-state input must retain:

```text
source
source version
provider event identity where available
observation time
availability time
arrival time
quality state
correction lineage
validation policy version
```

## 37. Determinism

Given identical source events, source versions, validation policy version, and deterministic ordering rules, canonical market-state reconstruction must be deterministic.

## 38. Adversarial cases

### Late tick

```text
observation_time = 10:00
arrival_time = 10:05
```

The tick cannot be used as though it were available at 10:00 unless the source contract establishes that availability earlier.

### Duplicate tick

Two identical payloads do not automatically represent two trades/events.
Provider identity and event semantics must determine duplication.

### Missing ask

```text
bid = valid
ask = missing
```

The system cannot manufacture a mid or executable buy price.

### Stale quote

A quote exceeding the applicable freshness policy becomes stale; it does not remain valid merely because no newer quote exists.

### Provider outage

Silence cannot be treated as a stable price.

### Corrected history

A later corrected historical value cannot be treated as real-time knowledge in a causal replay unless the evaluation explicitly models revised information.

### Partial option chain

A partial chain cannot be treated as the complete candidate universe.

### Out-of-order events

An event received later cannot automatically move the canonical state backward or forward without the ordering policy resolving it.

## 39. Implementation gate

The quality framework may be implemented for:

```text
schema validation
timestamp validation
deduplication
quality states
provenance
watermarks
ordering
correction lineage
```

Provider-specific thresholds and semantic fallbacks remain blocked until their source contracts are resolved.

## 40. Parameter classes

### Frozen architecture

```text
explicit quality states
observation/availability separation
historical correction lineage
causal gating
fail-closed mandatory inputs
provider outage distinction
ordering/deduplication boundary
provenance
```

### Source-defined configuration

```text
freshness thresholds
session calendars
provider sequence semantics
field-specific validity rules
source precedence
recovery behavior
```

### Learned

No learned data-quality parameter is introduced by A45.

### External UNKNOWN

```text
TrueData publication latency
TrueData sequence guarantees
TrueData correction guarantees
provider outage semantics
historical data completeness
instrument-specific session calendars
```

## 41. Completion criterion

A45 becomes `RESOLVED` when the system can determine for every input used by a decision:

```text
what the observation means
when it occurred
when it became available
whether it was fresh enough
whether it was complete
whether it was corrected
whether it was causally usable
which policy accepted it
```

and reproduce the same validity state during historical replay.

## ARCHITECTURE STATUS

**FROZEN:** quality-state vocabulary; temporal availability boundary; missing/stale/invalid distinction; ordering; correction lineage; provider-outage separation; causal decision gating; provenance; deterministic reconstruction.

**UNRESOLVED:** provider-specific freshness thresholds; publication latency; sequence guarantees; session calendars; source precedence; recovery semantics; complete historical availability.

**BLOCKERS:** Exact provider quality semantics remain external. A45 does not block framework implementation, but it blocks production validity claims for any input whose source semantics remain unresolved.

**NEXT ARTIFACT:** A46 — Market Session, Clock and Temporal Calendar Contract.
