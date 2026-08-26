# A198: F-101 Data Readiness and Feature Availability Audit

---

> [!WARNING]
> **AUDIT STATUS: DATA READINESS & FEATURE AVAILABILITY AUDIT ONLY**
> - **Formula ID**: `F-101` (`Feature normalization / feature score`)
> - **Formula Registry Status**: `LOCKED` (`FormulaStatus.LOCKED`)
> - **Execution Gate**: `BLOCKED`
> - **Implementation Status**: **NOT AUTHORIZED**
> - **Purpose**: Audits the exact TrueData API endpoints and historical feed fields available to Sterling against the [A197 Calibration Contract](file:///home/nageshmadaram/Sterling/docs/strategy/adaptive-edge/A197_F101_CALIBRATION_AND_VALIDATION_CONTRACT.md) and [A196 Proposed Feature Set](file:///home/nageshmadaram/Sterling/docs/strategy/adaptive-edge/A196_F101_STRATEGY_DECISION_MATRIX.md). Does **NOT** retrieve calibration datasets, generate parameter files, unlock `F-101`, or modify Python code.

---

## 1. Executive Verdict

```text
Overall Data Readiness:  PARTIALLY READY (DATA-READINESS GAP DETECTED)
Calibration Readiness:  NOT READY (BLOCKED BY HISTORICAL FEED LIMITATIONS)
Formula Registry Gate:   LOCKED (FormulaStatus.LOCKED)
Execution Gate:          BLOCKED
```

The data readiness audit established that while TrueData historical 1-minute bar feeds cleanly support price and volatility features (`LogReturn` and `VolatilityRatio`), historical 1-minute bar feeds **DO NOT** contain aggressor trade classification (aggressor buy/sell volume) or continuous market depth. Consequently, **`DeltaVelocity` is NOT AVAILABLE** in the historical bar dataset, and **`LiquidityImbalance` is CONDITIONALLY DERIVABLE** only if high-frequency tick quote history is fetched.

Per explicit governance rules, **no proxy has been invented, no feature replaced, and A196 has not been modified**. This data-readiness gap is logged as a formal strategy blocker.

---

## 2. TrueData Endpoint Inventory

Audit of documented TrueData API endpoints (v2.6 REST & v2.3 TCP) available to Sterling:

| Endpoint Path | Transport | Documented Endpoint Purpose | Available Historical Fields | Rate Limit / Throttling | Sterling Implementation Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `https://auth.truedata.in/token` | REST HTTP POST | OAuth2 Bearer Token Auth | `access_token`, `expires_in` | Standard | **IMPLEMENTED** ([`truedata.py`](file:///home/nageshmadaram/Sterling/backend/app/services/market_data/truedata.py#L94)) |
| `https://history.truedata.in/getbars` | REST HTTP GET | Historical OHLCV + OI Bars | `timestamp`, `open`, `high`, `low`, `close`, `volume`, `oi` | 10 req/sec | **IMPLEMENTED** ([`truedata.py`](file:///home/nageshmadaram/Sterling/backend/app/services/market_data/truedata.py#L168)) |
| `https://history.truedata.in/getlastnbars` | REST HTTP GET | Recent N OHLCV + OI Bars | `timestamp`, `open`, `high`, `low`, `close`, `volume`, `oi` | 10 req/sec | **IMPLEMENTED** ([`truedata.py`](file:///home/nageshmadaram/Sterling/backend/app/services/market_data/truedata.py#L198)) |
| `https://history.truedata.in/getticks` | REST HTTP GET | Historical Raw Trade & Quote Ticks | `timestamp`, `ltp`, `volume`, `oi`, (`bid`, `bidqty`, `ask`, `askqty` if `bidask=1`) | 5 req/sec | **IMPLEMENTED** ([`truedata.py`](file:///home/nageshmadaram/Sterling/backend/app/services/market_data/truedata.py#L143)) |
| `tcp.truedata.in:8082` | TCP Socket | Realtime Tick & Depth Feed | Realtime Quote, Trade, Depth | Stream | Documented (Not connected) |

---

## 3. Required Dataset Inventory (A197 Audit)

Audit of A197 calibration dataset requirements against TrueData capability:

| A197 Contract Requirement | Required Target | TrueData Capability | Audit Finding |
| :--- | :--- | :--- | :--- |
| **Instrument Universe** | `NIFTY 50` Index & Liquid Options | Fully Supported (`NIFTY 50`, `NIFTY26AUG24500CE`, etc.) | **COMPLIANT** |
| **Asset-Class Scope** | `INDEX_OPTION` | Fully Supported | **COMPLIANT** |
| **Bar Interval** | 1-minute (`1min`) | Fully Supported (`/getbars` interval=`1min`) | **COMPLIANT** |
| **Required Fields** | `timestamp`, `open`, `high`, `low`, `close`, `volume`, `oi` | Fully Supported in `/getbars` | **COMPLIANT** |
| **Timestamp Format** | ISO-8601 UTC | TrueData provides IST string; converted to UTC in adapter | **COMPLIANT** (via Adapter) |
| **Historical Depth** | 6 Calendar Months ($\sim 45,000$ 1-min bars) | Supported for 1-min bars back to contract launch | **COMPLIANT** |
| **Sample Count ($N_{\min}$)** | $\ge 25,000$ 1-minute bars per fold | Supported for 1-minute bars | **COMPLIANT** |
| **Historical Order Book Depth** | L2/L3 Bid/Ask Depth Queues | **NOT SUPPORTED** in historical `/getbars` | **NON-COMPLIANT** |
| **Historical Aggressor Buy/Sell Flags** | Classified Buy/Sell Trade Volume | **NOT SUPPORTED** in historical `/getbars` or `/getticks` | **NON-COMPLIANT** |

---

## 4. Feature-to-Data Dependency Matrix

Mapping of proposed A196 features to TrueData source fields:

| Proposed Feature Name | Canonical Variable ID | Target Mathematical Formula | Required Input Fields | TrueData Endpoint Required | Feature Readiness Classification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`LogReturn`** | `V-FTR-003` | $r_t = \ln(P_{\text{close}, t} / P_{\text{close}, t-1})$ | `close` | `/getbars` (1min) | **`DERIVABLE`** |
| **`VolatilityRatio`** | `V-FTR-002` | $VR_t = \frac{\sigma_{\text{short}}(r)}{\sigma_{\text{long}}(r)}$ | `close` | `/getbars` (1min) | **`DERIVABLE`** |
| **`LiquidityImbalance`** | `V-MKT-005/006` | $\text{LI}_t = \frac{Q^B_t - Q^A_t}{Q^B_t + Q^A_t}$ | `bidqty`, `askqty` | `/getticks` (`bidask=1`) | **`CONDITIONALLY DERIVABLE`** |
| **`DeltaVelocity`** | `V-FTR-001` | $\delta v_t = \frac{\Delta_W(t) - \Delta_W(t-\Delta W)}{\Delta W}$ | Classified Buy/Sell Trade Volume ($\text{ABV}_t, \text{ASV}_t$) | None (Not provided in history) | **`NOT AVAILABLE`** |

---

## 5. Exact Mathematical Derivability Analysis

### 5.1 `LogReturn` ($r_t$) — `DERIVABLE`
- **Source Data**: 1-minute bar `close` price $P_t$ from TrueData `/getbars`.
- **Derivation**:
  $$r_t = \ln\left( \frac{P_t}{P_{t-1}} \right)$$
- **Canonical Operator**: Logarithmic return operator $r_t$ from Section 2 of [`Exact Mathematical Operator Specification.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/Exact%20Mathematical%20Operator%20Specification.md#L66-L70).

### 5.2 `VolatilityRatio` ($\text{VR}_t$) — `DERIVABLE`
- **Source Data**: 1-minute bar `close` price $P_t$ from TrueData `/getbars`.
- **Derivation**:
  $$r_t = \ln(P_t / P_{t-1})$$
  $$\sigma_{\text{short}}(t) = \sqrt{\frac{1}{W_s}\sum_{j=0}^{W_s-1} (r_{t-j} - \bar{r}_s)^2}, \quad \sigma_{\text{long}}(t) = \sqrt{\frac{1}{W_l}\sum_{k=0}^{W_l-1} (r_{t-k} - \bar{r}_l)^2}$$
  $$\text{VR}_t = \frac{\sigma_{\text{short}}(t)}{\max(\sigma_{\text{long}}(t), \epsilon)}$$
- **Canonical Operator**: Volatility ratio operator $\text{VR}_t$ from Section 2 of `Exact Mathematical Operator Specification.md`.

### 5.3 `LiquidityImbalance` ($\text{LI}_t$) — `CONDITIONALLY DERIVABLE`
- **Source Data**: Top-of-book bid quantity $Q^B_t$ (`bidqty`) and ask quantity $Q^A_t$ (`askqty`).
- **Derivation**:
  $$\text{LI}_t = \frac{Q^B_t - Q^A_t}{Q^B_t + Q^A_t} \in [-1.0, +1.0]$$
- **Data Requirement**: Derivable ONLY when high-frequency tick quote history is fetched via `/getticks?bidask=1`. Standard 1-minute bar feeds (`/getbars`) do NOT contain quote depth.

### 5.4 `DeltaVelocity` ($\delta v_t$) — `NOT AVAILABLE`
- **Source Data Required**: Aggressor Buy Volume ($\text{ABV}_t$) and Aggressor Sell Volume ($\text{ASV}_t$).
- **Canonical Operator Requirement**: Section 7 of `Exact Mathematical Operator Specification.md` mandates trade classification:
  $$\text{BuyClass}_t = 1 \iff T_t \ge A_t, \quad \text{SellClass}_t = 1 \iff T_t \le B_t$$
  $$\text{ABV}_t = q_t \cdot \text{BuyClass}_t, \quad \text{ASV}_t = q_t \cdot \text{SellClass}_t, \quad \delta_t = \text{ABV}_t - \text{ASV}_t$$
- **TrueData Feed Audit**: TrueData historical `/getbars` and `/getticks` report aggregate `volume` only. They do NOT provide classified buy/sell trade flags or aggressor volume.
- **Verdict**: **`NOT AVAILABLE`** in TrueData historical market data feeds.

---

## 6. Historical Availability Analysis

1. **OHLCV + OI 1-Minute Bar History**:
   - **Status**: Available and consistent for `NIFTY 50` and options across multi-month historical windows via `/getbars`.
2. **Open Interest (`oi`) History**:
   - **Status**: Consistently present in TrueData option bar records.
3. **Historical Tick Quote History (`bid`, `ask`, `bidqty`, `askqty`)**:
   - **Status**: Available via `/getticks?bidask=1`, but limited in retention depth and bandwidth-heavy to query for multi-month calibration folds.
4. **Historical Aggressor Buy/Sell Trade Delta History**:
   - **Status**: **UNAVAILABLE** in TrueData historical REST endpoints.

---

## 7. Timestamp Analysis & Adapter Verification

- **TrueData Raw Timestamp Format**: String format `"YYYY-MM-DD HH:MM:SS"` in IST (Indian Standard Time, UTC+05:30).
- **Sterling Canonical Requirement**: ISO-8601 UTC timestamp strings with explicit timezone offset (`"+00:00"` or `"Z"`).
- **Adapter Verification**: [`TrueDataMarketDataAdapter.format_iso_timestamp()`](file:///home/nageshmadaram/Sterling/backend/app/services/providers/truedata/adapter.py#L40-L64) correctly converts IST strings to canonical UTC ISO-8601 strings and sets `available_at = event_time` for historical bars, enforcing $available\_at \ge event\_time$.

---

## 8. Missing-Data & Quality Analysis

- **TrueData Bar Zero-Volume Handling**: TrueData bar records during quiet sessions may contain `volume = 0` and identical `open = high = low = close`.
- **Handling in Adapter**: `TrueDataMarketDataAdapter.create_bar_event()` maps non-numeric or missing fields to `FeatureStatus.MISSING` and `value = None`.
- **Zero Scale Guard**: The proposed Median/IQR standardization correctly applies a scale floor $\epsilon = 1e-6$ when $\text{IQR} = 0$.

---

## 9. Provider Limitations & Endpoint Audit

1. **REST Rate Limits**: `/getbars` is limited to 10 requests per second; `/getticks` is limited to 5 requests per second.
2. **Historical Bar Interval Constraints**: TrueData V2.6 REST API supports documented intervals: `1min`, `2min`, `3min`, `5min`, `15min`, `30min`, `60min`.
3. **No Aggressor Order Flow**: Historical API endpoints do not provide trade initiator/aggressor classification flags.

---

## 10. Existing Sterling Implementation Coverage

| TrueData Feature / Endpoint | Documented in V2.6 API? | Implemented in [`truedata.py`](file:///home/nageshmadaram/Sterling/backend/app/services/market_data/truedata.py)? | Implemented in [`adapter.py`](file:///home/nageshmadaram/Sterling/backend/app/services/providers/truedata/adapter.py)? | Verified in Test Suite? |
| :--- | :--- | :--- | :--- | :--- |
| OAuth Authentication | YES | YES | YES | YES (`test_truedata_credentials.py`) |
| `/getbars` (OHLCV + OI) | YES | YES | YES | YES (`test_truedata_adapter.py`) |
| `/getlastnbars` | YES | YES | YES | YES (`truedata_auth_smoke_test.py`) |
| `/getticks` (Trades & Quotes) | YES | YES | YES | YES (`test_truedata_adapter.py`) |
| TCP Realtime Feed | YES | NO (Not needed for historical replay) | NO | N/A |

---

## 11. Data-Readiness Classification for F-101 Proposed Inputs

```text
[Feature Input]          [Classification]            [Data Readiness Verdict]
LogReturn                DERIVABLE                   READY (1min /getbars)
VolatilityRatio          DERIVABLE                   READY (1min /getbars)
LiquidityImbalance       CONDITIONALLY DERIVABLE     REQUIRES TICK QUOTE FEED (/getticks)
DeltaVelocity            NOT AVAILABLE               GAP DETECTED (No historical aggressor volume)
```

---

## 12. Explicit Data-Readiness Gaps

> [!IMPORTANT]
> **FORMAL DATA-READINESS GAP: HISTORICAL ORDER FLOW DELTA**
> - **Missing Provider Field**: Aggressor Buy Volume ($\text{ABV}_t$) and Aggressor Sell Volume ($\text{ASV}_t$) / Classified Buy/Sell trade flags.
> - **Impacted Proposed Feature**: `DeltaVelocity` ($\delta v_t$).
> - **Consequence**: `DeltaVelocity` cannot be calculated from historical TrueData bar data (`/getbars`). Calibration of `F-101` as proposed in A196 cannot be completed on historical bar datasets without resolving this data dependency.
> - **Governance Rule**: Per explicit user instructions, **NO PROXY HAS BEEN INVENTED, NO FEATURE HAS BEEN REPLACED, AND A196 HAS NOT BEEN ALTERED**. This gap is recorded as an explicit strategy-design blocker.

---

## 13. Non-Altering Recommendations

To resolve this data-readiness gap in future milestones without violating A196 or inventing uncanonical mathematics:
1. **TrueData Tick Quote Evaluation**: Research whether TrueData `/getticks?bidask=1` can be sampled across historical training folds to derive `LiquidityImbalance` ($\text{LI}_t$).
2. **TrueData Provider Query**: Inquire with TrueData support whether historical trade classification flags or aggressor volume feeds are available under an extended API subscription package.
3. **Strategy Lead Review**: Present this data-readiness gap to the Strategy Lead to decide whether `DeltaVelocity` requires a specialized tick ingestion pipeline or a formal specification adjustment.

---

## 14. Calibration Readiness Verdict & Final Status

```text
F-101 Status:             LOCKED (FormulaStatus.LOCKED)
A198 Audit Verdict:       DATA-READINESS GAP DETECTED
Calibration Readiness:    NOT READY (BLOCKED BY HISTORICAL DATA GAP)
Execution Gate:           BLOCKED
Kite Execution:           DISCONNECTED
```

- No calibration performed.
- No parameter files created (`f101_parameters_v1.json`).
- No runtime implementation authorized.
- No production Python code modified.
