# Sterling — Multi-Market Algo Trading Platform

A modular, broker-agnostic trading platform spanning two markets:

- **Crypto** (Delta Exchange India primary; Binance/Deribit/OKX adapters) —
  futures + options, VCP (Volume Concentration Profile) patterns + multi-
  timeframe momentum confluence, backtest-validated "edge" signals.
- **Indian equities & derivatives** (Zerodha Kite Connect, multi-tenant —
  each user's own encrypted credentials) — an auto-scan/auto-execute engine
  plus a full manual trading terminal (order window, positions, GTT, funds).

Brokers, markets, strategies, and risk rules are plug-and-play (see
[ARCHITECTURE.md](ARCHITECTURE.md)); every order — auto or manual, crypto or
Kite — funnels through one `OrderRouter` with paper/shadow/live modes and a
fail-closed safety pipeline, under a hard zero-regression discipline.

## Documentation

| Doc | What |
|---

## Claude Code Setup (Recommended)

This project is fully optimized for [Claude Code](https://claude.ai/code) / Claude Desktop App.

After cloning the repository, run **one command**:

    ./scripts/setup-claude.sh
    # or
    make setup-claude

This automatically sets up:

- `code-review-graph` (knowledge graph for massive token savings)
- Preferred CLI tools (`rg`, `fd`, `ast-grep`, `jq`, `yq`, `gh`)
- 100+ useful skills (superpowers, frontend-design, claude-mem, ui-ux-pro-max, etc.)
- Optimized `CLAUDE.md` with graph-first rules + critical invariants
- Global MCP registration
- Skill linking into `~/.claude/skills`

### After running the setup

1. Fully restart the **Claude Desktop App**
2. Open this project (Sterling)
3. Start a **new session**

### What Claude will follow

- Always uses `code-review-graph` tools **before** Grep/Read
- Protects critical trading invariants (CircuitBreaker, CorrelationTracker, CalibrationService, no lookahead)
- Uses skills selectively (1–3 max per task) for better token efficiency
- Prefers modern CLI tools (`rg`, `fd`, `sg`, etc.)

### Manual alternatives

    # Only install skills
    bash install-skills.sh

    # Verify setup
    bash claude-verify.sh

---
|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layered design, module map, design rules |
| [BROKERS.md](BROKERS.md) | Adding/replacing exchanges (the adapter contract + registry) |
| [MARKETS.md](MARKETS.md) | Supported markets + how to add one |
| [STRATEGIES.md](STRATEGIES.md) | Writing broker/market-agnostic strategies |
| [docs/AGENTS.md](docs/AGENTS.md) | Agents, event bus, orchestrator (trading agents) |
| [EXECUTION.md](EXECUTION.md) | Signal → order flow (the OrderRouter pipeline) |
| [RISK_MANAGEMENT.md](RISK_MANAGEMENT.md) | Safety pipeline + RiskEngine |
| [OBSERVABILITY.md](OBSERVABILITY.md) | JSON logging, correlation ids, metrics |
| [SECURITY.md](SECURITY.md) | Secrets, audit, HTTP hardening |
| [CONFIGURATION.md](CONFIGURATION.md) | Settings, registry, credentials |
| [TESTING.md](TESTING.md) | Test types + the fast zero-regression diff workflow |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Local + Docker |
| [MIGRATION.md](MIGRATION.md) | The phased hardening program (status + rollback) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Standards, workflow, where things go |

> Quick start: `make setup && make verify && make backend`. Performance/backtest
> reports live in [`docs/reports/`](docs/reports/).

---

## Architecture

```
Signal Generation → Track Selection → Orchestrator → OrderRouter → Exchange
(VCP / trend_following)  (highest score wins)  (paper/shadow/live)
```

> **Note:** the trees below cover the crypto/directional core this README was
> originally written around. The platform has since grown a second major
> pillar — **Zerodha Kite Connect** (Indian equities/derivatives, fully
> multi-tenant) — plus several more engines. See the module map in
> [ARCHITECTURE.md](ARCHITECTURE.md) and the current engine list in
> [STRATEGIES.md](STRATEGIES.md) for the complete picture; this section calls
> out the highlights.

### Backend (FastAPI + Python 3.12)

```
backend/
├── main.py                         App factory, lifespan (app.state singletons), 31 routers
├── app/
│   ├── domain/                      Signal/TradeEvent contracts, Protocols (no I/O)
│   ├── bus/                         EventBus — in-process async pub/sub
│   ├── agents/                      BrokerAgent/StrategyAgent/ExecutionAgent/RiskAgent/PNLAgent/Orchestrator
│   ├── api/v1/endpoints/            33 route files — see Key Endpoints below
│   ├── engines/                     15 packages — see STRATEGIES.md for the full list:
│   │   ├── sterling_engine/          Crypto scalper: MA-crossover, mean-reversion, breakout, price-action, SMC
│   │   ├── sterling_kite_engine/     Zerodha/Indian equities + derivatives engine
│   │   ├── directional/              Multi-track regime/signal/setup/sizing/execution pipeline ("Grok")
│   │   │   └── tracks/                vcp_track.py, trend_following, mean_reversion
│   │   ├── derivatives/ (+ derivatives_native/)  Greeks-aware strike/expiry/leverage selector
│   │   ├── edge/                      Backtest-validated 4h signal generator
│   │   ├── sterling_v2/               Track-system redesign (validated ma_crossover×3 @4h stack)
│   │   ├── hybrid_vcp/                VCP live-feed executor
│   │   ├── analytics/                 Walk-forward, sensitivity, correlation, CPCV, Monte Carlo (pure fns)
│   │   ├── risk/                      Drawdown circuit breaker, greeks budget, slippage, microstructure veto
│   │   └── indicators/, ml/, backtest/, arbitration/, common/
│   ├── services/
│   │   ├── execution/order_router.py  paper/shadow/live dispatch, fail-closed safety pipeline
│   │   ├── exchanges/                 adapters/ (delta_india, binance, deribit, okx, zerodha shim)
│   │   │   └── kite/                   Kite Connect v3 client — auth, instruments, ticker, multi-tenant accounts
│   │   ├── kite_engine/                Kite trading logic on top of kite/: scanner, sizing, strikes, protective stops
│   │   ├── calibration.py, snapshot_cache.py (45s TTL), db.py (SQLite)
│   ├── persistence/                   SQLAlchemy ORM mirror (dual-write, Migration Phase 5)
│   └── schemas/                       Pydantic boundary models
└── config/
    ├── registry.json                  Broker/market registry (source of truth for adapters)
    └── tracks.yaml                    Per-(instrument, profile) → [track_list]
```

### Frontend (React 19 + TypeScript + Vite)

```
frontend/src/
├── pages/
│   ├── SimpleTerminal.tsx            The production shell — KITE / CRYPTO top-tab switch
│   │                                   CRYPTO_TABS: sterlingEngine / grok / sterling_v2 / positions / backtest / paper
│   └── Terminal.tsx, Dashboard.tsx   Pro / legacy tabbed layouts
├── components/
│   ├── kite/                         Zerodha panes: ConnectPane, OrderWindow, PositionsPane, OrdersPane,
│   │   └── mac/                        GttPane, FundsPane, SterlingKiteEnginePane — mac/ = gated Mac-style
│   │                                    motion layer (useMacKite, lazy framer-motion, off by default)
│   ├── sterling_engine/, sterling_v2/  Per-engine tab components
│   ├── derivatives/                  Shared CommonFuturesCandidatesTable / CommonOptionsCandidatesTable /
│   │                                   CommonSourceBadge — parameterized per engine (Sterling vs Grok)
│   ├── BacktestPanel.tsx, MassiveBacktestDashboard.tsx, WalkForwardPanel.tsx, SensitivityPanel.tsx
│   └── PositionsPanel.tsx, PositionHeatmap.tsx, PaperLiveToggle.tsx, TradingTicket.tsx
├── hooks/                            ~55 domain hooks — useSignalFeed (SSE, append-only), useKiteLiveTicks
│                                       (WS singleton), useBacktest, useCorrelation, useDrawdownBreaker, useMacKite
├── store/                            Zustand: useStore (theme/appMode/underlying), useOrderWindowStore,
│                                       useKiteSettings, useKiteNotifications
└── styles/                           terminal.css (Bloomberg-dark tokens), kiteUI.tsx (Kite-parity light
                                        tokens), macMotion.ts (motion-layer springs)
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

> **⚠️ Diagram shows the conceptual shape, not the current call graph.**
> `app/engines/directional/orchestrator.py`'s `run_once()`/`preview()` are
> neutral **stubs** left from the 2026-05-24 strategy reset (they return
> `IDLE`/`NEUTRAL` with `reason: "strategy removed in reset"`). The live
> `/api/v1/directional/signals` endpoint does NOT call them — it computes
> signals via `_compute_signal_item()` in `app/api/v1/endpoints/directional.py`,
> which uses the since-reimplemented `regime_engine.py` (real ADX + SMA-slope)
> and `signal_engine.py` (real regime-following score), but several downstream
> pieces implied by this diagram — `track_scoring.py`, `track_selector.py`,
> `sizing_engine.py`, `execution_engine.py`, `structure_selector.py`,
> `policy_engine.py` — are still strategy-reset stubs returning neutral/no-op
> results. Treat this section as a design sketch pending a dedicated pass to
> re-diagram the actual `_compute_signal_item` call path.

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

## Signal status (frontend)

There is no `SignalsTable.tsx` / ALL-LATEST-LEGACY pill row anymore — it was
replaced by a status taxonomy in `hooks/useSignals.ts`:

- **Sterling** engine signals carry `entry_ok` directly.
- **Directional/"Grok"** signals have no `entry_ok` — status is derived from
  `state` (`TradeState`) via `getSignalStatus()`: `ENTRY_ARMED_*` → **ready**
  (armed, actionable now), `*_SETUP_ACTIVE` → **pending** (forming, not yet
  armed), `IDLE`/`NONE` → **watching**.

`GrokTab`'s signal counts and `GrokSignalPane`'s rows both filter through the
shared `visibleGrokSignals()`/`getSignalStatus()` helpers so they can't drift
out of sync with each other. NIFTY/BANKNIFTY are currently excluded from the
Grok tab. The `track`/`strategy` fields described above (which track won,
track-system vs. legacy path) are still exposed by `/signals` and still
rendered — just via `GrokSignalPane.tsx`/`SignalPane.tsx`/`sterling_v2/V2SignalsPane.tsx`
rather than a single shared table component.

---

## Key Endpoints

There are 33 route files under `app/api/v1/endpoints/`, all mounted under
`/api/v1` except `health`. Full detail lives in each router's source; the
groups below are the ones you'll touch most.

### Crypto trading & signals (original core)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/v1/trading/algo-router-mode` | Router dispatch mode (paper/shadow/live) |
| GET/POST | `/api/v1/trading/algo-mode` | Master auto-trading on/off |
| GET/POST | `/api/v1/trading/vcp-mode` | VCP feed status / enable-disable |
| POST | `/api/v1/trading/place-order` | Manual order |
| POST | `/api/v1/trading/test-credentials` | Verify exchange keys |
| GET | `/api/v1/directional/signals` | Live signal table (all instruments, fresh cache) |
| GET | `/api/v1/directional/snapshot?underlying=BTC` | Full state: spot + regime + signal + exec |
| GET | `/api/v1/directional/stream/{underlying}` | SSE live stream |

### Zerodha Kite (Indian equities/derivatives, multi-tenant)

| Router file | Prefix | Description |
|---|---|---|
| `kite.py` | `/kite` | Account CRUD, session/auth, orders, positions, GTT, funds, instruments (largest router, ~68 routes) |
| `kite_engine.py` | `/kite/engine` | Auto-scan/auto-execute engine control (PAPER/LIVE, MANUAL/AUTO toggles) |
| `kite_telegram.py` | `/kite/telegram` | Telegram alert integration |

### Derivatives, engines & analytics

| Router file | Prefix | Description |
|---|---|---|
| `derivatives.py` | `/derivatives` | Greeks-aware candidate selection, ~21 routes |
| `sterling_engine.py` | `/sterling-engine` | Crypto scalper control/status |
| `sterling_v2.py` | — | Track-system engine |
| `backtest.py`, `vectorized_backtest.py` | `/backtest` | Bar-by-bar and vectorized-sweep backtests |
| `wfo.py` | — | Walk-forward optimization |
| `analytics.py`, `analytics_baseline.py` | `/analytics` | Correlation, sensitivity, performance reports |
| `risk_dashboard.py` | — | Circuit breaker / greeks budget status |

### Shared infrastructure

`positions.py`, `paper.py`, `account.py`, `exchanges.py`, `alerts.py`,
`webhooks.py`, `options.py`, `stats.py`, `session.py`, `candles.py`,
`ohlcv.py`, `instruments.py`, `config.py`, `stream.py` (SSE, mounted at
`/api/v1/stream`).

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

## Historical research notes (superseded)

The two write-ups below (Overfitting Diagnosis 2026-05-25, Institutional WFO
2026-05-31) were written about the **Triple-SuperTrend engine and its
`ScalpingTab.tsx`/`ScalpingConfigPanel` UI**. Both were removed in the
2026-06-03 Sterling-only consolidation (`app/engines/triple_supertrend/` and
`app/engines/scalping/` are now empty dirs; there is no `ScalpingTab.tsx` in
the frontend). The underlying research (exit-stack overfitting, WFO/CPCV
timeframe filtering) still informed the surviving `sterling_engine`/`edge`
config choices (e.g. 4h as the timeframe where durable edge lives — see
[STRATEGIES.md](STRATEGIES.md)), but the specific config knobs and UI
described here (`min_confirm`, `ScalpingConfigPanel`, the Scalping Terminal
header) no longer exist. Full historical detail: `backend/docs/OVERFITTING_DIAGNOSIS_20260525.md`
and [`docs/reports/SCALPING_PERFORMANCE_REPORT.md`](docs/reports/SCALPING_PERFORMANCE_REPORT.md).

**Still accurate today** (from the "Known Issues Fixed" list this section
used to end with):
- `PaperLiveToggle` renders via `createPortal` to `document.body` to escape
  the `.term-root` z-index trap (see `reference_modal_stacking_term_root`
  pattern) — LIVE→SHADOW correctly sets `is_paper: true` directly.
- `algo_router_mode` persists across restarts via `db.set_config`.
- `/api/v1/directional/signals` exposes `track` + `strategy` fields showing
  which track won and whether the track system or legacy path was used.

---

## Frontend Build

```bash
cd frontend && npm run build   # TypeScript + Vite, clean build
```
### Dynamic skills

Skills are available globally but loaded **on demand** (1–3 per task).
Routing is defined in `CLAUDE.md`. Architecture analysis uses TrueCourse;
daily code exploration uses code-review-graph.

### TrueCourse options (during setup)

When you run `./scripts/setup-claude.sh`, TrueCourse will ask:

1. **Analysis mode**
   - **1 Deterministic** (default) — fast, no LLM token cost for rules  
   - **2 Full LLM** — deeper; can use a large number of tokens; needs Claude quota  
   - **3 Skip** — no analysis now  

2. **Pre-commit hook [y/N]** (default **N**)
   - **Y** — TrueCourse on every commit: stricter, slower commits; usually **no** large LLM token cost (diff/deterministic). Tokens rise only if LLM rules are enabled on the hook.  
   - **N** — fast commits; run `truecourse` manually when needed (recommended for most users).

### Graphify (optional, global)

During `./scripts/setup-claude.sh` you may also be asked about **Graphify**:

- **Install globally** — CLI `graphify` (PyPI: `graphifyy`) + Claude skill for all projects  
- **Extract graph** — builds `graphify-out/` for this repo (can take a while)  
- **Git hooks** — optional; default **N** if you already use code-review-graph hooks  

**Capability split:** code-review-graph = daily impact/MCP · TrueCourse = architecture violations · Graphify = knowledge graph (code + docs).

### AI context discipline

See `CLAUDE.md` and `docs/ai/CONTEXT.md` for tool ownership, plan-first workflow, MCP limits, and token-saving habits. Prefer graph tools over wide search; small branches; new session when context drifts.
