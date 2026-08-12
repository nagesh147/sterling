# ECONOMIC DECISION ENGINE MATHEMATICAL SPECIFICATION

## Canonical Economic Decision Contract — Version 1.0

## 1. Objective

The Economic Decision Engine transforms the probability state and current market economics into a candidate trade decision.

Its fundamental transformation is:

```text
Probability State
       +
Outcome Distribution
       +
Option Universe
       +
Execution State
       +
Risk State
       |
       v
Economic Evaluation
       |
       v
NO_TRADE
BUY_CE
BUY_PE
```

The engine does not predict the market.

It evaluates whether an already-estimated opportunity is economically exploitable.

---

# 2. Fundamental Principle

The system must never use:

```text
high directional probability
```

as a sufficient condition for trading.

The complete condition is:

```text
Predictive Edge
+
Sufficient Magnitude
+
Sufficient Persistence
+
Positive Option Economics
+
Positive Net Expected Value
+
Acceptable Downside
+
Executable Liquidity
+
Valid Risk Capacity
```

Only then can a trade become eligible.

---

# 3. Candidate Universe

At timestamp `t`, define:

```text
C_t
=
{
NO_TRADE,
CE_1,
CE_2,
...,
PE_1,
PE_2,
...
}
```

where each option candidate actually exists and is tradable at `t`.

---

# 4. No Universal Strike Rule

The system must not permanently encode:

```text
ATM
+ 1 strike
+ 2 strikes
```

as the option-selection mechanism.

Instead:

```text
OptionUniverse_t
        |
        v
Economic Evaluation
        |
        v
Candidate Ranking
```

determines the appropriate contract.

---

# 5. Underlying Forecast

The economic engine receives:

```text
P(Direction | State_t)
```

and preferably:

```text
P(ReturnMagnitude, Horizon | State_t)
```

rather than a single directional probability.

---

# 6. Directional Candidates

For each candidate:

```text
CE_i
```

the engine evaluates:

```text
P(UnderlyingOutcome | State_t)
```

against the option's payoff characteristics.

For:

```text
PE_i
```

the corresponding downside distribution is evaluated.

---

# 7. Option State

Each candidate option has:

```text
option_price
bid
ask
mid
strike
expiry
time_to_expiry
volume
open_interest
IV_if_available
```

and all other validated fields.

Unavailable fields remain unavailable.

---

# 8. Entry Cost

The economic engine must distinguish:

```text
signal_price
```

from:

```text
executable_entry_price
```

For a buy order, the executable price is based on the offer/liquidity model, not blindly on LTP.

Conceptually:

```text
EntryCost_i
=
ExecutableEntryPrice_i
+
TransactionCosts_i
```

---

# 9. Exit Distribution

The engine needs a distribution for possible future exit values.

For candidate option `i`:

```text
P(OptionExitValue_i | State_t)
```

is derived from the underlying outcome distribution and validated option-price mechanics.

---

# 10. Option Return Distribution

For candidate option `i`:

```text
R_i
=
ExitValue_i / EntryValue_i - 1
```

The system should evaluate the distribution:

```text
P(R_i | State_t)
```

rather than only its expected value.

---

# 11. Gross Expected Return

For candidate `i`:

```text
E[GrossReturn_i | State_t]
=
E[R_i | State_t]
```

before transaction costs.

---

# 12. Transaction Cost

Total expected transaction cost:

```text
E[Cost_i]
=
SpreadCost_i
+
Slippage_i
+
Brokerage_i
+
ExchangeCharges_i
+
Taxes_i
+
OtherApplicableCosts_i
```

The exact applicable components are source/configuration dependencies.

---

# 13. Net Return

The fundamental economic quantity is:

```text
NetReturn_i
=
GrossReturn_i
-
Cost_i
```

and therefore:

```text
E[NetReturn_i]
=
E[GrossReturn_i]
-
E[Cost_i]
```

---

# 14. Positive Expected Value Is Necessary

A candidate cannot be accepted when:

```text
E[NetReturn_i] <= 0
```

unless a separately defined portfolio-level reason exists.

For our initial directional option-buyer strategy:

