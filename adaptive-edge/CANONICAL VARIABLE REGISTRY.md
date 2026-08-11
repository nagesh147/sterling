# CANONICAL VARIABLE REGISTRY

Version 1.0

## 1. Purpose

The Canonical Variable Registry is the single source of truth for every variable used by the strategy.

It connects:

```text
Mathematical Specification
        ↕
Data Contract
        ↕
State Machine
        ↕
Feature Engine
        ↕
Probability Engine
        ↕
Economic Engine
        ↕
Risk Engine
        ↕
Execution Engine
        ↕
Learning Engine
```

A variable that does not exist in this registry is not a canonical system variable.

---

# 2. Variable Identity

Every variable receives an immutable:

```text
VariableID
```

The human-readable name may change during implementation.

The `VariableID` must not.

Conceptually:

```text
VariableID = V-XXXX
```

This allows implementation names to evolve without changing mathematical identity.

---

# 3. Canonical Variable Schema

Every registry entry contains:

```text
VariableID
CanonicalName
Definition
Type
Unit
Owner
Source
Dependencies
UpdateTrigger
TimestampSemantics
Availability
Formula
Domain
AllowedConsumers
Invariant
Status
Version
ExternalMapping
```

Not every field is populated immediately.

Unknown external information remains:

```text UNKNOWN
```

---

# 4. Status Definitions

A variable may have:

```text
FROZEN
LEARNED
CONFIGURED
EXTERNAL
DERIVED
PENDING_EXTERNAL
DEPRECATED
```

These have different meanings.

```text FROZEN
Definition is architecturally fixed.

LEARNED
Numerical value must be estimated historically.

CONFIGURED
Explicit operational value.

EXTERNAL
Obtained from an external authoritative source.

DERIVED
Calculated from other canonical variables.

PENDING_EXTERNAL
Definition exists but provider semantics remain unresolved.
```

---

# 5. Layer Ownership

Canonical ownership is:

```text DATA
MARKET_STATE
FEATURE
PROBABILITY
ECONOMICS
DECISION
RISK
EXECUTION
POSITION
TRADE_MANAGEMENT
LABEL
LEARNING
RESEARCH
OPERATIONS
```

A variable has exactly one owner.

---

# 6. Data Variables

## V-DATA-001 — EventID

Definition:

```text Unique identity of a canonical event.
```

Type:

```text Identifier
```

Owner:

```text DATA
```

Source:

```text Provider event identity or deterministic adapter-generated identity.
```

Status:

```text FROZEN
```

Invariant:

```text Two distinct canonical events must not share an EventID.
```

---

## V-DATA-002 — EventType

Definition:

```text Canonical classification of an incoming event.
```

Examples:

```text MARKET_TICK
MARKET_QUOTE
MARKET_TRADE
MARKET_DEPTH
OPTION_CHAIN_UPDATE
ORDER_EVENT
FILL_EVENT
DATA_QUALITY_EVENT
```

Status:

```text FROZEN
```

---

## V-DATA-003 — EventTimestamp

Definition:

```text Canonical timestamp representing when the event occurred.
```

Unit:

```text Time
```

Owner:

```text DATA
```

Status:

```text FROZEN
```

External mapping:

```text PENDING_EXTERNAL
```

Reason:

Exact TrueData timestamp semantics remain unverified.

---

## V-DATA-004 — SourceTimestamp

Definition:

```text Timestamp supplied by the external data source.
```

Status:

```text EXTERNAL
```

External mapping:

```text PENDING_EXTERNAL
```

---

## V-DATA-005 — ReceiptTimestamp

Definition:

```text Timestamp at which the local system receives the event.
```

Owner:

```text DATA
```

Status:

```text FROZEN
```

---

## V-DATA-006 — InstrumentID

Definition:

```text Canonical identity of the financial instrument associated with an event.
```

Status:

```text FROZEN
```

External mapping:

```text PENDING_EXTERNAL
```

---

# 7. Instrument Variables

## V-INST-001 — UnderlyingID

Definition:

```text Canonical identity of the underlying instrument.
```

Baseline:

```text NIFTY
```

Status:

```text CONFIGURED
```

---

## V-INST-002 — InstrumentType

