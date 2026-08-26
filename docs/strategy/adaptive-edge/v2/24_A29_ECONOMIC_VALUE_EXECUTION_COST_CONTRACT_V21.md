# Adaptive Edge V2.1 — A29 Economic Value, Execution Cost and Conservative Decision Contract

**Artifact:** A29
**Version:** 2.1.0
**Status:** PROPOSED-RESEARCH-CONTRACT
**Market/research source:** TrueData
**Execution source:** Zerodha Kite

## 1. Purpose

Convert a calibrated directional probability into an economic comparison of executable option candidates without conflating market observations with broker fills.

## 2. Candidate instrument boundary

The underlying/reference instrument supplies the primary directional state.

The execution instrument is a candidate option contract observable from TrueData at decision time and executable through Zerodha Kite.

```text
TrueData underlying
      |
      v
prediction
      |
      v
option candidate set
      |
      v
expected net value
      |
      v
Kite execution intent
```

No future option contract may be selected because it later produced a superior outcome.

## 3. Candidate set

At decision time `t_d`, candidate options must be generated only from information available at `t_d`:

```text
underlying
expiry
strike
option_type
instrument_id
quote availability
liquidity state
contract validity
```

The candidate set is deterministic for the same source state, strategy version, instrument policy version, and decision time.

## 4. Directional mapping

```text
P(UP)   -> CE candidates
P(DOWN) -> PE candidates
```

The strategy may reject all candidates if the directional edge is insufficient.

No simultaneous CE/PE requirement is introduced.

## 5. Economic scenarios

For candidate option `i` and directional state `k`:

```text
Gain_i,k
Loss_i,k
Cost_i
```

must be expressed in the same economic unit.

The scenario values are not invented from a generic points multiplier. They must be derived from the versioned instrument/contract model and historical TrueData outcome population.

## 6. Expected value

For candidate `i`:

```text
EV_i
 = Σ_k P(k | X_t,h) * E[NetOutcome_i | k, X_t]
```

The source-supported target/stop formulation is retained where a target/stop policy exists:

```text
EV(s,m)
 = P_target * E[Gain]
 - P_stop * E[Loss]
 - Costs
```

The implementation must not double-count costs.

## 7. Execution cost

Expected execution cost is separated into:

```text
SpreadCost
Slippage
Brokerage
ExchangeCharges
Taxes
LatencyCost
MarketImpact (if explicitly modelled)
```

The source decomposition is architectural. Numerical distributions are versioned research state.

### Brokerage and statutory costs

For live account economics, the cost schedule must be sourced from Zerodha's current published charges and the applicable statutory/exchange schedules, versioned by effective date. The current published Zerodha schedule states flat ₹20 brokerage per executed F&O option order for resident individual accounts, with exceptions and statutory charges varying by product/condition. These values are provider configuration, not Adaptive Edge mathematical constants.

### Realized costs

Realized cost is reconstructed from actual Kite execution/accounting records and must not be fed backward into the pre-trade decision that generated the order.

## 8. Expected versus realized

```text
ExpectedExecutionCost
    !=
RealizedExecutionCost
```

The former is available at decision time.

The latter exists only after execution/accounting events mature.

## 9. Conservative value

The decision layer consumes:

```text
ConservativeEV_i
    = LowerConfidenceBound(EV_i)
```

The confidence procedure and estimator are learned/validated research components.

Strict rule:

```text
ConservativeEV_i <= 0
    -> candidate rejected
```

## 10. Candidate selection

```text
i* = argmax_i ConservativeEV_i
```

subject to:

```text
DataOK
LiquidityOK
SlippageOK
RiskOK
ContractValid
ExecutionSupported
```

Ties resolve deterministically by the versioned candidate ordering policy; no future result is used for tie-breaking.

## 11. No-trade state

No trade is produced when:

```text
candidate set empty
OR
all candidates fail constraints
OR
max ConservativeEV <= 0
OR
risk authorization fails
OR
required execution semantics are unavailable
```

## 12. Cost-data boundary

Pre-trade cost estimation may use:

```text
current TrueData quote state
historical mature Kite execution observations
versioned Zerodha fee schedule
validated slippage model
```

It may not use:

```text
future fill
future realized cost
future position
future P&L
```

## 13. Slippage model

Slippage is a research quantity.

It may be estimated from prior Kite fills relative to the contemporaneous TrueData reference state, with explicit timestamp alignment and instrument identity.

The model must not assume zero slippage.

## 14. Latency cost

Latency cost is the economic effect of the interval between decision and actual execution.

It is learned/estimated from prior observations and cannot be known exactly before the order is executed.

## 15. Accounting identity

```text
NetEconomicResult
 = GrossEconomicResult
 - ExplicitlyDefinedCosts
```

Each cost component must have provenance and a versioned policy.

## 16. Dimensional analysis

Before arithmetic:

```text
all monetary quantities -> same currency
all option price quantities -> correct contract economic unit
all probability-weighted outcomes -> same payoff basis
```

Contract multiplier and currency conversion are explicit dependencies, never implicit constants.

## 17. Attack

### Double-counting

A cost already embedded in a provider-reported realized figure must not be subtracted again.

### Future-fill leakage

Realized slippage cannot influence contemporaneous EV estimation.

### Option hindsight

Candidate selection uses only the option universe visible at `t_d`.

### Model selection leakage

The best option-selection model cannot be selected using final holdout performance repeatedly.

### Unit mismatch

Premium points, currency, contract notional, and percentage return cannot be mixed without explicit conversion.

### Stale option chain

A stale quote cannot be treated as a contemporaneous executable reference.

## ARCHITECTURE STATUS

**FROZEN:** underlying-to-option separation; candidate-set causality; expected-versus-realized cost separation; EV/ConservativeEV relationships; argmax selection; fail-closed no-trade state; TrueData/Kite source separation.

**LEARNED/VALIDATED:** scenario distributions; slippage; latency cost; confidence estimator; candidate filters; economic thresholds.

**EXTERNAL CONFIGURATION:** Zerodha fee/statutory schedules by effective date; instrument contract metadata; exchange charges.

**UNKNOWN:** exact option candidate generation policy; exact risk constraint; contract multiplier for each instrument; final cost-estimation method.

**BLOCKERS:** A32 risk semantics and A34 candidate-input semantics remain upstream dependencies.

**NEXT ARTIFACT:** A32 — Effective Risk Definition and Risk Authorization Contract.
