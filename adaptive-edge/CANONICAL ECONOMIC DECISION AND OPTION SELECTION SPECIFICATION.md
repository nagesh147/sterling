# CANONICAL ECONOMIC DECISION AND OPTION SELECTION SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines how the statistical state is converted into an economically valid trading decision.

The decision function is:

```text
Market State
    +
Probability Distribution
    +
Option State
    +
Execution Cost
    +
Risk Constraints
        ↓
Economic Evaluation
        ↓
Option Selection
        ↓
NO_TRADE / BUY_CE / BUY_PE
```

The system must never use:

```text "probability is high" id="z2m7n4"
```

as sufficient justification for entering a trade.

---

# 2. Economic Decision Principle

The strategy trades only when:

```text ExpectedNetEconomicValue
>
RequiredEconomicCompensation
```

subject to:

```text probability validity
option validity
execution feasibility
risk authorization
```

If any mandatory condition fails:

```text NO_TRADE
```

---

# 3. Directional Probability

Let:

```text p_up(t) id="b7nq0m"
=
P(Underlying moves in the defined favorable direction | F_t)
```

and:

```text p_down(t)
=
1 - p_up(t)
```

where the outcome definition is exactly the one established by the label specification.

These are probabilities of the underlying outcome, not probabilities of option profitability.

---

# 4. Option Profitability Is a Separate Random Variable

For a candidate option `o`:

```text Y_o(T) id="m9k5f1"
=
Net economic outcome of buying option o
```

The option's future outcome depends on more than direction.

It may depend on:

```text underlying movement
time
option price
volatility
spread
execution
expiry
strike
```

Therefore:

```text P(UnderlyingUp)
```

cannot simply be substituted for:

```text P(OptionProfit > 0).
```

This distinction is fundamental.

---

# 5. Candidate Option Set

At decision time `t`, define:

```text O_t = {o_1, o_2, ..., o_n} id="r9w3x8"
```

as the set of options satisfying the initial structural eligibility rules.

Each candidate must have valid:

```text InstrumentID
OptionType
Strike
Expiry
Bid
Ask
Liquidity information
Timestamp
```

where available.

---

# 6. Candidate Eligibility

An option is eligible only if:

```text valid instrument
+
valid market data
+
valid contract
+
acceptable liquidity
+
acceptable execution conditions
+
acceptable time-to-expiry
+
risk compatibility.
```

The exact numerical thresholds remain unfrozen.

---

# 7. Reference Entry Price

For a market buy, the default economic reference is the:

```text current executable ask price id="7m4p8q"
```

subject to the eventual execution policy.

For a sell/exit, the corresponding executable bid is relevant.

This is deliberately different from:

```text last traded price.
```

---

# 8. Spread

For candidate option `o`:

```text Spread_o
=
Ask_o - Bid_o
```

and relative spread:

```text RelativeSpread_o
=
(Ask_o - Bid_o) / ReferencePrice_o
```

The exact reference-price convention will be frozen with the execution model.

---

# 9. Entry Cost

The economic entry cost contains at least:

```text spread component
+
brokerage/transaction charges
+
taxes/fees where applicable
+
expected market impact
+
slippage.
```

Exact external fee mappings remain pending.

---

# 10. Exit Cost

Expected exit cost must also be included.

Therefore:

```text ExpectedRoundTripCost_o
=
ExpectedEntryCost_o
+
ExpectedExitCost_o
```

A strategy that only models entry cost is incomplete.

---

# 11. Net Outcome

For candidate option `o`:

```text NetOutcome_o
=
GrossOptionOutcome_o
-
EntryCost_o
-
ExitCost_o
-
OtherApplicableCosts_o
```

The distribution of `NetOutcome_o` is the economically relevant distribution.

---

# 12. Expected Net Value

The canonical quantity is:

```text E[NetOutcome_o | F_t] id="f8q1wd"
```

not:

```text E[UnderlyingMove | F_t].
```

