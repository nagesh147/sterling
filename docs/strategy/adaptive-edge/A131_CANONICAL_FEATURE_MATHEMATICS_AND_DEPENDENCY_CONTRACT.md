# A131 — Canonical Feature Mathematics and Dependency Contract

**Status:** Canonical implementation source of truth  
**Depends on:** A128, A129, A130  
**Purpose:** Define the formal contract by which Adaptive Edge features are mathematically specified, causally computed, versioned, validated, and exposed to downstream consumers.

## 1. Purpose

A131 defines what a feature means mathematically and what evidence is required to compute it.

It does not select arbitrary numerical parameters and does not claim that any feature has predictive value. Feature usefulness must be demonstrated later by out-of-sample evaluation.

The canonical chain is:

```text
canonical event/state evidence
    -> feature definition
    -> dependency resolution
    -> mathematical transformation
    -> validity/quality evaluation
    -> feature value
    -> A130 snapshot
```

## 2. Feature definition

Every canonical feature must have:

```text
feature_id
feature_name
semantic_definition
mathematical_definition
input_types
input_feature_ids / event_ids
observation_window
availability_rule
normalization_rule, if any
units
range/domain
missingness_rule
quality_rule
formula_id
formula_version
consumer_contracts
```

A name alone is never a mathematical specification.

## 3. Mathematical purity

A feature function must be expressible as:

```text
F_t = f(X_<=t, C_t, V)
```

where:

```text
X_<=t = causally available observations
C_t   = explicitly versioned configuration
V     = explicitly versioned formula/model dependencies
```

The function may not depend on future observations, mutable ambient state, or undocumented external values.

## 4. Temporal domain

For a feature evaluated at time `t`, every input must satisfy:

```text
available_at(input) <= t
```

For a rolling window `[t-H, t]`, the implementation must define whether the boundary is inclusive/exclusive and must preserve that convention across research and production.

No implicit look-back/look-forward convention is permitted.

## 5. Observation windows

Every windowed feature declares:

```text
window_start
window_end
boundary convention
required observation density
minimum history
```

A feature with insufficient history is:

```text
INSUFFICIENT_HISTORY
```

not a partially fabricated value.

## 6. Units and dimensional consistency

Every numerical feature declares units.

Mathematical operations must preserve dimensional validity.

Examples of forbidden implicit operations:

```text
price + quantity
price / time without declaring rate semantics
percentage treated as decimal without explicit convention
points mixed with currency without conversion
```

Unit conversion must be explicit and versioned where material.

## 7. Normalization

Normalization is part of the feature definition when it changes mathematical meaning.

Examples:

```text
z-score
log return
percentage return
volatility scaling
rank transformation
winsorization
```

A normalized feature must declare the population/window from which normalization parameters are obtained.

A normalization statistic may not use future observations.

## 8. Cross-sectional features

For cross-sectional features, the eligible universe must be explicitly defined at time `t`.

The universe must not be reconstructed from today's surviving instruments.

This prevents survivorship bias.

Required metadata includes:

```text
universe_id
universe_version
eligibility_time
membership_rule
```

## 9. Event-derived features

Event-derived features must identify the exact event classes consumed.

Examples:

```text
TRADE
QUOTE
DEPTH
BAR
OPEN_INTEREST
SESSION_EVENT
REFERENCE_UPDATE
```

A feature may not infer unavailable semantics from another event type merely because the fields appear numerically compatible.

## 10. Bar-derived features

A feature consuming a bar must consume only a bar whose closure satisfies A129.

For a bar interval:

```text
[start, end)
```

its closing value is unavailable before `end` unless the source explicitly provides a separate causally available finalized value earlier, which must itself be documented.

## 11. Quote/depth-derived features

Bid, ask, trade price, and depth are distinct observations.

A feature that requires executable bid/ask evidence must not substitute LTP unless its own mathematical specification explicitly defines LTP as the intended variable.

Crossed or invalid books inherit A129 quality semantics.

## 12. Option-derived features

Option features must reference A128 contract identity.

