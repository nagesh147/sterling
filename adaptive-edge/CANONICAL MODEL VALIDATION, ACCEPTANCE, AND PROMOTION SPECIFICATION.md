# CANONICAL MODEL VALIDATION, ACCEPTANCE, AND PROMOTION SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines the formal process by which a strategy version progresses through:

```text
Research
   ↓
Validated Research Candidate
   ↓
Paper Trading Candidate
   ↓
Paper Trading
   ↓
Live Candidate
   ↓
Production
```

It also defines when a model must be:

```text
Rejected
Frozen
Reverted
Retired
```

The promotion system is deliberately harder than the model-fitting system.

A model does not become valid because it makes money in a backtest.

---

# 2. Fundamental Principle

Promotion requires simultaneous evidence across:

```text
Data Integrity
Statistical Validity
Calibration
Economic Edge
Execution Robustness
Risk Behavior
Temporal Stability
Regime Robustness
Adversarial Robustness
Operational Integrity
```

Failure of a mandatory category blocks promotion.

---

# 3. Validation Hierarchy

The canonical hierarchy is:

```text
Level 0
Data Validity

Level 1
Mathematical / Implementation Validity

Level 2
Statistical Validity

Level 3
Economic Validity

Level 4
Execution Validity

Level 5
Risk Validity

Level 6
Walk-Forward Robustness

Level 7
Adversarial Robustness

Level 8
Paper Trading Validation

Level 9
Production Promotion
```

A model cannot skip a level.

---

# 4. Research Candidate

A candidate begins as:

```text STATUS = RESEARCH
```

It may be modified freely during exploratory research.

However:

```text exploratory results
```

cannot be represented as unbiased validation evidence.

---

# 5. Candidate Freeze

Before formal validation begins, the candidate is frozen.

The frozen package includes:

```text FeatureDefinitionVersion
LabelDefinitionVersion
StatisticalModelVersion
EconomicModelVersion
RiskPolicyVersion
ExecutionModelVersion
ManagementPolicyVersion
AccountingVersion
ParameterVersion
```

---

# 6. Validation Dataset Separation

The canonical data separation is:

```text Training
    ↓
Validation
    ↓
Test
    ↓
Final Holdout
```

The final holdout remains inaccessible to iterative model selection.

---

# 7. Training Window

The training window is used to estimate:

```text learned parameters
distributions
probabilities
calibration
```

subject to the relevant model specification.

---

# 8. Validation Window

The validation window is used to determine:

```text parameter choices
model variants
thresholds
architecture selection
```

during the research process.

Repeated use of the same validation period increases selection bias.

---

# 9. Test Window

The test window evaluates the frozen candidate after research decisions have been completed.

The test window is not repeatedly inspected to improve the candidate.

---

# 10. Final Holdout

The final holdout is reserved for the final confirmation.

Once the candidate enters final validation:

```text FinalHoldout = LOCKED.
```

No parameter changes are permitted based on its results.

---

# 11. Walk-Forward Principle

The primary evaluation mechanism is chronological walk-forward evaluation.

Conceptually:

```text Train_1 → Test_1
Train_2 → Test_2
Train_3 → Test_3
...
Train_n → Test_n
```

Future observations are never available to earlier training periods.

---

# 12. Expanding Versus Rolling Windows

The architecture supports:

```text Expanding Window
```

and:

```text Rolling Window.
```

The selection must be defined before formal evaluation.

Changing window methodology after seeing results constitutes a new experiment.

---

# 13. Parameter Re-estimation

Only parameters explicitly classified as:

```text LEARNABLE
```

may change between walk-forward windows.

Frozen architectural parameters remain unchanged.

---

# 14. Parameter Classes

Every parameter belongs to one of:

```text ARCHITECTURAL
LEARNED
CALIBRATED
EXECUTION
RISK
OPERATIONAL
EXTERNAL-CONTRACT
```

Each class has different update rules.

---

# 15. Architectural Parameters

Architectural parameters define:

```text state definitions
event semantics
dependency relationships
state transitions
```

They are not continuously optimized.

A structural change creates a new model version.

---

# 16. Learned Parameters

Examples include:

```text probability thresholds
quantiles
state sensitivities
continuation thresholds
reversal thresholds
```

These may be estimated through the declared walk-forward procedure.

---

# 17. Calibration Parameters

Calibration parameters are learned separately according to the statistical calibration specification.

They cannot use future outcomes from the evaluation period.

---

# 18. Execution Parameters

Execution parameters include:

```text slippage model
latency assumptions
fill model
cost model
```

