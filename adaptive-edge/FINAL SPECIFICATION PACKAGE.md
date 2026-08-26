# FINAL SPECIFICATION PACKAGE

Version 1.0

## ARTIFACT ONE — CANONICAL EVENT MODEL AND DETERMINISTIC STATE MACHINE

### 1. Purpose

The state machine converts an ordered stream of canonical events into deterministic market state.

```text
State_t + Event_t
        ↓
State_(t+1)
```

The same inputs, versions, and configuration must always produce the same resulting state.

### 2. State Ownership

Only the State Engine may create a new canonical `MarketState`.

No prediction, risk, accounting, execution, or reporting component may mutate market state.

### 3. State Components

The state contains:

```text
SessionState
InstrumentState
OpeningRange
MarketRegime
VolatilityState
DirectionalState
LiquidityState
StateVersion
AsOfTime
```

Only components explicitly defined by the mathematical specification become canonical state.

### 4. Event Processing

Events are processed according to:

```text
event availability
→ event ordering
→ event validation
→ state transition
```

An event whose information was unavailable at the relevant historical point cannot be inserted retroactively into that state.

### 5. Idempotency

Processing the same canonical event twice must not create a second economic effect.

```text
process(E)
process(E)

≡

process(E)
```

The second occurrence is recognized through event identity.

### 6. Ordering

Ordering uses the authoritative source ordering contract.

The system must never reorder events merely because another ordering produces better trading results.

### 7. Session State

The state machine explicitly represents:

```text
PRE_OPEN
OPENING_RANGE
ACTIVE
CLOSING
CLOSED
HALTED
```

Only permitted transitions are accepted.

### 8. Opening Range

The opening range is constructed from events within the configured opening-range interval.

Once complete:

```text OpeningRangeHigh
OpeningRangeLow
OpeningRangeWidth
```

become immutable historical facts for that session.

### 9. Impossible Transitions

Examples:

```text CLOSED → OPEN without valid session transition
EXPIRED instrument → ACTIVE
future event → historical state
negative sequence → valid state
```

must fail.

### 10. State Replay

Given:

```text initial state
+
identical event stream
+
identical configuration
+
identical versions
```

the resulting state sequence must be identical.

### 11. State Tests

Required tests:

```text normal session
duplicate event
out-of-order event
missing event
market halt
market resume
opening-range completion
instrument expiry
session close
replay determinism
state corruption
future event injection
```

### 12. Exit Criterion

The state subsystem is accepted only when deterministic replay, transition invariants, idempotency, and adversarial tests all pass.

---

# ARTIFACT TWO — CANONICAL FEATURE SYSTEM

## 1. Purpose

The feature system converts causally available state into a versioned `FeatureSnapshot`.

```text
MarketState_t
      ↓
FeatureEngine
      ↓
FeatureSnapshot_t
```

### 2. Feature Definition

Every feature must specify:

```text FeatureID
mathematical definition
inputs
lookback
sampling frequency
availability rule
normalization
missing-data behavior
version
```

### 3. Feature Ownership

One feature has one authoritative implementation.

No backtester, research script, or strategy file may independently recalculate the same feature.

### 4. Causality

For a feature calculated at time `t`:

```text availability(input) <= t
```

must hold for every input.

### 5. Historical Windows

A lookback window must be explicitly defined.

For example:

```text [t - N, t]
```

is different from:

```text [t - N, t)
```

The boundary convention must be fixed.

### 6. Missing Data

Missing values must remain semantically distinguishable from zero.

Possible states:

```text VALID
PARTIAL
UNAVAILABLE
INVALID
```

### 7. Feature Snapshot

```text FeatureSnapshot {
    snapshotId
    asOfTime
    sourceStateId
    features
    featureVersion
    validity
}
```

### 8. Feature Versioning

Changing:

```text formula
lookback
normalization
source
availability
```

creates a new feature version.

### 9. Feature Leakage Tests

The validator must deliberately inject:

```text future candle
future high
future low
future volume
future spread
future label
future execution result
```

and verify that the feature engine rejects the dependency.

### 10. Feature Metamorphic Tests

Where mathematically appropriate:

```text future data added
→ historical feature unchanged

irrelevant instrument added
→ target feature unchanged

duplicate event
→ feature unchanged
```

### 11. Feature Exit Criterion

Every production feature must have:

```text unit test
causality test
boundary test
missing-data test
version
mathematical definition
```

before it enters the prediction path.

---

# ARTIFACT THREE — CANONICAL PREDICTION CONTRACT

## 1. Purpose

Prediction converts a feature snapshot into an immutable prediction.

```text FeatureSnapshot
       +
ModelVersion
       ↓
Prediction
```

### 2. Prediction Object

```text Prediction {
    predictionId
    opportunityId
    predictionTime
    featureSnapshotId
    modelVersion
    outputs
    uncertainty
    validity
}
```

### 3. Prediction Immutability

Once generated, a prediction cannot be modified.

A revised prediction receives a new identity.

### 4. Model Lineage

Every prediction identifies:

```text ModelVersion
FeatureVersion
SpecificationVersion
ParameterVersion
```

where applicable.

### 5. Determinism

For deterministic models:

```text same feature snapshot
+
same model version
=
same prediction
```

For stochastic models, randomness must be explicitly injected and seeded.

### 6. Prediction Is Not Authorization

This distinction is mandatory:

```text Prediction
    !=
EconomicEligibility
    !=
RiskAuthorization
    !=
Order
```

