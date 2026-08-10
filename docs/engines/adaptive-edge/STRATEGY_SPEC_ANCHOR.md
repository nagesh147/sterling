# Adaptive Edge Strategy Specification Anchor

Version: 0.1.0
Status: IMPLEMENTATION GUARDRAIL

## Purpose

This document is the implementation guardrail for the Adaptive Edge Kite engine.

The rule is simple:

> Implementation may not alter strategy semantics for convenience.

A formula may be implemented only when its mathematical definition is explicitly anchored to the strategy specification. If an exact formula is not recoverable, the implementation must stop at the boundary rather than inventing one.

## Scope

Adaptive Edge is a Sterling Kite engine only.

It is independent from:

- SuperTrend
- Flow Navigator
- crypto engines

It may use Sterling's shared Kite infrastructure for market data, execution, positions, safety, and accounting.

## Frozen decision pipeline

```text
Market Input
    -> State
    -> Opportunity Detection
    -> Prediction / Edge
    -> Economic Evaluation
    -> Dynamic Mode
    -> Risk Authorization
    -> Position Sizing
    -> Execution Intent
    -> Execution / Fill
    -> Position Management
    -> Profit Protection / Exit
```

## Semantic separations — MUST NOT collapse

```text
DynamicMode       != DynamicRisk
Prediction        != EconomicEligibility
EconomicEdge      != RiskAuthorization
RiskAuthorization != OrderIntent
OrderIntent       != Fill
Fill              != Position
Position          != Accounting
Backtest          != Production environment
```

## A-001 — Dynamic mode / dynamic risk separation

**Status: FROZEN**

A mode transition describes strategy behaviour. It does not grant risk capacity.

```text
mode(t -> t+1)
    MUST NOT imply
risk(t -> t+1)
```

In particular, becoming intraday cannot by itself increase authorized risk or permit previously protected predictive profit to be given back.

This is an executable invariant and is already represented in `contracts.py` and its tests.

## A-002 — Risk authorization immutability

**Status: FROZEN**

Once risk has been authorized for an opportunity, the authorization is immutable.

The following events cannot increase that authorization by implication:

- favorable mark-to-market P&L
- higher prediction score
- mode transition
- favorable execution
- partial exit
- lower estimated cost

Only an explicitly specified risk-policy transition may issue a new authorization.

## A-003 — Causal availability

**Status: FROZEN**

A decision at time `t` may use only information that was causally available at `t`.

```text
availability_time(input) <= decision_time
```

Future labels, future prices, future fills, future spread information, or future position outcomes must not enter the decision path.

## A-004 — Actual execution is authoritative

**Status: FROZEN**

Intent does not equal execution.

```text
OrderIntent -> Order -> Fill -> Position
```

Only authoritative fills change position state.

Partial fills remain partial. A failed exit does not erase the exit obligation.

## A-005 — Execution price semantics

**Status: FROZEN**

For realistic execution modelling:

```text
BUY  reference = executable ask
SELL reference = executable bid
```

Midpoint/LTP fills are not the default execution assumption.

Stale quotes cannot be used as valid fills.

Execution must explicitly model, where configured:

- spread
- latency
- slippage
- partial fills
- rejection/failure
- fees/costs

## A-006 — Accounting ownership

**Status: FROZEN**

Accounting is derived from authoritative execution state, not signal intent.

At minimum:

```text
CurrentPnL(t)
PeakPnL(t) = max(CurrentPnL(tau)) for tau <= t
ProfitGiveback(t) = PeakPnL(t) - CurrentPnL(t)
```

These definitions have one canonical owner.

## A-007 — Profit protection is not risk expansion

**Status: FROZEN**

Profit protection and risk authorization are separate mechanisms.

A protective rule may reduce exposure or force an exit. It must not silently increase the risk ceiling.

The implementation must therefore distinguish:

```text
profit protection state
risk authorization state
position state
```

## A-008 — Cost monotonicity

**Status: FROZEN**

Where the economic evaluation is defined as:

```text
ExpectedNetValue
    = ExpectedGrossValue - ExpectedExecutionCost
```

holding all other inputs constant:

```text
ExecutionCost ↑
    => ExpectedNetValue cannot improve
```

This property must be tested.

## A-009 — Backtest/live semantic parity

**Status: FROZEN**

The strategy mathematics must be identical between simulation and production.

Only environment-specific components may differ:

```text
historical data source vs live data source
simulated execution vs broker execution
simulated clock vs live clock
```

The strategy itself must not have a separate backtest formula.

## A-010 — Single authoritative formula owner

**Status: FROZEN**

A mathematical rule is implemented once.

No UI, backtester, reporting script, or alternate engine may independently reproduce a strategy formula and become a second source of truth.

## Formula implementation status

### Explicitly anchored and safe to implement

```text
F-001  Causal availability
F-002  Peak P&L
F-003  Profit giveback
F-004  Expected net value from gross value minus execution cost
F-005  Risk authorization immutability
F-006  Mode/risk independence
F-007  Executable BUY reference = ask
F-008  Executable SELL reference = bid
```

### Not yet safe to invent

The following require their exact strategy-specific mathematical definitions from the frozen design before implementation:

```text
F-101  Edge/prediction formula
F-102  Opportunity score
F-103  Opportunity eligibility thresholds
F-104  Dynamic-mode transition thresholds
F-105  Predictive-profit protection threshold/floor
F-106  Dynamic-risk schedule
F-107  Risk-per-unit formula
F-108  Position-sizing formula beyond platform constraints
F-109  Option-selection scoring formula
F-110  Entry trigger formula
F-111  Exit trigger formula
F-112  Trailing/profit-protection parameterization
F-113  Re-entry rule
F-114  Multiple-position/trade interaction rules
```

These are intentionally marked as `NOT IMPLEMENTED`. This is not incomplete engineering; it is a protection against semantic drift.

## Required implementation discipline

For every future formula, the implementation PR must contain:

```text
Formula ID
Mathematical definition
Input variables
Availability time for every input
Units
Boundary conditions
Version
Unit tests
Adversarial tests
```

A formula without these artifacts is not production code.

## Adversarial invariants

The following attacks must remain permanently tested:

```text
mode change -> risk increase          MUST FAIL
profit increase -> risk increase      MUST FAIL
future input -> historical decision   MUST FAIL
order without fill -> position change MUST FAIL
duplicate fill -> double position     MUST FAIL
higher cost -> better net edge        MUST FAIL
stale quote -> valid fill             MUST FAIL
failed exit -> obligation disappears  MUST FAIL
```

## Implementation gate

Adaptive Edge may proceed from contracts into feature/edge implementation only when every strategy-specific formula used by that layer has an explicit formula ID and source definition.

The correct response to an unavailable formula is:

```text
STOP
record missing formula
restore specification
then implement
```

Never:

```text
guess
simplify
substitute a familiar indicator
borrow SuperTrend logic
borrow Navigator logic
```