```text
E[NetReturn_i] <= 0
        ->
NO_TRADE
```

---

# 15. Expected Value Is Not Sufficient

A trade can have:

```text
E[NetReturn] > 0
```

but an unacceptable downside distribution.

Therefore the engine also evaluates:

```text
downside quantiles
probability of loss
maximum expected adverse movement
execution uncertainty
```

---

# 16. Downside Distribution

For candidate `i`:

```text
Loss_i
=
max(-NetReturn_i, 0)
```

The engine evaluates:

```text
P(Loss_i > x)
```

for validated risk levels.

---

# 17. Profit Distribution

Likewise:

```text
Profit_i
=
max(NetReturn_i, 0)
```

The engine evaluates:

```text
P(Profit_i > x)
```

rather than assuming one deterministic target.

---

# 18. Probability of Positive Return

Canonical:

```text
p_positive_i
=
P(NetReturn_i > 0 | State_t)
```

This is different from:

```text
p_up
```

because:

```text
p_up
```

describes the underlying.

Whereas:

```text
p_positive_i
```

describes the actual option trade.

---

# 19. Probability of Meaningful Return

A stronger quantity is:

```text
p_return_above_q_i
=
P(NetReturn_i > q | State_t)
```

where `q` is an economically meaningful return level derived through historical validation.

The threshold is not permanently fixed.

---

# 20. Probability of Losing

```text
p_loss_i
=
P(NetReturn_i < 0 | State_t)
```

This must be retained separately.

---

# 21. Expected Maximum Adverse Excursion

For candidate `i`:

```text
E[MAE_i | State_t]
```

and its distribution are estimated from historical outcomes.

This feeds the risk engine.

---

# 22. Expected Maximum Favorable Excursion

Similarly:

```text
E[MFE_i | State_t]
```

describes the potential favorable excursion.

This becomes important for:

`profit protection`

and:

`exit architecture`.

---

# 23. Opportunity Persistence

The economic engine also receives:

```text
P(Horizon | State_t)
```

because a profitable opportunity that exists for:

`seconds`

has different economics from one that persists for:

`hours`.

---

# 24. Horizon-Adjusted Value

Conceptually:

```text
ExpectedOpportunityValue_i
=
E[NetReturn_i]
weighted by
P(Horizon | State_t)
```

The exact aggregation must avoid double-counting the same future outcome across nested horizons.

---

# 25. No Fixed Trade Duration

The system does not require:

```text
Trade must last X minutes.
```

Instead:

```text
opportunity persistence
```

is probabilistic.

The trade can naturally terminate after:

`two minutes`

or:

`ten minutes`

or:

`thirty minutes`

or:

`intraday`

depending on the evolving state.

---

# 26. Micro-Scalp Eligibility

A short-lived opportunity can qualify if:

```text
expected_net_value
>
validated economic requirement
```

and:

```text
expected opportunity persistence
```

is sufficient relative to execution latency and costs.

There is no arbitrary minimum holding time.

---

# 27. Intraday Eligibility

An opportunity can qualify for a longer continuation path when:

```text
continuation value
```

remains positive across the relevant horizon distribution.

Again:

no fixed duration is required.

---

# 28. Execution Decay

For short-duration opportunities:

the engine must model:

```text
ExpectedEdge(Δt)
```

where `Δt` represents execution delay.

If:

```text
ExpectedEdge(Δt)
<=
ExpectedCost
```

then:

```text
NO_TRADE
```

for that candidate.

---

# 29. Latency-Aware EV

The actual quantity is therefore closer to:

```text
NetEV_i(Δt)
=
GrossEV_i(Δt)
-
ExecutionCost_i(Δt)
```

rather than:

```text
GrossEV_i
```

alone.

---

# 30. Liquidity Constraint

A candidate with excellent predicted return but insufficient liquidity is not necessarily tradable.

Therefore:

```text
TradeEligibility
```

requires:

```text
ExecutionCapability = VALID
```

---

# 31. Spread Constraint

We do not define:

```text spread < fixed number
```

as a universal rule.

Instead evaluate:

```text spread relative to expected opportunity
```

