# Sterling — System Architecture

> **Supersedes the former root-level `ARCHITECTURE.md`.** That file is deleted;
> this document is the authoritative architecture reference going forward and
> reflects the codebase **as it exists today** (verified against source and
> the code-review-graph, 2026-08-04, branch `kitev2-develop`).

Sterling is a modular, broker-agnostic trading platform covering crypto
(Delta India, Binance, Deribit, OKX) and Indian equities/derivatives
(Zerodha/Kite), with a shared domain layer, a plug-and-play broker/strategy
contract system, and a v3 risk/analytics stack (walk-forward validation,
adaptive calibration, correlation-aware sizing, drawdown circuit breaking).

---

## 1. Layering

Dependencies point **inward**. Inner layers know nothing about outer layers.
This shape is verified structurally consistent with the current code.

```
            ┌─────────────────────────────────────────────┐
            │ infrastructure                               │
            │  exchange adapters · persistence · FastAPI   │
            │  market feeds · WebSocket / SSE streams      │
            │     ┌───────────────────────────────────┐    │
            │     │ application                        │    │
            │     │  agents · orchestrator · event bus │    │
            │     │  OrderRouter · RiskEngine          │    │
            │     │     ┌─────────────────────────┐    │    │
            │     │     │ domain                   │    │    │
            │     │     │  models · interfaces ·   │    │    │
            │     │     │  events (pure, no I/O)   │    │    │
            │     │     └─────────────────────────┘    │    │
            │     └───────────────────────────────────┘    │
            └─────────────────────────────────────────────┘
```

- **domain** (`app/domain/`) — pure contracts, no I/O, no FastAPI: `Signal`,
  `TradeEvent` + taxonomy, canonical schemas, structural `Protocol`s
  (`BrokerProtocol`, `MarketAdapterProtocol`, `StrategyProtocol`,
  `RiskRuleProtocol`). This is the platform's anti-corruption boundary.
  Verified present: `app/domain/events.py`, `interfaces.py`, `models.py`.
- **application** — orchestration with no transport concerns: the `EventBus`
  (`app/bus/event_bus.py`), the named agents + `Orchestrator`
  (`app/agents/broker_agent.py`, `execution_agent.py`, `market_agent.py`,
  `orchestrator.py`, `pnl_agent.py`, `reconciliation_agent.py`,
  `risk_agent.py`, `strategy_agent.py`), the `OrderRouter`
  (`app/services/execution/order_router.py`), and the `RiskEngine`
  (`app/engines/risk/engine.py`).
- **infrastructure** — the outside world: exchange adapters
  (`app/services/exchanges/`), persistence (`app/services/*store*`, plus the
  newer `app/persistence/` SQLAlchemy layer), and the FastAPI app (`main.py`,
  `app/api/v1/`).

## 2. Module map

| Concern | Package | Notes |
|---|---|---|
| Canonical models & interfaces | `app/domain/` | `Signal`, `TradeEvent`, Protocols |
| Event bus | `app/bus/event_bus.py` | in-process async pub/sub |
| Agents + lifecycle | `app/agents/` | 8 agent files, incl. `reconciliation_agent.py` / `market_agent.py` (present but not called out in older shorthand docs) |
| Broker contract | `app/services/exchanges/trading_base.py` | `TradingExchangeAdapter` ABC |
| Broker adapters | `app/services/exchanges/adapters/` | delta_india, zerodha, binance, deribit, okx |
| Broker construction | `app/services/exchanges/adapter_factory.py` (`create_account_adapter`, back-compat), `registry.py` (`load_account_adapter`, preferred modern entry point) | single construction path — prevents registry metadata and factory code drifting apart |
| Broker registry | `app/services/exchanges/registry.py` + `config/registry.json` | `.brokers`: binance, delta_india, deribit, okx, zerodha (5). `.markets`: commodities, crypto, energy, equities, forex, metals (6) |
| Execution | `app/services/execution/order_router.py` | paper/shadow/live, safety pipeline |
| Risk (live primitives) | `app/services/live_safety.py`, `app/services/execution/circuit_breaker.py` | kill-switch, daily-loss halt, idempotency |
| Risk (engine, v3) | `app/engines/risk/` | separable rule registry — see §3 |
| Analytics (v3) | `app/engines/analytics/` | pure functions, no I/O — see §3 |
| Observability | `app/core/observability.py`, `app/core/metrics.py` | JSON logs, correlation ids, metrics |
| Strategy/engine packages | `app/engines/` | sterling_engine, directional, edge, derivatives, navigator, scalping (empty), triple_supertrend (empty) |
| API | `app/api/v1/` + `main.py` | FastAPI routers, 33 route files under `endpoints/` |
| Persistence | `app/services/db.py` (raw `sqlite3`, authoritative today) → `app/persistence/` (SQLAlchemy ORM, dual-write only, not yet authoritative) | |
| Kite raw client | `app/services/exchanges/kite/` | Kite Connect v3: auth, instruments, ticker, multi-tenant account store |
| Kite trading logic | `app/services/kite_engine/` | scanning, sizing, strike/futures selection, protective stops — see §4 |

