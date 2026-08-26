# Adaptive Edge V2 — Canonical Feature Set and Feature Semantics

**Version:** 2.0.0-draft
**Artifact:** A27
**Status:** SPECIFICATION-DRAFT
**Depends on:** A25 Strategy Charter, A26 Opportunity and Outcome Definition
**Implementation authorization:** NONE

## 1. Purpose

A27 defines the feature boundary for Adaptive Edge V2.

The feature layer answers one question only:

> What measurable information was available at `decision_time`, and what exact transformation produced each feature value?

A feature is not permitted to encode a future outcome, prediction, risk authorization, execution result, or accounting result.

The feature layer is therefore:

```text
Causally available observations
        |
        v
Canonical feature values
        |
        v
FeatureSnapshot
```

No strategy decision is made inside this layer.

## 2. Feature definition contract

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

## 3. Feature classes

V2 distinguishes four feature classes:

```text
OBSERVED
DERIVED
AGGREGATED
NORMALIZED
```

### OBSERVED

A canonical value directly represented by an authoritative market-data event.

### DERIVED

A deterministic transformation of canonical observed values.

### AGGREGATED

A deterministic transformation over a defined historical observation window.

### NORMALIZED

A transformation using learned or estimated reference quantities. Normalization parameters are versioned learned state and must obey the training-boundary rules defined by the learning artifact.

## 4. Canonical observed feature boundary

V2 defines the following semantic feature slots, subject to provider availability:

```text
F-OBS-BID
F-OBS-ASK
F-OBS-LAST
F-OBS-VOLUME
```

These names define canonical semantics, not provider field names.

### F-OBS-BID

Best currently available executable bid for the instrument at the observation timestamp.

### F-OBS-ASK

Best currently available executable ask for the instrument at the observation timestamp.

### F-OBS-LAST

Most recent canonical traded/last-price observation available at the observation timestamp.

### F-OBS-VOLUME

Cumulative traded volume represented by the authoritative observation source at the observation timestamp.

The exact provider/exchange semantics, update behavior, and availability guarantees remain external dependencies until documented.

## 5. Derived quote features

V2 defines the following derived feature semantics when their required inputs are valid:

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

### F-DER-SPREAD

```text
Spread(t) = Ask(t) - Bid(t)
```

Required inputs:

```text
Bid(t)
Ask(t)
```

A negative spread is not silently corrected. Crossed/locked market handling belongs to the canonical market-data contract.

### F-DER-SPREAD-BPS

The semantic definition is:

```text
SpreadBps(t) = 10000 * Spread(t) / Mid(t)
```

It is valid only when `Mid(t) > 0` and the quote state is valid.

The unit is basis points.

## 6. Price-return features

V2 permits return features only when their observation interval is explicitly versioned.

The canonical return equation is:

```text
Return(t, Δ) = P(t) / P(t-Δ) - 1
```

where `P` must itself be an explicitly selected canonical price feature.

The interval `Δ` is currently:

```text
UNKNOWN
```

No numerical lookback is frozen in A27.

Therefore no specific return feature instance is production-authorized yet.

## 7. Aggregated features

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

The following feature families are permitted but not numerically instantiated:

```text
rolling return
rolling volatility
rolling volume
rolling spread
range statistics
```

No lookback value is chosen because changing the window changes the statistical population and strategy behavior.

## 8. Volume features

`F-OBS-VOLUME` is cumulative source-defined volume.

Derived volume-rate features require an explicit interval and aggregation convention.

No assumption is made that:

```textvolume rate = cumulative volume / elapsed time
```

because session boundaries, market closures, missing observations, and provider semantics must first be defined.

## 9. Time features

Time-derived features are permitted only from the canonical decision timestamp and authoritative session calendar.

Examples of semantic slots include:

```text
session state
elapsed session time
remaining session time
```

The exact session calendar is an external dependency and remains UNKNOWN until the exchange/instrument contract is frozen.

Therefore these are not yet production feature instances.

## 10. Instrument-context features

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

## 11. Option-specific features

V2 does not automatically include:

```text
delta
gamma
vega
theta
implied_volatility
open_interest
option-chain rank
```

These require additional source/model semantics and are therefore not part of the canonical feature set until a later artifact explicitly defines them.

In particular, an option Greek cannot be introduced merely because it is mathematically computable. Its pricing model, volatility input, timestamp, contract specification, and calibration semantics would all need to be defined.

## 12. Feature snapshot

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

## 13. Causal availability

For every feature value `f` used by a decision:

```text
availability_time(f) <= decision_time
```

For a derived feature, this must hold for every dependency.

For an aggregated feature, every constituent observation must satisfy the same availability boundary.

## 14. Current-bar rule

A partially forming bar may not contribute its eventual final OHLC value to an earlier decision.

If a feature uses a completed bar, the bar's completion/availability timestamp must be <= `decision_time`.

The data contract must provide the authoritative availability semantics.

## 15. Missing-data states

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