and:

```text spread relative to historical execution distribution.
```

---

# 32. Relative Economic Cost

Conceptually:

```text
CostRatio_i
=
ExpectedExecutionCost_i
/
ExpectedGrossOpportunity_i
```

A candidate becomes less attractive as this ratio increases.

The acceptable relationship is learned/validated.

---

# 33. Option Ranking

Every eligible option receives an economic evaluation:

```text
Candidate_i
    |
    +-- ExpectedNetValue
    +-- Downside
    +-- ProbabilityOfProfit
    +-- ProbabilityOfLoss
    +-- MFE
    +-- MAE
    +-- Horizon
    +-- Liquidity
    +-- ExecutionCost
```

---

# 34. Dominance

Option `A` dominates option `B` if, under the validated comparison framework:

```text
A has no worse economic outcome
and
strictly better outcome
in at least one important dimension.
```

Dominated candidates can be removed.

---

# 35. Pareto Frontier

The remaining candidates form an economic frontier involving:

```text
expected return
risk
liquidity
execution cost
persistence
```

The final choice must be made using the validated objective function.

---

# 36. Why Not Simply Maximize Expected Return?

Because the highest expected return candidate may have:

`extreme downside`

`poor liquidity`

`large spread`

or:

`unstable historical performance`.

Therefore:

```text
Maximum EV
```

is not equivalent to:

```text Best Trade
```

---

# 37. Risk-Adjusted Economic Value

A candidate score may conceptually incorporate:

```text
economic value
-
risk penalty
-
execution penalty
-
uncertainty penalty
```

The exact coefficients are learned/validated.

They must not be invented.

---

# 38. Uncertainty Penalty

Suppose:

```text
E[NetReturn] = +5%
```

but uncertainty is enormous.

The engine should distinguish this from:

```text
E[NetReturn] = +5%
```

with strong historical support.

---

# 39. Conservative EV

A more robust quantity is:

```text
ConservativeEV_i
=
lower_quantile(
    NetReturnDistribution_i
)
```

or an equivalent validated lower-confidence economic measure.

The exact quantile is learned through walk-forward validation.

---

# 40. Economic Evidence

Every candidate receives:

```text
economic_evidence_strength
```

which incorporates:

`sample support`

`state similarity`

`historical stability`

`execution support`

and:

`distribution uncertainty`.

---

# 41. Candidate Rejection

A candidate is rejected if any mandatory condition fails.

Conceptually:

```text
Prediction invalid
        OR
Evidence insufficient
        OR
NetEV <= 0
        OR
Downside unacceptable
        OR
Execution invalid
        OR
Risk unavailable
        OR
Option unavailable
        ->
NO_TRADE
```

---

# 42. Direction Selection

The engine compares the best CE candidate against the best PE candidate.

Define:

```text
BestCEValue
BestPEValue
```

after all costs and risk considerations.

---

# 43. CE Decision

CE becomes eligible only if:

```text
BestCEValue
```

satisfies all mandatory constraints.

---

# 44. PE Decision

PE becomes eligible only if:

```text
BestPEValue
```

satisfies all mandatory constraints.

---

# 45. Competition Between CE and PE

If both qualify:

```text
BestCEValue
vs
BestPEValue
```

must be compared.

The system chooses the candidate with superior validated economic value.

---

# 46. No-Trade Margin

We do not want:

```text
CE EV = +0.01%
PE EV = +0.00%
```

to automatically generate a trade.

The candidate must exceed the economic uncertainty and execution noise sufficiently.

The required margin is learned/validated.

---

# 47. Economic Indifference Region

There is therefore an implicit region:

```text
               CE
                |
      TRADEABLE REGION
                |
         INDIFFERENCE
                |
      NO-TRADE REGION
                |
         INDIFFERENCE
                |
      TRADEABLE REGION
                |
               PE
```

The exact boundaries are empirical.

---

# 48. Probability-Only Trap

Example:

```text
p_up = 0.75
```

but:

```text
option_cost = very high
```

then:

```text
NetEV <= 0
```

and:

```text
NO_TRADE
```

---

