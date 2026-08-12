# Adaptive Edge V2.1 — A36 Position Lifecycle, Protection and Square-off Contract

**Artifact:** A36
**Version:** 2.1.0
**Status:** PROPOSED-RESEARCH-CONTRACT
**Execution authority:** Zerodha Kite only
**Market/research authority:** TrueData only

## 1. Purpose

Define the lifecycle of a confirmed option position and the conditions under which it is protected or squared off through Zerodha Kite.

## 2. Position creation

A position exists only after a confirmed Kite fill.

```text
Decision
 -> Authorization
 -> OrderIntent
 -> Kite Order
 -> Confirmed Trade/Fill
 -> Position
```

Order submission alone never creates position state.

## 3. Long-option position

V2.1 is directional option buying.

Therefore the initial position is:

```text
quantity > 0
side = LONG
```

The position's economic entry price is the quantity-weighted confirmed Kite fill price.

## 4. Position state

```text
FLAT
 -> ENTRY_PENDING
 -> PARTIALLY_OPEN
 -> OPEN
 -> EXIT_PENDING
 -> PARTIALLY_CLOSED
 -> FLAT
```

Terminal abnormal states:

```text
RECONCILIATION_REQUIRED
BROKER_STATE_UNKNOWN
```

## 5. Initial protection

Every authorized live position must have an initial protection policy before execution is considered fully armed.

The policy produces:

```text
InitialStopPrice
TargetPrice
HorizonExpiry
ProtectionPolicyVersion
```

The numerical stop/target distances are learned/validated research parameters.

## 6. Exit competition

The position exits at the first valid terminal exit condition observed under the authoritative execution/market-state rules:

```text
PROTECTIVE_STOP
TARGET
HORIZON_EXPIRY
SESSION_CLOSE
FORCED_RISK_EXIT
```

The exact priority for simultaneous conditions is deterministic and versioned.

For historical research, the path and execution model must distinguish which condition was observable first.

## 7. Market-data source for protection

TrueData provides the market observation used to evaluate whether a protection condition has become eligible.

Kite provides the actual order/fill state.

```text
TrueData trigger observation
        |
        v
Protection decision
        |
        v
Kite square-off order
        |
        v
Kite fill
```

A TrueData price does not itself close the position.

## 8. Square-off

All actual square-off operations are Zerodha Kite order operations.

A square-off intent contains:

```text
position_id
source_authorization_id
exit_reason
quantity
instrument_id
order_policy_version
decision_time
```

The resulting Kite order/fill is reconciled back to the position.

## 9. Partial exits

If only `q` of `Q` is filled:

```text
remaining_position = Q - q
```

The remaining position retains its lifecycle state and protection requirements.

No assumption of complete square-off is permitted.

## 10. Protection modification

A protection change creates a new versioned protection instruction.

It cannot mutate historical protection state.

A protection modification cannot increase authorized risk beyond the existing authorization without a new authorization event.

## 11. No risk expansion

```text
NewEffectiveRisk <= ExistingAuthorizedRisk
```

unless a new explicit risk authorization is created and independently validated.

A trailing stop may reduce risk; it may not silently move the protective boundary in a direction that expands authorized loss.

## 12. Session end

A position that cannot legally remain open beyond the strategy's configured trading session must enter an end-of-session exit workflow.

The exact session calendar is an external instrument/exchange dependency.

## 13. Broker failure

If Kite becomes unavailable while a position is open:

```text
BROKER_STATE_UNKNOWN
```

must be entered if authoritative position state cannot be confirmed.

The system must not fabricate a flat position.

Recovery is handled by reconciliation/recovery artifacts.

## 14. TrueData failure

If TrueData becomes unavailable while a position is open, protection evaluation may become unavailable.

The system must transition to the explicitly configured degraded-safety policy; it must not pretend the last observation is current without a validated freshness rule.

## 15. Attack

### Stop hindsight

Stop parameters are frozen for a decision before future path information is observed.

### Target hindsight

Target parameters cannot be selected after observing the future path.

### False square-off

A square-off order is not a closed position until confirmed Kite fills establish the reduction.

### Partial-fill error

Protection and remaining quantity must be based on actual confirmed fills.

### Risk expansion

Protection modifications cannot silently increase loss capacity.

### Broker-state divergence

Strategy state and Kite position are reconciled; one cannot overwrite the other without evidence.

## 16. Frozen

```text
position-from-confirmed-fills
Kite-only actual square-off
explicit protection state
partial-fill handling
no risk expansion
reconciliation-required abnormal states
```

## 17. Learned/configurable

```text
initial stop parameters
target parameters
trailing/profit-protection policy
horizon exit policy
session exit policy
protection update cadence
```

These require walk-forward validation and execution-cost sensitivity analysis.

## 18. External dependencies

```text
Kite order/fill semantics
TrueData freshness semantics
exchange session calendar
instrument contract lifecycle
Kite-supported protective mechanism
```

## ARCHITECTURE STATUS

**FROZEN:** position lifecycle; confirmed-fill requirement; Kite square-off authority; explicit protection state; no risk expansion; partial-fill semantics; fail-closed reconciliation.

**LEARNED/VALIDATED:** stop/target/trailing parameters and update policies.

**UNKNOWN:** exact numerical protection policy and exchange/session-specific boundaries.

**BLOCKERS:** live protection requires the Kite order mechanism and TrueData freshness/session contracts to be verified for the selected instrument.

**NEXT ARTIFACT:** A37 — Accounting, P&L and Risk Reconciliation Contract.
