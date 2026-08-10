# Adaptive Edge — Risk Semantics

## Risk is authorization, not prediction

```text
Edge says: opportunity quality.
Economics says: whether acting is worthwhile after cost.
Risk says: how much loss is authorized.
```

These values cannot be substituted for one another.

## Immutable authorization

`RiskAuthorization` is immutable for the opportunity for which it was issued.

The following cannot increase it implicitly:

- favorable P&L
- increased prediction score
- DynamicMode transition
- better fill
- lower realized execution cost

A new authorization requires an explicit policy event.

## Profit protection

Peak P&L is accounting state, not risk budget:

```text
PeakPnL(t) = max(CurrentPnL(τ))
ProfitGiveback(t) = PeakPnL(t) - CurrentPnL(t)
```

Protection can reduce exposure or force an exit. It cannot silently increase the risk ceiling.

## Position sizing

The exact Adaptive Edge risk-per-unit and sizing equations are locked until recovered as F-107/F-108. Do not substitute the existing generic Kite sizing or another strategy's sizing formula.
