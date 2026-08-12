# Adaptive Edge V2.1 — Calibration and Horizon Addendum

**Status:** PROPOSED / RESEARCH-ONLY
**Version:** 2.1.0-proposed

This addendum extends A26-ND so the previously blocked §25 calibration and §28 horizon components have explicit V2.1 semantics.

## Probability calibration

V2.1 uses temperature scaling.

Given logits `l_k` and positive temperature `T`:

```text
p_k(T) = exp(l_k / T) / sum_j exp(l_j / T)
```

The temperature is fitted on the validation partition only by deterministic grid search over an explicit configuration interval.

The selected temperature minimizes validation multiclass log loss.

```text
T* = argmin_T ValidationLogLoss(T)
```

No holdout observation may be passed to `fit_temperature`.

The calibration implementation is:

```text
backend/app/engines/adaptive_edge/calibration.py
```

## Horizon target

V2.1 defines the target as the underlying future return observed after a configured bar horizon.

The initial research configuration is:

```text
horizon_bars = 15
```

This value remains a research parameter.

Each observation contains:

```text
decision_time
observation_time
future_return
```

An observation is eligible only when:

```text
observation_time > decision_time
```

The empirical horizon distribution contains:

```text
sample_size
mean_return
standard_deviation
sorted_returns
```

and supports linear-interpolation empirical quantiles.

Implementation:

```text
backend/app/engines/adaptive_edge/horizon_distribution.py
```

## Research boundary

Neither calibration temperature nor horizon length is promoted as a universal market truth. Both remain versioned research parameters and must pass the existing walk-forward, protected-holdout, execution-cost and promotion gates.

## Resolution

```text
Original §25 source recovery: unresolved
V2.1 calibration definition: implemented
Original §28 source recovery: unresolved
V2.1 horizon definition: implemented
Production promotion: blocked
```
