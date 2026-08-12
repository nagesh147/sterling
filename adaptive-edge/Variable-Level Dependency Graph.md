# Variable-Level Dependency Graph
## Canonical Dependency Specification — Version 1.0

### 1. Dependency Direction

The entire system obeys one directional rule:

`RAW DATA`
→ `STATE`
→ `DERIVED STATE`
→ `FEATURE`
→ `PROBABILITY`
→ `ECONOMIC DECISION`
→ `POSITION`
→ `OUTCOME`
→ `LEARNING`
→ `FUTURE MODEL`

There must be no backward dependency.

In particular:

`OUTCOME` cannot influence `FEATURE_t`.

`POSITION` cannot influence the probability model except through explicitly defined historical labels.

`LEARNING` cannot alter the model that generated the observation currently being evaluated.

---

# 2. Complete Dependency Graph

```text
                           TRUE DATA
                              |
              +---------------+----------------+
              |               |                |
            PRICE           TRADE            QUOTE
              |               |                |
              v               v                v
        Price State       Trade State      Liquidity State
              |               |                |
       +------+-------+       |        +-------+-------+
       |              |       |        |               |
       v              v       v        v               v
    Return        Velocity   Volume   Spread       Bid/Ask Qty
       |              |       |        |               |
       +-------+------+-------+--------+---------------+
               |
               v
         Microstructure State
               |
       +-------+--------+----------------+
       |                |                |
       v                v                v
   Order Flow       Volatility       Liquidity
       |                |                |
       v                v                v
     Delta         Vol Percentile   Liquidity Score
       |
       +----------------+
       |
       v
   Delta Dynamics
       |
       +----------------------------+
                                    |
                                    v
                            Feature Vector X_t
                                    |
              +---------------------+--------------------+
              |                     |                    |
              v                     v                    v
        Regime Model        Direction Model       Horizon Model
              |                     |                    |
              v                     v                    v
        P(Regime)              P(Direction)        P(Horizon)
              |                     |                    |
              +----------+----------+--------------------+
                         |
                         v
                  Probability State
                         |
              +----------+-----------+
              |                      |
              v                      v
       MFE / MAE Model        Uncertainty Model
              |                      |
              +----------+-----------+
                         |
                         v
                  Trade Candidate
                         |
             +-----------+-----------+
             |                       |
             v                       v
       CE Candidate             PE Candidate
             |                       |
             +-----------+-----------+
                         |
                         v
                  Option Selection
                         |
                         v
                 Execution Model
                         |
                         v
                 Expected Net EV
                         |
                         v
                   Risk Engine
                         |
                         v
              NO TRADE / BUY CE / BUY PE
                         |
                         v
                    POSITION
                         |
          +--------------+---------------+
          |              |               |
          v              v               v
    Forward Model   Profit Model   Execution Monitor
          |              |               |
          v              v               v
    Continuation     Giveback        Slippage/Fill
     Probability       Model           Reality
          |              |               |
          +--------------+---------------+
                         |
                         v
                  Position Decision
                         |
              +----------+----------+
              |          |          |
              v          v          v
             HOLD    UPDATE STOP   EXIT
                                    |
                                    v
                                  OUTCOME
                                    |
                     +--------------+--------------+
                     |              |              |
                     v              v              v
                    PnL            MFE            MAE
                     |              |              |
                     +--------------+--------------+
                                    |
                                    v
                              LEARNING DATA
                                    |
                                    v
                            WALK-FORWARD MODEL
                                    |
                                    v
                             MODEL N+1
```

That is the top-level dependency graph.

Now we go one level deeper.

# 3. Price Dependency Chain

The fundamental price chain is:

`LTP`

→ `PriceChange`

→ `Return`

→ `Velocity`

→ `Acceleration`

→ `MomentumFeatures`

→ `DirectionalProbability`.

Formally:

`ΔP_t = P_t - P_(t-1)`

`R_t = ΔP_t / P_(t-1)`

`V_t = ΔP_t / Δt`

