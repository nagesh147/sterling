# A210 — F-104 Adaptive Horizon Canonical Recovery

**Status:** `[SOURCE-RECOVERED / RESEARCH IMPLEMENTATION]`
**Formula:** F-104 — Adaptive horizon distribution
**Source:** Adaptive Order-Flow Options Scalping and Intraday Strategy — Master Mathematical Specification v1.0
**Source commit:** `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`

## 1. Decision

F-104 is not a fixed clock-based strategy classifier. The recovered V1 source explicitly models a distribution over future trade duration:

```text
P(T < 3m)
P(3m <= T < 5m)
P(5m <= T < 15m)
P(15m <= T < 30m)
P(30m <= T < 45m)
P(T > 45m)
```

These are statistical expectations. A trade can evolve naturally from a short horizon into a longer management horizon without changing its identity.

Therefore F-104 must produce a **horizon distribution**, not a deterministic `MICRO/SCALP/INTRADAY` label from elapsed time.

## 2. Management classification

The implementation may derive a management classification from the distribution for downstream lifecycle controls:

```text
MICRO_SCALP
SCALP
EXTENDED_SCALP
INTRADAY
```

The classification is a derived management state, not the underlying statistical model.

## 3. Required inputs

F-104 consumes the causal probability/market state available at decision time, including where available:

```text
P_up
P_down
P_neutral
P_regime
volatility state
market regime
trade-state features
execution context
data quality
```

Future outcomes such as `TimeToMFE` may be used to construct historical labels after the original decision point is frozen, but may not be available as inputs to the decision that generated that label.

## 4. Causal contract

For decision time `t`:

```text
HorizonState_t = f(Information <= t)
```

Training labels are generated from future observations only after `t` has been frozen.

The fitted horizon model must therefore follow:

```text
TRAIN -> FREEZE -> VALIDATE -> TEST -> RECORD -> ADVANCE
```

No test-period duration distribution may influence the model before the test period is completed.

## 5. Mathematical contract

The canonical output is a probability vector:

```text
p = [p_<3,
     p_3_5,
     p_5_15,
     p_15_30,
     p_30_45,
     p_>45]
```

with:

```text
p_i >= 0
sum(p_i) = 1
```

The source does not prescribe production cutoff probabilities for collapsing this vector into a management class. Such cutoffs remain learned/validated parameters.

## 6. Horizon expectation

A representative horizon statistic can be computed from the distribution, but open-ended `T > 45m` must not be assigned an arbitrary midpoint without an explicitly validated estimator.

Therefore the research representation retains the probability mass directly and treats the tail as censored/open-ended rather than fabricating a point estimate.

## 7. Missingness

If the model lacks sufficient evidence to estimate a horizon distribution, it must return an explicit unavailable/insufficient state.

It must not silently choose:

```text
SCALP
```

or any other default horizon.

## 8. Position evolution

The lifecycle engine must reevaluate the current horizon distribution as new causal market events arrive. A position initially classified as `MICRO_SCALP` can become `SCALP` or `INTRADAY` if the updated distribution supports a longer expected persistence.

This transition must not loosen previously accepted risk. Horizon adaptation changes management expectations, not the original risk authorization.

## 9. Parameter governance

Unfrozen research parameters include:

```text
horizon-model coefficients
feature weights
regularization
calibration method
minimum effective sample size
classification policy
confidence threshold
```

These require chronological validation before production promotion.

## 10. Prohibited shortcuts

```text
elapsed_time -> forced horizon
fixed 5m threshold -> SCALP
fixed 30m threshold -> INTRADAY
missing distribution -> SCALP
future TimeToMFE -> decision feature
future TimeToMAE -> decision feature
```

## 11. Resolution

```text
Source definition:              RECOVERED
Horizon buckets:                RECOVERED
Causal semantics:               RECOVERED
Probability-vector contract:    RECOVERED
Production model parameters:    UNFROZEN
Calibration:                    REQUIRED
Production implementation:      NOT AUTHORIZED
```

## 12. Next step

Implement the research-only F-104 horizon distribution boundary with explicit normalization, no-lookahead training, and a derived management classification that never substitutes for the underlying probability state.
