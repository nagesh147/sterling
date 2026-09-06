# Adaptive Edge — Master Specification Traceability

## Authority

The authoritative strategy source recovered from the conversation artifacts is:

`Adaptive Order-Flow Options Scalping and Intraday Strategy — Master Mathematical Specification — Version 1.0`

It was uploaded into the Sterling workspace during the strategy recovery process. The repository's existing `docs/strategy/adaptive-edge/` files remain implementation/architecture records; this document establishes the recovered Master Specification as the strategy authority.

## Non-negotiable scope

- Kite only.
- Options scalping / intraday strategy.
- Separate engine from SuperTrend and Value Flow Navigator.
- No unrelated market logic.
- No reuse of SuperTrend/Navigator signal semantics as Adaptive Edge mathematics.

## Canonical mathematical chain

```text
Market observations
    -> microstructure / price / volume features
    -> contextual normalization
    -> probabilistic / similarity / Bayesian evidence
    -> expected move / outcome distribution
    -> option payoff
    -> execution cost + slippage + latency + impact
    -> expected net economic value
    -> conservative target/stop evaluation
    -> risk authorization
    -> quantity / contract selection
    -> entry / continuation / exit
    -> execution replay
```

## Recovered equations

### Price / microstructure

```text
Mid_t = (Bid_t + Ask_t) / 2
Spread_t = Ask_t - Bid_t
RelativeSpread_t = Spread_t / Mid_t
Return_t = PriceChange_t / LTP_(t-1)
Velocity_t = PriceChange_t / Delta_t
Acceleration_t = DeltaVelocity_t / Delta_t
```

### Order flow / liquidity

```text
Delta_t = AggressiveBuyVolume_t - AggressiveSellVolume_t
CumDelta_t = CumDelta_(t-1) + Delta_t
DeltaVelocity_t = Delta(Delta_t) / Delta_t
LiquidityImbalance_t = (BidQty_t - AskQty_t) / (BidQty_t + AskQty_t)
```

### Contextual normalization

The model must normalize features conditionally on the information available at the decision time. A global future-aware normalization is prohibited.

```text
Percentile_t = F(x_t | Context_t, Data <= t)
```

### Statistical evidence

The specification permits a parameterized multinomial probability model:

```text
P(Y=k | X) = exp(beta_k . X) / Sum_j exp(beta_j . X)
```

with regularized fitting, plus empirical similarity and Bayesian updating as additional evidence mechanisms where specified by the strategy configuration.

Empirical similarity:

```text
d(X_t, X_j) = sqrt(Sum_i w_i (Z_i,t - Z_i,j)^2)
w_j = exp(-d_j^2 / tau)
```

### Economics

```text
ExpectedNetEV_i = ExpectedGrossEV_i - ExecutionCost_i
```

Execution cost includes, where applicable:

```text
spread + slippage + brokerage + exchange charges + taxes + latency + market impact
```

Candidate selection is economic, not merely predictive:

```text
O* = argmax ExpectedNetEV_i
```

subject to liquidity, slippage, risk, and data-quality constraints.

### Target / stop optimization

```text
EV(s,m) = P_target * E[Gain] - P_stop * E[Loss] - Costs
(s*,m*) = argmax ConservativeEV(s,m)
```

```text
EV_conservative = LowerConfidenceBound(EV)
EV_conservative <= 0 -> NO_TRADE
```

### Risk / sizing

```text
RiskPerUnit = EntryPrice - InitialStop
GrossRisk = RiskPerUnit * Q
Q = floor(MaxRisk / EffectiveRiskPerUnit)
```

The actual contract multiplier, lot size, premium, spread, and execution costs must be represented explicitly for Kite options.

### Continuation / profit protection

```text
ContinuationValue_t = ExpectedFutureProfit_t - ExpectedFutureRisk_t - ExpectedFutureCost_t
Giveback_t = PeakProfit_t - CurrentProfit_t
AllowedGiveback_t = Q_q(Giveback | CurrentState, ProfitState)
ProfitFloor_t = PeakPrice_t - AllowedGiveback_t
```

Protection must be monotone:

```text
Stop_(t+1) >= Stop_t
MaximumAcceptedRisk_(t+1) <= MaximumAcceptedRisk_t
```

## Implementation mapping

| Specification domain | Sterling implementation boundary | Status |
|---|---|---|
| Price/microstructure | `adaptive_edge` canonical math | implemented |
| Causal feature construction | research dataset + feature layer | implemented |
| Contextual normalization | canonical math / feature pipeline | next integration |
| Probability evidence | probability engine | implemented as model family |
| Similarity evidence | canonical math | next integration |
| Bayesian evidence | canonical math | next integration |
| Expected move | economic/edge layer | next integration |
| Option payoff | Kite option layer | next integration |
| Execution cost | economic engine | implemented |
| Conservative EV | economic engine | implemented / needs end-to-end wiring |
| Risk per unit | risk engine | implemented |
| Quantity | sizing boundary | implemented / needs Kite lot integration |
| Target/stop search | protection/economic boundary | next integration |
| Continuation value | protection boundary | implemented |
| Profit floor / giveback | protection boundary | implemented |
| Historical replay | Adaptive Edge replay | implemented |
| Walk-forward fitting | research infrastructure | optional downstream, not strategy core |
| Calibration | research infrastructure | optional downstream |

## Drift correction

The recently added parameter fitting, calibration, and model-selection modules are **research infrastructure**, not the Adaptive Edge strategy itself. They must never become prerequisites that redefine the strategy.

The implementation order is now:

```text
1. canonical features
2. contextual normalization
3. evidence aggregation
4. expected move / outcome distribution
5. option payoff
6. execution economics
7. conservative EV gate
8. target/stop optimization
9. risk authorization + sizing
10. entry / continuation / exit
11. realistic replay
12. only then optional fitting/calibration/walk-forward research
```

## Prohibited substitutions

Do not substitute:

- arbitrary weighted feature scores;
- arbitrary probability thresholds;
- ATR-only target/stop rules;
- SuperTrend signals;
- Navigator fusion scores;
- generic Kelly sizing;
- unrelated derivatives-selector heuristics;
- hard-coded profitability thresholds not present in the Master Specification.

Those may be research experiments, but they are not Adaptive Edge unless explicitly promoted by the source specification and validated.
