# A183 — Canonical Research Dataset, Label Maturity & Walk-Forward Boundary Contract

## Status
CANONICAL

## Purpose
Defines the causal boundary between production observations and research datasets, including label maturity, training/validation/test separation, population construction, and walk-forward evaluation.

## Dataset lineage
Every research sample must trace:
```text
raw evidence
 -> canonical event
 -> point-in-time state
 -> feature snapshot
 -> decision context
 -> future outcome observation
 -> mature label
 -> dataset sample
```

A sample without complete lineage is ineligible for model training or validation.

## Label maturity
A label may be created only after its observation horizon has elapsed and every required outcome input is available.

```text
decision_time < label_maturity_time
```
An immature label is not a negative label, positive label, or zero label. It is `UNAVAILABLE`.

## Temporal boundary
For a sample generated at decision time `t`:
```text
features <= t
label > t
```
The label may describe future outcomes, but it cannot influence the feature or decision state that preceded it.

## Dataset partitions
The research system must maintain explicit boundaries for:
```text
training
validation
selection
holdout/test
final out-of-sample
```
An observation cannot belong to a future evaluation boundary merely because its file was created later.

## Walk-forward construction
A walk-forward fold has:
```text
training_window
validation_window
evaluation_window
```
with explicit temporal ordering.

```text
training_end < validation_start
validation_end <= evaluation_start
```
Exact overlap policy is defined by the research protocol and must prevent label leakage.

## Population definition
The dataset must define its historical population independently of the model result. Current survivorship or post-period membership must not silently redefine historical eligibility.

## Selection bias
All candidate-search decisions must preserve their search lineage. A model selected after many alternatives were tested cannot be evaluated as though it were the only candidate considered.

## Multiple testing
The research record must preserve:
```text
candidate_set
search_space
selection_rule
number_of_trials where material
```
so that validation evidence reflects the actual selection process.

## Feature versioning
Every sample binds to a feature version and formula registry version. A later feature implementation cannot silently reinterpret historical samples.

## Label versioning
Every label binds to a label-definition version. Changes to exit economics, horizon, cost assumptions, or outcome windows create a new label version.

## Execution realism
Where research models execution, the dataset must distinguish:
```text
market opportunity
estimated execution
realized execution
```
Historical realized fills cannot be used to improve the historical decision estimate unless the information was available at decision time.

## Research/live separation
Production execution evidence may be consumed by research only after the relevant label has matured and the sample is explicitly admitted. Research outputs cannot mutate historical production decisions.

## Model promotion boundary
A candidate may progress only through:
```text
research
 -> validation
 -> out-of-sample evaluation
 -> acceptance
 -> promotion authorization
```
No research result automatically becomes production authority.

## Reproducibility
A dataset build must be reproducible from:
```text
source revision
formula versions
feature versions
label version
configuration version
population definition
cutoff timestamps
```

## Invariants
```text
INV-183-001 immature labels are never used as mature outcomes
INV-183-002 future labels cannot influence historical features
INV-183-003 training and evaluation boundaries are explicit
INV-183-004 historical population cannot be silently rewritten by survivorship
INV-183-005 candidate-search lineage is preserved
INV-183-006 feature versions are immutable for existing samples
INV-183-007 label versions are immutable for existing samples
INV-183-008 realized future execution cannot contaminate historical decision estimates
INV-183-009 research cannot directly mutate production authority
INV-183-010 every promoted model is reproducible from an immutable dataset definition
```

## Adversarial tests
```text
immature label injection
future feature injection
future cost injection
survivorship population substitution
training/test overlap
label leakage through normalization
candidate-search contamination
multiple-testing omission
future model calibration leakage
revised historical data leakage
realized fill used as historical quote
```

## Parameter classes
Frozen: temporal ordering, label maturity concept, partition separation, lineage, reproducibility, research/live separation.

Configuration: fold windows, embargo/gap rules, population filters, minimum sample policies, retention.

Validation-dependent: sample sufficiency, statistical acceptance thresholds, model-specific hyperparameters.

## Status
ARCHITECTURE STATUS: COMPLETE
UNRESOLVED: None at architectural-contract level.
UNKNOWN / TODO: exact dataset storage implementation and final statistical acceptance protocol.
BLOCKERS: None for specification work.
NEXT ARTIFACT: A184 — Canonical Model Registry, Calibration, Promotion & Rollback Contract
