# Adaptive Edge — Source-Derived Mathematical Registry

## Authority

The authoritative strategy source is:

```text
adaptive-edge/Adaptive Order-Flow Options Scalping and Intraday Strategy.md
Master Mathematical Specification — Version 1.0
```

Source commit:

```text
38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1
```

See `ORIGINAL_SOURCE_MANIFEST.md` and `spec_registry.py` for traceability.

## Important correction

The old F-101..F-114 equations were a provisional reconstruction and contained invented numerical weights and thresholds. They are **not canonical** and are deprecated.

The Master Specification defines a larger mathematical system whose numerical coefficients, calibration parameters, quantiles, thresholds, and execution distributions are learned/validated where explicitly designated. This registry therefore records relationships and section anchors rather than inventing fixed constants.

## Canonical operators

### Price state — Master Specification §7

```text
Mid_t = (Bid_t + Ask_t) / 2
Spread_t = Ask_t - Bid_t
RelativeSpread_t = Spread_t / Mid_t
PriceChange_t = LTP_t - LTP_(t-1)
Return_t = PriceChange_t / LTP_(t-1)
Velocity_t = PriceChange_t / Δt
Acceleration_t = ΔVelocity_t / Δt
```

Implemented in `canonical_math.py`.

### Incremental volume — §8

```text
ΔVolume_t = TTQ_t - TTQ_(t-1)
```

If `ΔVolume_t < 0`, this is a data-integrity/reset event, not negative volume.

### Aggressor classification — §9

```text
TradePrice >= Ask  -> BUY
TradePrice <= Bid  -> SELL
Bid < TradePrice < Ask -> UNKNOWN
```

Unknown volume is never silently assigned to a side.

### Delta — §10

```text
Delta_t = AggressiveBuyVolume_t - AggressiveSellVolume_t
CumDelta_t = CumDelta_(t-1) + Delta_t
DeltaVelocity_t = ΔDelta_t / Δt
DeltaAcceleration_t = ΔDeltaVelocity_t / Δt
```

### Liquidity imbalance — §11

```text
LiquidityImbalance
    = (BidQty - AskQty) / (BidQty + AskQty)
```

only when the denominator is positive.

### Volume intensity — §12

```text
VolumeIntensity_t
    = CurrentVolumeRate_t
      / ExpectedVolumeRate(time_of_day, instrument, regime)
```

The operator is exact; the contextual expected-volume-rate source remains an unresolved strategy input.

### Conditional normalization — §19

```text
Percentile_t
    = F(x_t | Context_t, Data<=t)
```

The historical distribution must be causally available at decision time. The estimator, context construction, and minimum-data policy are not fully specified; therefore the complete normalization component remains BLOCKED.

### Directional probability — §21

```text
P_up(h | X_t)
P_down(h | X_t)
P_neutral(h | X_t)

NormalizedReturn(t,h)
    = Return(t,h) / σ_t
```

The movement threshold is learned and validated. The complete probability pipeline remains PARTIAL until its calibration/estimation procedure is defined.

### Multinomial logistic baseline — §22

```text
P(Y=k|X)
    = exp(β_k·X) / Σ_j exp(β_j·X)

Loss
    = CrossEntropy + λ||β||²
```

`β` and `λ` are learned through walk-forward validation. The mathematical operator is available; the exact fitting/optimization procedure is not source-defined.

### Empirical similarity — §23

```text
Z_i = (X_i - μ_i) / σ_i

d(X_t,X_j)
    = sqrt(Σ w_i(Z_i,t - Z_i,j)²)

w_j
    = exp(-d_j² / τ)
```

Minimum effective sample size is mandatory. The complete similarity-selection procedure remains PARTIAL until that gate is formally defined.

### Bayesian state — §24

```text
Beta(α, β)

α_t = ρ α_(t-1) + Successes_t
β_t = ρ β_(t-1) + Failures_t
```

`ρ` is learned and validated. Initialization and learning procedure remain unresolved.

### Execution cost — §31

```text
Cost_i
 = SpreadCost_i
 + Slippage_i
 + Brokerage_i
 + ExchangeCharges_i
 + Taxes_i
 + LatencyCost_i
```

The actual specification also permits explicitly modeled market impact. The decomposition is exact; provider-specific distributions remain unresolved.

### Option selection — §32

```text
O* = argmax ExpectedNetEV_i
```

subject to validated liquidity, slippage, risk and data-quality constraints.

The option is an execution instrument; the underlying state supplies primary direction. The exact argmax operator is available; complete candidate-input derivation remains PARTIAL.

### Target/stop competition — §33

```text
EV(s,m)
 = P_target × E[Gain]
 - P_stop × E[Loss]
 - Costs

(s*,m*)
 = argmax ConservativeEV(s,m)
```