---

## 3. Backend engine layers (v3 analytics / risk)

`app/engines/` is the strategy and analytics home. Contents verified directly
against the filesystem/graph, not assumed from older docs.

### 3.1 `app/engines/risk/` — v3 risk engine
`circuit_breaker.py` (`DrawdownCircuitBreaker` + `CircuitBreakerConfig`),
`cooldown.py`, `cooldown_redis.py`, `engine.py` (the separable `RiskEngine`),
`greeks_budget.py`, `microstructure_veto.py`, `option_pricing.py`,
`options_monitor.py`, `portfolio_greeks_aggregator.py`,
`regime_adaptive_sizer.py`, `slippage.py`, `track_budget.py`,
`vol_of_vol_gate.py`. Matches the drawdown-circuit-breaker / Greeks-budget /
slippage / microstructure-veto description in prior risk docs, plus several
modules (cooldown, portfolio Greeks aggregator, regime-adaptive sizer,
vol-of-vol gate, track budget) not individually documented before but present
and consistent with that purpose.

### 3.2 `app/engines/analytics/` — v3 analytics engine
`adaptive_stops.py`, `correlation.py` (`CorrelationTracker`), `cpcv.py`,
`decay_tracker.py`, `monte_carlo.py`, `performance.py`, `reconciliation.py`,
`sensitivity.py`, `walk_forward.py`. Matches the documented "walk-forward,
sensitivity, correlation, CPCV, Monte Carlo — pure functions, no I/O"
description, plus adaptive-stops / decay-tracker / performance /
reconciliation modules.

### 3.3 `app/engines/edge/` — backtest-validated signal generator
`catalog.py`, `live_arbitrator.py`, `registry.py`, `robustness.py`,
`signals.py`, `strategies.py`, plus a `sleeves/` subpackage (e.g.
`mean_reversion.py`). This is the "edge" feed — combos with CSV-gated
sharpe ≥ 0.8 from `backtest_edge_results.csv`.

### 3.4 `app/engines/derivatives/` — Greeks-aware selection
`expiry_picker.py`, `freeze_token.py`, `funding_cost_gate.py`,
`gex_engine.py`, `instrument_chooser.py`, `leverage_engine.py`,
`liquidity_score.py`, `pinning_gate.py`, `preview.py`, `profiles.py`,
`schemas.py`, `selector.py`, `sl_tp_solver.py`, `strike_picker.py`,
`time_shifted_revaluation.py`. This is a substantially larger, more mature
module set than a one-line "Greeks-aware strike/expiry/leverage selection"
summary suggests — notably a gamma-exposure engine (`gex_engine.py`), a
pinning-risk gate, and a funding-cost gate.

### 3.5 `app/engines/directional/` (a.k.a. "Grok") — flat layout, doc drift here
Current files (flat, no subpackages): `contract_health_engine.py`,
`dynamic_tp.py`, `execution_engine.py`, `indicators.py`, `monitor_engine.py`,
`mtf.py`, `orchestrator.py`, `policy_engine.py`, `regime_engine.py`,
`setup_engine.py`, `signal_engine.py`, `signal_weights.py`, `sizing_engine.py`,
`structure_selector.py`, `track_scoring.py`, `track_selector.py`,
`trailing_stop.py`.

