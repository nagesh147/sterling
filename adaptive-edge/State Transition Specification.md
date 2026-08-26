# State Transition Specification
## Canonical Event-Driven State Machine — Version 1.0

### 1. Purpose

This specification defines the exact transition behavior of the trading system.

The system is modeled as a temporal state machine:

`State_t + Event_(t+1) -> State_(t+1)`

Every transition must be deterministic given:

`CurrentState`

`IncomingEvent`

`CurrentModelVersion`

`CurrentExecutionState`.

The system must never require future information to determine the next state.

---

# 2. Global State Model

At event time `t`, the complete system state is:

`Ω_t = {M_t, F_t, P_t, C_t, R_t, X_t, L_t}`

where:

`M_t = MarketState`

`F_t = FeatureState`

`P_t = ProbabilityState`

`C_t = CandidateTradeState`

`R_t = RiskState`

`X_t = PositionState`

`L_t = LearningState`.

If there is no open position:

`X_t = NULL`.

The fundamental transition is:

`Ω_(t+1) = T(Ω_t, E_(t+1))`.

---

# 3. State Machine

The top-level states are:

`S0 = NO_TRADE`

`S1 = CANDIDATE`

`S2 = SIGNAL`

`S3 = ENTRY_PENDING`

`S4 = OPEN`

`S5 = EXIT_PENDING`

`S6 = CLOSED`

`S7 = OUTCOME_PENDING`

`S8 = LEARNING_ELIGIBLE`.

The normal lifecycle is:

`S0 → S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8`

A trade does not necessarily pass through every state on every event.

For example:

`NO_TRADE → CANDIDATE`

may occur on one event and immediately return to:

`NO_TRADE`

on the next event if the opportunity disappears.

---

# 4. State S0 — NO_TRADE

Definition:

No position is open and no currently validated trade candidate exists.

Conditions:

`Position = NULL`

and:

`EntryDecision = NO_TRADE`.

The system continuously evaluates incoming events.

Transition:

`NO_TRADE → CANDIDATE`

when:

`OpportunityScore > CandidateThreshold`

and:

`DataQuality = VALID`.

Otherwise:

`NO_TRADE → NO_TRADE`.

---

# 5. Candidate State

A candidate is not yet a trade signal.

It means:

"The current market state is statistically interesting enough to investigate further."

Candidate state contains:

`candidate_direction`

`candidate_horizon_distribution`

`candidate_regime_distribution`

`candidate_confidence`

`candidate_option_universe`.

No capital is committed.

No risk is accepted.

No order is submitted.

---

# 6. Candidate Creation

For each event:

`E_t`

update:

`MarketState_t`.

Then calculate:

`FeatureState_t`.

Then:

`ProbabilityState_t`.

Candidate creation occurs when the probability state enters the validated opportunity region.

Conceptually:

`CandidateScore = f(P_up, P_down, uncertainty, regime, liquidity, volatility)`.

Then:

`CandidateScore > validated_candidate_threshold`

causes:

`NO_TRADE → CANDIDATE`.

The threshold is learned through walk-forward validation.

---

# 7. Candidate Cancellation

A candidate immediately returns to `NO_TRADE` if:

`DataQuality = INVALID`

or:

`CandidateScore <= cancellation_threshold`

or:

`Liquidity becomes unacceptable`

or:

`Execution conditions become unacceptable`.

Therefore:

`CANDIDATE → NO_TRADE`.

No order is generated.

---

# 8. Candidate Direction

The candidate direction is:

`UP`

or:

`DOWN`.

It is determined from the probability distribution:

`P_up`

`P_down`

`P_neutral`.

The direction is not determined merely by:

`PriceChange > 0`

or:

`Delta > 0`.

Those are inputs.

---

# 9. Candidate to Signal

Transition:

`CANDIDATE → SIGNAL`

requires all mandatory gates to pass.

Conceptually:

`P_direction > validated_probability_requirement`

AND

`Uncertainty < validated_uncertainty_limit`

AND

`ConservativeEV > 0`

AND

`LiquidityOK`

AND

`ExecutionCostOK`

