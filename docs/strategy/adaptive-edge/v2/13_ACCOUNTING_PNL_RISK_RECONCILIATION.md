# Adaptive Edge V2 — Accounting, P&L and Risk-Reconciliation Contract

**Artifact:** A37  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** NONE

## 1. Purpose

A37 defines the accounting boundary between confirmed execution events, position state, cash/economic effects, realized P&L, and risk reconciliation.

It does not invent broker accounting, tax, fee, margin, contract multiplier, or currency-conversion semantics that have not been sourced.

## 2. Canonical causal chain

```text
FillEvents
    |
    +--> PositionState
    |
    +--> Cash/AccountEffects
    |
    +--> ExecutionCosts
    |
    v
Realized / Unrealized Economic State
    |
    v
P&L
    |
    v
RiskReconciliation
```

Accounting is downstream of execution. It cannot modify the historical decision that produced the execution.

## 3. Accounting truth

The canonical accounting record must be reconstructible from immutable source events.

At minimum, the system must retain:

```text
fill identity
instrument identity
side
quantity
fill price
fill timestamp
order/intent reference
execution provider reference
fee/cost references
currency
policy/version provenance
```

Exact provider fields remain UNKNOWN.

## 4. Position accounting

Position quantity must derive from confirmed fills.

A position is not created merely because an order was submitted.

Conceptually:

```text
PositionQuantity(t)
    = net signed filled quantity
      through t
```

The exact sign/netting convention must be defined by the account/execution contract before production implementation.

## 5. Cash/account effect

A fill may produce a cash or account effect.

The exact mapping depends on the instrument and account model.

A37 therefore distinguishes:

```text
FillEvent
CashEffect
PositionEffect
```

rather than assuming one universal formula.

## 6. Gross economic result

A realized gross result is conceptually the economic consequence of entry and exit execution before explicitly defined execution costs and other deductions.

The exact formula is instrument-dependent and remains unresolved until contract semantics are resolved.

No generic equity formula is substituted for an option contract without source definitions.

## 7. Execution costs

Execution costs are separate from gross economic result.

Potential components include only when explicitly defined:

```text
brokerage/commission
exchange charges
fees
slippage
spread-related execution effect
taxes/levies
other documented costs
```

Each component must have:

```text
source
semantic definition
unit
currency
timestamp
applicability
version
```

A cost cannot be silently assumed to be zero because the provider documentation is unavailable.

## 8. Net P&L relationship

The architectural relationship is:

```text
NetEconomicResult
    = GrossEconomicResult
      - ExplicitlyDefinedCosts
```

This is a structural relationship, not a completed numerical P&L formula.

The exact cost set must be defined before production P&L is claimed.

## 9. Expected versus realized economics

These remain separate:

```text
ExpectedNetValue
    !=
RealizedNetValue
```

The former is pre-trade expectation.

The latter is computed from actual post-trade events.

Realized economics must never be fed backward into the original eligibility or risk-authorization decision.

## 10. Unrealized P&L

Unrealized P&L requires a valuation price.

The valuation price must define:

```text
price type
source
observation timestamp
availability timestamp
freshness
valuation policy
```

A37 does not assume `last`, `mid`, bid, ask, or theoretical value as the universal mark.

## 11. Realized P&L timing

Realized P&L becomes final only when the relevant execution/accounting events are complete under the applicable accounting policy.

Partial exits therefore produce partial realized results while leaving residual position state.

## 12. Partial-exit accounting

For a position reduced in multiple fills:

```text
Entry fills
    -> Residual position
    -> Exit fill 1
    -> Exit fill 2
    -> ...
    -> Flat
```

The accounting method for assigning entry cost to each partial exit must be explicitly defined.

Possible accounting methods are not choices at A37; the authoritative strategy/account contract must establish the method.

## 13. Fees and deductions

Fees and deductions must not be double-counted.

If a provider's reported realized P&L already includes a component, the accounting pipeline must not subtract that same component again.

The source-of-truth hierarchy must be defined when provider documentation is available.

## 14. Currency

All economic values must identify currency.

Cross-currency conversion requires:

```text
source currency
target currency
FX rate source
FX observation timestamp
conversion policy
```

No FX rate is invented.

## 15. Contract multiplier

For derivative instruments, quantity and quoted price may not have the same economic unit.

A contract multiplier or equivalent economic conversion is therefore a required dependency where applicable.

Its value and historical validity remain UNKNOWN until authoritative contract metadata is sourced.

## 16. Expiry and settlement

Expiry/settlement economics depend on the instrument contract.

A37 does not assume physical settlement, cash settlement, automatic exercise, or any other behavior.

Those are external contract semantics.

## 17. Risk reconciliation

Risk reconciliation compares the risk that was authorized with the risk actually represented by the position/execution/accounting state.

The architectural relationship is:

```text
RiskAuthorization
        |
        v
AuthorizedRiskLedger
        |
        +-----> RiskConsumption / Reservation
        |
        v
ActualPosition / ExecutionState
        |
        v
RiskReconciliation
```

The exact risk-measure function remains blocked by A32.

## 18. Authorization is not realized loss

The system must not define:

```text
ConsumedRisk = RealizedLoss
```

unless a later authoritative risk policy explicitly defines that relationship.

Loss is an accounting outcome; risk authorization is a pre-trade policy state.

## 19. Risk consumption