They are validated independently.

A favorable trading result cannot justify an unrealistically favorable execution assumption.

---

# 19. Risk Parameters

Risk parameters include:

```text maximum risk
position limits
loss limits
protection parameters.
```

Risk parameters must be validated separately from predictive parameters.

---

# 20. Validation Principle

The correct question is not:

```text "Did the strategy make money?" id="8zq9yb"
```

The correct question is:

```text "Does the strategy demonstrate repeatable economic value
under causally valid,
cost-aware,
risk-constrained,
out-of-sample conditions?" id="l4v8zj"
```

---

# 21. Data Integrity Gate

Before any statistical evaluation:

```text DATA_VALIDITY = PASS
```

is required.

The system checks:

```text timestamp integrity
missing data
duplicate events
ordering
instrument identity
contract identity
corporate adjustments where relevant
```

---

# 22. Leakage Gate

The candidate fails immediately if any feature, label, calibration process, execution model, or parameter selection uses future information.

Therefore:

```text LeakageDetected = TRUE
```

produces:

```text REJECT.
```

---

# 23. Causal Replay Test

Historical replay must verify that every decision at time `t` can be reconstructed using:

```text information available <= t.
```

This is a hard requirement.

---

# 24. Statistical Validity Gate

The statistical model must demonstrate:

```text sufficient evidence
reasonable calibration
stable estimation
```

where applicable.

Failure results in:

```text STATISTICALLY_INVALID.
```

---

# 25. Calibration Gate

Calibration is evaluated independently from directional discrimination.

The candidate must demonstrate acceptable:

```text probability reliability
calibration error
Brier/log-loss behavior
```

under the declared validation protocol.

The exact thresholds remain:

```text UNFROZEN.
```

---

# 26. Economic Validity Gate

The strategy must demonstrate:

```text positive net economic value
```

after:

```text realistic execution costs
```

and:

```text applicable risk constraints.
```

Gross theoretical profitability is insufficient.

---

# 27. Cost Robustness Gate

The candidate must survive reasonable deterioration in:

```text spread
slippage
latency
fill conditions.
```

The exact stress multipliers remain unfrozen.

---

# 28. Risk Validity Gate

The candidate must demonstrate that:

```text realized risk
```

remains consistent with:

```text authorized risk
```

under normal and adverse conditions.

A profitable strategy with uncontrolled risk fails.

---

# 29. Drawdown Gate

The evaluation must measure:

```text MaximumDrawdown
DrawdownDuration
RecoveryDuration
TailLoss
ConsecutiveLosses
```

A candidate can fail despite positive expectancy if its downside behavior violates the risk policy.

---

# 30. Walk-Forward Consistency

The candidate must not depend on one historical period.

Evidence must be distributed across multiple chronological evaluation windows.

The exact acceptance threshold remains unfrozen.

---

# 31. Fold-Level Evaluation

Each walk-forward fold produces:

```text FoldResult {
    expectancy
    net_pnl
    drawdown
    win_rate
    profit_factor
    calibration
    execution_cost
    trade_count
}
```

The aggregate result alone is insufficient.

---

# 32. Fold Failure

A fold may fail because of:

```text negative expectancy
execution collapse
calibration failure
risk violation
insufficient evidence
```

The candidate must report the failure rather than hiding it inside aggregate statistics.

---

# 33. Consistency Versus Uniformity

The strategy does not require every fold to have identical performance.

Markets are nonstationary.

The requirement is:

```text absence of catastrophic instability
+
reasonable persistence of economic value.
```

---

# 34. Regime Robustness

The candidate must be evaluated across relevant market conditions.

Examples:

```text low volatility
normal volatility
high volatility
strong trend
weak trend
rapid reversal
opening instability
```

The exact regime taxonomy comes from the canonical state specification.

---

# 35. Regime Failure

If the strategy works only in one narrow regime and fails catastrophically elsewhere:

```text ROBUSTNESS_FAILURE.
```

It cannot be promoted merely because the dominant historical regime was profitable.

---

# 36. Adversarial Validation

The strategy must be deliberately attacked using scenarios such as:

```text sudden volatility expansion
false breakout
rapid reversal
spread explosion
liquidity collapse
delayed data
missing quotes
partial fills
large gap
option premium collapse
```

---

# 37. Adversarial Principle

The purpose is not to prove that the strategy never loses.

The purpose is to determine whether:

```text losses remain inside the designed failure envelope.
```

---

# 38. State-Machine Integrity

Every reachable state must satisfy:

```text valid predecessor
valid transition
valid inputs
valid invariants.
```

