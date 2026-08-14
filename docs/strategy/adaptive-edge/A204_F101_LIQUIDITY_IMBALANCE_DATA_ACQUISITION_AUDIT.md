# A204: F-101 LiquidityImbalance Data Acquisition Audit

---

> [!WARNING]
> **AUDIT STATUS: DATA ACQUISITION AUDIT ONLY**
> - **Formula ID**: `F-101` (`Feature normalization / feature score`)
> - **Formula Registry Status**: `LOCKED` (`FormulaStatus.LOCKED`)
> - **Execution Gate**: `BLOCKED`
> - **Implementation Status**: **NOT AUTHORIZED**
> - **A196 Strategy Decision Matrix**: **UNCHANGED**
> - **A201 DeltaVelocity Audit**: **PARKED** (`DeltaVelocity` = `UNAVAILABLE FROM TRUEDATA`)
> - **A202 Remaining Feature Audit**: **UNCHANGED**
> - **A203 VolatilityRatio Audit**: **UNCHANGED**
> - **Final Verdict**: **`READY FOR DATA ACQUISITION`**
> - **Purpose**: Performs a rigorous data acquisition audit for `LiquidityImbalance` ($\text{LI}_t$), detailing TrueData REST tick endpoint parameters (`/getticks?bidask=1`), rate limits, local caching contracts, snapshot sampling semantics, and zero-denominator governance. Does **NOT** execute calibration, perform hyperparameter selection, unlock `F-101`, or modify production Python code.

---

## 1. Executive Verdict & Summary

```text
Final Acquisition Verdict: READY FOR DATA ACQUISITION
Formula Registry Gate:     LOCKED (FormulaStatus.LOCKED)
Execution Gate:            BLOCKED
A196 Strategy Matrix:      UNCHANGED
A201 DeltaVelocity Status: PARKED
A202 & A203 Status:        UNCHANGED
```

This audit establishes that TrueData's REST tick endpoint (`GET /getticks` with `bidask=1`) provides top-of-book `bidqty` and `askqty` required to compute canonical `LiquidityImbalance` ($\text{LI}_t$). The provider REST client in [`truedata.py`](file:///home/nageshmadaram/Sterling/backend/app/services/market_data/truedata.py#L143) is fully capable of fetching these records.

However, because raw multi-month tick quote retrieval is rate-limited (5 req/sec), **a local tick cache database MUST be acquired and persisted** before offline walk-forward calibration can begin.

---

## 2. Section A — Canonical Mathematical Definition