AND

`RiskCapacity > 0`

AND

`ModelValid = TRUE`.

If any mandatory gate fails:

`CANDIDATE → NO_TRADE`.

---

# 10. Signal State

A signal is now an economically valid trade proposal.

The signal contains:

`Direction`

`CandidateOptionSet`

`ProbabilityState`

`ExpectedValue`

`ConservativeExpectedValue`

`MFEDistribution`

`MAEDistribution`

`RiskBudget`

`ExecutionConstraints`.

Still:

`Position = NULL`.

No trade has occurred.

---

# 11. Signal to Entry Pending

The system now evaluates actual option contracts.

For every eligible option `i`:

`OptionScore_i`

is calculated.

The option score depends on:

`ExpectedNetEV_i`

`EffectiveRisk_i`

`Liquidity_i`

`Spread_i`

`Slippage_i`

`OptionSensitivity_i`

`ExecutionQuality_i`.

The selected contract is:

`O* = argmax(ValidatedOptionScore_i)`.

If no option passes the execution gates:

`SIGNAL → NO_TRADE`.

If one passes:

`SIGNAL → ENTRY_PENDING`.

---

# 12. Entry Pending

This state exists because:

`Signal != Fill`.

The system now has an intended order.

State contains:

`selected_option`

`direction`

`requested_quantity`

`reference_price`

`maximum_acceptable_entry_price`

`initial_stop`

`risk_budget`

`order_timestamp`.

The system waits for execution.

---

# 13. Entry Pending — Fill

If an executable fill occurs:

`ENTRY_PENDING → OPEN`.

The actual execution price becomes:

`EntryPrice_actual`.

It must not be replaced by the original theoretical entry.

The position is initialized using the actual fill.

---

# 14. Entry Pending — No Fill

If the market moves beyond the validated executable region:

`ENTRY_PENDING → NO_TRADE`.

The system cancels the candidate.

No position exists.

This prevents stale signals from becoming late entries.

---

# 15. Entry Pending — Partial Fill

If only part of the requested quantity is filled:

`FilledQuantity < RequestedQuantity`.

The system creates a partial position.

The remaining quantity becomes:

`RemainingQuantity = RequestedQuantity - FilledQuantity`.

The system must then decide, according to validated execution rules, whether to:

`continue seeking fill`

or:

`cancel remainder`.

The risk engine recalculates actual exposure.

---

# 16. Open State

Once filled:

`PositionState = OPEN`.

The immutable initial trade record is created.

It contains:

`TradeID`

`ModelVersion`

`SignalTimestamp`

`EntryTimestamp`

`EntryPrice`

`InitialStop`

`InitialRisk`

`InitialProbabilityState`

`InitialEV`

`InitialMFEDistribution`

`InitialMAEDistribution`

`InitialHorizonDistribution`.

This is the original trade thesis.

It must never be overwritten.

---

# 17. Initial Risk

At entry:

`InitialRiskPerUnit = EntryPrice - InitialStop`

for a long option.

For quantity `Q`:

`InitialGrossRisk = Q × InitialRiskPerUnit`.

Effective risk additionally includes:

`ExpectedSlippage`

`ExecutionCosts`

and validated adverse execution effects.

The position must satisfy:

`EffectiveRisk <= RiskBudget`.

---

# 18. Current Net P&L

We resolve the earlier duplicate terminology here.

We will use:

`CurrentGrossPnL`

for mark-to-market P&L before transaction costs.

And:

`CurrentNetPnL`

for estimated realizable P&L after relevant transaction costs.

We will not use `CurrentProfit` as a separate canonical variable.

Therefore:

`CurrentProfit = INVALID VARIABLE`.

The canonical quantity is:

`CurrentNetPnL`.

---

# 19. Peak Net P&L

Similarly:

`PeakNetPnL_t = max(PeakNetPnL_(t-1), CurrentNetPnL_t)`.

There is no separate:

`PeakProfit`.

Canonical:

`PeakNetPnL`.

---

# 20. Unrealized Drawdown From Peak

Define:

`ProfitGiveback_t = PeakNetPnL_t - CurrentNetPnL_t`.