An impossible state is an implementation/specification failure.

---

# 39. Transition Coverage

The formal validation suite must cover:

```text every normal transition
every exit transition
every emergency transition
every failure transition
every recovery transition.
```

---

# 40. Impossible-State Testing

Examples include:

```text position exists without fill
exit occurs before entry
risk authorization exceeds account limit
negative quantity
protection becomes less conservative
trade enters after session lockout
```

Any such state is a hard failure.

---

# 41. Risk Monotonicity Test

The validation system must verify:

```text mode change
probability change
profit increase
```

cannot accidentally increase:

```text AuthorizedRisk.
```

This explicitly preserves the architectural rule established earlier.

---

# 42. Parameter Sensitivity

For each learned parameter:

```text θ
```

evaluate nearby values:

```text θ - δ
θ
θ + δ.
```

The strategy should not depend on an implausibly narrow numerical optimum.

---

# 43. Parameter Stability

A parameter is suspicious if:

```text tiny parameter change
```

produces:

```text enormous performance change.
```

Such a parameter requires additional investigation.

---

# 44. Parameter Distribution Across Folds

For learned parameter `θ`:

```text θ_1, θ_2, ..., θ_n
```

are recorded across walk-forward folds.

The system evaluates:

```text central tendency
dispersion
temporal drift
```

rather than selecting a single globally optimized number.

---

# 45. Multiple Testing

Every materially evaluated candidate must be recorded.

The research ledger contains:

```text CandidateID
Hypothesis
Parameters
EvaluationPeriod
Result
ReasonAccepted/Rejected
```

This prevents selective reporting.

---

# 46. Researcher Degrees of Freedom

The validation process must explicitly recognize that repeatedly changing:

```text feature
threshold
quantile
label horizon
risk parameter
execution assumption
```

until performance improves creates selection bias.

Each materially changed hypothesis is a new candidate.

---

# 47. Complexity Penalty

If two candidates have comparable out-of-sample performance:

```text simpler candidate wins.
```

Complexity must provide measurable incremental evidence.

---

# 48. Baseline Comparison

The candidate must be compared against relevant simple baselines.

Examples:

```text unconditional direction
simple directional breakout
simple fixed-risk baseline
randomized/no-signal baseline where appropriate.
```

A sophisticated architecture that cannot outperform simple baselines has not justified its complexity.

---

# 49. Incremental Value

Every additional layer should answer:

```text What information does this layer add?
```

and:

```text Does it improve out-of-sample economics?
```

If not:

```text remove it.
```

---

# 50. Ablation Testing

The system should evaluate:

```text FullModel
    versus
FullModel - ComponentA
    versus
FullModel - ComponentB
    ...
```

This identifies whether individual components actually contribute.

---

# 51. Ablation Failure

If a component adds complexity but produces no robust incremental value:

```text ComponentStatus = REMOVE.
```

The component does not remain merely because it sounds theoretically useful.

---

# 52. Execution Ablation

The strategy must separately determine whether profitability depends on:

```text unrealistic execution assumptions.
```

If performance disappears when moving from optimistic to realistic execution:

```text execution robustness failure.
```

---

# 53. Risk Ablation

The strategy must also be tested under:

```text conservative risk constraints.
```

If profitability exists only under excessive exposure:

```text risk robustness failure.
```

---

# 54. Out-of-Sample Economic Threshold

The canonical economic criterion is conceptually:

```text LowerBound(ExpectedNetEconomicValue)
>
MinimumRequiredEconomicEdge.
```

The exact statistical construction remains:

```text UNFROZEN.
```

---

# 55. Why Lower Bounds

A point estimate such as:

```text ExpectedNetValue = +₹100 id="6dyc2v"
```

does not prove that the true value is positive.

The validation framework therefore emphasizes uncertainty.

---

# 56. Trade Count

Performance must be interpreted relative to:

```text effective number of independent opportunities.
```

A large number of highly correlated trades does not automatically constitute strong evidence.

---

# 57. Temporal Dependence

The validation framework must account for:

```text serial correlation
clustered outcomes
regime persistence.
```

Naïve IID assumptions are not automatically accepted.

---

# 58. Bootstrap / Resampling

Where resampling is required, the methodology must preserve relevant temporal dependence.

The exact procedure remains unfrozen.

---

# 59. Final Holdout Protocol

Before opening the final holdout:

```text Model = FROZEN.
```

Then:

```text evaluate once
```

or under a strictly predefined limited protocol.

No tuning follows from the result.

---

# 60. Holdout Success

