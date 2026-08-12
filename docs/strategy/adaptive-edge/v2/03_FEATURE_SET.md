# Adaptive Edge V2 — Canonical Feature Set and Feature Semantics

**Version:** 2.0.0-draft
**Artifact:** A27
**Status:** SPECIFICATION-DRAFT / PARTIALLY-RESOLVED
**Depends on:** A25 Strategy Charter, A26 Opportunity and Outcome Definition, A01 TrueData Market-Data Contract
**Market-data authority:** TrueData only
**Trading/execution authority:** Zerodha Kite only; execution data is downstream and cannot enter a pre-decision feature snapshot
**Implementation authorization:** NONE

## 1. Purpose

A27 defines the feature boundary for Adaptive Edge V2.

The feature layer answers one question only:

> What measurable information was available at `decision_time`, and what exact transformation produced each feature value?

A feature is not permitted to encode a future outcome, prediction, risk authorization, execution result, or accounting result.

The feature layer is therefore:

```text
TrueData observations
        |
        v
Canonical market events/state
        |
        v
Canonical feature values
        |
        v
FeatureSnapshot
```

No strategy decision is made inside this layer.

## 2. Source boundary

All Adaptive Edge market/research observations used by this feature layer must originate from TrueData and pass through the canonical market-data boundary defined by A01.

The feature layer must not consume Kite quotes, Kite positions, Kite fills, or any other broker execution state.

Kite data may enter later execution/accounting/reconciliation artifacts, but cannot be used to construct a feature for a decision that predates the corresponding broker event.

## 3. Feature definition contract

Every production feature must have:

```text
feature_id
feature_version
semantic_definition
mathematical_definition
unit
input_dependencies
observation_window
availability_rule
missing_data_rule
staleness_rule
initialization_rule
normalization_rule
provenance
owner
```

A formula without these semantics is not a complete feature definition.

## 4. Feature classes

V2 distinguishes four feature classes:

```text
OBSERVED
DERIVED
AGGREGATED
NORMALIZED
```

### OBSERVED

A canonical value directly represented by an authoritative TrueData market-data event.

### DERIVED

A deterministic transformation of canonical observed values.

### AGGREGATED

A deterministic transformation over a defined historical observation window.

### NORMALIZED

A transformation using learned or estimated reference quantities. Normalization parameters are versioned learned state and must obey the training-boundary rules defined by the learning artifact.

## 5. Canonical observed feature boundary

V2 defines the following semantic feature slots, subject to A01 source availability:

```text
F-OBS-BID
F-OBS-ASK
F-OBS-LAST
F-OBS-VOLUME
```

These names define canonical semantics, not TrueData field names.

### F-OBS-BID

Best currently available bid for the instrument at the observation timestamp, sourced from the canonical TrueData quote event.

### F-OBS-ASK

Best currently available ask for the instrument at the observation timestamp, sourced from the canonical TrueData quote event.

### F-OBS-LAST

Most recent canonical traded/last-price observation available at the observation timestamp, sourced from TrueData.

### F-OBS-VOLUME

Cumulative traded volume represented by the authoritative TrueData observation at the observation timestamp, subject to the exact source semantics documented by A01.

## 6. Derived quote features

### F-DER-MID

```text
Mid(t) = (Bid(t) + Ask(t)) / 2
```

Required inputs:

```text
Bid(t)
Ask(t)
```

The feature is invalid when either required input is unavailable or fails the canonical quote-validity contract.

`Mid` is a valuation/reference quantity. It is not an executable fill price.

### F-DER-SPREAD

```text
Spread(t) = Ask(t) - Bid(t)
```

A negative spread is not silently corrected. Crossed/locked market handling belongs to the A01 canonical market-data validity contract.

### F-DER-SPREAD-BPS

```text
SpreadBps(t) = 10000 * Spread(t) / Mid(t)
```

Valid only when `Mid(t) > 0` and the quote state is valid.

Unit: basis points.

## 7. Price-return features

V2 permits return features only when their observation interval is explicitly versioned.

Canonical equation:

```text
Return(t, Δ) = P(t) / P(t-Δ) - 1
```

where `P` is an explicitly selected canonical price feature.

The interval `Δ` is currently:

```text
UNKNOWN
```

No numerical lookback is frozen in A27.

Therefore no specific return feature instance is production-authorized yet.

## 8. Aggregated features

Aggregated features require an explicit window:

```text
W = [t_start, t_end]
```