Possible values include:

```text INDEX
EQUITY
OPTION
```

Status:

```text FROZEN
```

---

## V-INST-003 — Expiry

Definition:

```text Contract expiry associated with an option.
```

Owner:

```text MARKET_STATE
```

Status:

```text EXTERNAL
```

External mapping:

```text PENDING_EXTERNAL
```

---

## V-INST-004 — StrikePrice

Definition:

```text Strike price of an option contract.
```

Unit:

```text Price
```

Status:

```text EXTERNAL
```

---

## V-INST-005 — OptionType

Domain:

```text CE
PE
```

Status:

```text FROZEN
```

---

## V-INST-006 — LotSize

Definition:

```text Minimum tradable contract quantity for the instrument.
```

Status:

```text EXTERNAL
```

External mapping:

```text PENDING_EXTERNAL
```

---

## V-INST-007 — TickSize

Definition:

```text Minimum permitted price increment.
```

Status:

```text EXTERNAL
```

---

# 8. Market State Variables

## V-MKT-001 — UnderlyingPrice

Definition:

```text Latest valid underlying market price available at time t.
```

Owner:

```text MARKET_STATE
```

Source:

```text Canonical market event.
```

Status:

```text EXTERNAL
```

External mapping:

```text PENDING_EXTERNAL
```

---

## V-MKT-002 — UnderlyingTradeQuantity

Definition:

```text Quantity associated with an observed underlying market trade.
```

Important distinction:

```text MarketTradeQuantity
    !=
OurExecutedQuantity
```

Status:

```text EXTERNAL
```

---

## V-MKT-003 — BidPrice

Definition:

```text Latest valid bid price available for the instrument.
```

Status:

```text EXTERNAL
```

---

## V-MKT-004 — AskPrice

Definition:

```text Latest valid ask price available for the instrument.
```

Status:

```text EXTERNAL
```

---

## V-MKT-005 — BidQuantity

Definition:

```text Quantity available at the canonical bid observation.
```

Status:

```text EXTERNAL
```

---

## V-MKT-006 — AskQuantity

Definition:

```text Quantity available at the canonical ask observation.
```

Status:

```text EXTERNAL
```

---

## V-MKT-007 — MarketTimestamp

Definition:

```text Timestamp associated with the current market state.
```

Derived from:

```text EventTimestamp.
```

Status:

```text DERIVED
```

---

# 9. Session Variables

## V-SES-001 — SessionID

Definition:

```text Identifier of the trading session containing the event.
```

Status:

```text DERIVED
```

---

## V-SES-002 — SessionStart

Definition:

```text Start timestamp of the applicable trading session.
```

Status:

```text EXTERNAL / CONFIGURED
```

Exact exchange semantics remain pending verification.

---

## V-SES-003 — SessionEnd

Definition:

```text End timestamp of the applicable trading session.
```

Status:

```text EXTERNAL / CONFIGURED
```

---

## V-SES-004 — SessionElapsedTime

Definition:

```text Current event time - session start.
```

Status:

```text DERIVED
```

---

# 10. Opening Range Variables

## V-OR-001 — OpeningRangeHigh

Definition:

```text Maximum eligible underlying price observed during the canonical opening-range interval.
```

Status:

```text DERIVED
```

---

## V-OR-002 — OpeningRangeLow

Definition:

```text Minimum eligible underlying price observed during the canonical opening-range interval.
```

Status:

```text DERIVED
```

---

## V-OR-003 — OpeningRangeWidth

Definition:

```text OpeningRangeHigh - OpeningRangeLow.
```

Status:

```text DERIVED
```

---

## V-OR-004 — OpeningRangeComplete

Definition:

```text Indicates whether the canonical opening-range interval has completed.
```

Domain:

```text TRUE / FALSE
```

Status:

```text DERIVED
```

---

# 11. Feature Variables

Features are canonical only when their mathematical definitions have been frozen.

The initial registry therefore records the feature class rather than inventing numerical formulas.

---

## V-FTR-001 — DirectionalEvidence

Definition:

```text Canonical representation of evidence supporting one or more directional outcomes.
```

Status:

```text DERIVED
```

Exact construction:

```text DEFINED BY PROBABILITY SPECIFICATION
```

