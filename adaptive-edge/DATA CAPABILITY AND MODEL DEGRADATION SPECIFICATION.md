# DATA CAPABILITY AND MODEL DEGRADATION SPECIFICATION
## Canonical Specification — Version 1.0

## 1. Purpose

The production system must never assume that every required data domain is available at every timestamp.

The system must distinguish:

`market information unavailable`

from:

`market information neutral`.

These are fundamentally different.

Therefore the strategy must never convert:

`MISSING`

into:

`0`.

Instead, every feature domain has an explicit capability state.

---

# 2. Capability State

Every information domain has:

`AVAILABLE`

`PARTIAL`

`STALE`

`INVALID`

`UNAVAILABLE`.

The aggregate capability state is:

`CAPABILITY_STATE_t`.

It is calculated from the individual domains.

---

# 3. Information Domains

The strategy recognizes these domains:

`PRICE`

`TRADE_FLOW`

`ORDER_BOOK`

`VOLUME`

`VOLATILITY`

`SESSION`

`OPTION_MARKET`

`OPTION_GREEKS`

`LIQUIDITY`

`EXECUTION`

`HISTORICAL_SUPPORT`.

Each domain can independently degrade.

---

# 4. PRICE DOMAIN

Required minimum:

`LTP`

and, for executable decisions:

`BEST_BID`

`BEST_ASK`.

If:

`LTP = valid`

but:

`BID/ASK = unavailable`

then:

`PRICE = PARTIAL`.

The system may calculate descriptive price features.

It must not assume executable entry/exit prices are known.

---

# 5. Price Failure Rule

If the strategy requires immediate option purchase and:

`OPTION_ASK = unavailable`

then:

`TRADE = NO_TRADE`.

Reason:

The system cannot reliably calculate executable entry cost.

---

# 6. Trade-Flow Domain

Required for full microstructure mode:

`Trade`

plus a defensible directional classification.

If only trades exist:

`TRADE_FLOW = PARTIAL`.

If directional classification is validated:

`TRADE_FLOW = AVAILABLE`.

If classification is unavailable:

`Delta`

and:

`FlowImbalance`

are unavailable.

---

# 7. No Fake Delta

The system must never execute:

`UnknownAggressorSide -> assume BUY`

or:

`UnknownAggressorSide -> assume SELL`.

Unknown remains:

`UNKNOWN`.

Therefore:

`Delta`

cannot be fabricated.

---

# 8. Order-Book Domain

If the required depth levels are available:

`ORDER_BOOK = AVAILABLE`.

If only partial depth exists:

`ORDER_BOOK = PARTIAL`.

If no required depth exists:

`ORDER_BOOK = UNAVAILABLE`.

The model must know which state applies.

TrueData's current public documentation specifically describes a top-five market-depth API for BSE, while its broader product page separately says depth is available “where available.” Therefore NSE depth must remain an entitlement/source-contract question until proven for our subscription.

---

# 9. Depth Is Optional Evidence

The strategy must not make:

`Depth`

a mandatory dependency for every trade.

Instead:

`Depth`

is an evidence domain.

Therefore the system can potentially operate without it if the remaining evidence passes the required statistical threshold.

---

# 10. Historical Support Domain

This is different from live capability.

A feature can be:

`LIVE_AVAILABLE`

but:

`HISTORICALLY_UNSUPPORTED`.

Example:

`Depth`.

This creates:

`TRAINING_CAPABILITY != LIVE_CAPABILITY`.

The model must explicitly account for that.

---

# 11. Historical Tick Constraint

TrueData currently documents default historical tick availability as:

`last 5 trading days`.

Therefore our default source contract cannot claim multi-year tick training.

This does not prevent using longer historical data at lower resolution.

---

# 12. Replay Is Different

TrueData currently documents Full Market Feed Replay for active Market Data API subscribers.

Replay therefore becomes a separate capability:

`REPLAY_CAPABILITY`.

It must not automatically be interpreted as:

`historical API storage`.

Those are different interfaces with different operational semantics.

---

# 13. Minimum Information Set

The system defines a minimum information set for each decision mode.

The modes are:

`MICRO`

