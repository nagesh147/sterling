# Adaptive Edge V2 — Economic Value, Expected Value and Decision Utility Contract

**Artifact:** A42  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** NONE

## 1. Purpose

A42 defines the causal boundary between prediction and an economically meaningful decision.

It establishes how a prediction may be combined with defined outcome economics, execution costs, and risk constraints to produce an expected economic quantity and, eventually, a decision input.

A42 does not invent the target, payoff distribution, execution-cost model, risk function, or decision threshold.

## 2. Canonical causal chain

```text
Prediction
    |
    +--> Outcome/payoff definition
    |
    +--> Execution economics
    |
    +--> Risk constraints
    |
    v
Expected Economic Value
    |
    v
Decision Utility / Eligibility
    |
    v
Decision
```

## 3. Prediction is not economics

A probability or score alone does not determine whether an action is economically justified.

The economic layer requires an explicitly defined mapping from possible outcomes to economic consequences.

## 4. Outcome state space

A canonical expected-value calculation requires an outcome state space:

```text
Y in OutcomeSpace
```

and a payoff/economic function:

```text
G(Y, action, state)
```

The exact outcome space and payoff function remain UNKNOWN because A26 target/outcome semantics are unresolved.

## 5. Expected economic value

The structural relationship is:

```text
E[G | X]
    =
Σ_y P(Y=y | X) * G(y)
```

for a discrete outcome space, or the corresponding expectation/integral for a continuous outcome.

This formula is only a mathematical structure. It does not define the actual `Y`, probability semantics, payoff units, or distribution.

## 6. Cost-adjusted value

If execution costs are defined as a random or deterministic quantity `C`, the net economic quantity is structurally:

```text
NetValue = GrossValue - C
```

and expected net value must be defined consistently with the timing and conditioning of `C`.

It is invalid to subtract a future realized cost from a contemporaneous decision unless that cost is represented as an ex-ante expectation available at decision time.

## 7. Execution cost dependency

A42 consumes the output of A35:

```text
ExpectedExecutionCost
```

A35 deliberately leaves its numerical model unresolved. Therefore A42 cannot produce a final numerical expected-net-value formula until A35 is resolved.

## 8. Risk dependency

A42 also consumes the applicable risk policy.

A risk constraint may be represented structurally as:

```text
RiskMeasure(action, state) <= RiskLimit
```

but the actual risk measure and limit are not defined by A42.

## 9. Decision utility

Expected monetary value and decision utility are not automatically identical.

A utility function may be defined as:

```text
U = Utility(EconomicOutcome, RiskState, Preferences/Policy)
```

but no utility function is selected here.

If the system ultimately uses expected monetary value directly, that must be an explicit policy choice rather than an implicit assumption.

## 10. Action set

The decision layer requires an explicit action set.

Architectural categories may include:

```text
NO_ACTION
ENTER
EXIT
ADJUST
OTHER_EXPLICIT_ACTION
```

The actual action set depends on the strategy state machine.

## 11. No-action baseline

Every economic decision must define what the action is being compared against.

For an entry decision, the baseline is typically the economic state of not entering, but the exact baseline must be explicitly defined.

A positive expected value relative to an undefined baseline is not a valid decision criterion.

## 12. Opportunity cost

If capital, risk budget, or execution capacity is scarce, selecting one action can prevent another.

The decision utility contract must eventually define whether opportunity cost is included.

No opportunity-cost model is invented here.

## 13. Conditional expectation

Expected value must condition on exactly the information available at decision time:

```text
E[G | I_t]
```

where `I_t` is the canonical information set at time `t`.

Future information cannot enter `I_t`.

## 14. Conditioning population

The economic expectation must use the same population semantics as the prediction it consumes.

A probability conditioned on eligible trades cannot be combined with a payoff distribution estimated from all opportunities without explicitly accounting for the population difference.

## 15. Probability calibration dependency

If A41 supplies a calibrated probability, A42 must use the probability for the exact target event and horizon defined by the label contract.

A calibrated probability for a different event cannot be substituted.

## 16. Distributional versus binary expectation

A binary probability may be sufficient only when the economic payoff conditional on each binary outcome is explicitly defined.

If payoff magnitude varies materially within a class, a binary probability alone may be insufficient for expected economic value.

The required outcome representation remains unresolved.

## 17. Tail outcomes

Expected value can hide asymmetric or heavy-tailed losses.

Therefore decision eligibility cannot rely on expected value alone if the risk policy requires tail constraints.

A42 passes this responsibility to the risk artifact rather than inventing a risk adjustment.

## 18. Execution uncertainty

Expected execution price/cost may itself be uncertain.

The economic layer must eventually define whether it uses:

```text
point estimate
conditional distribution
conservative bound
other explicit representation
```

No choice is frozen.

## 19. Slippage and spread

A theoretical payoff calculated from underlying price movement is not necessarily the realized payoff of an option or other traded instrument.

Instrument economics and execution costs must be mapped consistently.

No point-to-currency or underlying-to-option conversion is invented here.

## 20. Transaction costs

All costs that affect decision economics must be included only if their semantic definitions are known.

Missing cost definitions do not justify assuming zero cost.

If a required cost cannot be estimated causally, the decision may need to fail closed.

