# Adaptive Edge V2.1 — New Strategy Definition

**Artifact:** A26-ND
**Version:** 2.1.0-proposed
**Status:** PROPOSED / RESEARCH-ONLY
**Purpose:** Explicitly unlock implementation of the previously blocked strategy-specific formula family without claiming that the proposal was recovered from the historical Adaptive Edge source.

## 1. Why this artifact exists

The A26 resolution attack established that the repository does not contain authoritative complete definitions for F-101..F-114. The repository therefore permits an unlock only through a new versioned Adaptive Edge strategy definition.

This artifact is that definition.

It is a **new strategy semantic**, not a recovered historical formula.

The implementation is therefore allowed to exist, but it is not production-authorized until the research/promotion gate passes.

## 2. Strategy objective

V2.1 is a causal directional option-buying strategy. It evaluates a decision-time feature vector, derives a bounded directional edge, evaluates economic eligibility, applies an explicit operating mode, authorizes a risk budget, selects a directionally compatible option candidate, sizes the position under explicit constraints, and manages the resulting position with explicit protection/re-entry rules.

The implementation is provider-neutral. Contract metadata such as multiplier and quantity increment are inputs from the instrument contract rather than hidden constants in the strategy.

## 3. Decision horizon

The initial research configuration uses:

```text
horizon_bars = 15
```

This is a **research parameter**, not a source-recovered truth. It is versioned and must be validated through walk-forward research before promotion.

## 4. F-101 — Feature score

For feature vector `X`, feature means `mu`, feature scales `sigma`, and weights `w`:

```text
z_j = (X_j - mu_j) / sigma_j

S = tanh( sum_j(w_j z_j) / sum_j |w_j| )
```

Domain:

```text
-1 <= S <= 1
```

All normalization parameters are explicit strategy state and must be fitted only inside the temporal research boundary when they are learned rather than configured.

## 5. F-102 — Directional edge

The bounded feature score is mapped to three directional states through a numerically stable softmax:

```text
l_up      = S
l_down    = -S
l_neutral = 0

p_k = exp(l_k - max(l)) / sum_j exp(l_j - max(l))

Edge = p_up - p_down
```

Direction is:

```text
UP    if Edge >= edge_threshold
DOWN  if Edge <= -edge_threshold
NONE  otherwise
```

`edge_threshold` is a research parameter.

## 6. F-103 — Opportunity eligibility

An opportunity is eligible only when all required conditions pass:

```text
Direction exists
AND ExpectedNetValue >= minimum_expected_net_value
AND data quality is valid
AND operating mode != DISABLED
```

Failure reasons are explicit and additive.

No future outcome or realized P&L may participate in this decision.

## 7. F-104 — Operating mode

The operating mode is derived from decision-time volatility and drawdown state:

```text
DISABLED if:
    data invalid
    OR volatility_ratio >= disabled_volatility_ratio
    OR drawdown >= disabled_drawdown_fraction

RESTRICTED if:
    volatility_ratio >= restricted_volatility_ratio
    OR drawdown >= restricted_drawdown_fraction

NORMAL otherwise
```

Thresholds are explicit research parameters.

Mode does not itself authorize risk.

## 8. F-105 — Profit protection

For an upward position:

```text
initial_stop = entry - initial_stop_distance
candidate_stop
    = entry
      + (favorable_extreme - entry) * profit_lock_fraction
      - initial_stop_distance

stop_t = max(previous_stop, initial_stop, candidate_stop)
```

For a downward position the relation is symmetric:

```text
initial_stop = entry + initial_stop_distance
candidate_stop
    = entry
      - (entry - favorable_extreme) * profit_lock_fraction
      + initial_stop_distance

stop_t = min(previous_stop, initial_stop, candidate_stop)
```

Thus protective stops move monotonically in the favorable direction and never loosen.

## 9. F-106 — Dynamic risk

Given base authorized risk `R`, edge strength `e`, and mode multiplier `m(mode)`:

```text
strength = clamp(e, edge_risk_floor, edge_risk_ceiling)

dynamic_risk
    = min(maximum_risk,
          R * m(mode) * strength)
```

with:

```text
m(NORMAL)     = normal_risk_multiplier
m(RESTRICTED) = restricted_risk_multiplier
m(DISABLED)   = disabled_risk_multiplier
```

Risk is capped and cannot become negative.

## 10. F-107 — Risk per unit

V2.1 defines planned risk per unit as protection distance plus explicitly modeled execution cost, converted through the contract multiplier:

```text
RiskPerUnit
    = max(
        |EntryPrice - ProtectionPrice| * ContractMultiplier
        + (EntryCostPerUnit + ExitCostPerUnit) * ContractMultiplier,
        minimum_risk_per_unit
      )
```

