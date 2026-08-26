# Adaptive Edge V2.1 — Canonical Specification Closure

**Version:** 2.1.0
**Status:** SPECIFICATION-COMPLETE / RESEARCH-ONLY
**Market data:** TrueData only
**Trading/execution/positions/square-off:** Zerodha Kite only

## 1. Purpose

This document closes the V2.1 specification dependency chain without claiming empirical validation or production authorization.

## 2. Canonical causal chain

```text
TrueData raw market observations
        |
        v
Canonical market events/state
        |
        v
FeatureSnapshot
        |
        v
Horizon-conditional directional probability
        |
        v
Economic candidate evaluation
        |
        v
Eligibility
        |
        v
Risk authorization
        |
        v
Option selection
        |
        v
OrderIntent
        |
        v
Zerodha Kite order
        |
        v
Kite trade/fill
        |
        v
Kite position/accounting
        |
        v
Future TrueData outcome
        |
        v
Mature label
        |
        v
Walk-forward learning
        |
        v
Future model version
```

## 3. Source authority

```text
Market/research observations = TrueData
Trading operations            = Zerodha Kite
Orders/fills                  = Zerodha Kite
Positions                     = Zerodha Kite
Order-wise charges            = Zerodha Kite charge endpoint
```

TrueData is never replaced by Kite for Adaptive Edge market/research data.

Kite is never used to manufacture historical TrueData observations.

## 4. Predictive target

The V2.1 target family is:

```text
Y_h ∈ {UP, DOWN, NEUTRAL}
```

based on terminal normalized future return of the underlying/reference instrument:

```text
Z(t,h) = Return(t,h) / sigma_t
```

with:

```text
UP       if Z >  theta_h
DOWN     if Z < -theta_h
NEUTRAL  otherwise
```

The equality boundary is therefore deterministic and non-overlapping.

`h`, `theta_h`, and the volatility-estimation state are research quantities, not arbitrary constants.

## 5. Target price convention

The V2.1 research target uses completed TrueData bar closes for deterministic historical reconstruction:

```text
P(t)   = completed reference-bar close at the decision boundary
P(t+h) = completed reference-bar close at the horizon boundary
```

The bar interval is a versioned research configuration.

## 6. Opportunity definition

The opportunity population is generated from valid decision-time market state and required feature availability only.

Prediction and future outcome cannot create the historical opportunity population.

Economic eligibility remains a downstream stage.

## 7. Prediction

Primary baseline:

```text
multinomial logistic regression
```

with canonical softmax probability and L2-regularized cross-entropy.

Coefficients and regularization are learned through walk-forward research.

Temperature scaling is the baseline calibration method and is fitted only on validation data.

## 8. Economics

For candidate option `i`:

```text
EV_i
 = Σ_k P(k|X,h) * E[NetOutcome_i | k]
```

and the source-defined target/stop formulation remains available:

```text
EV(s,m)
 = P_target * E[Gain]
 - P_stop * E[Loss]
 - Costs
```

Candidate selection:

```text
i* = argmax ConservativeEV_i
```

with `ConservativeEV` defined as the validated lower-confidence bound of expected value.

## 9. Execution costs

Cost components are explicitly separated:

```text
spread
slippage
brokerage
exchange charges
statutory taxes
latency
market impact if explicitly modeled
```

Realized charge truth comes from Kite's order-wise charge interface/accounting records.

Expected cost is estimated pre-trade and cannot use future realized cost.

## 10. Risk

For long option buying:

```text
RiskPerUnit = max(0, EntryPrice - InitialStopPrice)

GrossRisk = RiskPerUnit * ContractMultiplier * Quantity

Quantity = floor(MaxRisk / EffectiveRiskPerContract)
```

The exact stop policy and MaxRisk values are learned/configured and require validation.

Risk authorization is explicit state and cannot be inferred from prediction or P&L.

## 11. Execution

```text
OrderIntent
 -> Kite submission
 -> Kite acknowledgement/status
 -> Kite trades
 -> Position
```

A successful order placement does not prove execution. Kite's order/trade interfaces are authoritative for execution state.

Square-off is an opposite Kite order using the appropriate product/instrument semantics.

## 12. Position

Position quantity is derived from confirmed Kite trades and reconciled against Kite's authoritative position API.

Partial fills produce partial positions.

No order intent is treated as a position.

## 13. Protection

Position protection is versioned and consists of:

```text
initial stop
target
horizon expiry
session exit
forced risk exit
```

Numerical distances are research parameters.

Protection may reduce risk but cannot silently expand authorized risk.

## 14. Accounting

The accounting chain is:

```text
Kite trade
 -> fill ledger
 -> position effect
 -> charges
 -> realized economic result
```

All source events are immutable and provenance-preserving.

## 15. Learning

A row is eligible only after:

```text
feature availability <= decision time
label maturity <= training cutoff
```

Training, validation and holdout are chronologically separated.

Overlapping labels are not assumed independent.

## 16. What is frozen

```text
TrueData market-data authority
Kite execution/accounting authority
causal dependency direction
opportunity/outcome/label separation
normalized-return directional target family
three-state label space
completed-bar target convention
multinomial logistic baseline
validation-only temperature calibration
EV/ConservativeEV architecture
risk-from-entry-to-stop architecture
option candidate causality
Kite order/fill/position separation
Kite charge provenance
position reconciliation
label maturity
walk-forward governance
holdout protection
append-only provenance
fail-closed behavior
```

## 17. What is learned

```text
feature subset
bar interval if treated as research resolution
lookback windows
volatility estimator parameters
horizon
movement threshold
model coefficients
L2 coefficient
calibration temperature
economic scenario distributions
slippage
latency cost
candidate filters
expiry/strike policy
stop/target parameters
MaxRisk
portfolio risk budget
```

Every learned quantity requires a declared research-selection family and out-of-sample validation.

## 18. External configuration

```text
TrueData entitlement
TrueData endpoint availability
TrueData timestamp semantics
Kite instrument master
Kite account permissions
Kite effective charge schedules
exchange contract metadata
session/holiday calendar
statutory charges
```

These are not strategy mathematics.

## 19. Production blockers

The following are not specification gaps; they are empirical/operational gates:

```text
actual TrueData entitlement verification
actual historical dataset acquisition
actual Kite account/execution verification
walk-forward parameter estimation
holdout evaluation
execution-cost sensitivity
risk-capacity validation
operational recovery testing
promotion approval
```

No production numerical parameter is authorized until these gates pass.

## 20. Impossible-state invariants

```text
future data -> past decision                 FORBIDDEN
Kite data -> pre-decision market feature    FORBIDDEN
TrueData quote -> proof of Kite fill        FORBIDDEN
order intent -> position                    FORBIDDEN
partial fill -> full position               FORBIDDEN
realized cost -> contemporaneous EV         FORBIDDEN
immature label -> training                   FORBIDDEN
holdout -> parameter selection              FORBIDDEN
risk authorization -> risk expansion        FORBIDDEN
missing data -> fabricated neutral          FORBIDDEN
future option -> historical candidate       FORBIDDEN
```

## 21. Final readiness state

```text
SPECIFICATION = COMPLETE
IMPLEMENTATION = PARTIAL / EXISTING BOUNDARIES
RESEARCH PARAMETERS = NOT YET VALIDATED
EMPIRICAL EVIDENCE = REQUIRED
PROMOTION = NOT APPROVED
LIVE EXECUTION = BLOCKED
```

This is the correct state until real TrueData research data and actual Kite execution evidence have been processed through the declared validation protocol.