`A_t = ΔV_t / Δt`.

No probability variable is allowed to directly consume an unvalidated future return.

---

# 4. Quote Dependency Chain

```text
Bid
 |
 +--> Spread
 |      |
 |      +--> RelativeSpread
 |      |
 |      +--> SpreadVelocity
 |
 +--> MidPrice
 |
 +--> LiquidityImbalance
        |
        +--> LiquidityScore
        |
        +--> LiquidityStress
```

Definitions:

`Mid = (Bid + Ask)/2`

`Spread = Ask - Bid`

`RelativeSpread = Spread / Mid`

`LI = (BidQty - AskQty)/(BidQty + AskQty)`.

The quote chain feeds:

`Liquidity`

`Execution`

`Microstructure`.

It does not directly produce:

`BUY_CE`

or:

`BUY_PE`.

It must pass through the probability and economic-decision layers.

---

# 5. Trade-Flow Dependency Chain

```text
Trade
 |
 +--> TradePrice
 |
 +--> TradeSize
 |
 +--> Aggressor Classification
          |
          +--> Buy Volume
          |
          +--> Sell Volume
          |
          +--> Unknown Volume
                    |
                    v
                  Delta
                    |
             +------+------+
             |             |
             v             v
       Cumulative      Delta Velocity
          Delta              |
             |               v
             |        Delta Acceleration
             |               |
             +-------+-------+
                     |
                     v
              Flow Features
                     |
                     v
              Probability Model
```

This reveals an important architectural constraint.

`Delta` is not itself a signal.

`Delta` is an input.

The probability model determines whether the observed delta historically corresponds to a meaningful future outcome under the current context.

---

# 6. Volume Dependency Chain

```text
TradeSize
    |
    +--> Cumulative Volume
    |
    +--> Volume Rate
    |
    +--> Trade Frequency
    |
    +--> Average Trade Size
    |
    +--> Volume Intensity
             |
             v
       Normalized Volume
             |
             v
       Feature Vector
```

`VolumeIntensity` depends on a historical expected-volume distribution.

Therefore:

`CurrentVolume`

→ `HistoricalContext`

→ `ExpectedVolume`

→ `VolumeIntensity`.

The historical expected-volume model must itself obey the walk-forward cutoff.

---

# 7. Volatility Dependency Chain

```text
Price
 |
 v
Returns
 |
 +--> Micro Volatility
 |
 +--> Short Volatility
 |
 +--> Intraday Volatility
        |
        v
Volatility Distribution
        |
        v
Volatility Percentile
        |
        v
Regime / Probability Model
```

A critical rule:

`VolatilityPercentile_t`

can only use historical volatility observations available before `t`.

It cannot use the eventual day's volatility.

---

# 8. Profile Dependency Chain

```text
Trade Price + Trade Volume
             |
             v
      Volume-by-Price
             |
             v
       Volume Profile
             |
       +-----+-----+
       |     |     |
       v     v     v
      POC   HVN   LVN
       |
       v
Distance From POC
       |
       v
Profile Features
       |
       v
Probability Model
```

The same principle applies to Market Profile.

Profiles are **stateful accumulators**, not future-aware indicators.

---

# 9. Options Dependency Chain

The option chain is downstream of the underlying market context for directional decision-making.

```text
UNDERLYING
    |
    +--> Directional Probability
    |
    +--> Volatility State
    |
    +--> Regime
    |
    v
Candidate Option Universe
    |
    +--> Strike
    +--> Expiry
    +--> CE/PE
    +--> Bid/Ask
    +--> Volume
    +--> OI
    +--> IV
    +--> Greeks
    |
    v
Option Quality
    |
    +--> Liquidity
    +--> Spread
    +--> Slippage
    +--> Sensitivity
    |
    v
Option Selection
```

This preserves our earlier principle:

`Underlying determines direction.`

`Option determines expression of that direction.`

---

# 10. Normalization Dependency

Every normalized feature follows:

```text
Raw Variable
     |
     v
Context
     |
     +--> Instrument
     +--> Time Of Day
     +--> Volatility State
     +--> Expiry State
     +--> Historical Regime
     |
     v
Conditional Distribution
     |
     v
Percentile / Z-score
     |
     v
Feature
```

The conditional distribution is itself learned.

Therefore:

`Raw Data`

→ `Historical Distribution`

→ `Normalization`

→ `Feature`.

Not:

`Raw Data`

→ `Feature`

→ `Historical Distribution`.

That latter direction would create a circular dependency.

---

# 11. Feature-to-Probability Dependency

The feature vector is:

`X_t = {Price, Flow, Volume, Liquidity, Volatility, Profile, Options, Time}`.

Then:

`X_t`

→ `RegimeModel`

→ `P(Regime|X_t)`.

And:

`X_t`

→ `DirectionModel`

→ `P(Up|X_t), P(Down|X_t), P(Neutral|X_t)`.

And:

`X_t`

→ `HorizonModel`

→ `P(Horizon|X_t)`.

And:

`X_t`

→ `MFE/MAEModel`

→ `F(MFE|X_t), F(MAE|X_t)`.

These models may share the same underlying feature vector, but their outputs remain conceptually separate.

---

# 12. Probability Fusion

The probability layer becomes:

```text
                 Feature Vector
                       |
       +---------------+---------------+
       |               |               |
       v               v               v
   Parametric       Empirical       Bayesian
     Model            Model           State
       |               |               |
       +---------------+---------------+
                       |
                       v
                Probability Fusion
                       |
                       v
                 Calibration
                       |
                       v
               Final Probability
                       |
                       v
                  Uncertainty
```

This is where we need to be particularly careful.

Calibration cannot be used to generate the raw probability that it is calibrating.

Otherwise we create a circular dependency.

Correct:

`RawModelProbability`

→ `CalibrationModel`

→ `CalibratedProbability`.

Incorrect:

`CalibratedProbability`

→ `CalibrationModel`

→ `CalibratedProbability`.

---

# 13. Trade-Decision Dependency

The decision chain is:

```text
Final Probability
        |
        +--> Direction
        |
        +--> Horizon
        |
        +--> MFE
        |
        +--> MAE
        |
        v
Candidate Trade
        |
        +--> Option Selection
        |
        +--> Execution Cost
        |
        +--> Risk
        |
        v
Expected Net EV
        |
        v
Conservative EV
        |
        v
Risk Gate
        |
        v
Decision
```

The decision cannot consume realized P&L.

Realized P&L does not exist at entry.

---

# 14. Position Entry Dependency

```text
BUY_CE / BUY_PE
       |
       v
Execution Request
       |
       v
Fill
       |
       +--> Entry Price
       +--> Fill Timestamp
       +--> Slippage
       |
       v
Position State
```

The actual entry price must be downstream of execution.

This prevents another subtle error:

`ExpectedEntryPrice`

must not be treated as:

`ActualEntryPrice`.

---

# 15. Position Management Dependency

Once the position exists:

```text
Position State
      |
      +--> Current Market State
      |
      +--> Updated Probability State
      |
      +--> Forward Distribution
      |
      +--> Profit State
      |
      +--> Execution State
      |
      v
Management Engine
```

Then:

`ContinuationValue`

and:

`ProfitProtectionState`

are independently calculated.

---

# 16. Forward Model

```text
Current Position State
        |
        +--> Current Market State
        |
        +--> Current Probability State
        |
        v
Future Opportunity Distribution
        |
        +--> Expected Additional MFE
        +--> Expected Additional MAE
        +--> Continuation Probability
        |
        v
Continuation Value
```

The forward model answers:

`"Is there enough statistically justified opportunity remaining?"`

It does not answer:

`"How much profit have we already made?"`

That is handled separately.

---

# 17. Backward Profit-Protection Model

