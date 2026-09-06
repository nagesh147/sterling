# Adaptive Edge — Original Source Manifest

## Source of truth

The original strategy-development artifacts were uploaded in Git commit `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1` (`adaptive edge files uploaded`) on branch `feature/kite-settings-config-ux`.

This commit is the authoritative source for the strategy mathematics recovered from the original conversation-generated artifacts.

## Primary mathematical source

`adaptive-edge/Adaptive Order-Flow Options Scalping and Intraday Strategy.md`

Title: **Adaptive Order-Flow Options Scalping and Intraday Strategy — Master Mathematical Specification — Version 1.0**

This specification defines the strategy objective, causal event model, feature state, probability state, economic evaluation, option selection, risk, position management, walk-forward learning, validation, and system invariants.

## Canonical supporting sources

The uploaded source set also contains the following strategy specifications:

- `CANONICAL DATA-TO-EVENT CONTRACT.md`
- `CANONICAL DATA-TO-MATHEMATICS CONTRACT.md`
- `CANONICAL DECISION PRIORITY AND CONFLICT-RESOLUTION SPECIFICATION.md`
- `CANONICAL DOMAIN TYPE AND EVENT SCHEMA SPECIFICATION.md`
- `CANONICAL ECONOMIC DECISION AND OPTION SELECTION SPECIFICATION.md`
- `CANONICAL EXECUTION AND FILL MODEL.md`
- `CANONICAL EXECUTION, SLIPPAGE, AND FILL MODEL SPECIFICATION.md`
- `CANONICAL FORMAL STATE-MACHINE COMPLETENESS AUDIT.md`
- `CANONICAL NUMERICAL PARAMETER LEARNING AND WALK-FORWARD CALIBRATION SPECIFICATION.md`
- `CANONICAL POSITION SIZING AND RISK BUDGET SPECIFICATION.md`
- `CANONICAL RESEARCH DATASET AND WALK-FORWARD CONSTRUCTION SPECIFICATION.md`
- `CANONICAL RESEARCH EXPERIMENT AND VALIDATION PROTOCOL.md`
- `CANONICAL STATISTICAL ESTIMATION AND CALIBRATION SPECIFICATION.md`
- `LIVE POSITION STATE TRANSITION AND DYNAMIC MODE-RISK SPECIFICATION.md`
- `POSITION INITIATION AND ENTRY STATE SPECIFICATION.md`
- `PROBABILITY ENGINE MATHEMATICAL SPECIFICATION.md`
- `EXIT AND EXECUTION STATE SPECIFICATION.md`
- `Exact Mathematical Operator Specification.md`
- `FEATURE ENGINEERING MATHEMATICAL SPECIFICATION.md`
- `Historical Label Specification and Parameter Schema.md`
- `WALK-FORWARD WINDOW, PURGE AND EMBARGO SPECIFICATION.md`
- `TRUE DATA SOURCE-CONTRACT RECONCILIATION.md`
- `ADVERSARIAL MARKET VERIFICATION.md`
- `END-TO-END ADVERSARIAL VERIFICATION.md`

## Source precedence

When sources disagree, precedence is:

```text
Master Mathematical Specification
    ↓
Exact Mathematical Operator Specification
    ↓
Canonical subsystem specifications
    ↓
Canonical audits / verification specifications
    ↓
Implementation
```

Implementation is never evidence against the mathematical specification.

## Important correction

The previous reconstructed F-101..F-114 model was provisional. It used invented weights, thresholds, ATR multipliers, and option scoring coefficients that were not present in the original specification.

Those values must not be treated as canonical strategy mathematics.

The current branch therefore replaces that interpretation with parameterized operators directly traceable to the source specification. Numerical parameters explicitly designated as learned remain learned parameters and are not assigned arbitrary constants.

## Scope

This branch remains restricted to Adaptive Edge for Sterling Kite. No SuperTrend engine or Value Flow Navigator implementation is part of this source-of-truth recovery.
