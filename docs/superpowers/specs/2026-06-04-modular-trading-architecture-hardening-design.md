# Modular Trading Platform — Architecture Hardening & Documentation

**Date:** 2026-06-04
**Status:** Design — pending user review
**Author:** Architecture pass (Claude) with Nagesh Madaram
**Scope owner:** `backend/` (FastAPI) + `frontend/` (React/Vite) + repo docs

---

## 1. Goal

Reorganize, harden, and future-proof the Sterling trading app into a **modular, plug-and-play, production-grade architecture** where brokers, markets, strategies, and risk rules can be added or replaced with minimal effort and maximum safety.

## 2. Non-negotiable constraint — ZERO REGRESSION

The refactored system must behave **exactly** as the app does today, especially the **Delta Exchange India** integration (futures + options, paper/shadow/live). Every phase is additive and individually shippable, gated by the existing **153-test suite** plus a Delta India golden smoke test. No working file is moved or rewritten without test-proven parity. Behavior-changing steps run in **shadow/log-only** mode before becoming authoritative.

## 3. Key finding — most of the target already exists

A survey of the codebase shows the requested architecture is **~60–70% already built** and, in the execution path, genuinely production-grade. This effort is therefore **formalization + documentation + additive infill**, NOT a rewrite.

| Requested capability | Already present | File(s) |
|---|---|---|
| Broker interface (ABC) | `BaseExchangeAdapter` (public data) + `AuthenticatedExchangeAdapter` (account ops) | `app/services/exchanges/base.py`, `authenticated_base.py` |
| Multiple brokers | **5 adapters**: delta_india, binance, deribit, okx, zerodha | `app/services/exchanges/adapters/` |
| Broker registry/factory | `create_account_adapter(cfg)` | `app/services/exchanges/adapter_factory.py` |
| Execution router | `OrderRouter` — paper/shadow/live, fail-closed safety pipeline, idempotency, DI | `app/services/execution/order_router.py` |
| Risk primitives | composite safety gate, kill-switch, daily-loss, cooldown, portfolio caps, correlation penalty, Greeks budget gate, circuit breaker | `app/services/live_safety.py`, `app/services/execution/circuit_breaker.py`, `app/engines/risk/` |
| Unified models | 13 Pydantic schemas (account, execution, positions, market, greeks, risk, instruments, …) | `app/schemas/` |
| Instrument normalization | `instrument_registry.py` | `app/services/exchanges/` |
| Paper/live mode | `RouterMode`, `adapter_manager`, `paper_store` | `app/services/` |
| Streaming | SSE feed | `app/api/v1/endpoints/stream.py` |
| Tests (regression net) | **153 test files** incl. `test_zerodha_alerts`, `test_trading_mode`, `test_webhooks_options`, `test_walk_forward` | `backend/tests/` |

### Genuine gaps (what this effort actually adds)

1. **Order contract is not in the interface.** `place_order` / `cancel_order` / `place_order_option` live on the concrete `DeltaIndiaAdapter` and are documented only as the informal `_AsyncAdapterShim` inside `order_router.py`. A new broker author has no *enforced* order-side contract. **(Phase 1)**
2. **No config-driven `registry.json`.** The factory is a hardcoded `if/elif` ladder. **(Phase 1)**
3. **No canonical `domain` layer / `TradeEvent`.** Models live in `schemas/` but there is no single "contracts" surface or trade-event type. **(Phase 1)**
4. **No structured-JSON logging / correlation IDs / metric hooks.** `core/logging.py` is basic. **(Phase 2)**
5. **No in-process event bus** (only HTTP SSE). **(Phase 3)**
6. **No named Agent layer / Orchestrator.** The 8 "agents" exist as scattered services, not named units with a lifecycle. (`AGENTS.md` at root is actually MCP tooling docs, not trading agents.) **(Phase 3)**
7. **RiskEngine not separated from execution.** Risk logic is embedded in `OrderRouter` deps + `live_safety`. **(Phase 4)**
8. **Persistence is raw `sqlite3`** (`services/db.py` + 4 others), not SQLAlchemy. **(Phase 5)**
9. **Docs incomplete + root cluttered** with ~18 performance/backtest report `.md` files. **(Phase 6)**