If:

`CurrentNetPnL > PeakNetPnL`

then:

`PeakNetPnL = CurrentNetPnL`

and:

`ProfitGiveback = 0`.

This quantity is central to backward profit protection.

---

# 21. Expected Horizon

We also resolve:

`ExpectedHoldingTime`

versus:

`ExpectedHorizon`.

We retain only one canonical representation:

`HorizonDistribution`.

For example:

`P(T <= 3m)`

`P(3m < T <= 5m)`

`P(5m < T <= 15m)`

etc.

Then:

`ExpectedHorizon = E[T | CurrentState]`.

Therefore:

`ExpectedHorizon`

is a derived scalar.

`ExpectedHoldingTime`

is removed as a separate variable.

---

# 22. Trade Mode

Trade mode is derived from the current horizon distribution and state.

Possible modes:

`MICRO_SCALP`

`SCALP`

`EXTENDED_SCALP`

`INTRADAY`.

The mode is descriptive.

It does not constitute a separate strategy.

The transition is:

`TradeMode_t = g(HorizonDistribution_t, RegimeState_t, ContinuationValue_t)`.

---

# 23. Open-State Event Cycle

Every new market event while the position is open executes:

`Market Update`

→ `Feature Update`

→ `Probability Update`

→ `Regime Update`

→ `Position Mark`

→ `Forward Evaluation`

→ `Backward Protection`

→ `Stop Evaluation`

→ `Exit Evaluation`.

This sequence is repeated for every applicable event.

---

# 24. Position Mark

For every new executable market state:

`CurrentGrossPnL_t`

is calculated.

Then:

`CurrentNetPnL_t`

is estimated.

Then:

`PeakNetPnL_t`

is updated.

Then:

`ProfitGiveback_t`

is calculated.

---

# 25. Forward Evaluation

The current state is passed to the forward model.

Calculate:

`P_continuation`

`P_reversal`

`ExpectedAdditionalMFE`

`ExpectedAdditionalMAE`

`ExpectedRemainingCost`

`ExpectedRemainingHorizon`.

Then:

`ContinuationValue`

is calculated.

Conceptually:

`CV_t = E[FutureNetProfit | State_t] - E[FutureRisk | State_t]`.

The exact formulation is learned and validated.

---

# 26. Backward Evaluation

The profit-protection model receives:

`PeakNetPnL`

`CurrentNetPnL`

`ProfitGiveback`

`CurrentState`

`MFE`

`MAE`

`Regime`.

It estimates:

`AllowedGiveback`.

Then:

`ProfitFloor`.

The important distinction is:

Forward model:

`"How much opportunity remains?"`

Backward model:

`"How much accumulated profit should we protect?"`

They remain independent.

---

# 27. Candidate Stop

The stop engine calculates:

`CandidateStop_t`

from:

`InitialRiskBoundary`

`ProfitProtectionBoundary`

`DynamicRiskBoundary`.

Then:

`NewStop_t = max(CurrentStop_(t-1), CandidateStop_t)`.

Therefore:

`NewStop_t >= CurrentStop_(t-1)`.

This is a hard invariant.

---

# 28. Stop Cannot Widen

Suppose:

`CurrentStop = 120`

and new calculations produce:

`CandidateStop = 115`.

The result is:

`NewStop = 120`.

Never:

`115`.

This remains true even if the probability model becomes more optimistic.

---

# 29. Stop Cannot Increase Risk

Suppose:

`Entry = 100`

`InitialStop = 80`.

Later:

`CurrentPrice = 145`.

The system may move the stop:

`80 → 110 → 125 → 135 → 140`

depending on validated statistical conditions.

It cannot move:

`140 → 130`.

That would deliberately increase previously protected downside.

---

# 30. Regime Transition

A regime transition occurs when the posterior regime distribution changes sufficiently.

For example:

`P(TrendUp) ↓`

while:

`P(Reversal) ↑`.

The transition sensitivity is learned.

The system does not react merely because one tick changed direction.

The transition must be statistically significant relative to the current state.

---

# 31. Forward Regime Transition