A high probability does not itself authorize a trade.

### 7. Prediction Uncertainty

Uncertainty must not be represented as an arbitrary confidence score unless its mathematical interpretation is defined.

### 8. Prediction Validation

Validate:

```text output range
model compatibility
feature compatibility
causal availability
version compatibility
determinism
```

### 9. Calibration

If probabilities are used, calibration is a separate validation concern.

A model output of:

```text p = 0.70
```

does not automatically mean seventy percent empirical frequency.

That relationship must be measured.

### 10. Prediction Exit Criterion

Prediction is accepted only when lineage, reproducibility, causality, and output validity are mechanically testable.

---

# ARTIFACT FOUR — CANONICAL ECONOMIC ENGINE AND OPTION SELECTION

## 1. Purpose

The economic engine determines whether a predicted opportunity has positive expected economic value after relevant costs.

```text Prediction
+
MarketState
+
Instrument
+
ExecutionEstimate
        ↓
EconomicEvaluation
```

### 2. Economic Components

The canonical evaluation contains:

```text ExpectedGrossValue
ExpectedExecutionCost
ExpectedNetValue
EconomicEligibility
```

### 3. Fundamental Relationship

Where defined:

```text ExpectedNetValue
=
ExpectedGrossValue
-
ExpectedExecutionCost
```

No downstream module may silently substitute gross value for net value.

### 4. Cost Components

Costs may include:

```text spread
slippage
fees
taxes
brokerage
latency cost
market impact
other explicitly modeled costs
```

Only costs actually included in the specification may be used.

### 5. Cost Monotonicity

Holding all else constant:

```text cost ↑
→ ExpectedNetValue cannot improve
```

If this property fails, the economic implementation is defective.

### 6. Economic Eligibility

The result is explicitly:

```text ELIGIBLE
INELIGIBLE
UNKNOWN
```

Unknown is not equivalent to eligible.

### 7. Option Candidate Generation

The option-selection system generates candidates satisfying:

```text instrument type
expiry
strike constraints
liquidity constraints
price availability
trading status
lot size
execution constraints
```

### 8. Option Scoring

Each candidate receives a versioned score according to the approved selection specification.

The selector must not use future option behavior.

### 9. Selection

```text CandidateSet
      ↓
Eligibility
      ↓
EconomicEvaluation
      ↓
SelectionScore
      ↓
SelectedInstrument
```

### 10. Selection Invariants

The selected contract must:

```text belong to candidate set
be valid
be active
satisfy constraints
have valid market information
```

### 11. Option Selection Is Not Risk

The selector answers:

```text Which instrument best satisfies the opportunity specification?
```

Risk answers:

```text How much exposure is authorized?
```

These remain separate.

### 12. Exit Criterion

Economic and option-selection components must pass:

```text cost sensitivity
candidate validity
expiry tests
liquidity tests
missing-data tests
future-information tests
deterministic selection tests
```

---

# ARTIFACT FIVE — CANONICAL RISK AND POSITION-SIZING SYSTEM

## 1. Purpose

Risk determines permitted exposure independently from predictive confidence.

```text EconomicEvaluation
+
RiskState
+
RiskPolicy
        ↓
RiskAuthorization
        ↓
PositionSizing
        ↓
AuthorizedQuantity
```

### 2. Risk Authorization

```text RiskAuthorization {
    authorizationId
    opportunityId
    authorizationTime
    authorizedRisk
    riskPerUnit
    riskStatus
    riskPolicyVersion
    expiry
}
```

### 3. Risk Is Independent

The following are not equivalent:

```text predictive strength
profitability
market regime
risk capacity
position size
```

Each has its own definition.

### 4. Critical Invariant

A previously authorized risk amount cannot be increased merely because:

```text P&L increased
PeakPnL increased
prediction improved
market mode changed
execution was favorable
partial position was closed
```

unless the approved risk policy explicitly defines such a transition.

### 5. Dynamic Mode Versus Dynamic Risk

This is explicitly frozen:

```text DynamicMode
    !=
DynamicRisk
```

A mode transition cannot implicitly grant additional risk.

### 6. Risk State

Risk state may include:

```text current exposure
remaining risk budget
drawdown state
halt state
loss state
session state
risk-policy version
```

### 7. Risk Authorization Immutability

Once issued:

```text RiskAuthorization
```

cannot be mutated.

A new authorization is a new object.

### 8. Position Sizing

Sizing converts authorization into executable quantity.

```text authorizedRisk
÷
riskPerUnit
=
rawQuantity
```

followed by:

```text lot constraint
position constraint
capital constraint
execution constraint
```

according to the canonical specification.

### 9. Quantity Safety

The resulting quantity must satisfy:

```text executableRisk <= authorizedRisk
quantity >= 0
quantity respects lot size
quantity respects position limits
```

### 10. Risk Attacks

The test suite must attempt:

```text profit → risk increase
prediction → risk increase
mode → risk increase
better fill → risk increase
partial exit → risk increase
lower cost → risk increase
```

and reject all unspecified transitions.

### 11. Risk Halt

A risk halt prevents new exposure according to the risk policy.

A valid signal cannot bypass the halt.

### 12. Risk Reset

A halt can clear only through an explicitly defined reset condition.

It cannot be implicitly cleared by:

```text profit
mode change
new signal
time passage
```

unless the policy explicitly says so.

### 13. Exit Criterion

Risk is accepted only when authorization, sizing, limits, halt behavior, reset behavior, and adversarial tests all pass.