## 4. Chosen approach — Strangler-fig / additive-in-place

Three approaches were considered:

- **A. Strangler-fig / additive-in-place (CHOSEN).** Leave every working file where it is. Add new packages (`domain/`, `bus/`, `agents/`, `persistence/`) alongside existing code; existing services adopt them incrementally via thin facades. SQLAlchemy runs parallel to raw-sqlite (dual-write + verify, flag default-OFF). Every step gated by tests + Delta smoke. → Lowest regression risk, every step shippable.
- **B. Parallel "v2" package + cutover.** Cleaner end-state but duplicated code mid-flight; the cutover is where regressions hide. *(Rejected — higher risk for the same outcome.)*
- **C. Big-bang restructure.** Fastest to a "pretty" tree, highest risk, violates the zero-regression constraint. *(Rejected.)*

**Decision:** Approach **A**. It structurally guarantees "works exactly as today" at every commit.

## 5. Target architecture

### 5.1 Layering (north-star — documented in `ARCHITECTURE.md`)

```
domain  (pure models + interfaces, NO I/O)
   ▲
application  (agents, orchestrator, risk engine, event bus)
   ▲
infrastructure  (broker adapters, persistence, market feeds, FastAPI)
```

Dependencies point **inward** (infrastructure → application → domain). `domain` imports nothing from the other layers — this is the anti-corruption boundary.

### 5.2 Additive folder structure (existing dirs stay put)

```
backend/app/
  domain/              # NEW — canonical contracts (no I/O)
    models.py          #   re-export/bless schemas/* + add Signal, TradeEvent
    interfaces.py      #   Broker, MarketAdapter, Strategy, RiskRule Protocols
    events.py          #   TradeEvent taxonomy (SignalRaised, OrderSubmitted, …)
  bus/                 # NEW — in-process async EventBus (pub/sub)
    event_bus.py
  agents/              # NEW — thin facades over existing services (NO logic moved)
    broker_agent.py    #   wraps adapter_manager / adapter_factory
    market_agent.py    #   wraps market-data services + instrument_registry
    strategy_agent.py  #   wraps engines/* signal generation
    execution_agent.py #   wraps OrderRouter
    risk_agent.py      #   wraps RiskEngine (Phase 4)
    pnl_agent.py       #   wraps paper_store / pnl aggregation
    reconciliation_agent.py  # wraps fills vs broker reports
    orchestrator.py    #   lifecycle: startup/shutdown/heartbeat/recovery
  persistence/         # NEW — SQLAlchemy (parallel, flag-gated, Postgres-ready)
    models.py  session.py  repositories.py
  services/exchanges/  # EXISTING — formalize order methods into the ABC here
  engines/risk/        # EXISTING — promote to RiskEngine + rule registry (Phase 4)
  core/                # EXISTING — extend logging.py → structured JSON (Phase 2)
  api/ engines/ schemas/ services/   # EXISTING — untouched except adoption seams
backend/config/registry.json   # NEW — brokers/markets/strategies registry + loader
docs/                  # 15 canonical docs at root; reports archived to docs/reports/
```

**Frontend:** untouched by this effort (renames already verified safe). No UI/UX changes.

## 6. Core contract definitions

### 6.1 Formalized broker order contract (Phase 1)