`SCALP`

`EXTENDED_SCALP`

`INTRADAY`.

The required evidence differs by mode.

---

# 14. MICRO MODE

Micro mode attempts to exploit very short-horizon movement.

Therefore it has the strictest requirements.

Required:

`Price`

`Executable Bid/Ask`

`Current volatility`

`Liquidity`

`Current option market`

`Current timestamp`

`Information timestamp`

`Execution-cost estimate`.

Trade-flow is preferred but cannot be blindly assumed.

---

# 15. Micro Trade Rule

If the minimum executable state is incomplete:

`MICRO_ENTRY = FALSE`.

The system does not downgrade an incomplete micro trade into a normal trade merely because the signal looks attractive.

---

# 16. SCALP MODE

Scalp mode permits a slightly broader information set.

Required:

`Price`

`Executable option quote`

`Volatility`

`Liquidity`

`Historical probability support`

`Execution-cost estimate`.

Trade-flow and depth improve evidence quality but may be optional depending on the validated model.

---

# 17. EXTENDED-SCALP MODE

This mode handles trades whose expected horizon extends beyond the shortest microstructure regime.

Required:

`Price`

`Volatility`

`Option economics`

`Historical distribution`

`Risk model`.

Microstructure becomes supporting evidence rather than the sole information basis.

---

# 18. INTRADAY MODE

Intraday mode is less dependent on instantaneous microstructure.

Required:

`Price`

`Volatility`

`Option economics`

`Historical directional distribution`

`Risk`

`Execution`.

Trade-flow may be unavailable without disabling the entire intraday strategy.

---

# 19. Capability Vector

At time `t`:

`C_t = {`

`C_price`

`C_flow`

`C_book`

`C_volume`

`C_volatility`

`C_option`

`C_greeks`

`C_liquidity`

`C_execution`

`C_history`

`}`.

Each element has:

`0 = unavailable`

`1 = partial`

`2 = available`.

---

# 20. Feature Capability Mask

Every feature has:

`RequiredDomains(feature)`.

For example:

`FLOW_IMBALANCE`

requires:

`TRADE_FLOW`.

Therefore:

`C_flow = 0`

means:

`FLOW_IMBALANCE = UNAVAILABLE`.

It does not become zero.

---

# 21. Model Capability Mask

The probability model receives:

`FeatureVector`

and:

`CapabilityMask`.

Therefore the model knows:

"this feature is absent"

rather than:

"this feature equals zero."

---

# 22. Why This Matters

Suppose:

`OBI = 0`.

That could mean:

balanced order book.

But:

`OBI = UNAVAILABLE`

means:

we have no information.

These imply completely different posterior probabilities.

---

# 23. Model Family Selection

The system contains several statistically related model configurations.

Not different strategies.

They are different valid information subsets of the same strategy.

For example:

`MODEL_FULL`

uses:

`Price + Flow + Depth + Option + Volatility + Liquidity`.

`MODEL_NO_DEPTH`

uses:

`Price + Flow + Option + Volatility + Liquidity`.

`MODEL_PRICE_OPTION`

uses:

`Price + Option + Volatility + Liquidity`.

---

# 24. Critical Rule

A degraded model may only be used if it has been independently validated.

We cannot say:

"Depth is missing, so remove depth and continue."

That would create an unvalidated model.

Instead:

`ModelSubset`

must have its own historical walk-forward performance.

---

# 25. Model Hierarchy

The hierarchy is:

```text
FULL MODEL
    |
    +-- if capability sufficient
    |
    v
NO-DEPTH MODEL
    |
    +-- if validated and capability sufficient
    |
    v
NO-FLOW MODEL
    |
    +-- if validated and capability sufficient
    |
    v
PRICE+OPTION MODEL
    |
    +-- if validated and capability sufficient
    |
    v
NO TRADE
```

This hierarchy is not assumed valid.

Every transition must be statistically validated.

---

# 26. Evidence Penalty

Missing information should generally reduce evidence.

But we should not simply multiply:

`Evidence × 0.5`.

That would be an arbitrary number.

Instead:

`EvidenceDegradation`

must be learned from historical comparison between:

`full-information observations`

and:

`reduced-information observations`.

---

# 27. Capability-Conditional Probability

We therefore estimate:

`P(Y | X, C)`.

Where:

`X = available features`

and:

`C = capability state`.

This is superior to pretending that:

`P(Y | X)`

is unchanged when information disappears.

---

# 28. Domain-Specific Missingness

Missing depth may be different from missing option IV.

Therefore:

`MissingDepth`

and:

`MissingIV`

must not automatically have identical effects.

The historical dataset determines their impact.

---

# 29. Stale Data

A value may technically exist but be too old to use.

Therefore:

`AVAILABLE != FRESH`.

For feature `X`:

`Age_X = CurrentInformationTime - X.Timestamp`.

If:

`Age_X > validated freshness limit`

then:

`X = STALE`.

The freshness threshold must be learned/validated rather than invented.

---

# 30. Cross-Domain Timestamp Alignment

Suppose:

`Underlying tick = 10:15:00.100`

but:

`Option quote = 10:14:59.800`.

The option quote may be stale relative to the underlying.

Therefore the feature engine must preserve:

`timestamp per input`.

It cannot blindly merge everything into:

`CurrentTime`.

---

# 31. Synchronization Rule

For a feature snapshot:

`F_t`

every component must satisfy its domain-specific freshness requirement.

Otherwise:

`F_t = PARTIAL`.

---

# 32. Probability Suppression

If the required information is incomplete:

the probability model may still produce a mathematical output.

But:

`ProbabilityAvailable != TradeEligible`.

This distinction is critical.

A probability can exist without being sufficiently reliable for trading.

---

# 33. Evidence Gate

The decision layer therefore requires:

`ProbabilityValid`

AND:

`EvidenceSufficient`

AND:

`CapabilitySufficient`

AND:

`ExecutionValid`

AND:

`RiskValid`.

Only then:

`TradeEligible = TRUE`.

---

# 34. NO_TRADE Dominance

Any hard safety failure dominates all predictive evidence.

Therefore:

`DataUnsafe -> NO_TRADE`

`ExecutionUnsafe -> NO_TRADE`

`RiskLimitExceeded -> NO_TRADE`

`ProbabilityInvalid -> NO_TRADE`

`EvidenceInsufficient -> NO_TRADE`.

No positive signal can override these.

---

# 35. Data Gap During Open Position

This is different.

If data becomes unavailable while a position already exists:

the system does NOT automatically treat that as:

`NO_TRADE`.

It becomes:

`POSITION_MANAGEMENT_DEGRADED`.

---

# 36. Position Degradation Hierarchy

When the feed degrades:

`Full Position Management`

→

`Reduced Position Management`

→

`Emergency Protection`

→

`Emergency Exit`

depending on severity.

---

# 37. Full Management

All required information is available.

The system may dynamically calculate:

`CurrentStop`

`ContinuationValue`

`ReversalProbability`

`ProfitProtectionBoundary`.

---

# 38. Reduced Management

Some predictive features disappear.

The system must stop opening new positions if required.

But it may continue managing an existing position using:

`Current executable price`

`Current stop`

`Hard risk limits`.

---

# 39. Emergency Protection

If the predictive layer is unavailable but executable pricing remains available:

the system stops making discretionary predictive decisions.

It relies on:

`hard protection`

and:

`predefined emergency rules`.

---

# 40. Emergency Exit

If the system cannot reliably determine:

`current executable market`

or:

`position state`

or:

`risk exposure`

then the system enters:

`EXECUTION_SAFETY_FAILURE`.

The exact broker-side recovery procedure must be specified separately.

---

# 41. Important Principle

The strategy must never say:

"Data disappeared, therefore price is unchanged."

It says:

"Current state is unknown."

That distinction prevents catastrophic stale-data decisions.

---

# 42. Option-Specific Failure

Suppose:

`Underlying = available`

but:

`Option quote = unavailable`.

We may still calculate:

`UnderlyingDirection`.

But we cannot safely execute:

`BUY_CE`.

Therefore:

`OptionExecutionCapability = FALSE`.

Result:

`NO_NEW_OPTION_ENTRY`.

---

# 43. Option IV Failure

Suppose:

`OptionPrice`

and:

`Bid/Ask`

exist but:

`IV`

does not.

If IV is not mandatory for the validated model:

the system may use a model variant without IV.

If IV is mandatory:

`NO_TRADE`.

The distinction comes from historical validation.

---

# 44. Depth Failure

Suppose:

`Price + Flow + Option + Volatility`

are available.

But:

`Depth`

is unavailable.

If:

`MODEL_NO_DEPTH`

has passed walk-forward validation:

the strategy can continue.

Otherwise:

`NO_TRADE`.

---

# 45. Flow Failure

Suppose:

`Trade data exists`

but:

`Aggressor classification unavailable`.

Then:

`Flow model unavailable`.

The strategy may fall back only to a separately validated model.

---

# 46. Historical-Support Failure

A new market condition may fall outside the historical feature domain.

Then:

`DOMAIN_STATUS = OUT_OF_DOMAIN`.

This is not the same as missing data.

All fields may be available while the model has insufficient historical support.

---

# 47. Out-of-Domain Rule

If:

`DOMAIN_STATUS = OUT_OF_DOMAIN`

then:

`EvidenceScore`

must be reduced or:

`Trade = NO_TRADE`

depending on the validated policy.

Again, the numerical threshold is learned.

---

# 48. Novelty Versus Missingness

The system distinguishes:

`MISSING_INFORMATION`

from:

`NOVEL_INFORMATION`.

Missing:

"We cannot see it."

Novel:

"We can see it, but historical data does not contain comparable states."

These require different responses.

---

# 49. Capability State Machine

The capability state machine is:

```text
FULL
 |
 +-- data degradation --> PARTIAL
 |
 +-- data recovery ----> FULL
 |
 +-- severe degradation -> UNSAFE
 |
 +-- recovery ----------> PARTIAL/FULL
```

No state transition occurs merely because a model prediction changes.

---

# 50. Feature State Machine

For each feature:

```text
UNAVAILABLE
     |
     | valid source arrives
     v
VALID
     |
     | age exceeds threshold
     v
STALE
     |
     | valid update
     v
VALID
     |
     | malformed source
     v
INVALID
```

---

# 51. Model State Machine

Each model configuration has:

`TRAINING`

`VALIDATING`

`SHADOW`

`ACTIVE`

`RETIRED`.

Only:

`ACTIVE`

may make production decisions.

---

# 52. Degraded Model Activation

A degraded model must itself be:

`VALIDATED`.

Therefore:

`CapabilityChange`

can select:

`ACTIVE_VALIDATED_MODEL_FOR_CAPABILITY_STATE`.

It cannot dynamically invent a new feature subset.

---

# 53. This Is Important for Our Dynamic Strategy

Our earlier idea was:

"Let the system dynamically decide whether this is micro-scalping, scalping, or intraday."

That remains valid.

But we now add another dimension:

`Information Capability`.

Therefore the decision is not simply:

`Horizon -> Mode`.

It is:

`Market State`

+

`Expected Horizon`

+

`Capability State`

+

`Evidence`

+

`Economic Value`

→

`Trade Mode`.

---

# 54. Example

Suppose:

`Expected Horizon = 8 minutes`

and:

`Full microstructure data available`.

Then:

`MICRO/SCALP MODEL`

may be eligible.

But if:

`Depth unavailable`

and:

`No validated no-depth model`

then:

`NO_TRADE`.

The system does not force itself into intraday merely because the data is incomplete.

---

# 55. Another Example

Suppose:

`Expected Horizon = 25 minutes`.

The system classifies:

`SCALP`.

Then the flow feed becomes unavailable.

If:

`NO-FLOW SCALP MODEL`

is validated:

continue using that model.

Otherwise:

stop new entries.

The trade does not magically become:

`INTRADAY`.

---

# 56. Open Position Example

Suppose:

`Entry = ₹100`

`CurrentPrice = ₹145`

and the trade has accumulated substantial profit.

Then:

`FlowFeed disappears`.

The system must not:

`widen stop`

because the continuation model has become uncertain.

