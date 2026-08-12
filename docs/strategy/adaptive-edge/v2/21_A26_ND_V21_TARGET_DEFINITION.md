# Adaptive Edge V2.1 — New-Definition Target and Outcome Proposal

**Artifact:** A26-ND
**Version:** 2.1.0-proposed
**Status:** PROPOSED / RESEARCH-ONLY
**Implementation authorization:** RESEARCH ONLY; NO LIVE EXECUTION

## 1. Why this artifact exists

The original A26 correctly separates Opportunity, OutcomeObservation and Label but leaves the primary target and horizon unresolved. Repository recovery did not recover an authoritative numerical target. This artifact therefore creates a new, explicitly versioned research definition rather than silently modifying A26.

Approval of this artifact means only that the candidate target family is registered for research. It does not imply that any member of the family will be promoted.

## 2. Strategy intent

V2.1 is designed to evaluate directional opportunity in the underlying/reference instrument before downstream option selection.

The predictive target is therefore defined on the underlying/reference market state, not on a retrospectively selected option contract.

## 3. Decision boundary

A decision occurs at a completed canonical observation timestamp `t_d`.

The reference price is the canonical last/close value available at `t_d`. A feature snapshot may use only observations whose `availability_time <= t_d`.

No partially formed future bar may enter the decision snapshot.

## 4. Candidate target family

Each target candidate is a separately versioned label definition. The research registry must evaluate the pre-registered candidate set rather than inventing new candidates after inspecting final holdout results.

For horizon `H` and neutral threshold `theta`:

```text
R(t_d,H) = P(t_d + H) / P(t_d) - 1
```

where `P` is the canonical reference price and both observations must be causally observable under the outcome contract.

The ternary label is:

```text
UP       if R >  theta
NEUTRAL  if |R| <= theta
DOWN     if R < -theta
```

This is a market-outcome label. It is not an execution P&L label.

## 5. Pre-registered candidate set

The initial research grid is deliberately small:

```text
H in {5min, 10min, 15min, 30min}

theta in {0.0000, 0.0010, 0.0025, 0.0050}
```

Each `(H, theta)` pair receives a unique `label_definition_version`.

These values are research candidates, not production constants. The grid itself is frozen before the final holdout is opened.

## 6. Why a ternary target

The strategy needs to distinguish directional movement from insufficient movement. A zero-threshold binary direction label forces tiny movements into UP/DOWN and can create a target that is statistically measurable but economically irrelevant.

The neutral band therefore exists as an explicit candidate parameter rather than being hidden inside the model.

## 7. Horizon semantics

`H` is measured in canonical market bars/elapsed trading observations from the decision boundary, not wall-clock time that may cross unavailable market periods.

The label builder must record:

```text
outcome_start_time
outcome_end_time
actual_observation_time
label_maturity_time
```

If the required future observation is unavailable, the label is not fabricated.

## 8. Maturity

For a candidate with horizon `H`, the label becomes mature only when the required terminal reference observation is available under the source contract.

```text
PENDING -> MATURE
```

A missing terminal observation produces `CENSORED` or `INVALID` according to the dataset contract; it never becomes a neutral label by default.

## 9. Opportunity population

For the initial research population, every valid decision timestamp with sufficient causal history is a candidate opportunity. The model/prediction result does not determine whether the candidate exists.

This prevents:

```text
prediction -> opportunity existence
future outcome -> opportunity existence
```

The research implementation may later introduce a structural opportunity filter only as a new, separately registered policy.

## 10. Features

The initial model may use only canonical features whose definitions are resolved by A27/A40. No provider-specific field may enter the model directly.

The first research implementation should prefer a small, auditable feature set. Feature selection is part of model selection and must occur inside training/validation boundaries.

## 11. Model target

The baseline model target is the three-class label:

```text
DOWN / NEUTRAL / UP
```

The baseline probability object is:

```text
P(class | FeatureSnapshot_t)
```

The class probabilities must sum to one and identify the exact target/horizon version.

## 12. Calibration

Raw model outputs are not automatically treated as calibrated probabilities.

The existing V2.1 calibration implementation uses validation-only temperature scaling. Calibration parameters must be fitted only on the validation population for the relevant research cycle and must never use final holdout labels.

## 13. Economic boundary

This target predicts underlying market direction. It does not directly predict option P&L.

Option selection, expected execution cost, protection, risk and sizing remain downstream contracts.

A directional probability is therefore insufficient by itself to authorize an order.

## 14. Research-selection rule

The research registry must retain every tested `(H, theta)` candidate and its cycle-level results.

Selection may use training/validation evidence according to the pre-declared research policy.

The final holdout may be inspected only after candidate/feature/model/calibration selection is frozen.

If holdout results influence any subsequent selection, the holdout is contaminated and cannot support a final out-of-sample claim.

## 15. Leakage attacks

Forbidden:

```text
future P(t_d + H) -> features(t_d)
future label -> feature normalization
future label -> opportunity existence
future option performance -> target construction
future contract selection -> historical label
holdout performance -> candidate selection
```

## 16. Survivorship

The reference instrument universe must be historically valid. Current membership must not be substituted for historical membership.

## 17. Censoring

A target is `CENSORED` when the required outcome window cannot be completed because the authoritative data boundary or instrument lifecycle prevents observation.

Censored observations are excluded from ordinary mature-label training unless a later statistical artifact explicitly defines a censored-learning method.

## 18. Research-only status

This proposal intentionally does not resolve:

```text
final H
final theta
final feature subset
final model hyperparameters
final probability threshold
option selection
risk budget
stop/target
execution policy
promotion threshold
```

Those quantities must be selected through the registered walk-forward research process.

## 19. Completion criterion for A26-ND

A candidate target definition is research-ready when it has:

```text
exact formula
exact source price
exact horizon
exact threshold
exact class mapping
maturity rule
censoring rule
version
provenance
causal tests
```

A candidate becomes production-authorized only after the separate validation and promotion gates pass.

## STATUS

```text
A26 original semantic boundary = RESOLVED
A26-ND target family          = DEFINED FOR RESEARCH
Candidate grid                = PRE-REGISTERED
Production target             = NOT SELECTED
Live execution                = BLOCKED
```
