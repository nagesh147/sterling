# Sterling — Unified Crypto Options & Futures Platform (v3)

Paper-trading-first, unified engine for **crypto options (long/short) and futures (leveraged/unleveraged)**.  
Exchange adapters: **Deribit** (default) · **OKX** · **Delta Exchange** · **Binance** · **Zerodha Kite**.  
No live order routing. All execution is read-only evaluation + paper simulation.

> **v3 Unified Engine**: a single evaluation pipeline routes every signal to the optimal instrument — naked options, spread strategies, or leveraged futures — based on IVR, score, and market structure. Hard score gates (≥75/≥85), ATR slope volatility veto, HA/Real divergence filter, and adaptive Kelly sizing enforce portfolio-level discipline.

---

## Architecture

```
underlying domain   → signal truth   (spot/index/perp + 4H/1H/15m candles)
options domain      → tradability    (chain, IV, DTE, OI, spread)
execution domain    → timing truth   (pullback vs continuation on 15m)
risk domain         → survival       (sizing, exits, monitor)
```

### Backend (FastAPI + Python 3.12)

```
backend/
├── main.py                            app factory, lifespan, adapter stack
├── app/
│   ├── core/                          config, logging, rate_limit
│   ├── schemas/                       pydantic: instruments, market, directional,
│   │                                  execution, risk (ScoringWeights), positions,
│   │                                  backtest, snapshot, account, alerts
│   ├── engines/
│   │   ├── indicators/                heikin_ashi, supertrend, ema, atr
│   │   ├── directional/               regime, signal, setup, policy, execution,
│   │   │                              option_translation, contract_health,
│   │   │                              structure_selector, sizing, scoring,
│   │   │                              monitor, orchestrator
│   │   └── backtest/                  backtest_engine, bs_pricing (Black-Scholes)
│   ├── services/
│   │   ├── cache.py                   CachingAdapter (TTL + canonical-limit dedup)
│   │   ├── retry.py                   RetryingAdapter (exponential backoff + timeout)
│   │   ├── db.py                      SQLite (positions, alerts, webhooks,
│   │   │                              exchanges, signal_history)
│   │   ├── paper_store.py             in-memory + write-through positions store
│   │   ├── eval_history.py            SQLite-persisted rolling eval log
│   │   ├── alert_store.py             SQLite-persisted alert store
│   │   ├── alert_service.py           check_and_fire() — shared by SSE + poller
│   │   ├── snapshot_cache.py          45s TTL cache — SSE writes, poller reuses
│   │   ├── arrow_store.py             7-day TTL arrow event store
│   │   └── exchanges/
│   │       ├── base.py                BaseExchangeAdapter (abstract)
│   │       ├── instrument_registry.py BTC, ETH, SOL, XRP, NIFTY, BANKNIFTY
│   │       └── adapters/
│   │           ├── deribit.py         Deribit public API (DVOL, options, candles)
│   │           ├── okx.py             OKX public API (ATM-IV for IVR)
│   │           ├── delta_india.py     Delta Exchange India (BTCUSDT/ETHUSDT perps)
│   │           ├── binance.py         Binance USDT-M futures (candles/prices)
│   │           └── zerodha.py         Zerodha Kite (NIFTY/BANKNIFTY options)
│   └── api/v1/endpoints/
│       ├── health.py                  exchange ping, positions count, cache keys
│       ├── instruments.py             instrument registry CRUD
│       ├── directional.py             status, watchlist, snapshot, market-snapshot,
│       │                              preview, run-once, run-all, history,
│       │                              SSE stream, arrows, regime-trend, vol-scan
│       ├── positions.py               CRUD + enter, monitor, monitor-all, summary,
│       │                              greeks (Δ/Γ/V/Θ), pnl-live, close-all,
│       │                              pnl-history, notes, analytics, export
│       ├── config.py                  risk params, scoring weights, eval-history-cap,
│       │                              data-source hot-swap, system info
│       ├── backtest.py                indicator replay + Black-Scholes option P&L
│       ├── exchanges.py               exchange account CRUD + data-source activation
│       ├── account.py                 balances, positions, orders, fills, exports
│       ├── alerts.py                  CRUD, check, dismiss + status/days filters
│       ├── webhooks.py                Discord / Telegram / HTTP delivery
│       ├── options.py                 option chain browser with health assessment
│       ├── stats.py                   session aggregate counts
│       └── session.py                 export bundle, reset
└── tests/                             544 tests, all mocked, no live network
```