A successful final holdout confirms:

```text the frozen candidate's performance
```

under previously unseen data.

It does not authorize arbitrary changes.

---

# 61. Holdout Failure

If the final holdout fails:

```text candidate is not promoted.
```

The researcher must return to:

```text RESEARCH
```

and create a new version.

The failed candidate remains preserved.

---

# 62. No Holdout Recycling

The same final holdout cannot repeatedly become:

```text training data
validation data
test data
holdout data
```

whenever convenient.

Any such change requires a new evaluation protocol.

---

# 63. Paper Trading Gate

A candidate that passes historical validation becomes:

```text PAPER_CANDIDATE.
```

It is not yet live.

---

# 64. Paper Trading Purpose

Paper trading evaluates:

```text live data integrity
real-time state transitions
execution assumptions
latency
operational reliability
```

It is not primarily another opportunity to optimize the strategy.

---

# 65. Paper Trading Model Freeze

During formal paper validation:

```text model parameters remain frozen.
```

Otherwise paper trading becomes another training dataset.

---

# 66. Paper Trading Comparison

The system compares:

```text expected execution
versus
observed market/execution conditions
```

and:

```text simulated decision
versus
real-time decision.
```

---

# 67. Paper Trading Failure

Failure may include:

```text unexpected latency
data mismatch
state-machine failure
execution-cost underestimation
risk mismatch
operational errors.
```

Any mandatory failure blocks production promotion.

---

# 68. Live Candidate

Only after historical and paper validation:

```text STATUS = LIVE_CANDIDATE.
```

The candidate still operates under:

```text restricted production risk.
```

---

# 69. Production Ramp

The initial live phase should use a predefined conservative risk budget.

Risk cannot increase because the first few trades are profitable.

---

# 70. Live Promotion

Full production risk requires evidence that:

```text live behavior
```

is consistent with:

```text validated assumptions.
```

The exact live promotion threshold remains unfrozen.

---

# 71. Production Monitoring

Production monitoring must continuously inspect:

```text data quality
prediction calibration
execution cost
slippage
risk
drawdown
state transitions
model drift.
```

---

# 72. Drift Detection

If production behavior deviates materially from validated behavior:

```text monitoring event
```

is generated.

Drift does not automatically imply retraining.

---

# 73. Production Failure Modes

The system distinguishes:

```text DATA_FAILURE
MODEL_FAILURE
EXECUTION_FAILURE
RISK_FAILURE
ACCOUNTING_FAILURE
OPERATIONAL_FAILURE
```

These must not be collapsed into generic:

```text strategy loss.
```

---

# 74. Automatic Safety Response

Certain failures should produce:

```text FAIL_CLOSED.
```

Examples:

```text risk reconciliation failure
invalid position
corrupted market data
unknown instrument
impossible state
loss-control violation.
```

---

# 75. Strategy Suspension

If a mandatory production invariant fails:

```text StrategyStatus = SUSPENDED.
```

New entries stop.

Existing positions remain under the safety/exit policy.

---

# 76. Re-Promotion

A suspended strategy cannot simply resume because the next trade looks attractive.

It requires:

```text failure diagnosis
correction
validation
re-approval.
```

---

# 77. Model Versioning

Every materially changed candidate receives:

```text new ModelVersion.
```

No silent mutation of a production model is permitted.

---

# 78. Promotion Record

A promotion decision contains:

```text ModelVersion
ValidationDatasetVersion
ExecutionModelVersion
RiskPolicyVersion
AccountingVersion
ValidationReport
KnownLimitations
PromotionDecision
Approver/ProcessRecord
Timestamp
```

---

# 79. Rejection Record

Every rejected candidate retains:

```text CandidateID
ReasonForRejection
FailedTests
EvaluationResults
ParameterVersion
```

Rejected models are not deleted.

They become part of the research history.

---

# 80. Acceptance Matrix

Conceptually:

```text id="3d7h1v"
                         PASS REQUIRED
Data Integrity               YES
Leakage Tests                YES
Statistical Validity        YES
Calibration                  YES*
Economic Edge                YES
Execution Robustness        YES
Risk Validity                YES
Walk-Forward Stability      YES
Regime Robustness            YES*
Adversarial Tests            YES
State-Machine Integrity      YES
Final Holdout                YES
Paper Trading                YES
Operational Integrity        YES
```

`*` Exact applicability depends on the component being evaluated.

---

# 81. Hard Failure Versus Soft Failure

Hard failures:

```text future leakage
risk breach
accounting inconsistency
impossible state
invalid execution reconstruction
final-holdout failure
```

