# Sterling — Universal Crypto Options Platform

Paper-trading-first, engine-driven crypto options evaluator.  
Exchange adapters: **Deribit** (default) · **OKX** (set `EXCHANGE_ADAPTER=okx`).  
No live order routing. All execution is read-only evaluation + paper simulation.

---

## Architecture

```
underlying domain   → signal truth   (spot/index/perp + 4H/1H/15m candles)
options domain      → tradability    (chain, IV, DTE, OI, spread)
execution domain    → timing truth   (pullback vs continuation on 15m)
risk domain         → survival       (sizing, exits, monitor)
```

### Backend (FastAPI + Python)

```
backend/
├── main.py                            app factory, lifespan, adapter stack
├── app/
│   ├── core/                          config, logging
│   ├── schemas/                       pydantic: instruments, market, directional,
│   │                                  execution, risk, positions, backtest, snapshot
│   ├── engines/
│   │   ├── indicators/                heikin_ashi, supertrend, ema, atr
│   │   ├── directional/               regime, signal, setup, policy, execution,
│   │   │                              option_translation, contract_health,
│   │   │                              structure_selector, sizing, scoring,
│   │   │                              monitor, orchestrator
│   │   └── backtest/                  backtest_engine (indicator-only replay)
│   ├── services/
│   │   ├── cache.py                   CachingAdapter (TTL per resource type)
│   │   ├── retry.py                   RetryingAdapter (exponential backoff + timeout)
│   │   ├── db.py                      SQLite persistence (optional, graceful fallback)
│   │   ├── paper_store.py             in-memory + write-through positions store
│   │   ├── eval_history.py            rolling evaluation log per underlying
│   │   └── exchanges/
│   │       ├── base.py                BaseExchangeAdapter (abstract)
│   │       ├── instrument_registry.py BTC, ETH, SOL, XRP metadata
│   │       └── adapters/
│   │           ├── deribit.py         Deribit public API
│   │           └── okx.py             OKX public API
│   └── api/v1/endpoints/
│       ├── health.py                  enhanced health (exchange ping, positions, cache)
│       ├── instruments.py             instrument registry CRUD
│       ├── directional.py             status, watchlist, snapshot, market-snapshot,
│       │                              preview, run-once, history, SSE stream
│       ├── positions.py               CRUD + enter, monitor, monitor-all, summary
│       ├── config.py                  runtime risk params GET/PUT/reset
│       └── backtest.py                indicator replay endpoint
└── tests/                             167 tests, all mocked, no live network
```

### Adapter Stack (production)

```
CachingAdapter
  └── RetryingAdapter (3 attempts, 0.4s base, 8s per-call timeout)
        └── DeribitAdapter | OKXAdapter
```

### Frontend (React + TypeScript + Vite)

```
frontend/src/
├── types/           TypeScript interfaces mirroring backend schemas
├── utils/           api.get/post/put/delete
├── store/           Zustand: selectedUnderlying
├── hooks/           useInstruments, useDirectionalStatus, useSnapshot,
│                    useMarketSnapshot, usePreview, useRunOnce,
│                    useBacktest, usePositions, useMonitorPosition,
│                    usePortfolioSummary, useRiskConfig, useWatchlist,
│                    useSignalStream (SSE), useEvalHistory
├── components/      InstrumentSelector, StatusPanel, MarketSnapshot,
│                    PreviewCandidates (with score bars), RunOnceResult
│                    (with score breakdown), PositionsPanel (with monitor),
│                    PortfolioSummary, WatchlistPanel, StreamBadge,
│                    ArrowAlert (SSE-driven overlay), RiskConfigPanel,
│                    EvalHistoryPanel, BacktestPanel
└── pages/           Dashboard (5 tabs: Analysis/Backtest/Positions/Watchlist/Config)
```

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
| GET | `/api/v1/directional/snapshot?underlying=BTC` | Complete state in one call (spot + regime + signal + exec + IVR) |
| GET | `/api/v1/directional/watchlist` | All instruments — parallel evaluation |
| GET | `/api/v1/directional/debug/market-snapshot?underlying=BTC` | Proves live data source |
| GET | `/api/v1/directional/preview?underlying=BTC` | Ranked candidate structures |
| POST | `/api/v1/directional/run-once?underlying=BTC` | Full evaluation plan (paper-only) |
| GET | `/api/v1/directional/history/{underlying}` | Last 50 evaluation snapshots |
| GET | `/api/v1/directional/stream/{underlying}?interval=30` | SSE live signal stream (fires alerts automatically) |
| GET | `/api/v1/directional/arrows/{underlying}` | Arrow event history |
| GET | `/api/v1/directional/arrows` | All arrow events across underlyings |
| GET | `/api/v1/directional/regime-trend/{underlying}?n_bars=30` | 4H candles with EMA50 + regime per bar |

