# Adaptive Edge V2.1 — A32 Effective Risk and Risk Authorization Contract

**Artifact:** A32
**Version:** 2.1.0
**Status:** PROPOSED-RESEARCH-CONTRACT

## 1. Purpose

Define the quantity of economic loss that a proposed option position consumes from an explicit risk budget.

## 2. Risk unit

For a long option position:

```text
RiskPerUnit
    = max(0, EntryPrice - InitialStopPrice)
```

The source-defined relationship is retained.

For a contract with economic multiplier `M`:

```text
GrossRiskPerContract
    = RiskPerUnit * M
```

If entry/exit costs are explicitly attributable to the risk boundary:

```text
EffectiveRiskPerContract
    = GrossRiskPerContract
      + RiskRelevantEntryCost
      + RiskRelevantExitCost
```

Costs must not be double-counted between risk and P&L.

## 3. Position sizing

For maximum authorized loss budget `MaxRisk`:

```text
Q
    = floor(MaxRisk / EffectiveRiskPerContract)
```

subject to:

```text
Q >= 0
Q <= instrument_quantity_limit
Q <= account/exchange quantity limit
```

If `EffectiveRiskPerContract <= 0` or undefined:

```text
NO_AUTHORIZATION
```

## 4. Risk budget

`MaxRisk` is a strategy configuration/research parameter, not a hard-coded source constant.

Its selection must be validated through historical drawdown, loss-tail, capacity, and multi-position analysis.

## 5. Initial stop

`InitialStopPrice` is supplied by the versioned protection policy.

A32 does not choose the stop formula.

Therefore:

```text
A32 defines how stop distance becomes risk.
A36 defines how the stop itself is constructed.
```

## 6. Effective risk

The canonical risk object contains:

```text
risk_id
decision_id
instrument_id
entry_reference_price
initial_stop_price
risk_per_unit
contract_multiplier
risk_relevant_cost
 effective_risk_per_contract
max_risk_budget
quantity_limit
computed_quantity
risk_policy_version
instrument_policy_version
```

## 7. Risk authorization

Authorization is a state, not a number.

```text
RISK_ASSESSED
    -> AUTHORIZED
    -> CONSUMED
    -> RELEASED
```

Forbidden:

```text
prediction -> authorization
P&L -> retroactive authorization
fill -> increase authorized risk
```

## 8. Reservation invariant

At authorization time:

```text
ReservedRisk <= MaxRiskBudget
```

Across concurrent positions:

```text
Σ ActiveReservedRisk <= GlobalRiskBudget
```

The portfolio/global budget policy is versioned separately.

## 9. Fill interaction

A fill does not create a new risk authorization.

It consumes an existing authorization subject to the authorized quantity.

If the confirmed fill exceeds the authorized quantity:

```text
RISK_RECONCILIATION_FAILURE
```

and the system must not silently expand the authorization.

## 10. Partial fills

For fill quantity `q`:

```text
ConsumedRisk(q)
    = EffectiveRiskPerContract * q
```

Residual authorization remains:

```text
RemainingQuantity
    = AuthorizedQuantity - ConfirmedFilledQuantity
```

## 11. Rejection/cancellation

If an order is rejected or cancelled before fill:

```text
reserved risk -> released
```

subject to the authoritative execution/reconciliation event sequence.

## 12. Risk reconciliation

Compare:

```text
AuthorizedRisk
vs
ActualPositionRisk
```

Any unexplained excess is a hard reconciliation failure.

## 13. Failure conditions

Authorization fails closed when:

```text
initial stop undefined
entry reference undefined
contract multiplier undefined
risk budget undefined
risk calculation non-finite
quantity <= 0
quantity exceeds hard instrument/account limit
risk reservation exceeds available budget
instrument contract invalid
```

## 14. Learned/configurable quantities

```text
MaxRisk
stop policy parameters
contract-specific risk model parameters
cost-risk allocation
portfolio risk budget
concurrency limits
```

All require declared training/validation or operational-policy provenance.

## 15. Frozen quantities

```text
risk is derived from entry-to-stop loss
risk is denominated in economic units
quantity is bounded by authorized risk
authorization is explicit state
fills consume but cannot expand authorization
reconciliation compares authorized and actual risk
```

## 16. Attack

### Zero-risk illusion

A stop at entry is not automatically a valid zero-risk trade; costs and gap/slippage risk must be considered.

### Stop hindsight

The stop cannot be chosen after observing the future path.

### Risk leakage

Future realized loss cannot be used to tune the stop for the same historical decision without an outer validation boundary.

### Multiplier mismatch

Option quantity and premium points cannot be treated as the same economic unit.

### Partial-fill error

A partial fill cannot consume the risk of the entire requested quantity.

### Concurrent-position error

Per-trade limits do not prove portfolio-level risk is within budget.

## ARCHITECTURE STATUS

**FROZEN:** risk unit relationship; explicit authorization; risk reservation; quantity bound; fill consumption; reconciliation; fail-closed semantics.

**LEARNED/VALIDATED:** MaxRisk; stop parameters; cost-risk allocation; portfolio risk budget; concurrency policy.

**EXTERNAL:** contract multiplier and exchange/account quantity constraints.

**UNKNOWN:** exact stop construction; exact account risk budget; exact portfolio interaction policy.

**BLOCKERS:** A36 protection and instrument contract must supply the stop and multiplier semantics before live sizing is authorized.

**NEXT ARTIFACT:** A34 — Option Candidate Generation and Contract Selection.