### Adapter Stack (production)

```
CachingAdapter  (TTL per resource; canonical-limit dedup)
  └── RetryingAdapter  (3 attempts, 0.4s base, 8s per-call timeout)
        └── DeribitAdapter | OKXAdapter | DeltaIndiaAdapter | BinanceAdapter | ZerodhaAdapter
```

### Frontend (React 19 + TypeScript 5.9 + Vite 8)

```
frontend/src/
├── types/       TypeScript interfaces mirroring backend schemas
├── utils/       api.get/post/put/delete · fmt helpers (fmtState, fmtStructure,
│                fmtDirection, fmtArrow, fmtN, fmtUSD, ivrColor, fmtAge)
├── store/       Zustand 5: useSelectedUnderlying / useSetSelectedUnderlying selectors
├── hooks/       30 hooks — see Hook Inventory below
├── components/  33 components — see Component Inventory below
└── pages/       Dashboard (8 tabs: Analysis / Option Chain / Account / Alerts /
                                    Backtest / Positions / Watchlist / Config)
```

**Hook Inventory**: useInstruments · useDirectionalStatus · useSnapshot · useMarketSnapshot ·
usePreview · useRunOnce · useBacktest · usePositions · useMonitorPosition · usePortfolioSummary ·
usePortfolioGreeks · useRiskConfig · useScoringWeights · useWatchlist · useSignalStream (SSE) ·
useEvalHistory · useAlerts · useExchanges · useAccount · useAnalytics · useArrows · useOptionChain ·
useVolatilityScan · useWebhooks · useSessionStats · usePnlHistory · useLivePnl · useRegimeTrend ·
useConfigInfo · useDownload

**Component Inventory**: InstrumentSelector · SnapshotPanel · MarketSnapshot · PreviewCandidates ·
RunOnceResult (score breakdown + tooltips) · PositionsPanel · PortfolioSummary · GreeksPanel ·
AnalyticsPanel · WatchlistPanel · StreamBadge · ExchangeBadge · AlertBadge · ArrowAlert (SSE overlay) ·
ArrowHistoryPanel · RiskConfigPanel · ScoringWeightsPanel · EvalHistoryPanel · BacktestPanel ·
ExchangeManager · AccountPanel · AlertManager · OptionChainViewer · VolatilityScanPanel ·
WebhookManager · PositionSizingCalc · PnLSparkline · RegimeSparkline · SessionStatsPanel ·
SessionExport · SystemInfoPanel · PanelBoundary · ErrorBoundary

---

## API Reference

### Core

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status, exchange ping, positions count, cache keys |
| GET | `/api/v1/instruments` | All registered underlyings |
| GET | `/api/v1/instruments/{underlying}` | Single instrument metadata |

