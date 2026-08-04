# Sterling — Product Requirements Document

> **Status: descriptive, not aspirational.** This document describes Sterling **as it exists today**. It is not a proposal, roadmap, or spec for new work. Where the platform is deliberately incomplete or intentionally scoped out, that is called out explicitly in [Non-Goals](#non-goals--explicit-scope-limits) rather than framed as a gap to close.

## 1. What Sterling Is

Sterling is a modular, broker-agnostic algorithmic trading platform spanning two markets simultaneously:

1. **Crypto** — Delta Exchange India as the primary broker, with Binance, Deribit, and OKX adapters also present. Trades futures and options via VCP (Volume Concentration Profile) pattern detection plus multi-timeframe momentum confluence, with backtest-validated "edge" signals.
2. **Indian equities & derivatives** — via Zerodha Kite Connect, fully multi-tenant (each user supplies their own encrypted API credentials). Offers both an auto-scan/auto-execute engine and a full manual trading terminal (order window, positions, GTT orders, funds).

Both markets run inside one system with shared risk plumbing, one execution integration point, and one terminal UI — not two separate tools bolted together.

## 2. Core Value Proposition

Every order — auto-generated or manually placed, crypto or Kite/equities — funnels through exactly one integration point, the `OrderRouter`, which supports paper/shadow/live dispatch modes and a fail-closed safety pipeline.

Brokers, markets, strategies, and risk rules are explicitly designed to be **plug-and-play**: a strategy is written once against normalized `Signal` / `Candle` / `OptionSummary` models and runs unchanged whether the underlying is a Delta India crypto perpetual or a Zerodha equity/derivative, because broker adapters absorb all exchange-specific differences (auth, symbol formats, lot sizing).

This is enforced by a **"strangler-fig" hardening discipline** — all new capability ships additively, with a hard zero-regression test gate at every step, rather than rewrites.

## 3. Target User

Primarily the platform's own operator/developer. This reads as a personal or small-team trading system, not a SaaS product with paying end users. The target user:

- Trades both crypto (via Delta India) and Indian equities/derivatives (via their own Zerodha account).
- Wants one coherent system with shared risk plumbing, observability, and a Bloomberg-dark-themed terminal UI, rather than juggling separate broker-native tools.

The multi-tenant design of the Kite integration means multiple individual users can each connect their own Zerodha account with their own encrypted credentials — but there is no evidence of a commercial multi-customer business model, billing, or admin/tenant-management layer. It reads as **infrastructure for individual account owners**, not a managed product.

## 4. Architecture (for feature-accuracy context)

Dependencies point strictly inward across three layers:

- **Domain** (`app/domain/`) — pure contracts, no I/O, no FastAPI: `Signal`, `TradeEvent` + taxonomy, canonical schemas, structural `Protocol`s (`BrokerProtocol`, `MarketAdapterProtocol`, `StrategyProtocol`, `RiskRuleProtocol`). The platform's anti-corruption boundary.
- **Application** — orchestration with no transport concerns: the `EventBus` (`app/bus/event_bus.py`), the named agents + `Orchestrator` (`app/agents/`: `broker_agent.py`, `execution_agent.py`, `market_agent.py`, `orchestrator.py`, `pnl_agent.py`, `reconciliation_agent.py`, `risk_agent.py`, `strategy_agent.py`), the `OrderRouter` (`app/services/execution/order_router.py`), and the `RiskEngine` (`app/engines/risk/engine.py`).
- **Infrastructure** — the outside world: exchange adapters (`app/services/exchanges/`), persistence (`app/services/*store*`, plus the newer SQLAlchemy layer under `app/persistence/`), and the FastAPI app (`main.py`, `app/api/v1/`).

**Broker adapter layer.** Three adapter base classes of increasing capability: `BaseExchangeAdapter` (public market data), `AuthenticatedExchangeAdapter` (+ private account data), `TradingExchangeAdapter` (+ order placement, enforced by `tests/test_broker_contract.py`). Construction is centralized through `adapter_factory.py::create_account_adapter`, with `registry.load_account_adapter` as the preferred modern entry point. The broker registry (`config/registry.json`) declares 5 brokers (`binance`, `delta_india`, `deribit`, `okx`, `zerodha`) and 6 markets (`commodities`, `crypto`, `energy`, `equities`, `forex`, `metals`).

Zerodha specifically splits into two layers by convention: the raw Kite Connect v3 client (auth, instruments, ticker, multi-tenant account store) lives in `app/services/exchanges/kite/`; the Zerodha-specific trading logic (scanning, sizing, strike/futures selection, protective stops) lives in `app/services/kite_engine/` — substantially larger than a "thin trading layer," with `scanner.py` and `service.py` as its two largest, most central files.

**Execution flow (`OrderRouter`).** Pure orchestration, no FastAPI dependency, deterministic across modes, fail-closed, idempotent. Three `RouterMode` values — `PAPER` (never calls the exchange, records a paper position), `SHADOW` (calls the exchange **and** records a paper position, for audit/diff), `LIVE` (calls the exchange, no paper record) — hot-swappable between calls. `submit(req)` runs, in strict order: (1) resolve underlying → instrument, (2) composite safety gate (kill-switch, daily-loss halt, minute-bucketed idempotency), (3) per-`(symbol, mode, direction)` cooldown, (4) portfolio bucket caps, (5) microstructure veto, (6) correlation penalty (a size multiplier, not an outright veto), (7) dispatch by mode — LIVE additionally runs the Greeks-budget hard gate (paper/shadow are intentionally not gated on Greeks, so breaches can be learned from). On an exchange error the router enqueues a retry item for an out-of-band worker and returns immediately rather than blocking callers.

## 5. Feature Set

### 5.1 Signal-generation engines
- `sterling_engine` — price-action / MA-crossover crypto scalper with its own backtester.
- `sterling_kite_engine` — Zerodha equities/derivatives engine.
- `directional` (a.k.a. "Grok") — multi-track regime/signal/setup/sizing/execution pipeline.
- `derivatives` / `derivatives_native` — Greeks-aware strike/expiry/leverage selection, including gamma-exposure (`gex_engine.py`), pinning-risk, and funding-cost-gate logic.
- `edge` — backtest-validated 4h signal generator gated by a Sharpe ≥ 0.8 CSV registry.
- `sterling_v2` — a validated track-system redesign.
- `hybrid_vcp` — live-feed VCP executor.
- `navigator` (`app/engines/navigator/` + `app/services/navigator/`) — a substantial, actively-developed engine that fuses AVWAP, gamma activity, option flow, and projected-range/volatility evidence into a per-user `NavigatorDecision`, feeding `sterling_kite_engine`. Owns all Navigator in-process mutable runtime state as a rebuildable cache. This is current, live work (the five most recent commits on this branch are all Navigator fixes), not a finished or formally documented subsystem yet.

### 5.2 Shared candidate infrastructure
Shared "candidate" tables for futures and options per engine (parameterized common components), with a `source` badge so the UI never conflates which engine produced a row.

### 5.3 Risk & analytics
- **Pure, no-I/O analytics library**: walk-forward optimization, sensitivity sweeps, correlation tracking, CPCV (combinatorial purged cross-validation), Monte Carlo, plus adaptive stops, decay tracking, performance, and reconciliation helpers.
- **Stateful risk layer**: drawdown circuit breaker, Greeks budget, slippage model, microstructure veto, plus cooldown, portfolio Greeks aggregation, regime-adaptive sizing, vol-of-vol gating, and track budgeting.

### 5.4 Manual trading terminal (Kite)
Order window, positions, GTT (good-till-triggered) orders, funds, instrument search, live WebSocket ticks, and an optional "Mac motion" gated UI layer (framer-motion, lazy-loaded, off by default) for a more native-feeling interaction model.

### 5.5 Trading-mode controls
PAPER vs LIVE per account, and MANUAL vs AUTO execution toggles, exposed both globally and per-row in the UI.

### 5.6 Observability
Structured JSON logging (opt-in), request correlation IDs, an in-process metrics registry — all additive/opt-in, none changes default behavior.

### 5.7 Market taxonomy
Crypto and equities are live. Commodities is manual-trading-only (not yet wired into the auto-scan universe). Forex, metals, and energy are declared as markets in the registry but have no broker serving them yet — planned, not implemented.

### 5.8 Frontend
React 19 + TypeScript + Vite. `frontend/src/pages/SimpleTerminal.tsx` is the production shell (KITE / CRYPTO top-tab switch). `components/kite/` holds the Zerodha panes (ConnectPane, OrderWindow, PositionsPane, OrdersPane, GttPane, FundsPane, SterlingKiteEnginePane) plus a `mac/` gated motion-layer subfolder. `components/sterling_engine/` and `sterling_v2/` are per-engine tab components; `components/derivatives/` holds shared parameterized candidate tables. ~55 domain hooks under `hooks/` (`useSignalFeed` SSE, `useKiteLiveTicks` WS singleton, `useBacktest`, `useCorrelation`, `useDrawdownBreaker`, `useMacKite`). Zustand stores under `store/`. Styling in `styles/` (`terminal.css` Bloomberg-dark tokens, `kiteUI.tsx` Kite-parity light tokens, `macMotion.ts` motion-layer springs).

### 5.9 Tech stack
Backend: FastAPI + Python 3.12, SQLite (raw `sqlite3`, authoritative today) with a parallel SQLAlchemy ORM layer (Postgres-ready, dual-write only, default off). Real-time: WebSocket ticker for Kite, SSE (`/api/v1/stream`) for crypto signal streaming. Deployment: `make setup/backend/frontend` for local dev, Docker Compose for containerized deployment, health/readiness via `GET /health`.

## 6. Non-Goals / Explicit Scope Limits

These are deliberate, documented boundaries — not oversights or bugs:

- **Commodities trading is manual-only.** Not wired into the auto-scan universe. A backlog item by design, not a defect.
- **`RiskEngine` (`app/engines/risk/engine.py`) is not authoritative.** It runs in shadow/log-only mode via `shadow_compare()` until disagreement-free parity with the live safety pipeline is demonstrated. Promoting it early is an explicit non-goal until that bar is met.
- **SQLAlchemy/Postgres persistence is dual-write only.** SQLite remains authoritative today. Flipping Postgres to authoritative in production is a known, not-yet-done step, not an oversight.
- **Several `directional/` modules are neutral/no-op stubs** (`track_scoring.py`, `track_selector.py`, `sizing_engine.py`, `execution_engine.py`, `structure_selector.py`, `policy_engine.py`), left over from a 2026-05-24 "strategy reset." The project's own documentation flags its signal-generation diagram as "the conceptual shape, not the current call graph" — this is a known, self-documented gap.
- **`app/engines/scalping/` and `app/engines/triple_supertrend/` are intentionally empty.** Their logic was consolidated elsewhere during the 2026-06-03 "Sterling-only consolidation." The instruction is explicitly: do not add new code there.
- **No commercial multi-tenant business layer.** Multi-tenant Kite credential storage exists, but there is no billing, admin console, or tenant-management product surface — this is infrastructure for individual account owners, not a managed SaaS.

## 7. Success Criteria

Sterling does not track these as formal KPIs; they are the implied, enforced bar for the system today:

- **Zero-regression is the literal gate for every change.** No new test failure vs. the `main` baseline (`backend/scripts/regression_gate.sh`, CI workflow `.github/workflows/regression-gate.yml`).
- **Delta Exchange India's behavior must never silently change.** Pinned by the "golden smoke" test (`tests/test_golden_smoke_delta.py`).
- **Strategies must survive out-of-sample / cross-symbol validation before being trusted.** The codebase carries hard-won evidence that strategies overfit on short windows, and that momentum specifically has shown negative IS↔OOS correlation. The 4-hour timeframe is repeatedly cited as where durable edge has actually been found.

## 8. Known Documentation Drift (context for readers of this PRD)

For accuracy, this PRD reflects a few points where existing docs (README/ARCHITECTURE/STRATEGIES) have drifted from the current codebase:

- README's file-tree diagram shows a `directional/tracks/` subdirectory (`vcp_track.py`, `trend_following`, `mean_reversion`) that does not exist on disk — `directional/` is currently a flat file layout with no subdirectories, and no `vcp_track.py` or `trend_following.py` exists anywhere in the repo.
- The `navigator` engine (§5.1) is not mentioned in README.md, ARCHITECTURE.md, or STRATEGIES.md at all, despite being a substantial, actively-developed subsystem with five of the branch's most recent commits touching it.
- `calibration_service` is accessed in endpoints via `getattr(request.app.state, "calibration_service", None)` rather than a FastAPI `Depends(...)` provider function — a possible drift from the "always inject via Depends" convention stated in project instructions.

These are noted here so future updates to this PRD (or to README/ARCHITECTURE/STRATEGIES) can close the gap deliberately rather than by accident.