### Positions (Paper)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/positions` | List all (filter: ?underlying=BTC&status=open) |
| GET | `/api/v1/positions/summary` | Portfolio summary (open risk, P&L, margin) |
| GET | `/api/v1/positions/analytics` | Win rate, avg P&L, profit factor |
| GET | `/api/v1/positions/greeks` | Aggregate net delta from open positions |
| GET | `/api/v1/positions/export` | CSV download |
| POST | `/api/v1/positions/enter` | Evaluate + create paper position |
| POST | `/api/v1/positions/monitor-all` | Batch monitor + record P&L history |
| GET | `/api/v1/positions/{id}` | Single position |
| GET | `/api/v1/positions/{id}/pnl-history` | Session P&L snapshots (recorded on each monitor call) |
| POST | `/api/v1/positions/{id}/close` | Close with exit spot price |
| POST | `/api/v1/positions/{id}/monitor` | Check exit conditions + record P&L snapshot |
| DELETE | `/api/v1/positions/{id}` | Remove position |

### Exchanges & Account

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/exchanges` | List configured exchanges |
| POST | `/api/v1/exchanges` | Add exchange (delta_india / zerodha / deribit / okx) |
| GET | `/api/v1/exchanges/supported` | List supported adapter names |
| PUT | `/api/v1/exchanges/{id}` | Update API key/secret |
| DELETE | `/api/v1/exchanges/{id}` | Remove |
| POST | `/api/v1/exchanges/{id}/activate` | Set active account exchange |
| POST | `/api/v1/exchanges/{id}/test` | Verify credentials |
| GET | `/api/v1/account/info` | Active exchange info |
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
| GET | `/api/v1/alerts` | List all (filter: ?underlying=BTC) |
| GET | `/api/v1/alerts/triggered` | Triggered alerts only |
| POST | `/api/v1/alerts` | Create alert |
| POST | `/api/v1/alerts/check` | Check all active alerts against live snapshot |
| POST | `/api/v1/alerts/{id}/dismiss` | Dismiss triggered alert |
| DELETE | `/api/v1/alerts/{id}` | Delete alert |

### Config & Backtest

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/config/risk` | Current risk params |
| PUT | `/api/v1/config/risk` | Update (capital, position %, max contracts) |
| POST | `/api/v1/config/risk/reset` | Reset to env defaults |
| GET | `/api/v1/config/info` | System info (version, adapter stack, instruments) |
| POST | `/api/v1/backtest/run` | Indicator-only historical signal replay |

### Config & Backtest

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/config/risk` | Current risk params |
| PUT | `/api/v1/config/risk` | Update risk params (takes effect immediately) |
| POST | `/api/v1/config/risk/reset` | Reset to env defaults |
| POST | `/api/v1/backtest/run` | Indicator-only historical signal replay |

---

## Strategy Logic

### Multi-Timeframe Signal

| TF | Data | Purpose |
|----|------|---------|
| 4H | Real candles | Macro regime (EMA50 filter) |
| 1H | Heikin-Ashi | Directional state (ST × 3) |
| 15m | Real candles | Execution timing (pullback / continuation) |

**Directional state**: ST(7,3) + ST(14,2) + ST(21,1) on HA candles  
- All green → bullish · All red → bearish · Mixed → neutral  
- `green_arrow = all_green_now AND NOT all_green_prev` — setup activation  
- Macro filter: bullish only if 4H close > EMA50; bearish only if 4H close < EMA50

### State Machine

```
IDLE → EARLY_SETUP_ACTIVE → CONFIRMED_SETUP_ACTIVE → FILTERED
                                                    → ENTRY_ARMED_PULLBACK
                                                    → ENTRY_ARMED_CONTINUATION
                                                    → ENTERED → PARTIALLY_REDUCED
                                                    → EXIT_PENDING → EXITED / CANCELLED