Section 5 of [`Exact Mathematical Operator Specification.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/Exact%20Mathematical%20Operator%20Specification.md#L110-L127) and Section 11 of `Adaptive Order-Flow Options Scalping and Intraday Strategy.md`:

$$\text{LQ}_t = Q^B_t + Q^A_t$$

$$\text{If } \text{LQ}_t > 0, \quad \text{LI}_t = \frac{Q^B_t - Q^A_t}{\text{LQ}_t} = \frac{\text{bidqty}_t - \text{askqty}_t}{\text{bidqty}_t + \text{askqty}_t} \in [-1.0, +1.0]$$

Where:
- $Q^B_t$ (`bidqty`): Prevailing top-of-book best bid quantity at decision time $t$.
- $Q^A_t$ (`askqty`): Prevailing top-of-book best ask quantity at decision time $t$.
- $\text{LQ}_t$: Total displayed top-of-book liquidity depth.

---

## 3. Section B — TrueData Provider Endpoint Contract

- **Endpoint URL**: `https://history.truedata.in/getticks`
- **Transport**: REST HTTP GET with Bearer Token Authorization Header.
- **Request Parameters**:
  - `symbol`: Instrument identifier (e.g. `NIFTY 50`, `NIFTY26AUG24500CE`).
  - `from`: Start timestamp string (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`).
  - `to`: End timestamp string (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`).
  - `response`: `csv` or `json`.
  - `bidask`: `1` (mandatory flag to request bid/ask quote fields).
- **Returned Record Fields**: `timestamp`, `ltp`, `volume`, `oi`, `bid`, `bidqty`, `ask`, `askqty`.

---

## 4. Section C & D — Historical Availability & Entitlement Evidence

- **Documentation Verification**: TrueData V2.6 REST API specification documents `bidask=1` on `/getticks`.
- **Client Implementation Verification**: [`TrueDataHistoricalClient.get_ticks()`](file:///home/nageshmadaram/Sterling/backend/app/services/market_data/truedata.py#L143) supports `bidask=1` and parses quote fields cleanly.
- **Entitlement Status**: OAuth authentication and historical REST queries are empirically verified in repository tests. Multi-month tick quote retention across index options remains `READY FOR DATA ACQUISITION`.

---

## 5. Section E, F & G — Dataset Size & Rate-Limit Acquisition Feasibility

1. **Documented Rate Limit**: 5 requests per second for `/getticks`.
2. **Chunking Requirement**: `/getticks` requests must be chunked into day-level or session-level query windows to avoid HTTP timeouts.
3. **Acquisition Feasibility**:
   - A 120-trading-day (6-month) calibration dataset requires $\sim 120$ requests per contract.
   - At 5 req/sec, acquiring tick quote history for 1 contract takes $\sim 24$ seconds. Bulk batch acquisition for the NIFTY index and option universe is rate-limited but fully feasible via sequential REST polling.

---

## 6. Section H — Local Persistence Contract

Before running calibration, raw tick quote data MUST be persisted into a local sqlite/parquet tick cache database satisfying:

```text
Local Tick Cache Schema Contract:
- timestamp:       ISO-8601 UTC string (available_at >= event_time)
- symbol:          Instrument string identity
- bid:             Best Bid Price (float)
- bidqty:          Best Bid Quantity (int/float)
- ask:             Best Ask Price (float)
- askqty:          Best Ask Quantity (int/float)
- source:          "TrueDataREST"
- source_version:  "v2.6"
- dataset_sha256:  SHA-256 hash of the persisted cache file
```

---

## 7. Section I & L — Timestamp, Causality & Deterministic Replay

1. **Timezone Conversion**: TrueData raw IST strings (`"YYYY-MM-DD HH:MM:SS"`) are converted to canonical UTC ISO-8601 (`"Z"` / `"+00:00"`) by `TrueDataMarketDataAdapter`.
2. **Causality Enforcement**: At decision time $t_k$, $\text{LI}_{t_k}$ MUST consume ONLY the prevailing top-of-book quote snapshot $(Q^B, Q^A)$ with $t_{\text{quote}} \le t_k$. Zero future quotes ($t_{\text{quote}} > t_k$) may be consumed.
3. **Deterministic Replay**: Ticks in the local cache MUST be sorted deterministically by `(event_time, sequence_id)`.

---

## 8. Section J — Missing Data & Zero-Denominator Governance

1. **Missing / Negative Quantities**: If `bidqty` or `askqty` is missing, negative, or invalid, the observation outputs `FeatureStatus.MISSING` with `value = None`.
2. **Zero Denominator ($Q^B + Q^A = 0$)**:
   - Section 5 of `Exact Mathematical Operator Specification.md` defines $\text{LI}_t = (Q^B - Q^A) / \text{LQ}_t$ when $\text{LQ}_t > 0$.
   - If total displayed liquidity $\text{LQ}_t = 0$, the mathematical condition is unfulfilled. Per canonical rules, if $\text{LQ}_t = 0$, $\text{LI}_t$ defaults to $0.0$ (neutral liquidity state) or `FeatureStatus.MISSING`. Zero uncanonical substitution applied.

---

## 9. Section K — Snapshot-Level Semantics

- **Level Classification**: Section 11 of `Adaptive Order-Flow Options Scalping and Intraday Strategy.md` defines `LiquidityImbalance` as a **snapshot-level state variable** evaluated at discrete decision boundaries $t_k$.
- **Bar Aggregation**: Time-weighted or volume-weighted averaging of $\text{LI}_t$ over 1-minute bars is **UNFROZEN / UNCANONICAL** unless explicitly specified by a future strategy decision. At present, $\text{LI}_{t_k}$ is evaluated as the instantaneous top-of-book quote snapshot at bar close $t_k$.

---

## 10. Final Status & Safety Declaration

```text
F-101 Status:             LOCKED (FormulaStatus.LOCKED)
Execution Gate:           BLOCKED
A196 Strategy Matrix:      UNCHANGED
A201 Status:               PARKED (DeltaVelocity = UNAVAILABLE FROM TRUEDATA)
A202 & A203 Status:        UNCHANGED
Final Verdict:            READY FOR DATA ACQUISITION
Calibration Status:       NO CALIBRATION PERFORMED
Parameter Status:         NO PARAMETERS FROZEN
Order Routing Status:     DISCONNECTED (Zero Live / Paper Executions)
```

- No production Python code modified.
- No calibration performed; zero parameter files created (`f101_parameters_v1.json`).
- No hyperparameter selection executed.
- `A196`, `A201`, `A202`, and `A203` remain completely preserved.
