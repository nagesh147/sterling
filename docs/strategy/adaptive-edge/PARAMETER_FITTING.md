# Adaptive Edge — Parameter Fitting

## Purpose

Fit the parameterized probability model from causally valid training rows without introducing strategy-specific coefficients by hand.

## Model

The Master Mathematical Specification defines the multinomial logistic family:

```text
P(Y=k | X) = exp(beta_k · X) / sum_j exp(beta_j · X)
```

The implementation is `backend/app/engines/adaptive_edge/parameter_fitting.py`.

## Training boundary

Only the `train` partition supplied by the walk-forward splitter may be used for fitting. Validation and holdout observations are never passed into the optimizer.

```text
TRAIN -> fit parameters
VALIDATION -> select/reject configuration
HOLDOUT -> final untouched evaluation
```

## Current fitter

The current research implementation uses deterministic batch gradient descent with L2 regularization. This is an implementation of the specified model family, not evidence that these hyperparameters are optimal.

The fitter therefore does not promote any of these values to strategy truth:

```text
learning_rate
number of epochs
L2 coefficient
window sizes
probability threshold
calibration threshold
```

They are research configuration and must be validated out-of-sample.

## Promotion gate

A fitted model may not be considered tradable merely because training loss decreases. At minimum, promotion requires:

1. causal dataset validation;
2. purged/embargoed chronological folds;
3. validation performance exceeding the pre-declared acceptance criteria;
4. untouched holdout evaluation;
5. execution-cost sensitivity;
6. calibration review;
7. drawdown and risk-capacity review.

## Important distinction

A statistically valid probability model is not automatically an economically valid trading model. The probability output must flow through expected gross value, execution cost, conservative expected net value, and risk authorization before an opportunity can be actionable.
