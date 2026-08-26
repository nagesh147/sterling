# A215 — F-109 Option Moneyness / Strike Selection Canonical Recovery

**Status:** `[SOURCE-RECOVERED / EXISTING IMPLEMENTATION RECONCILED / PARAMETER-GOVERNED]`
**Formula:** F-109
**Source:** Adaptive Order-Flow Options Scalping and Intraday Strategy — Master Mathematical Specification v1.0
**Source commit:** `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`

## 1. Canonical decision

F-109 resolves the tradable option contract after direction and economic eligibility have been established. It is an **instrument-selection problem**, not a second directional model.

The selector must choose from the actually listed option chain for the authorized underlying and expiry. A theoretical strike must never be converted into an order unless the exact listed contract exists and passes contract/data-quality checks.

## 2. Moneyness representation

For a call:

```text
ITM  <=> Strike < Spot
ATM  <=> Strike nearest Spot
OTM  <=> Strike > Spot
```

For a put the economic interpretation reverses:

```text
ITM  <=> Strike > Spot
ATM  <=> Strike nearest Spot
OTM  <=> Strike < Spot
```

Ordinal labels such as `ITM1`, `ITM2`, `OTM1`, `OTM2` refer to neighboring **listed strikes**, not arbitrary point offsets.

Therefore:

```text
spot = 24520
strike_step = 50
ATM ~= 24500
```

is only a candidate mapping. The actual contract must be resolved from the available chain.

## 3. Underlying direction is upstream

F-109 must not infer `BUY_CE` or `BUY_PE` from strike geometry. It receives direction from the upstream decision state.

```text
BUY_CE -> CE candidate ladder
BUY_PE -> PE candidate ladder
NO_TRADE -> no instrument
```

## 4. Candidate ordering

For each option type, candidate contracts are ordered by moneyness relative to the spot and then evaluated against the economic/instrument constraints.

The implementation may expose a standard research ladder such as:

```text
ITM2, ITM1, ATM, OTM1, OTM2
```

but this ladder is a **candidate set**, not a guarantee that ATM is selected.

## 5. Required hard constraints

A candidate must be rejected if any mandatory contract property is unavailable or invalid:

```text
listed contract absent
wrong expiry
wrong underlying
wrong option type
invalid strike
invalid lot size
missing token/contract identifier
stale option-chain data
invalid price data
unacceptable liquidity
unacceptable spread/slippage
risk constraint violated
```

No synthetic option symbol may be manufactured for execution.

## 6. Economic selection relationship

F-109 does not duplicate F-106's economic calculation. It supplies the concrete contract identity and moneyness attributes needed by the candidate-evaluation layer.

The architecture is:

```text
F-106 candidate economics
          ^
          |
       F-109
          |
   listed option chain
```

Where multiple contracts remain eligible, selection must be deterministic and use the validated candidate-ranking policy.

## 7. Existing implementation reconciliation

`backend/app/engines/adaptive_edge/option_ladder.py` already documents itself as a research/display adapter and explicitly states that it does not implement F-109. Its standard ladder is therefore retained as a display/candidate mechanism only, not promoted to the production F-109 formula. fileciteturn88file0L2-L6

The separate derivatives strike picker is Greeks/liquidity aware, but it contains crypto-oriented timeframe/IV assumptions and therefore cannot be silently promoted as the Adaptive Edge F-109 production formula. fileciteturn86file0L2-L6

## 8. Parameter governance

Potentially learned/validated parameters include:

```text
acceptable moneyness range
preferred delta range
delta tolerance
liquidity floors
spread limits
slippage limits
expiry selection policy
candidate ranking weights
```

These must remain versioned and calibrated. They are not implied merely by the presence of an ATM/ITM/OTM ladder.

## 9. Causal/data boundary

The option chain used for F-109 must be available no later than the decision timestamp:

```text
chain_available_at <= decision_time
```

Historical replay must use the chain that actually existed at the decision point. Current-chain reconstruction is prohibited for historical decisions when it changes contract availability or pricing.

## 10. Failure behavior

If no listed candidate satisfies all hard constraints:

```text
NO_TRADE
```

The selector must never downgrade the contract quality requirement merely to obtain a trade.

## 11. Resolution

```text
Source semantics:              RECOVERED
Existing candidate ladder:     DISPLAY/RESEARCH ONLY
Production strike policy:      PARAMETER-UNFROZEN
Historical chain requirement:  REQUIRED
Synthetic contracts:           PROHIBITED
Production implementation:     NOT YET AUTHORIZED
```

## 12. Next step

F-110 should consume the selected listed contract and establish the canonical order-intent construction boundary, including quantity, side, order type, limit protection, idempotency, and causal timestamps. 