### Directional

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/directional/status?underlying=BTC` | Regime + signal + state |
| GET | `/api/v1/directional/snapshot?underlying=BTC` | Full state in one call (spot + regime + signal + exec + IV Rank) |
| GET | `/api/v1/directional/watchlist` | All instruments — parallel evaluation |
| GET | `/api/v1/directional/debug/market-snapshot?underlying=BTC` | Live data source probe |
| GET | `/api/v1/directional/preview?underlying=BTC` | Ranked candidate structures |
| POST | `/api/v1/directional/run-once?underlying=BTC` | Full evaluation plan (paper-only) |
| POST | `/api/v1/directional/run-all` | Evaluate all instruments in parallel |
| GET | `/api/v1/directional/history/{underlying}` | Last N evaluation snapshots (configurable cap) |
| GET | `/api/v1/directional/stream/{underlying}?interval=30` | SSE live signal stream — fires configured alerts automatically |
| GET | `/api/v1/directional/arrows/{underlying}` | Arrow event history (7-day TTL) |
| GET | `/api/v1/directional/arrows` | All arrow events across underlyings |
| GET | `/api/v1/directional/regime-trend/{underlying}?n_bars=30` | 4H candles with EMA50 + regime per bar |
| POST | `/api/v1/directional/volatility-scan` | Scan all instruments for vol regime signals |

### Positions (Paper)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/positions` | List all (filter: ?underlying=BTC&status=open) |
| GET | `/api/v1/positions/summary` | Portfolio summary (open risk, P&L, margin) |
| GET | `/api/v1/positions/analytics` | Win rate, avg P&L, profit factor |
| GET | `/api/v1/positions/greeks` | Aggregate Δ / Γ / V / Θ from open positions (BS-computed) |
| GET | `/api/v1/positions/pnl-live` | Live unrealised P&L across all open positions |
| GET | `/api/v1/positions/export` | CSV download |
| POST | `/api/v1/positions/enter` | Evaluate + create paper position |
| POST | `/api/v1/positions/close-all` | Close all open positions at current spot |
| POST | `/api/v1/positions/monitor-all` | Batch monitor + record P&L history |
| GET | `/api/v1/positions/{id}` | Single position |
| GET | `/api/v1/positions/{id}/pnl-history` | Session P&L snapshots |
| POST | `/api/v1/positions/{id}/close` | Close with exit spot price |
| POST | `/api/v1/positions/{id}/monitor` | Check exit conditions + record P&L snapshot |
| PATCH | `/api/v1/positions/{id}/notes` | Update trade journal notes |
| DELETE | `/api/v1/positions/{id}` | Remove position |

### Exchanges & Account

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/exchanges` | List configured exchanges |
| POST | `/api/v1/exchanges` | Add exchange (delta_india / zerodha / deribit / okx) |
| GET | `/api/v1/exchanges/supported` | List supported adapter names |
| GET | `/api/v1/exchanges/{id}` | Single exchange config |
| PUT | `/api/v1/exchanges/{id}` | Update API key/secret |
| DELETE | `/api/v1/exchanges/{id}` | Remove |
| POST | `/api/v1/exchanges/{id}/activate` | Set active account exchange |
| POST | `/api/v1/exchanges/{id}/activate-data-source` | Switch live market data source |
| POST | `/api/v1/exchanges/{id}/test` | Verify credentials |
| GET | `/api/v1/account/info` | Active exchange info (safe: no 4xx when unconfigured) |
| GET | `/api/v1/account/summary` | Portfolio snapshot (balance, PnL, margin) |
| GET | `/api/v1/account/balances` | Per-asset balances |
| GET | `/api/v1/account/positions` | Open positions (filter: ?underlying=BTC) |
| GET | `/api/v1/account/orders` | Open orders |
| GET | `/api/v1/account/fills?limit=50` | Recent fills/trades |
| GET | `/api/v1/account/fills/export` | Fills CSV download |
| GET | `/api/v1/account/positions/export` | Positions CSV download |

### Alerts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/alerts` | List all (filter: ?underlying=BTC&status=active&days=7) |
| GET | `/api/v1/alerts/triggered` | Triggered alerts only |
| POST | `/api/v1/alerts` | Create alert |
| POST | `/api/v1/alerts/check` | Check all active alerts against live snapshot |
| POST | `/api/v1/alerts/{id}/dismiss` | Dismiss triggered alert |
| DELETE | `/api/v1/alerts/{id}` | Delete alert |
| DELETE | `/api/v1/alerts` | Bulk-delete all dismissed alerts |

### Webhooks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/webhooks` | List configured webhooks |
| POST | `/api/v1/webhooks` | Add webhook (Discord / Telegram / generic HTTP) |
| DELETE | `/api/v1/webhooks/{id}` | Remove webhook |
| POST | `/api/v1/webhooks/{id}/test` | Send a test delivery |
| POST | `/api/v1/webhooks/{id}/toggle` | Enable / disable webhook |

