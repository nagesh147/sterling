# A132 — Canonical Edge and Probability Output Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.0  
**Depends on:** A129 Canonical Market Data Normalization and Temporal Integrity; A130 Canonical Feature and State Snapshot; A131 Canonical Feature Mathematics and Dependency Contract.

## 1. Purpose

A132 defines the boundary between causal feature/state evidence and probabilistic/edge evidence consumed by economics, lifecycle and decision logic.

It answers:

```text
Given exactly what was causally available at time t,
what probability distribution and uncertainty does the statistical layer
assert, what economic edge does it imply, and how is that assertion versioned?
```

A132 does **not** decide whether to trade. It produces evidence for downstream decision/economic contracts.

Existing Adaptive Edge probability work defines a three-state probability concept (`UP`, `DOWN`, `NEUTRAL`), Bayesian/hierarchical estimation, uncertainty, evidence strength and calibration. A132 makes the interface to that machinery canonical without freezing arbitrary numerical parameters.

## 2. Boundary

```text
A130 Snapshot
     |
     v
A131 Features
     |
     v
A132 Probability / Edge Evidence
     |
     +--> Economics
     +--> Lifecycle / Horizon
     +--> Risk
     |
     v
Decision
```

Forbidden:

```text
Probability -> order directly
Probability -> position mutation directly
Edge -> broker command directly
```

## 3. Canonical output object

A probability/edge result contains, at minimum:

```text
edge_output_id
snapshot_id
instrument_id
observation_time
available_at
outcome_schema_id
outcome_schema_version
estimator_id
estimator_version
calibration_id?
calibration_version?
probability_distribution
probability_uncertainty
conservative_probability?
evidence_strength
reference_population_id
training_boundary
feature_schema_version
formula_registry_version
configuration_version
model_artifact_id?
quality_status
created_at
```

The output is immutable.

A later recalculation produces a new output ID/version; it never mutates the historical result used by a prior decision.

## 4. Probability state

The initial canonical directional outcome space is:

```text
UP
DOWN
NEUTRAL
```

The probability vector is:

```text
P_t = (p_up, p_down, p_neutral)
```

with:

```text
p_up >= 0
p_down >= 0
p_neutral >= 0
p_up + p_down + p_neutral = 1
```

within an explicitly versioned numerical tolerance.

The tolerance is an implementation/validation parameter, not a trading parameter.

## 5. Probability is not a trade signal

```text
P(UP) high
```

does not imply:

```text
BUY
```

Likewise:

```text
P(DOWN) high
```

does not imply:

```text
SELL
```

The probability layer describes expected outcome likelihood under its declared outcome definition.

Trading requires additional economic and lifecycle conditions.

## 6. Outcome contract

Every probability distribution references an explicit outcome definition:

```text
outcome_schema_id
outcome_schema_version
observation_horizon
label_definition
neutral_definition
price_basis
instrument_basis
```

The outcome definition must specify whether the probability concerns:

```text
price direction
return class
barrier outcome
option economic outcome
other explicitly defined outcome
```

No consumer may reinterpret a probability under a different outcome definition.

## 7. Direction versus economics

A132 separates:

```text
DirectionalProbability
```

from:

```text
EconomicOutcomeDistribution
```

A directional probability may be useful while having negative economic expectancy after:

```text
spread
slippage
fees
option decay
financing/carry
execution uncertainty
```

Therefore:

```text
probability != expected P&L
edge != probability
```

## 8. Edge definition

For a defined action `a`, outcome state `Y`, and economic payoff function `G`:

```text
Edge(a,t)
=
E[G(a,Y,t) | information available at t]
```

The payoff function must reference a separate canonical economics/execution contract.

A132 therefore does not invent brokerage, slippage, option decay, stop-loss, target, or fill assumptions.

## 9. Net economic edge

Where the economics contract defines explicit costs:

```text
NetEdge
=
ExpectedGrossBenefit
-
ExpectedExecutionCost
-
ExpectedOtherCosts
```

Every term must be provenance-linked.

If a required cost is unknown:

```text
NetEdge = UNAVAILABLE
```

not an optimistic zero-cost assumption.

## 10. Probability uncertainty

A probability output must distinguish:

```text
point estimate
```

from:

```text
uncertainty around the estimate
```

The canonical statistical representation may retain a posterior distribution or equivalent uncertainty representation.

A point probability without uncertainty is insufficient when the estimator contract requires uncertainty.