# 49. Magnitude Trap

Example:

```text
p_up = 0.65
```

but the expected underlying movement is too small to overcome:

`premium`

`spread`

`theta`

and:

`slippage`.

Again:

```text
NO_TRADE
```

---

# 50. Timing Trap

Example:

```text
p_up = 0.70
```

but the expected move occurs too slowly relative to:

`option decay`

and:

`opportunity persistence`.

The trade can still have:

```text
NetEV <= 0
```

and must be rejected.

---

# 51. Liquidity Trap

Example:

```text
excellent directional forecast
+
poor option liquidity
```

may produce:

```text
poor executable economics.
```

The strategy must reject it.

---

# 52. IV Trap

If option pricing is expensive relative to the forecasted movement:

the directional forecast can be correct while:

```text
option return < 0
```

The economic engine catches this.

---

# 53. Theta Trap

A slow expected move can be economically harmful for an option buyer because:

```text
time passes
+
option value decays
```

The expected option-return distribution must account for this where the available data/model permits.

---

# 54. Gamma Trap

Near-expiry options can exhibit nonlinear response to underlying movement.

The engine must evaluate actual option economics rather than assuming:

```text option_return ≈ delta × underlying_return.
```

That approximation may be useful in some contexts but cannot be treated as universally exact.

---

# 55. Volatility Trap

A volatility increase can help an option buyer.

But a volatility decrease can offset directional correctness.

Therefore:

```text
UnderlyingForecast
```

and:

```text
OptionPricingState
```

remain separate inputs.

---

# 56. Option Payoff Model

At minimum, terminal intrinsic payoff for a call is:

```text
max(S_T - K, 0)
```

and for a put:

```text
max(K - S_T, 0)
```

But our trading horizon is generally before expiration.

Therefore terminal payoff alone is insufficient.

---

# 57. Mark-to-Market Option Value

For intraday exits:

the relevant quantity is:

```text
OptionValue_(t+h)
```

not merely:

```text
ExpirationPayoff.
```

This requires the historical option-price behavior or a rigorously validated option-pricing reconstruction.

---

# 58. Option Model Boundary

If the historical data provides actual option prices at future timestamps:

the preferred baseline is to use:

```text
historically observed option outcomes.
```

rather than relying unnecessarily on a theoretical pricing model.

---

# 59. Why This Is Better

Observed option prices naturally incorporate:

`IV`

`theta`

`gamma`

`skew`

`liquidity`

`market microstructure`.

A theoretical model can miss these.

---

# 60. Synthetic Option Model

A theoretical model may still be used where historical observations are unavailable, but then:

```text
model_assumption
```

must be explicitly represented and validated.

---

# 61. Option Candidate Horizon

For candidate option `i`, the system evaluates possible future states:

```text
t + h
```

where:

```text
h ~ P(Horizon | State_t).
```

The resulting option return distribution is integrated over those possible horizons.

---

# 62. Expected Option Value

Conceptually:

```text
E[V_i]
=
Σ_h
P(h | State_t)
×
E[V_i(t+h) | State_t, h]
```

or the continuous analogue where appropriate.

---

# 63. Net Expected Value

The final economic quantity becomes:

```text
NetEV_i
=
E[V_i_exit]
-
EntryCost_i
-
ExpectedExitCost_i
```

with all relevant transaction costs represented consistently.

---

# 64. Position Sizing Boundary

The Economic Engine identifies:

```text candidate trade
```

but it should not independently override the risk engine.

The risk engine determines:

```text maximum permissible quantity.
```

---

# 65. Position Size

For candidate `i`:

```text
Q_i
=
RiskCapacity
/
RiskPerUnit_i
```

subject to:

`lot size`

`available capital`

`liquidity`

`execution constraints`.

The exact risk-capacity function belongs to the risk specification.

---

# 66. Lot Constraint

For options:

position quantity must satisfy:

```text
Q_i
=
n × lot_size
```

where `n` is an allowed integer quantity.

---

# 67. Position Size Does Not Change Direction

If:

```text risk_capacity
```

is too small to trade one valid lot:

the result is:

```text NO_TRADE
```