Example:

`MICRO_SCALP → SCALP`

if the continuation distribution becomes more favorable.

Then:

`SCALP → EXTENDED_SCALP`

if the expected horizon and continuation value expand.

Then:

`EXTENDED_SCALP → INTRADAY`

if the statistically supported continuation horizon becomes sufficiently long.

No fixed clock forces these transitions.

---

# 32. Backward Regime Transition

The reverse transition is equally valid.

For example:

`INTRADAY → EXTENDED_SCALP`

if continuation deteriorates.

Then:

`EXTENDED_SCALP → SCALP`.

Then:

`SCALP → MICRO_SCALP`.

The trade is progressively managed more defensively.

This directly implements the forward/backward adaptation principle.

---

# 33. Profit-Protection Transition

The system does not wait for the trade to become a loss.

If:

`PeakNetPnL > 0`

and:

`P_reversal ↑`

or:

`ContinuationValue ↓`

then:

`AllowedGiveback ↓`.

Consequently:

`ProfitFloor ↑`

for a long option.

The stop therefore tightens.

---

# 34. Emergency Reversal

Emergency reversal is triggered when the current state is statistically inconsistent with continued exposure.

Conceptually:

`P_reversal >= validated_reversal_threshold`

AND

`StateTransitionConfidence >= validated_transition_requirement`.

Then:

`EmergencyState = TRUE`.

The response is:

`ProfitProtection → maximum validated defensiveness`.

If continuation value also becomes non-positive:

`EXIT`.

---

# 35. Important Distinction

A reversal probability increase does not automatically mean:

`EXIT`.

There are three levels:

`Level 1: Warning`

`Level 2: Protection`

`Level 3: Exit`.

This prevents the system from overreacting to every adverse microstructure event.

---

# 36. Level One — Warning

Condition:

`P_reversal increases`

but:

`ContinuationValue > 0`

and:

`ProfitProtection remains adequate`.

Action:

`HOLD`.

No stop change may be necessary.

---

# 37. Level Two — Protection

Condition:

`P_reversal materially increases`

or:

`ExpectedAdditionalMAE increases`

or:

`ProfitGiveback becomes statistically abnormal`.

Action:

`UPDATE_STOP`.

The stop tightens.

The position remains open.

---

# 38. Level Three — Exit

Exit when any mandatory exit condition is satisfied:

`HardRiskBreached`

OR:

`ConservativeContinuationValue <= 0`

OR:

`EmergencyReversal`

OR:

`SessionTermination`

OR:

`ExecutionSafetyFailure`.

Then:

`OPEN → EXIT_PENDING`.

---

# 39. Exit Pending

This state exists for the same reason as Entry Pending.

`ExitDecision != ExitFill`.

The system has decided to leave but has not necessarily executed yet.

State contains:

`ExitReason`

`ExitTimestamp`

`ReferenceExitPrice`

`MaximumAcceptableSlippage`.

---

# 40. Exit Fill

When execution occurs:

`EXIT_PENDING → CLOSED`.

Actual exit price becomes immutable.

Then:

`RealizedNetPnL`

is calculated.

---

# 41. Exit Failure

If the expected execution does not occur, the position remains exposed.

The system does not pretend the position is closed.

It returns to:

`OPEN`

with an updated:

`ExecutionRiskState`.

The emergency execution policy then applies.

---

# 42. Closed State

Once the position is actually closed:

`Position = NULL`.

The trade record becomes immutable.

Calculate:

`RealizedGrossPnL`

`RealizedNetPnL`

`ActualHoldingDuration`

`MaximumFavorableExcursion`

`MaximumAdverseExcursion`

`ExecutionSlippage`.

The trade is then:

`CLOSED → OUTCOME_PENDING`.

---

# 43. Realized Net P&L

Canonical formula:

`RealizedNetPnL = GrossPnL - AllApplicableExecutionCosts`.

This is the final economic result.

It must not be confused with:

`CurrentNetPnL`

which was an estimate during the trade.

---

# 44. Outcome Pending

The trade's immediate result is known.

However, some future-dependent labels may require additional time.