The underlying prediction is an input.

The tradable object is the option.

---

# 13. Conditional Option Outcome Distribution

For each candidate option:

```text F_o(y | F_t)
```

represents the estimated distribution of future net economic outcome.

This may be constructed empirically from historically comparable option situations.

The system must not assume a theoretical option-pricing distribution merely because one is mathematically convenient.

---

# 14. Intrinsic and Extrinsic Components

For an option:

```text OptionPremium
=
IntrinsicValue
+
ExtrinsicValue
```

The system may track these components for diagnostics.

However, the trading decision must ultimately operate on:

```text expected net economic outcome.
```

---

# 15. Time Decay

For a long option position, passage of time can reduce economic value even if the underlying does not move.

Therefore:

```text ExpectedHoldingTime
```

is an economic input.

It must remain distinct from:

```text LabelHorizon
ActualHoldingTime.
```

---

# 16. Volatility Exposure

Option outcome depends on changes in implied volatility as well as underlying movement.

Therefore, where data permits, candidate evaluation should account for:

```text current volatility state
expected volatility behavior
option sensitivity to volatility.
```

No assumption is made that implied volatility remains constant.

---

# 17. Greeks

Greeks may be used as explanatory variables or model inputs:

```text Delta
Gamma
Theta
Vega
```

but they are not automatically required.

Their inclusion must earn its place through empirical validation.

---

# 18. Option Selection Objective

The selected option is:

```text o* = argmax_o Utility(o | F_t) id="d4n7b1"
```

subject to all hard constraints.

The exact utility function is deliberately defined below before numerical parameters are selected.

---

# 19. Economic Utility

The baseline utility is based on:

```text expected net outcome
+
downside distribution
+
execution feasibility
+
risk.
```

A candidate cannot win merely because it has the highest raw expected return.

---

# 20. Profit Floor

For candidate `o`:

```text Q_q(NetOutcome_o | F_t)
```

represents the selected lower quantile.

This is the canonical profit-floor measure.

The quantile `q` remains:

```text UNFROZEN.
```

---

# 21. Profit-Floor Requirement

A candidate may require:

```text ProfitFloor_o > minimum acceptable economic floor.
```

The exact floor remains learned/configured.

This protects against candidates whose expected value is positive only because of a small number of extreme historical winners.

---

# 22. Expected Value Alone Is Insufficient

Consider:

```text Candidate A:
high mean
large downside tail

Candidate B:
lower mean
substantially better downside profile.
```

The system cannot automatically choose A.

The full conditional outcome distribution must be considered.

---

# 23. Tail Risk

The economic evaluator may consider:

```text lower quantile
Expected Shortfall
Maximum Adverse Excursion distribution
probability of loss
```

subject to sufficient historical evidence.

---

# 24. Probability of Positive Net Outcome

For candidate `o`:

```text P(NetOutcome_o > 0 | F_t)
```

is a useful secondary quantity.

It is not equivalent to:

```text P(UnderlyingDirectionCorrect).
```

---

# 25. Break-Even Probability

If the option has asymmetric payoff and known costs, the economically relevant threshold is:

```text P_required
```

such that:

```text E[NetOutcome_o | F_t] > 0
```

under the chosen outcome model.

The threshold is therefore option-specific.

There is no universal:

```text "70% probability means trade."
```

rule.

---

# 26. Economic Edge

Define:

```text EconomicEdge_o
=
ExpectedNetValue_o
-
RequiredEconomicValue_o
```

Trade eligibility requires:

```text EconomicEdge_o > 0.
```

The minimum positive margin remains unfrozen.

---

# 27. Edge Must Cover Model Error

A tiny estimated positive edge is not necessarily actionable.

Therefore:

```text RequiredEconomicMargin
```

must account for uncertainty in:

```text probability estimation
option outcome estimation
execution cost estimation.
```

The exact uncertainty-adjusted threshold remains a research parameter.

---