```text
Entry
 |
 v
Peak Price
 |
 v
Peak Profit
 |
 v
Current Profit
 |
 v
Profit Giveback
 |
 v
Historical Giveback Distribution
 |
 v
Allowed Giveback
 |
 v
Profit Floor
 |
 v
Candidate Stop
```

This model answers:

`"Given how much profit we have already accumulated, how much of that profit is statistically reasonable to expose to reversal?"`

It does not predict future upside.

---

# 18. Stop Dependency

The final stop is:

`CandidateStop`

derived from:

`OriginalRiskBoundary`

`ProfitFloor`

`DynamicRiskBoundary`

Then:

`CurrentStop_t = max(CurrentStop_(t-1), CandidateStop_t)`

for a long position.

Therefore:

```text
CurrentStop
    |
    v
CandidateStop
    |
    v
MAX
    |
    v
NewCurrentStop
```

There is intentionally no dependency from:

`NewCurrentStop`

back into:

`CandidateStop`

for the same event.

This prevents circular stop calculation.

---

# 19. Regime Reclassification

Regime classification is based on:

`Current Market State`

not on:

`Current Trade P&L`.

The trade's profitability may affect risk protection, but it cannot manufacture a new market regime.

Correct:

`MarketState → Regime`.

Then:

`Regime + PositionState → ManagementPolicy`.

Incorrect:

`PositionProfit → Regime`.

This distinction is important.

---

# 20. Trade-Duration Classification

The trade duration model depends on:

`P(Horizon | CurrentState)`.

It does not depend primarily on:

`TimeSinceEntry`.

Time since entry is contextual information.

It is not the classification itself.

Therefore:

```text
Current State
     |
     v
Horizon Distribution
     |
     v
Expected Holding Profile
     |
     v
Trade Mode
```

This permits:

`MICRO_SCALP`

→ `SCALP`

→ `EXTENDED_SCALP`

→ `INTRADAY`

or the reverse transition.

---

# 21. Exit Dependency

Exit is:

```text
Current Position
       |
       +--> Hard Risk
       |
       +--> Continuation Value
       |
       +--> Reversal Probability
       |
       +--> Profit Floor
       |
       +--> Execution State
       |
       +--> Session Constraint
       |
       v
EXIT DECISION
```

No single component is allowed to override a hard risk boundary.

---

# 22. Outcome Dependency

After exit:

```text
Entry
 |
 +--> Entry Price
 |
Exit
 |
 +--> Exit Price
 |
 +--> Time
 |
 v
Realized PnL
```

And independently:

```text
Entry
 |
 v
Future Price Path
 |
 +--> MFE
 |
 +--> MAE
 |
 +--> TimeToMFE
 |
 +--> TimeToMAE
 |
 v
Outcome Dataset
```

The future path is used to evaluate the trade after the decision has already occurred.

---

# 23. Learning Dependency

```text
Historical Market State
        |
        +--> Decision
        |
        +--> Future Market Path
                       |
                       v
                    Outcome
                       |
                       v
                Learning Dataset
                       |
                       v
                Training Window
                       |
                       v
                Model Candidate
                       |
                       v
                 Validation
                       |
                       v
                    Test
                       |
                       v
               CHALLENGER
                       |
                       v
               Promotion Gate
                       |
                       v
                 CHAMPION
```

The champion model used at time `t` cannot learn from the outcome occurring at time `t` until that outcome becomes historically available and the next model-generation cycle begins.

---

# 24. Critical Anti-Circularity Rules

The following dependencies are explicitly prohibited.

`P&L → DirectionProbability`

during the same trade.

`FutureMFE → EntryProbability`.

`FutureMAE → EntryProbability`.

`FinalDayVolume → MorningVolumeFeature`.

`EndOfDayProfile → EarlierIntradayDecision`.

`TestPeriod → TrainingParameters`.

`TestPeriod → FeatureNormalization`.

`Outcome → SameTradeModel`.

`ActualFill → HistoricalSignal`.

`FutureRegime → HistoricalRegime`.

`FutureVolatility → CurrentVolatility`.

These are all forms of information leakage.