For example:

`Was this entry capable of producing a larger MFE?`

`What was the eventual MAE distribution?`

`What was the maximum favorable movement within the evaluation horizon?`

Therefore:

`CLOSED → OUTCOME_PENDING`.

---

# 45. Outcome Completion

When all predefined outcome horizons have elapsed:

`OutcomePending = FALSE`.

Then:

`OUTCOME_PENDING → LEARNING_ELIGIBLE`.

The trade can now contribute to future model training.

---

# 46. Critical Learning Boundary

A trade that occurred at time:

`t`

cannot update the model used at:

`t`.

Even after exit, its outcome is associated with:

`ModelVersion_at_entry`.

Only a future model-generation cycle can consume the outcome.

Therefore:

`Trade_t`

→ `Outcome_t`

→ `LearningDataset`

→ `Model_(t+k)`.

Never:

`Trade_t`

→ `Model_t`.

---

# 47. Learning State

Learning operates outside the live decision state machine.

It receives:

`CompletedOutcome`

and:

`HistoricalStateAtDecision`.

The learning system generates:

`CandidateModel`.

Then:

`CandidateModel → Validation`.

Then:

`Validation → Test`.

Then:

`Test → Challenger`.

Then:

`Challenger → PromotionGate`.

Then, if successful:

`Champion_(N) → Champion_(N+1)`.

---

# 48. Champion Promotion

Promotion requires all predefined constraints to pass.

The candidate must demonstrate:

`PositiveOutOfSampleEV`

`AcceptableDrawdown`

`AcceptableRuinProbability`

`AcceptableCalibration`

`ExecutionRobustness`

`ParameterStability`

`RegimeRobustness`.

A model cannot be promoted solely because:

`TotalReturn_candidate > TotalReturn_champion`.

---

# 49. Data Failure State

At any point, the system can enter:

`DATA_UNSAFE`.

Triggers include:

`FeedGap`

`InvalidTimestamp`

`SequenceFailure`

`StaleQuote`

`CorruptEvent`

`UnacceptableLatency`

`IncompleteMarketState`.

While:

`DATA_UNSAFE = TRUE`

then:

`NewEntry = DISABLED`.

Existing positions follow their independent risk-protection rules.

---

# 50. Model Failure State

The system can also enter:

`MODEL_UNSAFE`.

Possible causes:

`CalibrationFailure`

`StatisticalDrift`

`PredictionDistributionShift`

`ExecutionDistributionShift`

`OutOfDomainState`.

Then:

`NewEntry = DISABLED`.

This is different from data failure.

Data failure means:

"The information is unreliable."

Model failure means:

"The information is valid, but our statistical interpretation is no longer validated."

---

# 51. Market Closure State

At the validated session boundary:

`OPEN → EXIT_PENDING`.

No new positions may be opened after the strategy's configured entry cutoff.

The exact cutoff is a learned/validated operational parameter subject to exchange and instrument rules.

---

# 52. Event-Level Transition Algorithm

Every event follows this causal sequence:

```text id="t4p7w4"
EVENT(t)
   |
   v
VALIDATE
   |
   +-- invalid --> DATA_UNSAFE
   |
   v
UPDATE MARKET STATE
   |
   v
UPDATE FEATURES
   |
   v
UPDATE PROBABILITIES
   |
   +-----------------------------+
   |                             |
Position = NULL             Position != NULL
   |                             |
   v                             v
Evaluate Candidate         Mark Position
   |                             |
   v                             v
Evaluate Trade EV          Forward Model
   |                             |
   v                             v
Trade Decision             Backward Model
                                 |
                                 v
                           Stop Evaluation
                                 |
                                 v
                           Exit Evaluation
   |                             |
   +-------------+---------------+
                 |
                 v
             EXECUTION
                 |
                 v
            NEW STATE
```

---

# 53. Event Ordering Rule

Within a single event, calculations must occur in dependency order.

For example:

`Bid/Ask`

must update before:

`Spread`.

`Spread`

must update before:

`SpreadPercentile`.

`SpreadPercentile`

must update before:

`ExecutionQuality`.