Required dimensions may include:

```text
underlying
expiry
strike
option_type
contract_version
```

Greeks and implied volatility are observations or derived estimates, not contract identity fields.

Their calculation method, inputs, timestamp, and version must be explicit.

No future option-chain observation may be used to reconstruct a historical value unless historical availability is established.

## 13. Feature composition

If:

```text
F3 = g(F1, F2)
```

then `F3` inherits the causal availability constraints of `F1` and `F2`.

Therefore:

```text
available_at(F3)
    >= max(available_at(F1), available_at(F2), computation_latency_boundary)
```

The exact operational latency boundary is implementation-specific, but the semantic ordering is frozen.

## 14. Feature dependency graph

The feature graph must be acyclic:

```text
Event
  -> F1
  -> F2
F1 -> F3
F2 -> F3
F3 -> F4
```

Forbidden:

```text
F1 -> F2 -> F3 -> F1
```

Dependency graphs must be versioned with the feature schema.

## 15. Recursive/time-series features

A recursive feature must define its recurrence explicitly.

For example:

```text
F_t = g(F_{t-1}, X_t)
```

requires:

```text
initial_state
state-update rule
reset condition
missing-input behavior
session boundary behavior
```

An implementation may not choose an initial state or reset rule implicitly.

## 16. State-dependent features

A feature may consume strategy/position state only when the state is explicitly declared as an input dependency.

This prevents circularity such as:

```text
feature -> decision -> position state -> same feature
```

If a feature depends on a decision or position generated by the same decision cycle, that dependency is invalid unless the specification explicitly defines a later causal phase.

## 17. Leakage barriers

The following are prohibited:

```text
future close
future high/low
future volume
future option chain
future open interest
future corporate action knowledge
future universe membership
future model output
future configuration
future execution result
```

unless the value's `available_at` is demonstrably <= the feature timestamp.

## 18. Corporate actions and adjusted data

Raw and adjusted prices remain separate mathematical domains.

A feature must declare its price basis:

```text
RAW
ADJUSTED
NOT_APPLICABLE
```

A feature may not mix the two without an explicit transformation contract.

Corporate-action source remains an external dependency governed by A129 until formally selected.

## 19. Numerical stability

Every mathematical feature must declare behavior for:

```text
zero denominator
near-zero denominator
overflow
underflow
NaN
infinity
negative domain for logarithms
invalid square-root domain
empty sample
constant sample
```

A mathematically undefined result must become an explicit invalid/missing state, not an arbitrary numerical substitute.

## 20. Outlier treatment

Outlier handling is part of the feature definition only if explicitly specified.

The following are not allowed implicitly:

```text
winsorization
clipping
capping
removal
replacement
```

If used, the rule and parameter source must be versioned.

Parameters derived from data must obey the same chronological training boundary as all other learned quantities.

## 21. Learned feature parameters

A feature parameter is learned only if its value is estimated from historical data rather than fixed by mathematical definition.

For every learned feature parameter, the specification must define:

```text
parameter_id
historical population
estimation method
positive/negative label, if supervised
observation horizon
label maturity
training boundary
validation boundary
test boundary
update frequency
promotion rule
rollback rule
```

No parameter is frozen because it appears profitable in-sample.

## 22. Feature quality

A feature is `VALID` only when all required mathematical and data conditions hold.

Quality evaluation includes:

```text
input quality
input completeness
causal availability
mathematical domain validity
unit consistency
version compatibility
numerical validity
```

One invalid required dependency invalidates the feature unless a feature-specific degraded mode is explicitly defined.

## 23. Consumer contract

Every feature declares who may consume it.

Example:

```text
feature -> Edge
feature -> Economics
feature -> Risk
feature -> Lifecycle
```

A consumer may not reinterpret the feature's units, timing, or mathematical meaning.

If a different interpretation is needed, a new canonical feature is defined.

## 24. Feature selection

A feature is not promoted to canonical status merely because it is intuitive, correlated with returns, or profitable in one backtest.

Promotion requires the research/evaluation contracts to establish:

```text
out-of-sample behavior
stability across time
stability across relevant regimes
transaction-cost sensitivity
parameter sensitivity
multiple-testing accounting
selection process provenance
```

## 25. Multiple testing and selection bias

Feature selection must record the candidate population considered.

A final selected feature set must not be evaluated as if it were the only hypothesis tested.

Research artifacts must preserve:

```text
candidate_set_id
experiment_id
selection_rule
selection_timestamp
validation results
held-out test status
```

The test set is not used for iterative feature selection.

## 26. Survivorship bias

For historical cross-sectional features, instrument eligibility is determined using time-valid membership data.

Current constituents cannot be silently substituted for historical constituents.

## 27. Backtest/live equivalence

A feature must have one canonical mathematical definition across:

```text
research
backtest
paper/simulation
live
```

Differences may exist in source adapters or latency, but not in semantic meaning.

## 28. Dependency matrix

| Dependency | Owner | Update | Consumer | Invariant | Failure |
|---|---|---|---|---|---|
| Market events | A129 | event-driven | feature engine | causal/typed | reject/degrade |
| Instrument identity | A128 | contract-version driven | feature engine | exact identity | reject |
| Formula registry | A131 | version-driven | all feature consumers | immutable version | block |
| Configuration | A130 config authority | version-driven | formula execution | explicit version | block |
| State | A126/A127/state owners | event-driven | state-dependent features | causal state | block/degrade |
| Universe | research/data authority | membership-version driven | cross-sectional features | historical membership | block affected study |
| Corporate actions | external authority | event-driven | adjusted features | explicit price basis | block affected feature |
| Greek/IV source | selected provider/calculation | event-driven | option features | timestamped method | degrade/block |

## 29. Frozen architecture

```text
formal feature identity
mathematical definition requirement
explicit dependency graph
causal availability
window boundary semantics
unit/dimensional validity
normalization provenance
cross-sectional universe validity
option contract identity dependency
recursive-state specification
numerical-domain handling
quality propagation
consumer ownership
backtest/live semantic equivalence
multiple-testing provenance
survivorship protection
```

## 30. Learned / configurable / unfrozen

A131 freezes the specification mechanism, not arbitrary numerical trading parameters.

Potential learned quantities include:

```text
normalization parameters
volatility estimators
calibration parameters
model coefficients
thresholds derived from historical distributions
```

These remain unfrozen until walk-forward research establishes them.

Potential configuration includes:

```text
window lengths
minimum history
quality thresholds
sampling frequency
universe definitions
feature enablement
```

These are versioned configuration, not hidden constants.

## 31. Hostile review

The feature contract must reject or expose:

```text
look-ahead through rolling windows
future normalization statistics
current universe applied historically
current contract metadata applied historically
future option-chain data
LTP substituted for required executable quote
bar-close leakage
recursive feature initialization leakage
circular feature dependencies
future position/execution state
silent missing-value imputation
unit mismatch
NaN/Inf propagation
in-sample parameter selection
multiple-testing inflation
survivorship bias
formula-version drift
research/live semantic divergence
```

## 32. Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- canonical feature identity
- mathematical-definition requirement
- causal dependency model
- dependency DAG
- temporal/window semantics
- dimensional/unit contract
- normalization provenance
- option feature contract
- recursive feature contract
- state dependency boundary
- numerical-domain failure semantics
- quality propagation
- consumer ownership
- research/live semantic equivalence
- multiple-testing provenance
- survivorship protection

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- concrete historical corporate-action provider
- concrete historical universe-membership provider
- concrete historical Greek/IV provider or calculation implementation

These external sources are not invented and do not prevent defining the feature mathematics contract.

CONFIGURATION TO VALIDATE:
- individual feature windows
- minimum history requirements
- numerical tolerances
- quality acceptance thresholds
- universe definitions

LEARNED PARAMETERS:
None frozen by A131.
All empirical parameters require walk-forward validation and explicit promotion.

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A132 — Canonical Edge / Probability Output Contract
```
