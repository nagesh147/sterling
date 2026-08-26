# A184 — Canonical Model Registry, Calibration, Promotion & Rollback Contract

## Status
CANONICAL

## Purpose
Defines model identity, calibration evidence, promotion authority, activation, rollback, and historical reproducibility. It does not prescribe a specific model family.

## Model identity
Every model version must bind:
```text
model_id
model_version
training_dataset_version
feature_version
label_version
formula_registry_version
configuration_version
training_cutoff
validation_boundary
test_boundary
code_revision
created_at
```

## Prediction separation
```text
raw_score != calibrated_probability
calibrated_probability != economic value
model output != execution authorization
```

## Calibration
Where a probability is consumed as a probability, calibration must be evaluated independently from discrimination or ranking performance.

Calibration evidence must identify:
```text
calibration_population
calibration_method
calibration_version
training boundary
validation boundary
out-of-sample evidence
```

No calibration parameter may be fitted on a future evaluation set and then reported as historical performance.

## Candidate status
```text
DRAFT
RESEARCH
VALIDATING
ACCEPTED
PROMOTION_PENDING
PRODUCTION
RETIRED
REJECTED
```
Transitions are explicit and auditable.

## Promotion
Promotion requires a complete evidence set under the research contract. A model cannot be promoted because it merely outperforms an incumbent in-sample.

Required evidence includes, as applicable:
```text
out-of-sample performance
robustness
cost sensitivity
population definition
search/selection lineage
feature/label lineage
calibration evidence
operational compatibility
```

## No silent activation
A newly registered model is not production-active by default.

```text
registry existence != production authority
```

## Activation
Production activation requires an explicit authorized release and compatible configuration/version set.

## Rollback
Rollback selects an already authorized prior model version. It must not rewrite predictions or decisions already issued under the previous model.

## Model retirement
Retirement blocks new use but preserves all historical evidence and remains queryable for audit/replay.

## Inference reproducibility
A historical prediction must be reproducible from the recorded:
```text
model version
feature snapshot
formula versions
configuration
input evidence
```

## Provider independence
Provider changes must not silently change model identity. If provider semantics alter canonical features or economics, a new compatible version/evidence path is required.

## Security
Model promotion and activation are privileged operations. Model payloads cannot self-authorize activation.

## Failure conditions
Promotion is blocked for:
```text
missing dataset lineage
missing feature/label versions
missing validation boundary
incomplete test evidence
unresolved data leakage
incompatible configuration
unverified model artifact
unauthorized promotion
```

## Invariants
```text
INV-184-001 model identity is immutable
INV-184-002 production activation is explicit
INV-184-003 research models cannot self-promote
INV-184-004 historical predictions remain bound to their original model
INV-184-005 rollback cannot rewrite historical decisions
INV-184-006 calibration cannot use future evaluation information
INV-184-007 promotion requires reproducible evidence
INV-184-008 retired models remain auditable
INV-184-009 provider changes cannot silently mutate model semantics
INV-184-010 model artifacts cannot self-authorize privileged activation
```

## Adversarial tests
```text
future calibration data
missing dataset version
feature version mismatch
label version mismatch
candidate activation without approval
rollback while positions are open
retired model requested for new decision
provider schema change
model artifact corruption
promotion after selection over many candidates
```

## Parameter classes
Frozen: model identity, lineage, promotion separation, activation authority, rollback semantics, historical immutability.

Configuration: approval roles, registry retention, activation workflow, rollback scope.

Validation-dependent: calibration method, model family, hyperparameters, acceptance thresholds.

## Status
ARCHITECTURE STATUS: COMPLETE
UNRESOLVED: None at architectural-contract level.
UNKNOWN / TODO: exact registry technology, artifact storage, calibration library.
BLOCKERS: None for specification work.
NEXT ARTIFACT: A185 — Canonical Production Release, Deployment, Feature-Flag & Environment Promotion Contract
