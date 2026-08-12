# Adaptive Edge V2.1 — A37 Accounting, P&L and Risk Reconciliation Contract

**Artifact:** A37
**Version:** 2.1.0
**Status:** PROPOSED-RESOLVED-PROVIDER-CONTRACT
**Market/research source:** TrueData
**Execution/accounting source:** Zerodha Kite

## 1. Source authority

```text
Market observation       = TrueData
Order/execution truth    = Kite
Trade/fill truth         = Kite trades
Position truth           = Kite positions
Order-wise charge truth  = Kite virtual contract-note endpoint
```

Kite documents `/trades`, `/orders/:order_id/trades`, `/portfolio/positions`, and `/charges/orders`. The charges endpoint provides order-wise brokerage, STT, stamp duty, exchange transaction charges, SEBI turnover charge and GST.

## 2. Immutable accounting source events

Canonical source events:

```text
KITE_ORDER
KITE_TRADE
KITE_POSITION_SNAPSHOT
KITE_CHARGE
```

Every event retains:

```text
event_id
provider
provider_reference
instrument_id
occurred_at
received_at
currency
payload_fingerprint
source_version
```

## 3. Fill truth

A position mutation is permitted only from confirmed Kite trade/fill events.

Kite documents that one order may produce multiple trades, each representing an individual execution chunk.

Therefore:

```text
Order(Q)
 -> Trade(q1)
 -> Trade(q2)
 -> ...
 -> Position(Q_confirmed)
```

## 4. Position truth

Kite's position API exposes `net` and `day` positions. `net` is the current net position portfolio; `day` represents that day's activity.

The broker position is the operational reconciliation authority.

The internally reconstructed position from fills must reconcile to the authoritative Kite position.

## 5. Contract multiplier

Kite position data explicitly exposes `multiplier`, described as the quantity/lot-size multiplier used for P&L calculation.

Therefore contract multiplier is no longer an UNKNOWN semantic at the broker boundary.

The multiplier used for a historical event must be retained with the event/position version applicable to that instrument.

## 6. Realized P&L

Realized P&L is reconstructed from confirmed entry/exit trades using the versioned position-accounting policy.

The policy must explicitly define entry-cost allocation for partial exits.

The broker's reported P&L may be used as a reconciliation observation, not as an unexplained replacement for the canonical fill-derived ledger.

## 7. Unrealized P&L

Unrealized P&L requires a valuation price and timestamp.

Kite positions expose `last_price`, `value`, `pnl`, `m2m`, and `unrealised` fields. These remain provider-reported observations.

The Adaptive Edge market valuation used in a research decision remains TrueData-derived.

The provider-reported Kite P&L is used for execution/accounting reconciliation.

## 8. Charges

For realized accounting, order-wise charges are sourced from Kite's charges/virtual-contract-note endpoint.

The canonical charge record includes, where returned:

```text
brokerage
STT/CTT
stamp duty
exchange transaction charges
SEBI turnover charge
GST
other documented charges
```

The current Zerodha published resident-individual F&O schedule is treated as external policy documentation, not embedded strategy constants. Account-specific and effective-date-specific charges are resolved from the provider/account contract and order-wise charge response.

## 9. Cost identity

```text
NetEconomicResult
 = GrossEconomicResult
 - ExplicitlyDefinedCharges
 - ExplicitlyDefinedExecutionEffects
```

A component already included in a provider-reported accounting field cannot be deducted a second time.

## 10. Currency

Each accounting event must identify its currency.

Cross-currency conversion is required only when an instrument/account produces values in different currencies and must use a versioned FX source/policy.

No FX conversion is invented for INR-only NFO equity-index option trading.

## 11. Partial exits

Entry allocation method is a versioned accounting policy.

For every partial exit:

```text
confirmed_exit_quantity
allocated_entry_cost
exit_value
direct_charges
realized_gross
realized_net
residual_position
```

must remain reconstructible.

## 12. Corrections

Provider corrections never mutate historical source events in place.

A correction is a new event that references/supersedes the prior event and preserves both payload fingerprints.

## 13. Reconciliation

At each reconciliation point:

```text
InternalConfirmedFills
        ==
KiteConfirmedTrades
```

and:

```text
InternalPosition
        ==
KiteNetPosition
```

within explicitly documented provider quantity/product semantics.

Any unexplained difference creates:

```text
ACCOUNTING_RECONCILIATION_FAILURE
```

## 14. Risk reconciliation

Compare:

```text
AuthorizedRisk
vs
Position-derived-risk
```

using the current instrument multiplier, confirmed quantity, entry/stop policy and explicit costs.

No risk expansion occurs merely because the broker reports a larger position.

## 15. Temporal rule

Accounting facts that occur after decision time cannot be fed backward into:

```text
features
prediction
opportunity existence
pre-trade EV
risk authorization
```

They may affect future state and future learning only after maturity.

## 16. Attack

### Duplicate trade

Same trade ID/payload is idempotent. Same ID with different payload is an integrity failure.

### Partial fill

A single order is not treated as a single fill.

### Charge double-count

Provider-reported charges are not subtracted again from a value already net of those charges.

### Position mismatch

Broker position and internally reconstructed position are reconciled, never silently overwritten.

### Future accounting leakage

Realized costs and P&L cannot influence the historical decision that caused the trade.

### Multiplier mismatch

The instrument multiplier is sourced from the provider/instrument contract, not inferred from quantity.

## 17. Frozen

```text
Kite trade = execution/fill truth
Kite position = broker position truth
Kite order-wise charges = accounting charge source
multiplier = provider instrument/position metadata
fill-derived internal ledger
append-only provenance
reconciliation failure on unexplained divergence
```

## 18. Learned/configurable

```text
entry-cost allocation method
execution slippage model
latency-cost model
research-only expected cost distribution
risk-relevant cost allocation
```

## 19. External dependencies

```text
account-specific fee policy
current effective statutory charges
instrument-specific settlement rules
FX policy if non-INR instruments are introduced
historical availability of Kite account events
```

## ARCHITECTURE STATUS

**FROZEN:** provider boundaries, fill/position/accounting source hierarchy, multiplier provenance, order-wise charge source, partial-fill accounting, reconciliation and causal restrictions.

**UNRESOLVED:** account-specific/effective-date policy details and research estimation parameters.

**BLOCKERS:** none for accounting architecture. Production accounting requires live verification of the authenticated Kite account's applicable charge/position behavior.

**NEXT ARTIFACT:** A38 — Label Maturity and Learning Dataset Contract.
