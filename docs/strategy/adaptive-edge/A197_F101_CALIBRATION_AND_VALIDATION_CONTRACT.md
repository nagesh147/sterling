# A197: F-101 Calibration and Validation Contract

---

> [!WARNING]
> **PROPOSAL STATUS: CALIBRATION & VALIDATION CONTRACT ONLY**
> - **Formula ID**: `F-101` (`Feature normalization / feature score`)
> - **Formula Registry Status**: `LOCKED` (`FormulaStatus.LOCKED`)
> - **Execution Gate**: `BLOCKED`
> - **Implementation Status**: **NOT AUTHORIZED**
> - **Purpose**: Defines the rigorous offline calibration protocol, temporal splitting rules, validation framework, baseline benchmarks, and parameter freeze criteria for `F-101`. Does **NOT** execute calibration, generate frozen parameter files, unlock `F-101`, or modify runtime code.

---

## 1. Calibration Objective

### 1.1 Objective Definition
The objective of `F-101` calibration is to estimate the non-invariant numerical parameter vector $\boldsymbol{\theta}_t = (\boldsymbol{\mu}_t, \boldsymbol{\sigma}_t, \mathbf{w}_t)$ required to transform raw causal market state observations ($\text{FeatureSnapshot}$) into a dimensionless, stationary normalized feature representation $\mathbf{z}(t)$ and composite feature score $S_{\text{feature}}(t)$.

