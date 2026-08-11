# Adaptive Edge — End-to-End Strategy Specification

## 1. Objective

Adaptive Edge is a standalone Sterling strategy that evaluates market state, estimates opportunity/edge, evaluates the economics of acting on that opportunity, applies the strategy's dynamic operating mode, obtains explicit risk authorization, and only then produces execution intent.

It is not a renamed SuperTrend or Value Flow Navigator strategy.

## 2. Pipeline

```text
Market Data
  -> Feature Layer
  -> Edge / Prediction
  -> Economic Evaluation
  -> Dynamic Mode
  -> Risk Authorization
  -> Position Sizing
  -> Execution Intent
  -> Order / Fill
  -> Position State
  -> P&L / Peak P&L
  -> Profit Protection / Exit
```

## 3. Hard boundaries

### Strategy semantics

The strategy owns its feature definitions, edge definition, eligibility, mode transitions, economic gate, and strategy-specific exits.

### Platform semantics

Sterling owns normalized market data, broker adapters, order routing, authoritative fills, persistence, reconciliation, and safety infrastructure.

## 4. State model

At minimum the strategy state is conceptually:

```text
OBSERVATION
CANDIDATE
EVALUATED
AUTHORIZED
INTENT
ORDERED
PARTIALLY_FILLED
OPEN
PROTECTING
EXIT_INTENT
CLOSED
REJECTED
```

A state transition must be causally explainable and auditable.

## 5. Economic separation

Prediction answers:

```text
"What is the expected opportunity?"
```

Economic evaluation answers:

```text
"Is that opportunity still worth paying the costs required to express it?"
```

Risk authorization answers:

```text
"How much loss are we permitted to accept if the opportunity is wrong?"
```

These are distinct questions and must remain distinct modules.

## 6. Dynamic mode

Dynamic mode changes strategy behavior. It is not a risk budget.

```text
mode transition != risk authorization transition
```

A favorable P&L observation, a higher score, or a mode change cannot silently increase authorized risk.

## 7. Execution truth

```text
intent != order
order != fill
fill != position
```

Only authoritative fills change position state.

BUY execution uses the executable ask; SELL execution uses the executable bid. Spread, slippage, latency, partial fill, rejection and fees are execution concerns and must not be hidden inside the prediction formula.

## 8. Profit protection

Peak P&L and current P&L are accounting state:

```text
PeakPnL(t) = max(CurrentPnL(τ)) for τ <= t
ProfitGiveback(t) = PeakPnL(t) - CurrentPnL(t)
```

Profit protection may reduce exposure or trigger exit. It does not grant additional risk.

## 9. Backtest parity

The strategy formulae are identical in backtest and production. Only environment adapters differ.

```text
same strategy math
+ historical data/execution adapter
= backtest

same strategy math
+ live data/broker adapter
= production
```

## 10. Formula lock

See `FORMULAS.md`. F-001 through F-008 are explicitly anchored. F-101 through F-114 remain locked until the exact prior strategy definitions are recovered.

## 11. Failure policy

If a required strategy-specific definition cannot be recovered:

```text
STOP -> record missing definition -> recover specification -> implement
```

Never substitute another indicator, strategy, or familiar formula merely to complete the code path.