---

# 25. Duplicate Variable Audit

We currently have several concepts that could accidentally become duplicates.

### Duplicate Candidate One

`VolatilityPercentile`

and:

`NormalizedVolatility`.

These should become one canonical concept.

Canonical name:

`volatility_percentile`.

A Z-score can remain a separate representation if we actually use it.

---

### Duplicate Candidate Two

`CurrentPnL`

and:

`CurrentProfit`.

These represent the same economic quantity unless we explicitly distinguish gross and net.

Canonical names should therefore be:

`current_gross_pnl`

and:

`current_net_pnl`.

---

### Duplicate Candidate Three

`PeakPnL`

and:

`PeakProfit`.

Same issue.

Canonical:

`peak_net_pnl`.

---

### Duplicate Candidate Four

`AggressiveBuyVolume`

and:

`BuyVolume`.

We should not have two independent variables.

Canonical:

`aggressive_buy_volume`.

---

### Duplicate Candidate Five

`LiquidityImbalance`

and:

`OrderBookImbalance`.

These are potentially different.

We must define:

`top_of_book_liquidity_imbalance`

versus:

`multi_level_orderbook_imbalance`.

They cannot share the same name.

---

### Duplicate Candidate Six

`ExpectedHoldingTime`

and:

`ExpectedHorizon`.

These should be unified unless one represents a probability distribution and the other a point estimate.

Canonical:

`horizon_distribution`.

Derived:

`expected_horizon`.

---

### Duplicate Candidate Seven

`StopLoss`

and:

`CurrentStop`.

The first should refer to the initial protective boundary.

The second refers to the dynamically maintained executable stop.

Canonical:

`initial_stop`

and:

`current_stop`.

---

### Duplicate Candidate Eight

`Target`

and:

`ExpectedMFE`.

These are not the same.

`ExpectedMFE` is a statistical distribution.

`Target` is a decision boundary derived from that distribution and economic constraints.

Therefore:

`MFE_distribution → target_candidate`.

---

# 26. Potential Circularity We Discovered

There is one particularly important potential circular dependency.

We previously defined:

`RiskBudget = f(Capital, Drawdown, Edge, Volatility, Liquidity)`.

But:

`Edge`

is derived from probability.

And probability may use:

`Liquidity`

and:

`Volatility`.

That itself is fine.

However, if we allow:

`RiskBudget → Probability`

we create:

`Probability → RiskBudget → Probability`.

We therefore explicitly prohibit risk budget from feeding the directional probability model.

Correct:

`Probability → RiskBudget`.

Not:

`RiskBudget → Probability`.

---

# 27. Another Potential Circularity

We defined:

`Option Selection`

using:

`Expected EV`.

But:

`Expected EV`

uses:

`Execution Cost`.

And execution cost depends on:

`Option Liquidity`.

Therefore:

```text
Option
  |
  +--> Liquidity
  |
  +--> Execution Cost
  |
  +--> Expected EV
  |
  +--> Option Ranking
```

There is no circularity.

But option ranking must not alter the liquidity estimate used to calculate its own execution cost.

---

# 28. Another Important Circularity

`ProfitFloor`

depends on:

`PeakProfit`.

`PeakProfit`

depends on:

`ActualExecution`.

Therefore:

`Execution → PeakProfit → ProfitFloor → Stop`.

This is valid.

But:

`Stop → Execution → PeakProfit`

can appear circular.

It isn't, because the stop affects **future execution**, while the current `PeakProfit` is already known.

The dependency is time-directed:

`State_t → Stop_t → Execution_(t+1) → State_(t+1)`.

This temporal indexing is essential.

---

# 29. The Real Dependency Graph Is a Directed Acyclic Graph Per Event

The entire system should therefore be understood as:

`DAG_t`

for every event `t`.

Then:

`DAG_t → DAG_(t+1)`.

There can be temporal feedback across events:

`State_t → State_(t+1)`.

But there must not be an instantaneous circular dependency inside the same event.