`ExecutionQuality`

must update before:

`ExpectedNetEV`.

`ExpectedNetEV`

must update before:

`TradeDecision`.

This creates a deterministic evaluation order.

---

# 54. Temporal Rule

Every state variable receives an explicit timestamp:

`Variable(t)`.

If:

`A_t → B_t`

then `B_t` can consume `A_t`.

If:

`B_t → A_t`

would be required to calculate `A_t`, that is an instantaneous circular dependency and is prohibited.

Cross-event dependencies are permitted:

`A_t → B_(t+1)`.

That is how adaptive behavior works.

---

# 55. Example: One Tick During an Open Trade

Suppose the position is long a CE.

A new event arrives.

The event changes:

`Bid`

`Ask`

`LTP`.

Then:

`Spread`

changes.

Then:

`LiquidityImbalance`

changes.

Then:

`PriceChange`

and:

`Delta`

may change.

Then:

`Features`

change.

Then:

`P_continuation`

changes.

Suppose:

`P_continuation ↓`

and:

`P_reversal ↑`.

The forward model calculates lower continuation value.

The backward model observes that the trade is already profitable.

Therefore:

`AllowedGiveback ↓`.

Then:

`ProfitFloor ↑`.

Then:

`CandidateStop ↑`.

Then:

`CurrentStop ↑`.

The system does **not** immediately exit unless the validated exit condition is crossed.

This is the precise mechanism for dynamic protection.

---

# 56. Example: Adverse Tick After Large Profit

Suppose:

`Entry = 100`

and eventually:

`PeakNetPnL = +45`.

A new adverse sequence begins.

The system does not reason:

"Price fell, therefore exit."

Instead:

```text id="v4a5tx"
New Event
   |
   v
Market State Changes
   |
   v
Probability State Changes
   |
   +--> P(reversal)
   +--> P(continuation)
   +--> Expected MFE
   +--> Expected MAE
   |
   v
Continuation Value
   |
   v
Profit Giveback Distribution
   |
   v
Allowed Giveback
   |
   v
Profit Floor
   |
   v
Current Stop
```

If the statistically allowed giveback is now small enough that the current price violates the floor:

`EXIT`.

If continuation remains sufficiently positive:

`HOLD`.

That is the rigorous implementation of the forward/backward idea.

---

# 57. Example: Intraday Trade Becomes Scalp

Suppose the trade originally has:

`P(T > 45m)` high.

Later:

`P(T <= 15m)` becomes dominant.

The state transitions:

`INTRADAY → EXTENDED_SCALP`.

The system does not forcibly close merely because the classification changed.

Instead it changes:

`ContinuationPolicy`

and:

`ProfitProtectionPolicy`.

If the new state demands greater protection:

`Stop tightens`.

---

# 58. Example: Scalp Becomes Intraday

Suppose:

`P(T <= 15m)` initially dominates.

Then price acceptance, order flow, liquidity and volatility evolve such that:

`P(T > 45m)` rises significantly.

The state becomes:

`SCALP → EXTENDED_SCALP → INTRADAY`.

The system may allow the position to continue.

But:

`InitialRisk`

does not increase.

This is crucial.

A longer projected horizon can increase allowed participation in upside.

It cannot increase downside exposure.

---

# 59. Example: False Breakout

Suppose:

`P_up` becomes high.

A CE signal is generated.

Price initially rises.

Then:

`AggressiveBuyVolume` remains elevated.

But:

`PriceResponse` collapses.

This creates a potential:

`AbsorptionState`.

If the historical model shows that this combination predicts reversal:

`P_reversal ↑`.

Then:

`ContinuationValue ↓`.

Then:

`ProfitFloor tightens`.

The strategy may exit before the original stop is reached.

This is exactly why we use multiple independent information channels.

---

# 60. State Transition Invariants

These are permanent.

`Position cannot exist without a fill.`

`Trade cannot be considered closed without an exit fill.`

`CurrentStop cannot move backward.`

`Risk cannot increase after entry.`

`Future information cannot affect the current decision.`

`A regime change cannot increase risk.`

