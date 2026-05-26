# Sterling v4 — Hybrid VCP-Momentum Scalper

Live crypto futures + options trading platform. Auto-trades based on VCP (Volume Concentration Profile) patterns + multi-timeframe momentum confluence. Supports paper simulation, shadow audit, and live execution via Delta Exchange India.

---

## Architecture

```
Signal Generation → Track Selection → Orchestrator → OrderRouter → Exchange
(VCP / trend_following)  (highest score wins)  (paper/shadow/live)
```

### Backend (FastAPI + Python 3.12)

```
backend/
├── main.py                         App factory, lifespan, VCP feeds, auto-trading
├── app/
│   ├── api/v1/endpoints/
│   │   ├── directional.py           Signals, snapshot, preview, run-once, SSE stream
│   │   ├── trading.py               algo-mode, algo-router-mode, place-order, test-credentials
│   │   ├── positions.py            CRUD, enter, monitor, close, summary, P&L
│   │   ├── exchanges.py             Exchange accounts, credentials, data source switch
│   │   └── account.py               Balances, positions, orders, fills
│   ├── engines/
│   │   ├── directional/
│   │   │   ├── orchestrator.py      Runs track registry, picks winning track
│   │   │   ├── signal_engine.py     Multi-TF indicator pipeline → SignalResult
│   │   │   ├── signal_features.py   assemble_signal_score + regime-aware weights
│   │   │   ├── regime_engine.py     4H macro filter (EMA, ATR percentile, ADX)
│   │   │   ├── setup_engine.py      State machine transitions
│   │   │   ├── structure_selector   IVR routing + leverage by score + signal_strength
│   │   │   └── tracks/
│   │   │       ├── vcp_track.py     Volume concentration profile patterns
│   │   │       ├── trend_following  Classic momentum (ST + RSI + squeeze + vol)
│   │   │       └── mean_reversion   Fade-extremes specialist
│   │   └── hybrid_vcp/
│   │       ├── executor.py           VCP live feed executor → order submission
│   │       └── feeder.py            VCP feed state machine
│   └── services/
│       ├── execution/
│       │   └── order_router.py      paper/shadow/live dispatch
│       ├── snapshot_cache.py         45s TTL cache
│       └── db.py                     SQLite (positions, alerts, exchanges)
└── config/
    └── tracks.yaml                   Per-(instrument, profile) → [track_list]
```

### Frontend (React 19 + TypeScript + Vite)

```
frontend/src/
├── components/
│   ├── SignalsTable.tsx              Signal feed with strategy filter (LATEST/LEGACY)
│   ├── LiveControlPanel.tsx          Kill switch, algo-mode, algo-router-mode selector
│   ├── PaperLiveToggle.tsx           3-way PAPER / SHADOW / LIVE toggle
│   ├── V4AnalyticsDashboard.tsx       Live P&L + realized PnL + mode badge
│   ├── ArrowAlert.tsx                SSE overlay alert cards
│   └── ...
├── hooks/
│   ├── useSignalFeed.ts              Append-only signal feed, SSE-driven
│   ├── useSignals.ts                 Polling REST /signals endpoint
│   ├── useExchanges.ts               Exchange CRUD + test connection
│   └── useLivePnl.ts                 Live unrealized + realized P&L
└── pages/
    └── Dashboard.tsx                 8 tabs: Analysis / Signals / Positions / etc.
```

---

## Trading Modes

| Mode    | Exchange call | Paper position | Use |
|---------|--------------|-----------------|-----|
| `paper`  | NO           | YES             | Simulation, backtesting |
| `shadow` | YES          | YES             | Live audit — compare fills |
| `live`   | YES          | NO              | Production |

**algo_mode** (master switch) — enables/disables auto-trading for both VCP feeds and directional engine.  
**algo_router_mode** (paper/shadow/live) — controls execution dispatch for all auto-orders.

Auto-order fires only when `signal_strength == "STRONG"` (≥75% confluence score).

---

## Signal Generation Pipeline

```
每条K线进来:
  DirectionalOrchestrator.run_once()
    → regime_engine.compute_regime()    4H macro (EMA, ADX, ATR percentile)
    → track.compute() × N              VCP + trend_following + mean_reversion
    → best_track = highest score       Winner takes direction
    → evaluate_setup()                State machine
    → compute_signal_score()           assemble_signal_score (0-20 scale)
      STRONG  ≥ 15 (≥75%)
      SIGNAL  ≥ 7  (≥35%)
      NONE    < 35%
    → OrderRouter.submit()             Only if algo_mode=true + STRONG
```

> **Deep Dive**: See the [Scalping Strategy Logic](backend/docs/SCALPING_LOGIC.md) for detailed logic, conditions, and code snippets behind the Price Action, SMC, and MA Crossover scalping engines.

## Track System (`config/tracks.yaml`)

