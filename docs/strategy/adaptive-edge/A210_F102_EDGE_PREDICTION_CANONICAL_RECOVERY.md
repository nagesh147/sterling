# A210 — F-102 Edge / Prediction Canonical Recovery

**Status:** `[CANONICAL RECOVERY / RESEARCH IMPLEMENTATION PREPARATION]`
**Date:** 2026-08-17
**Formula:** F-102 — Edge / prediction score
**Source:** Adaptive Order-Flow Options Scalping and Intraday Strategy — Master Mathematical Specification v1.0
**Source commit:** `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`

## 1. Decision

F-102 is recovered as the probability-state / directional-prediction layer downstream of the causal feature representation.

The recovered source explicitly defines:

```text
ProbabilityState_t
P_up
P_down
P_neutral
P_regime
P_horizon
MFE_distribution
MAE_distribution
ExecutionDistribution
Uncertainty
```

It then defines directional probabilities for horizon `h`:

```text
P_up(h | X_t)
P_down(h | X_t)
P_neutral(h | X_t)
```

The Version 1 baseline candidate is regularized multinomial logistic regression:

```text
P(Y=k|X) = exp(beta_k · X) / sum_j exp(beta_j · X)

Loss = CrossEntropy + lambda ||beta||^2
```

The regularization parameter is selected through walk-forward validation. fileciteturn57file0L2-L2

## 2. Critical interpretation

F-102 is **not** a hand-authored weighted score such as:

```text
score = 0.3 * price + 0.4 * delta + ...
```

That would violate the recovered strategy contract.

The canonical V1 baseline is a probabilistic classifier whose coefficients are learned from chronologically valid training data.

The source also specifies empirical and Bayesian probability components and a later combined probability whose weights are learned and regularized. fileciteturn57file0L2-L2

Therefore the production F-102 contract has two layers:

```text
F-102A: baseline directional model
F-102B: calibrated / combined probability state
```

Neither layer receives future information.

## 3. Causal input

F-102 consumes the normalized feature representation derived from F-101.

At decision time `t`:

```text
X_t = normalized_feature_state_t
```

and:

```text
X_t must depend only on information available by t
```

The target used for training may reference future movement only after the historical decision point has been frozen. The target cannot be used while constructing `X_t`.

## 4. Directional target semantics

For horizon `h`, the source defines a volatility-normalized future movement conceptually as:

```text
NormalizedReturn(t,h) = Return(t,h) / sigma_t
```

The meaningful-movement threshold is learned and validated rather than hard-coded as a universal point threshold. fileciteturn57file0L2-L2

Consequently, F-102 must not contain a permanent rule such as:

```text
future_move > 50 points => UP
```

unless that threshold is separately learned, versioned, and validated.

## 5. Baseline mathematical contract

Let the model classes be:

```text
k ∈ {UP, DOWN, NEUTRAL}
```

For feature vector `x` and coefficient vector `beta_k`:

```text
z_k = beta_k · x
```

and the stable softmax is:

```text
P_k = exp(z_k - max(z)) / sum_j exp(z_j - max(z))
```

This is mathematically equivalent to the source definition while avoiding numerical overflow.

The output is:

```text
P_up
P_down
P_neutral
```

with:

```text
P_up + P_down + P_neutral = 1
```

within floating-point tolerance.

## 6. Edge representation

The implementation must retain the complete probability state rather than collapsing it immediately into a binary trade command.

A directional edge can be represented as:

```text
directional_edge = max(P_up, P_down) - P_neutral
```

and the preferred direction as:

```text
UP   if P_up > P_down
DOWN if P_down > P_up
NONE when neither direction passes downstream economic/uncertainty gates
```

`directional_edge` is a derived research diagnostic. It is **not** by itself an entry trigger.

The strategy requires expected value, conservative expected value, liquidity, slippage, risk, and data-quality gates downstream. fileciteturn50file0L2-L2

## 7. Model parameters

The following remain learned and unfrozen:

```text
beta_UP
beta_DOWN
beta_NEUTRAL
lambda
feature coefficients / ordering
meaningful-movement target threshold
training window
minimum training sample
probability calibration
combined-model weights
```

No historical optimum is promoted merely because it maximizes backtest return.

## 8. Calibration

Raw model probabilities are not automatically treated as calibrated probabilities.

The source permits:

```text
Platt scaling
Isotonic regression
```

and requires calibration to be performed walk-forward. fileciteturn57file0L2-L2

Therefore an F-102 implementation must expose the distinction between:

```text
raw_probability
calibrated_probability
confidence
uncertainty
```

## 9. Numerical and data safeguards

F-102 must fail closed when:

```text
required feature is missing
feature is invalid
feature is stale
feature is non-finite
coefficient is non-finite
model version is incompatible
feature ordering is incompatible
training sample is insufficient
```

It must never convert missing data to zero merely to obtain a prediction.

## 10. Walk-forward boundary

For evaluation period `T`:

```text
TRAIN
  <= train_end

VALIDATE
  > train_end

TEST
  > validation_end
```

The test period cannot influence model coefficients, normalization, calibration, target thresholds, or model selection before testing is complete.

This follows the recovered source's explicit walk-forward requirement. fileciteturn50file0L2-L2

## 11. Implementation status

```text
Source definition recovered:       YES
Core probability semantics:        RECOVERED
Baseline model mathematics:       RECOVERED
Causal boundary:                   RECOVERED
Calibration semantics:             RECOVERED
Production coefficients:           NOT FROZEN
Target threshold:                  NOT FROZEN
Calibration parameters:            NOT FROZEN
Production implementation:         NOT AUTHORIZED
Execution:                          BLOCKED
```

## 12. Next implementation step

Implement a research-only F-102 multinomial probability evaluator accepting a frozen, versioned coefficient set and producing stable `P_up`, `P_down`, `P_neutral` plus a derived diagnostic edge.

Do not change the formula registry to `IMPLEMENTED` until the model has chronological training, calibration, out-of-sample validation, and attached adversarial tests.
