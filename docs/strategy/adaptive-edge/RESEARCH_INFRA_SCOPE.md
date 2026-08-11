# Adaptive Edge — Research Infrastructure Scope

The following modules are research infrastructure, not the definition of Adaptive Edge:

```text
parameter_fitting.py
calibration.py
model_selection.py
walk_forward.py
```

## Allowed role

They may answer questions such as:

- how to estimate coefficients when the Master Specification requires learned coefficients;
- whether a candidate parameterization generalizes out of sample;
- whether probability outputs are calibrated;
- whether a frozen model survives an untouched holdout.

## Forbidden role

They must not:

- define the strategy's feature weights;
- invent entry thresholds;
- invent option-selection rules;
- invent stop/target multipliers;
- replace the source economic gate;
- become a prerequisite for basic deterministic strategy evaluation;
- cause a positive backtest result to override a failed economic/risk invariant.

## Ordering

```text
Strategy mathematics
        |
        v
Deterministic strategy core
        |
        v
Economic + risk decision
        |
        v
Replay
        |
        +--> research fitting / calibration / walk-forward
```

The research branch can tune quantities that the source specification explicitly declares learnable. It cannot define quantities that the source specification leaves as fixed relationships or safety invariants.
