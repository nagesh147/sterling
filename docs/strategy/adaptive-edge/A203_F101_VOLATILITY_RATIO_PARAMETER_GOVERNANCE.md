# A203: F-101 VolatilityRatio Parameter Governance

---

> [!WARNING]
> **GOVERNANCE STATUS: HYPERPARAMETER GOVERNANCE AUDIT ONLY**
> - **Formula ID**: `F-101` (`Feature normalization / feature score`)
> - **Formula Registry Status**: `LOCKED` (`FormulaStatus.LOCKED`)
> - **Execution Gate**: `BLOCKED`
> - **Implementation Status**: **NOT AUTHORIZED**
> - **A196 Strategy Decision Matrix**: **UNCHANGED**
> - **A201 DeltaVelocity Audit**: **PARKED** (`DeltaVelocity` = `UNAVAILABLE FROM TRUEDATA`)
> - **A206 (later)**: C-DV removes DeltaVelocity from the F-101 subset. VR lookbacks remain `[UNFROZEN]`. This audit is unchanged.
> - **A202 Remaining Feature Audit**: **UNCHANGED**
> - **Final Verdict**: **`READY FOR HYPERPARAMETER SELECTION`**
> - **Purpose**: Audits and establishes the formal parameter governance, classification, temporal constraints, leakage controls, and walk-forward selection protocol for `VolatilityRatio` lookback parameters ($W_{\text{short}}, W_{\text{long}}$). Does **NOT** assign numerical values, modify strategy matrices, calibrate parameters, unlock `F-101`, or modify production Python code.

---

## 1. Executive Verdict & Summary

```text
Final Governance Verdict: READY FOR HYPERPARAMETER SELECTION
Formula Registry Gate:    LOCKED (FormulaStatus.LOCKED)
Execution Gate:           BLOCKED
A196 Strategy Matrix:     UNCHANGED
A201 DeltaVelocity Status:PARKED
A202 Feature Status:      UNCHANGED
```

This audit establishes that $W_{\text{short}}$ and $W_{\text{long}}$ are **UNFROZEN HYPERPARAMETERS**. They are neither fixed mathematical constants nor hardcoded defaults. Per the canonical walk-forward parameter learning specification, their optimal values MUST be selected via out-of-sample validation folds ($T_{\text{val}}$) during offline walk-forward calibration under strict multiple-testing controls.

---

## 2. Section A — Canonical Definition