A later resolved risk ledger must distinguish at least:

```text
AuthorizedRisk
ReservedRisk
ConsumedRisk
ReleasedRisk
RealizedLoss
```

These terms cannot be treated as synonyms.

Their exact mathematical definitions remain blocked until A32 and the risk-accounting contract are resolved.

## 20. Reconciliation invariant

At a minimum, the ledger must be capable of detecting:

```text
unauthorized exposure
risk reservation exceeding authorization
unaccounted fills
position/account mismatch
missing cost records
duplicate cost records
negative/invalid quantity states
```

The exact numerical reconciliation equations remain unresolved.

## 21. Double-entry-style event integrity

Every economic effect must trace to an immutable source event or an explicitly versioned derived calculation.

A derived P&L record without traceable fill/contract/cost provenance is not production-auditable.

## 22. Idempotency

Accounting event processing must be idempotent.

Reprocessing the same fill event must not duplicate:

```text
position quantity
cash effect
fees
P&L
risk consumption
```

Each source event therefore requires a stable identity.

## 23. Ordering

Fill events and account events must be processed according to their authoritative event timestamps and deterministic tie-breaking rules.

A later event cannot be applied as though it occurred earlier merely because it was received first.

## 24. Corrections

If a provider corrects an execution/accounting event, the system must preserve the original event and record a correction/supersession relationship.

Historical audit records must not be silently overwritten.

## 25. Reconciliation with broker/account state

If provider account state is available, reconciliation should compare canonical internal state with the provider's authoritative state.

The provider semantics and polling/event guarantees are currently UNKNOWN.

A mismatch must produce an explicit reconciliation failure rather than silently mutating strategy state.

## 26. Accounting versus strategy state

Accounting reports what happened.

Strategy state determines what the strategy decided.

Accounting must not retroactively rewrite:

```text
prediction
eligibility
risk authorization
order intent
```

A correction creates an auditable new event/derived state.

## 27. Learning boundary

Realized P&L and outcomes may eventually become training/label inputs only after their maturity conditions are satisfied.

They cannot enter training data as if mature while future execution events are still unknown.

The learning artifact must define label maturity and training cutoffs.

## 28. Adversarial attack — future P&L leakage

Invalid:

```text
future realized P&L
-> revise historical risk authorization
-> replay strategy
```

This changes the historical decision boundary.

Correct approach:

```text
historical authorization remains immutable
future P&L becomes a later outcome event
```

## 29. Adversarial attack — fee double count

Invalid:

```text
provider P&L already includes fee
+
internal fee subtraction
```

The same cost must not be deducted twice.

## 30. Adversarial attack — stale valuation

Invalid:

using a future price or an unavailable mark to calculate an earlier unrealized P&L state.

## 31. Adversarial attack — partial exit

Invalid:

```text
partial exit
-> position closed
-> all remaining risk removed
```

unless canonical filled quantity actually reaches the flat state.

## 32. Adversarial attack — corrected fill

Invalid:

silently replacing the original fill record with a corrected provider value.

The correction must remain auditable.

## 33. Adversarial attack — unauthorized position

If confirmed fills imply exposure but no valid risk authorization exists, reconciliation must flag an unauthorized exposure condition.

It must not manufacture an authorization after the fact.

## 34. Adversarial attack — risk equals loss

Invalid assumption:

```text
RiskConsumed = RealizedLoss
```

without an explicit policy definition.

This is exactly the semantic distinction required before A32 can be resolved.

## 35. Parameter classes

### Frozen architecture

```text
fills are accounting inputs
position derives from fills
expected and realized economics are separate
costs require explicit provenance
currency is explicit
risk authorization is separate from loss
accounting is immutable/auditable
processing is idempotent
corrections are append/audit events
```

### Source-defined configuration

```text
contract multiplier
fee schedule
tax/levy treatment
settlement rules
account netting
provider P&L semantics
currency conversion policy
```

### Learned parameters

No learned accounting parameter is introduced by A37.

### External UNKNOWN

```text
broker/accounting semantics
fee schedule
contract multiplier
settlement semantics
historical account records
provider P&L inclusion rules
FX source
```

## 36. Implementation gate

A37 cannot become production accounting until contract, provider, and risk semantics required for each economic quantity are resolved.

Internal event-ledger interfaces may be implemented only without inventing numerical accounting behavior.

## 37. Completion criterion

A37 becomes `RESOLVED` when every production P&L and reconciliation number can be traced:

```text
source event
 -> canonical event
 -> position/account effect
 -> cost
 -> P&L
 -> risk ledger
 -> reconciliation result
```

with explicit units, currency, timestamps, policy versions, and correction lineage.

## ARCHITECTURE STATUS

**FROZEN:** fill-derived accounting boundary; position truth; expected/realized separation; explicit cost provenance; currency identity; risk/accounting separation; idempotency; correction lineage; reconciliation boundary; no retroactive strategy mutation.

**UNRESOLVED:** exact P&L formula; partial-exit accounting method; contract multiplier; fee/tax semantics; settlement; valuation price; currency conversion; risk consumption equations; provider accounting semantics.

**BLOCKERS:** A32 risk-measure semantics; instrument/accounting contract semantics; provider accounting/fee documentation.

**NEXT ARTIFACT:** A38 — Label Maturity, Outcome Construction and Learning Boundary.