with:

```text
every observation used
    must satisfy
availability_time <= decision_time
```

Permitted architectural families include:

```text
rolling return
rolling volatility
rolling volume
rolling spread
range statistics
```

No lookback value is chosen because changing the window changes the statistical population and strategy behavior.

## 9. Volume features

`F-OBS-VOLUME` is source-defined cumulative volume.

Derived volume-rate features require an explicit interval and aggregation convention.

The implementation must not assume that a field named `volume` means a particular unit until A01/TrueData documentation establishes it.

## 10. Time features

Time-derived features are permitted only from the canonical decision timestamp and authoritative session calendar.

Examples:

```text
session state
elapsed session time
remaining session time
```

Exact session semantics remain an external dependency until the exchange/instrument contract is frozen.

## 11. Instrument-context features

Feature snapshots may carry immutable instrument context required to interpret observations:

```text
instrument_id
instrument_type
underlying_id
expiry
strike
option_type
contract_multiplier
```

These are context, not predictive features by default.

Their exact availability and historical validity are governed by the instrument contract.

## 12. Option-specific features

The following are not automatically admitted to the predictive feature set merely because TrueData may provide them:

```text
delta
gamma
vega
theta
implied_volatility
open_interest
option-chain rank
```

Each requires a separate canonical semantic definition, source provenance, timestamp semantics, and causal availability contract before use.

Provider-supplied Greeks remain distinct from internally reconstructed Greeks.

## 13. Order-flow features

The master strategy specification defines aggressor-side and delta concepts, but A01 currently marks authoritative aggressor-side volume as UNKNOWN.

Therefore the following remain unavailable to the canonical feature set until their source semantics are resolved:

```text
aggressive buy volume
aggressive sell volume
cumulative delta
flow imbalance
```

A quote-based reconstruction may be considered only as an explicitly DERIVED feature after its classification error is defined and validated.

## 14. Historical microstructure constraint

A01 establishes that default documented TrueData tick history is limited and historical depth is not established.

Therefore A27 cannot silently assume multi-year tick/depth history for feature normalization or model training.

Feature populations must record the actual historical source coverage used.

## 15. Feature snapshot

At decision time `t_d`:

```text
FeatureSnapshot
{
    snapshot_id
    strategy_version
    feature_set_version
    decision_time
    observation_cutoff_time

    feature_values
    feature_statuses

    source_event_references
    instrument_context

    provenance
}
```

A snapshot is immutable once used for a decision.

## 16. Causal availability

For every feature value `f` used by a decision:

```text
availability_time(f) <= decision_time
```

For a derived feature, this must hold for every dependency.

For an aggregated feature, every constituent observation must satisfy the same availability boundary.

## 17. Current-bar rule

A partially forming bar may not contribute its eventual final OHLC value to an earlier decision.

If a feature uses a completed bar, the bar's completion/availability timestamp must be <= `decision_time`.

The authoritative availability semantics must come from the TrueData feed contract, not from assumptions about generic bars.

## 18. Missing-data states

A feature value must carry an explicit status:

```text
VALID
MISSING
STALE
INVALID
NOT_APPLICABLE
```

Missing values are not silently converted to zero.

Stale values are not silently treated as current.

Invalid source data is not silently repaired inside the strategy feature layer.

## 19. Staleness

A feature requiring freshness must define:

```text
reference_time
maximum_allowed_age
staleness_action
```

No universal numerical freshness threshold is frozen here.

Until a feature-specific freshness policy exists, the feature cannot be used where freshness is a required strategy condition.

## 20. Initialization

A rolling feature cannot become valid before its required historical observation population exists.

It must not be initialized using future observations or undocumented defaults.

## 21. Normalization

Any fitted transformation such as:

```text
z = (x - μ) / σ
```

must treat `μ` and `σ` as versioned learned state.

They must be estimated only from the permitted training population and must never use future observations relative to the decision being evaluated.

Full-dataset normalization before temporal evaluation is forbidden.

## 22. Feature dependencies

Every feature has an explicit dependency graph.

Example:

```text
F-DER-SPREAD-BPS
        |
        +--> F-DER-SPREAD
        |       +--> F-OBS-ASK
        |       +--> F-OBS-BID
        |
        +--> F-DER-MID
                +--> F-OBS-ASK
                +--> F-OBS-BID
```

A feature cannot read from a later strategy stage.

Forbidden:

```text
feature -> prediction
feature -> risk authorization
feature -> execution result
feature -> future label
```

## 23. Feature provenance

Every feature value used in a decision must be traceable to:

```text
TrueData raw source event(s)
    -> canonical event(s)
    -> canonical state
    -> feature formula/version
    -> feature value
    -> FeatureSnapshot
```

## 24. Feature versioning

A semantic change to any of the following requires a new feature version:

```text
formula
input source
input semantics
window
normalization
missing-data rule
staleness rule
initialization rule
unit
```

Historical snapshots retain the version that actually produced them.

## 25. Feature set versioning

A `feature_set_version` identifies the exact collection of features supplied to a model/decision stage.

Changing feature membership is distinguishable from changing one feature's formula.

## 26. Attack — future information

Forbidden:

```text
future close
future volume
future spread
future option chain
future normalized distribution
```

entering a snapshot before those observations were available.

## 27. Attack — provider semantics

A TrueData field cannot be mapped to a canonical feature merely because its name looks equivalent.

For example:

```text
TrueData field = "volume"
```

does not establish whether the field represents cumulative session volume, interval volume, last-trade quantity, or another quantity until the authoritative source contract establishes it.

## 28. Attack — stale quote

A bid/ask that is present but stale must not be interpreted as a contemporaneous executable quote.

## 29. Attack — crossed quote

For:

```text
Ask < Bid
```

V2 does not silently reorder values.

The canonical market-data contract determines whether the observation is invalid or otherwise handled.

## 30. Attack — hidden execution information

Features may not use:

```text
actual fill price
fill latency
fill success
realized slippage
post-decision order-book response
```

for a prediction made before those events occurred.

## 31. Attack — survivorship and instrument leakage

Historical instrument context must be time-valid.

A current instrument universe cannot be substituted for the historical universe.

## 32. Attack — feature-selection overfitting

Selecting features because they perform best on the eventual test period is forbidden.

Feature selection is itself a model-selection operation and must obey the temporal validation protocol.

## 33. Attack — multiple testing

If many candidate features are evaluated and the best subset is selected, the selection process must be included in the validation design.

The final test set cannot be repeatedly inspected to choose the feature set.

## 34. Attack — redundant evidence

Feature names must not be treated as independent evidence merely because they are distinct names.

Semantic and statistical redundancy must be assessed during research.

## 35. Initial V2 feature inventory

```text
OBSERVED
--------
F-OBS-BID
F-OBS-ASK
F-OBS-LAST
F-OBS-VOLUME

DERIVED
-------
F-DER-MID
F-DER-SPREAD
F-DER-SPREAD-BPS

DEFERRED / PARAMETERIZED
------------------------
Return(Δ)
RollingReturn(W)
RollingVolatility(W)
RollingVolume(W)
RollingSpread(W)
SessionTime
AggressorSide
Delta
FlowImbalance
OptionGreeks
OpenInterest-derived features
```

Only the first seven feature semantics are mathematically specified at this stage, and their provider availability remains governed by A01.

## 36. Dependencies

```text
A01 TrueData Market-Data Contract
A26 Opportunity / Outcome boundary
Instrument/contract metadata contract
Exchange session/calendar contract
Normalization and learning contract
```

## 37. Completion criterion

A feature is production-resolvable only when:

```text
semantic meaning
+ exact formula
+ all inputs
+ units
+ availability
+ window
+ missing/stale behavior
+ initialization
+ provenance
+ version
```

are defined and the required TrueData source semantics are confirmed.

## ARCHITECTURE STATUS

Frozen:

```text
feature-layer ownership
TrueData-only market-data boundary
causal feature boundary
FeatureSnapshot contract
observed quote feature semantics
mid/spread/spread-bps formulas
feature versioning
feature-set versioning
missing/stale/invalid state separation
provenance requirement
normalization leakage prohibition
```

## UNRESOLVED

```text
TrueData exact field mappings where not yet confirmed
session semantics
return intervals
rolling windows
warm-up policies
feature-specific freshness thresholds
option-specific derived features
aggressor classification
historical microstructure coverage
final predictive feature subset
```

## BLOCKERS

TrueData-specific feature implementation is blocked wherever the source contract is not confirmed.

Parameterized features remain blocked until their windows and semantics are established and validated.

A26's exact predictive target remains unresolved and therefore predictive feature selection cannot yet be finalized.

## NEXT ARTIFACT

**A28 — Edge / Prediction Contract.**