not:

`smaller invalid position`.

---

# 68. Capital Constraint

A candidate may be economically attractive but impossible to execute because:

`available capital`

is insufficient.

Then:

```text NO_TRADE.
```

---

# 69. Margin/Capital Treatment

Because our strategy is restricted to option buying:

the capital requirement is fundamentally the option premium plus applicable charges.

The exact accounting must use actual broker/exchange rules once finalized.

---

# 70. Expected Loss Constraint

Even when one-lot capital is affordable:

the candidate must satisfy the validated downside-risk boundary.

---

# 71. Trade Decision Contract

The economic engine outputs:

```text
EconomicDecision_t =
{
    action,
    selected_option_id,
    expected_net_value,
    conservative_net_value,
    probability_of_profit,
    probability_of_loss,
    downside_distribution,
    expected_horizon,
    economic_evidence,
    rejection_reason_if_any
}
```

---

# 72. Rejection Reasons

`NO_TRADE` must be explainable.

Examples:

```text
INSUFFICIENT_DIRECTIONAL_EVIDENCE
INSUFFICIENT_ECONOMIC_EVIDENCE
NEGATIVE_NET_EV
EXCESSIVE_DOWNSIDE
EXECUTION_COST_TOO_HIGH
LIQUIDITY_INSUFFICIENT
OPTION_UNAVAILABLE
CAPITAL_INSUFFICIENT
RISK_CAPACITY_INSUFFICIENT
MODEL_DEGRADED
DATA_DEGRADED
```

---

# 73. Multiple Rejection Reasons

A decision may have multiple failed conditions.

The system should retain:

```text
all failed gates
```

rather than only the first failure.

This makes research much easier.

---

# 74. Decision Priority

The gates are conceptually evaluated in this order:

```text
Data validity
      |
Model validity
      |
Directional evidence
      |
Economic distribution
      |
Execution
      |
Risk
      |
Candidate comparison
      |
Final action
```

The exact computational ordering can later be optimized without changing semantics.

---

# 75. Final Decision

The complete decision is:

```text
IF
    data valid
AND model supported
AND economic candidate exists
AND candidate has positive validated net value
AND downside is acceptable
AND execution is feasible
AND risk capacity exists
THEN
    choose best eligible candidate
ELSE
    NO_TRADE
```

---

# 76. No Forced Trading

The system is not required to produce:

`BUY CE`

or:

`BUY PE`

every time the market moves.

The default state is:

```text
NO_TRADE
```

---

# 77. Trade Frequency Is an Output

We do not optimize:

```text
number of trades per day.
```

Trade frequency emerges from:

```text
market opportunity
+
economic conditions
+
execution conditions
+
risk constraints.
```

---

# 78. Scalping Frequency

If the market produces many short-lived positive-EV opportunities:

the strategy can generate many trades.

If execution costs eliminate them:

the strategy should produce few or zero trades.

This is precisely what we want.

---

# 79. Intraday Frequency

Likewise:

longer opportunities appear only when:

`probability`

`magnitude`

`persistence`

and:

`economic value`

support continuation.

---

# 80. Micro-to-Intraday Transition

The economic engine does not permanently classify a trade as:

`SCALP`

or:

`INTRADAY`.

It continuously reevaluates:

```text
continuation_value
```

using the updated state.

---

# 81. Important Separation

A mode transition:

```text
SCALP -> INTRADAY
```

does not mean:

```text risk tolerance increases.
```

It means:

```text continuation economics have changed.
```

---

# 82. Intraday-to-Scalp Transition

If the continuation distribution deteriorates:

```text
INTRADAY -> SCALP
```

can occur.

This may cause:

`earlier exit`

or:

`tighter protection`.

---

# 83. Intraday-to-No-Trade

For an open trade:

the correct state is not literally:

`NO_TRADE`.

It is:

```text EXIT
```

because a position already exists.

---

# 84. Entry Decision Versus Position Decision

This distinction is important:

```text
NO_TRADE
```

applies to:

`new-entry eligibility`.

For an existing position:

```text
HOLD
or
EXIT
```

is the relevant decision.