---

## V-FTR-002 — VolatilityState

Definition:

```text Current volatility-related state derived from permitted historical market information.
```

Status:

```text DERIVED
```

Exact estimator:

```text UNFROZEN
```

---

## V-FTR-003 — MomentumState

Definition:

```text Canonical representation of recent directional price behavior.
```

Status:

```text DERIVED
```

Exact lookback:

```text LEARNED / VALIDATED
```

---

## V-FTR-004 — MarketStructureState

Definition:

```text Canonical representation of relevant price-structure conditions.
```

Status:

```text DERIVED
```

---

## V-FTR-005 — TimeOfDayState

Definition:

```text State derived from current session time.
```

Status:

```text DERIVED
```

No future market information is permitted.

---

# 12. Probability Variables

## V-PRB-001 — DirectionalProbability

Definition:

```text Probability assigned to the currently evaluated directional outcome given information available at time t.
```

Mathematically:

```text P_t = P(Direction | F_t)
```

Domain:

```text [0,1]
```

Status:

```text DERIVED
```

---

## V-PRB-002 — Direction

Domain:

```text UP
DOWN
```

Status:

```text FROZEN
```

---

## V-PRB-003 — ProbabilityModelVersion

Definition:

```text Immutable identifier of the statistical model used to produce the probability.
```

Status:

```text FROZEN
```

---

## V-PRB-004 — ProbabilityParameterVersion

Definition:

```text Immutable identifier of the parameter set used by the probability model.
```

Status:

```text FROZEN
```

---

## V-PRB-005 — EvidenceStrength

Definition:

```text Statistical strength of the evidence supporting the current probability estimate.
```

Status:

```text DERIVED
```

Exact formulation remains part of the statistical model specification.

---

# 13. Economic Variables

## V-ECO-001 — ExpectedGrossValue

Definition:

```text Expected economic outcome before transaction and execution costs.
```

Status:

```text DERIVED
```

---

## V-ECO-002 — ExpectedExecutionCost

Definition:

```text Expected cost of entering and exiting the candidate position under the information available at decision time.
```

Status:

```text LEARNED / CONFIGURED
```

---

## V-ECO-003 — ExpectedNetValue

Definition:

```text ExpectedGrossValue - ExpectedExecutionCost.
```

Status:

```text DERIVED
```

---

## V-ECO-004 — EconomicMargin

Definition:

```text ExpectedNetValue relative to the relevant economic/risk normalization.
```

Exact normalization:

```text UNFROZEN.
```

---

# 14. Option Variables

## V-OPT-001 — CandidateOption

Definition:

```text An option contract eligible for evaluation at decision time.
```

Status:

```text DERIVED
```

---

## V-OPT-002 — SelectedOption

Definition:

```text Option contract selected by the option-selection algorithm before execution.
```

Status:

```text DERIVED
```

---

## V-OPT-003 — OptionBidPrice

Definition:

```text Latest valid bid price for the candidate option.
```

Status:

```text EXTERNAL
```

---

## V-OPT-004 — OptionAskPrice

Definition:

```text Latest valid ask price for the candidate option.
```

Status:

```text EXTERNAL
```

---

## V-OPT-005 — TimeToExpiry

Definition:

```text ExpiryTimestamp - DecisionTimestamp.
```

Status:

```text DERIVED
```

---

## V-OPT-006 — OptionLiquidityState

Definition:

```text Canonical representation of whether the candidate option satisfies the validated liquidity constraints.
```

Status:

```text DERIVED
```

Exact construction:

```text PENDING DATA CONTRACT + VALIDATION.
```

---

# 15. Decision Variables

## V-DEC-001 — DecisionID

Definition:

```text Immutable identifier for a strategy decision.
```

Status:

```text FROZEN
```

---

## V-DEC-002 — DecisionTimestamp

Definition:

```text Timestamp at which the decision became authoritative.
```

Status:

```text DERIVED
```

---

## V-DEC-003 — DecisionAction

Domain:

```text BUY_CE
BUY_PE
NO_TRADE
```

Status:

```text FROZEN
```

---

## V-DEC-004 — DecisionReason

Definition:

```text Structured explanation of the conditions responsible for the decision.
```

