# A200: TrueData DeltaVelocity Provider Confirmation Specification

---

> [!WARNING]
> **AUDIT STATUS: PROVIDER CONFIRMATION SPECIFICATION ONLY**
> - **Formula ID**: `F-101` (`Feature normalization / feature score`)
> - **Formula Registry Status**: `LOCKED` (`FormulaStatus.LOCKED`)
> - **Execution Gate**: `BLOCKED`
> - **Implementation Status**: **NOT AUTHORIZED**
> - **Feature Status**: `DeltaVelocity` = **UNRESOLVED**
> - **Purpose**: Defines the exact data requirements, TrueData endpoint field audit, provider inquiry manifest, and resolution decision tree required to resolve the remaining `DeltaVelocity` order-flow dependency. Does **NOT** implement `F-101`, calibrate parameters, unlock formulas, or modify production Python code.

---

## 1. Executive Status

```text
Feature ID:              V-FTR-001 (DeltaVelocity)
Current Dependency:      Aggressor Buy Volume (ABV_t) & Aggressor Sell Volume (ASV_t)
Audited Feed Status:     UNRESOLVED (Requires Provider Confirmation)
Formula Registry Gate:   LOCKED (FormulaStatus.LOCKED)
Execution Gate:          BLOCKED
```

This specification defines the exact evidence required from TrueData support to resolve the `DeltaVelocity` data dependency without violating the Master Mathematical Specification or inventing uncanonical trade classification heuristics.

---

## 2. TASK 1 — Exact Canonical Data Requirement

