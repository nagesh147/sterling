# A175 — Canonical Economic Valuation, Transaction-Cost & Opportunity Contract

**Status:** CANONICAL  
**Authority:** Economic valuation and opportunity-eligibility contract  
**Scope:** Adaptive Edge  
**Dependencies:** A153–A174

## 1. Purpose

A175 defines the boundary between predictive probability and economic opportunity. It freezes semantic relationships, not arbitrary numerical thresholds.

```text
probability
    -> scenario economics
    -> executable-price semantics
    -> transaction costs
    -> liquidity/execution uncertainty
    -> economic eligibility
    -> risk authorization
```

Probability is not economic value, and economic eligibility is not risk authorization.

## 2. Canonical distinctions

```text
raw_score            != probability
probability          != economics
economics             != risk_authorization
estimated_economics   != realized_economics
observed_price        != executable_price
unknown_cost          != zero_cost
```

## 3. Economic identity

Every consequential economic estimate must preserve, as applicable:

```text
economic_observation_id
decision_id
instrument_identity
side
quantity_reference
entry_reference
exit_reference
probability_reference
horizon
price_semantics_version
cost_model_version
liquidity_reference
configuration_version
causal_cutoff
created_at
```

## 4. Executable price

The system must distinguish:

```text
last_trade
bid
ask
observed_quote
estimated_executable_price
realized_execution_price
```

LTP must never be silently substituted for executable price.

If executable-price semantics are unavailable:

```text
EXECUTABLE_PRICE = UNKNOWN
```

## 5. Transaction costs

Material costs must remain identifiable, including where applicable:

```text
brokerage
exchange charges
regulatory charges
taxes
spread cost
slippage
market impact
other instrument/provider costs
```

Unknown material cost is not zero.

## 6. Gross and net economics

Where the relevant formula is defined:

```text
net_economic_value
    = gross_economic_value
    - estimated_transaction_cost
```

The exact gross-value formula and numerical cost parameters are formula-registry/research dependencies and remain UNFROZEN.

## 7. Scenario economics

Where uncertainty requires scenario representation:

```text
scenario_i = {
    outcome,
    probability,
    economic_value
}
```

For a complete discrete distribution:

```text
p_i >= 0
Σ p_i = 1
E[V] = Σ p_i V_i
```

Expected value must not be confused with realized return or risk authorization.

## 8. Liquidity

When material, economic valuation must preserve:

```text
bid_size
ask_size
spread
available_quantity
depth_reference
observation_time
```

Liquidity constraints are evidence about executable economics, not merely descriptive features.

## 9. Options

Option economics must preserve canonical contract identity and, where applicable:

```text
underlying
expiry
strike
option_type
lot_size
premium
bid/ask
liquidity
execution uncertainty
```

Provider Greeks may be consumed only when their semantics are verified. They do not automatically become canonical formulas.

## 10. Estimated versus realized economics

Decision-time economic estimates are immutable historical evidence.

After execution, realized economics are derived from actual fills and actual known costs.

```text
estimated_economics != realized_economics
```

Realized P&L must never overwrite the decision-time estimate.

## 11. Slippage

Slippage must identify its reference price and side convention.

Conceptually:

```text
slippage = realized_execution_price - reference_executable_price
```

with sign normalized by trade side.

## 12. Causal rule

For a decision at time `t`:

```text
available_at(input) <= t
```

must hold for every material economic input.

Later fills, later quotes, later cost observations, and later market movement cannot influence the historical estimate.

## 13. Economic eligibility

Economic eligibility is a policy predicate over:

```text
probability
scenario economics
price semantics
costs
liquidity
horizon
execution uncertainty
```

Its structure is frozen; its numerical thresholds are validation-dependent.

## 14. Risk separation

Economic attractiveness cannot authorize exposure.

```text
EconomicEligibility
        |
        v
RiskAuthorization
        |
        v
ExecutionIntent
```

A positive economic estimate may still be rejected by risk, lifecycle, data-quality, or provider constraints.

## 15. Failure conditions

The economic layer must not produce a normal executable economic decision when required material inputs are:

```text
unknown price semantics
unknown material cost
invalid instrument
expired/invalid contract
stale required liquidity evidence
causally unavailable
invalid probability
invalid scenario distribution
inconsistent units/signs
```

The applicable downstream policy may reject, defer, or mark the opportunity unavailable.

## 16. Frozen architecture

```text
probability/economics separation
estimated/realized separation
quote/executable-price separation
cost/economics separation
unknown-cost semantics
scenario representation
causal availability rule
liquidity as executable constraint
risk-authority separation
historical estimate immutability
```

## 17. Learned / validation-dependent

```text
slippage distributions
market-impact estimates
fill probabilities
cost distributions
liquidity-response functions
minimum economic edge
opportunity thresholds
calibrated economic parameters
```

No value is selected merely because it appears reasonable.

## 18. Configuration to validate

```text
cost inclusion policy
price-reference policy
quote staleness limits
liquidity acceptance rules
scenario horizon policy
minimum economic-edge policy
```

## 19. External dependencies

UNKNOWN / TODO:

```text
exact Kite fee/billing semantics
exact TrueData executable-price semantics
historical liquidity population
historical slippage population
market-impact methodology
option transaction-cost population
```

These must be empirically verified or learned; they must not be invented.

## 20. Hostile scenarios

The implementation must test:

```text
future quote
future fill
unknown fee treated as zero
LTP substituted for executable price
stale bid/ask
crossed market
zero liquidity
partial fill
wrong option lot size
expired option
probability outside [0,1]
scenario probabilities not summing to one
negative/incorrect cost sign
estimated economics overwritten by realized P&L
```

## 21. Invariants

```text
INV-175-001  Probability and economics are separate domains.
INV-175-002  Unknown material cost is never zero cost.
INV-175-003  Observed price is not automatically executable price.
INV-175-004  Estimated economics cannot be rewritten by realized execution.
INV-175-005  Realized economics use actual execution evidence where available.
INV-175-006  Material economic inputs obey causal availability.
INV-175-007  Economic eligibility cannot bypass risk authorization.
INV-175-008  Scenario probabilities are non-negative and normalize to one.
INV-175-009  Economic quantities preserve units and sign conventions.
INV-175-010  Historical economic estimates remain immutable.

## 22. Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- probability/economics separation
- estimated/realized distinction
- executable-price boundary
- transaction-cost boundary
- unknown-cost semantics
- scenario economics
- liquidity/execution uncertainty
- causal economic inputs
- risk separation
- immutable historical economic estimates

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- exact provider fee semantics
- executable-price methodology
- cost-model registry implementation
- empirical liquidity/slippage populations
- market-impact methodology

CONFIGURATION TO VALIDATE:
- cost inclusion
- price reference
- staleness
- liquidity
- minimum economic-edge policy

LEARNED / VALIDATION-DEPENDENT:
- slippage
- market impact
- fill probability
- cost distributions
- economic thresholds

BLOCKERS:
None for specification.
Production economic validation remains blocked until provider and historical cost/liquidity evidence is verified.

NEXT ARTIFACT:
A176 — Canonical Risk Capital Allocation, Exposure Budget & Hard-Risk Authorization Contract
```
