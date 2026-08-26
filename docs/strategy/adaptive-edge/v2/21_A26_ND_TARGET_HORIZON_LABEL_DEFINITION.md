# Adaptive Edge V2.1 — A26 New-Definition Target, Horizon and Label Contract

**Artifact:** A26-ND
**Version:** 2.1.0
**Status:** PROPOSED-RESEARCH-CONTRACT
**Depends on:** A25, A26-RA, A01, A27
**Market-data authority:** TrueData only
**Trading/execution authority:** Zerodha Kite only
**Implementation authorization:** NONE until this contract passes validation gates

## 1. Purpose

A26-RA established that the original V2 source does not contain a unique numerical opportunity rule, horizon, target, or label function. The canonical mathematical source nevertheless establishes a directional-probability family over a horizon using a volatility-normalized future return:

```text
P_up(h | X_t)
P_down(h | X_t)
P_neutral(h | X_t)

NormalizedReturn(t,h)
    = Return(t,h) / sigma_t
```

A26-ND converts that source-supported mathematical family into an explicit versioned V2.1 research definition without inventing fixed numerical thresholds or horizons.

This is a strategy-definition artifact, not evidence that the definition is profitable or production-authorized.

## 2. Decision unit

An opportunity evaluation is generated from a causally valid TrueData market-state snapshot at decision time `t_d`.

The opportunity population is deliberately broad:

```text
OpportunityExists(t_d)
    = canonical market-data state is valid
      AND required feature inputs are available
      AND the decision timestamp is inside the configured trading session
```

This definition makes opportunity generation independent of the future outcome. Economic eligibility remains downstream.

The exact required-feature set and session calendar remain dependencies of A27/A01 and the instrument contract.

## 3. Prediction target

The primary research target is the **directional movement of the selected underlying/reference instrument**, not the future option premium and not the realized broker execution result.

For a selected horizon `h`:

```text
Return(t,h) = P(t+h) / P(t) - 1

Z(t,h) = Return(t,h) / sigma_t
```

where:

```text
P(t)       = canonical TrueData underlying/reference price at decision time
P(t+h)     = canonical TrueData underlying/reference price at the horizon
sigma_t    = causal volatility estimate available at decision time
```

The exact canonical price field and volatility estimator are A27/A19 dependencies and must be explicitly versioned before implementation.

No Kite price, fill price, position, or realized P&L enters the target.

## 4. Three-state label

For each selected horizon `h` and movement threshold `theta_h >= 0`:

```text
Y(t,h) = UP       if Z(t,h) >  theta_h
Y(t,h) = DOWN     if Z(t,h) < -theta_h
Y(t,h) = NEUTRAL  otherwise
```

Equality is intentionally assigned to `NEUTRAL`:

```text
Z = +theta_h -> NEUTRAL
Z = -theta_h -> NEUTRAL
```

This creates a deterministic non-overlapping partition.

`theta_h` is not a hard-coded strategy constant. It is a learned/research parameter selected only through the declared walk-forward protocol.

## 5. Horizon definition

The model is explicitly horizon-conditional:

```text
P(Y=k | X_t, h)
```

A production model version must contain an immutable horizon-selection policy and the selected horizon state.

The original source does not establish a fixed numerical horizon. Therefore A26-ND does not invent one.

Research may evaluate a pre-declared candidate horizon set:

```text
H_candidate = {h_1, h_2, ..., h_n}
```

The candidate set itself must be declared before the corresponding evaluation boundary is opened.

A selected horizon is promoted only when its selection procedure passes the same out-of-sample and multiple-testing controls as any other learned strategy quantity.

## 6. Target instrument

The target is defined on the underlying/reference market instrument used to construct the decision state.

Option selection is downstream:

```text
TrueData underlying state
        |
        v
prediction target
        |
        v
expected economic value
        |
        v
option candidate selection
        |
        v
Kite execution
```

This prevents option-selection hindsight from contaminating the predictive target.

## 7. Outcome observation

The outcome observation contains only TrueData market observations required by the target definition:

```text
opportunity_id
decision_time
horizon_id
outcome_start_time
outcome_end_time
P(t)
P(t+h)
sigma_t_snapshot_reference
source_event_references
outcome_definition_version
availability_provenance
```

The outcome is not an execution outcome.

## 8. Label maturity

A label becomes mature only when the complete required TrueData observation at `t+h` is available under the canonical source contract.

```text
PENDING
   |
   v
HORIZON_COMPLETE
   |
   v
SOURCE_COMPLETE
   |
   v
MATURE
```

If required source observations cannot be obtained under the authoritative data contract, the outcome becomes `CENSORED` or `INVALID_DATA`; it is never silently converted to `NEUTRAL`.

## 9. Censoring

A label is censored when its required future observation cannot be established because of an authoritative data/instrument boundary such as:

```text
source gap
instrument lifecycle termination
session termination where the target definition cannot continue
invalid source event
missing required TrueData observation
```

Censoring treatment in model fitting is a separate statistical policy and must not be confused with the label value itself.

## 10. No path-dependent threshold crossing

A26-ND deliberately defines the label from the **terminal normalized return at the selected horizon**.

It does not use:

```text
first target touch
first stop touch
MFE/MAE race
intrahorizon path ordering
```

This removes the unresolved simultaneous-threshold-crossing ambiguity identified by A26-RA.

Intrahorizon path behavior belongs to the later economic/execution/exit model, not the primary predictive label.

## 11. Why normalized return

This choice is directly grounded in the canonical source's §21 definition of directional probability and normalized return. The source defines the probability states by horizon and defines normalized return as future return divided by sigma.

A26-ND therefore does not introduce a different target family such as future option P&L, MFE, or broker-fill P&L.

## 12. Learned quantities

The following are learned/research quantities:

```text
horizon selection
movement threshold theta_h
volatility-estimation parameters
model coefficients
calibration parameters
probability/decision thresholds
```

They must be selected using the causal walk-forward protocol.

No value becomes strategy truth merely because it improves an in-sample result.

## 13. Training population

A training row requires:

```text
valid opportunity
causal feature snapshot
mature outcome
complete label provenance
strategy definition version
feature-set version
label-definition version
```

Rows whose labels are pending, censored, or invalid are excluded according to the statistical learning policy; they are not silently relabeled.

## 14. Leakage rules

Forbidden:

```text
future outcome -> opportunity existence
future outcome -> feature normalization
future option choice -> target
future fill -> target
future P&L -> target
future model performance -> threshold/horizon selection
future data availability -> historical feature validity
```

## 15. Execution separation

Kite is used only after the economic decision and risk authorization stages.

The target does not depend on:

```text
Kite order status
Kite fill price
Kite position
Kite square-off
Kite realized P&L
```

Those are execution/accounting facts and are recorded independently.

## 16. Research selection protocol

For each candidate horizon and threshold configuration:

```text
TRAIN
  -> fit model / estimate parameters
VALIDATION
  -> select candidate configuration
HOLDOUT
  -> untouched final evaluation
```

The holdout must not be inspected to select:

```text
horizon
theta_h
feature set
model family
calibration
execution policy
```

Selection across multiple candidate horizons/thresholds must be recorded as a multiple-testing/research-selection family.

## 17. Versioning

Any change to:

```text
target price field
volatility estimator
horizon definition
horizon candidate population
threshold definition
label equality rule
censoring rule
underlying instrument definition
```

requires a new label-definition version and invalidates comparability with prior model versions unless a formal compatibility analysis proves equivalence.

## 18. Attack — target leakage

The target uses future TrueData observations only after the decision boundary. It cannot influence the feature snapshot or opportunity population.

## 19. Attack — option hindsight

The prediction target is on the underlying/reference instrument. Therefore selecting a future option that later performed best cannot alter the target.

## 20. Attack — threshold overfitting

`theta_h` is not selected on holdout data. If a large threshold grid is searched, the entire grid is a research-selection family and must be controlled for multiple testing.

## 21. Attack — horizon overfitting

The same rule applies to horizon selection. A horizon that wins only because many alternatives were searched cannot be treated as independently validated.

## 22. Attack — volatility leakage

`sigma_t` must be computed only from data available at `t_d`. Any estimator fitted using observations after `t_d` is invalid for that decision.

## 23. Attack — execution contamination

Because the target is defined from TrueData underlying observations, broker execution latency, fill quality, and square-off behavior cannot contaminate the statistical target.

They remain explicit inputs to downstream economic evaluation.

## 24. Attack — missing future observation

Missing `P(t+h)` is not `NEUTRAL`.

It produces an unavailable/censored outcome according to the source-data contract.

## 25. Attack — overlapping labels

Overlapping horizon labels are permitted but are not assumed independent. Walk-forward evaluation must preserve dependence-aware inference and purging/embargo rules where required.

## 26. Frozen architecture

```text
Target family = directional classification of normalized future underlying return
Target states = UP / DOWN / NEUTRAL
Outcome source = TrueData
Execution source = Zerodha Kite
Outcome != execution outcome
Terminal horizon return, not intrahorizon path race
No fixed numerical horizon is invented
No fixed numerical threshold is invented
```

## 27. Research/configuration

```text
horizon candidate set       = research configuration
selected horizon            = learned/validated
threshold candidate set     = research configuration
selected threshold          = learned/validated
volatility estimator        = versioned research configuration
```

## 28. External dependencies

```text
A01 TrueData source semantics
A19 normalization/volatility estimator contract
A27 exact canonical price field
instrument/session calendar
historical TrueData coverage
```

All unresolved external dependencies remain explicit until their source contracts are confirmed.

## ARCHITECTURE STATUS

**FROZEN:** directional normalized-return target family; three-state label; underlying target; TrueData outcome source; terminal-horizon semantics; explicit maturity/censoring; no execution contamination; causal training boundary; research-selection governance.

**UNRESOLVED:** numerical horizon; numerical threshold; exact canonical price field; exact volatility estimator; final opportunity required-feature set; source-coverage limitations.

**BLOCKERS:** No blocker to the V2.1 target family. Numerical promotion remains blocked until the declared research configuration is evaluated causally and out-of-sample and the required TrueData field semantics are frozen.

**NEXT ARTIFACT:** A27 — Canonical Feature Set and TrueData Field-Level Contract.