```

### Options Policy (IVR-driven)

| IVR | Behavior |
|-----|----------|
| < 60 | Naked allowed |
| 60–80 | Prefer debit spreads |
| > 80 | Avoid long premium |

**DTE**: reject < 5, prefer 10–15, force exit ≤ 3  
**Structures**: naked_call/put, bull_call_spread, bear_put_spread, bull_put_spread (credit), bear_call_spread (credit)

### Scoring (deterministic, 0–100 per component)

| Component | Weight |
|-----------|--------|
| Macro regime | 20% |
| Signal | 20% |
| Execution timing | 15% |
| Contract health | 20% |
| DTE | 15% |
| Risk/reward | 10% |

`score_no_trade` compared against best structure — no-trade wins if structure score is lower.

### Contract Health (hard veto)

- Invalid bid/ask (zero, negative, bid ≥ ask)
- Spread > 15% of mid
- OI < 10 · Volume < 1/day · Quote stale > 5 min · |mark − mid| > 20%

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
# 167 tests — indicators, engines, adapter (Deribit + OKX), registry, API,
# structures, positions, backtest, cache, retry, persistence, snapshot
```

### Docker

```bash
docker compose up --build
# backend: http://localhost:8000
# frontend: http://localhost:3000
```

---

## Instrument Registry

Extend `instrument_registry.py` to add new underlyings — zero engine changes required:

```python
"BNB": InstrumentMeta(
    underlying="BNB",
    tick_size=0.01, strike_step=10.0,
    has_options=False,      # set True once options go live
    exchange="deribit",
    exchange_currency="BNB",
    perp_symbol="BNB-PERPETUAL",
    index_name="bnb_usd",
    dvol_symbol=None,
    okx_perp_symbol="BNB-USDT-SWAP",
    okx_index_id="BNB-USDT",
    okx_underlying=None,
)
```

## Exchange Adapters

| Adapter | Candles | Index | Options | DVOL/IVR |
|---------|---------|-------|---------|---------|
| Deribit | ✓ | ✓ | ✓ | ✓ (BTC, ETH) |
| OKX | ✓ | ✓ | ✓ | — (returns None) |

Switch via `EXCHANGE_ADAPTER=okx` env var. CachingAdapter + RetryingAdapter wrap both identically.

## Persistence

Positions stored in `sterling_paper.db` (SQLite, configurable via `STERLING_DB_PATH`).  
Survives server restart. Falls back to in-memory-only if SQLite unavailable.

## Deferred (post-v0.3)

| Feature | Notes |
|---------|-------|
| Live order routing | Not started — paper-only by design |
| WebSocket upgrade | SSE sufficient for current use case |
| Portfolio Greeks | Aggregate delta/gamma/vega across positions |
| Historical option data | Candle infrastructure ready; options chains not archived |
| Multi-exchange arbitrage | Registry + adapters ready; routing logic needed |
| User accounts / auth | Not started |
| Redis session store | Swap `paper_store._positions` dict for Redis hash |

## Webhooks (Alert Delivery)

Sterling can push alert notifications to Discord, Telegram, or any HTTP endpoint.

**Discord**: Paste your Discord channel webhook URL — messages arrive as rich embeds.  
**Telegram**: Use `https://api.telegram.org/bot{TOKEN}/sendMessage`, set `extra = {"chat_id": "xxx"}`.  
**Generic**: Any URL accepting `POST` JSON `{subject, message, data}`.

Configure in: Config tab → Webhook Notifications → Add.  
Test delivery without waiting for an alert to fire: TEST button.

## Option Chain Browser

`GET /api/v1/options/chain?underlying=BTC&type=call&min_dte=5&max_dte=45`

Returns full chain with per-contract health assessment (spread, OI, volume, staleness, mark-mid stability).  
Strikes sorted ascending within each expiry. Unhealthy contracts shown with veto reason.

Frontend: OPTION CHAIN tab — filter by calls/puts, DTE range, see health dot per contract.

## Zerodha Kite — Setting Access Token

Zerodha session tokens expire daily. After daily login:
1. Account → Exchange Accounts → Zerodha → EDIT KEYS
2. Extra Config JSON: `{"access_token": "your_session_token_here"}`
3. Save → Test → Set Active

Kite API key and secret are permanent; only access_token changes daily.
