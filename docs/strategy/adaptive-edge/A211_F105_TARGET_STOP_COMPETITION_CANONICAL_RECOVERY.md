# A211 — F-105 Target/Stop Competition and Conservative EV Recovery

**Status:** `[SOURCE-RECOVERED / RESEARCH IMPLEMENTATION]`
**Formula:** F-105
**Source:** Adaptive Order-Flow Options Scalping and Intraday Strategy — Master Mathematical Specification v1.0
**Source commit:** `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`

## 1. Canonical role

F-105 converts the probability state and historical excursion distributions into a target/stop competition and conservative economic viability decision.

It does not choose a trade direction by itself. Direction comes from the underlying market-state/probability layer. F-105 answers:

```text
Given this direction and candidate management parameters,
is the expected economic outcome sufficiently positive and robust?
```

## 2. Competing outcomes

The source models the first relevant event among:

```text
Target reached first
Stop reached first
Neither reached within horizon
```

The outcome probabilities are:

```text
P_T = P(Target first)
P_S = P(Stop first)
P_N = P(Neither)
```

with:

```text
P_T + P_S + P_N = 1
```

The probabilities must be estimated from causal historical labels using only information that would have been available when the candidate trade was created.

## 3. Candidate target and stop

For a long option:

```text
R = Entry - Stop
Target = Entry + mR
```

where `m` is a candidate reward/risk multiple selected through research rather than hard-coded as a production constant.

The initial stop must respect the strategy's bounded-risk invariant.

## 4. Expected value

For candidate target `T`, stop `S`, and entry `E`, the gross outcome model is represented as:

```text
EV_gross = P_T * Gain_T
          + P_S * Loss_S
          + P_N * Outcome_N
```

The economic model must then subtract execution friction:

```text
EV_net = EV_gross - ExpectedExecutionCost
```

Expected execution cost includes, where supported:

```text
spread
slippage
fees
option-specific execution friction
```

The exact cost estimator is not frozen by F-105.

## 5. Conservative EV

The source requires a lower-confidence-bound form of expected value:

```text
EV_conservative = LCB(EV_net)
```

A candidate is economically eligible only when the conservative value is positive:

```text
EV_conservative > 0
```

Otherwise:

```text
NO_TRADE
```

This is intentionally stricter than:

```text
EV_net > 0
```

because a positive point estimate with excessive uncertainty is not sufficient.

## 6. Uncertainty

The uncertainty model must account for sample size and outcome dispersion. It must not fabricate confidence when historical support is weak.

Insufficient evidence produces an explicit unavailable/uncertain state and fails closed.

## 7. Causality

Historical target/stop labels may use future market observations only after the original decision timestamp has been frozen.

The feature/probability state used to estimate the candidate must not include:

```text
future MFE
future MAE
future target hit
future stop hit
future realized PnL
```

The fitting sequence remains:

```text
TRAIN -> FREEZE -> VALIDATE -> TEST -> RECORD -> ADVANCE
```

## 8. Candidate comparison

Multiple target/stop candidates may be evaluated. Selection must be deterministic for identical inputs and frozen parameters.

The selection objective is not raw historical PnL. It must respect:

```text
positive conservative EV
risk constraints
execution costs
sample sufficiency
data quality
```

If no candidate satisfies all constraints:

```text
NO_TRADE
```

## 9. Missingness and failure behavior

F-105 fails closed when any required quantity is unavailable:

```text
missing probability
missing excursion distribution
invalid target/stop
missing execution cost
insufficient evidence
non-finite EV
```

No missing value may be converted to zero merely to produce an eligible candidate.

## 10. Parameter governance

Research-only/unfrozen quantities include:

```text
candidate reward/risk multiples
MFE/MAE distribution estimator
minimum sample size
uncertainty estimator
LCB confidence level
execution-cost estimator
candidate selection policy
```

None becomes a production parameter without chronological calibration and promotion evidence.

## 11. Prohibited shortcuts

```text
EV_gross > 0 -> trade
EV_net > 0 -> trade
fixed 2:1 target -> production
fixed stop percentage -> production
future MFE as feature -> prohibited
missing cost -> cost = 0
insufficient sample -> assume confidence
historical PnL maximum -> automatic promotion
```

## 12. Resolution

```text
Source semantics:               RECOVERED
Target/stop competition:        RECOVERED
Net-EV requirement:             RECOVERED
Conservative-EV requirement:    RECOVERED
Production parameters:          UNFROZEN
Calibration:                    REQUIRED
Production implementation:      NOT AUTHORIZED
```

## 13. Next step

Implement the research F-105 contract as a deterministic candidate evaluator. It must expose gross EV, execution cost, net EV, uncertainty, conservative EV, and final eligibility separately so downstream F-103 can compose them without duplicating economics.