Each instrument+profile is routed to an ordered track list:

| Instrument | Profile | Tracks |
|------------|---------|--------|
| BTC | scalping_5m/15m, intraday_1h/4h | `[vcp, trend_following]` |
| ETH | scalping_5m/15m/30m, intraday_1h | `[vcp, trend_following]` |
| BTC | scalping_30m | `[vcp, mean_reversion]` |

VCP runs first, sets direction; trend_following scores the move. Orchestrator picks whichever score is higher.

---

## Signal Table — Strategy Filter

The signal table (frontend) shows a pill-row of strategy filters:

| Button | Color | Shows |
|--------|-------|-------|
| ALL | gray | All signals |
| LATEST | amber | A track (VCP/trend_following/mean_reversion) produced a directional signal |
| LEGACY | purple | No track won — old Sterling `compute_signal` fallback used |

- **LATEST**: `strategy="latest"` — track system won. `track` field shows which track (VCP / trend_following / mean_reversion).
- **LEGACY**: `strategy="legacy"` — no track had a directional signal; old Sterling `compute_signal` path used as fallback.

Counts update every 5s. Filter is independent of mode/status filters.

---

## Key Endpoints

### Trading

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/trading/algo-router-mode` | Current mode (paper/shadow/live) |
| POST | `/api/v1/trading/algo-router-mode` | Switch mode |
| GET | `/api/v1/trading/algo-mode` | algo_mode on/off |
| POST | `/api/v1/trading/algo-mode` | Toggle algo_mode |
| POST | `/api/v1/trading/place-order` | Manual order |
| POST | `/api/v1/trading/test-credentials` | Verify exchange keys |

### Signals

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/directional/signals` | Live signal table (all instruments, fresh cache) |
| GET | `/api/v1/directional/snapshot?underlying=BTC` | Full state: spot + regime + signal + exec |
| GET | `/api/v1/directional/stream/{underlying}` | SSE live stream |

### VCP Feeds

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/trading/vcp-mode` | VCP feed status, active profiles |
| POST | `/api/v1/trading/vcp-mode` | Enable/disable VCP feeds |

---

## Quick Start

```bash
# Backend
cd backend && source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm run dev   # http://localhost:5173
```

## Auto-Trading Requirements

Both must be enabled for full auto-trading:
1. `algo_mode = true` — master on/off switch
2. `algo_router_mode != paper` — paper/shadow/live determines execution

VCP feeds require `vcp_mode = true` in addition to `algo_mode`.

Signal gate: `signal_strength == "STRONG"` required before any order places.

---

## Overfitting Diagnosis (2026-05-25)

The ensemble backtest showing PF < 1.0 across all modes was confirmed as **exit logic overfitting, not signal failure**. [Full diagnosis →](backend/docs/OVERFITTING_DIAGNOSIS_20260525.md)

**Root cause:** The exit stack (fixed TP, partials, breakeven triggers) systematically cuts winners short:
- Raw Triple ST signal on 4H with ST3 trailing only: **PF = 1.064–1.282** (valid edge)
- Same signal with fixed TP + BE + partials: **PF = 0.900** (edge destroyed)
- Breakeven alone costs −12% PF (0.900 → 0.796)

**Confirmed fixes (priority order):**

| Fix | Change | Expected Impact |
|-----|--------|-----------------|
| 1. Remove fixed TP | `partials = ()`, trail-only exits | PF 0.900 → 1.064+ |
| 2. Disable breakeven | `be_trigger_r = 999` or remove logic | PF 0.796 → 0.900 |
| 3. Wider stops | `sl_mult = 2.5` (from 1.5) | Higher win rate (38% vs 34%) |
| 4. Relax consensus | `min_confirm = 2` (from 3/3) | More signals, PF 1.064 → 1.124 |
| 5. 1H has no edge | 1H raw PF = 0.788–0.916 — disable | Avoid losing regime |

**Recommended production config:**
```python
min_confirm = 2      # 2/3 consensus (more signals, better PF)
sl_mult = 2.5        # Wider stops
be_trigger_r = 999   # DISABLED
partials = ()        # NO partials (let winners run)
trail_source = "ST3" # Keep ST3 trailing only
```

## Known Issues Fixed

- **PaperLiveToggle shadow switching**: SHADOW button in LIVE mode was opening a confirmation modal that did the wrong thing. Fixed — LIVE→SHADOW now directly sets `is_paper: true`.
- **Mode persistence**: `algo_router_mode` now stored in SQLite via `set_config`, survives restarts.
- **Signal strategy exposure**: Backend now exposes `track` + `strategy` fields in `/signals` — shows which strategy won (VCP/trend_following/mean_reversion) and whether track system or legacy path was used.

---

## Frontend Build

```bash
cd frontend && npm run build   # TypeScript + Vite, clean build
```