That is the clean mathematical solution.

---

# 30. Canonical Event Evaluation Order

For every incoming event:

```text
1. Receive Event
2. Validate Event
3. Update Raw State
4. Update Primitive State
5. Update Derived State
6. Update Rolling Statistics
7. Update Profiles
8. Update Normalized Features
9. Update Probability State
10. Evaluate New Trade Opportunity
11. If Position Exists:
       Update Position State
       Update Forward Model
       Update Profit-Protection Model
       Update Stop
       Evaluate Exit
12. Execute Decision
13. Record Event/Decision
14. Advance State
```

Learning does **not** occur inside this same causal decision chain.

Learning is downstream.

---

# 31. Learning Evaluation Order

Separately:

```text
Historical Outcome Becomes Available
            |
            v
Outcome Validation
            |
            v
Learning Dataset
            |
            v
Walk-Forward Training
            |
            v
Validation
            |
            v
Unseen Test
            |
            v
Robustness Tests
            |
            v
Champion / Challenger
```

This separation is mandatory.

---

# 32. Final Dependency Architecture

The canonical mathematical dependency is therefore:

`E_t`

→ `S_t`

→ `X_t`

→ `P_t`

→ `C_t`

→ `R_t`

→ `D_t`

→ `Position_(t+1)`

→ `Outcome`

→ `Learning`

→ `Model_(future)`.

Where:

`E = Event`

`S = State`

`X = Feature`

`P = Probability`

`C = Candidate`

`R = Risk/Economic Evaluation`

`D = Decision`.

The critical temporal constraint is:

`Decision_t = f(E_0...E_t)`

and:

`Outcome_t = f(E_t...E_future)`.

Then:

`Model_(t+1) = f(History <= t)`.

Never:

`Decision_t = f(History > t)`.

---

# 33. Dependency Audit Result

After the first dependency audit:

`No fundamental architectural circular dependency remains.`

We found several naming duplications and resolved them conceptually.

We found one important potential circularity involving `RiskBudget` and `Probability`; it is resolved by making probability upstream of risk.

We found a temporal dependency involving stops and execution; it is valid when explicitly indexed by time.

We also established that the system is best represented as a sequence of event-level DAGs rather than one static graph.

The unresolved items are now mostly **source-bound**, not architecture-bound.

Those remain in the existing TrueData `TODO` registry and do not block further mathematical design.

---

# 34. Single Source of Truth

The hierarchy is now:

`Master Mathematical Specification`
        |
        v
`Canonical Variable Registry`
        |
        v
`Variable Dependency Graph`
        |
        v
`Data Source Mapping`
        |
        v
`Implementation`
        |
        v
`Tests`

Any future change must propagate downward.

For example:

`Change probability definition`

requires:

`Registry update`

→ `Dependency graph update`

→ `Data requirements update`

→ `Implementation update`

→ `Test update`.

This prevents implementation from silently diverging from the mathematical strategy.

---

# 35. Current Architectural Freeze

At this point we have:

`Five-stage strategy architecture`

`Master mathematical specification`

`Canonical variable registry`

`Variable dependency graph`

`Circular-dependency audit`

`Duplicate-variable audit`

`Anti-lookahead constraints`

`Temporal event model`

`Learning boundary`

`TrueData TODO boundary`.

The next layer should therefore not be another conceptual strategy layer.

The next artifact should be the **State Transition Specification**: the exact mathematical conditions under which every state changes, including:

`NO_TRADE → CANDIDATE`

`CANDIDATE → SIGNAL`

`SIGNAL → ENTRY_PENDING`

`ENTRY_PENDING → OPEN`

`OPEN → HOLD`

`OPEN → UPDATE_STOP`

`OPEN → REGIME_CHANGE`

`REGIME_CHANGE → PROFIT_PROTECTION`

`OPEN → EXIT`

`EXIT → OUTCOME`

`OUTCOME → LEARNING`.

That will turn the dependency graph into an executable mathematical state machine without yet writing implementation code.