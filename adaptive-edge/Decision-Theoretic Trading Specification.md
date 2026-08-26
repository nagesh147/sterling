# Decision-Theoretic Trading Specification
## Canonical Economic Decision Layer — Version 1.0

## 1. Objective

The decision engine receives:

`MarketState`

`ProbabilityState`

`EvidenceState`

`CandidateOptions`

`ExecutionState`

`PortfolioState`

`RiskState`

and produces exactly one decision for each candidate:

`NO_TRADE`

`BUY_CE`

`BUY_PE`

or, for an existing position:

`HOLD`

`UPDATE_PROTECTION`

`EXIT`.

The decision engine does not predict the market.

Prediction has already occurred.

Its job is:

`Choose the action with the highest validated risk-adjusted economic value.`

---

# 2. Fundamental Decision Equation

For candidate trade `i`:

`DecisionValue_i = E[NetPnL_i | State_t] - RiskPenalty_i - OpportunityCost_i`.

A trade is eligible only if:

`DecisionValue_i > 0`.

However, expected value alone is insufficient because option returns are asymmetric and distributions have fat tails.

Therefore we use the full conditional outcome distribution:

`F_i(PnL | State_t)`.

---

# 3. Net P&L Distribution

For candidate `i`:

`NetPnL_i`

contains:

`GrossPriceMovement`

plus:

`OptionValueChange`

minus:

`SpreadCost`

minus:

`Slippage`

minus:

`Brokerage`

minus:

`Taxes`

minus:

`ExecutionCost`

minus:

`Financing/other applicable costs`.

The exact cost fields remain dependent on the production execution environment.

---

# 4. Why Gross EV Is Rejected

Suppose:

`GrossEV = +₹500`.

But:

`ExpectedExecutionCost = ₹300`.

Then:

`NetEV = +₹200`.

Now suppose adverse slippage is larger than expected.

The conservative economic value may become:

`<= 0`.

Therefore:

`GrossEV`

can never authorize a trade by itself.

---

# 5. Conservative Expected Value

We define:

`CEV_i = ConservativeExpectedValue(F_i)`.

Conceptually:

`CEV_i = E[NetPnL_i] - UncertaintyPenalty_i - TailRiskPenalty_i`.

The exact penalty functions are learned and validated.

The purpose is to prevent a fragile positive mean from becoming a trade.

---

# 6. Probability Is Only an Input

Suppose:

`P(UP) = 0.80`.

That does not imply:

`BUY_CE`.

We additionally require:

`OptionPayoffDistribution`

`ExecutionCost`

`DownsideDistribution`

`Evidence`

`PortfolioRisk`.

Thus:

`P(UP) → economic model → decision`.

Not:

`P(UP) → BUY`.

---

# 7. Directional Candidate Construction

For every decision timestamp:

`Candidate_UP`

and:

`Candidate_DOWN`

are independently evaluated.

For UP:

`CandidateOptionSet = CE contracts`.

For DOWN:

`CandidateOptionSet = PE contracts`.

Each option receives its own conditional economic distribution.

---

# 8. Option Selection

For each option `j`:

`CEV_j`

is calculated.

The selected option is:

`j* = argmax(CEV_j)`.

But only among:

`EligibleOptions`.

An option with the highest theoretical EV is rejected if:

`ExecutionRisk`

or:

`LiquidityRisk`

or:

`Evidence`

is unacceptable.

---

# 9. Candidate Eligibility

Option `j` is eligible only when:

`DataValid`

AND

`ModelInDomain`

AND

`EvidenceValid`

AND

`CEV_j > 0`

AND

`PortfolioRiskValid`

AND

`ExecutionValid`

AND

`RiskCapacity > 0`.

Otherwise:

`Eligible_j = FALSE`.

---

# 10. No-Trade Is a First-Class Decision

The system always includes:

`NO_TRADE`.

Therefore:

`DecisionSet = {NO_TRADE, BUY_CE, BUY_PE}`.

The system does not need a positive signal to trade.

It needs a positive economic advantage over:

`NO_TRADE`.

---

# 11. Opportunity Cost

Suppose:

`BUY_CE CEV = ₹400`