A new mixin ABC `TradingExchangeAdapter(AuthenticatedExchangeAdapter)` lifts the *existing* de-facto contract (today's `_AsyncAdapterShim` + `DeltaIndiaAdapter`) into an enforced interface. Signatures match what Delta already implements so **no adapter changes behavior**:

```python
class TradingExchangeAdapter(AuthenticatedExchangeAdapter):
    @abstractmethod
    async def get_product_id(self, symbol: str) -> int: ...

    @abstractmethod
    async def place_order(
        self, symbol: str, side: str, size: float,
        order_type: str = "market_order", limit_price: float | None = None,
        time_in_force: str = "gtc", post_only: bool = False,
        reduce_only: bool = False, stop_loss: float | None = None,
        take_profit: float | None = None, trail_amount: float | None = None,
        **kwargs,
    ) -> dict: ...

    @abstractmethod
    async def place_order_option(
        self, option_symbol: str, side: str, size: float,
        order_type: str = "market_order", limit_price: float | None = None,
        stop_loss: float | None = None, take_profit: float | None = None,
    ) -> dict: ...

    @abstractmethod
    async def cancel_order(self, order_id: str, product_id: int) -> dict: ...

    # Optional capabilities (default raise NotImplementedError so partial
    # adapters still boot) — declared so OrderRouter can feature-detect:
    async def set_leverage(self, product_id: int, leverage: float) -> None: ...
    async def set_margin_mode(self, product_id: int, mode: str) -> None: ...
    async def cancel_replace_stop(self, **kwargs) -> dict: ...
    async def market_reduce_close(self, **kwargs) -> dict: ...
```

`DeltaIndiaAdapter` already satisfies this — making it inherit the mixin is a **declaration-only** change. A **contract test** (`tests/test_broker_contract.py`) asserts every registered adapter satisfies the Protocol, so a future broker that forgets `cancel_order` fails CI, not production.

### 6.2 `registry.json` + loader (Phase 1)

Replaces the hardcoded factory ladder with declarative config. The loader keeps the **same return type and behavior**; the `if/elif` becomes a fallback default so removing the JSON cannot break boot.

```json
{
  "brokers": {
    "delta_india": {"adapter": "app.services.exchanges.adapters.delta_india:DeltaIndiaAdapter",
                    "markets": ["crypto"], "capabilities": ["futures", "options"], "auth": "hmac"},
    "zerodha":     {"adapter": "app.services.exchanges.adapters.zerodha:ZerodhaAdapter",
                    "markets": ["equities", "commodities"], "capabilities": ["equity", "futures"], "auth": "token"},
    "binance":     {"adapter": "...:BinanceAdapter", "markets": ["crypto"], "capabilities": ["futures"]},
    "deribit":     {"adapter": "...:DeribitAdapter", "markets": ["crypto"], "capabilities": ["options"]},
    "okx":         {"adapter": "...:OKXAdapter", "markets": ["crypto"], "capabilities": ["futures"]}
  },
  "markets":   {"crypto": {}, "equities": {}, "commodities": {}, "forex": {}, "metals": {}, "energy": {}},
  "strategies": {}
}
```

Loader: `registry.load_broker(name, cfg)` → imports `adapter` path, instantiates with `cfg`. Falls back to the existing `create_account_adapter` ladder if JSON missing/partial.

### 6.3 Canonical domain models (Phase 1)

`domain/models.py` **re-exports** the existing `schemas/*` types as the canonical surface (no duplication) and adds the two missing primitives:

- `Signal` — normalized strategy output (underlying, direction, instrument_type, score, strength, stops/targets) — already implicit in `OrderRouterRequest`; formalized here so strategies are broker/market-agnostic.
- `TradeEvent` — base event for the bus (see 6.4).

### 6.4 Event bus + events (Phase 3)

`bus/event_bus.py` — in-process async pub/sub over `asyncio`, no external broker:

```python
class EventBus:
    def subscribe(self, event_type: type[TradeEvent], handler) -> None: ...
    async def publish(self, event: TradeEvent) -> None: ...   # fan-out, isolated handler errors
```

Event taxonomy (`domain/events.py`): `SignalRaised`, `OrderSubmitted`, `OrderAccepted`, `OrderRejected`, `FillReceived`, `PositionClosed`, `RiskBreach`, `Heartbeat`. Handlers are isolated — one failing subscriber never blocks others or the publisher.

**Adoption:** wire exactly **one** non-critical reference flow in Phase 3 (e.g. `FillReceived → PNLAgent → ReconciliationAgent`) so the bus is proven, not dead code. All other flows untouched.

### 6.5 Agent layer + Orchestrator (Phase 3)

Eight **thin facades** — they delegate to existing services, moving **no business logic**:

| Agent | Wraps (existing) | Responsibility |
|---|---|---|
| BrokerAgent | `adapter_manager`, `adapter_factory` | auth, adapter lifecycle, rate limits, retries |
| MarketAgent | market-data services, `instrument_registry` | normalize feeds into `MarketData` |
| StrategyAgent | `engines/*` | run strategy logic → `Signal` |
| ExecutionAgent | `OrderRouter` | route signals → broker after risk |
| RiskAgent | `RiskEngine` (Phase 4), `live_safety` | limits, exposure, drawdown, kill-switch |
| PNLAgent | `paper_store`, pnl aggregation | fills, positions, P&L |
| ReconciliationAgent | broker `get_positions/get_fills` | reconcile internal vs broker |
| Orchestrator | all of the above + `EventBus` | startup/shutdown/heartbeat/recovery |

### 6.6 RiskEngine (Phase 4)

Extract the risk rules currently passed as `RouterDeps` callables + `live_safety` checks into a `RiskEngine` with a **rule registry** (each rule = `evaluate(context) -> RiskDecision`). Runs in **shadow/log-only** alongside the existing path first; once outputs match for a verification window, the `OrderRouter` deps are pointed at the engine and the duplicate inline checks are retired. The existing fail-closed semantics are preserved exactly.

### 6.7 Persistence — SQLAlchemy (Phase 5)

SQLAlchemy 2.0 models mirroring the current sqlite schema (`services/db.py`, `paper_store`, `calibration`, `ohlcv_store`, `derivatives_audit`). Introduced **parallel** to raw sqlite:

- Phase 5a: models + session + repositories, **read-only mirror** (dual-read verify in tests).
- Phase 5b: **dual-write** behind `USE_SQLALCHEMY` flag (default **OFF**); a reconciliation check asserts sqlite and SQLAlchemy agree.
- Phase 5c: flip flag ON after a verification window; raw-sqlite path retained as fallback for one release.
- Postgres-ready: engine URL from config, no SQLite-specific SQL in the ORM layer.

## 7. Phase plan (risk-ordered; each phase = one reviewable PR)

| Phase | Deliverable | Risk | Live-flow impact | Gate |
|---|---|---|---|---|
| **0** | Safety net: remove empty `engines/scalping/` + stale pycache, fix `test_scalping_backtest` docstring; add `make verify` (full pytest + frontend `tsc`) + a Delta India golden smoke test; record baseline pass count | none | no | baseline green |
| **1** | `TradingExchangeAdapter` ABC + contract test; `domain/` models (`Signal`, `TradeEvent`); `registry.json` + loader (factory fallback retained) | low | no | tests + new contract test |
| **2** | Structured-JSON logging wrapper on `core/logging.py`; correlation/trade IDs; metric hooks (counters/timers, no exporter required) | low | no (logging only) | tests, log-shape test |
| **3** | `EventBus` + 8 agent facades + `Orchestrator`; wire ONE reference flow (`FillReceived→PNL→Reconciliation`), feature-flagged | medium | one opt-in flow | tests + bus unit tests |
| **4** | `RiskEngine` + rule registry; run **shadow/log-only** vs existing checks; promote only after parity | medium | shadow first | parity diff = 0 |
| **5** | SQLAlchemy parallel store (5a read-mirror → 5b dual-write flag-OFF → 5c flip after verify) | higher | parallel, OFF by default | dual-store reconcile |
| **6** | All 15 docs; market-segregation seam (crypto/equities/commodities/forex/metals/energy taxonomy via registry + instrument_registry); document Zerodha→equities plug-in path; archive root reports → `docs/reports/` | none | no | docs build / link check |

Each phase ends with: `make verify` green, Delta golden smoke green, commit. A phase that cannot prove parity is reverted, not patched forward.

## 8. Documentation deliverables (Phase 6)

**Canonical docs at repo root** (created/updated): `README.md`, `ARCHITECTURE.md`, `BROKERS.md`, `MARKETS.md`, `STRATEGIES.md`, `RISK_MANAGEMENT.md`, `EXECUTION.md`, `SECURITY.md`, `OBSERVABILITY.md`, `TESTING.md`, `DEPLOYMENT.md`, `CONFIGURATION.md`, `MIGRATION.md`, `CONTRIBUTING.md`.

**Trading-agents doc:** placed at **`docs/AGENTS.md`** (NOT root). The existing root `AGENTS.md` is the conventional AI-coding-tool instruction file (MCP graph guidance + claude-mem context) and is left **untouched** to avoid breaking tooling that reads it. `README.md` links to `docs/AGENTS.md`. *(Decision 2026-06-04: zero-risk default chosen over repurposing root `AGENTS.md`.)*

**Declutter:** the ~18 root performance/backtest reports (`BACKTEST_EDGE_REPORT.md`, `SCALPING_PERFORMANCE_REPORT.md`, `STERLING_TRADING_REPORT_*.md`, `KRONOS_*.md`, `VALIDATED_KRONOS_FINAL_REPORT.md`, `REAL_DATA_PERFORMANCE.md`, `DERIVATIVES_EDGE_STUDY.md`, etc.) move to `docs/reports/` via `git mv` (history preserved, no content lost). `CLAUDE.md`, `GEMINI.md`, root `AGENTS.md` (tooling) handled per their tools' expectations.

`MIGRATION.md` is the load-bearing doc: it records, per phase, the exact non-breaking steps, the verification gate, and the rollback procedure.

## 9. Testing / zero-regression strategy

- **Baseline:** Phase 0 records the current pass count of the 153 tests; this is the floor.
- **Golden smoke:** a Delta India smoke test (paper mode) exercises adapter construction → `OrderRouter.submit` → paper position, asserting unchanged response shape.
- **Contract tests:** every registered broker adapter must satisfy `TradingExchangeAdapter` (Phase 1+).
- **Shadow parity:** Phases 4 and 5 require a clean diff between old and new paths before cutover.
- **`make verify`:** single command = backend pytest + frontend `tsc --noEmit`. Run at the end of every phase.
- **No mocks of the system under test** for the smoke path; real adapter in paper mode.

## 10. Out of scope / YAGNI

- No external message broker (Kafka/Redis) — in-process `asyncio` bus is sufficient at current scale; the interface leaves room to swap later.
- No live SQLAlchemy cutover beyond flag-OFF dual-write unless a verification window passes (Phase 5c may land in a later cycle).
- No new strategies, no UI/UX changes, no broker behavior changes.
- No horizontal-scaling infra (k8s, queues) built now — `ARCHITECTURE.md` documents the seams; global state is avoided in new code so it stays possible.

## 11. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Hidden coupling surfaces during formalization | Additive-only; existing code paths untouched; tests gate each phase |
| SQLAlchemy divergence from sqlite | Dual-write + reconciliation check; flag default-OFF; fallback retained |
| Event bus becomes dead code | Wire exactly one reference flow; defer broader adoption to a later cycle |
| RiskEngine alters reject decisions | Shadow/log-only until parity diff = 0 |
| Doc archival breaks external links | `git mv` (history preserved); add redirects/links in `README.md` |
| Renames left a dangling ref | Verified clean (Phase 0 re-checks); golden smoke + `tsc` catch regressions |

## 12. Open questions

None blocking. Defaults chosen: in-process bus (not external), SQLAlchemy flag default-OFF, market taxonomy = {crypto, equities, commodities, forex, metals, energy}. Revisit at Phase 6 if Zerodha onboarding reveals an equities-specific need.