Status:

```text FROZEN
```

---

# 16. Risk Variables

## V-RSK-001 — StrategyRiskBudget

Definition:

```text Maximum risk authorized by the strategy for the applicable trade.
```

Status:

```text CONFIGURED / LEARNED
```

Exact numerical value:

```text UNFROZEN.
```

---

## V-RSK-002 — AuthorizedQuantity

Definition:

```text Maximum quantity permitted by the risk and execution constraints.
```

Status:

```text DERIVED
```

---

## V-RSK-003 — AuthorizedRisk

Definition:

```text Maximum loss exposure authorized under the current risk contract.
```

Status:

```text DERIVED
```

---

## V-RSK-004 — ProtectionLevel

Definition:

```text Current canonical protection level governing the active trade.
```

Status:

```text DERIVED
```

Invariant:

```text Protection_(t+1) >= Protection_t
```

---

## V-RSK-005 — ExitObligation

Definition:

```text Indicates that the current position has entered a state requiring exit.
```

Domain:

```text TRUE / FALSE
```

Status:

```text DERIVED
```

---

# 17. Position Variables

## V-POS-001 — PositionQuantity

Definition:

```text Actual currently held quantity based solely on authoritative execution events.
```

Status:

```text DERIVED
```

Invariant:

```text PositionQuantity >= 0
```

---

## V-POS-002 — AverageEntryPrice

Definition:

```text Canonical average economic entry price derived from actual entry fills.
```

Status:

```text DERIVED
```

---

## V-POS-003 — ExposureValue

Definition:

```text Current economic value of actual position exposure under the declared valuation convention.
```

Status:

```text DERIVED
```

---

# 18. P&L Variables

## V-PNL-001 — CurrentPnL

Definition:

```text Current economic result of the active position under the declared valuation convention.
```

Status:

```text DERIVED
```

Critical unresolved dependency:

```text exact valuation price convention = TODO.
```

---

## V-PNL-002 — RealizedPnL

Definition:

```text Economic result realized through completed executions and applicable costs.
```

Status:

```text DERIVED
```

---

## V-PNL-003 — PeakPnL

Definition:

```text Maximum observed CurrentPnL during the active trade lifecycle.
```

Formula:

```text PeakPnL_t
=
max(PeakPnL_(t-1), CurrentPnL_t)
```

Status:

```text DERIVED
```

---

## V-PNL-004 — ProfitGiveback

Definition:

```text PeakPnL - CurrentPnL
```

when CurrentPnL is below PeakPnL.

Status:

```text DERIVED
```

Invariant:

```text ProfitGiveback >= 0
```

---

## V-PNL-005 — ActualHoldingTime

Definition:

```text ActualExitTimestamp - ActualEntryTimestamp.
```

Status:

```text DERIVED
```

Important:

```text outcome variable
```

not an entry-time prediction.

---

# 19. Prediction Variables

## V-PRED-001 — ExpectedHorizon

Definition:

```text Model-estimated future holding/continuation horizon relevant to the current opportunity or active trade.
```

Status:

```text DERIVED
```

---

## V-PRED-002 — ExpectedProfitFloor

Definition:

```text Model-derived lower quantile or equivalent conservative estimate of future economic outcome used by the management framework.
```

Status:

```text LEARNED
```

Exact quantile:

```text UNFROZEN.
```

---

## V-PRED-003 — ContinuationValue

Definition:

```text Estimated value of maintaining the current position rather than exiting under the current state.
```

Status:

```text DERIVED
```

---

## V-PRED-004 — EmergencyReversalProbability

Definition:

```text Probability or statistical evidence that the current directional thesis has entered an adverse reversal regime.
```

Status:

```text DERIVED
```

---

# 20. Trade Management Variables

## V-MGT-001 — TradeID

Definition:

```text Immutable identity of an active or completed trade lifecycle.
```

Status:

```text FROZEN
```

---

## V-MGT-002 — Mode

Definition:

```text Current validated trade-management regime.
```

Possible conceptual values:

```text MICRO
SCALP
EXTENDED
INTRADAY
```

Exact state set remains subject to the finalized transition specification.

---

## V-MGT-003 — ModeTransitionEvidence