`BUY_PE CEV = ₹300`.

Normally:

`BUY_CE`.

But suppose capital required for CE prevents another independent opportunity with:

`CEV = ₹700`.

Then the CE trade has negative opportunity value relative to the alternative allocation.

Therefore:

`OpportunityCost`

must be included.

---

# 12. Capital Is Scarce

The system does not optimize every trade independently.

It optimizes the portfolio:

`PortfolioEV`.

For candidate set:

`C = {c1,c2,...,cn}`.

The objective is approximately:

`maximize E[PortfolioNetPnL]`

subject to:

`Risk <= RiskLimit`

`Capital <= CapitalLimit`

`ExecutionCapacity <= ExecutionLimit`.

The exact optimization method remains deliberately model-agnostic.

---

# 13. Incremental Portfolio Value

For candidate `i`:

`IncrementalEV_i`

is not simply:

`StandaloneEV_i`.

It is:

`EV(Portfolio + i) - EV(Portfolio)`.

This accounts for existing positions.

---

# 14. Correlated Exposure

Suppose:

`NIFTY CE`

is already open.

A new:

`BANKNIFTY CE`

may have positive standalone EV.

But if correlation is high:

`IncrementalRisk`

may be substantially larger than its standalone risk.

Therefore:

`StandaloneEV > 0`

does not guarantee:

`IncrementalEV > 0`.

---

# 15. Portfolio Risk

Let portfolio P&L be:

`Π = Σ_i w_i X_i`.

Risk depends on the joint distribution:

`F(X_1,...,X_n)`.

Not simply:

`Σ individual risks`.

This prevents underestimating correlated positions.

---

# 16. Position Size

For candidate `i`, position quantity is determined from:

`RiskBudget_i`

and:

`LossDistribution_i`.

Conceptually:

`Q_i = maximum quantity satisfying portfolio risk constraints`.

This is superior to:

`fixed percentage of capital`.

---

# 17. Why Fixed Position Size Is Rejected

A fixed:

`10 contracts`

can have radically different risk under:

`low volatility`

versus:

`extreme volatility`.

Therefore quantity is endogenous to:

`CurrentRisk`

`OptionPrice`

`ExpectedMAE`

`ExecutionRisk`

`PortfolioExposure`.

---

# 18. Hard Risk Constraint

Regardless of expected value:

`PortfolioTailRisk <= HardLimit`.

Expected profitability can never override this.

This is a permanent invariant.

---

# 19. Asymmetric Payoff

Option trades are not symmetric.

Suppose:

`ProbabilityWin = 0.60`.

Trade A:

`Win = ₹100`

`Loss = ₹80`.

Trade B:

`Win = ₹300`

`Loss = ₹250`.

Their expected values differ.

Therefore probability alone is insufficient.

---

# 20. Full Outcome Distribution

The system estimates:

`P(PnL = x | State_t)`.

In practice this may be represented empirically or parametrically depending on the validated model.

We intentionally do not prescribe the final distributional representation yet.

---

# 21. Tail Risk

Two trades may have the same:

`ExpectedPnL`.

But one has a much larger:

`left-tail loss`.

The system therefore compares:

`ExpectedValue`

and:

`TailRisk`.

A high-mean trade with unacceptable tail behavior is rejected.

---

# 22. Utility Function

A general decision-theoretic representation is:

`U_i = E[NetPnL_i] - λ × Risk_i`.

Where:

`λ`

is the risk-aversion parameter.

However, we should not freeze:

`λ`.

It must be calibrated against the actual capital/risk objective.

---

# 23. Why Utility Is Better Than EV Alone

Consider:

Trade A:

`EV = ₹500`

`TailLoss = ₹1,000`.

Trade B:

`EV = ₹450`

`TailLoss = ₹200`.

If capital preservation matters, B can dominate A.

Therefore:

`maximize EV`

is not necessarily:

`maximize long-term capital growth`.

---

# 24. Risk Measure

The risk measure may incorporate:

`Expected Shortfall`

`Conditional Drawdown`

`MAE`

`Execution Tail Loss`.

The final choice must be empirically validated.

We should not arbitrarily select one metric merely because it is mathematically elegant.

