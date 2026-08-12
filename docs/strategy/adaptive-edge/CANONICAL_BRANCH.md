# Adaptive Edge — Canonical Branch Policy

## Single active branch

```text
feature/adaptive-edge-canonical
```

All future Adaptive Edge code, tests, specifications, and integration work must be committed to this branch until the strategy is ready for a single merge into `main`.

## Consolidated lineage

The branch is based on the latest parameter-fitting lineage and incorporates the source-defined infrastructure recovered on the earlier artifact-resolution and A40 branches.

Integrated areas include:

- canonical Adaptive Edge mathematical/model infrastructure
- research and parameter-fitting infrastructure
- A38 learning-boundary guards
- A39 walk-forward evaluation primitives
- A40 feature availability, immutable snapshots, and feature lineage
- source-defined accounting and quote-feature operators
- A41 prediction and decision-input interface

## Historical branches

The previous branches remain preserved for audit/history. They are not active development targets:

```text
feature/adaptive-edge-artifact-resolution
feature/adaptive-edge-engine
feature/adaptive-edge-engine-implementation
feature/adaptive-edge-engine-v1
feature/adaptive-edge-formula-recovery
feature/adaptive-edge-parameter-fitting
feature/adaptive-edge-strategy-canonical
feature/adaptive-edge-a40-feature-lineage
```

Do not create additional Adaptive Edge feature branches unless there is a specific isolation requirement. The normal workflow is:

```text
feature/adaptive-edge-canonical
        |
        +--> implementation
        +--> tests
        +--> artifact resolution
        +--> review
        |
        v
main
```