Definition:

```text Evidence supporting a transition between management modes.
```

Status:

```text DERIVED
```

---

## V-MGT-004 — StateTransitionSensitivity

Definition:

```text Parameter governing the sensitivity of management-state transitions to new evidence.
```

Status:

```text LEARNED
```

---

# 21. Execution Variables

## V-EXE-001 — OrderID

Definition:

```text Immutable identifier of an order intent/submission.
```

Status:

```text FROZEN
```

---

## V-EXE-002 — OrderStatus

Domain includes:

```text CREATED
SUBMITTED
ACCEPTED
PARTIALLY_FILLED
FILLED
CANCEL_REQUESTED
CANCELLED
REJECTED
UNKNOWN
```

Exact broker statuses may be mapped into this canonical domain.

---

## V-EXE-003 — RequestedQuantity

Definition:

```text Quantity requested for execution.
```

Status:

```text DERIVED
```

---

## V-EXE-004 — ExecutedQuantity

Definition:

```text Quantity actually executed according to authoritative fill events.
```

Status:

```text EXTERNAL / DERIVED
```

---

## V-EXE-005 — ActualFillPrice

Definition:

```text Actual price at which the execution occurred.
```

Status:

```text EXTERNAL
```

For historical simulation:

```text MODELED.
```

---

## V-EXE-006 — ActualExecutionCost

Definition:

```text Actual transaction and execution cost associated with the trade.
```

Status:

```text EXTERNAL / DERIVED
```

---

## V-EXE-007 — Slippage

Definition:

```text Difference between actual execution and the declared reference execution price.
```

Status:

```text DERIVED
```

Exact reference price:

```text UNFROZEN.
```

---

# 22. Operational Variables

## V-OPS-001 — OperationalState

Domain:

```text NORMAL
DATA_DEGRADED
RECONCILIATION_REQUIRED
SYSTEM_HALTED
```

Status:

```text FROZEN
```

---

## V-OPS-002 — DataQualityState

Definition:

```text Current quality status of required market data.
```

Status:

```text DERIVED
```

---

## V-OPS-003 — ReconciliationStatus

Definition:

```text Whether internal state agrees with authoritative external execution state.
```

Status:

```text DERIVED
```

---

# 23. Opportunity Variables

## V-OPP-001 — OpportunityID

Definition:

```text Immutable identifier for a historically eligible strategy opportunity.
```

Status:

```text FROZEN
```

---

## V-OPP-002 — OpportunityTimestamp

Definition:

```text Timestamp at which the opportunity became evaluable using only available information.
```

Status:

```text DERIVED
```

---

## V-OPP-003 — OpportunityEligibility

Definition:

```text Whether the current market state satisfies the pre-decision opportunity population definition.
```

Status:

```text DERIVED
```

---

## V-OPP-004 — NoTradeReason

Definition:

```text Structured reason explaining why an eligible opportunity did not produce a trade.
```

Status:

```text DERIVED
```

---

# 24. Label Variables

## V-LBL-001 — LabelID

Definition:

```text Immutable identity of a historical label.
```

Status:

```text FROZEN
```

---

## V-LBL-002 — LabelDefinitionVersion

Definition:

```text Version of the mathematical definition used to produce the label.
```

Status:

```text FROZEN
```

---

## V-LBL-003 — LabelObservationStart

Definition:

```text Beginning of the future observation interval required by the label.
```

Status:

```text DERIVED
```

---

## V-LBL-004 — LabelObservationEnd

Definition:

```text End of the future observation interval required by the label.
```

Status:

```text DERIVED
```

---

## V-LBL-005 — LabelMaturityTime

Definition:

```text Earliest time at which all information required to determine the label is available.
```

Status:

```text DERIVED
```

---

## V-LBL-006 — LabelStatus

Domain:

```text IMMATURE
MATURED
INVALID
EXCLUDED
```

Status:

```text FROZEN
```

---

# 25. Learning Variables

## V-LEARN-001 — TrainingCutoff

Definition:

```text Latest information timestamp permitted in a training dataset.
```

Status:

```text CONFIGURED BY WALK-FORWARD PROCEDURE
```

---

## V-LEARN-002 — ValidationWindow

