# Adaptive Edge V2.1 — A34 Option Candidate Generation and Selection Contract

**Artifact:** A34
**Version:** 2.1.0
**Status:** PROPOSED-RESEARCH-CONTRACT
**Market-data authority:** TrueData
**Execution authority:** Zerodha Kite

## 1. Purpose

Define how the strategy transforms an underlying directional prediction into a causally valid set of option execution candidates.

## 2. Separation

```text
Underlying state
    -> directional probability
    -> option candidate set
    -> economic evaluation
    -> risk authorization
    -> Kite order intent
```

The option is an execution instrument. It is not the primary prediction target.

## 3. Candidate universe

At decision time, obtain the option universe from the authoritative TrueData option-chain/symbol source.

Every candidate must have:

```text
instrument_id
underlying_id
expiry
strike
option_type
LTP
bid
ask
bid_size
ask_size
volume
OI
source_timestamp
availability_timestamp
```

No future chain state is permitted.

## 4. Directional filter

```text
UP   -> CE candidates
DOWN -> PE candidates
NEUTRAL -> no directional option candidate
```

The directional state comes from the calibrated prediction layer, not from option hindsight.

## 5. Contract validity

A candidate is valid only if:

```text
contract exists at decision_time
TrueData source observation is valid
expiry is valid
option type matches direction
required quote fields are available
instrument mapping to Kite is established
```

## 6. Expiry policy

The expiry-selection policy is a versioned strategy configuration.

It may consider only information available at decision time:

```text
expiry date
remaining session/time
liquidity
quote quality
contract lifecycle
```

The exact preferred expiry is not hard-coded here.

## 7. Strike policy

Strike selection is a versioned research configuration.

The candidate generator may consider:

```text
moneyness
premium
spread
liquidity
OI
execution cost
risk capacity
```

It may not select the strike using its future realized return.

## 8. Liquidity filter

The candidate must satisfy the versioned liquidity policy.

Potential inputs:

```text
bid/ask presence
spread
spread percentage
bid size
ask size
volume
OI
```

No numerical threshold is frozen until validated.

## 9. Economic selection

After candidate construction:

```text
i* = argmax ConservativeEV_i
```

subject to risk, liquidity, data-quality and execution constraints.

This is the source-defined option-selection operator.

## 10. Deterministic ordering

If multiple candidates have identical evaluated value, use a deterministic versioned tie-break sequence, for example by canonical instrument identity.

Future performance is never a tie-breaker.

## 11. Underlying/option relationship

The prediction target remains the underlying/reference instrument.

The option candidate converts the predicted directional state into a tradable instrument.

Therefore:

```text
prediction target != option selection target
```

## 12. Kite mapping

Every selected TrueData instrument must map to a valid Kite instrument identity before execution authorization.

If mapping is missing or ambiguous:

```text
NO_EXECUTION
```

No symbol-name guessing is permitted.

## 13. Attack

### Hindsight strike selection

Forbidden: choose the strike that later maximized P&L.

### Hindsight expiry selection

Forbidden: choose the expiry that later produced the best return.

### Survivorship bias

Historical candidate generation must use contracts actually available at the historical decision time.

### Stale chain

A stale option chain cannot establish current candidate liquidity or price.

### Quote-to-fill confusion

TrueData bid/ask is a reference observation, not evidence of a Kite fill.

### Contract mismatch

A TrueData option identifier and Kite tradingsymbol/instrument token must be explicitly reconciled.

## 14. Frozen

```text
TrueData option chain = candidate-source authority
Underlying prediction = directional authority
Kite = execution authority
Candidate set is decision-time causal
Option selection is downstream of prediction
Future option performance cannot affect candidate generation
```

## 15. Learned/configurable

```text
expiry policy
strike/moneyness policy
liquidity thresholds
spread thresholds
OI/volume thresholds
candidate count
selection tie-break policy
```

These require research validation.

## 16. External dependencies

```text
TrueData option-chain entitlement
Kite instrument master
exchange contract multiplier
historical expired-option coverage
historical contract lifecycle
```

## ARCHITECTURE STATUS

**FROZEN:** causal candidate generation; TrueData option-chain source; underlying-to-option directional mapping; Kite mapping requirement; argmax economic selection; no-hindsight rule.

**UNRESOLVED:** numerical expiry/strike/liquidity policies; historical expired-option coverage; exact contract multiplier.

**BLOCKERS:** live execution requires valid TrueData-to-Kite instrument mapping and exchange contract metadata.

**NEXT ARTIFACT:** A36 — Position Lifecycle and Protection Contract.