immediately block promotion.

Soft failures require explicit review:

```text moderate calibration degradation
regime-specific weakness
parameter drift
execution-cost uncertainty.
```

---

# 82. Promotion Is Not a Single Metric

No combination such as:

```text Sharpe > X
```

or:

```text WinRate > X
```

is sufficient by itself.

Promotion is a conjunction of independent requirements.

---

# 83. Production Safety Dominates Performance

If:

```text Performance = excellent
```

but:

```text Risk Integrity = failed,
```

the model is rejected.

Likewise:

```text EconomicEdge = excellent
```

does not override:

```text ExecutionIntegrity = failed.
```

---

# 84. Validation State Machine

The canonical lifecycle is:

```text RESEARCH
   ↓
FROZEN_CANDIDATE
   ↓
HISTORICAL_VALIDATION
   ↓
PAPER_CANDIDATE
   ↓
PAPER_VALIDATION
   ↓
LIVE_CANDIDATE
   ↓
CONTROLLED_LIVE
   ↓
PRODUCTION
```

Failure transitions:

```text REJECTED
SUSPENDED
RETIRED
```

---

# 85. Promotion Invariants

```text VAL-001 id="9q9cwj"
No candidate may skip a mandatory validation stage.

VAL-002
Future data cannot influence model selection.

VAL-003
Final holdout data cannot influence parameter selection.

VAL-004
Every materially evaluated candidate is recorded.

VAL-005
Failed candidates remain immutable historical records.

VAL-006
A single performance metric cannot authorize promotion.

VAL-007
Risk failure blocks promotion regardless of profitability.

VAL-008
Execution failure blocks promotion when execution materially affects economics.

VAL-009
A model change creates a new version.

VAL-010
Paper trading cannot silently become training data during formal validation.

VAL-011
Production models are immutable.

VAL-012
Production failures trigger the defined safety state.

VAL-013
Re-promotion requires validation after material corrective changes.

VAL-014
Complexity must demonstrate incremental out-of-sample value.

VAL-015
Performance must survive realistic costs.

VAL-016
Walk-forward performance is evaluated chronologically.

VAL-017
Adversarial scenarios are part of validation.

VAL-018
Impossible states constitute specification/implementation failure.
```

---

# 86. Numerical Acceptance Parameters Still Unfrozen

We deliberately do not choose:

```text minimum expectancy
minimum trade count
maximum drawdown
maximum drawdown duration
minimum calibration quality
minimum walk-forward pass rate
maximum parameter dispersion
minimum regime robustness
execution deterioration tolerance
paper-trading duration
live-ramp duration
production promotion threshold.
```

These must be determined through the research protocol rather than invented.

---

# 87. Canonical Promotion Principle

The final decision is:

```text PROMOTE
```

only when:

```text Mathematical Integrity
AND
Data Integrity
AND
Statistical Validity
AND
Economic Validity
AND
Execution Validity
AND
Risk Validity
AND
Temporal Robustness
AND
Adversarial Robustness
AND
Operational Validity
```

all satisfy their respective acceptance contracts.

Otherwise:

```text DO NOT PROMOTE.
```

---

# 88. Current Architecture Status

```text Mathematical Specification              COMPLETE
Variable Registry                          COMPLETE
Dependency Graph                           COMPLETE
State Transition Specification              COMPLETE
Historical Label Specification              COMPLETE
Statistical Estimation Specification       COMPLETE
Economic Decision Specification             COMPLETE
Option Selection Specification              COMPLETE
Risk Budget Specification                   COMPLETE
Position Sizing Specification               COMPLETE
Execution Specification                     COMPLETE
P&L / Accounting Specification              COMPLETE
Performance Attribution                     COMPLETE
Model Validation Specification              COMPLETE
Promotion / Rejection Specification         COMPLETE
```

The architecture is now **specification-complete at the major system-boundary level**.

The remaining work is increasingly about making the specification executable and filling the deliberately unfrozen quantities with evidence.

---

# 89. Next Artifact

The next logical artifact is the:

# CANONICAL RESEARCH EXPERIMENT AND VERSION-CONTROL SPECIFICATION

This will define how we conduct the actual research without contaminating it.

It will formalize:

```text hypothesis
experiment ID
candidate creation
parameter provenance
dataset snapshot
walk-forward run
baseline comparison
ablation
multiple-testing ledger
result storage
reproducibility
model versioning
promotion evidence
```

This is the artifact that prevents us from accidentally turning the research process itself into an uncontrolled source of overfitting.