---

# 85. Entry Economic Engine

At flat state:

```text
NO_TRADE
BUY_CE
BUY_PE
```

are valid strategy outputs.

---

# 86. Position Economic Engine

With an open position:

```text
HOLD
EXIT
```

are the relevant economic outputs.

A new opposite trade is not automatically opened.

---

# 87. Reversal

A reversal requires a separate validated condition.

The system must not:

```text EXIT CE
+
immediately BUY PE
```

merely because:

`p_down > p_up`.

The exit decision and new-entry decision remain separate.

---

# 88. Hysteresis

This prevents:

```text
CE
PE
CE
PE
```

oscillation caused by tiny probability changes.

Transition sensitivity is learned/validated.

---

# 89. Economic Decision Stability

If:

```text NetEV_CE
```

and:

```text NetEV_PE
```

are statistically indistinguishable:

the preferred action should generally be:

```text NO_TRADE
```

rather than forcing a marginal choice.

---

# 90. Economic Uncertainty

If the confidence interval around:

```text NetEV
```

contains zero:

the candidate may be considered economically unsupported.

The exact statistical criterion is learned/validated.

---

# 91. Robustness Requirement

The chosen candidate should not depend on an extremely narrow parameter setting.

If tiny changes in:

`historical window`

`execution assumption`

or:

`probability estimate`

flip:

```text BUY_CE
```

to:

```text NO_TRADE
```

the opportunity should be classified as fragile.

---

# 92. Fragility

Canonical:

`economic_fragility`.

A fragile candidate may be rejected even when its point estimate is positive.

---

# 93. Stress Testing

Each candidate must be evaluated under adverse execution assumptions:

```text
higher spread
higher slippage
higher latency
lower liquidity
```

If the trade ceases to be profitable immediately:

the edge may not be robust enough.

---

# 94. Cost Stress

The strategy should survive reasonable perturbations around the estimated execution cost.

The exact stress distribution comes from historical execution data.

---

# 95. Probability Stress

Likewise, evaluate the trade under:

```text lower directional probability
```

and:

```text lower magnitude forecast.
```

A trade requiring perfect prediction is not robust.

---

# 96. Option Stress

Evaluate:

```text worse IV movement
worse exit spread
worse option liquidity
```

where historically realistic.

---

# 97. Economic Robustness Score

A candidate can receive a research-only metric:

```text
economic_robustness
```

summarizing how much adverse perturbation it can tolerate before:

```text NetEV <= 0.
```

This is not itself a trading signal.

---

# 98. Candidate Ranking

The ranking process is:

```text
Generate candidates
       |
       v
Remove invalid candidates
       |
       v
Calculate net distributions
       |
       v
Apply risk constraints
       |
       v
Apply execution constraints
       |
       v
Apply uncertainty requirements
       |
       v
Rank survivors
       |
       v
Select best eligible candidate
```

---

# 99. Mathematical Output

The economic engine's canonical output is:

```text
D_t
=
{
action,
candidate,
NetEV,
ConservativeEV,
P(Profit),
P(Loss),
MAE_distribution,
MFE_distribution,
Horizon_distribution,
execution_cost,
economic_evidence,
fragility
}
```

---

# 100. Exact Decision Semantics

For a flat portfolio:

```text
D_t = BUY_CE
```

means:

```text
At timestamp t,
the selected CE candidate is economically superior
to every admissible alternative and satisfies
all mandatory constraints.
```

Similarly:

```text
D_t = BUY_PE
```

has the corresponding meaning.

---

# 101. NO_TRADE Semantics

```text
D_t = NO_TRADE
```

means:

```text
No candidate currently satisfies the complete
economic, execution, evidence, and risk contract.
```

It does not mean:

```text market will not move.
```

---

# 102. Critical Invariant

A market forecast can be correct while:

```text
action = NO_TRADE.
```

This is not a failure.

It is often the correct behavior.

---

# 103. Example

Suppose:

```text
P(UP) = 0.70
```

but:

```text expected underlying movement = small
option premium = high
spread = high
theta cost = significant
```

Then:

```text
NetEV_CE < 0
```

