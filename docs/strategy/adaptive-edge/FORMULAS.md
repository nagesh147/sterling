# Adaptive Edge Formula Registry

Formula IDs are immutable identifiers. The F-101..F-114 equations below are a **reconstructed strategy revision**, not a recovered historical transcript. They are implemented for research/backtest and are not production-authorized until validation passes.

## Anchored platform/strategy invariants

### F-001 — Causal availability
```text
availability_time(x) <= decision_time
```

### F-002 — Peak P&L
```text
PeakPnL(t) = max(CurrentPnL(tau)) for tau <= t
```

### F-003 — Profit giveback
```text
ProfitGiveback(t) = PeakPnL(t) - CurrentPnL(t)
```

### F-004 — Expected net value
```text
ExpectedNetValue = ExpectedGrossValue - ExpectedExecutionCost
```

### F-005 — Risk authorization immutability
Risk authorization cannot increase because of P&L, score, mode, execution quality, or partial exit.

### F-006 — Mode/risk independence
```text
DynamicMode != DynamicRisk
```

### F-007 / F-008 — Execution references
```text
BUY  = executable ASK
SELL = executable BID
```

---

# Reconstructed Adaptive Edge v0.1.0

## F-101 — Composite feature score

Inputs are first clipped to [-1, 1].

```text
S = 0.35*T + 0.30*M + 0.20*V + 0.15*X
```

where:

```text
T = directional trend score
M = normalized momentum score
V = relative-volume score
X = volatility-expansion score
```

Final:

```text
F101 = clip(S, -1, +1)
```

All features must be causally available.

## F-102 — Edge / prediction score

```text
F102 = tanh(2 * F101)
```

Sign determines direction; magnitude determines edge strength.

Expected gross opportunity value is modelled as:

```text
ExpectedGrossValue = |F102| * ExpectedMove
```

## F-103 — Opportunity eligibility

```text
eligible iff:
    |F102| >= 0.60
    AND confidence >= 0.55
    AND ExpectedGrossValue > ExpectedExecutionCost
```

## F-104 — Dynamic operating mode

```text
strength = |F102| * confidence

stale                    -> HALTED
late session             -> EXIT_ONLY
strength >= 0.48         -> INTRADAY
0.25 <= strength < 0.48  -> ACTIVE
0.12 <= strength < 0.25  -> DEFENSIVE
strength < 0.12          -> OBSERVE
```

Mode changes behavior only. It does not mutate risk authorization.

## F-105 — Predictive-profit protection

```text
giveback = max(PeakPnL - CurrentPnL, 0)
floor = max(0, PeakPnL * (1 - 0.35))
```

A current P&L below the floor is an exit condition. The protection rule cannot increase risk.

## F-106 — Dynamic risk schedule

Risk is independently determined from confidence, volatility and drawdown:

```text
confidence_factor = clip(confidence, 0, 1)
volatility_factor = 1 / max(volatility_ratio, 1)
drawdown_factor = clip(1 - drawdown_ratio, 0, 1)

risk_multiplier = clip(
    confidence_factor * volatility_factor * drawdown_factor,
    0, 1
)

AuthorizedRisk = BaseRisk * risk_multiplier
```

DynamicMode is intentionally absent from this equation.

## F-107 — Risk per unit

```text
RiskPerUnit = |EntryPrice - StopPrice| * PointValue + EstimatedExecutionCost
```

## F-108 — Position sizing

```text
Units = floor(AuthorizedRisk / RiskPerUnit)
PositionSize = floor(Units / LotSize) * LotSize
```

## F-109 — Option/instrument selection

Candidate score:

```text
0.40 * delta_fit
+ 0.30 * liquidity
+ 0.20 * relative_volume
- 0.07 * spread_penalty
- 0.03 * theta_penalty
```

with target absolute delta 0.55 and all bounded inputs normalized to [0,1]. Highest valid score wins.

## F-110 — Entry trigger

```text
Entry = eligible
        AND mode in {ACTIVE, INTRADAY}
        AND instrument_score >= 0.60
```

## F-111 — Exit trigger

```text
Exit = edge reversal
       OR current_pnl < protection_floor
```

For a long opportunity, edge reversal is `F102 <= -0.10`; for a short opportunity, `F102 >= +0.10`.

## F-112 — Protection parameterization

Given ATR and edge strength:

```text
strength = |F102|
stop_distance   = ATR * (1.50 - 0.50 * strength)
target_distance = ATR * (2.00 + 1.00 * strength)
```

The implementation currently expresses these as long-side price distances; short-side conversion belongs to the execution/instrument adapter.

## F-113 — Re-entry

```text
reenter iff:
    prior position was exited
    AND cooldown elapsed
    AND |new F102| >= 0.60
    AND |new F102| > |prior F102|
```

## F-114 — Multi-position interaction

```text
remaining_budget = max(TotalRiskBudget - ExistingRisk, 0)
correlation_adjusted_budget = remaining_budget * (1 - correlation_penalty)
NewRisk = min(RequestedRisk, correlation_adjusted_budget)
```

`correlation_penalty` is bounded to [0,1].

---

# Research status

```text
F-001..F-008  anchored/implemented
F-101..F-114  reconstructed v0.1.0 / implemented
```

This is a **model version**, not a claim about what the inaccessible historical conversation contained. It must be evaluated through deterministic tests, historical backtest, out-of-sample validation, execution-cost sensitivity, and paper/shadow validation before any live authorization.
