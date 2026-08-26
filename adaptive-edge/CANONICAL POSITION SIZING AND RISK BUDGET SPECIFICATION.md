# CANONICAL POSITION SIZING AND RISK BUDGET SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines how the strategy determines:

```text
whether risk may be taken
how much risk may be taken
how many option lots may be purchased
maximum permitted loss
initial protection
risk state after entry
risk behavior during trade management
```

The central architectural rule is:

```text
Prediction → Economic Opportunity
Risk Policy → Risk Authorization
Risk Authorization → Position Size
```

These are separate transformations.

A better prediction cannot automatically create more risk capacity.

---

# 2. Core Risk Principle

The system distinguishes:

```text
Expected Return
Probability
Economic Edge
Risk Budget
Position Size
Protection
```

They are related, but they are not interchangeable.

In particular:

```text
Higher Probability
        !=
Higher Risk Authorization
```

and:

```text
Dynamic Mode Change
        !=
Risk Budget Change
```

---

# 3. Risk Budget

Define:

```text
R_strategy(t)
```

as the maximum loss the strategy is authorized to accept under the current risk policy.

This is a policy variable.

It is not estimated from:

```text current probability
current unrealized profit
current market confidence.
```

---

# 4. Risk Budget Hierarchy

Risk authorization is hierarchical:

```text
Account Risk Limit
        ↓
Strategy Risk Limit
        ↓
Session Risk Limit
        ↓
Trade Risk Limit
        ↓
Position Risk Limit
        ↓
Quantity
```

A lower-level component cannot exceed an upper-level limit.

---

# 5. Account Risk Limit

The account-level risk limit represents the maximum exposure the strategy is permitted to create relative to the available trading capital.

The exact definition depends on the eventual broker/account contract.

It remains:

```text UNFROZEN.
```

---

# 6. Strategy Risk Limit

The strategy receives an explicit maximum risk budget.

Conceptually:

```text R_strategy <= R_account
```

The strategy cannot override the account-level limit.

---

# 7. Session Risk Limit

A session-level risk budget may restrict cumulative losses during a trading session.

Conceptually:

```text R_session_remaining
=
R_session_limit
-
RealizedRiskUsage
```

The exact reset and loss-accounting convention remain to be finalized.

---

# 8. Trade Risk Limit

Each new trade receives an independent maximum authorized risk:

```text R_trade.
```

The trade cannot consume more than:

```text R_trade <= R_session_remaining
```

and:

```text R_trade <= R_strategy_remaining.
```

---

# 9. Risk Authorization

Before entry:

```text RiskAuthorization_t
```

must be explicitly created.

It contains:

```text RiskAuthorizationID
TradeID
AuthorizedRisk
AuthorizedQuantity
RiskPolicyVersion
Timestamp
Reason
```

---

# 10. Risk Authorization Is Immutable

Once an entry is authorized:

```text AuthorizedRisk
```

cannot increase because:

```text probability increases
expected value increases
market moves favorably
trade enters profit
management mode changes.
```

Any new risk authorization would constitute a separate architectural event.

---

# 11. Baseline No-Pyramiding Rule

The baseline strategy does not increase exposure to an existing trade.

Therefore:

```text ActivePosition
+
NewSignal
```

does not produce additional quantity.

It produces either:

```text IGNORE
```

or:

```text separate opportunity
```

according to the explicit trade-concurrency policy.

---

# 12. Risk Per Unit

For candidate option `o`, define:

```text RiskPerUnit_o
```

as the maximum permitted loss attributable to one tradable unit under the defined protection/execution model.

For a long option:

```text RiskPerUnit
```

must include:

```text entry cost
+
maximum permitted adverse movement
+
relevant execution costs.
```

The exact protection model determines the final expression.

---

# 13. Position Size

The theoretical quantity is:

```text Q_raw
=
AuthorizedRisk
/
RiskPerUnit
```

Actual quantity is then constrained by:

```text lot size
capital
liquidity
maximum quantity
broker constraints.
```

---

