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

---

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

### Conditional normalization — §19

```text
Percentile_t
    = F(x_t | Context_t, Data<=t)
```

The historical distribution must be causally available at decision time.

### Directional probability — §21

```text
P_up(h | X_t)
P_down(h | X_t)
P_neutral(h | X_t)

NormalizedReturn(t,h)
    = Return(t,h) / σ_t
```

The movement threshold is learned and validated.

### Multinomial logistic baseline — §22

```text
P(Y=k|X)
    = exp(β_k·X) / Σ_j exp(β_j·X)

Loss
    = CrossEntropy + λ||β||²
```

`β` and `λ` are learned through walk-forward validation.

### Empirical similarity — §23

```text
Z_i = (X_i - μ_i) / σ_i

d(X_t,X_j)
    = sqrt(Σ w_i(Z_i,t - Z_i,j)²)

w_j
    = exp(-d_j² / τ)
```

Minimum effective sample size is mandatory.

### Bayesian state — §24

```text
Beta(α, β)

α_t = ρ α_(t-1) + Successes_t
β_t = ρ β_(t-1) + Failures_t
```

`ρ` is learned and validated.

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

The actual specification also permits explicitly modeled market impact.

### Option selection — §32

```text
O* = argmax ExpectedNetEV_i
```

subject to validated liquidity, slippage, risk and data-quality constraints.

The option is an execution instrument; the underlying state supplies primary direction.

### Target/stop competition — §33

```text
EV(s,m)
 = P_target × E[Gain]
 - P_stop × E[Loss]
 - Costs

(s*,m*)
 = argmax ConservativeEV(s,m)
```

### Conservative expected value — §34

```text
EV_conservative
    = LowerConfidenceBound(EV)

EV_conservative <= 0
    -> NO_TRADE
```

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

### Initial risk and sizing — §36

```text
RiskPerUnit
    = EntryPrice - InitialStop

GrossRisk
    = RiskPerUnit × Q

Q
    = floor(MaxRisk / EffectiveRiskPerUnit)
```

The production implementation must additionally enforce lot, capital, position and execution constraints.

### Continuation value — §39

```text
ContinuationValue_t
    = ExpectedFutureProfit_t
    - ExpectedFutureRisk_t
    - ExpectedFutureCost_t
```

### Profit protection — §40

```text
Giveback_t
    = PeakProfit_t - CurrentProfit_t

AllowedGiveback_t
    = Q_q(Giveback | CurrentState, ProfitState)

ProfitFloor_t
    = PeakPrice_t - AllowedGiveback_t
```

`q` is learned through walk-forward validation.

### Monotonic stop — §41

```text
CandidateStop_t
    = max(OriginalRiskBoundary,
          ProfitFloor_t,
          DynamicRiskBoundary_t)

Stop_t
    = max(Stop_(t-1), CandidateStop_t)
```

Therefore the protective stop can tighten but cannot loosen.

### No risk expansion — §42

```text
MaximumAcceptedRisk_(t+1)
    <= MaximumAcceptedRisk_t
```

### Mode transition — §43

```text
TradeMode_t
    = f(ExpectedHorizonDistribution_t,
        Regime_t,
        ContinuationValue_t)
```

Elapsed time alone does not determine mode.

### Continuation exit — §46

```text
ConservativeContinuationValue <= 0
    -> EXIT
```

### Walk-forward learning — §§50–54

```text
TRAIN
→ FREEZE
→ VALIDATE
→ TEST
→ RECORD
→ ADVANCE
```

No test-period information may influence normalization, coefficients, calibration, thresholds or parameter selection before the test completes.

### Canonical trade objective — §66

```text
NetEV_i
    = E[Profit_i]
    - E[Loss_i]
    - E[ExecutionCost_i]

EVPerRisk_i
    = ConservativeEV_i / EffectiveRisk_i
```

Eligibility requires the conservative estimate to be positive.

---

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
```

These belong to the walk-forward learning and validation system.

## Status

```text
Master Specification     SOURCE OF TRUTH
Canonical operators      IMPLEMENTED
Economic relationships   IMPLEMENTED
Risk relationships       IMPLEMENTED
Protection relationships IMPLEMENTED
Learned parameters       NOT INVENTED
Provisional F-101..114   DEPRECATED
```