### Volatility & Options

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/options/chain` | Full chain with health dots (filter: ?underlying=BTC&type=call&min_dte=5&max_dte=45) |
| POST | `/api/v1/directional/volatility-scan` | IV rank scan across all instruments |

### Config & Backtest

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/config/risk` | Current risk params |
| PUT | `/api/v1/config/risk` | Update (capital, position %, max contracts) |
| POST | `/api/v1/config/risk/reset` | Reset to env defaults |
| GET | `/api/v1/config/scoring-weights` | Current scoring component weights |
| PUT | `/api/v1/config/scoring-weights` | Update weights (auto-normalised server-side) |
| POST | `/api/v1/config/scoring-weights/reset` | Reset weights to defaults |
| GET | `/api/v1/config/eval-history-cap` | Current eval history cap (default 50) |
| PUT | `/api/v1/config/eval-history-cap` | Change cap (10–500) |
| GET | `/api/v1/config/data-source` | Active market data source |
| POST | `/api/v1/config/data-source` | Hot-swap data source without restart |
| POST | `/api/v1/config/data-source/invalidate-cache` | Force-clear market data cache |
| GET | `/api/v1/config/info` | System info (version, adapter stack, instruments) |
| POST | `/api/v1/backtest/run` | Indicator replay + optional Black-Scholes option P&L |

### Stats & Session

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/stats/session` | Aggregate session counts (arrows, alerts, positions) |
| GET | `/api/v1/session/export` | Download full session state as JSON bundle |
| DELETE | `/api/v1/session/reset` | Clear transient data (eval history, arrows, P&L snapshots) |

---

## Strategy Logic (v3 Unified Engine)

The engine routes every signal to the optimal instrument — **options or futures** — based on IVR, score, and market structure. A single evaluation pipeline handles both.

### Layer 1 — Macro Filter (4H)

| Field | Logic |
|-------|-------|
| Trend bias | EMA21 > EMA55 AND close > EMA21 → Bull; inverse → Bear |
| Volatility | ATR(14)/Close slope ≥ 0 (expanding or flat) = healthy |
| **IDLE veto** | ATR percentile < 30 on 2 consecutive bars **OR** ATR/Close slope < 0 with pct < 35 |
| Cooldown | 2-bar cooldown after contraction (slope-triggered) |
| ADX gating | ADX < 15 → RANGING; 15–20 → partial signals; ≥ 20 → full trend |

`atr_slope` is exposed on `RegimeResult` for dashboard display.

### Layer 2 — Signal Trigger (1H)

| Indicator | Weight |
|-----------|--------|
| SuperTrend flip (ST7,3) | 3 |
| RSI gate (40–78 long / 22–60 short) | 2 |
| RSI momentum bonus (RSI >60 bull / <40 bear) | 1 |
| BB/KC squeeze breakout | 4 |
| Volume spike (>1.5× median) | 4 |
| HA body aligned with trend | 4 |
| HA/Real divergence < 0.3% | 2 |

**Total weight = 20 pts → mapped to 0–20 signal_score.**  
`signal_score ≥ 15` (75%) = STRONG; ≥ 7 (35%) = SIGNAL; below = NONE.

`ha_real_divergence_pct` and `vol_confirm` are exposed on `SignalResult`.

### Layer 3 — Micro Entry (15m)

| Mode | Condition | exec_score |
|------|-----------|-----------|
| **A — Pullback** | Price within 1.5 ATR of ST(7,3) support/resistance + EMA20 aligned + rejection wick bonus | 14 |
| **B — Continuation** | Close beyond 5-bar range + 2× volume | 10 |
| Wait | Neither | 0 |

### Instrument Routing (IVR-driven)

| IVR | Allowed structures |
|-----|-------------------|
| `None` | Fail-closed — ELEVATED band; debit spreads only |
| < 40 | **Long naked calls/puts** + debit spreads |
| 40–60 | All structures (debit preferred) |
| 60–70 | Debit spreads preferred over naked |
| > 70 | **Naked shorts** (IVR >70, OI >100, spread <5%) + credit spreads; hedge with futures |

**Options Long**: 1.5% risk/trade cap · portfolio max 4.5%  
**Options Short**: 1.0% risk/trade cap · portfolio max 3.0%  
**Futures**: 2.0% risk/trade cap; added when IVR routing recommends futures or no healthy chain exists

### Futures Leverage Scale

| Score | Signal | Leverage |
|-------|--------|----------|
| ≥ 95 | STRONG | 50× |
| ≥ 90 | STRONG | 25× |
| ≥ 85 | STRONG | 10× |
| ≥ 80 | any | 5× |
| ≥ 75 | any | 3× |
| < 75 | any | 1× (or no-trade) |

**Scalp leverage (≥ 50×)**: hard 0.5% capital-at-risk ceiling, applied before Kelly sizing.

### Score Thresholds (Hard Gates — not soft comparisons)

| Condition | Required score |
|-----------|---------------|
| Normal trade (options/futures ≤ 5×) | **≥ 75** |
| High leverage (≥ 10×) or naked short | **≥ 85** |

Structures scoring below the applicable threshold are **excluded** from ranked output, not just ranked lower.

### Hard Vetoes (any instrument)

| Veto | Condition |
|------|-----------|
| Spread | > 10% of mid (> 5% for naked shorts) |
| OI | < 50 contracts (> 100 required for naked shorts) |
| Dead zone | 02:00–06:00 UTC |
| Funding rate | \|rate\| > 2.5% |

### State Machine

| Internal code | Display label |
|---|---|
| `IDLE` | Watching |
| `EARLY_SETUP_ACTIVE` | Signal forming |
| `CONFIRMED_SETUP_ACTIVE` | Setup confirmed |
| `ENTRY_ARMED_PULLBACK` | Waiting for pullback entry |
| `ENTRY_ARMED_CONTINUATION` | Waiting for breakout entry |
| `ENTERED` | Trade active |
| `PARTIALLY_REDUCED` | Partially closed |
| `EXITED` | Closed |
| `FILTERED` | Filtered |

### Scoring (0–100, deterministic)

| Component | Points | What it measures |
|-----------|--------|-----------------|
| Macro regime | 0–20 | EMA21/55 trend + ADX + ATR percentile on 4H |
| 1H signal | 0–20 | SuperTrend confluence, RSI, BB squeeze, volume, HA |
| Execution timing | 0–15 | Pullback (14 pts) vs continuation (10 pts) vs wait (0) |
| Contract health | 0–20 | Spread, OI, volume, quote freshness |
| Days to expiry | 0–10 | Proximity to preferred 10–15 DTE (futures always 10) |
| Risk / reward | 0–15 | max_gain / max_loss ratio |
| **Total** | **100** | |

Weights configurable live: `PUT /api/v1/config/scoring-weights`.

### Contract Health

**Hard veto** (score = 0, excluded from structures):
- Zero / negative / inverted bid-ask
- Spread > 15% of mid
- OI < 10 · Volume < 1/day · Quote stale > 5 min · |mark − mid| > 20%
- DTE < instrument minimum (default 5)

**Soft score** (0–100, four equal 25-pt components):  
spread tightness + open interest depth + volume activity + quote freshness

### Backtest Engine

Replays indicator signals over historical candle windows.  
**Optional Black-Scholes option P&L** — pass `atm_iv` (e.g. `0.80` = 80%) to get theoretical  
entry premium and forward P&L at 4H / 12H / 24H horizons alongside candle returns.  
Backtest uses fully-closed 4H bars only (no look-ahead bias).

---

## Quick Start

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev   # http://localhost:5173
```