## 16. Staleness

A feature requiring freshness must define:

```text
reference_time
maximum_allowed_age
staleness_action
```

No universal numerical freshness threshold is frozen here.

Until a feature-specific freshness policy exists, the feature cannot be used where freshness is a required strategy condition.

## 17. Initialization

A rolling feature cannot become valid before its required historical observation population exists.

For example, a feature requiring a window `W` cannot be initialized using future observations or an undocumented default value.

The exact warm-up policy belongs to the feature definition.

## 18. Normalization

Any fitted transformation such as:

```text
z = (x - μ) / σ
```

must treat `μ` and `σ` as versioned learned state.

They must be estimated only from the permitted training population and must never use future observations relative to the decision being evaluated.

Full-dataset normalization before temporal evaluation is forbidden.

## 19. Feature dependencies

Each feature has an explicit dependency graph.

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

## 20. Feature provenance

Every feature value used in a decision must be traceable to:

```text
raw source event(s)
    -> canonical event(s)
    -> canonical state
    -> feature formula/version
    -> feature value
    -> FeatureSnapshot
```

This is required for reproducibility and audit.

## 21. Feature versioning

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

## 22. Feature set versioning

A `feature_set_version` identifies the exact collection of features supplied to a model/decision stage.

Changing feature membership is therefore distinguishable from changing one feature's formula.

Both changes are versioned.

## 23. Attack — future information

Forbidden:

```text
future close
future volume
future spread
future option chain
future normalized distribution
```

entering a snapshot before those observations were available.

## 24. Attack — provider semantics

A provider field cannot be mapped to a canonical feature merely because its name looks equivalent.

Example:

```text
provider_field = "volume"
```

does not prove whether it represents:

```text
cumulative session volume
bar volume
tick count
contract volume
```

The provider documentation must establish the mapping.

## 25. Attack — stale quote

A bid/ask that is present but stale must not be silently interpreted as a contemporaneous executable quote.

The stale policy must be explicit.

## 26. Attack — crossed quote

For:

```text
Ask < Bid
```

V2 does not silently reorder the values.

The market-data validity contract must determine whether the observation is invalid, corrected, or otherwise handled.

## 27. Attack — negative/zero price

Price-derived features must define their domain.

For example:

```text
SpreadBps
```

requires:

```text
Mid > 0
```

A zero/negative denominator must produce an explicit invalid state, not an arbitrary numerical replacement.

## 28. Attack — survivorship

Historical instrument context must be time-valid.

A current instrument universe cannot be substituted for the historical universe.

## 29. Attack — feature selection overfitting

Choosing features because they perform best on the eventual test period is forbidden.

Feature selection is itself a learned/model-selection process and must obey the training/validation/test protocol.

## 30. Attack — multiple testing

If many candidate features are evaluated and the best subset is selected, the selection process must be included in the validation design.

The final test set cannot be repeatedly inspected to choose the feature set.

## 31. Attack — duplicate information

Two feature names may encode substantially identical information.

The feature registry must retain semantic definitions so redundancy can be detected rather than accidentally interpreted as independent evidence.

## 32. Attack — leakage through normalization

A feature may appear causally valid while its normalization parameters were fitted using future data.

That is still leakage.

Therefore preprocessing belongs inside the temporal validation boundary.

## 33. Attack — hidden execution information

Features may not use:

```text
actual fill price
fill latency
fill success
realized slippage
post-decision order-book response
```

for a prediction made before those events occurred.

## 34. Initial V2 feature inventory

The canonical inventory at this artifact level is:

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

PARAMETERIZED / DEFERRED
------------------------
Return(Δ)
RollingReturn(W)
RollingVolatility(W)
RollingVolume(W)
RollingSpread(W)
SessionTime
```

Only the first seven feature semantics are fully specified mathematically at this stage, subject to source-data validity.

The parameterized families are architectural slots, not production-authorized feature instances.

## 35. External dependencies

### TrueData

Status: UNKNOWN.

No provider field mapping is frozen without TrueData documentation.

### Exchange/instrument specification

Status: UNKNOWN.

Required for exact session calendar, contract metadata, historical instrument validity, and instrument-specific market-data semantics.

## 36. Completion criterion

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

are defined.

## ARCHITECTURE STATUS

Frozen:

```text
feature-layer ownership
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
provider mappings
session semantics
exact return intervals
rolling windows
warm-up policies for parameterized features
feature-specific freshness thresholds
option-specific derived features
normalization methodology
final predictive feature subset
```

## BLOCKERS

No blocker to the feature architecture.

TrueData-specific feature implementation remains blocked until provider documentation is received.

Parameterized features remain blocked until their windows and semantics are established and subsequently validated.

## NEXT ARTIFACT

**A28 — Edge / Prediction Definition**

A28 must define exactly what V2 predicts from the FeatureSnapshot, the mathematical prediction object, prediction horizon dependency, calibration semantics, and the separation between prediction and economic eligibility.
