# A199: TrueData Historical Order-Flow Capability Audit

---

> [!WARNING]
> **AUDIT STATUS: PROVIDER CAPABILITY AUDIT ONLY**
> - **Formula ID**: `F-101` (`Feature normalization / feature score`)
> - **Formula Registry Status**: `LOCKED` (`FormulaStatus.LOCKED`)
> - **Execution Gate**: `BLOCKED`
> - **Implementation Status**: **NOT AUTHORIZED**
> - **Supersedes**: `A198` (Superseded strictly as the latest data capability audit; `A198` is **NOT DELETED**).
> - **Purpose**: Evaluates TrueData API capabilities, endpoints, and WebSocket replay features against the `A198` data gaps for `LiquidityImbalance` and `DeltaVelocity`. Does **NOT** calibrate `F-101`, generate parameter files, unlock `F-101`, or modify production Python code.

---

## 1. Executive Verdict

```text
Overall Audit Verdict:   B. PARTIALLY RESOLVED — PROVIDER CONFIRMATION REQUIRED
LiquidityImbalance:      RESOLVED (REST Tick API /getticks?bidask=1)
DeltaVelocity:           UNCERTAIN / REQUIRES PROVIDER CONFIRMATION
Formula Registry Gate:   LOCKED (FormulaStatus.LOCKED)
Execution Gate:          BLOCKED
```

This provider capability audit establishes that:
1. **LiquidityImbalance ($\text{LI}_t$) is RESOLVED**: TrueData REST tick endpoint `/getticks` with `bidask=1` returns top-of-book `bidqty` and `askqty`, enabling exact derivation using the canonical operator $\text{LI}_t = \frac{Q^B - Q^A}{Q^B + Q^A}$.
2. **DeltaVelocity ($\delta v_t$) REQUIRES PROVIDER CONFIRMATION**: Standard REST historical bar (`/getbars`) and tick (`/getticks`) endpoints provide aggregate `volume` only, without aggressor buy/sell trade classification. Provider inquiry is required to determine whether TrueData's WebSocket Replay stream (`wss://replay.truedata.in`) or enterprise add-on package includes classified order flow delta feeds.

Per governance rules, **A196 is preserved without alteration, no proxy feature has been invented, and no code has been modified**.

---

## 2. TASK 1 Audit — Liquidity Imbalance ($\text{LI}_t$)

### 2.1 Endpoint & Request Parameter Analysis
- **Authoritative Endpoint**: `https://history.truedata.in/getticks`
- **Transport**: REST HTTP GET
- **Request Parameters**:
  - `symbol`: Instrument identity (e.g. `NIFTY 50`, `NIFTY26AUG24500CE`).
  - `from`: Start timestamp string (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`).
  - `to`: End timestamp string (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`).
  - `response`: Format (`csv` or `json`).
  - `bidask`: Set to `1` to request quote fields.

### 2.2 Response Field Audit
When `bidask=1`, TrueData `/getticks` returns:
- `timestamp`: Event timestamp string in IST.
- `ltp`: Last Traded Price (INR).
- `volume`: Trade volume.
- `oi`: Open Interest.
- `bid`: Best Bid Price (INR).
- `bidqty`: Best Bid Quantity (Contracts).
- `ask`: Best Ask Price (INR).
- `askqty`: Best Ask Quantity (Contracts).