Definition:

```text Chronological interval used for validation.
```

Status:

```text CONFIGURED BY RESEARCH PROTOCOL
```

---

## V-LEARN-003 — TestWindow

Definition:

```text Chronological interval reserved for out-of-sample confirmation.
```

Status:

```text CONFIGURED BY RESEARCH PROTOCOL
```

---

## V-LEARN-004 — ParameterVersion

Definition:

```text Immutable identifier of a parameter set.
```

Status:

```text FROZEN
```

---

## V-LEARN-005 — ModelVersion

Definition:

```text Immutable identifier of a statistical model implementation and configuration.
```

Status:

```text FROZEN
```

---

## V-LEARN-006 — LearningEligible

Definition:

```text Whether an observation is eligible to enter the learning dataset at the current time.
```

Status:

```text DERIVED
```

---

# 26. Runtime Variables

## V-RUN-001 — StrategyRuntimeVersion

Definition:

```text Immutable bundle identifying the complete strategy runtime used for a decision.
```

It references:

```text ModelVersion
ParameterVersion
FeatureVersion
RiskPolicyVersion
ExecutionPolicyVersion
DataContractVersion.
```

Status:

```text FROZEN
```

---

## V-RUN-002 — FeatureVersion

Definition:

```text Version of the feature definitions and transformations used by the strategy.
```

Status:

```text FROZEN
```

---

## V-RUN-003 — ExecutionPolicyVersion

Definition:

```text Version of the execution assumptions and execution rules.
```

Status:

```text FROZEN
```

---

## V-RUN-004 — RiskPolicyVersion

Definition:

```text Version of the risk-management rules.
```

Status:

```text FROZEN
```

---

# 27. Research Variables

## V-RES-001 — ExperimentID

Definition:

```text Immutable identifier of a research experiment.
```

---

## V-RES-002 — DatasetVersion

Definition:

```text Immutable version of the historical dataset used by an experiment.
```

---

## V-RES-003 — ExperimentConfiguration

Definition:

```text Complete configuration used to execute an experiment.
```

---

## V-RES-004 — ExperimentResult

Definition:

```text Immutable recorded result of an experiment.
```

---

# 28. Variable Dependency Rules

Every variable must satisfy:

```text Variable
    ↓
Dependencies
    ↓
Earlier information
```

No variable may depend on a variable whose availability occurs later in the same decision boundary.

---

# 29. Canonical Temporal Dependencies

The principal chain is:

```text Event
 ↓
MarketState
 ↓
FeatureState
 ↓
ProbabilityState
 ↓
EconomicState
 ↓
Decision
 ↓
Execution
 ↓
Position
 ↓
TradeManagement
 ↓
Outcome
 ↓
Label
 ↓
Learning
 ↓
FutureModel.
```

This is the canonical temporal ordering.

---

# 30. Forbidden Dependencies

The following are explicitly forbidden:

```text CurrentDecision
    -> FutureOutcome

CurrentProbability
    -> FutureLabel

CurrentRisk
    -> FuturePnL

HistoricalDecision
    -> LaterModelVersion

HistoricalFeature
    -> FullDatasetStatistic
```

unless the relevant information was genuinely available at the original decision timestamp.

---

# 31. Variable Uniqueness Rule

There must not be two canonical variables representing the same semantic quantity.

For example, these are prohibited:

```text CurrentProfit
CurrentPnL
OpenProfit
UnrealizedProfit
```

if they all mean the same thing.

Only:

```text CurrentPnL
```

is canonical.

Aliases may exist at the API boundary, but they must map to the same canonical variable.

---

# 32. Expected Versus Actual Rule

The naming convention is mandatory:

```text ExpectedX
=
prediction

ActualX
=
observed outcome.
```

Examples:

```text ExpectedHorizon
ActualHoldingTime

ExpectedExecutionCost
ActualExecutionCost

ExpectedValue
RealizedPnL.
```

---

# 33. State Versus Prediction Rule

A variable describing what is happening now is state.

A variable describing what is expected to happen later is prediction.

Therefore:

```text CurrentPnL
=
state

ExpectedProfit
=
prediction.
```

They must never be merged.

---

# 34. Market Versus Execution Rule