### Tests

```bash
cd backend
pytest -v
# 718+ tests — indicators, engines, adapters (Deribit + OKX + Delta India),
# registry, API, structures, positions, backtest (BS pricing), cache, retry,
# persistence, snapshot, alerts (integration), webhooks, account, options,
# stats, session, scoring weights, adapter fixtures, v3 unified engine
```

### Docker

```bash
docker compose up --build
# backend: http://localhost:8000
# frontend: http://localhost:3000
```

---

## Instrument Registry

Six underlyings registered. Extend `instrument_registry.py` with zero engine changes:

| Underlying | Exchange | Has Options | Delta Perp | OKX Perp |
|-----------|---------|------------|-----------|---------|
| BTC | Deribit | ✓ | BTCUSDT | BTC-USDT-SWAP |
| ETH | Deribit | ✓ | ETHUSDT | ETH-USDT-SWAP |
| SOL | Deribit | ✓ | SOLUSDT | — |
| XRP | Deribit | — | XRPUSDT | — |
| NIFTY | Zerodha | ✓ | — | — |
| BANKNIFTY | Zerodha | ✓ | — | — |

```python
"BNB": InstrumentMeta(
    underlying="BNB",
    tick_size=0.01, strike_step=10.0,
    has_options=False,
    exchange="deribit",
    exchange_currency="BNB",
    perp_symbol="BNB-PERPETUAL",
    index_name="bnb_usd",
    dvol_symbol=None,
    okx_perp_symbol="BNB-USDT-SWAP",
    okx_index_id="BNB-USDT",
    okx_underlying=None,
    delta_perp_symbol="BNBUSDT",
    delta_option_underlying=None,
)
```