---

# 25. Conservative Decision Rule

For candidate `i`:

`UtilityLowerBound_i`

must exceed the utility of:

`NO_TRADE`.

Therefore:

`Trade_i`

is selected only if:

`LowerBound(U_i) > U_NO_TRADE`.

This incorporates uncertainty.

---

# 26. NO_TRADE Utility

We explicitly define:

`U_NO_TRADE = 0`

after accounting for the opportunity value of retaining capital.

This means a trade must earn more than:

`zero`

after risk and uncertainty.

---

# 27. Capital Retention Has Value

Remaining uncommitted capital retains:

`FutureOpportunityValue`.

Therefore in a high-opportunity environment, taking a mediocre trade can be worse than waiting.

This prevents:

`FOMO-by-algorithm`.

---

# 28. Trade Ranking

For all eligible candidates:

`Score_i = IncrementalUtility_i`.

Sort:

`Score_1 >= Score_2 >= ...`.

The system allocates capital beginning with the highest-value candidate subject to portfolio constraints.

---

# 29. Simultaneous CE and PE

Suppose:

`CEV_CE > 0`

and:

`CEV_PE > 0`.

This does not mean both should be purchased.

We compare:

`IncrementalUtility_CE`

against:

`IncrementalUtility_PE`.

If:

`CE > PE`

then:

`BUY_CE`.

If:

`PE > CE`

then:

`BUY_PE`.

If neither exceeds the required margin:

`NO_TRADE`.

---

# 30. Decision Margin

Suppose:

`CEV_CE = ₹110`

`CEV_PE = ₹105`.

The difference:

`₹5`

may be smaller than model uncertainty.

Therefore choosing CE simply because:

`110 > 105`

is statistically unjustified.

The decision requires:

`UtilityDifference > UncertaintyOfDifference`.

The exact confidence criterion is learned.

---

# 31. Robust Ranking

We therefore rank using:

`LowerBound(Utility_i)`.

Not merely:

`PointEstimate(Utility_i)`.

This protects against choosing a trade whose apparent advantage is statistical noise.

---

# 32. Entry Decision

The canonical entry function is:

```text
If DataUnsafe:
    NO_TRADE

Else if ModelOutOfDomain:
    NO_TRADE

Else if EvidenceInsufficient:
    NO_TRADE

Else calculate CE and PE candidates

For each candidate:
    calculate probability distribution
    calculate option P&L distribution
    calculate execution distribution
    calculate portfolio incremental risk
    calculate conservative utility

Reject invalid candidates

If no candidate remains:
    NO_TRADE

Else choose candidate with highest validated incremental utility

If its utility does not exceed NO_TRADE by required evidence:
    NO_TRADE

Else:
    submit trade
```

This is a mathematical decision sequence, not implementation pseudocode.

---

# 33. Entry Is a Sequential Filter

The decision process is therefore:

`DATA`

→ `PREDICTION`

→ `EVIDENCE`

→ `ECONOMICS`

→ `EXECUTION`

→ `PORTFOLIO`

→ `DECISION`.

A failure at any mandatory layer stops the trade.

---

# 34. Expected Holding Horizon

We explicitly retain the distinction:

`ExpectedHorizon`

is a statistical property of the predicted opportunity.

It is not:

`MaximumHoldingTime`.

For example:

`ExpectedHorizon = 12 minutes`

does not mean:

`Exit at 12 minutes`.

It means:

"The conditional distribution currently assigns substantial probability to the opportunity resolving around this temporal region."

---

# 35. Holding Decision

For an existing position:

`ContinuationValue_t(H)`

represents the expected incremental economic value of remaining invested over future horizon `H`.

The system evaluates:

`Continue`

versus:

`Exit`.

---

# 36. Continuation Value

Define:

`CV_t = E[FutureNetPnL - CurrentExitValue | State_t]`.

If:

`CV_t > 0`

holding may be justified.

If:

`CV_t <= 0`

exit becomes economically attractive.

But:

`CV_t`

must still satisfy:

`Risk constraints`.

---

# 37. Profit Protection

For an existing profitable position:

`PeakPnL_t`

is maintained.

The system estimates:

`FutureGivebackDistribution`.

Then it calculates a validated profit floor.

The profit floor cannot decrease simply because the model predicts continuation.

This preserves the backward-protection mechanism.

---

# 38. Forward and Backward Decision Functions

We now formally separate:

`ForwardModel = FutureOpportunityValue`.

and:

`BackwardModel = ProtectionOfAlreadyEarnedValue`.

The management decision solves:

`maximize FutureOpportunityValue`

subject to:

`GivebackRisk <= allowed boundary`.

This is the rigorous form of our earlier forward/backward idea.

---

# 39. Exit Decision

For an existing position:

`EXIT`

when any mandatory condition is satisfied:

`HardRiskViolation`

or:

`ExecutionEmergency`

or:

`Data/Risk safety condition requiring exit`

or:

`ConservativeContinuationValue <= ExitValue`

or:

`ProfitProtection boundary violated`.

---

# 40. Hold Decision

`HOLD`

only when:

`ContinuationValue > ExitValue`

AND

`Risk constraints valid`

AND

`ProfitProtection valid`.

Otherwise the system must reassess.

---

# 41. Stop Update

A stop update occurs when:

`CandidateProtectionLevel > CurrentStop`.

Then:

`CurrentStop = CandidateProtectionLevel`.

Otherwise:

`CurrentStop unchanged`.

The stop can never move backward.

---

# 42. Stop and Target Are Not Symmetric

A target says:

"Expected value beyond this point may be lower."

A stop says:

"Further downside is no longer acceptable."

Therefore a target is not necessarily a hard exit.

The continuation model can determine whether remaining upside justifies holding.

The risk boundary cannot be similarly overridden.

---

# 43. Dynamic Reclassification

The trade's horizon classification is:

`argmax P(Horizon_k | State_t)`.

But the classification is informational.

It modifies:

`ManagementPolicy`.

It does not directly modify:

`RiskLimit`.

---

# 44. Risk Cannot Expand Because Prediction Improves

Suppose:

`P_continuation ↑`.

The system may conclude:

`ExpectedValue ↑`.

But:

`HardRiskLimit`

does not increase.

This is an explicit invariant.

---

# 45. Risk Can Contract

If:

`Uncertainty ↑`

or:

`ExecutionRisk ↑`

or:

`PortfolioCorrelation ↑`

then:

`AllowedQuantity ↓`.

Therefore:

`Confidence cannot create unlimited leverage`.

---

# 46. Opportunity Competition

Suppose three candidates:

`A: utility = 0.40`

`B: utility = 0.35`

`C: utility = 0.20`.

But A and B are highly correlated.

Holding both may produce:

`PortfolioUtility(A+B) < Utility(A)`.

The system therefore evaluates candidates jointly when required.

This prevents independent ranking from producing excessive correlated exposure.

---

# 47. Capital Allocation

The allocation problem becomes:

`maximize U(Portfolio)`

subject to:

`Capital`

`Risk`

`Liquidity`

`Execution`

and:

`PositionConstraints`.

The system does not need to invest all available capital.

Optimal allocation may be:

`Q = 0`.

---

# 48. Why This Matters for Our ₹25K Starting Capital

Small capital creates an additional constraint:

`MinimumTradableQuantity`.

If the mathematically optimal quantity is:

`0.3 contracts`

but the market requires:

`1 lot`.

The system cannot trade:

`0.3`.

Therefore:

`MinimumLotConstraint`

must be applied before execution.

If one lot violates the risk constraint:

`NO_TRADE`.

---

# 49. No Fractional Risk Illusion

The system must not mathematically claim:

`Risk = ₹400`

when the minimum executable position actually creates:

`Risk = ₹1,200`.

The executable position determines actual risk.

---

# 50. Execution-Aware EV

For option candidate `j`:

`NetEV_j = GrossEV_j - ExpectedExecutionCost_j`.

But because execution cost itself is uncertain:

`ExecutionCost ~ F_Cost`.

Therefore:

`ConservativeNetEV`

must incorporate its uncertainty.

---

# 51. Latency-Aware Decision

If:

`ExpectedEdgeDuration`

is extremely short relative to:

`FeedLatency + OrderLatency + FillLatency`,

then the opportunity may already be gone before execution.

Therefore:

`EdgePersistence > ExecutionLatency`

is a necessary condition for micro-scalping.

Not necessarily a fixed threshold; the relationship is estimated empirically.

---

# 52. Scalping Decision

For very short opportunities:

the dominant variables become:

`EdgeMagnitude`

`EdgePersistence`

`Spread`

`Latency`

`FillProbability`

`MicrostructureState`.

The system must therefore become more conservative as expected opportunity duration approaches execution latency.

---

# 53. Intraday Decision

For longer opportunities:

the dominant variables shift toward:

`DirectionalProbability`

`TrajectoryDistribution`

`RegimePersistence`

`OptionEconomics`

`ExpectedDrawdown`

`ContinuationValue`.

The same decision framework remains intact.

---

# 54. Unified Decision Function

Therefore both strategies use:

`Decision = f(Prediction, Evidence, Economics, Execution, PortfolioRisk)`.

Only the conditional distributions differ by horizon.

This is preferable to building two unrelated strategies.

---

# 55. Micro-Scalp to Intraday

A trade may transition:

`MICRO`

→ `SCALP`

→ `EXTENDED_SCALP`

→ `INTRADAY`.

At each transition:

`Prediction`

`Evidence`

`ExpectedHorizon`

`ContinuationValue`

are recalculated.

Risk limits remain independent.

---

# 56. Intraday to Scalp

The reverse transition is:

`INTRADAY`

→ `EXTENDED_SCALP`

→ `SCALP`

→ `MICRO`.

The system does not assume the original expected horizon remains valid.

---

# 57. Reclassification Does Not Reset the Trade

When:

`INTRADAY → SCALP`

the system does not reset:

`EntryPrice`

`PeakPnL`

`MAE`

`MFE`

`TimeInTrade`.

It merely changes:

`CurrentManagementRegime`.

This preserves historical path information.

---

# 58. Entry Decision Invariant

Once a position is open:

`BUY_CE`

is no longer an available decision.

The decision space becomes:

`HOLD`

`UPDATE_PROTECTION`

`EXIT`.

This prevents accidental repeated entries.

---

# 59. Position Direction Invariant

If:

`PositionDirection = CE`

the management engine cannot suddenly interpret the position as:

`PE`.

A reversal requires:

`EXIT`

then:

`NEW_ENTRY`.

No implicit flip.

---

# 60. Why We Do Not Immediately Add Machine Learning Complexity

The entire decision engine can operate using:

`Empirical distributions`

`Bayesian updating`

`Conditional probabilities`

`Calibration`

`Statistical decision theory`.

No neural network is required.

This keeps:

`Auditability`

`Interpretability`

`Failure analysis`

high.

---

# 61. Canonical Decision Formula

The conceptual production decision is:

`a* = argmax_a LowerBound(U(a | State_t))`

where:

`a ∈ {NO_TRADE, BUY_CE, BUY_PE}`

for a flat account.

For an open position:

`a ∈ {HOLD, UPDATE_PROTECTION, EXIT}`.

Subject to:

`HardRiskConstraints`

`DataConstraints`

`ExecutionConstraints`

`PortfolioConstraints`.

---

# 62. Complete Flat-State Decision

```text
Current State
      |
      v
Is data valid?
      |
     NO ---> NO_TRADE
      |
     YES
      |
      v
Is model in domain?
      |
     NO ---> NO_TRADE
      |
     YES
      |
      v
Is statistical evidence sufficient?
      |
     NO ---> NO_TRADE
      |
     YES
      |
      v
Generate CE and PE distributions
      |
      v
Apply option economics
      |
      v
Apply execution model
      |
      v
Apply portfolio risk
      |
      v
Calculate conservative utility
      |
      v
Compare CE vs PE vs NO_TRADE
      |
      v
Does best trade exceed NO_TRADE?
      |
     NO ---> NO_TRADE
      |
     YES
      |
      v
Position sizing
      |
      v
Executable quantity valid?
      |
     NO ---> NO_TRADE
      |
     YES
      |
      v
BUY CE / BUY PE
```

---

# 63. Complete Open-Position Decision

