# A194: F-101 Feature Normalization Specification Gap & Strategy Design Blocker

---

## 1. Executive Status

```text
Formula ID:            F-101
Formula Name:          Feature normalization / feature score
Registry Status:       LOCKED (FormulaStatus.LOCKED)
Execution Gate:        BLOCKED
Implementation Status: NOT AUTHORIZED
```

This document establishes an explicit strategy-design blocker for formula `F-101`. Implementation of `F-101` is **STRICTLY PROHIBITED** until the Strategy Lead approves a complete mathematical definition and parameter-calibration contract.

---

## 2. Canonical Specification Evidence

The following authoritative specification documents establish what `F-101` requires and explicitly prohibit uncalibrated or assumed formulas:

1. **`adaptive-edge/FEATURE ENGINEERING MATHEMATICAL SPECIFICATION.md`**:
   - Outlines the feature admission pipeline and candidates.
   - Mandates: *"Features are canonical only when their mathematical definitions have been frozen. The initial registry therefore records the feature class rather than inventing numerical formulas."*
2. **`adaptive-edge/CANONICAL VARIABLE REGISTRY.md`**:
   - Registers variable identities.
   - Marks `VolatilityState`, `MomentumState`, and feature normalization parameters as `UNFROZEN` / `LEARNED`.
3. **`adaptive-edge/Exact Mathematical Operator Specification.md`**:
   - Specifies primitive market operators (midpoint, relative spread, log returns, velocity, delta).
   - Leaves composite feature normalization operators and parameters unassigned.
4. **`adaptive-edge/CANONICAL NUMERICAL PARAMETER LEARNING AND WALK-FORWARD CALIBRATION SPECIFICATION.md`**:
   - Mandates that every non-invariant numerical quantity must emerge from a defined walk-forward estimation procedure $\text{Parameter}_t = \text{Estimate}(\text{Info}_{\le t})$.
   - Explicitly forbids placing numerical values into the strategy merely because they "look reasonable."

---

## 3. Recovered Historical Evidence & Non-Canonicity Audit

An exhaustive git history audit examined historical candidate implementations:

1. **Commit `4ac79901` (`backend/app/engines/adaptive_edge/model.py`)**:
   - Introduced a provisional baseline model.
   - Explicitly documented in module docstring: *"This is a reconstructed baseline, not a recovered historical specification."*
   - Retired in commit `12a8f4e5`.
2. **Commit `1aaa108a` (`backend/app/engines/adaptive_edge/strategy_v21.py`)**:
   - Introduced a proposed parameterized V2.1 baseline.
   - Explicitly documented in module docstring: *"This module is the explicit new-definition path required by A26-RA after repository recovery found no authoritative complete F-101..F-114 definitions. It therefore does not claim to recover the old strategy."*
   - Retired in commit `5c65decd` / `cfd5c6a4`.

**Audit Conclusion**: Both historical implementations were provisional research proposals, explicitly disclaimed being recovered canonical strategy mathematics, and were formally retired. They **MUST NOT** be reused or treated as canonical truth.

---

## 4. Unresolved Mathematical Decisions Required

The Strategy Lead must formally define the following mathematical operators for `F-101`:

1. **Normalization Operator**:
   - Choice of transformation: Z-score ($Z = \frac{x - \mu}{\sigma}$), Min-Max scaling ($S = \frac{x - x_{\min}}{x_{\max} - x_{\min}}$), Robust Quantile scaling, or non-linear sigmoid/tanh scaling.
2. **Feature Input Subset**:
   - Exact subset of raw/derived features from `FeatureSnapshot` participating in `F-101`.
3. **Feature Transformation**:
   - Pre-scaling transforms (log transform, difference transform, winsorization).
4. **Aggregation Function**:
   - Linear combination ($\sum w_i z_i$), dot product, or non-linear combination.
5. **Weighting Mechanism**:
   - Equal weighting, inverse volatility weighting, principal components, or optimization weights.