Instead:

the loss of predictive information can only make protection:

`equal or tighter`

unless an explicitly validated risk rule permits otherwise.

This preserves our earlier backward-profit-protection principle.

---

# 57. Protection Monotonicity

For a long-premium position, the economic protection rule is:

`Protection_t+1 >= Protection_t`

unless:

`ExplicitRiskTransition = TRUE`.

Therefore information degradation cannot accidentally loosen a previously established profitable protection boundary.

---

# 58. Important Correction to Earlier Thinking

We previously discussed dynamically widening a stop when a trade transitions from:

`scalp -> intraday`.

That is dangerous.

The correct rule is:

`TradeMode change`

does not automatically imply:

`Stop loosening`.

The stop is governed independently by:

`risk`

`MFE`

`giveback`

`reversal probability`

`execution`.

A mode change can affect the candidate protection calculation, but cannot violate the protection invariant.

---

# 59. Reverse Transition

If:

`INTRADAY -> SCALP`

because the predicted horizon contracts:

the system can tighten protection.

It must not assume that:

`SCALP -> INTRADAY`

requires loosening protection.

This is a major improvement.

---

# 60. Dynamic Mode Is Not Dynamic Risk Permission

This distinction is now canonical:

`TRADE_MODE`

describes expected opportunity horizon.

`RISK_MODE`

describes acceptable current downside.

They are separate state variables.

---

# 61. Risk Mode

Possible conceptual states:

`INITIAL_RISK`

`PROFIT_PROTECTION`

`BREAKEVEN_PROTECTION`

`LOCKED_PROFIT`

`EMERGENCY`.

Exact transitions will be determined by the step-four statistical framework.

---

# 62. Why This Matters

A trade can be:

`INTRADAY opportunity`

while simultaneously being:

`LOCKED_PROFIT risk state`.

Therefore:

`Longer expected horizon`

does not mean:

`more allowed downside`.

---

# 63. Model Degradation During Learning

If historical data is insufficient to estimate a degraded model:

that model is:

`UNVALIDATED`.

It cannot enter production.

Therefore the registry can explicitly contain:

`MODEL_NO_DEPTH = UNVALIDATED`.

The runtime then knows:

`Depth unavailable -> NO_TRADE`.

---

# 64. No Automatic Retraining

Runtime capability changes must not trigger immediate model retraining.

Otherwise:

`data outage`

could alter:

`model parameters`.

That would create uncontrolled adaptation.

Runtime:

`selects among validated models`.

Offline learning:

`creates new models`.

---

# 65. Model Promotion

A new degraded model must pass:

`walk-forward validation`

`out-of-sample test`

`cost-adjusted evaluation`

`calibration`

`stability`

`adversarial tests`.

Only then can it become:

`ACTIVE`.

---

# 66. Capability Logging

Every decision must record:

`CapabilityState`

and:

`ModelVersion`.

Therefore later we can answer:

"Did this trade occur under full or degraded information?"

---

# 67. Required Decision Record

Each trade decision must contain:

`DecisionTimestamp`

`CapabilityState`

`FeatureCapabilityMask`

`ModelVersion`

`ProbabilityState`

`EvidenceState`

`ExpectedHorizonDistribution`

`EconomicDistribution`

`RiskState`

`ExecutionState`

`Decision`.

---

# 68. Research Requirement

When evaluating model performance, results must be segmented by capability.

For example:

`Full-information trades`

versus:

`Reduced-information trades`.

Otherwise the aggregate performance could hide a severe dependency on one data domain.

---

# 69. Required Performance Breakdown

At minimum:

`Full`

`Partial`

`NoDepth`

`NoFlow`

`HighLatency`

`HighSpread`

`HighVolatility`

`OutOfDomain`.

Each regime should have independent:

`WinRate`

`ExpectedNetPnL`

`Drawdown`

`TailLoss`

`Calibration`.

---

# 70. Capability Robustness Criterion

A model should not be considered production-grade merely because:

`Full model profitable`.

We also require:

`known degradation behavior`.

The system must know exactly when it should stop trading.

---

# 71. No-Trade Is a First-Class Output