Observed market activity is not our execution.

Therefore:

```text MarketTradePrice
!=
ActualFillPrice.
```

This is a permanent canonical distinction.

---

# 35. Registry Integrity Rule

Every implementation variable that influences:

```text decision
risk
execution
learning
performance
```

must map to a registry entry.

Unregistered variables are implementation defects.

---

# 36. External Mapping Rule

Every variable marked:

```text EXTERNAL
```

must eventually have:

```text Provider
ProviderField
SourceSemantics
HistoricalAvailability
Entitlement
Precision
TimestampSemantics
```

before production use.

---

# 37. Unknown Handling

Until external documentation is supplied:

```text UNKNOWN
```

means exactly:

```text not yet verified.
```

It does not mean:

```text probably available.
```

No implementation is allowed to silently convert UNKNOWN into an assumption.

---

# 38. Current External TODOs

The registry currently has unresolved external mappings for:

```text EventTimestamp semantics
InstrumentID
Expiry
StrikePrice
LotSize
TickSize
UnderlyingPrice
BidPrice
AskPrice
BidQuantity
AskQuantity
TradeQuantity
Volume semantics
Depth semantics
TBT sequencing
Option-chain semantics
Historical availability
```

These are documentation tasks, not mathematical design blockers.

---

# 39. Current Numerical TODOs

The following remain deliberately unfrozen:

```text Profit-floor quantile
Continuation threshold
Emergency-reversal threshold
State-transition sensitivity
Feature lookbacks
Risk coefficients
Execution-cost parameters
Slippage parameters
Quote-freshness threshold
```

They must be learned or validated through the walk-forward framework.

---

# 40. Critical Registry Invariants

```text REG-001
Every canonical variable has exactly one VariableID.

REG-002
Every canonical variable has exactly one owner.

REG-003
Every derived variable has explicit dependencies.

REG-004
Every external variable has a source.

REG-005
Every learned parameter has a training procedure.

REG-006
Every temporal variable has timestamp semantics.

REG-007
Expected and Actual variables are distinct.

REG-008
Market and execution observations are distinct.

REG-009
Unknown external mappings are never silently assumed.

REG-010
Deprecated variables cannot be used by new implementation code.

REG-011
No variable may introduce future information into an earlier state.

REG-012
Every decision-affecting implementation variable maps to the registry.
```

---

# 41. Registry as Single Source of Truth

From this point forward:

```text Mathematical specification
        ↓
Variable Registry
        ↓
Implementation
```

The registry becomes the authoritative bridge.

If an implementation engineer asks:

```text "What is CurrentPnL?"
```

the answer comes from:

```text V-PNL-001.
```

If they ask:

```text "Can this variable use future information?"
```

the answer comes from its:

```text dependencies
timestamp
availability
```

If they ask:

```text "Where does this value come from?"
```

the answer comes from:

```text Source
ExternalMapping.
```

---

# 42. Architecture Status

At this stage:

```text Mathematical specification      COMPLETE

State machine                      COMPLETE

Consistency audit                  COMPLETE

Implementation contracts           COMPLETE

Verification plan                  COMPLETE

Data-to-event contract             COMPLETE

Canonical variable registry        COMPLETE

TrueData field mapping             PENDING DOCUMENTATION

Broker execution mapping           PENDING DOCUMENTATION

Numerical calibration              PENDING HISTORICAL DATA
```

The architecture itself is now sufficiently mature to begin translating the contracts into an implementation skeleton.

---

# 43. Next Artifact

The next artifact should be:

# CANONICAL EVENT SCHEMA AND STATE SCHEMA

This is the first artifact that gets close to actual code structure.

We will define the exact shape of:

```text CanonicalMarketEvent
CanonicalQuoteEvent
CanonicalTradeEvent
CanonicalOptionEvent
CanonicalOrderEvent
CanonicalFillEvent
CanonicalDataQualityEvent
```

and then:

```text MarketState
FeatureState
ProbabilityState
EconomicState
RiskState
PositionState
TradeManagementState
OperationalState.
```

We will deliberately keep provider-specific fields abstract until the TrueData documentation is supplied.

The result will be the direct contract that the eventual implementation must satisfy.