# 28. Conservative Expected Value

Where statistical uncertainty is material, the system may use:

```text conservative expected value
```

rather than the point estimate.

Conceptually:

```text E_conservative[Y]
```

is a lower-confidence estimate of expected outcome.

The precise statistical construction remains unfrozen.

---

# 29. CE Versus PE

The direction engine determines the preferred underlying direction.

Then:

```text UP thesis → CE candidates
DOWN thesis → PE candidates
```

The option-selection engine determines which candidate best expresses that thesis economically.

---

# 30. No Cross-Direction Substitution

A strong bullish probability does not permit:

```text BUY_PE
```

unless the statistical and economic state explicitly changes to a bearish thesis.

The option selector cannot override directional state.

---

# 31. Directional Probability Threshold

A minimum directional evidence requirement may exist:

```text p_up >= θ_up
```

or:

```text p_down >= θ_down.
```

The exact thresholds are:

```text UNFROZEN.
```

They must be learned/validated.

---

# 32. Directional Ambiguity

If:

```text p_up
```

and:

```text p_down
```

do not produce sufficient directional separation:

```text NO_TRADE.
```

The system does not force a directional choice.

---

# 33. Candidate Ranking

Eligible candidates are ranked according to:

```text EconomicUtility_o.
```

The ranking must be deterministic.

Ties require a predefined tie-breaking rule.

---

# 34. Tie-Breaking

A tie may be resolved using predetermined secondary criteria such as:

```text lower execution cost
higher liquidity
lower downside uncertainty
closer data freshness
```

The rule must be fixed before forward testing.

---

# 35. Liquidity Constraint

A candidate option may be rejected when:

```text spread too large
available quantity insufficient
quote stale
market depth inadequate
```

subject to validated thresholds.

---

# 36. Stale Quote Rule

An option quote is valid only if its timestamp satisfies:

```text DecisionTimestamp - QuoteTimestamp
<= MaximumQuoteAge.
```

The exact maximum age remains:

```text UNFROZEN.
```

---

# 37. Missing Quote

If required executable pricing is unavailable:

```text candidate = INVALID.
```

The system does not estimate a favorable fill from:

```text last traded price.
```

unless the execution model explicitly defines such a procedure.

---

# 38. Spread Expansion

If the spread widens after the original evaluation but before execution:

```text the original decision may become economically invalid.
```

The decision must not blindly execute using obsolete economics.

---

# 39. Decision Revalidation

Immediately before execution, the system may perform:

```text execution-validity revalidation.
```

This checks:

```text quote freshness
spread
option availability
risk state
operational state
```

It does not rewrite the original statistical decision.

---

# 40. Revalidation Failure

If the trade no longer satisfies the execution contract:

```text OrderIntent = CANCELLED/EXPIRED
```

and:

```text no position is opened.
```

---

# 41. Risk Constraint

Economic attractiveness cannot override risk limits.

Therefore:

```text EconomicEdge > 0
```

does not imply:

```text AuthorizedQuantity > 0.
```

Both conditions are independently required.

---

# 42. Position Sizing

For candidate `o`:

```text Quantity_o
=
RiskBudget
/
RiskPerUnit_o
```

subject to:

```text lot size
maximum position
capital availability
execution constraints.
```

The exact risk-budget and sizing formulation remain governed by the separate risk specification.

---

# 43. Lot Constraint

Actual quantity must satisfy:

```text Quantity ∈ valid lot increments.
```

The system must round in the direction that does not violate the risk limit.

---

# 44. Zero-Quantity Result

If the economically/risk-authorized quantity is:

```text 0
```

then:

```text NO_TRADE.
```

The system does not round zero-risk capacity upward merely to produce a trade.

---

# 45. Capital Constraint

The candidate must satisfy the applicable:

```text available capital
margin/capital rules
broker constraints.
```

Exact broker semantics remain external.

---

# 46. Cost-to-Edge Ratio

The system should explicitly record:

```text CostToEdgeRatio
=
ExpectedExecutionCost
/
ExpectedGrossEdge.
```

A candidate whose costs consume most of its gross edge should be rejected if the validated threshold requires it.

---

# 47. Expected Value Decomposition

For auditability:

```text ExpectedGrossValue
        -
ExpectedSpreadCost
        -
ExpectedSlippage
        -
ExpectedFees
        -
ExpectedOtherCosts
        =
ExpectedNetValue.
```

Every component must be separately recorded.

---

# 48. Option Selection Record

The selected candidate must record:

```text CandidateSetVersion
SelectedOption
SelectionTimestamp
ExpectedGrossValue
ExpectedExecutionCost
ExpectedNetValue
ProfitFloor
ProbabilityOfPositiveOutcome
RiskPerUnit
EconomicUtility
SelectionReason
```

This makes the selection auditable.

---

# 49. No-Trade Record

If no candidate passes:

```text NO_TRADE
```

with a structured reason such as:

```text NO_DIRECTIONAL_EDGE
INSUFFICIENT_STATISTICAL_EVIDENCE
NO_ECONOMIC_EDGE
PROFIT_FLOOR_FAILURE
OPTION_INVALID
LIQUIDITY_FAILURE
COST_FAILURE
RISK_FAILURE
DATA_STALE
OPERATIONAL_FAILURE.
```

---

# 50. Decision Function

Conceptually:

```text
Decision(F_t)
=
NO_TRADE
```

unless all required conditions hold.

Otherwise:

```text Direction = UP
    ↓
Select best eligible CE
    ↓
BUY_CE
```

or:

```text Direction = DOWN
    ↓
Select best eligible PE
    ↓
BUY_PE.
```

---

# 51. Formal Decision Predicate

For candidate `o`:

```text TradeEligible(o,t)
=
P_valid
AND
Direction_valid
AND
Option_valid
AND
Liquidity_valid
AND
Cost_valid
AND
ExpectedNetValue_valid
AND
ProfitFloor_valid
AND
Risk_authorized
AND
Operationally_valid.
```

If:

```text TradeEligible = FALSE
```

then:

```text NO_TRADE.
```

---

# 52. Candidate Selection Function

Among valid candidates:

```text o*
=
argmax Utility(o,t)
```

subject to:

```text TradeEligible(o,t) = TRUE.
```

---

# 53. Utility Must Not Be Learned From Final P&L Directly

The utility function itself is part of the strategy architecture.

Its structure cannot be repeatedly altered until historical P&L improves.

Any alternative utility formulation becomes a separate research candidate.

---

# 54. Option Selection Does Not Change Direction

The option selector is subordinate to the directional thesis.

Its job is:

```text express the existing directional thesis efficiently.
```

It does not independently create a new directional thesis.

---

# 55. Probability and Option Selection Separation

The probability engine answers:

```text "What does the underlying most likely do?" id="3e8l9j"
```

The option engine answers:

```text "Which eligible option best monetizes that thesis after costs and risk?" id="xq2tdu"
```

These are separate mathematical questions.

---

# 56. Economic State Transition

The economic engine therefore consumes:

```text ProbabilityState
+
OutcomeDistribution
+
OptionState
+
ExecutionCostModel
+
RiskConstraints
```

and produces:

```text EconomicState.
```

---

# 57. Economic State Does Not Execute

The economic engine cannot:

```text submit order
modify position
modify risk budget.
```

It only evaluates economic attractiveness.

---

# 58. Decision Engine Does Not Estimate

The decision engine consumes the already-estimated:

```text probability
distribution
economic state
```

It does not secretly refit statistical parameters.

---

# 59. Parameter Separation

The following remain independently versioned:

```text StatisticalModelVersion
EconomicModelVersion
ExecutionCostModelVersion
RiskPolicyVersion
```

A change to one does not silently alter the others.

---

# 60. Model Uncertainty

