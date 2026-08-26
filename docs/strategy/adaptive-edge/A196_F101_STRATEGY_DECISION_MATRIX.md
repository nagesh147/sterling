# A196: F-101 Strategy Design Decision Matrix & Provisional Design Contract

---

> [!WARNING]
> **PROPOSAL STATUS: STRATEGY DESIGN DECISION ARTIFACT**
> - **Formula ID**: `F-101` (`Feature normalization / feature score`)
> - **Formula Registry Status**: `LOCKED` (`FormulaStatus.LOCKED`)
> - **Execution Gate**: `BLOCKED`
> - **Implementation Status**: **NOT AUTHORIZED**
> - **Purpose**: Resolves the four core strategy-design decisions for `F-101` (Feature Subset, Aggregation, Calibration Scope, Validation Criteria) and identifies temporal governance alignments against canonical specifications. Does **NOT** unlock `F-101` or authorize implementation code.
> - **SUBSET SUPERSESSION (2026-08-14)**: Strategy Lead **C-DV** via [`A206`](A206_F101_STRATEGY_LEAD_LI_A_AND_CDV_DECISION.md) **removes `DeltaVelocity` from the F-101 subset**. No proxy. The Exact Math Spec operator is unchanged. Current authorized vector: \((\mathrm{LogReturn},\ \mathrm{LiquidityImbalance},\ \mathrm{VolatilityRatio})\).

---

## 1. Authoritative Evidence Base & Classification Conventions

Every normative statement in this document is strictly classified under one of four evidence tiers:
- **`CANONICAL EVIDENCE`**: Supported directly by an existing canonical specification document in `adaptive-edge/`.
- **`PROPOSED DESIGN`**: A deliberate research/design choice introduced for Strategy Lead evaluation.
- **`EMPIRICAL QUESTION`**: A hypothesis requiring historical out-of-sample data verification.
- **`STRATEGY DECISION`**: A choice requiring formal Strategy Lead approval.

---

## 2. DECISION 1 — F-101 FEATURE SUBSET

### 2.1 Complete Candidate Inventory Audit

| Variable ID | Canonical Name | Definition / Units | Source | Raw / Derived | Causal Availability | Scale Norm Required? | Redundancy & Downstream Target | Selection Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `V-DATA-001` | EventID | Identifier | Data Layer | Raw Event | Instantaneous | NO | Metadata / Audit trail | **EXCLUDED** (Metadata) |
| `V-MKT-001` | UnderlyingPrice | Price (INR) | TrueData Bar | Raw Observed | Instantaneous | YES (LogReturn transform) | Non-stationary level | **EXCLUDED** (Raw level non-stationary) |
| `V-MKT-002` | UnderlyingTradeQuantity | Volume (Contracts) | TrueData Bar | Raw Observed | Bar End | YES (Log Volume / Scale) | Raw volume non-stationary | **EXCLUDED** (Replaced by relative volume) |
| `V-INST-006` | OpenInterest | OI (Contracts) | TrueData Bar | Raw Observed | Bar End | YES (OI Delta transform) | Raw OI non-stationary | **EXCLUDED** (Replaced by OI change) |
| `V-FTR-003` | LogReturn | $r_t = \ln(P_t / P_{t-1})$ (Unitless) | `Exact Math Spec` | Primitive Derived | Bar End | YES (Robust scaling) | Target: `F-102` Directional Edge | **SELECTED** (Core Directional Input) |
| `V-MKT-005/006` | LiquidityImbalance | $\text{LI}_t = \frac{Q^B - Q^A}{Q^B + Q^A} \in [-1, +1]$ | `Exact Math Spec` | Primitive Derived | Quote Event | NO (Self-bounded $[-1, +1]$) | Target: `F-102`, `F-109` Option Selection | **SELECTED** (Order Book Imbalance Input) |
| `V-FTR-001` | DeltaVelocity | $\delta v_t = \frac{\Delta_W(t) - \Delta_W(t-\Delta W)}{\Delta W}$ | `Exact Math Spec` | Primitive Derived | Event Window | YES (Robust scaling) | Target: `F-102` Flow Acceleration | **SUPERSEDED by A206 C-DV — REMOVED from F-101 subset (no proxy)** |
| `V-FTR-002` | VolatilityRatio | $VR_t = \frac{\sigma_{\text{short}}}{\sigma_{\text{long}}}$ (Ratio) | `Exact Math Spec` | Primitive Derived | Rolling Window | YES (Location / Scale) | Target: `F-104` Mode, `F-106` Risk | **SELECTED** (Volatility State Input) |
| `V-OR-001/003` | OpeningRangeWidth | Price Range (Points) | `Variable Registry` | Derived State | Post-OR Completion | YES | Regime classification | **EXCLUDED** (Regime state, downstream) |
| `V-SES-004` | SessionElapsedTime | Time (Seconds) | `Variable Registry` | Derived State | Clock Event | NO | Intraday seasonality filter | **EXCLUDED** (Session state, downstream) |