# 14. Lot Rounding

If the instrument trades in discrete lots:

```text Q_actual
=
floor(Q_raw / LotSize) × LotSize
```

subject to the risk convention.

The rounding direction must never increase authorized risk.

---

# 15. Zero-Quantity Rule

If:

```text Q_actual = 0
```

then:

```text NO_TRADE.
```

The system does not increase quantity merely to satisfy a minimum lot size.

---

# 16. Maximum Position Constraint

Even if the risk calculation permits a large quantity:

```text Q_actual <= Q_max
```

must hold.

`Q_max` may be constrained by:

```text capital
liquidity
instrument exposure
strategy policy
broker limits.
```

---

# 17. Liquidity Constraint

The position size must also respect executable market liquidity.

Conceptually:

```text Q_actual <= Q_liquidity.
```

The exact liquidity model remains dependent on available market-depth data.

---

# 18. Slippage-Aware Quantity

If expected slippage increases with quantity:

```text RiskPerUnit(Q)
```

is not necessarily constant.

Therefore, where evidence supports it, quantity must be solved iteratively or through a validated cost function.

Conceptually:

```text Find Q such that:

ExpectedRisk(Q) <= AuthorizedRisk.
```

The simplistic:

```text Risk / fixed_unit_risk
```

formula is only valid when the cost/risk relationship is sufficiently linear.

---

# 19. Capital Constraint

The position must satisfy:

```text RequiredCapital(Q)
<=
AvailableCapital.
```

A positive expected-value trade is rejected if it cannot be funded under the applicable account rules.

---

# 20. Initial Protection

Every active position must have an initial protection definition.

Conceptually:

```text InitialProtection
```

is established at or immediately after entry according to the strategy specification.

The protection may be expressed using:

```text option price
underlying price
economic loss
market structure.
```

The final mathematical form remains linked to the previously defined protection architecture.

---

# 21. Protection Is Not a Prediction

Protection exists to control downside.

It is not:

```text predicted future price
```

and must not be derived from:

```text optimistic expected value.
```

---

# 22. Maximum Loss

The system must calculate:

```text MaximumPermittedLoss
```

before entry.

The trade is eligible only if:

```text MaximumPermittedLoss
<=
AuthorizedRisk.
```

---

# 23. Actual Loss Can Differ

Actual realized loss can differ from modeled maximum loss because of:

```text gaps
slippage
execution delay
liquidity
partial fills
market discontinuity.
```

Therefore the risk model must distinguish:

```text modelled risk
```

from:

```text realized execution outcome.
```

---

# 24. Gap Risk

If the market moves through the protection level before execution:

```text realized loss > nominal protection loss
```

may occur.

The system must not falsely classify this as a violation of the mathematical model.

It is an execution-risk event.

---

# 25. Risk State After Entry

Once the first fill occurs:

```text RiskState
```

becomes associated with the position.

It records:

```text AuthorizedRisk
InitialRisk
CurrentProtectedRisk
PeakProfit
CurrentRiskStatus
RiskPolicyVersion.
```

---

# 26. Initial Risk Immutability

The original:

```text AuthorizedRisk
```

is immutable.

The system may reduce risk.

It cannot silently expand the original authorization.

---

# 27. Risk Reduction

Suppose:

```text InitialRisk = R0.
```

Later protection improves:

```text CurrentProtectedRisk < R0.
```

This is permitted.

The strategy has reduced risk.

---

# 28. Risk Expansion

The reverse is prohibited:

```text CurrentProtectedRisk > PreviouslyAuthorizedRisk
```

unless an explicit new risk authorization event exists.

The baseline architecture does not generate such an event during an active trade.

---

# 29. Profit Cannot Be Reused as Risk Capital

This invariant is critical.

Suppose:

```text Trade enters
Trade becomes profitable
```

The system cannot say:

```text "We have ₹X unrealized profit,
therefore we can now tolerate ₹X additional downside."
```

unless such behavior is explicitly part of a separately validated risk policy.

The baseline strategy does not permit it.

---