If the estimated economic value is smaller than its estimation uncertainty:

```text economic evidence is insufficient.
```

The baseline response is:

```text NO_TRADE.
```

This prevents the system from treating statistical noise as economic edge.

---

# 61. Adversarial Economic Test

The decision architecture must survive:

```text high probability
+
terrible option spread.
```

Expected result:

```text NO_TRADE.
```

---

# 62. Adversarial Direction Test

The architecture must survive:

```text strong bullish probability
+
CE candidate economically poor
+
another CE candidate economically valid.
```

Expected result:

```text select economically superior CE.
```

Not:

```text arbitrary CE.
```

---

# 63. Adversarial Cost Test

If:

```text GrossEdge = positive
```

but:

```text NetEdge <= 0
```

then:

```text NO_TRADE.
```

---

# 64. Adversarial Probability Test

If:

```text Probability = high
```

but:

```text sample evidence insufficient
```

then:

```text NO_TRADE.
```

---

# 65. Adversarial Liquidity Test

If:

```text ExpectedValue > 0
```

but executable liquidity fails:

```text NO_TRADE.
```

---

# 66. Adversarial Risk Test

If:

```text EconomicEdge > 0
```

but:

```text AuthorizedRisk = 0
```

then:

```text NO_TRADE.
```

---

# 67. Adversarial Stale-Data Test

If:

```text underlying state valid
```

but:

```text option quote stale,
```

the candidate is invalid.

The system must not substitute a stale quote merely because it produces favorable economics.

---

# 68. Adversarial Extreme-Winner Test

If a candidate's positive expected value is caused primarily by a small number of extreme historical winners:

```text ProfitFloor / tail analysis
```

should expose this.

The candidate may fail the economic robustness requirement.

---

# 69. Economic Invariants

```text ECO-001 id="wmv5w2"
Probability of underlying direction is not probability of option profitability.

ECO-002
Expected gross value is distinct from expected net value.

ECO-003
All material execution costs must be represented.

ECO-004
Option selection cannot override directional state.

ECO-005
Statistical significance does not imply economic eligibility.

ECO-006
Economic edge cannot override risk constraints.

ECO-007
A stale executable quote cannot be treated as current.

ECO-008
Missing executable information cannot silently become zero cost.

ECO-009
Position size cannot exceed risk authorization.

ECO-010
NO_TRADE is a valid terminal decision.

ECO-011
Decision revalidation cannot rewrite the historical decision.

ECO-012
Option candidates are evaluated using information available at decision time.

ECO-013
Economic utility cannot be repeatedly tuned against the final holdout.

ECO-014
Every selected option has an auditable economic justification.
```

---

# 70. Numerical Parameters Still Unfrozen

We deliberately have not chosen:

```text directional probability threshold
profit-floor quantile
minimum economic edge
maximum spread
maximum quote age
minimum liquidity
cost tolerance
uncertainty penalty
utility weights
risk-adjusted utility parameters.
```

These remain walk-forward research quantities.

---

# 71. Architecture Status

The following is now structurally complete:

```text Probability Architecture          COMPLETE
Conditional Distribution Architecture COMPLETE
Calibration Architecture              COMPLETE
Economic Evaluation Architecture      COMPLETE
Option Selection Architecture         COMPLETE
NO_TRADE Logic                         COMPLETE
CE/PE Decision Contract                COMPLETE
```

The numerical values remain intentionally unfrozen.

---

# 72. Next Artifact

The next artifact should be:

# CANONICAL POSITION SIZING AND RISK BUDGET SPECIFICATION

That document will define the final bridge from:

```text economically valid opportunity
        ↓
risk authorization
        ↓
quantity
        ↓
lot sizing
        ↓
initial protection
        ↓
maximum permissible loss
```

It will also formally enforce the principle we established earlier:

```text dynamic management mode
        !=
dynamic risk authorization
```

and ensure that becoming more confident or switching management modes can never silently increase risk or give back previously established protection.