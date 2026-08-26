# Adaptive Edge V2.1 — A38 Label Maturity and Learning Dataset Contract

**Artifact:** A38
**Version:** 2.1.0
**Status:** PROPOSED-RESOLVED

## 1. Purpose

Guarantee that only causally mature labels enter training, validation or holdout populations.

## 2. Label lifecycle

```text
PREDICTION
    |
    v
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

Alternative terminal states:

```text
CENSORED
INVALID
```

## 3. Maturity rule

For decision time `t_d` and selected horizon `h`:

```text
maturity_time >= outcome_end_time
```

and all required TrueData observations needed by the target definition must be available.

## 4. Training eligibility

A row is training-eligible at cutoff `T` only if:

```text
label_status == MATURE
label_maturity_time <= T
feature_availability_time <= decision_time
```

No future observation after `T` may enter the training population.

## 5. Dataset partitions

```text
TRAIN
VALIDATION
HOLDOUT
```

The partitions are chronological and causally separated.

Calibration uses validation only.

Final model evaluation uses untouched holdout.

## 6. Label provenance

Every label stores:

```text
opportunity_id
prediction_id
label_definition_version
horizon_id
threshold_version
outcome_source_version
outcome_event_references
maturity_time
label_value
label_status
```

## 7. Censoring

Censored observations are retained in the research ledger but are not silently mapped to UP/DOWN/NEUTRAL.

Their treatment in a particular estimator must be explicitly declared.

## 8. Overlapping labels

Overlapping horizons are allowed.

They are not assumed independent.

Walk-forward inference must use purging/embargo/dependence-aware methods where the selected estimator requires them.

## 9. No label mutation

A promoted historical label cannot be silently rewritten.

If source data are revised:

```text
new source version
    -> new outcome version
    -> new label version
```

with compatibility analysis.

## 10. Attack

```text
future outcome -> feature       FORBIDDEN
future label -> opportunity     FORBIDDEN
immature label -> training      FORBIDDEN
holdout -> calibration          FORBIDDEN
holdout -> threshold selection  FORBIDDEN
```

## ARCHITECTURE STATUS

**FROZEN:** maturity lifecycle; training eligibility; provenance; chronological partitions; censoring; no silent mutation; causal boundary.

**CONFIGURABLE:** partition windows, purge/embargo lengths, censoring estimator policy.

**BLOCKERS:** none at the lifecycle level. Exact dataset windows depend on the research experiment.

**NEXT ARTIFACT:** A39 — Walk-Forward Research and Promotion Contract.