Section 2 of [`Exact Mathematical Operator Specification.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/Exact%20Mathematical%20Operator%20Specification.md#L68) and Section 13 of `Adaptive Order-Flow Options Scalping and Intraday Strategy.md`:

$$\text{VR}_t = \frac{\sigma_{\text{short}}(t)}{\max(\sigma_{\text{long}}(t), \epsilon)}$$

Where:
- Log Return: $r_t = \ln(P_t / P_{t-1})$.
- Rolling Volatility Estimator:
  $$\sigma_W(t) = \sqrt{\frac{1}{W} \sum_{k=0}^{W-1} (r_{t-k} - \bar{r}_W)^2}, \quad \text{where } \bar{r}_W = \frac{1}{W} \sum_{k=0}^{W-1} r_{t-k}$$
- $\epsilon > 0$: Scale floor numerical safety constant to prevent zero-division ($\epsilon = 1e-6$).

---

## 3. Section B — Parameter Classification Matrix

| Parameter Symbol | Parameter Role | Governance Classification | Selection Mechanism |
| :--- | :--- | :--- | :--- |
| **$W_{\text{short}}$** | Short Volatility Lookback Window | **`UNFROZEN HYPERPARAMETER`** | Walk-forward cross-validation on $T_{\text{val}}$ |
| **$W_{\text{long}}$** | Long Volatility Lookback Window | **`UNFROZEN HYPERPARAMETER`** | Walk-forward cross-validation on $T_{\text{val}}$ |
| **$\epsilon$** | Scale Floor Zero-Division Safeguard | **`NUMERICAL SAFETY INVARIANT`** | Fixed numerical constant ($\epsilon = 1e-6$) |
| **$\text{Med}_{\text{VR}}$** | Stage 1 Robust Standardization Location | **`LEARNED PARAMETER`** | Training fold sample median on $T_{\text{train}}$ |
| **$\text{Scale}_{\text{VR}}$** | Stage 1 Robust Standardization Scale | **`LEARNED PARAMETER`** | Training fold normal-equivalent IQR on $T_{\text{train}}$ |
| **$w_{\text{VR}}$** | Stage 2 Composite Feature Score Weight | **`LEARNED PARAMETER`** | Out-of-sample Information Ratio weighting on $T_{\text{val}}$ |

---

## 4. Section C — Repository & History Recovery Audit

An exhaustive search across the current working tree, git history, and canonical specification documents established:
1. **Zero Frozen Numerical Values**: No canonical specification document specifies frozen numerical values for $W_{\text{short}}$ or $W_{\text{long}}$.
2. **Explicit Unfrozen Status**: [`CANONICAL VARIABLE REGISTRY.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/CANONICAL%20VARIABLE%20REGISTRY.md#L723) explicitly registers `V-FTR-002 VolatilityState` exact estimator as **`UNFROZEN`**.
3. **Proposed Candidate Values**: `A196` proposed $W_{\text{short}} = 15\text{min}$ and $W_{\text{long}} = 60\text{min}$ as candidate design examples, but explicitly classified them as `PROPOSED / UNFROZEN`.

---

## 5. Section D — Allowed Parameter-Selection Mechanism

Per Sections 4 & 5 of [`CANONICAL NUMERICAL PARAMETER LEARNING AND WALK-FORWARD CALIBRATION SPECIFICATION.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/CANONICAL%20NUMERICAL%20PARAMETER%20LEARNING%20AND%20WALK-FORWARD%20CALIBRATION%20SPECIFICATION.md#L45-L80):

1. Hyperparameters $(W_{\text{short}}, W_{\text{long}})$ MUST be selected through discrete grid search over out-of-sample validation folds ($T_{\text{val}}$).
2. Selection Criterion: The optimal lookback pair $(W_{\text{short}}^*, W_{\text{long}}^*)$ maximizes out-of-sample Information Ratio ($\text{IR}_{\text{val}}$) or classification performance gain without violating parameter stability.
3. Separation of Phases:
   - **Feature-Definition Hyperparameters**: $(W_{\text{short}}, W_{\text{long}})$ evaluated over $T_{\text{val}}$.
   - **Learned Normalization Parameters**: $(\text{Med}, \text{Scale})$ estimated strictly over $T_{\text{train}}$.

---

## 6. Section E — Temporal & Structural Constraints

Every candidate lookback pair $(W_{\text{short}}, W_{\text{long}})$ evaluated during hyperparameter selection MUST satisfy:

1. **Ordering Constraint**:
   $$W_{\text{short}} < W_{\text{long}}$$
2. **Minimum Short Window Constraint**:
   $$W_{\text{short}} \ge 2 \text{ 1-minute bars}$$
   *(At least 2 return observations are required to compute sample variance).*
3. **Scale Floor Constraint**:
   $$\epsilon > 0 \quad (\epsilon = 1e-6)$$
4. **Purge & Embargo Alignment**:
   Per [`WALK-FORWARD WINDOW, PURGE AND EMBARGO SPECIFICATION.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/WALK-FORWARD%20WINDOW,%20PURGE%20AND%20EMBARGO%20SPECIFICATION.md#L28-L68), purging length $\tau_{\text{purge}} = H_{\max}$ and embargo length $\tau_{\text{embargo}}$ derived from feature autocorrelation decay.

---

## 7. Section F — Minimum-History Calculation

- To compute a valid log return $r_t$, at least 2 consecutive 1-minute bar prices $P_t, P_{t-1}$ are required.
- To compute a valid rolling standard deviation $\sigma_{\text{long}}(t)$, at least $W_{\text{long}}$ consecutive return observations are required.
- Therefore, the exact minimum historical bar count required before the first valid $\text{VR}_t$ observation can exist is:

$$N_{\text{min\_history}} = W_{\text{long}} + 1 \text{ 1-minute bars}$$

For any observation index $k < N_{\text{min\_history}}$, feature computation outputs `FeatureStatus.INSUFFICIENT_HISTORY` with `value = None`.

---

## 8. Section G — Data Leakage Controls

1. **Test Set Isolation**: The test fold $T_{\text{test}}$ is strictly held out.
2. **Prohibited Search Space Operations**: Hyperparameter candidates MUST NOT be evaluated or tuned on $T_{\text{test}}$.
3. **Causal Boundary Enforcement**: All rolling volatility calculations enforce $\text{available\_at} \le t_{\text{decision}}$.

---

## 9. Section H — Multiple-Testing & Research Bias Controls

1. **Holm-Bonferroni Adjustment**: When evaluating $M$ candidate lookback pairs $(W_{\text{short}}, W_{\text{long}})_m$ in the search grid, p-values must satisfy:
   $$p_{(i)} \le \frac{\alpha}{M - i + 1}$$
2. **Deflated Sharpe Ratio (DSR)**: Compute DSR across the search grid to adjust for trial variance and backtest overfitting.

---

## 10. Section I — Parameter Freeze Requirements

Final frozen values $(W_{\text{short}}^*, W_{\text{long}}^*, \text{Med}_{\text{VR}}^*, \text{Scale}_{\text{VR}}^*, w_{\text{VR}}^*)$ will be written to [`config/adaptive_edge/f101_parameters_v1.json`](file:///home/nageshmadaram/Sterling/config/adaptive-edge/f101_parameters_v1.json) **ONLY** when:
1. Walk-forward offline calibration executes without errors.
2. Selected lookback pair satisfies $W_{\text{short}}^* < W_{\text{long}}^*$.
3. All A197 technical and economic validation criteria are satisfied.
4. Cryptographic manifest `calibration_manifest.json` is generated and verified.

---

## 11. Section J — Explicit Unresolved Decisions

- The discrete search grid bounds for $(W_{\text{short}}, W_{\text{long}})$ (e.g. $W_{\text{short}} \in \{5, 10, 15\}$, $W_{\text{long}} \in \{30, 45, 60\}$) must be formally approved in the offline calibration script specification prior to running calibration execution.

---

## 12. Section K — Final Status & Non-Authorization Declaration

```text
F-101 Status:             LOCKED (FormulaStatus.LOCKED)
Execution Gate:           BLOCKED
A196 Strategy Matrix:      UNCHANGED
A201 Status:               PARKED (DeltaVelocity = UNAVAILABLE FROM TRUEDATA)
A202 Status:               UNCHANGED
Final Verdict:            READY FOR HYPERPARAMETER SELECTION
Calibration Status:       NO CALIBRATION PERFORMED
Parameter Status:         NO PARAMETERS FROZEN
Order Routing Status:     DISCONNECTED (Zero Live / Paper Executions)
```

- No production Python code modified.
- No calibration performed; zero parameter files created (`f101_parameters_v1.json`).
- No lookback numerical values hardcoded or assumed.
- `A196`, `A201`, and `A202` remain completely preserved.
