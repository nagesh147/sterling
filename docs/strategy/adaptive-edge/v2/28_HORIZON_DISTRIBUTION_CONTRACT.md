# Adaptive Edge V2 — Horizon Distribution Boundary

**Artifact:** §28 implementation boundary  
**Status:** BLOCKED

## 1. Source relationship

The canonical registry identifies §28 as the horizon-distribution mathematical boundary. The recovered prediction contract establishes that every prediction must carry a versioned `horizon_definition_version`, and that the target requires an explicit observation horizon.

The recovered source does not provide a sufficiently complete horizon-distribution estimator or frozen target/horizon semantics to implement §28 as executable strategy mathematics.

## 2. Dependency boundary

The causal dependency is:

```text
Opportunity / decision time
        |
        v
TargetDefinition
        +
ObservationHorizon
        |
        v
Outcome / label
        |
        v
Horizon-dependent prediction distribution
```

A26 currently leaves the primary target and outcome horizon unresolved. A28 consequently does not freeze a production prediction target.

## 3. Distribution boundary

If a future implementation predicts a distribution, the prediction contract permits the mathematical form:

```text
F_t(y) = P(Y <= y | X_t)
```

But the source does not select the distributional model, target support, horizon value, censoring treatment, or calibration method.

Therefore no parametric family, empirical horizon grid, fixed holding period, or numerical horizon is introduced here.

## 4. Versioning invariant

A prediction must retain:

```text
horizon_definition_version
```

A prediction generated under horizon `H1` must not be silently compared with an outcome labeled under `H2`.

Changing the horizon changes the target definition and therefore requires a new target/model version.

## 5. Explicitly prohibited assumptions

This boundary does not choose:

```text
fixed holding period
bar count
minute horizon
expiry-based horizon
MFE/MAE horizon
return horizon
quantile grid
parametric distribution
censoring policy
horizon threshold
```

Those values require authoritative strategy semantics or an explicitly versioned research specification.

## 6. Implementation decision

No horizon-distribution estimator is added.

The correct state is `BLOCKED`, not `PARTIAL`, because the missing inputs determine the quantity being predicted rather than merely tuning an implementation.

## 7. Required unblock artifact

Before executable horizon-distribution mathematics can be added, the project needs a versioned contract defining at minimum:

1. target definition;
2. observation horizon semantics;
3. horizon units and boundary convention;
4. outcome maturity/censoring semantics;
5. distributional representation;
6. estimation procedure;
7. validation/calibration procedure;
8. horizon/model versioning rules.