```text
OPEN POSITION
      |
      v
Data / execution safety?
      |
      v
Hard risk breached?
      |
     YES ---> EXIT
      |
      NO
      |
      v
Profit protection violated?
      |
     YES ---> EXIT
      |
      NO
      |
      v
Calculate continuation value
      |
      v
Calculate future giveback distribution
      |
      v
Reclassify horizon/regime
      |
      v
Is continuation value still superior?
      |
     NO ---> EXIT
      |
     YES
      |
      v
Calculate candidate protection level
      |
      v
CandidateStop > CurrentStop?
      |
     YES ---> UPDATE STOP
      |
      NO
      |
      v
HOLD
```

---

# 64. What Is Now Mathematically Defined

We have now defined the chain:

`Observed Event`

→ `State`

→ `Features`

→ `Probability`

→ `Evidence`

→ `Outcome Distribution`

→ `Economic Value`

→ `Portfolio Increment`

→ `Risk`

→ `Execution`

→ `Decision`.

This is the complete causal decision chain.

---

# 65. What Is Still Deliberately Unfrozen

We still do not invent:

`Risk-aversion coefficient`

`Utility penalty`

`Probability quantiles`

`Evidence thresholds`

`Minimum sample sizes`

`Domain thresholds`

`Execution-cost parameters`

`Position-size coefficients`

`Portfolio correlation thresholds`.

These must come from:

`Walk-forward empirical estimation`

and:

`out-of-sample validation`.

That remains correct.

---

# 66. New Invariants

The decision-theoretic layer adds:

`I21: Positive probability does not imply positive economic value.`

`I22: Positive gross EV does not imply positive net EV.`

`I23: Standalone trade EV does not imply positive incremental portfolio EV.`

`I24: Probability cannot override hard risk.`

`I25: Prediction confidence cannot increase hard risk limits.`

`I26: NO_TRADE always remains available.`

`I27: Minimum executable quantity determines actual risk.`

`I28: A horizon change cannot reset accumulated trade state.`

`I29: Reclassification cannot itself trigger an entry.`

`I30: Position direction cannot change without an explicit exit and new entry.`

---

# 67. Current Canonical Architecture

The complete system now becomes:

```text
TRUE MARKET EVENTS
       |
       v
DATA INTEGRITY
       |
       v
MARKET STATE
       |
       v
FEATURE STATE
       |
       v
PROBABILITY STATE
       |
       v
EVIDENCE STATE
       |
       v
OUTCOME DISTRIBUTION
       |
       v
ECONOMIC VALUE
       |
       v
EXECUTION MODEL
       |
       v
PORTFOLIO RISK
       |
       v
DECISION ENGINE
       |
       +----------+
       |          |
       v          v
   NO TRADE     TRADE
                  |
                  v
             POSITION STATE
                  |
                  v
          FORWARD VALUE
                  +
          BACKWARD PROTECTION
                  |
                  v
               EXIT
                  |
                  v
             REALIZED OUTCOME
                  |
                  v
             LABEL DATA
                  |
                  v
             WALK-FORWARD
                  |
                  v
             NEW MODEL
```

---

# 68. Next Artifact

At this point, the remaining major pre-implementation problem is no longer conceptual prediction or decision logic.

It is **temporal market-state reconstruction**.

We need to specify exactly how raw TrueData events become:

`OrderFlowState`

`PriceState`

`LiquidityState`

`VolatilityState`

`OptionState`

`ExecutionState`

at every event timestamp.

That is where our tick-by-tick premise becomes concrete.

The next artifact should therefore be:

# EVENT → STATE TRANSFORMATION SPECIFICATION

For every incoming event `E_t`, we will define:

`which state variables change`

`which do not change`

`the exact mathematical transformation`

`rolling windows`

`event-time versus clock-time updates`

`session resets`

`missing events`

`out-of-order events`

`tick aggregation`

`volume accumulation`

`flow imbalance`

`price response`

`volatility`

`liquidity`

`option state`

and, critically:

`which resulting variables are allowed to influence the probability engine at that exact timestamp`.

That is the final bridge between our abstract mathematical strategy and the actual TrueData stream. 