## 11. Conservative probability

A downstream risk/economic consumer may use a conservative probability derived from the declared uncertainty representation:

```text
p_conservative
=
Q_q(P | evidence)
```

where `q` is configuration/validation controlled.

No quantile value is frozen here.

## 12. Evidence strength

`evidence_strength` is distinct from probability.

It describes the amount and quality of evidence supporting the estimate.

It may incorporate:

```text
effective sample size
similarity/state density
data quality
temporal independence
regime consistency
calibration quality
```

The exact composition must be versioned by the estimator contract.

## 13. Reference population

The result must identify the historical/reference population used by the estimator:

```text
reference_population_id
training_boundary
population_definition
eligibility_rules_version
```

For a decision at time `t`:

```text
all training/reference observations
must satisfy causal availability <= t
```

No future observation may enter the reference population.

## 14. Training, calibration and evaluation separation

A probability estimator must distinguish:

```text
estimation/training population
calibration population
validation population
final test population
```

A sample used to fit the raw probability estimator must not also be used as an unbiased calibration/evaluation sample without an explicit nested/resampling protocol.

Chronological boundaries are mandatory for temporal market data.

## 15. Calibration

Calibration transforms a raw probability distribution into a calibrated distribution only under a separately versioned calibration artifact:

```text
RawProbability
      |
      v
CalibrationModel
      |
      v
CalibratedProbability
```

Calibration must preserve the multiclass simplex:

```text
p_up + p_down + p_neutral = 1
```

Candidate calibration methods may include simple statistical methods such as isotonic or logistic calibration where empirically appropriate. The method is not frozen until walk-forward validation demonstrates that it improves calibration without unacceptable degradation elsewhere.

## 16. Calibration validity

A calibrated probability is valid only with:

```text
calibration_id
calibration_version
calibration_training_boundary
calibration_evaluation_boundary
calibration_population_definition
```

A calibration artifact must not be trained using future observations relative to the decision being replayed.

## 17. Model/estimator versioning

Every probability result identifies:

```text
estimator_id
estimator_version
feature_schema_version
formula_registry_version
configuration_version
```

If the estimator changes, historical probability outputs remain immutable.

## 18. Quality state

Canonical result quality:

```text
VALID
DEGRADED
UNAVAILABLE
INVALID
CAUSALLY_UNAVAILABLE
UNCERTAIN
```

`VALID` means the estimator's declared input and statistical validity requirements are satisfied.

It does not mean that the probability is profitable.

## 19. Failure behavior

Probability output must be unavailable or degraded when:

```text
required feature unavailable
causal boundary violated
instrument identity unresolved
reference population invalid
insufficient evidence under the estimator contract
model/calibration version unavailable
probability normalization fails
required economic input unavailable
model artifact integrity fails
```

The system must not substitute:

```text
0.5
previous probability
uniform distribution
latest available model
```

unless an explicit, versioned fallback policy exists.

## 20. Edge availability

The following are distinct states:

```text
PROBABILITY_AVAILABLE
ECONOMICS_AVAILABLE
EDGE_AVAILABLE
DECISION_ELIGIBLE
```

For example:

```text
probability available
but execution cost unavailable
```

means:

```text
probability = valid
edge = unavailable
```

It does not imply zero cost.

## 21. Probability/economics interface

A downstream economic consumer receives:

```text
probability_distribution
uncertainty
reference population
outcome definition
execution/economic assumptions references
```

It must not reconstruct the probability from raw features.

Likewise, the probability engine must not reconstruct broker costs from provider data unless explicitly part of its contract.

## 22. No circular dependency

Forbidden:

```text
Probability -> Edge -> Probability
```

The dependency direction is:

```text
Features
  -> Probability
  -> Economics
  -> Decision
```

If economics feeds a probability model as a feature, that dependency must be explicit and causally available before the probability timestamp; the economic result produced by the same decision cycle cannot be used recursively.

## 23. Options

For options, probability must preserve the underlying/contract identity from A128.

Directional probability on the underlying is not automatically equivalent to option profitability.

Option economics require explicit modeling of:

```text
option contract
entry economics
exit economics
spread
liquidity
implied volatility / Greek inputs where used
expiry
execution uncertainty
fees/taxes
```

Unknown inputs produce an unavailable or uncertain economic result rather than an invented estimate.

## 24. Learned parameters

A132 introduces no frozen trading thresholds.

Potential learned quantities include:

```text
feature weights
neighborhood selection
prior strength
hierarchical shrinkage parameters
calibration parameters
uncertainty transformation
conservative quantile
```

Each must be learned only through the canonical walk-forward process and must declare:

```text
population
label
observation horizon
label maturity
training boundary
validation boundary
test boundary
update cadence
promotion rule
rollback rule
```

## 25. Statistical validation requirements

A probability/edge model is not accepted merely because:

```text
accuracy > baseline
```

Validation must separately examine:

```text
calibration
proper scoring rules
discrimination where relevant
stability across time
stability across regimes
effective sample size
selection bias
multiple testing
parameter sensitivity
transaction-cost sensitivity
out-of-sample economic value
```

Exact acceptance thresholds remain unfrozen until the experimental design establishes them.

## 26. Multiple-testing control

If multiple feature sets, estimators, horizons, thresholds or calibration methods are evaluated, the final reported result must preserve the experiment/search lineage.

The system must not treat the best backtest among many undisclosed trials as an unbiased estimate.

Required provenance includes:

```text
experiment_id
candidate_set
selection_rule
search_boundary
validation results
final test result
```

## 27. Reproducibility

Given identical:

```text
snapshot
feature/formula versions
estimator version
calibration version
reference population
configuration
```

the probability/edge output must be reproducible.

## 28. Causal lineage

Canonical lineage becomes:

```text
raw data
 -> canonical event
 -> causal snapshot
 -> feature
 -> probability estimate
 -> calibration
 -> economic distribution
 -> edge
 -> decision
 -> execution
 -> outcome
 -> label
 -> learning
```

No downstream outcome may alter the probability that existed before the outcome occurred.

## 29. Hostile review

The contract must reject or expose:

```text
future training observations
future calibration observations
future normalization parameters
using test data for model selection
using calibration data as an undisclosed training population
survivorship-biased reference population
random temporal splitting
probability interpreted as profitability
zero-cost fallback
LTP-based option economics without executable-price evidence
circular probability/economics dependency
stale model artifact
unversioned calibration
sparse-state overconfidence
multiple-testing winner's curse
```

## 30. Frozen architecture

```text
probability is an evidence output, not an order
probability has an explicit outcome definition
UP/DOWN/NEUTRAL simplex is explicit
probability is separated from economics
edge is expected economic value under an explicit payoff contract
uncertainty is first-class
reference population is first-class
training/calibration/evaluation boundaries are explicit
calibration is separately versioned
model/estimator versions are immutable
quality/failure states are explicit
no silent probability fallback
no circular probability/economics dependency
full causal lineage is retained
```

## 31. Unfrozen parameters

```text
outcome classification boundaries
observation horizons
prior/hierarchical strength
similarity metric and feature weights
neighborhood selection
uncertainty estimator
calibration method
calibration hyperparameters
conservative quantile
acceptance thresholds
```

None may be frozen from intuition or selected solely for in-sample performance.

## 32. External dependencies

| Dependency | Owner | Consumer | Failure |
|---|---|---|---|
| Causal snapshot | A130 | estimator | unavailable |
| Feature mathematics | A131 | estimator | invalid |
| Outcome/label definition | label contract | estimator | unavailable |
| Historical population | research-data contract | estimator | unavailable/biased |
| Calibration population | experiment contract | calibration | calibration invalid |
| Economic payoff | economics contract | edge | edge unavailable |
| Execution assumptions | execution/economics contracts | edge | uncertain |
| Model artifact registry | model authority | estimator | version unavailable |

## 33. Architecture status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- probability/edge output boundary
- probability vs trade decision separation
- explicit outcome schema
- three-state directional simplex
- directional/economic separation
- uncertainty as first-class output
- evidence strength as distinct from probability
- reference-population lineage
- chronological training/calibration separation
- calibration versioning
- estimator/model versioning
- explicit failure states
- no silent statistical fallback
- causal lineage
- multiple-testing provenance
- no circular probability/economics dependency

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
None that blocks this contract. Specific data providers, model implementations and economic formulas are governed by their respective contracts and must be resolved before the affected capability is enabled.

LEARNED / VALIDATION-DEPENDENT:
- outcome thresholds
- estimator structure
- prior strength
- neighborhood/weighting method
- calibration method
- uncertainty method
- conservative probability policy
- statistical/economic acceptance thresholds

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A133 — Canonical Economic Value, Cost, and Decision Utility Contract
```