Per Section 7-9 of [`Exact Mathematical Operator Specification.md`](file:///home/nageshmadaram/Sterling/adaptive-edge/Exact%20Mathematical%20Operator%20Specification.md#L170-L248):

1. **Trade Classification Inputs**:
   - Trade Price $T_t$, Trade Quantity $q_t$, Valid Bid Price $B_t$, Valid Ask Price $A_t$.
2. **Aggressor Classification Rules**:
   $$\text{BuyClass}_t = \mathbb{I}(T_t \ge A_t), \quad \text{SellClass}_t = \mathbb{I}(T_t \le B_t), \quad \text{UnknownClass}_t = 1 - (\text{BuyClass}_t + \text{SellClass}_t)$$
3. **Aggressor Volume Equations**:
   $$\text{ABV}_t = q_t \cdot \text{BuyClass}_t, \quad \text{ASV}_t = q_t \cdot \text{SellClass}_t$$
4. **Order Flow Delta ($\delta_t$) & Cumulative Delta ($\text{CD}_t$)**:
   $$\delta_t = \text{ABV}_t - \text{ASV}_t, \quad \Delta_W(t) = \sum_{j \in (t-W, t]} \delta_j$$
5. **Delta Velocity ($\delta v_t$)**:
   $$\delta v_t = \frac{\Delta_W(t) - \Delta_W(t - \Delta W)}{\Delta W}$$

---

## 3. TASK 2 — TrueData Source Field Audit Matrix

Audit of documented TrueData API feeds against order-flow fields:

| Field Name | `GET /getbars` | `GET /getticks` | Replay WebSocket (`replay.truedata.in`) | Realtime Push WebSocket (`push.truedata.in`) | TCP API (Port 8082) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `timestamp` | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED |
| `trade price` | EXPLICITLY PROVIDED (`close`) | EXPLICITLY PROVIDED (`ltp`) | EXPLICITLY PROVIDED (`ltp`) | EXPLICITLY PROVIDED (`ltp`) | EXPLICITLY PROVIDED (`ltp`) |
| `trade quantity` | EXPLICITLY PROVIDED (`volume`) | EXPLICITLY PROVIDED (`volume`) | EXPLICITLY PROVIDED (`volume`) | EXPLICITLY PROVIDED (`volume`) | EXPLICITLY PROVIDED (`volume`) |
| `bid price` | NOT PROVIDED | EXPLICITLY PROVIDED (`bid`) | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED |
| `ask price` | NOT PROVIDED | EXPLICITLY PROVIDED (`ask`) | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED |
| `bid quantity` | NOT PROVIDED | EXPLICITLY PROVIDED (`bidqty`) | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED |
| `ask quantity` | NOT PROVIDED | EXPLICITLY PROVIDED (`askqty`) | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED | EXPLICITLY PROVIDED |
| `aggressor side` | NOT PROVIDED | NOT PROVIDED | PROVIDER CONFIRMATION REQUIRED | NOT PROVIDED | NOT PROVIDED |
| `buy/sell classification` | NOT PROVIDED | NOT PROVIDED | PROVIDER CONFIRMATION REQUIRED | NOT PROVIDED | NOT PROVIDED |
| `order-flow delta` | NOT PROVIDED | NOT PROVIDED | PROVIDER CONFIRMATION REQUIRED | NOT PROVIDED | NOT PROVIDED |
| `cumulative delta` | NOT PROVIDED | NOT PROVIDED | PROVIDER CONFIRMATION REQUIRED | NOT PROVIDED | NOT PROVIDED |

---

## 4. TASK 3 — Prohibition of Unauthorized Trade Classification Proxies

> [!CAUTION]
> **STRICT PROHIBITION ON HEURISTIC TRADE CLASSIFICATION**
> 
> Section 7 of `Exact Mathematical Operator Specification.md` mandates:
> *"The system must not force unknown trades into buy or sell classifications."*
> 
> The following heuristics constitute **UNAUTHORIZED PROXIES** and are **STRICTLY FORBIDDEN**:
> 1. **Uptick / Downtick Classification**: Inferring buy/sell direction from price change ($\Delta P_t = P_t - P_{t-1}$).
> 2. **Lee-Ready Quote Rule**: Classifying trades between bid and ask based on price proximity without explicit quote synchronization.
> 3. **Midpoint Distance Heuristic**: Classifying trades based on distance to midpoint $M_t$.
> 4. **Bid/Ask Volume Ratio Inference**: Estimating buy/sell volume from bid/ask depth ratios.
> 
> If TrueData does not explicitly provide aggressor side classification or synchronized tick-level trade+quote events, `DeltaVelocity` is classified as **UNAVAILABLE** rather than using a proxy heuristic.

---

## 5. TASK 4 — TrueData Replay WebSocket Specification Audit

Audit of documented TrueData WebSocket Replay feed (`wss://replay.truedata.in`):

- **Emitted Messages**: Chronological stream of market trade events and top-of-book quote updates.
- **Payload Fields**: `symbol`, `timestamp`, `ltp`, `volume`, `oi`, `bid`, `bidqty`, `ask`, `askqty`.
- **Trade & Quote Distinction**: Trades and quotes arrive as discrete WebSocket JSON frames differentiated by message type (`trade` vs `quote`).
- **Trade-Time Bid/Ask State**: Quote frames precede trade frames, but whether quote states are guaranteed to be microsecond-synchronized at trade time is **UNKNOWN / PROVIDER CONFIRMATION REQUIRED**.
- **Explicit Aggressor Direction**: NOT documented in standard V2.6 REST or TCP docs.
- **Historical Date Range**: Arbitrary historical trading dates supported via playback request message.
- **Replay Determinism**: Deterministic if tick messages arrive in identical sequence and epoch timestamp order across connections.
- **Canonical Bridge Feasibility**: Feasible to wrap streamed replay frames into `CanonicalMarketEvent` structures if trade-quote synchronization is verified.

---

## 6. TASK 5 — TrueData Support Provider Confirmation Inquiry

The following formal technical query must be submitted to TrueData API Support:

```text
================================================================================
FORMAL TRUEDATA API TECHNICAL INQUIRY — ORDER FLOW & REPLAY FEED CAPABILITIES
================================================================================

Target Account ID: TD-6037DD0DD3
Subscriber ID:     Tr****96

1. Explicit Aggressor Classification:
   Does TrueData offer an API endpoint, WebSocket stream field, or enterprise add-on
   feed that provides explicit aggressor-side trade classification (Buyer-Initiated
   vs Seller-Initiated / Aggressor Buy Volume vs Aggressor Sell Volume)?

2. Synchronized Trade & Quote Replay:
   In the WebSocket Replay stream (wss://replay.truedata.in), are tick trade events
   guaranteed to be microsecond-synchronized with the prevailing top-of-book Bid
   and Ask prices (B_t, A_t) at the exact moment of trade execution?

3. Order Flow Delta Fields:
   Does TrueData provide an official API field or endpoint for Order Flow Delta
   (ABV - ASV) or Cumulative Delta (CD) for NIFTY Index and Option contracts?

4. Subscription Entitlements:
   Is historical WebSocket Replay (wss://replay.truedata.in) enabled for our current
   account subscription (TD-6037DD0DD3)?

5. Replay Historical Depth:
   What maximum historical depth (calendar months or years) is supported for tick-by-tick
   replay queries on NIFTY option contracts?

6. Tick Trade Quantities:
   Does the WebSocket Replay stream report individual tick trade quantities (q_t) for
   every execution?

7. Deterministic Playback:
   Is WebSocket replay playback guaranteed to be 100% bitwise deterministic across
   repeated connections for identical historical date ranges?

8. Historical REST Tick Depth:
   What is the maximum supported historical date range for REST /getticks?bidask=1
   queries for index option contracts?
================================================================================
```

---

## 7. TASK 6 — Data Resolution Decision Tree

```text
                               ┌────────────────────────────────┐
                               │     TRUEDATA INQUIRY RESPONSE  │
                               └───────────────┬────────────────┘
                                               │
               ┌───────────────────────────────┼───────────────────────────────┐
               │                               │                               │
               ▼                               ▼                               ▼
       ┌───────────────┐               ┌───────────────┐               ┌───────────────┐
       │    CASE A     │               │    CASE B     │               │    CASE C     │
       │ Explicit ABV/ │               │ Synchronized  │               │ Trades/Quotes │
       │ ASV Provided  │               │ Trade + Quote │               │ Un-synchronized│
       └───────┬───────┘               └───────┬───────┘               └───────┬───────┘
               │                               │                               │
               ▼                               ▼                               ▼
     DeltaVelocity                     DeltaVelocity                   DeltaVelocity
     FULLY RESOLVED                    CONDITIONALLY DERIVABLE         UNRESOLVED
     (Proceed to                      (Requires Canonical             (Requires Strategy
      Calibration)                     Approval)                       Lead Decision)
```

- **CASE A (Explicit Aggressor Side / ABV / ASV Provided)**:
  - `DeltaVelocity` is **FULLY RESOLVED**. Proceed to A197 calibration protocol.
- **CASE B (Synchronized Trade + Quote Data Provided)**:
  - `DeltaVelocity` is **CONDITIONALLY DERIVABLE** using canonical operator $\text{BuyClass}_t = \mathbb{I}(T_t \ge A_t)$. Subject to formal Strategy Lead validation.
- **CASE C (Un-synchronized Trade + Quote Data)**:
  - `DeltaVelocity` remains **UNRESOLVED**. Cannot apply heuristic proxies.
- **CASE D (Neither Aggressor Side nor Synchronized Quotes Provided)**:
  - `DeltaVelocity` is declared **UNAVAILABLE from TrueData**. Requires Strategy Lead decision to modify proposed feature set.

---

## 8. TASK 7 — Required Acceptance Evidence

Before `A200` can be updated to **`RESOLVED`**, the repository must receive:
1. **Written Provider Confirmation**: Official written response from TrueData support answering the 8-part inquiry.
2. **Documented Endpoint Specification**: Exact endpoint URL, transport protocol, and JSON/binary field schema.
3. **Payload Sample Artifact**: Verified sample payload containing trade timestamp, price, quantity, and aggressor side or synchronized quote snapshot.
4. **Replay Determinism Proof**: Replay hash verification test proving 100% bitwise equality across double-pass replay connections.
5. **Canonical Mathematical Compatibility**: Formal verification that the provider feed satisfies Sections 7-9 of `Exact Mathematical Operator Specification.md`.

---

## 9. Final Status & Safety Declaration

```text
F-101 Status:             LOCKED (FormulaStatus.LOCKED)
A200 Audit Status:        PROVIDER CONFIRMATION SPECIFICATION ONLY
DeltaVelocity Status:     UNRESOLVED (Pending TrueData Technical Response)
Calibration Readiness:    NOT READY (BLOCKED BY A200 RESOLUTION)
Execution Gate:           BLOCKED
Kite Execution:           DISCONNECTED
```

- No production Python code modified.
- No calibration performed; zero parameter files created (`f101_parameters_v1.json`).
- No unauthorized trade classification proxies applied.
- `A196`, `A197`, `A198`, and `A199` remain completely preserved.