---

### 2.2 Detailed Subset Justification (`STRATEGY DECISION`)

#### Proposed F-101 Subset ($\mathbf{x}_{\text{F101}}$) (`PROPOSED DESIGN`, **subset superseded by A206**)

Historical A196 4-vector (record only):

$$\mathbf{x}_{\text{F101}}^{\text{A196}}(t) = \big( \text{LogReturn}(t), \text{LiquidityImbalance}(t), \text{DeltaVelocity}(t), \text{VolatilityRatio}(t) \big)^T$$

**Authorized after C-DV (`A206`):**

$$\mathbf{x}_{\text{F101}}^{\text{A206}}(t) = \big( \text{LogReturn}(t), \text{LiquidityImbalance}(t), \text{VolatilityRatio}(t) \big)^T$$

- **Why Selected**:
  1. **Dimensionless & Complementary**: Covers directional price momentum (`LogReturn`), order book liquidity imbalance (`LiquidityImbalance`), institutional trade flow impulse (`DeltaVelocity`), and volatility regime expansion (`VolatilityRatio`).
  2. **Zero Multicollinearity Redundancy**: Price, depth, flow, and volatility measure distinct microstructural dynamics.
  3. **Direct Downstream Mapping**: Directly feeds directional edge (`F-102`), eligibility (`F-103`), dynamic mode (`F-104`), dynamic risk (`F-106`), and option contract selection (`F-109`).

- **Why Excluded**:
  1. **Raw Price Levels (`V-MKT-001`)**: Non-stationary; price level itself carries no fixed directional predictive distribution across time.
  2. **Raw Quantities (`V-MKT-002`, `V-INST-006`)**: Non-stationary across market regimes; transformed into relative returns, liquidity imbalance, and delta velocity.
  3. **Session & Opening Range State (`V-OR-001`, `V-SES-004`)**: Belong to macro regime classification layers, not feature-level standardization.

---

## 3. DECISION 2 — AGGREGATION

### 3.1 Candidate Comparison Audit