## Exchange Adapters

| Adapter | Candles | Index price | Options chain | IV Rank source |
|---------|---------|------------|--------------|---------------|
| Deribit | ✓ | ✓ | ✓ | DVOL index (BTC, ETH) |
| OKX | ✓ | ✓ | ✓ | ATM option markVol percentile |
| Delta India | ✓ | ✓ | ✓ (C-/P- format) | HV fallback |
| Binance | ✓ | ✓ | — | HV fallback |
| Zerodha | ✓ | ✓ | ✓ | India VIX proxy |

**Switching data source** (hot-swap, no restart):
```bash
# Via API
curl -X POST http://localhost:8000/api/v1/config/data-source \
  -H 'Content-Type: application/json' \
  -d '{"exchange": "delta_india"}'

# Or set default at startup
EXCHANGE_ADAPTER=okx uvicorn main:app --port 8000
```

**IVR when source lacks a vol index**: falls back to rolling 30-day realized-vol (HV) percentile computed from 1H candles. When IV data is unavailable (`ivr=None`), policy defaults to ELEVATED band — naked long premium is excluded and defined-risk spreads are preferred.

## Persistence

| Data | Store | Survives restart |
|------|-------|-----------------|
| Paper positions | SQLite `sterling_paper.db` | ✓ |
| Alerts + fire history | SQLite | ✓ |
| Webhooks | SQLite | ✓ |
| Exchange accounts | SQLite | ✓ |
| Signal history (eval log) | SQLite (configurable cap) | ✓ |
| Arrow events | In-memory (7-day TTL) | ✗ |
| Live P&L snapshots | In-memory | ✗ |

Path configurable via `STERLING_DB_PATH` env var. Falls back to in-memory-only if SQLite unavailable.

## Alert System

Alerts fire **even when the UI / SSE is closed** — a background poller runs every 30s.

**Duplicate-fetch prevention**: When the SSE stream is active for an instrument, the background poller reads from a 45s snapshot cache written by the SSE tick. No duplicate exchange calls.

**Conditions**: price above/below, IV Rank above/below, green/red arrow, state equals.  
**Delivery**: Discord embed, Telegram `sendMessage`, or any HTTP POST endpoint.  
**Cooldown**: configurable re-arm window per alert (0 = fire once, N = re-arm after N hours).

Configure in: Config tab → Webhooks → Add.  
Test without waiting for a condition: **TEST** button.

## Option Chain Browser

```
GET /api/v1/options/chain?underlying=BTC&type=call&min_dte=5&max_dte=45
```

Returns full chain with per-contract health assessment (spread, OI, volume, staleness, mark-mid stability).  
Strikes sorted ascending within each expiry. Unhealthy contracts include a veto reason.

Frontend: **Option Chain** tab — filter calls/puts, DTE range, health dot per contract.

## Zerodha Kite — Setting Access Token

Zerodha session tokens expire daily. After daily login:
1. Account tab → Exchange Accounts → Zerodha → EDIT KEYS
2. Extra Config JSON: `{"access_token": "your_session_token_here"}`
3. Save → Test → Set Active

API key and secret are permanent; only `access_token` changes daily.

## Deferred (post-v0.4)

| Feature | Notes |
|---------|-------|
| Live order routing | Not started — paper-only by design |
| WebSocket upgrade | SSE sufficient for current use case |
| Historical option data | Candle infrastructure ready; options chains not archived |
| Multi-exchange arbitrage | Registry + adapters ready; routing logic needed |
| User accounts / auth | Not started |
| Redis session store | Swap `paper_store._positions` dict for Redis hash |
