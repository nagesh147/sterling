# Adaptive Edge — Exactness Audit

Date: 2026-08-11

## Audit method

Before extending the implementation, the existing Adaptive Edge code was compared against:

1. `docs/strategy/adaptive-edge/INDEX.md`
2. `docs/strategy/adaptive-edge/SPEC.md`
3. `docs/strategy/adaptive-edge/FORMULAS.md`
4. the Master Mathematical Specification Version 1.0
5. the existing implementation and tests

## Corrections made

### Risk per unit

The implementation previously added absolute-value, point-value and execution-cost semantics inside the risk-per-unit operator. The source relationship is:

```text
RiskPerUnit = EntryPrice - InitialStop
```

The operator now implements that relationship directly. Additional production constraints belong outside the mathematical operator.

### Position sizing boundary

The source defines:

```text
GrossRisk = RiskPerUnit × Q
Q = floor(MaxRisk / EffectiveRiskPerUnit)
```

The exact sizing operator now returns the source-defined `floor(MaxRisk / EffectiveRiskPerUnit)` result. Lot-size enforcement is a separate production constraint rather than being folded into the mathematical operator.

### Profit-protection boundary

The source defines:

```text
Giveback = PeakProfit - CurrentProfit
ProfitFloor = PeakPrice - AllowedGiveback
CandidateStop = max(OriginalRiskBoundary, ProfitFloor, DynamicRiskBoundary)
Stop_t = max(Stop_(t-1), CandidateStop_t)
```

The exact candidate-stop and monotonic-stop operators are now represented separately. The learned `AllowedGiveback` and dynamic risk boundary remain external inputs.

### Unanchored state contracts

The previous `contracts.py`, `state.py`, and `state_machine.py` introduced named mode values and lifecycle transitions that were not sufficiently specified by the source. They were removed rather than being treated as equivalent implementations.

The source-defined state names remain documentation requirements, but transition behavior will not be invented until the exact transition rules are recovered from the authoritative artifact.

### Deprecated formula gate

The edge boundary previously required an `F-10x` formula identifier. Those identifiers are deprecated compatibility metadata and are not the authoritative strategy formulas. The edge boundary now requires an explicit source anchor instead.

### Option-selection gate

§32 defines option selection as an argmax of `ExpectedNetEV_i` subject to validated liquidity, slippage, risk and data-quality constraints. A positive-EV gate was removed from §32 because the positive conservative-EV eligibility requirement belongs to §§34-35 and §66.

### Normalization estimator

The source defines the conditional CDF relationship:

```text
Percentile_t = F(x_t | Context_t, Data<=t)
```

The recovered source does not specify the empirical-CDF convention, interpolation/tie rule, smoothing, or minimum sample-size rule. A previously added empirical-CDF implementation was therefore treated as non-exact and is blocked pending recovery.

### Target/stop validation

§33 defines selection as `argmax ConservativeEV(s,m)` and §34 separately defines `ConservativeEV <= 0 -> NO_TRADE`. The target/stop module previously added undocumented positivity/range checks for target, stop, probabilities, gains, losses, and costs. Those checks were removed from the mathematical selection layer. Upstream validated inputs remain external to the source-defined operator.

### Traceability statuses

The source registry distinguishes:

```text
exact
parameterized
blocked
```

A mathematical operator may be exact while its learned parameter remains unresolved. The complete strategy component is not marked exact until all source-required definitions are available.

### Provisional traceability

The old F-101..F-114 matrix was removed from active traceability. It was a reconstruction, not the original mathematical specification.

## Current exactness policy

```text
Source relationship absent
    -> do not implement

Source relationship present but required parameter is learned
    -> implement operator, leave parameter unresolved

External provider contract absent
    -> implement provider-neutral boundary only

Implementation behavior not source-anchored
    -> remove or block it
```

## Result

This audit deliberately reduces the amount of code classified as implemented. That is intentional. The project is optimized for specification fidelity rather than apparent feature completeness.