The model's outputs are therefore not simply:

`BUY`

or:

`SELL`.

They are:

`BUY_CE`

`BUY_PE`

`HOLD`

`EXIT`

`NO_TRADE`.

And:

`NO_TRADE`

has explicit reasons.

---

# 72. No-Trade Reason Codes

Examples:

`NTR_DATA_UNAVAILABLE`

`NTR_DATA_STALE`

`NTR_DATA_INVALID`

`NTR_DOMAIN_UNKNOWN`

`NTR_EVIDENCE_LOW`

`NTR_EXPECTED_VALUE_LOW`

`NTR_EXECUTION_COST_HIGH`

`NTR_RISK_LIMIT`

`NTR_OPTION_UNAVAILABLE`

`NTR_MODEL_UNVALIDATED`.

This makes the system auditable.

---

# 73. Capability-Aware Decision Function

The canonical decision concept becomes:

`Decision_t = D(`

`MarketState_t,`

`FeatureState_t,`

`CapabilityState_t,`

`Probability_t,`

`Evidence_t,`

`EconomicState_t,`

`RiskState_t,`

`ExecutionState_t`

`)`.

This is now the complete decision boundary.

---

# 74. Hard Invariants

The following are now locked:

`Missing != Zero`

`Stale != Current`

`Unknown != Neutral`

`Partial != Full`

`Unvalidated != Available`

`Probability != Eligibility`

`Mode != Risk`

`MarketTime != InformationTime`.

These are architectural invariants.

---

# 75. Final Degradation Principle

The system should become:

`less aggressive`

as information quality decreases.

It should never become:

`more aggressive`

because information is missing.

Therefore:

`Information uncertainty ↑`

must never directly produce:

`Risk tolerance ↑`.

---

# 76. Result

The strategy can now operate under:

`FULL DATA`

`PARTIAL DATA`

`HIGH LATENCY`

`MISSING MICROSTRUCTURE`

`MISSING OPTION DATA`

`OUT-OF-DOMAIN CONDITIONS`

without pretending those conditions are equivalent.

---

# 77. Current Architecture

The complete runtime chain is now:

```text
TRUE DATA
   |
   v
RAW EVENT
   |
   v
TIME + VALIDATION
   |
   v
CANONICAL STATE
   |
   v
CAPABILITY MASK
   |
   v
FEATURE SNAPSHOT
   |
   v
VALIDATED MODEL FOR CAPABILITY
   |
   v
PROBABILITY
   |
   v
EVIDENCE
   |
   v
EXPECTED HORIZON
   |
   v
ECONOMIC DISTRIBUTION
   |
   v
RISK STATE
   |
   v
EXECUTION STATE
   |
   v
DECISION
   |
   v
POSITION
   |
   v
PROTECTION
   |
   v
OUTCOME
   |
   v
MATURED LABEL
   |
   v
WALK-FORWARD LEARNING
```

---

# 78. Architecture Status

At this point we have completed:

`Mathematical state definition`

`Canonical variable registry`

`Dependency graph`

`State transitions`

`Historical labels`

`Probability mechanism`

`Economic decision mechanism`

`Dynamic protection`

`Temporal causality`

`TrueData source reconciliation`

`Capability management`

`Model degradation`.

The next artifact should therefore be substantially more demanding.

# NEXT: SYNTHETIC ADVERSARIAL MARKET VERIFICATION

We should construct hostile synthetic sequences and feed them through this entire specification.

Examples:

`Flash spike`

`False breakout`

`Liquidity disappearance`

`Spread explosion`

`Feed freeze`

`Delayed ticks`

`Out-of-order events`

`Duplicate ticks`

`Extreme volatility`

`Option quote freeze`

`Underlying moves while option feed stalls`

`Profitable trade followed by violent reversal`

`Micro-scalp that becomes an intraday candidate`

`Intraday candidate that suddenly collapses`

`Model out-of-domain event`

`Capability degradation during maximum profit`.

For every scenario, we will calculate the exact state transitions and ask:

`Can the system lose money?`

More importantly:

`Can it lose money because of a specification error?`

That is the next formal-verification exercise before implementation.