The cost values must be explicit pre-trade estimates. Realized future costs cannot be substituted.

## 11. F-108 — Position sizing

The quantity is the largest increment-aligned quantity that does not exceed authorized risk:

```text
Q_raw = floor(AuthorizedRisk / RiskPerUnit)

Q = floor(Q_raw / QuantityIncrement) * QuantityIncrement
```

Then apply the maximum quantity constraint.

If the resulting quantity is below the minimum tradable quantity, the result is zero with an explicit reason.

## 12. F-109 — Instrument selection

For an upward edge, only `CE` candidates are eligible.

For a downward edge, only `PE` candidates are eligible.

Candidates must also satisfy:

```text
liquidity_ok
slippage_ok
data_quality_ok
```

The selected contract is:

```text
argmax(ExpectedNetValue)
```

with deterministic instrument-ID tie-breaking.

Strike, expiry, multiplier, quantity increment and candidate availability are supplied by the time-valid instrument contract.

V2.1 does not hardcode a strike offset or expiry rule.

## 13. F-110 — Entry trigger

For an upward opportunity:

```text
UnderlyingPrice >= TriggerPrice
```

For a downward opportunity:

```text
UnderlyingPrice <= TriggerPrice
```

The trigger price is an explicit decision-time input.

## 14. F-111 — Exit trigger

An exit occurs when any explicit exit condition holds:

```text
protection breached
OR target reached
OR horizon expired
```

For upward positions:

```text
protection: price <= stop
 target:    price >= target
```

For downward positions:

```text
protection: price >= stop
target:     price <= target
```

## 15. F-112 — Protection parameterization

Given entry price and strategy parameters:

```text
initial_stop_distance = configured research parameter

target_distance
    = initial_stop_distance * target_multiple

profit_lock_fraction
    = configured research parameter
```

These are versioned strategy parameters.

## 16. F-113 — Re-entry

A re-entry is allowed only when:

```text
reentry_count < maximum_reentries
AND current_bar - prior_exit_bar >= reentry_cooldown_bars
AND a new opportunity exists
```

No re-entry may reuse a stale opportunity identity.

## 17. F-114 — Multi-position interaction

V2.1 applies a shared risk-capacity constraint:

```text
existing_risk + candidate_risk
    <= maximum_risk * portfolio_risk_fraction
```

and:

```text
existing_positions < maximum_positions
```

No candidate is allowed to exceed portfolio capacity merely because its individual economics are attractive.

## 18. Causal invariant

Every input to F-101 through F-114 must satisfy:

```text
availability_time <= decision_time
```

except post-trade outcome observations used only by future learning/evaluation.

## 19. Versioning

The complete semantic definition is:

```text
strategy_version = 2.1.0-proposed
```

Any change to a formula, parameter meaning, input semantics, state transition, or dependency requires a new strategy version.

## 20. Parameter governance

The initial values in `StrategyParameters` are research configuration only.

They are not claimed to be optimal and are not production-approved.

The research process must evaluate:

```text
feature normalization parameters
edge threshold
mode thresholds
risk multipliers
risk cap
protection parameters
re-entry parameters
portfolio constraints
```

using walk-forward validation and protected final evaluation.

## 21. Promotion gate

Implementation status is separate from production authorization.

```text
IMPLEMENTED
     |
     v
RESEARCH VALIDATION
     |
     v
PROMOTION APPROVED
     |
     v
EXECUTION AUTHORIZED
```

The current V2.1 definition is:

```text
IMPLEMENTED = yes
PROMOTED     = no
EXECUTABLE   = no
```

This prevents implementation from being mistaken for validated strategy truth.

## 22. Adversarial requirements

The implementation must test:

```text
future feature rejection
invalid normalization parameters
probability normalization
threshold boundary
mode degradation
monotonic protection
risk cap
lot/increment rounding
invalid option direction
trigger direction
horizon exit
re-entry cooldown
re-entry count
portfolio risk cap
maximum position count
```

## 23. Explicit limitations

This new definition does not claim:

```text
historical recovery of the original Adaptive Edge formulas
optimal parameter values
statistical profitability
live-trading readiness
provider-specific execution semantics
historical contract completeness
```

Those require research and external contract validation.

## 24. Resolution state

```text
A26 semantic architecture        RESOLVED
A26 original formula recovery   NOT RECOVERED
A26 new V2.1 definition          PROPOSED
F-101..F-114 implementation      IMPLEMENTED
research validation               REQUIRED
promotion                         NOT APPROVED
live execution                    BLOCKED
```

This is the deliberate unlock path authorized by the existing A26 resolution protocol.