The argmax operator is exact for supplied candidate estimates.

### Conservative expected value — §34

```text
EV_conservative
    = LowerConfidenceBound(EV)

EV_conservative <= 0
    -> NO_TRADE
```

The strict eligibility predicate is exact; the source does not provide a complete estimator for the lower-confidence-bound inputs.

### Entry gates — §35

```text
BUY_CE = DataOK
         ∧ DirectionalEdgeOK
         ∧ EV_CE > 0
         ∧ ConservativeEV_CE > 0
         ∧ LiquidityOK
         ∧ SlippageOK
         ∧ RiskOK

BUY_PE = analogous gates for PE
```

The Boolean predicate is exact; upstream derivations remain unresolved.

### Initial risk and sizing — §36

The recovered source contains the relationships:

```text
RiskPerUnit
    = EntryPrice - InitialStop

GrossRisk
    = RiskPerUnit × Q

Q
    = floor(MaxRisk / EffectiveRiskPerUnit)
```

However, `RISK.md` and the strategy-specification anchor explicitly record that the strategy-specific F-107/F-108 definitions were not recovered. In particular, the semantics of `EffectiveRiskPerUnit` are not defined sufficiently to authorize production sizing. Therefore these relationships are **NOT strategy-authorized executable formulas** until their complete input semantics, units, boundary conditions, and provenance are recovered. Generic mathematical operators may exist in code, but they must not be treated as the Adaptive Edge sizing implementation.

### Continuation value — §39

```text
ContinuationValue_t
    = ExpectedFutureProfit_t
    - ExpectedFutureRisk_t
    - ExpectedFutureCost_t
```

The arithmetic operator is exact; the estimators supplying its inputs remain unresolved.

### Profit protection — §40

```text
Giveback_t
    = PeakProfit_t - CurrentProfit_t

AllowedGiveback_t
    = Q_q(Giveback | CurrentState, ProfitState)

ProfitFloor_t
    = PeakPrice_t - AllowedGiveback_t
```

`q` is learned through walk-forward validation. Peak/current profit and giveback are exact accounting relationships; the learned quantile estimator remains BLOCKED.

### Monotonic stop — §41

```text
CandidateStop_t
    = max(OriginalRiskBoundary,
          ProfitFloor_t,
          DynamicRiskBoundary_t)

Stop_t
    = max(Stop_(t-1), CandidateStop_t)
```

Therefore the protective stop can tighten but cannot loosen. Upstream boundary definitions remain required.

### No risk expansion — §42

```text
MaximumAcceptedRisk_(t+1)
    <= MaximumAcceptedRisk_t
```

Exact invariant.

### Mode transition — §43

```text
TradeMode_t
    = f(ExpectedHorizonDistribution_t,
        Regime_t,
        ContinuationValue_t)
```

The function itself is not defined sufficiently to implement the strategy mode transition.

### Continuation exit — §46

```text
ConservativeContinuationValue <= 0
    -> EXIT
```

Exact gate; conservative continuation-value estimation remains unresolved.

### Walk-forward learning — §§50–54

```text
TRAIN
→ FREEZE
→ VALIDATE
→ TEST
→ RECORD
→ ADVANCE
```

No test-period information may influence normalization, coefficients, calibration, thresholds or parameter selection before the test completes. Exact fitting/calibration procedures remain unresolved where not explicitly defined.

### Canonical trade objective — §66

```text
NetEV_i
    = E[Profit_i]
    - E[Loss_i]
    - E[ExecutionCost_i]

EVPerRisk_i
    = ConservativeEV_i / EffectiveRisk_i
```

The relationships are exact, but `EffectiveRisk_i` is not semantically defined in the recovered source. Therefore EV-per-risk is not executable until that input is defined.

## Parameter policy

The following must not be hard-coded without evidence:

```text
model coefficients
probability calibration
Bayesian decay
MFE/MAE distributions
profit-floor quantile
continuation threshold
reversal threshold
regime-transition sensitivity
risk allocation
execution/slippage distributions
option-selection parameters
time-of-day effects
EffectiveRisk_i semantics
EffectiveRiskPerUnit semantics
```

These belong to the walk-forward learning and validation system or require recovery of the missing strategy definition.

## Status

```text
Master Specification     SOURCE OF TRUTH
Canonical operators      IMPLEMENTED where independently exact
Economic relationships   PARTIAL where all inputs are not defined
Risk relationships       BLOCKED for strategy authorization until F-107/F-108 are recovered
Protection relationships PARTIAL where learned inputs remain unresolved
Learned parameters       NOT INVENTED
Provisional F-101..114   DEPRECATED
```