## 21. Threshold decision

A generic decision rule may eventually take the form:

```text
Decision = ENTER
if ExpectedUtility(action | I_t) > Utility(NO_ACTION | I_t)
            and
RiskConstraintSatisfied
            and
ExecutionConstraintSatisfied
```

This is an architectural template, not the V2 numerical decision rule.

No threshold is selected.

## 22. Hysteresis / minimum edge

If the final policy requires a minimum economic advantage to prevent noise-driven decisions, that margin is a configurable policy parameter.

It cannot be selected from the final test set.

## 23. Decision monotonicity

If the system defines a scalar economic score, the relationship between score and action must be explicitly specified.

A score increasing numerically does not automatically mean action desirability increases.

## 24. Decision determinism

Given identical:

```text
prediction
information set
cost estimate
risk state
policy versions
```

the decision function must produce the same decision.

## 25. Decision provenance

Every decision must retain:

```text
decision_id
prediction_id
feature_snapshot_id
economic_assessment_id
risk_assessment_id
execution_assessment_id
policy_version
decision_time
reason/status
```

## 26. Rejection reasons

A no-trade result must distinguish at least whether it failed because of:

```text
PREDICTION_INVALID
ECONOMIC_VALUE_INSUFFICIENT
RISK_CONSTRAINT
EXECUTION_CONSTRAINT
CONTRACT_CONSTRAINT
DATA_INVALID
POLICY_DISABLED
OTHER_EXPLICIT_FAILURE
```

Exact categories can be expanded but must remain explicit.

## 27. No silent fallback

If expected economic value cannot be computed because a required input is unknown or invalid, the system must not substitute:

```text
zero cost
zero risk
average payoff
default probability
latest available future value
```

It must fail closed or enter an explicitly defined degraded state.

## 28. Causal information set

The information set `I_t` must include only data and state satisfying A40's availability boundary and A41's model-version/state boundary.

Therefore:

```text
I_t
  subset of
all information eventually known
```

## 29. Expected value versus realized outcome

The decision uses an ex-ante quantity.

The later realized outcome is an observation used for accounting and eventual learning.

```text
ExpectedValue_t
    !=
RealizedOutcome_{t+h}
```

The latter cannot alter the former retrospectively.

## 30. Adversarial attack — favorable future payoff

Invalid:

```text
future maximum favorable excursion
-> expected payoff at entry
```

unless the distribution of that excursion was estimated from causally eligible historical data before the decision.

## 31. Adversarial attack — realized cost subtraction

Invalid:

```text
entry decision
-> observe actual future slippage
-> subtract it from entry-time economics
```

The decision may use only an ex-ante cost estimate available at entry.

## 32. Adversarial attack — binary probability with variable payoff

Invalid:

```text
P(win)=0.65
-> assume one fixed win amount
```

when actual win magnitude is variable and the payoff distribution has not been defined.

## 33. Adversarial attack — risk hidden in expected value

Invalid:

```text
high expected value
-> automatically trade
```

when the action violates an independent risk constraint.

## 34. Adversarial attack — population mismatch

Invalid:

```text
probability estimated on eligible opportunities
+
payoff distribution estimated on all opportunities
-> combine without adjustment
```

The conditioning populations must be compatible.

## 35. Adversarial attack — undefined baseline

Invalid:

```text
ExpectedValue > 0
-> trade
```

if zero does not represent the correct economic value of the no-action alternative.

## 36. Parameter classes

### Frozen architecture

```text
prediction/economics separation
conditional-information requirement
cost separation
risk separation
explicit action set
no-action baseline requirement
decision provenance
explicit rejection reasons
fail-closed missing economics
```

### Learned/configurable

```text
payoff distribution
cost model
utility function
minimum edge/margin
decision threshold
opportunity-cost model
risk-adjustment parameters
```

only after source definitions and walk-forward validation.

### External UNKNOWN

```text
actual payoff function
execution-cost semantics
instrument multiplier/conversion
risk measure
account constraints
```

## 37. Implementation gate

A42 cannot implement a numerical expected-value or utility function until:

```text
A26 target/outcome semantics
A35 execution-cost semantics
A37 accounting/instrument semantics
A32 risk semantics
A41 probability semantics
```

are sufficiently resolved.

The structural decision interface can be implemented independently.

## 38. Completion criterion

A42 becomes `RESOLVED` when the system can reconstruct for every decision:

```text
information set at t
prediction semantics
probability/score semantics
outcome/payoff definition
expected economic value
expected costs
risk constraints
baseline
utility/decision rule
final decision
```

with no future information entering the pre-trade computation.

## ARCHITECTURE STATUS

**FROZEN:** prediction/economics separation; causal information set; explicit action set; no-action baseline requirement; cost/risk separation; decision provenance; explicit rejection reasons; fail-closed missing economics.

**UNRESOLVED:** payoff function; outcome distribution; expected-cost model; utility function; minimum edge; decision threshold; opportunity cost; risk adjustment; instrument economic conversion.

**BLOCKERS:** A26 target/outcome semantics; A32 risk semantics; A35 execution cost semantics; A37 accounting/instrument semantics; A41 probability semantics.

**NEXT ARTIFACT:** A43 — Decision / Eligibility / Risk-Authorization State Machine.