# 30. Dynamic Management Separation

The strategy may transition:

```text MODE_A
    ↓
MODE_B
```

because market conditions change.

This does not automatically change:

```text RiskAuthorization.
```

---

# 31. Dynamic Mode Example

Suppose:

```text InitialMode = SCALP
InitialRisk = R
```

and later:

```text Mode = INTRADAY.
```

Then:

```text RiskAuthorization = R
```

unless an explicit independent risk event says otherwise.

The mode change cannot create:

```text RiskAuthorization = 2R.
```

---

# 32. Protection Monotonicity

For a long position, define:

```text ProtectedRisk_t
```

as the amount of risk still exposed under the active protection mechanism.

The baseline invariant is:

```text ProtectedRisk_(t+1)
<=
ProtectedRisk_t
```

unless a separately specified event explicitly authorizes otherwise.

In normal operation, protection may tighten.

It may not loosen.

---

# 33. Profit Locking

When the position has generated sufficient favorable movement, the protection system may lock some of the accumulated profit.

Conceptually:

```text CurrentProtection
>
InitialProtection
```

for a profitable long trade.

The exact trigger remains a learned/configured quantity.

---

# 34. Trailing Protection

A trailing mechanism can be represented as:

```text Protection_t
=
f(
PeakObservedState_t,
RiskPolicy,
MarketState
)
```

subject to:

```text Protection_(t+1) >= Protection_t
```

when protection is expressed as a favorable exit threshold.

---

# 35. Current P&L Versus Risk

Current P&L is:

```text CurrentPnL.
```

Risk is:

```text RemainingRisk.
```

They must never be merged into one variable.

---

# 36. Peak P&L

The canonical peak-profit variable is:

```text PeakPnL_t
=
max(PnL_0 ... PnL_t).
```

Therefore:

```text PeakPnL_(t+1) >= PeakPnL_t.
```

---

# 37. Giveback

Define:

```text Giveback_t
=
max(0, PeakPnL_t - CurrentPnL_t).
```

Giveback is an observation.

It is not itself a risk budget.

---

# 38. Giveback Cannot Increase Risk Budget

An increase in:

```text Giveback
```

may trigger:

```text trade-management action
```

but cannot increase:

```text AuthorizedRisk.
```

---

# 39. Emergency Exit

If the emergency-reversal or emergency-exit condition is satisfied:

```text ExitObligation = TRUE.
```

This is a reduction of risk.

It does not create permission for a new opposite position.

---

# 40. Exit Priority

The risk hierarchy is:

```text System Safety
    >
Position Protection
    >
Trade Management
    >
New Entry Opportunity
```

A new signal cannot override an existing safety obligation.

---

# 41. Session-Level Loss Control

If cumulative realized losses reach the configured session risk boundary:

```text NewEntryAuthorization = FALSE.
```

Existing positions continue under their independent protection policy.

---

# 42. Risk Lockout

A session risk lockout is represented explicitly:

```text RiskStatus = HALTED.
```

The system does not rely on downstream components remembering not to trade.

---

# 43. Lockout Reset

Reset conditions must be explicitly defined.

A risk lockout cannot disappear because:

```text probability improves
new opportunity appears
market regime changes.
```

---

# 44. Concurrent Positions

If multiple positions are allowed, total risk must satisfy:

```text Σ PositionRisk_i
<=
PortfolioRiskAuthorization.
```

The sum must use the defined risk convention rather than simply adding:

```text option premiums.
```

---

# 45. Correlated Positions

If simultaneous positions are permitted, correlation may cause actual portfolio risk to exceed the sum of isolated trade risks.

Therefore the architecture permits:

```text PortfolioRiskAdjustment.
```

The exact methodology remains a research parameter.

---

# 46. Baseline Simplification

The first production version should avoid unnecessary portfolio optimization.

The baseline may initially enforce:

```text one active position at a time
```

if that produces a cleaner and more auditable risk system.

Whether multiple simultaneous positions are ultimately permitted must be validated separately.

---

# 47. Risk Concentration

