# A206: F-101 Strategy Lead Decision — LI Path A and DeltaVelocity C-DV

---

> [!WARNING]
> **GOVERNED STRATEGY DECISION ARTIFACT**
> - **Formula ID**: `F-101`
> - **Formula Registry**: `LOCKED`
> - **ExecutionGate**: `BLOCKED`
> - **Kite**: `DISCONNECTED`
> - **Calibration**: `NOT STARTED`
> - **No DeltaVelocity proxy**
> - **A197 window**: **NOT shortened**

---

## 1. Authorization

Strategy Lead explicit decisions (session instruction, 2026-08-14):

| Decision | Code | Meaning |
|---|---|---|
| LiquidityImbalance history | **A** | Obtain/enable sufficient TrueData historical tick entitlement for A197-scale LI |
| DeltaVelocity | **C-DV** | Formally supersede A196 and **remove** DeltaVelocity from the F-101 feature subset. Do **not** replace it with a proxy |

These two decisions are treated as unambiguous authorization for the actions in this artifact only.

---

## 2. Impact map (before any further code)

### 2.1 Artifacts that named DeltaVelocity as an F-101 input

| Artifact | Role | Action under C-DV |
|---|---|---|
| `A196_F101_STRATEGY_DECISION_MATRIX.md` | Proposed 4-feature subset including `V-FTR-001` | **Superseded for subset only.** Banner + subset row updated. Historical rationale retained. |
| `A197_F101_CALIBRATION_AND_VALIDATION_CONTRACT.md` | Required derived variables listed DV | Required-derived list updated by this artifact. **120-day / 6-month coverage unchanged.** |
| `A195_F101_FEATURE_NORMALIZATION_PROPOSAL.md` | Proposed feature universe includes DV | Left as historical proposal. A206 is the later decision. |
| `A198` / `A199` / `A200` / `A201` | Data audits; A201 PARKED | **Unchanged.** A201 remains the provider-capability record. |
| `A202` / `A203` / `A204` | Readiness / VR / LI audits | **Unchanged** as historical audits. Readiness now follows A206 + live LI depth. |
| Exact Math Spec §7–9 | Canonical \(\delta v_t\) mathematics | **Unchanged.** C-DV removes F-101 *use*, not the operator definition. |
| `CANONICAL VARIABLE REGISTRY.md` `V-FTR-001` | Variable identity | **Unchanged.** Variable still exists; it is no longer an F-101 input. |

### 2.2 Runtime / tests

| Path | DV dependency | Action |
|---|---|---|
| `formula_registry.py` | F-101 still `LOCKED` | **No change** |
| `execution_gate.py` | BLOCKED | **No change** |
| `liquidity_imbalance.py` | LI primitive only | **No change** |
| Adaptive Edge Python/TS | **No** `DeltaVelocity` / `V-FTR-001` symbol | **No runtime DV to delete** |
| Kite path | Disconnected | **No change** |

### 2.3 LI = A impact

Acquisition already implemented: `tick_history.py`, `tick_store.py`, `acquire_truedata_li_ticks.py`.  
A197 still requires ~120 trading days of LI-capable quotes. Live re-measure after this decision: `/getticks?bidask=1` still **empty before 2026-08-06**.

---

## 3. C-DV — superseding subset

### 3.1 Prior A196 subset (`PROPOSED`, now superseded)

\[
\mathbf{x}_{\text{F101}}^{\text{A196}}(t)
=
\big(\mathrm{LogReturn}(t),\ \mathrm{LiquidityImbalance}(t),\ \mathrm{DeltaVelocity}(t),\ \mathrm{VolatilityRatio}(t)\big)^T
\]

### 3.2 Authorized subset after C-DV

\[
\mathbf{x}_{\text{F101}}^{\text{A206}}(t)
=
\big(\mathrm{LogReturn}(t),\ \mathrm{LiquidityImbalance}(t),\ \mathrm{VolatilityRatio}(t)\big)^T
\]

| Feature | Status |
|---|---|
| LogReturn | **RETAINED** |
| LiquidityImbalance | **RETAINED** |
| VolatilityRatio | **RETAINED** |
| DeltaVelocity (`V-FTR-001`) | **REMOVED from F-101 subset** |

### 3.3 What C-DV does **not** do

- Does **not** invent ABV/ASV, uptick/downtick, Lee-Ready, midpoint, or bid/ask-ratio proxies
- Does **not** delete or rewrite Exact Math Spec \(\delta v_t\)
- Does **not** unlock F-101
- Does **not** reopen A201 except as a historical PARKED record
- Does **not** authorize LI removal (C-LI was **not** chosen)

---

## 4. LI = A — entitlement verification (2026-08-14)

Read-only live `/getticks?bidask=1` on `NIFTY-I` after the decision:

| Window | `n` |
|---|---|
| 2026-08-06 09:15–09:16 | 41 (\(LQ>0\)) |
| 2026-07-01, 06-01, 05-01, 04-01, 03-02, 02-02 | **0** |
| 2025-12-01, 09-01, 08-01, 02-14 | **0** |
| `/getbars` `NIFTY 50` 2025-02-14 09:15–09:30 | 15 bars (no `bidqty`) |

**LI = A is authorized but not realized.** This account still does not return A197-scale tick quotes. The existing acquirer already persists the entitled ~7 trading days. Additional code cannot create empty history.

A197 coverage requirement (**not shortened**): ~6 calendar months / ~120 trading days / ~45,000 1-minute bars **and** LI over that window.

---

## 5. Resulting F-101 readiness

```text
Subset:            A206 3-vector (LogReturn, LI, VR)
DeltaVelocity:     OUT OF F-101 SUBSET (C-DV)
LI history:        ENTITLEMENT AUTHORIZED, NOT PRESENT
A197 dataset:      NOT CONSTRUCTIBLE
VR W_short/W_long: still UNFROZEN; selection not started
F-101:             LOCKED
Calibration:       BLOCKED on LI depth
ExecutionGate:     BLOCKED
Kite:              DISCONNECTED
```

---

## 6. Safety

- No F-101 implementation
- No parameter freeze
- No ExecutionGate / Kite change
- No proxy
- No A197 window shrink