**Known stale detail (fix on next docs pass):** older backend file-tree
diagrams show a `directional/tracks/` subdirectory containing
`vcp_track.py, trend_following, mean_reversion`. **This subdirectory does not
exist on disk** — `directional/` has zero subdirectories, and neither
`vcp_track.py` nor `trend_following.py` exists anywhere in the repo (only
`mean_reversion.py`, which lives under `app/engines/edge/sleeves/` and
`app/engines/sterling_engine/`, not under `directional/`). This is a
physical-layout drift, separate from the already-known caveat that several
directional modules are still strategy-reset stubs.

**Unverified-this-session, carried from project memory (2026-06-06 audit):**
`STERLING-V4-SPEC.md` (repo root) was previously found to describe a
`scoring.py` that doesn't exist, and much of the directional/"Grok" pipeline
was found emitting fabricated scores. Treat `STERLING-V4-SPEC.md` as
**unverified/suspect** until re-checked against current directional internals
— it is not confirmed current in this pass.

### 3.6 `app/engines/scalping/` and `app/engines/triple_supertrend/`
Confirmed **empty** — only `__pycache__`, zero `.py` source. Legacy/dead, as
documented; this is accurate, not stale.

### 3.7 `app/engines/navigator/` + `app/services/navigator/` — undocumented, actively developed
A substantial engine present in current code, **not mentioned in any prior
architecture/README/strategy doc** (zero hits searching those docs for
"navigator"). It is currently the most actively developed part of the
codebase: the five most recent commits on `kitev2-develop` are entirely
Navigator work ("Stop the board mislabelling Navigator rows and rupee moves",
"Draw Navigator on the chart, and stop the strike badges lying", "Enforce the
trailing stop as a real exit", "Fix blank signal prices and make the exit
state honest", "Fix Navigator lifecycle, cache and calibration defects").

- `app/engines/navigator/` — `avwap.py`, `fusion.py`, `gamma_activity.py`,
  `option_flow.py`, `projected_ranges.py`, `quality.py`, `schemas.py`,
  `volatility.py`.
- `app/services/navigator/` — `adapters.py`, `calendar.py`, `calibration.py`,
  `chain_sampler.py`, `chart_series.py`, `config_store.py`,
  `instrument_slice.py`, `repository.py`, `runtime.py`, `service.py`,
  `status.py`.

`service.py`'s own docstring: *"Navigator runtime service: per-user decision
cache, the one safe join point the scanner calls, the central-gate
eligibility recheck, and the price-feature-only evaluation pipeline (spec
§16, §18) ... owns ALL Navigator in-process mutable runtime state ... a
CACHE: it is always safe to drop and rebuild ... restart never marks old
evidence as current."* It fuses AVWAP, gamma activity, option flow, and
projected-range/volatility evidence into a `NavigatorDecision`, feeding
`app/engines/sterling_kite_engine` (whose `config.py`, `exits.py`, `regime.py`,
`schemas.py` were modified the same day). The referenced internal spec (§16,
§18) was not located during this pass and likely lives under
`docs/superpowers/specs/`. **Treat Navigator as a first-class current engine**
in any deeper architecture work, not an afterthought.

---

## 4. Broker adapter layer

Three adapter base classes in `app/services/exchanges/`, in increasing
capability order:

1. `BaseExchangeAdapter` — public market data only.
2. `AuthenticatedExchangeAdapter` — + private account data.
3. `TradingExchangeAdapter` — + order placement; the enforced order contract,
   checked by `tests/test_broker_contract.py`.

Adapter construction is centralized through
`app/services/exchanges/adapter_factory.py::create_account_adapter`, with
`registry.load_account_adapter` as the preferred modern entry point (the
older `create_account_adapter` remains for backward compatibility only). This
"exactly one construction path" design keeps registry metadata and factory
code from drifting apart.

### Zerodha / Kite — two layers kept deliberately separate

- **Raw Kite Connect v3 client** — `app/services/exchanges/kite/`: auth,
  instruments, ticker, multi-tenant account store. Verified files:
  `accounts.py`, `client.py` (47 KB, largest file here), `constants.py`,
  `errors.py`, `instruments.py`, `models.py`, `session.py`, `ticker.py`,
  `ticker_manager.py`.
- **Zerodha-specific trading logic** — `app/services/kite_engine/`: scanning,
  sizing, strike/futures selection, protective stops. Now substantially
  larger than a "thin trading layer" description implies: `backtest.py`,
  `backtest_service.py`, `detail.py`, `expiry_calendar.py`,
  `expiry_series_compat.py`, `expiry_series_runtime.py`, `futures.py`,
  `greeks.py`, `held_contract_scan.py`, `market_hours.py`, `monitor.py`,
  `positions.py`, `protective_stop.py`, `scanner.py` (56 KB),
  `service.py` (56 KB), `signal_board_runtime.py` (21 KB), `sizing.py`,
  `state.py`, `stock_registry.py`, `strikes.py`, `universe.py`/`universe.json`.
  `scanner.py` and `service.py` are the two largest, most central files in
  the whole Kite stack.

Keeping these two layers separate by convention means the raw broker client
never encodes strategy/sizing logic, and the trading engine never talks to
Kite's wire protocol directly.

---

## 5. Execution flow — `OrderRouter`

`app/services/execution/order_router.py`. Pure orchestration, no FastAPI
dependency, deterministic across modes, fail-closed, idempotent.

**Modes** (`RouterMode`, hot-swappable between calls without reconstructing
the router):

| Mode | Behavior |
|---|---|
| `PAPER` | Never calls the exchange; records a paper position. |
| `SHADOW` | Calls the exchange **and** records a paper position, for audit/diff. |
| `LIVE` | Calls the exchange; no paper record. |

**`submit(req)` pipeline, in strict order:**

1. Resolve underlying → instrument.
2. Composite safety gate (kill-switch, daily-loss halt, minute-bucketed
   idempotency).
3. Per-`(symbol, mode, direction)` cooldown.
4. Portfolio bucket caps.
5. Microstructure veto.
6. Correlation penalty (a size multiplier, not an outright veto —
   sized-to-zero rejects).
7. Dispatch by mode — `LIVE` additionally runs the Greeks-budget hard gate
   (paper/shadow are intentionally **not** gated on Greeks, "so you can learn
   from breaches").

Dependencies (`list_open_positions`, `create_paper_position`,
`cooldown_blocked`, `correlation_penalty`, `portfolio_cap_breach`,
`microstructure_veto`, `greeks_budget_gate`, `instrument_resolver`) are all
injected as a `RouterDeps` bundle — the whole pipeline is unit-testable
without touching a real exchange.

On an exchange error the router enqueues a `live_safety.RetryItem` for an
out-of-band retry worker and returns immediately
(`accepted=False, code="exchange_error"`) — callers never block on retries.

`ExecutionAgent` (`app/agents/execution_agent.py`) wraps the router purely to
emit bus events (`OrderSubmitted` → `OrderAccepted`/`OrderRejected`) without
duplicating safety logic.

---

## 6. Singleton services

Sterling maintains a fixed set of named singletons on `app.state`, wired in
`backend/main.py`'s `lifespan()` startup function (confirmed by direct source
read, ~lines 1443–1460):

```python
app.state.circuit_breaker      = CircuitBreaker(telegram=_telegram_svc)
# app/services/execution/circuit_breaker.py — EXECUTION-level breaker

app.state.dd_circuit_breaker   = DrawdownCircuitBreaker(dd_cfg, portfolio_value=100_000.0)
# app/engines/risk/circuit_breaker.py — DRAWDOWN-level breaker (v3)

app.state.correlation_tracker  = CorrelationTracker(assets=['BTC', 'ETH', 'SOL'])
# app/engines/analytics/correlation.py

app.state.calibration_service  = CalibrationService(db_path=_db._DB_PATH)
# app/services/calibration.py
```

This matches the project's standing invariants exactly — **verified, not
stale**:

| Singleton | Where it sits in the flow |
|---|---|
| `circuit_breaker` (`CircuitBreaker`) | Execution-level breaker, separate class/state from `dd_circuit_breaker` — the two must never be confused. Guards live order placement. |
| `dd_circuit_breaker` (`DrawdownCircuitBreaker`) | **Must run FIRST inside `evaluate()`** (alias `CircuitBreaker.update()` in the invariant naming). Gates whether new risk can be taken on given current drawdown, ahead of any other evaluate-time check. |
| `correlation_tracker` (`CorrelationTracker`) | **`.update()` must be called with 1H closes on every `evaluate()`.** Feeds the `OrderRouter`'s correlation-penalty size multiplier (step 6 of `submit()`, §5). |
| `calibration_service` (`CalibrationService`) | **`.record_trade()` must fire on every paper_store position close.** Persists adaptive win-rate / IVR-percentile state to SQLite (`calibration_state`, `calibration_trades` tables). |

`CalibrationService.record_trade()` callers, traced via the graph
(`callers_of`): `app/api/v1/endpoints/positions.py::_monitor_one`,
`close_position`, `monitor_position` (all position-close paths), plus
`app/engines/backtest/backtest_mtf.py::_replay_profile` for backtests —
consistent with the "every paper_store position close" invariant.

**Possible drift, flagged for a deliberate decision (not silently
corrected):** the stated rule is "always inject `CalibrationService` via
`Depends(...)` — never import directly." Current endpoint code universally
accesses it as `getattr(request.app.state, "calibration_service", None)`
inside handlers (verified in `positions.py`, `risk_dashboard.py`,
`sterling_engine.py`, `derivatives.py`) — there is no
`get_calibration_service`-style FastAPI dependency-provider function anywhere
in the codebase. Reading a lifespan-populated `app.state` attribute rather
than hard-importing the module does satisfy the spirit of "don't import the
singleton directly," but it is not literally `Depends(...)` injection. Treat
this as an open question for whoever next tightens the invariant wording,
not as something this doc silently papers over.

### 6.1 Other `app.state` caches (same singleton pattern)

Later derivatives/edge work added further `app.state` caches following the
same lifespan-wiring pattern:

- `app.state.derivatives_scan_cache` — populated solely by the background
  scanner, read-only for endpoints. Introduced to fix an
  event-loop-starvation bug where synchronous full-universe scans blocked
  all endpoints.
- `app.state.edge_registry` — loaded from `backtest_edge_results.csv`,
  invalidated on `POST /derivatives/edge-gate`.
- `app.state.edge_gate` — operator-tunable `EdgeGate` thresholds.

---

## 7. Runtime state & persistence mechanisms

Beyond the four core singletons, several load-bearing runtime-state
mechanisms exist across the platform. Grouped here because they recur as a
pattern (in-process cache / DB-persisted key / debounced flush) worth
recognizing before touching adjacent code.

### 7.1 CalibrationService (adaptive win-rate / IVR)
Introduced in the Sterling v3 upgrade (`app/services/calibration.py`),
persisting adaptive win-rate and IVR-percentile state to SQLite via
`calibration_state` and `calibration_trades`. The Sterling-only consolidation
(2026-06-03) deliberately kept this service and its endpoint/panel wired into
the terminal even after deleting the standalone CALIBRATION browsing tab —
the recording mechanism survived because other surfaces (Pro Terminal's
BottomPanel/StatusBar) still depend on it.

### 7.2 Kite chart-state KV persistence
The most-iterated runtime-state mechanism in this codebase. Backend storage
is a raw key-value blob (`app_db.set_config`/`get`, keyed
`kite_chart_state_{user_id}_{symbol}` originally, now a single `__global__`
key per user) exposed via `POST/GET /api/v1/kite/chart-state/{symbol}` in
`backend/app/api/v1/endpoints/kite.py`.

- The save endpoint does a **full replace, no merge** — any field sent as
  `null` overwrites the stored value. Durable trap: any new field added to
  the persisted shape must be added to **both** the POST whitelist **and**
  the GET `setdefault`s, or it is silently dropped on the next round-trip.
- Current shape: global chart config (timeframe, active indicators, params,
  Heikin-Ashi flag, log-scale flag, volume-profile flag, zoom) shared across
  every symbol, plus a per-symbol `drawingsBySymbol: {[symbol]: Drawing[]}`
  map.
- A frontend module-level cache, `globalChartStateCache`, is loaded once by
  the first GET and updated synchronously inside `saveChartState`; lazy
  `useState` initializers read this cache so a component remount (the
  Mac-motion-mode `MacSectionFade` remount on symbol switch) reseeds
  instantly instead of racing a fresh GET against a just-flushed POST to the
  same `__global__` key.
- Guard: if the mount-time GET for `__global__` throws, the catch block must
  `return` (not swallow-and-continue) so `chartStateLoaded` stays `false` and
  save-on-change effects never fire with default values — otherwise a
  transient load error would trigger a full-replace POST that clobbers real
  stored state.
- Saves are debounced 700ms behind a single shared timer ref
  (`flushSave()`/`pendingSaveRef` fires the pending save immediately on
  unmount); a `pagehide` + `visibilitychange`→hidden path forces a
  `keepalive` POST on tab close.
- `signalData`-triggered chart opens are treated as transient and skip the
  save path, so opening a signal's 1H/Heikin-Ashi view doesn't get persisted
  as the user's chosen global config.

### 7.3 Kite OI (open-interest) baseline caching
Kite's quote API has no change-in-OI field and no intraday OI-history
endpoint, so delta-OI is computed entirely client-side against a rolling
day-baseline cached in `localStorage` under
`kiteOiBaseline:{underlying}:{expiry}:{IST-date}` — the first OI snapshot
each day becomes the reference point, diffed against each subsequent poll
(~15s). Explicitly client-only, non-durable (resets at midnight IST by
construction of the key), and labeled honestly in the UI as "since first
snapshot today" rather than "since previous close."

### 7.4 Paper-trade position/PnL tracking
Core store: `paper_store`, backed by the live `backend/sterling_paper.db`
(~3 GB). `close_position` is the canonical call site that must invoke
`CalibrationService.record_trade()` (§6). Position sizing correctness
depends on `SizedTrade.contracts` (exchange lot count) vs `SizedTrade.qty`
(`contracts × contract_value`, actual coin quantity) — any code path
computing value/risk/PnL/notional/Greeks-notional must use `.qty`, never raw
`.contracts`. `contract_value` is sourced from
`DeltaIndiaAdapter.get_contract_value`, fetched via the raw unwrapped adapter
(`_adm.get_raw_adapter()`) because the Caching/RetryingAdapter wrappers don't
proxy that method. `capital_at_risk_pct` is computed per-position at add-time
from real account equity (not recomputed later) — a backend restart is
required after any formula correction for it to reflect in already-open
positions.

On the Kite side, a parallel but separate registry exists:
`kite_engine/positions.py` is a DB-persisted open-position registry (key
`kite_engine_positions_{uid}`), the source of truth for stop management,
order-update reconciliation, and sizing. `should_exit` is a pure function;
stops are enforced to only ratchet upward (`update_stop`, never loosens).
Auto-open state is guarded by a separate DB-persisted key
(`kite_engine_auto_open_{uid}`) reconciled against the broker's live
`GET /positions` on startup, before the auto-scan loop starts, so a server
restart can't cause double-entry. Kite's daily realized PnL (feeding the
crypto-only daily-loss breaker logic, deliberately **not** applied to
Kite/INR) is persisted under `kite_engine_daily_pnl_{uid}`, mirroring the
auto-open-guard pattern — an earlier in-memory-only version zeroed out on a
mid-day restart.

### 7.5 Operational safety / kill-switch (research paper trader)
A separate, isolated `study/paper_trader.py` mechanism (not wired to the live
SterlingEngine) persists its own state atomically to `data/paper/state.json`
(write to tmp file, fsync, `os.replace`) plus an append-only `trades.csv`.
`study/paper_safety.py` layers a drawdown kill-switch with hysteresis
(`update_kill_switch`/`apply_kill_switch`: trips the book flat and drops open
positions when forward equity falls a configured threshold below its
high-water mark, re-arms only once equity recovers within a smaller band), an
exclusive `flock`-based `run_lock` to prevent concurrent state mutation, and
a `should_run` check enforcing exactly-once-per-bar execution. This breaker
acts only on the paper trader's own recomputed book, never on real broker
equity.

### 7.6 Client/connection-level caches (performance, not trading state)
Kite's `kite_accounts.acquire_client()`/`release_client()` pattern maintains
one warm `KiteClient` per account id (rebuilt only when encrypted credentials
change) specifically to preserve its `InstrumentCache` (an in-memory parse of
Kite's ~80k-row instrument dump) and its httpx connection pool across
requests. **Standing invariant: never call `build_client()` on a hot/per-request
path** — doing so was the root cause of a 2-minute instrument-search
regression. `InstrumentCache.load()` uses a per-key `asyncio.Lock` to
deduplicate concurrent cold fetches.

### 7.7 Other durable DB-backed state
`wf_results`, `parameter_sensitivity`, `calibration_state`,
`calibration_trades`, `equity_snapshots` tables (v3); a background
sensitivity sweep that runs at startup and weekly, cached 7 days (standing
invariant); and the additive SQLAlchemy persistence layer
(`app/persistence/`) with dual-write mirroring (`sync.py`,
`MirroredRecord`) into ORM tables for positions/equity-snapshots/pnl-history
/alerts/webhooks/exchange-accounts/calibration/derivatives-audit, gated
behind a `use_sqlalchemy` flag still **OFF in production** — a safety net for
a future cutover, not yet the live source of truth.

---

## 8. Frontend structure

React 19 + TypeScript + Vite.

- `frontend/src/pages/SimpleTerminal.tsx` — the production shell (KITE /
  CRYPTO top-tab switch).
- `components/kite/` — Zerodha panes: `ConnectPane`, `OrderWindow`,
  `PositionsPane`, `OrdersPane`, `GttPane`, `FundsPane`,
  `SterlingKiteEnginePane`, plus a `mac/` gated motion-layer subfolder.
- `components/sterling_engine/`, `components/sterling_v2/` — per-engine tab
  components.
- `components/derivatives/` — shared parameterized candidate tables
  (`Common*`).
- `hooks/` — ~55 domain hooks: `useSignalFeed` (SSE), `useKiteLiveTicks` (WS
  singleton), `useBacktest`, `useCorrelation`, `useDrawdownBreaker`,
  `useMacKite`, etc.
- `store/` — Zustand stores: `useStore` (theme/appMode/underlying),
  `useOrderWindowStore`, `useKiteSettings`, `useKiteNotifications`.
- `styles/` — `terminal.css` (Bloomberg-dark tokens), `kiteUI.tsx`
  (Kite-parity light tokens), `macMotion.ts` (motion-layer springs).

The Mac-grade motion layer (`useMacKite()` + `macMotion` tokens) is gated and
lazy-loaded — `framer-motion` must never be statically imported, since that
would defeat the lazy gate for users who don't opt in.

---

## 9. Data flow between components

```
Market data (WS ticks / REST poll)
        │
        ▼
Broker adapter (app/services/exchanges/*, kite_engine/*)
        │  normalizes to domain models
        ▼
Strategy / engine layer (app/engines/*: edge, derivatives, directional,
navigator, sterling_engine, sterling_kite_engine)
        │  emits Signal (app/domain/models.py)
        ▼
StrategyAgent → EventBus (app/bus/event_bus.py)
        │
        ▼
RiskAgent / RiskEngine (app/engines/risk/engine.py)
        │  dd_circuit_breaker.evaluate() FIRST
        │  correlation_tracker.update(1H closes) every evaluate()
        ▼
ExecutionAgent → OrderRouter.submit() (app/services/execution/order_router.py)
        │  safety gate → cooldown → portfolio caps → microstructure veto
        │  → correlation penalty → mode dispatch (paper/shadow/live)
        │  → Greeks-budget gate (LIVE only)
        ▼
Broker adapter (order placement) ──▶ Exchange
        │
        ▼
paper_store / positions registry (app/services/db.py, kite_engine/positions.py)
        │  close_position → calibration_service.record_trade()
        ▼
Persistence (SQLite authoritative; app/persistence/ SQLAlchemy dual-write)
        │
        ▼
FastAPI API layer (app/api/v1/) ──▶ Frontend
        (SSE /api/v1/stream for crypto signals; WebSocket ticker for Kite;
         REST polling for chart-state, OI, positions, PnL)
```

Key invariants that hold at the Risk stage regardless of engine or broker:
`DrawdownCircuitBreaker.update()` runs first inside `evaluate()`;
`CorrelationTracker.update()` runs with 1H closes on every `evaluate()`;
`CalibrationService.record_trade()` fires on every paper_store position
close. See §6 for the verified wiring.

---

## 10. Tech stack summary

| Layer | Stack |
|---|---|
| Backend | FastAPI + Python 3.12 |
| Primary datastore | SQLite (raw `sqlite3`, `sterling_paper.db`) — authoritative today |
| Secondary datastore | SQLAlchemy ORM layer (Postgres-ready engine URL), dual-write only, default off |
| Frontend | React 19 + TypeScript + Vite |
| Kite multi-tenancy | Encrypted per-user credential storage in the account store |
| Real-time (Kite) | WebSocket ticker |
| Real-time (crypto) | SSE (`/api/v1/stream`) signal streaming |
| Local dev | `make setup` / `make backend` / `make frontend` |
| Deployment | Docker Compose (`docker-compose.yml` at repo root; backend built from `backend/Dockerfile`) |
| Health check | `GET /health` |

---

## 11. Design rules (keep it plug-and-play)

Carried forward from the prior architecture doc — still the governing rules:

1. **Strategies are broker- and market-agnostic.** They consume normalized
   market data and emit `Signal`s. They never import an adapter.
2. **Adapters implement contracts, not strategies.** A broker that supports
   orders subclasses `TradingExchangeAdapter` and is registered in
   `registry.json`. See `BROKERS.md`.
3. **Execution is the only thing that talks to a broker for orders**, via the
   `OrderRouter`. See `EXECUTION.md`.
4. **Risk is separate from execution.** The safety pipeline runs inside the
   router; the `RiskEngine` is a separable rule registry. See
   `RISK_MANAGEMENT.md`.
5. **Avoid global state in new code** so the system can scale horizontally
   later. Inject dependencies (the `OrderRouter` and agents do this) — see
   the CalibrationService `Depends` note in §6 for where this currently
   isn't fully honored.

---

## 12. Evolution / migration status

The platform is hardened in place via a strangler-fig program (additive
modules, no big-bang rewrite). Phase 5 (SQLAlchemy persistence) is
self-documented as **partial**: dual-write sub-phases (5a/5b/5c) are done,
with a "production flip" planned but **not executed** — `use_sqlalchemy`
remains off, and SQLite via `app/services/db.py` remains the live source of
truth. Preserve this "not yet authoritative" framing in any future doc update
rather than implying persistence has already moved to Postgres/SQLAlchemy.
The full phased plan and zero-regression gates live in `MIGRATION.md`; the
design spec is at
`docs/superpowers/specs/2026-06-04-modular-trading-architecture-hardening-design.md`.

---

## 13. Known documentation staleness (tracked, not yet fixed elsewhere)

For transparency, open discrepancies found while compiling this document:

1. `directional/tracks/` subdirectory referenced in older file-tree diagrams
   does not exist on disk (§3.5).
2. `app/engines/navigator/` + `app/services/navigator/` were entirely absent
   from prior architecture/README/strategy docs despite being the most
   actively developed engine on this branch (§3.7) — now documented here.
3. `STERLING-V4-SPEC.md` is unverified this session; prior audit found it
   described a nonexistent `scoring.py` (§3.5) — treat as suspect, not
   ground truth, until re-checked.
4. The "`CalibrationService` via `Depends`" invariant phrasing does not match
   current `getattr(request.app.state, ...)` access pattern in endpoint code
   (§6) — flagged for a deliberate decision, not silently resolved.
5. Test-suite quirks (order-dependent tests, one real-socket test that must
   be deselected — `--deselect
   "tests/test_delta_iv_socket.py::test_lifespan_starts_iv_stream_only_when_env_set"`)
   are intentional, known characteristics, not defects.

---

## 14. Provenance / verification notes

This document was compiled by cross-checking claims against the
code-review-graph and direct source reads rather than trusting prior docs at
face value. Graph snapshot used: 1,010 files; 9,552 nodes (889 classes, 1,010
files, 5,044 functions, 2,609 tests); 79,410 edges (51,539 CALLS, 8,845
CONTAINS, 5,394 IMPORTS_FROM, 323 INHERITS, 805 REFERENCES, 12,504
TESTED_BY); languages: python, bash, javascript, typescript, tsx. Community
detection is directory-level (two dominant communities: `backend` ~5,040
members, `frontend` ~1,568 members) rather than semantically fine-grained,
so targeted `semantic_search_nodes` / `query_graph` calls — not community
listing — were the source of the engine-level detail above.

Related docs: `BROKERS.md`, `MARKETS.md`, `EXECUTION.md`,
`RISK_MANAGEMENT.md`, `STRATEGIES.md`, `MIGRATION.md`, `TESTING.md`,
`docs/ai/CONTEXT.md`, `docs/ai/WORKFLOWS.md`.