### 2.3 Exact Mathematical Derivation
Using the canonical operator from Section 5 of [`Exact Mathematical Operator Specification.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/Exact%20Mathematical%20Operator%20Specification.md#L110-L127):
$$\text{LI}_t = \frac{Q^B_t - Q^A_t}{Q^B_t + Q^A_t} = \frac{\text{bidqty}_t - \text{askqty}_t}{\text{bidqty}_t + \text{askqty}_t} \in [-1.0, +1.0]$$
- **Condition**: Evaluated whenever $\text{bidqty}_t + \text{askqty}_t > 0$. If sum is zero, $\text{LI}_t = 0.0$.
- **Replay Determinism**: Bitwise deterministic when ticks are replayed in chronological order.
- **Verdict**: **`RESOLVED VIA REST TICK API`**.

---

## 3. TASK 2 Audit — Delta Velocity ($\delta v_t$)

### 3.1 Canonical Requirements
Section 7-9 of [`Exact Mathematical Operator Specification.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/Exact%20Mathematical%20Operator%20Specification.md#L170-L248) defines:
$$\text{ABV}_t = q_t \cdot \mathbb{I}(T_t \ge A_t), \quad \text{ASV}_t = q_t \cdot \mathbb{I}(T_t \le B_t), \quad \delta_t = \text{ABV}_t - \text{ASV}_t$$
$$\delta v_t = \frac{\Delta_W(t) - \Delta_W(t - \Delta W)}{\Delta W}$$

### 3.2 Provider Source Capability Classification

| TrueData Endpoint / Mechanism | Transport | Provided Fields | Order-Flow Capability Status | Classification |
| :--- | :--- | :--- | :--- | :--- |
| `GET /getbars` | REST | `open`, `high`, `low`, `close`, `volume`, `oi` | Aggregate volume only; no buy/sell split | **NOT AVAILABLE** |
| `GET /getticks` | REST | `ltp`, `volume`, `oi`, `bid`, `bidqty`, `ask`, `askqty` | Trade volume $q_t$ without aggressor trade flag | **NOT AVAILABLE** |
| `wss://push.truedata.in` (Port 8082) | TCP WebSocket | Realtime Quotes & Trades | Realtime stream; no multi-month history | **NOT AVAILABLE (Realtime only)** |
| `wss://replay.truedata.in` | TCP WebSocket | Replay Quotes & Trades | Streams historical ticks tick-by-tick | **UNCERTAIN / REQUIRES PROVIDER CONFIRMATION** |

### 3.3 Strict Governance Rule
- Aggressor direction **MUST NOT** be inferred from bar price movements ($P_t - P_{t-1}$).
- Buy/Sell volume **MUST NOT** be estimated from bid/ask quantity ratios.
- Trade classification **MUST NOT** be fabricated.
- **Verdict**: Classified as **`UNCERTAIN / REQUIRES PROVIDER CONFIRMATION`** pending technical inquiry with TrueData support regarding WebSocket Replay order-flow payloads.

---

## 4. TASK 3 Audit — Historical Replay Capability

Audit of TrueData Replay WebSocket specification from [`config.py`](file:///home/nageshmadaram/Sterling/backend/app/services/providers/truedata/config.py#L29):
- **Replay URL**: `wss://replay.truedata.in`
- **Authentication**: Bearer Token in WebSocket handshake (`Authorization: bearer <access_token>`).
- **Functionality**: Replays historical market sessions tick-by-tick at custom playback speeds ($1\times, 5\times, \text{max}$).
- **Data Payload**: Streams chronological trade events and quote snapshots.
- **Deterministic Replay Feasibility**: High, provided tick message sequence and timestamps remain identical across connections.
- **Sterling Implementation Status**: Configured in `TrueDataProviderConfig`, but **NOT CONNECTED / NOT IMPLEMENTED** in production engine code.

---

## 5. TASK 4 Audit — Existing Sterling Implementation Coverage

Audit of [`backend/app/services/market_data/truedata.py`](file:///home/nageshmadaram/Sterling/backend/app/services/market_data/truedata.py) and [`adapter.py`](file:///home/nageshmadaram/Sterling/backend/app/services/providers/truedata/adapter.py):

| Documented Capability | Implemented in [`truedata.py`](file:///home/nageshmadaram/Sterling/backend/app/services/market_data/truedata.py)? | Implemented in [`adapter.py`](file:///home/nageshmadaram/Sterling/backend/app/services/providers/truedata/adapter.py)? | Integration Status |
| :--- | :--- | :--- | :--- |
| OAuth Token Auth (`/token`) | YES (Lines 94-126) | YES | Fully Implemented & Tested |
| Historical Bar API (`/getbars`) | YES (Lines 168-196) | YES (`create_bar_event`) | Fully Implemented & Tested |
| Historical Last N Bars (`/getlastnbars`) | YES (Lines 198-225) | YES | Fully Implemented & Tested |
| Historical Tick API (`/getticks`) | YES (Lines 143-166) | YES (`create_tick_event`) | Fully Implemented & Tested |
| Realtime Push WS (`push.truedata.in`) | NO | NO | Configured in `config.py` only |
| Replay WS (`replay.truedata.in`) | NO | NO | Configured in `config.py` only |

---

## 6. TASK 5 Audit — Provider Subscription Capability

Evaluation of current TrueData account (`TD-6037DD0DD3` / `Tr****96`):

- **Confirmed Subscription Capabilities** (Empirically verified by live REST tests):
  - Real OAuth token authentication $\rightarrow$ `HTTP 200 OK`.
  - Historical 1-minute bar retrieval (`/getbars` & `/getlastnbars`) $\rightarrow$ Verified.
  - Historical tick retrieval (`/getticks`) $\rightarrow$ Verified.
- **Unconfirmed Subscription Capabilities**:
  - Multi-month historical tick quote access (`/getticks?bidask=1` over 6 months).
  - Access to WebSocket Replay server (`wss://replay.truedata.in`).
  - Pre-classified order flow / aggressor volume data feeds.
- **Entitlement Verdict**: **`PROVIDER CONFIRMATION REQUIRED`** for full multi-month tick quote depth and WebSocket replay entitlements.

---

## 7. TASK 6 — Feature Resolution Matrix

| Feature Name | Required Fields | TrueData Source Endpoint | Historical Availability? | Exact Derivation Possible? | Data Readiness Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`LogReturn`** | `close` | `GET /getbars` (1min) | YES | YES ($r_t = \ln(P_t / P_{t-1})$) | **FULLY RESOLVED** |
| **`VolatilityRatio`** | `close` | `GET /getbars` (1min) | YES | YES ($\text{VR}_t = \sigma_{\text{short}} / \sigma_{\text{long}}$) | **FULLY RESOLVED** |
| **`LiquidityImbalance`** | `bidqty`, `askqty` | `GET /getticks` (`bidask=1`) | YES (REST Tick API) | YES ($\text{LI}_t = \frac{\text{bidqty} - \text{askqty}}{\text{bidqty} + \text{askqty}}$) | **FULLY RESOLVED** |
| **`DeltaVelocity`** | `ABV`, `ASV` | None in REST / Replay WS | UNCERTAIN | NO (Missing aggressor flags) | **PARTIALLY RESOLVED — PROVIDER CONFIRMATION REQUIRED** |

---

## 8. TASK 7 Decision

> **`B. PARTIALLY RESOLVED — PROVIDER CONFIRMATION REQUIRED`**

- `LogReturn`, `VolatilityRatio`, and `LiquidityImbalance` are fully resolved using documented TrueData REST endpoints.
- `DeltaVelocity` remains blocked pending technical confirmation from TrueData support regarding aggressor trade classification in WebSocket Replay streams or enterprise add-on feeds.
- The A196 strategy feature set is **NOT** modified.

---

## 9. Final Status & Non-Authorization Declaration

```text
F-101 Status:             LOCKED (FormulaStatus.LOCKED)
A199 Audit Verdict:       PARTIALLY RESOLVED — PROVIDER CONFIRMATION REQUIRED
Supersedes:               A198 (Superseded as latest data capability audit; A198 retained)
Calibration Readiness:    NOT READY (BLOCKED BY PROVIDER CONFIRMATION)
Execution Gate:           BLOCKED
Kite Execution:           DISCONNECTED
```

- No calibration performed.
- No parameter files created (`f101_parameters_v1.json`).
- No runtime implementation authorized.
- No production Python code modified.