| Evaluation Dimension | Candidate A: Linear Weighted ($\sum w_i z_i$) | Candidate B: Robust Weighted + Tanh ($\tanh(\mathbf{w}^T \mathbf{z})$) | Candidate C: Non-Linear Kernel | Candidate D: Hierarchical / Grouped |
| :--- | :--- | :--- | :--- | :--- |
| **Mathematical Form** | $S = \sum_{i=1}^K w_i z_i$ | $S = \tanh\left(\sum_{i=1}^K w_i z_i\right)$ | $S = K(\mathbf{z}, \mathbf{z}')$ | $S = \sum w_g S_{\text{group},g}$ |
| **Interpretability** | High | High (Bounded) | Low (Black box) | Moderate |
| **Parameter Count** | $K$ weights | $K$ weights | $K^2 + C$ kernel params | $K + G$ weights |
| **Calibration Burden** | Low | Low | Very High | Moderate |
| **Outlier Sensitivity** | High (Unbounded output) | Low (Soft-bounded $(-1, +1)$) | High | Moderate |
| **Replay Determinism** | Bitwise Exact | Bitwise Exact | Numerical Drift Risk | Bitwise Exact |
| **Overfitting Risk** | Low | Low | High | Moderate |
| **Compatibility F-102+** | Unbounded (Distorts thresholds) | Perfect ($S \in (-1, +1)$ input) | Complex | Moderate |

---

### 3.2 Recommended Aggregation Operator (`PROPOSED DESIGN`)

$$\mathbf{z}_i(t) = \text{clip}\left( \frac{x_i(t) - \text{Med}_i}{\max(\text{IQR}_i / 1.349, \epsilon)}, -4.0, +4.0 \right)$$
$$S_{\text{feature}}(t) = \tanh\left( \sum_{i=1}^{K} w_i \cdot z_i(t) \right)$$

- **Classification**: Candidate B (**Robust Weighted Aggregation with Tanh Bounding**).
- **Weight Governance** (`LEARNED PARAMETER`): Weight vector $\mathbf{w} = (w_1, w_2, \dots, w_K)^T$ must be estimated via out-of-sample walk-forward calibration $\mathbf{w}_t = \text{Estimate}(\text{Info}_{\le t})$ with $\sum |w_i| = 1.0$. Zero arbitrary weights permitted.

---

## 4. DECISION 3 — CALIBRATION SCOPE

### 4.1 Scope Comparison Audit

| Calibration Scope | Description | Overfitting Risk | Sample Availability | Operational Complexity | Suitability |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Universal** | Single $(\boldsymbol{\mu}, \boldsymbol{\sigma})$ for all instruments | Zero | Extremely High | Minimum | **POOR** (Index & Options have incompatible price scales) |
| **B. Asset-Class** (`PROPOSED`) | Separate $(\boldsymbol{\mu}, \boldsymbol{\sigma})$ per asset class (Index Options vs Equity) | Low | High ($> 25,000$ bars) | Low | **RECOMMENDED** (Balances scale fidelity & sample stability) |
| **C. Instrument** | Separate $(\boldsymbol{\mu}, \boldsymbol{\sigma})$ per individual option strike | High | Low ($< 1,000$ bars/strike) | High | **POOR** (Severe sample deficiency on illiquid strikes) |
| **D. Regime-Conditioned** | Separate $(\boldsymbol{\mu}, \boldsymbol{\sigma})$ per volatility regime | Very High | Variable | High | **OPEN DECISION** (Requires regime stability proof) |
| **E. Hierarchical** | Global mean + instrument delta shrinkage | Moderate | High | High | Complex for baseline |

---

### 4.2 Recommended Calibration Scope (`PROPOSED DESIGN CHOICE`)
- **Recommendation**: **Asset-Class Specific Calibration** (`INDEX_OPTION` vs `EQUITY_STOCKS`).
- **Rationale**: Provides adequate sample size ($N > 25,000$ bars per fold) while isolating index option price/volatility dynamics from stock options.

---

## 5. DECISION 4 — VALIDATION ACCEPTANCE CRITERIA

### 5.1 Technical vs Economic Validation Framework (`PROPOSED DESIGN`)

```text
Technical Validation Pass (Engine Safety)
        |
        v
Economic Validation Pass (Strategy Advantage)
        |
        v
Formula Promotion Approval (FormulaStatus: LOCKED -> IMPLEMENTED)
```

### 5.2 Validation Acceptance Criteria Matrix

| Criterion | Evaluation Type | Threshold Type | Candidate Threshold (`PROPOSED DESIGN`) | Required Verification Artifact |
| :--- | :--- | :--- | :--- | :--- |
| **1. Numerical Stability** | Technical | Hard Gate | Zero NaN/Inf outputs under $10\times$ volume/price spikes | Unit test suite pass |
| **2. Distributional Stationarity** | Technical | Statistical Gate | Kolmogorov-Smirnov fold test $p > 0.05$ | Walk-forward audit report |
| **3. Parameter Stability** | Technical | Stability Gate | Max parameter drift between folds $\frac{\|\boldsymbol{\theta}_{k} - \boldsymbol{\theta}_{k-1}\|}{\|\boldsymbol{\theta}_{k-1}\|} < 15\%$ | Parameter drift report |
| **4. Causality Invariant** | Technical | Hard Invariant | 100% $\text{available\_at} \le \text{decision\_time}$ | Causal assertion test |
| **5. Deterministic Replay** | Technical | Bitwise Gate | 100% SHA-256 hash match on 2-pass replay | Replay hash test |
| **6. Missing-Data Robustness** | Technical | Failure Gate | `FeatureStatus.MISSING` propagation; zero unhandled exceptions | Missing-data test suite |
| **7. Incremental Predictive Value** | Economic | Strategy Edge | Out-of-sample directional hit-rate gain $> +2.5\%$ vs raw features | Out-of-sample experiment report |
| **8. Economic Net Value** | Economic | Strategy Edge | Cost-adjusted expected net value $\mathbb{E}[\text{Net}] > 0.0$ | Backtest P&L attribution |

> [!NOTE]
> All numerical threshold values above are explicitly marked as `OPEN STRATEGY DECISION` items requiring formal Strategy Lead sign-off.

---

## 6. TEMPORAL GOVERNANCE ALIGNMENT

### 6.1 Audit Against Canonical Walk-Forward Specification

The canonical document [`WALK-FORWARD WINDOW, PURGE AND EMBARGO SPECIFICATION.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/WALK-FORWARD%20WINDOW,%20PURGE%20AND%20EMBARGO%20SPECIFICATION.md) governs temporal partitioning:

1. **Section 11 & 15 (Purging Rule & Maximum Horizon $H_{\max}$)** (`CANONICAL EVIDENCE`):
   - Purge interval $\tau_{\text{purge}}$ is **NOT** a fixed constant. It is strictly determined by the maximum label horizon $H_{\max}$ of the experiment:
     $$\tau_{\text{purge}} = H_{\max}$$
2. **Section 17-19 (Embargo Rule & Correlation Length)** (`CANONICAL EVIDENCE`):
   - Embargo interval $\tau_{\text{embargo}}$ is **NOT** an arbitrary number. Section 19 explicitly states: *"We do not declare embargo = 30 minutes because it sounds reasonable. It must be justified by label horizon and correlation length."*

### 6.2 Conflict Resolution: A195 Proposal vs Canonical Specification

- **Identified Conflict**: A195 Section 8 proposed fixed numerical values ($\tau_{\text{purge}} = 1\text{ day}, \tau_{\text{embargo}} = 2\text{ days}$).
- **Canonical Resolution** (`CANONICAL CONSTRAINT`):
  - Fixed $\tau_{\text{purge}} = 1\text{ day}$ and $\tau_{\text{embargo}} = 2\text{ days}$ are **REJECTED as fixed constants**.
  - In the walk-forward calibration pipeline, $\tau_{\text{purge}}$ must be set dynamically to $H_{\max}$, and $\tau_{\text{embargo}}$ must be derived from historical autocorrelation decay analysis of the feature set.

---

## 7. FINAL STRATEGY DECISION MATRIX

| Decision Area | Current Status | Canonical Constraint | Candidate Options | Recommended Option (`PROPOSED DESIGN`) | Rationale | Approval Required |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Feature Subset** | **Superseded by A206 C-DV** | Must be causal, unitless, non-redundant | A. All raw features<br>B. 4-vector including DV<br>C-DV. 3-vector without DV | **A206**: `(LogReturn, LiquidityImbalance, VolatilityRatio)` | DV removed by Strategy Lead; no proxy | Strategy Lead (executed) |
| **2. Aggregation Operator** | Unfrozen | Must preserve determinism & causality | A. Linear weighted<br>B. Median/IQR + Tanh<br>C. Non-linear Kernel | **Option B**: Robust standardization + Tanh bounding | Resists outliers, outputs bounded $(-1, +1)$ | Strategy Lead |
| **3. Calibration Scope** | Unfrozen | Must prevent cross-asset distortion | A. Universal<br>B. Asset-Class<br>C. Symbol-Specific | **Option B**: Asset-Class Specific (`INDEX_OPTION`) | Sufficient sample size without scale bias | Strategy Lead |
| **4. Acceptance Criteria** | Unfrozen | Must enforce technical & economic gates | A. Technical only<br>B. Tech + Economic Gates | **Option B**: Dual-gate validation | Guarantees safety & strategy advantage | Strategy Lead |

---

## 8. F-101 PROVISIONAL DESIGN CONTRACT

### 8.1 Justified & Frozen Design Choices (`PROPOSED DESIGN`)
1. **Input Interface**: Consumes `FeatureSnapshot` at decision time $t$.
2. **Feature Subset**: **A206** 3-variable vector $\mathbf{x}_{\text{F101}} = (\text{LogReturn}, \text{LiquidityImbalance}, \text{VolatilityRatio})^T$. (`DeltaVelocity` removed; no proxy.)
3. **Operator Pipeline**: Two-Stage Median/IQR Robust Scaling + Tanh Soft-Bounding.
4. **Causality & Replay Contract**: 100% $\text{available\_at} \le \text{decision\_time}$; bitwise deterministic replay hash match.
5. **Temporal Partitioning**: Dynamic $\tau_{\text{purge}} = H_{\max}$ and autocorrelation-derived $\tau_{\text{embargo}}$.

### 8.2 Unresolved Items Pending Strategy Lead Approval (`OPEN DECISION`)
1. Formal sign-off on feature subset: **done for C-DV** (A206). 3-vector is the authorized subset.
2. Sign-off on Asset-Class Calibration Scope (`INDEX_OPTION`).
3. Out-of-sample economic gain threshold sign-off ($> +2.5\%$).
4. Execution of walk-forward parameter calibration script on historical NIFTY dataset to generate `f101_parameters_v1.json`.

---

## 9. EXPLICIT SAFETY & NON-AUTHORIZATION NOTICE

> [!CAUTION]
> **REMAINING LOCK & SAFETY DECLARATION**
> 
> 1. Formula `F-101` remains strictly **`LOCKED`** (`FormulaStatus.LOCKED`).
> 2. `A196` is a design decision matrix and does **NOT** authorize runtime code changes or parameter creation.
> 3. `ExecutionGate` remains **`BLOCKED`**.
> 4. No order routing (Paper or Live) is enabled.
> 5. No prediction models (`F-102`+) are introduced or unlocked.
