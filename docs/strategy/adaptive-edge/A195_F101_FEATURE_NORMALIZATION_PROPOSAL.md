# A195: F-101 Feature Normalization Strategy Proposal & Design Contract

---

> [!WARNING]
> **PROPOSAL STATUS: NON-CANONICAL RESEARCH PROPOSAL**
> - **Formula ID**: `F-101` (`Feature normalization / feature score`)
> - **Formula Registry Status**: `LOCKED` (`FormulaStatus.LOCKED`)
> - **Execution Gate**: `BLOCKED`
> - **Implementation Status**: **NOT AUTHORIZED**
> - **Purpose**: This document formulates a technically defensible strategy proposal for `F-101` for review by the Strategy Lead. It does **NOT** constitute canonical strategy truth, authorize code changes, or unlock execution.

---

## 1. Executive Summary

- **Intended Role** (`PROPOSED DESIGN`): `F-101` transforms raw causal market state observations (`FeatureSnapshot`) into a dimensionless, stationary, normalized feature vector $\mathbf{Z}(t)$ and composite feature score $S_{\text{feature}}(t)$ for downstream probability and economic engines (`F-102`+).
- **Current Blocker Status** (`CANONICAL CONSTRAINT`): `F-101` is locked due to [A194](file:///home/nageshmadaram/Sterling/docs/strategy/adaptive-edge/A194_F101_FEATURE_NORMALIZATION_SPECIFICATION_GAP.md) (unfrozen scaling operators, missing weight vectors, missing calibration parameters, and uncalibrated lookback windows).
- **Proposal Goal** (`PROPOSED DESIGN`): `A195` presents a complete mathematical operator proposal, walk-forward calibration protocol, parameter schema, and validation framework for Strategy Lead evaluation.
- **Non-Authorization Clause** (`CANONICAL CONSTRAINT`): `A195` does **NOT** authorize runtime implementation or code modifications. `F-101` remains strictly `LOCKED`.

---

## 2. Semantic Contract

- **Input** (`CANONICAL CONSTRAINT`): Causal `FeatureSnapshot` at decision time $t$ containing raw observed market variables ($P_{\text{close}}, V, \text{OI}$) and primitive derived quantities ($r_t, \text{LI}_t, \delta v_t, \text{VR}_t$).
- **Output** (`PROPOSED DESIGN`): Normalized feature snapshot containing dimensionless feature values $\mathbf{z}(t)$, composite feature score $S_{\text{feature}}(t)$, feature statuses, and provenance tracking.
- **Invariants Preserved** (`CANONICAL CONSTRAINT`):
  1. **Strict Causality**: $\text{feature\_available\_at} \le \text{decision\_time}$ for every normalized element.
  2. **Provenance Traceability**: `source_event_ids` and `formula_version` preserved.
  3. **Deterministic Replay**: Identical canonical event sequence + parameter artifact $\rightarrow$ Bitwise identical feature vector $\mathbf{z}(t)$.

---

## 3. Feature Universe

| Feature Name | Canonical Variable ID | Source | Units | Raw / Derived | Expected Direction | Normalization Required? | Classification Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `UnderlyingPrice` | `V-MKT-001` | TrueData Bar | Price (INR) | Raw Observed | Neutral | `PROPOSED DESIGN`: Log Return Transform | `CANONICAL CONSTRAINT` |
| `UnderlyingVolume` | `V-MKT-002` | TrueData Bar | Contracts | Raw Observed | Positive | `PROPOSED DESIGN`: Scale Normalization | `CANONICAL CONSTRAINT` |
| `OpenInterest` | `V-INST-006` | TrueData Bar | Contracts | Raw Observed | Neutral/Positive | `PROPOSED DESIGN`: Difference Normalization | `CANONICAL CONSTRAINT` |
| `LogReturn` | `V-FTR-003` | `Exact Math Spec` | Unitless Ratio | Primitive Derived | Directional | `PROPOSED DESIGN`: Robust Z-score Normalization | `LEARNED PARAMETER` |
| `LiquidityImbalance` | `V-MKT-005/006` | `Exact Math Spec` | Ratio $[-1, +1]$ | Primitive Derived | Directional | `CANONICAL CONSTRAINT`: Self-Bounded | `CANONICAL CONSTRAINT` |
| `DeltaVelocity` | `V-FTR-001` | `Exact Math Spec` | Delta / sec | Primitive Derived | Directional | `PROPOSED DESIGN`: Robust Scale Normalization | `LEARNED PARAMETER` |
| `VolatilityRatio` | `V-FTR-002` | `Exact Math Spec` | Ratio | Primitive Derived | Magnitude | `PROPOSED DESIGN`: Location / Scale Normalization | `LEARNED PARAMETER` |

---

## 4. Candidate Normalization Operators Evaluation

### Candidate A: Standard Z-Score Normalization (`PROPOSED DESIGN CANDIDATE`)
- **Formula**: $z_i(t) = \frac{x_i(t) - \mu_i}{\sigma_i}$
- **Inputs**: Raw feature $x_i(t)$, location parameter $\mu_i$, scale parameter $\sigma_i$.
- **Parameters**: $\mu_i$ (mean), $\sigma_i$ (standard deviation).
- **Advantages**: Simple, preserves variance linear scale.
- **Failure Modes**: Vulnerable to severe market spikes/fat tails; outliers distort mean $\mu_i$ and blow up variance $\sigma_i^2$.
- **Evaluation**: Non-preferred candidate for intraday order flow due to heavy-tailed distributions.

### Candidate B: Robust Location / Scale Normalization (Median / IQR) (`PROPOSED DESIGN CANDIDATE`)
- **Formula**: $z_i(t) = \text{clip}\left(\frac{x_i(t) - \text{Med}_i}{\text{IQR}_i / 1.349}, -C, +C\right)$.
- **Inputs**: Raw feature $x_i(t)$, median $\text{Med}_i$, Interquartile Range $\text{IQR}_i$, clip threshold $C=4.0$.
- **Parameters**: $\text{Med}_i$ (median), $\text{IQR}_i$ ($Q_{75} - Q_{25}$).
- **Advantages**: Insensitive to extreme market outliers; preserves rank and local linear relationships.
- **Failure Modes**: Division by zero if $\text{IQR}_i = 0$ (handled via scale floor $\epsilon$).
- **Evaluation**: Primary proposed candidate for feature standardization.

### Candidate C: Quantile-Based Empirical CDF Normalization (`PROPOSED DESIGN CANDIDATE`)
- **Formula**: $z_i(t) = 2 \cdot \hat{F}_i(x_i(t)) - 1 \in [-1, +1]$.
- **Inputs**: Feature observation $x_i(t)$, empirical CDF table $\hat{F}_i$.
- **Parameters**: Empirical CDF quantiles (100 bins).
- **Advantages**: Produces strictly bounded uniform output $[-1, +1]$.
- **Failure Modes**: Distorts distance metrics in distribution tails; dense lookup parameter tables.
- **Evaluation**: Secondary candidate.

### Candidate D: Soft-Bounded Tanh Transformation (`PROPOSED DESIGN CANDIDATE`)
- **Formula**: $z_i(t) = \tanh\left(\frac{x_i(t) - \mu_i}{k \cdot \sigma_i}\right) \in (-1, +1)$.
- **Inputs**: Feature observation $x_i(t)$, location $\mu_i$, scale $\sigma_i$, stiffness $k=2.0$.
- **Parameters**: Location $\mu_i$, scale $\sigma_i$, stiffness $k$.
- **Advantages**: Smooth, continuous soft boundary; robust against extreme outliers.
- **Failure Modes**: Saturated gradients in deep tails ($\tanh(\pm \infty) \to \pm 1$).
- **Evaluation**: Proposed candidate for composite score final mapping.

---

## 5. Recommended Candidate Design (`PROPOSED DESIGN — NOT CANONICAL`)

It is proposed to adopt a **Two-Stage Robust Normalization + Tanh Bounding Pipeline**:
1. **Stage 1 (Feature-Level Standardization)** (`PROPOSED DESIGN`):
   $$z_i(t) = \text{clip}\left( \frac{x_i(t) - \text{Med}_i}{\max(\text{IQR}_i / 1.349, \epsilon)}, -4.0, +4.0 \right)$$
2. **Stage 2 (Composite Aggregation & Soft Bounding)** (`PROPOSED DESIGN`):
   $$S_{\text{feature}}(t) = \tanh\left( \sum_{i=1}^{K} w_i \cdot z_i(t) \right) \in (-1.0, +1.0)$$

> [!NOTE]
> This recommended pipeline is a **proposed design choice** for Strategy Lead evaluation. It is **NOT** a recovered canonical requirement.

---

## 6. Composite Score Design (`PROPOSED DESIGN`)

- **Feature Vector $\mathbf{x}(t)$**: $(x_1, x_2, \dots, x_K)^T$ (`OPEN DECISION`).
- **Location Vector $\boldsymbol{\mu}$** (`LEARNED PARAMETER`): $(\text{Med}_1, \text{Med}_2, \dots, \text{Med}_K)^T$.
- **Scale Vector $\boldsymbol{\sigma}$** (`LEARNED PARAMETER`): $(\text{IQR}_1, \text{IQR}_2, \dots, \text{IQR}_K)^T$.
- **Normalized Vector $\mathbf{z}(t)$**: $(z_1, z_2, \dots, z_K)^T$.
- **Weight Vector $\mathbf{w}$** (`LEARNED PARAMETER`): $(w_1, w_2, \dots, w_K)^T$ where $\sum |w_i| = 1.0$.
- **Aggregation Function** (`PROPOSED DESIGN`): $S_{\text{feature}}(t) = \tanh(\mathbf{w}^T \mathbf{z}(t))$.
- **Output Domain** (`PROPOSED DESIGN`): $S_{\text{feature}}(t) \in (-1.0, +1.0)$.

---

## 7. Parameter Governance (`CANONICAL CONSTRAINT`)

Per `CANONICAL NUMERICAL PARAMETER LEARNING AND WALK-FORWARD CALIBRATION SPECIFICATION.md`:
1. **Causal Estimation**: Every parameter $\boldsymbol{\theta}_t = (\boldsymbol{\mu}_t, \boldsymbol{\sigma}_t, \mathbf{w}_t)$ must be estimated using strictly historical data available at or before $t$:
   $$\boldsymbol{\theta}_t = \text{Estimate}(\text{Info}_{\le t})$$
2. **Prohibited Practices**:
   - `NO` estimation on the full historical dataset (lookahead bias).
   - `NO` runtime default fallbacks ($\mu=0, \sigma=1$).
   - `NO` uncalibrated arbitrary weight assignments.
   - `NO` implicit runtime self-calibration without versioned parameter artifacts.

---

## 8. Walk-Forward Calibration Proposal (`PROPOSED DESIGN`)

- **Training Window Length ($W_{\text{train}}$)**: 60 trading days (`PROPOSED DESIGN CHOICE`).
- **Validation Window Length ($W_{\text{val}}$)**: 20 trading days (`PROPOSED DESIGN CHOICE`).
- **Purge Interval ($\tau_{\text{purge}}$)**: 1 trading day (`PROPOSED DESIGN CHOICE` - concept of purging is `CANONICAL CONSTRAINT`).
- **Embargo Interval ($\tau_{\text{embargo}}$)**: 2 trading days (`PROPOSED DESIGN CHOICE` - concept of embargo is `CANONICAL CONSTRAINT`).
- **Re-estimation Frequency**: Monthly walk-forward fold updates (`PROPOSED DESIGN CHOICE`).
- **Minimum Sample Requirement ($N_{\min}$)**: 5,000 bars per training window (`PROPOSED DESIGN CHOICE`).
- **Parameter Versioning**: Semantic versioning `v{major}.{minor}.{patch}` attached to parameter artifact SHA-256 hash (`CANONICAL CONSTRAINT`).

---

## 9. Validation Framework (`PROPOSED DESIGN`)

### Technical Validation (Engine Invariants)
1. **Numerical Stability**: Zero NaN/Inf outputs under extreme price/volume inputs ($10\times$ baseline volume).
2. **Distributional Stationarity**: Kolmogorov-Smirnov test across walk-forward folds ($p > 0.05$).
3. **Outlier Sensitivity**: Sensitivity test proving single-bar spikes alter normalized score by $< 5\%$.
4. **Causal Correctness**: Verified $\text{available\_at} \le \text{decision\_time}$.
5. **Deterministic Replay**: Bitwise equality of feature vectors across 2-pass replay runs.

### Economic Validation (Strategy Edge)
1. **Incremental Predictive Value**: Out-of-sample expected net value test proving $S_{\text{feature}}$ increases directional hit-rate by $> 2.5\%$.
2. **Monotonicity**: Higher $|S_{\text{feature}}|$ corresponds monotonically to higher mean trade return.

---

## 10. Worked Mathematical Examples (`ILLUSTRATIVE — NOT CALIBRATED PARAMETERS`)

> [!NOTE]
> The following numerical values demonstrate the mathematical operator mechanics. They do **NOT** represent calibrated production parameters or historically recovered values.

### Example A: Single Feature Standardization
- Feature $x = \text{LogReturn} = 0.0025$.
- Baseline parameters: $\text{Med} = 0.0005$, $\text{IQR} = 0.0010$.
- Scale calculation: $\text{Scale} = 0.0010 / 1.349 = 0.0007413$.
- Raw $z$: $(0.0025 - 0.0005) / 0.0007413 = 2.6980$.
- Clipped $z$: $\text{clip}(2.6980, -4.0, +4.0) = \mathbf{2.6980}$.

### Example B: Two-Feature Composite Aggregation
- Normalized features: $\mathbf{z} = (2.6980, -1.2000)^T$.
- Feature weights: $\mathbf{w} = (0.60, 0.40)^T$.
- Weighted sum: $(0.60 \times 2.6980) + (0.40 \times -1.2000) = 1.6188 - 0.4800 = 1.1388$.
- Composite score: $S_{\text{feature}} = \tanh(1.1388) = \mathbf{0.8136}$.

---

## 11. Failure Modes & Fail-Closed Matrix (`CANONICAL CONSTRAINT`)

| Trigger Event | System Failure Mode | System Response & Action | Resulting Status |
| :--- | :--- | :--- | :--- |
| Missing Input Feature | Feature element $x_i = \text{None}$ | Omit feature from composite sum; mark feature element | `FeatureStatus.MISSING` |
| Insufficient History ($N < N_{\min}$) | Uncalibrated baseline | Fail-closed; suppress score output | `FeatureStatus.MISSING` |
| Scale Collapse ($\text{IQR} \le 0$) | Zero division risk | Substitute scale floor $\epsilon = 1e-6$ | `FeatureStatus.VALID` (Warning) |
| Stale Input Data | Event delay $> \text{threshold}$ | Mark feature element stale | `FeatureStatus.STALE` |
| Missing Parameter Artifact | Calibration file missing | Hard fail-closed on startup | `RuntimeError` |
| Parameter/Data Mismatch | Feature count mismatch | Hard fail-closed on snapshot creation | `ValueError` |
| Lookahead Violation | $\text{available\_at} > \text{decision\_time}$ | Hard exception in snapshot post-init | `ValueError` |

---

## 12. Instrument / Regime Scope Analysis (`OPEN DECISION`)

- **Option Scope A (Universal Scope)**: Single set of parameters for all instruments. (Not recommended: Index options and stock options have incompatible price/volume scales).
- **Option Scope B (Asset-Class Specific Scope)**: Separate parameters for Index Options (NIFTY/BANKNIFTY) vs Stock Options. (`PROPOSED DESIGN CHOICE`).
- **Option Scope C (Instrument-Specific Scope)**: Dedicated parameter vectors per instrument symbol. (Higher overfitting risk).

**Recommendation**: Adopt **Option B (Asset-Class Specific Calibration)** as a proposed design choice to balance statistical stability with scale fidelity.

---

## 13. Downstream Interface Contract (`PROPOSED INTERFACE CONTRACT`)

`F-101` is proposed to expose the following standardized interface to downstream engines:
- `F-102` (Edge Score): Consumes $S_{\text{feature}}(t) \in (-1, +1)$ as a primary directional signal input.
- `F-103` (Eligibility): Evaluates $|S_{\text{feature}}(t)| \ge \text{threshold}_{\text{min\_edge}}$.
- `F-104` (Dynamic Mode): Consumes $z_{\text{volatility}}(t)$ to evaluate volatility regime triggers.
- `F-106` (Dynamic Risk): Scales authorized risk multiplier by $|S_{\text{feature}}(t)|$.
- `F-109` (Option Selection): Uses normalized liquidity scores $z_{\text{liquidity}}(t)$ to rank candidate contracts.

---

## 14. Determinism & Cryptographic Hash Contract (`CANONICAL CONSTRAINT`)

The output of `F-101` is strictly deterministic. The tuple:
$$\big(\text{CanonicalEventSequence}, \text{FeatureSnapshot}, \text{ParameterArtifact\_v1}\big)$$
must produce an identical normalized snapshot sequence with SHA-256 hash match:
$$\text{Hash}_{\text{F101}} = \text{SHA256}\Big( \text{JSON}\big(\mathbf{z}(t), S_{\text{feature}}(t), \text{statuses}, \text{available\_at}\big) \Big)$$

---

## 15. Proposed Parameter Freeze Schema (`PROPOSED DESIGN`)

```json
{
  "parameter_id": "PARAM-F101-NIFTY-V1",
  "formula_id": "F-101",
  "version": "1.0.0",
  "asset_class": "INDEX_OPTION",
  "estimation_window": {
    "start_date": "2026-01-01T00:00:00Z",
    "end_date": "2026-06-30T23:59:59Z",
    "sample_count": 25000
  },
  "purge_interval_days": 1,
  "embargo_interval_days": 2,
  "features": ["log_return", "liquidity_imbalance", "delta_velocity", "volatility_ratio"],
  "location_parameters": [0.0005, 0.0, 0.0, 1.0],
  "scale_parameters": [0.0010, 0.50, 12.5, 0.35],
  "weights": [0.35, 0.25, 0.25, 0.15],
  "clip_threshold": 4.0,
  "scale_floor_epsilon": 1e-6,
  "source_dataset_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "code_commit": "c5e3a575",
  "calibration_timestamp": "2026-08-14T12:00:00Z",
  "sha256": "4a5e1e4baab89f3a8b7c6d5e4f3a2b1c"
}
```

---

## 16. Acceptance Criteria for Status Transition (`LOCKED` $\rightarrow$ `IMPLEMENTED`)

Formula `F-101` may be unlocked **ONLY** after all 10 governance criteria are satisfied:

1. **Strategy Lead Approval**: Formal sign-off on `A195` proposal.
2. **Mathematical Closure**: Operator formulas committed to canonical specification package.
3. **Parameter Calibration**: Walk-forward parameter artifact generated and committed (`f101_parameters_v1.json`).
4. **Worked Examples Verification**: Unit tests verify 100% bitwise parity with worked mathematical examples.
5. **Technical Validation Pass**: All 5 technical validation tests pass (numerical stability, stationarity, causality, replay, missing-data).
6. **Economic Validation Pass**: Out-of-sample backtest proves positive expected net value contribution.
7. **Deterministic Replay Pass**: SHA-256 sequence hash match across double-pass replay.
8. **Adversarial Test Pass**: 100% pass rate on adversarial market scenarios (price spikes, missing bars, zero volume).
9. **Parameter Freeze**: Immutable parameter schema signed and checksummed.
10. **Governance Sign-off**: Explicit promotion PR approval.

---

## 17. Explicit Non-Authorization Declaration

> [!CAUTION]
> **REMAINING LOCK & NON-AUTHORIZATION NOTICE**
> 
> 1. Formula `F-101` remains strictly **`LOCKED`** (`FormulaStatus.LOCKED`).
> 2. `A195` does **NOT** authorize runtime implementation or code modifications.
> 3. No production or strategy code may consume `F-101` outputs.
> 4. `ExecutionGate` remains **`BLOCKED`**.
> 5. No live or paper order routing is enabled.