and:

```text
NO_TRADE.
```

That is correct.

---

# 104. Opposite Example

Suppose:

```text
P(UP) = 0.62
```

but:

```text expected magnitude = large
option cost = low
execution = strong
downside = acceptable
```

Then:

```text
NetEV_CE > 0
```

and the CE can become eligible.

Therefore:

```text probability alone
```

does not determine the trade.

---

# 105. Most Important Mathematical Object

The most important object leaving this layer is not:

```text p_up.
```

It is:

```text
P(NetReturn_i | State_t, Execution_t)
```

for each candidate option.

That is what allows the system to make an economically meaningful decision.

---

# 106. Complete Economic Architecture

```text
                    PROBABILITY STATE
                           |
             +-------------+-------------+
             |                           |
             v                           v
      Direction Distribution       Horizon Distribution
             |                           |
             +-------------+-------------+
                           |
                           v
                   Underlying Outcome
                      Distribution
                           |
                           v
                    Option Candidates
                           |
                           v
                  Option Outcome Model
                           |
                  +--------+--------+
                  |                 |
                  v                 v
             Gross Return      Downside
                  |                 |
                  +--------+--------+
                           |
                           v
                    Execution Costs
                           |
                           v
                     Net Return
                     Distribution
                           |
                           v
                    Economic Gates
                           |
                           v
                    Risk Constraints
                           |
                           v
                  Candidate Ranking
                           |
                           v
                 NO_TRADE / CE / PE
```

---

# 107. What Is Frozen

The architecture is now fixed around:

```text
candidate-based evaluation
+
full return distribution
+
execution-adjusted economics
+
uncertainty
+
risk separation
+
dynamic horizon
+
CE/PE competition
+
default NO_TRADE
```

---

# 108. What Remains Empirical

We intentionally do not freeze:

```text
exact economic EV threshold
exact downside quantile
exact probability requirement
exact option candidate universe
exact strike-selection representation
exact execution-cost model
exact slippage model
exact horizon aggregation
exact uncertainty penalty
exact robustness requirement
exact candidate-ranking function
```

These must be discovered through walk-forward research.

---

# 109. Why We Refuse Fixed Numbers

A fixed rule such as:

```text
P(UP) > 0.65
```

could be excellent in one market regime and useless in another.

Likewise:

```text spread < 2%
```

has no universal meaning across:

`different options`

`different prices`

`different liquidity`

`different volatility`.

Our architecture therefore compares quantities against their empirically validated distributions.

---

# 110. Dynamic Economic Threshold

The eventual threshold can conceptually be:

```text
RequiredEV_t
=
f(
uncertainty_t,
execution_t,
volatility_t,
liquidity_t,
evidence_t,
risk_state_t
)
```

rather than:

```text
RequiredEV = fixed_constant.
```

The function itself must be learned and validated.

---

# 111. No Circularity

The economic threshold cannot depend on:

```text realized future trade outcome.
```

It may depend on:

```text current uncertainty
current execution
current risk
historical validated distributions
```

only.

---

# 112. Final Boundary

This layer produces:

```text
TRADE CANDIDATE
```

but does not yet manage the position after entry.

That belongs to the already-defined dynamic position/risk architecture.

The next layer therefore reconnects this economic decision to the live state machine.

---

# 113. Next Artifact

The next logical artifact is:

# POSITION INITIATION AND ENTRY STATE SPECIFICATION

That specification will define, at the exact event level:

```text
NO_POSITION
     |
     v
SIGNAL_DETECTED
     |
     v
ECONOMIC_VALIDATION
     |
     v
ENTRY_AUTHORIZATION
     |
     v
ORDER_SUBMITTED
     |
     v
ORDER_FILLED
     |
     v
POSITION_ACTIVE
```

and, critically, exactly what becomes immutable at entry:

```text
entry timestamp
entry price
initial risk boundary
initial probability snapshot
initial economic snapshot
selected option
position quantity
trade mode
model version
```

It will also define what remains dynamically recalculable immediately after entry, which is the bridge into our micro-scalp -> scalp -> extended-scalp -> intraday architecture.