`A longer projected horizon cannot widen a stop.`

`A probability increase cannot override a hard risk boundary.`

`A probability decrease cannot force an exit unless the validated exit condition is reached.`

`Data failure disables new entries.`

`Model failure disables new entries.`

`Learning cannot modify the active model instantaneously.`

`No trade is always a valid state.`

---

# 61. Canonical Transition Function

The entire state machine can therefore be represented as:

`S_(t+1) = T(S_t, E_(t+1), M_t)`.

Where:

`S_t = CurrentState`

`E_(t+1) = NewMarketEvent`

`M_t = FrozenModelVersion`.

The model itself does not change during the event-processing cycle.

---

# 62. Model Update Function

Separately:

`M_(k+1) = L(D_(<=k), M_k)`

where:

`D = Completed historical outcomes`.

Then:

`M_(k+1)`

must pass:

`Validation(M_(k+1))`

before it becomes eligible for production.

Thus:

`TradingState`

and:

`LearningState`

are separate machines.

---

# 63. Final Two-Machine Architecture

The system actually consists of two interacting but temporally separated machines.

### Machine A — Trading Machine

`Event`

→ `Market State`

→ `Features`

→ `Probability`

→ `Decision`

→ `Position`

→ `Exit`.

This operates during market processing.

### Machine B — Learning Machine

`Completed Outcome`

→ `Training Dataset`

→ `Candidate Model`

→ `Validation`

→ `Test`

→ `Champion`.

This operates outside the causal path of the trade that generated the outcome.

That separation is one of the strongest safeguards against accidental look-ahead.

---

# 64. Final Canonical State Graph

```text id="6wq2d5"
                         +----------------+
                         |   DATA_UNSAFE  |
                         +-------+--------+
                                 |
                                 v
+-----------+
| NO_TRADE  |
+-----+-----+
      |
      | Opportunity
      v
+-----------+
| CANDIDATE |
+-----+-----+
      |
      | All gates pass
      v
+-----------+
|  SIGNAL   |
+-----+-----+
      |
      | Option + execution valid
      v
+----------------+
| ENTRY_PENDING  |
+-------+--------+
        |
        | Fill
        v
+----------------+
|     OPEN       |
+---+---+---+----+
    |   |   |
    |   |   +--------------------+
    |   |                        |
    |   v                        v
    | UPDATE_STOP             EXIT_PENDING
    |                              |
    v                              | Fill
  HOLD                             v
    |                           CLOSED
    |                              |
    +------------------------------+
                                   |
                                   v
                            OUTCOME_PENDING
                                   |
                                   | All labels available
                                   v
                            LEARNING_ELIGIBLE
                                   |
                                   v
                             LEARNING MACHINE
                                   |
                                   v
                              CHALLENGER
                                   |
                              Promotion
                                   |
                                   v
                               CHAMPION
```

The important property is that the `LEARNING MACHINE` never feeds backward into the historical event that generated its training observation.

It only affects future trading after validation and promotion.

---

# 65. Specification Status

After this state-transition specification:

`Master Mathematical Specification = LOCKED`

`Canonical Variable Registry = LOCKED`

`Variable Dependency Graph = LOCKED`

`State Transition Specification = LOCKED`

`Risk Invariants = LOCKED`

`Learning Boundary = LOCKED`

`TrueData Field Mapping = TBD`

`Learned Numerical Parameters = TBD`

`Execution API Mapping = TBD`

The remaining unknowns are now predominantly empirical or source-specific rather than conceptual.

The system is therefore ready for the next specification layer:

`Exact Mathematical Operators and Threshold Contracts`.

That layer will define precisely how quantities such as:

`OpportunityScore`

`ConservativeEV`

`RegimeTransitionScore`

`ContinuationValue`

`AllowedGiveback`

`ProfitFloor`

`ReversalScore`

`CandidateStop`

and:

`PromotionScore`

are mathematically constructed, while still leaving their learned numerical parameters to walk-forward validation.

That is the point where the specification becomes sufficiently precise that two independent engineers should be able to implement the same mathematical system and obtain the same state transitions from the same input stream.