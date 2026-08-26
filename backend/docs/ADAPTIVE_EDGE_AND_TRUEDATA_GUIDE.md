# Adaptive Edge & TrueData Operational Guide

## 1. Overview & Architecture

The Sterling platform features two distinct trading and research engines with strict separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STERLING PLATFORM                                 │
├──────────────────────────────────────┬──────────────────────────────────────┤
│       ADAPTIVE EDGE (RESEARCH)       │        KITE ENGINE (EXECUTION)       │
├──────────────────────────────────────┼──────────────────────────────────────┤
│ • Canonical A197 L2 Tick Replay      │ • 1H Spot & Premium SuperTrend (ST)  │
│ • Delta, CVD, POC, Volume Profile    │ • Value-Flow Navigator (AVWAP + OI)  │
│ • Canonical A126 Horizon State       │ • Dynamic Strike & Ladder Resolver   │
│   Machine (IMPULSE → INTRADAY)       │ • Liquid Contract & Spread Filtering │
│ • F-101..F-114 Locked Governance     │ • Live Broker Order Placement        │
│ • TrueData Port 8082 / Ticks Stream  │ • Kite REST API & WebSocket Feeds    │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

---

## 2. Market Data Source Selection

Under **Connect → TrueData**, users can dynamically configure the active market data source:
- **`TrueData`**: Primary data feed for tick-level order flow, volume profile, VWAP bands, and Adaptive Edge research tables.
- **`Zerodha Kite`**: Primary data feed for broker-quoted live option chain snapshots, SuperTrend indicators, and order execution.

The selection is persisted in the backend database under the config key `"market_data_source"` and accessible via:
- `GET /api/v1/truedata/settings`
- `POST /api/v1/truedata/settings`

---

## 3. Stock Options vs. Index Options Liquidity Gating

To eliminate the drag from illiquid monthly stock option contracts while maintaining low-latency execution for weekly index options:
1. **Spread Gating**: Stock option contracts with `(ask - bid) / mid > 3.5%` are automatically filtered out.
2. **Volume & Open Interest Floor**: Stock contracts with zero volume or open interest $< 500$ are excluded.
3. **Weekly Index Prioritization**: `NIFTY`, `BANKNIFTY`, `FINNIFTY`, and `SENSEX` continue to evaluate all tight-spread weekly contracts.

Implementation reference: [`filter_liquid_contracts`](file:///home/nageshmadaram/Sterling/backend/app/services/kite_engine/strikes.py).

---

## 4. Dynamic Horizon Protection Scaling

Initial stops, trailing offsets, and profit-lock levels scale dynamically as trade lifecycle transitions across horizons:

| Horizon Mode | Stop Multiplier | Trailing Stop Offset | Profit Lock Activation |
| :--- | :--- | :--- | :--- |
| **`MICRO` / `IMPULSE`** | $1.0\times$ Base Stop | $0.6\times$ ATR | $1.2\times$ ATR |
| **`SCALP` / `TACTICAL`** | $1.3\times$ Base Stop | $1.2\times$ ATR | $2.5\times$ ATR |
| **`INTRADAY_SWING`** | $1.8\times$ Base Stop | $2.0\times$ ATR | $4.0\times$ ATR |
| **`SESSION_TREND`** | $2.5\times$ Base Stop | $3.2\times$ ATR | $6.0\times$ ATR |

Implementation reference: [`get_horizon_protection_policy`](file:///home/nageshmadaram/Sterling/backend/app/engines/adaptive_edge/protection.py).

---

## 5. Mandatory Session Cutoff (14:45 IST)

- Normal intraday trading is cut off 45 minutes before market close (`SESSION_CLOSE - 45m` = `14:45 IST`).
- Active intraday positions are auto-flattened, and new entries or promotions are locked.
- Implementation reference: [`check_session_cutoff`](file:///home/nageshmadaram/Sterling/backend/app/engines/adaptive_edge/lifecycle_engine.py).

---

## 6. Real-Time Telegram & Audio Notifications

- **Telegram Lifecycle Alerts**: Formatted HTML alerts broadcast horizon promotions (`⚡ PROMOTED: MICRO ↗ SCALP`) and demotions (`🛡️ DEMOTED: INTRADAY ↘ SCALP`).
- **Web Audio Chimes**: Synthesized frequency ramps via the HTML5 Web Audio API in [`AdaptiveEdgePane.tsx`](file:///home/nageshmadaram/Sterling/frontend/src/components/kite/AdaptiveEdgePane.tsx) provide instant audio cues without external assets.

---

## 7. Verification & Testing

```bash
# Run full Adaptive Edge test suite (179 tests)
backend/.venv/bin/pytest backend/tests/engines/test_adaptive_edge* backend/tests/engines/adaptive_edge/

# Run complete backend test suite (2,684 tests)
backend/.venv/bin/pytest backend/tests/

# Run frontend test suite & build check
npm --prefix frontend test --run
npm --prefix frontend run build
```