The strategy must not indirectly concentrate exposure through:

```text multiple correlated options
multiple signals on the same underlying
multiple entries representing the same thesis.
```

A portfolio-level exposure identity may therefore be required.

---

# 48. Underlying Exposure

For an option position, risk analysis should retain:

```text OptionExposure
UnderlyingExposure
```

as separate concepts.

The option premium alone does not fully describe directional exposure.

---

# 49. Delta-Based Exposure

Where Greek data is available:

```text DeltaExposure
```

may be recorded.

However:

```text Delta exposure
```

is not automatically equivalent to:

```text risk.
```

It is an explanatory exposure measure.

---

# 50. Gamma and Convexity

For short-duration option positions, nonlinear exposure may become significant.

Therefore the risk framework may track:

```text Delta
Gamma
Theta
Vega
```

but only validated quantities should influence production risk decisions.

---

# 51. Risk Recalculation

Risk state may be recalculated after:

```text fill
market update
protection movement
partial exit
```

But:

```text AuthorizedRisk
```

remains unchanged.

Only:

```text CurrentRisk
```

may change.

---

# 52. Partial Exit

If a partial exit occurs:

```text PositionQuantity decreases.
```

Remaining risk must be recalculated.

It cannot increase because of the partial exit.

---

# 53. Partial Fill

If only part of the entry order fills:

```text ActualPositionRisk
```

is based on the actual filled quantity.

Unfilled quantity does not count as position risk.

---

# 54. Order Cancellation

Cancelled/unfilled quantity has:

```text no position risk.
```

The system must not treat an order request as an actual exposure.

---

# 55. Failed Exit

If an exit order fails:

```text Position remains active.
```

The system must retain:

```text ExitObligation = TRUE.
```

and escalate through the execution/recovery policy.

A failed exit does not eliminate the underlying risk.

---

# 56. Risk-Reconciliation Failure

If actual broker position differs from internal position:

```text RiskStatus = RECONCILIATION_REQUIRED.
```

New entries are prohibited.

---

# 57. Risk Calculation Provenance

Every risk authorization must reference:

```text RiskPolicyVersion
EconomicStateVersion
OptionStateVersion
ExecutionCostModelVersion
PositionSizingVersion.
```

This makes quantity reproducible.

---

# 58. Position-Sizing Function

Conceptually:

```text Q_t
=
PositionSize(
AuthorizedRisk_t,
RiskPerUnit_t,
Liquidity_t,
Capital_t,
LotSize_t
)
```

with:

```text Q_t >= 0.
```

---

# 59. Position-Sizing Safety Constraint

The function must satisfy:

```text Risk(Q_t)
<=
AuthorizedRisk_t.
```

This is the fundamental sizing invariant.

---

# 60. Risk Monotonicity

If all other inputs remain constant:

```text Higher AuthorizedRisk
```

may produce:

```text equal or higher permitted quantity.
```

But:

```text Higher Probability
```

alone must not.

---

# 61. Risk Function Independence

The position-sizing function cannot directly consume:

```text raw model confidence
```

unless the risk specification explicitly defines confidence as a validated risk-policy input.

The baseline does not.

---

# 62. Risk and Expected Value

A trade with:

```text very high expected value
```

can still receive:

```text zero quantity
```

if:

```text risk authorization = zero.
```

This is intentional.

---

# 63. Risk and Profit Floor

A strong profit floor does not increase risk authorization.

It can only influence:

```text economic eligibility.
```

---

# 64. Risk and Continuation

A high continuation probability may justify:

```text holding
```

but does not justify:

```text increasing initial risk.
```

---

# 65. Risk and Emergency Reversal

A high reversal probability can trigger:

```text exit.
```

It cannot trigger:

```text opposite entry.
```

in the baseline architecture.

---

# 66. Risk State Machine

The canonical risk lifecycle is:

```text UNAUTHORIZED
      ↓
AUTHORIZED
      ↓
ACTIVE
      ↓
REDUCING
      ↓
CLOSED
```

With failure states:

```text RISK_BREACH
RECONCILIATION_REQUIRED
HALTED
```

---

# 67. Risk Authorization Transition

```text Opportunity
    ↓
Economic Eligibility
    ↓
Risk Evaluation
    ↓
RiskAuthorization
```

Failure:

```text NO_TRADE.
```

---

# 68. Risk Authorization Preconditions

All must hold:

```text valid economic decision
available session risk
available account/strategy risk
valid quantity calculation
valid execution conditions
valid operational state.
```

---

# 69. Risk Authorization Postconditions

The system records:

```text authorized quantity
authorized risk
initial protection
risk policy version
timestamp
```

and freezes the authorization.

---

# 70. Risk Breach

A risk breach occurs when:

```text ActualRisk
>
PermittedRisk
```

according to the authoritative risk model.

The response is:

```text stop new entries
flag position
invoke safety policy.
```

---

# 71. No Automatic Risk Expansion

After a breach:

```text system cannot increase risk authorization
```

to accommodate the actual position.

It must reduce/reconcile the exposure.

---

# 72. Risk Invariants

```text RISK-001 id="k3ng1m"
AuthorizedRisk is explicitly created.

RISK-002
AuthorizedRisk is immutable during a trade.

RISK-003
Position size cannot exceed authorized risk.

RISK-004
Mode changes cannot increase risk.

RISK-005
Probability changes cannot increase risk.

RISK-006
Unrealized profit cannot automatically create new risk capacity.

RISK-007
Protection cannot loosen.

RISK-008
Partial exits cannot increase remaining risk.

RISK-009
Unfilled orders are not positions.

RISK-010
Failed exits preserve the exit obligation.

RISK-011
Reconciliation failure blocks new exposure.

RISK-012
Risk breach fails closed.

RISK-013
Risk budget and economic value are separate variables.

RISK-014
Risk authorization is versioned.

RISK-015
Every quantity calculation is reproducible.

RISK-016
Risk constraints dominate opportunity generation.
```

---

# 73. Numerical Parameters Still Unfrozen

We deliberately have not selected:

```text account risk percentage
strategy risk percentage
session loss limit
per-trade risk
maximum position size
maximum concurrent positions
portfolio correlation adjustment
protection distance
trailing parameters
minimum risk-reward requirement
slippage assumptions
risk buffer.
```

These must be established through the research and validation protocol.

---

# 74. Important Architectural Boundary

At this point the complete decision chain is:

```text id="4m7z8a"
MARKET DATA
    ↓
CAUSAL STATE
    ↓
FEATURES
    ↓
PROBABILITY
    ↓
OUTCOME DISTRIBUTION
    ↓
ECONOMIC VALUE
    ↓
OPTION SELECTION
    ↓
RISK AUTHORIZATION
    ↓
POSITION SIZE
    ↓
EXECUTION
```

No stage may bypass the stage immediately above it.

---

# 75. Architecture Status

```text Mathematical Specification              COMPLETE
Variable Registry                          COMPLETE
Event Schema                               COMPLETE
State Schema                               COMPLETE
State Transition Specification              COMPLETE
Research Dataset Specification              COMPLETE
Walk-Forward Specification                  COMPLETE
Statistical Estimation Specification       COMPLETE
Economic Decision Specification             COMPLETE
Option Selection Specification              COMPLETE
Risk Budget Specification                   COMPLETE
Position Sizing Specification               COMPLETE
```

The remaining unknowns are primarily numerical and external-data dependent.

---

# 76. Next Artifact

The next artifact should now be the:

# CANONICAL EXECUTION, SLIPPAGE AND FILL MODEL SPECIFICATION

This is the remaining major bridge between a mathematically valid decision and actual realized P&L.

We will specify:

```text order generation
quote selection
marketability
spread
slippage
partial fills
latency
order rejection
order cancellation
fill sequencing
execution cost estimation
historical execution simulation
worst-case execution assumptions
```

That artifact is critical because an apparent statistical edge that disappears under realistic execution costs is not an edge.