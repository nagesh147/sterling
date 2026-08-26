# A212 — F-106 Option Selection Canonical Recovery

**Status:** `[SOURCE-RECOVERED / RESEARCH IMPLEMENTATION]`
**Formula:** F-106 — Candidate option economic selection
**Source:** Adaptive Order-Flow Options Scalping and Intraday Strategy — Master Mathematical Specification v1.0
**Source commit:** `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`

## 1. Canonical role

F-106 selects the executable option after the underlying directional probability state and opportunity/economic gates have produced candidate CE/PE instruments.

The recovered source defines candidate evaluation using:

```text
ExpectedGrossEV_i
ExecutionCost_i
ExpectedNetEV_i
Risk_i
Liquidity_i
Slippage_i
Confidence_i
```

and selects:

```text
O* = argmax ExpectedNetEV_i
```

subject to liquidity, slippage, risk, and data-quality constraints.

Therefore F-106 is **not** a fixed ATM selector.

## 2. Directional boundary

The option is an execution instrument for an already-established underlying direction.

```text
BUY_CE -> CE candidates
BUY_PE -> PE candidates
NO_TRADE -> no option selection
```

F-106 must not independently manufacture a directional signal.

## 3. Candidate economics

For each candidate `O_i`, the selection state must expose separately:

```text
ExpectedGrossEV_i
ExecutionCost_i
ExpectedNetEV_i
Risk_i
Liquidity_i
ExpectedSlippage_i
Confidence_i
DataQuality_i
```

Execution cost must include available components:

```text
SpreadCost
Slippage
Brokerage
ExchangeCharges
Taxes
LatencyCost
```

Missing cost information cannot silently become zero.

## 4. Eligibility constraints

A candidate is selectable only if:

```text
Liquidity_i >= required level
ExpectedSlippage_i <= allowable level
Risk_i <= authorized risk budget
DataQuality_i >= required level
```

The thresholds are calibration/authorization parameters, not invented constants in the F-106 implementation.

## 5. Selection objective

Among candidates that satisfy all mandatory constraints:

```text
O* = argmax ExpectedNetEV_i
```

If no candidate satisfies the constraints:

```text
NO_INSTRUMENT
```

The result must be deterministic for identical candidate states.

## 6. Moneyness

ATM/ITM/OTM are candidate descriptors, not a hard-coded preference.

A candidate may be selected only because its validated economics satisfy the full constraint set. A fixed rule such as `always ATM` is not F-106.

## 7. Data quality and causality

All candidate values must be available by the decision timestamp.

The selection layer must reject:

```text
future quote
stale quote beyond policy
missing bid/ask when required
non-finite economics
negative liquidity
negative risk
```

Historical option outcomes may be used for model training only after the original candidate decision point has been frozen.

## 8. Position sizing boundary

F-106 does not determine final quantity. It supplies the selected instrument and its instrument-level risk/economic state to the risk authorization stage.

The downstream quantity rule remains:

```text
Q = floor(MaxRisk / EffectiveRiskPerUnit)
```

## 9. Prohibited shortcuts

```text
always ATM
nearest strike only
highest premium
highest raw EV ignoring costs
highest liquidity ignoring economics
lowest spread ignoring risk
future option quote
LTP == executable price
missing slippage -> 0
missing data quality -> pass
```

## 10. Resolution

```text
Source definition:          RECOVERED
Candidate inputs:           RECOVERED
Selection objective:        RECOVERED
Constraint families:        RECOVERED
Production thresholds:      UNFROZEN
Calibration:                REQUIRED
Production implementation:  NOT AUTHORIZED
```

## 11. Next step

Implement F-106 as a deterministic candidate selector that accepts fully formed candidate economics and returns either one selected instrument or `NO_INSTRUMENT`. It must not hide cost/risk/liquidity calculations inside the selector.