6. **Scaling & Bounding**:
   - Hard clipping bounds $[-C, +C]$ or dynamic scaling bounds.
7. **Lookback Window ($L$)**:
   - Exact interval duration or bar count for baseline estimation.
8. **Minimum Sample Size ($N_{\min}$)**:
   - Minimum required valid observation count before output is valid.
9. **Missing-Data Semantics**:
   - Handling of missing individual features within an otherwise valid snapshot.
10. **Regime Dependence**:
    - Whether normalization parameters vary across volatility or intraday market regimes.

---

## 5. Parameter Governance & Calibration Decisions Required

`F-101` parameters belong to **Category B: LEARNED PARAMETERS (Offline / Walk-Forward Calibrated)**. The following governance decisions are required:

1. **Estimation Mode**: Offline walk-forward calibration vs online adaptive estimation.
2. **Walk-Forward Window**: Training window length, step size, fold count.
3. **Purge & Embargo**: Purge interval $\tau_{\text{purge}}$ and embargo interval $\tau_{\text{embargo}}$ to eliminate lookahead bias.
4. **Estimation Frequency**: Daily, weekly, or event-driven re-calibration schedule.
5. **Validation Folds**: Out-of-sample cross-validation structure.
6. **Distribution Stability Criteria**: Kolmogorov-Smirnov / Wasserstein stability thresholds across folds.
7. **Economic Contribution Criteria**: Minimum required out-of-sample expected net value positivity.
8. **Parameter Versioning**: Schema definition for parameter calibration artifacts.
9. **Immutable Freeze Artifact**: Requirement for a signed, versioned JSON/YAML parameter artifact.

---

## 6. Required Worked Examples

To authorize implementation, the Strategy Lead must provide:

- A minimum of 3 worked numerical examples detailing raw input vectors, intermediate transformations, parameter applications, and exact expected floating-point output values (accurate to 6 decimal places).

---

## 7. Required Calibration Artifact

To authorize implementation, the repository must contain:

- A versioned calibration artifact (`config/adaptive_edge/f101_parameters_v1.json`) containing frozen parameter vectors ($\boldsymbol{\mu}, \boldsymbol{\sigma}, \mathbf{w}, L, N_{\min}$) derived from an audited walk-forward calibration run on NIFTY market data.

---

## 8. Acceptance Criteria for Status Transition (`LOCKED` $\rightarrow$ `IMPLEMENTED`)

Formula `F-101` may transition from `FormulaStatus.LOCKED` to `FormulaStatus.IMPLEMENTED` in `formula_registry.py` **ONLY** when ALL of the following conditions are met:

1. **Mathematical Specification Recovery**: The exact mathematical formula and operators are documented and committed to the canonical specification.
2. **Parameter Freezing**: An audited calibration artifact (`f101_parameters_v1.json`) is committed and passes verification.
3. **Test Attachment**: Unit tests verify bitwise floating-point outputs against worked numerical examples.
4. **Governance Approval**: Formal promotion review and sign-off by the Strategy Lead.

---

## 9. Explicit Prohibitions

> [!CAUTION]
> **STRICT PROHIBITION ON ASSUMPTIONS & RUNTIME FABRICATION**
> 
> No engineer, AI assistant, or automated pipeline may:
> 1. Assume Z-score normalization.
> 2. Assume Min-Max normalization.
> 3. Assume Robust Quantile scaling.
> 4. Assume equal feature weights.
> 5. Assume arbitrary rolling lookback windows.
> 6. Assume default mean (`0.0`) or standard deviation (`1.0`).
> 7. Assume arbitrary numerical thresholds.
> 8. Derive parameters from the entire historical dataset (lookahead bias).
> 9. Use runtime self-calibration or online rolling estimation as a substitute for the missing specification.

---

## 10. Design Blocker Declaration

> **F-101 cannot proceed until the Strategy Lead approves the mathematical definition and parameter-learning contract.**
