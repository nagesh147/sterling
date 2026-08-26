# Adaptive Edge V2.1 — A39 Walk-Forward Research and Promotion Contract

**Artifact:** A39
**Version:** 2.1.0
**Status:** PROPOSED-RESOLVED

## 1. Purpose

Define how all learned quantities are selected without future leakage and how a strategy version can progress from research to promotion.

## 2. Research cycle

```text
Historical population
      |
      v
TRAIN
      |
      +--> fit model
      +--> estimate normalization
      +--> estimate volatility
      +--> estimate thresholds
      +--> estimate cost/slippage parameters
      |
      v
VALIDATION
      |
      +--> calibration
      +--> configuration selection
      +--> model selection
      |
      v
HOLDOUT
      |
      +--> one-time final evaluation
      |
      v
PROMOTION REVIEW
```

## 3. Selection family

The following are explicitly part of research selection:

```text
feature subset
horizon
movement threshold
volatility estimator
model coefficients
regularization
calibration temperature
option candidate policy
cost model
stop/target policy
risk parameters
```

Each candidate configuration receives a versioned experiment identity.

## 4. Training boundary

Training uses only rows with:

```text
label_maturity_time <= training_cutoff
```

No validation or holdout row may enter fitting.

## 5. Validation boundary

Validation may select configuration but may not be treated as final evidence.

## 6. Holdout boundary

The holdout is untouched until all strategy/model/configuration choices are frozen.

Repeated holdout inspection invalidates its final-test status.

## 7. Purging and embargo

Overlapping outcome windows require purging of observations whose label spans overlap a validation/test boundary.

An embargo may additionally be applied when temporal dependence remains after purging.

The numerical embargo length is experiment configuration, not strategy truth.

## 8. Multiple testing

Every search over:

```text
horizons
thresholds
features
models
cost assumptions
stop/target policies
```

is registered as a research-selection family.

Final claims must account for the selection process.

## 9. Promotion criteria

Promotion requires all of:

```text
causal dataset validation
no leakage
validation success against predeclared criteria
untouched holdout evaluation
execution-cost sensitivity
parameter sensitivity
multiple-testing control
calibration review
risk/drawdown review
operational gate pass
```

## 10. Failure

If any mandatory criterion fails:

```text
PROMOTION_REJECTED
```

No parameter is changed after holdout failure and re-tested on the same holdout while retaining the same claim.

## 11. Reproducibility

A research result must be reproducible from:

```text
data snapshot/version
strategy version
feature-set version
label version
model version
research configuration
randomness policy
code version
experiment id
```

## 12. Attack

### Leakage

Future labels are excluded from fitting before maturity.

### Selection bias

The research population is generated independently of future outcomes.

### Multiple testing

Candidate searches are registered.

### Survivorship

Historical instrument universe is time-valid.

### Regime selection

A regime cannot be selected because it performs best on the final holdout.

### Execution overfit

A cost model cannot be tuned on final realized trades and then presented as pre-trade evidence.

## ARCHITECTURE STATUS

**FROZEN:** causal train/validation/holdout ordering; promotion gate; research-selection registration; reproducibility requirements; purging principle; no holdout reuse.

**CONFIGURABLE/LEARNED:** all numerical model and strategy parameters, fold windows, purge/embargo lengths and acceptance thresholds.

**BLOCKERS:** actual promotion evidence does not yet exist. This is a research gate, not a mathematical blocker.

**NEXT ARTIFACT:** A40 — Feature Availability and Snapshot Provenance Contract.