### 1.2 Separation of Concerns (`CANONICAL CONSTRAINT`)
Per Section 1 of [`CANONICAL NUMERICAL PARAMETER LEARNING AND WALK-FORWARD CALIBRATION SPECIFICATION.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/CANONICAL%20NUMERICAL%20PARAMETER%20LEARNING%20AND%20WALK-FORWARD%20CALIBRATION%20SPECIFICATION.md#L8-L23):
- **PARAMETER ESTIMATION**: The historical process of finding parameters $\boldsymbol{\theta}$ using strictly training information $\text{Info}_{\le t}$.
- **MODEL / STRATEGY VALIDATION**: The out-of-sample evaluation of whether the already-frozen parameter configuration $\boldsymbol{\theta}$ delivers statistically stable and economically profitable strategy edge without overfitting.

These two phases must remain strictly segregated. Parameter estimation must never consume validation or test data.

---

## 2. Data Requirements

### 2.1 Historical Dataset Specification (`PROPOSED DESIGN`)
To perform `F-101` calibration without data contamination, the input dataset must satisfy:
- **Provider Source**: TrueData REST / TCP Market Feed (`CanonicalMarketEvent`).
- **Asset-Class Scope**: `INDEX_OPTION` (NIFTY 50 Index and NIFTY Liquid Options).
- **Bar Interval**: 1-minute OHLCV + Open Interest bars.
- **Required Market Fields**: `open`, `high`, `low`, `close`, `volume`, `oi`.
- **Required Derived Variables**: LogReturn ($r_t$), LiquidityImbalance ($\text{LI}_t$), VolatilityRatio ($\text{VR}_t$).  
  (`DeltaVelocity` **removed from F-101 requirements by A206 C-DV**. No proxy. **Minimum Historical Coverage below is NOT shortened.**)
- **Timestamp Integrity**: All observations must contain UTC ISO-8601 timestamps satisfying `available_at` $\ge$ `event_time`.
- **Missing-Data Threshold**: Maximum missing bar rate $< 0.1\%$ per training fold; missing fields produce `FeatureStatus.MISSING`.
- **Minimum Historical Coverage**: 6 calendar months (approx. 120 trading days / $\sim 45,000$ 1-minute bars).
- **Dataset Cryptographic Provenance**: Every calibration dataset must be versioned and signed with SHA-256 (`dataset_sha256`).

---

## 3. Temporal Splitting & Walk-Forward Partitioning

### 3.1 Partitioning Structure (`CANONICAL CONSTRAINT`)
Per [`WALK-FORWARD WINDOW, PURGE AND EMBARGO SPECIFICATION.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/WALK-FORWARD%20WINDOW,%20PURGE%20AND%20EMBARGO%20SPECIFICATION.md#L28-L68), every calibration fold follows the strict sequence:
$$\text{TRAIN} \longrightarrow \text{PURGE} \longrightarrow \text{VALIDATE} \longrightarrow \text{EMBARGO} \longrightarrow \text{TEST}$$

### 3.2 Dynamic Purge & Embargo Derivation (`CANONICAL CONSTRAINT`)
1. **Dynamic Purge Length ($\tau_{\text{purge}}$)**:
   - Fixed 1-day purging is **REJECTED as a fixed constant**.
   - Per Section 11 & 15 of the canonical specification, $\tau_{\text{purge}}$ MUST equal the maximum label horizon $H_{\max}$ of the experiment:
     $$\tau_{\text{purge}} = H_{\max}$$
2. **Dynamic Embargo Length ($\tau_{\text{embargo}}$)**:
   - Fixed 2-day embargo is **REJECTED as a fixed constant**.
   - Per Section 17-19 of the canonical specification, $\tau_{\text{embargo}}$ MUST be derived from the autocorrelation decay of the feature set ($R_x(\tau) \le 0.05$).

---

## 4. F-101 Parameter Estimation Protocol

### 4.1 Location ($\boldsymbol{\mu}$) & Scale ($\boldsymbol{\sigma}$) Estimation (`PROPOSED DESIGN`)
For each feature $x_i$ over training interval $T_{\text{train}}$:
- **Location Estimator**: Sample Median $\text{Med}_i = \text{Median}(x_{i, t \in T_{\text{train}}})$.
- **Scale Estimator**: Normal-equivalent Interquartile Range $\text{Scale}_i = \frac{Q_{75}(x_i) - Q_{25}(x_i)}{1.349}$.
- **Scale Floor Safeguard**: If $\text{Scale}_i \le \epsilon$ (where $\epsilon = 1e-6$), $\text{Scale}_i$ is set to $\epsilon$ to prevent zero-division.

### 4.2 Causal Invariant (`CANONICAL CONSTRAINT`)
$$\boldsymbol{\theta}_t = \text{Estimate}\Big( \{x_\tau \mid \tau \in T_{\text{train}}, \tau \le t - \tau_{\text{purge}}\} \Big)$$
Parameters estimated over the full dataset $\text{Estimate}(\text{FullDataset})$ are strictly forbidden.

---

## 5. Feature Subset Evaluation Protocol

### 5.1 Proposed Subset Vector (`PROPOSED DESIGN`, **superseded for DV by A206**)

Historical A197 4-vector (record only):

$$\mathbf{x}_{\text{F101}}^{\text{A196}} = \big( \text{LogReturn}(t), \text{LiquidityImbalance}(t), \text{DeltaVelocity}(t), \text{VolatilityRatio}(t) \big)^T$$

**Authorized after C-DV:**

$$\mathbf{x}_{\text{F101}}^{\text{A206}} = \big( \text{LogReturn}(t), \text{LiquidityImbalance}(t), \text{VolatilityRatio}(t) \big)^T$$

### 5.2 Subset Elimination & Screening Rules (`STRATEGY DECISION`)
Before freezing a feature $x_i$ into the subset:
1. **Multicollinearity Screening**: Pairwise Spearman rank correlation $|\rho(x_i, x_j)| < 0.70$ over $T_{\text{train}}$. If $|\rho| \ge 0.70$, the variable with lower incremental predictive power is eliminated.
2. **Stationarity Gate**: Augmented Dickey-Fuller (ADF) test on $x_i$ over $T_{\text{train}}$ must reject non-stationarity ($p < 0.01$).
3. **Variance Gate**: Feature variance $\text{Var}(x_i) > 1e-8$. Zero-variance features are eliminated.

---

## 6. Weight Estimation Protocol

### 6.1 Candidate Weight Learning Algorithms (`OPEN DECISION`)
- **Option A (Equal Weighting)**: $w_i = \frac{1}{K}$ (`PROPOSED DESIGN BASELINE`).
- **Option B (Inverse Volatility Weighting)**: $w_i \propto \frac{1}{\text{Scale}_i}$.
- **Option C (Out-of-Sample Information Ratio Weighting)**: $w_i \propto \text{IR}_{i, T_{\text{val}}}$.

### 6.2 Weight Constraints (`CANONICAL CONSTRAINT`)
- Normalized weights: $\sum_{i=1}^K |w_i| = 1.0$.
- Zero arbitrary manual weights permitted; weights must be derived via authorized offline learning algorithms.

---

## 7. Normalization Pipeline Evaluation

### 7.1 Mathematical Form (`PROPOSED DESIGN`)
$$\mathbf{z}_i(t) = \text{clip}\left( \frac{x_i(t) - \text{Med}_i}{\max(\text{Scale}_i, \epsilon)}, -C, +C \right)$$
$$S_{\text{feature}}(t) = \tanh\left( \sum_{i=1}^{K} w_i \cdot z_i(t) \right)$$

### 7.2 Numerical Constants Justification (`PROPOSED DESIGN`)
- **Normal Scale Factor ($1.349$)**: Standard normal interquartile range factor ($z_{0.75} - z_{0.25} \approx 1.34898$). Proposed to align IQR scale with standard deviation under Gaussian normality while resisting heavy tails.
- **Clip Bounds ($\pm 4.0$)**: Proposed to prevent extreme $4\sigma+$ black-swan events from overwhelming downstream aggregations.
- **Scale Floor ($\epsilon = 1e-6$)**: Proposed numerical safety constant to guarantee zero-division immunity.

---

## 8. Validation Framework

```text
                               ┌────────────────────────────────┐
                               │  TECHNICAL VALIDATION GATES   │
                               │  - Numerical Determinism       │
                               │  - 100% Causality              │
                               │  - Deterministic Replay Hash   │
                               │  - Fail-Closed Missing Data    │
                               │  - Parameter Stability (<15%)  │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │   ECONOMIC VALIDATION GATES    │
                               │  - Out-of-Sample Hit-Rate Gain │
                               │  - Cost-Adjusted Net Value     │
                               │  - Monotonic Return Gradient   │
                               │  - Max Turnover Limit          │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │    PARAMETER FREEZE GATE       │
                               └────────────────────────────────┘
```

### 8.1 Technical Validation Battery (`PROPOSED DESIGN`)
1. **Numerical Determinism**: 100% bitwise parity on IEEE-754 floating point calculations.
2. **Causality Assertion**: 100% pass on `assert_causal(decision_time)` across all validation snapshots.
3. **Deterministic Replay**: SHA-256 hash match of feature vector outputs on 2-pass replay.
4. **Parameter Stability**: Maximum location/scale parameter drift across folds:
   $$\frac{\|\boldsymbol{\theta}_k - \boldsymbol{\theta}_{k-1}\|}{\|\boldsymbol{\theta}_{k-1}\|} < 15\%$$
5. **Distributional Diagnostic Battery**: Kolmogorov-Smirnov test ($p > 0.05$) supplemented by Wasserstein distance $W_1(F_k, F_{k-1}) < 0.10$ across validation folds.

### 8.2 Economic Validation Battery (`PROPOSED DESIGN`)
1. **Incremental Predictive Value**: Out-of-sample directional classification hit-rate improvement $> +2.5\%$ over benchmark baseline.
2. **Cost-Adjusted Expected Net Value**: Net P&L after simulated TrueData slippage and transaction costs $\mathbb{E}[\text{Net}] > 0.0$.
3. **Monotonicity Requirement**: Mean trade return must increase monotonically across feature score deciles $D_1 < D_2 < \dots < D_{10}$.

---

## 9. Mandatory Baselines & Benchmarks

To prove that `F-101`'s proposed complexity adds real strategy value, calibration MUST evaluate against 4 mandatory baselines:

| Baseline ID | Benchmark Name | Formula / Operator | Purpose |
| :--- | :--- | :--- | :--- |
| `BM-01` | Raw Unnormalized | $S = x_{\text{LogReturn}}$ | Test if normalization adds value |
| `BM-02` | Simple Z-Score | $z = \frac{x - \mu}{\sigma}, S = \frac{1}{K}\sum z_i$ | Test if robust scaling outperforms Gaussian Z-score |
| `BM-03` | Robust Equal Weight | $z = \text{Median/IQR}, S = \tanh(\frac{1}{K}\sum z_i)$ | Test if learned weights outperform equal weights |
| `BM-04` | Proposed `F-101` Design | Stage 1 Robust + Stage 2 Learned Tanh | Candidate design under test |

`F-101` candidate design (`BM-04`) must statistically outperform `BM-01`, `BM-02`, and `BM-03` on out-of-sample validation folds ($p < 0.05$) to be accepted.

---

## 10. Out-of-Sample Protection Protocol (`CANONICAL CONSTRAINT`)

1. **Test Set Isolation**: The final Test Set ($T_{\text{test}}$) is strictly held out.
2. **Prohibited Test Set Influences**: Test Set data MUST NOT influence feature selection, operator selection, weight learning, hyperparameter tuning, or threshold setting.
3. **Invalidation Rule**: If a design choice is modified based on Test Set results, that Test Set fold is declared **CONTAMINATED AND INVALIDATED** for final strategy promotion.

---

## 11. Multiple Testing & Research Selection Bias Controls

1. **Family-Wise Error Rate (FWER) Control**: When evaluating $M$ candidate feature configurations, apply Holm-Bonferroni p-value adjustment:
   $$p_{(i)} \le \frac{\alpha}{M - i + 1}$$
2. **Deflated Sharpe Ratio (DSR)**: Compute DSR to account for backtest overfitting across multiple research iterations.

---

## 12. Formal Acceptance Criteria Matrix

| Criterion ID | Target Metric | Classification Status | Required Threshold | Action on Failure |
| :--- | :--- | :--- | :--- | :--- |
| `AC-TECH-01` | Numerical Determinism | `CANONICAL CONSTRAINT` | Bitwise Exact (0.0 diff) | Hard Reject |
| `AC-TECH-02` | Causality Assertion | `CANONICAL CONSTRAINT` | 100% Pass (`available_at <= decision_time`) | Hard Reject |
| `AC-TECH-03` | Replay SHA-256 Hash | `CANONICAL CONSTRAINT` | 100% Replay Match | Hard Reject |
| `AC-TECH-04` | Parameter Drift | `PROPOSED DESIGN` | $< 15\%$ between folds | Reject Candidate Fold |
| `AC-TECH-05` | Wasserstein Distance | `PROPOSED DESIGN` | $W_1 < 0.10$ across folds | Require Re-calibration |
| `AC-ECON-01` | Hit-Rate Improvement | `OPEN STRATEGY DECISION` | $> +2.5\%$ out-of-sample vs `BM-01` | Hard Reject |
| `AC-ECON-02` | Net Expected Value | `OPEN STRATEGY DECISION` | $\mathbb{E}[\text{Net}] > 0.0$ post-slippage | Hard Reject |
| `AC-ECON-03` | Monotonic Return Deciles | `PROPOSED DESIGN` | 100% Monotonic decile returns | Hard Reject |

---

## 13. Reproducibility & Cryptographic Provenance Protocol

Every calibration run must automatically generate a signed metadata manifest (`calibration_manifest.json`) recording:
- `calibration_run_id`: UUIDv4
- `timestamp`: UTC ISO-8601
- `git_commit_hash`: Exact commit hash of codebase
- `dataset_sha256`: Cryptographic hash of input TrueData market dataset
- `config_sha256`: Cryptographic hash of calibration config file
- `python_version` & `dependency_lock_hash`: Runtime environment environment details

---

## 14. Parameter Freeze Gate Requirements

The parameter artifact [`config/adaptive_edge/f101_parameters_v1.json`](file:///home/nageshmadaram/Sterling/config/adaptive-edge/f101_parameters_v1.json) may be created **ONLY** when:
1. `A197` Calibration & Validation Contract is formally signed off by Strategy Lead.
2. Calibration script executes offline without errors or warnings.
3. All 8 Acceptance Criteria (`AC-TECH-01...05`, `AC-ECON-01...03`) are satisfied.
4. Baseline benchmark test proves `BM-04` statistically outperforms `BM-01...03`.
5. Cryptographic manifest `calibration_manifest.json` is generated and verified.

---

## 15. Failure & Rejection Conditions

Calibration **MUST BE IMMEDIATELY ABORTED AND REJECTED** if any of the following occur:
1. **Data Contamination**: Any overlap detected between $T_{\text{train}}$ and $T_{\text{test}}$ without proper dynamic purge/embargo.
2. **Parameter Instability**: Parameter fold drift $\ge 15\%$.
3. **Sign Inconsistency**: Feature weight $w_i$ flips sign across walk-forward folds.
4. **Economic Degradation**: Out-of-sample expected net value $\mathbb{E}[\text{Net}] \le 0.0$.
5. **Reproducibility Failure**: Inability to reproduce exact parameter values from `dataset_sha256` and random seed.

---

## 16. Final Status & Non-Authorization Declaration

> [!CAUTION]
> **REMAINING LOCK & NON-AUTHORIZATION NOTICE**
> 
> 1. Formula `F-101` remains strictly **`LOCKED`** (`FormulaStatus.LOCKED`).
> 2. `A197` is a calibration contract document only and does **NOT** authorize runtime implementation or code modifications.
> 3. No calibration scripts have been executed; no parameter files (`f101_parameters_v1.json`) have been created.
> 4. `ExecutionGate` remains **`BLOCKED`**.
> 5. No live or paper order routing is enabled.
