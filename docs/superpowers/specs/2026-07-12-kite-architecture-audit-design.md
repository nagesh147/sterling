# Kite Module — Architecture Audit & Prioritized Roadmap

**Date:** 2026-07-12
**Scope:** Sterling's Zerodha Kite integration (`backend/app/services/exchanges/kite/`, Kite tab/terminal frontend). Crypto engines out of scope.
**Status:** Design/audit doc — no code changed. Ground-truthed against the actual codebase, not assumed.

## 0. Core thesis

The brief benchmarks Sterling against "Zerodha Kite" as if Sterling needs to rebuild what Zerodha itself runs: a matching engine, a Kafka bus, Go microservices, Postgres at exchange scale, SSO/2FA, ELK/ClickHouse compliance pipelines. **That's a category error.** Zerodha is the exchange-connected broker. Sterling-Kite is a *retail client* of Zerodha's Kite Connect REST/WebSocket API — one HTTP/WS caller among thousands, same tier as any other API user. It has no order book to match, no exchange gateway to run, no other participants to serve.

Auditing a REST client against exchange-operator infrastructure produces a roadmap that adds enormous operational complexity (Kafka cluster, Go rewrite, distributed Postgres) to solve problems Sterling doesn't have, while starving the problems it *does* have — two of which turned out to be live, not hypothetical (§3, §5 Tier 0).

Ground truth (verified by direct codebase read, not memory/assumption — see full findings folded into each section below):

| Layer | Reality | Rough-cut assumption |
|---|---|---|
| Order execution | Hand-rolled `httpx` REST client (`kite/client.py`), no SDK, no matching engine | "core matching engine," CPU-pinned single-threaded path |
| Backend | FastAPI, plain asyncio, single process, `asyncio.create_task` loops for background work, no Celery | Go microservices |
| Data fan-out | Shared `StreamManager` channel per user over the existing app WS (`ticker_manager.py`) | org-wide Kafka bus |
| DB | SQLite (WAL) primary + an **unguarded parallel Postgres path with hardcoded creds, live in `main.py`** | "hundreds of billions of rows" tuned Postgres |
| Cache | Redis used narrowly (cross-worker cooldown, fail-open) — everything else in-process | "self-managed Redis hotpath IMDG" |
| Frontend | React 19 + Zustand + React Query + Vite, plain CSS-in-JS, **no list virtualization** | generic "modular workspace" ask, under-specifies the one thing actually missing |
| Auth | Zerodha's login page owns 2FA/SSO entirely; Sterling only exchanges `request_token`→`access_token`. Server-side identity is **`X-User-Id` header, default `"default"`** | "OAuth lifecycle, SSO + 2FA" (wrong layer) vs the real gap (spoofable header) |
| Testing | pytest, **no coverage gate**; Playwright E2E **already exists** | "establish E2E automation" (already exists, needs auditing not building) |
| Observability | Deliberately no Prometheus/Grafana/Sentry (documented decision in `OBSERVABILITY.md`) — correlation-ID + JSON logs + in-process metrics registry | Enterprise SRE stack |
| Audit logging | Trade rows in SQLite (`positions`, `equity_snapshots`), no immutability/retention guarantee | "ELK/ClickHouse, terabytes over years" |
| Architecture health | TrueCourse wave1 already zeroed the violation backlog (`.truecourse/LATEST.json`: 0 open at every severity) | Implicitly asks to build this from scratch |

---

## 1. Domain-by-domain critique and right-sized target

Each domain below: **what the brief assumed → what's actually true → the audit that's actually worth doing.**

### D1 — Trading Engine & Order Execution
No matching engine exists or should exist — Zerodha's exchange gateway owns that. Real hot path: `KiteClient._place`/`place_order` (`client.py:297,344`) with AMO auto-resubmit. Audit: (a) is `place_order` idempotent under retry (duplicate-order risk on timeout+retry), (b) any synchronous/blocking call on the asyncio loop between tick receipt and order submit, (c) does margin check use Kite's live margin response or a stale local copy, (d) slippage measurement = compare decision-tick timestamp to broker ack timestamp, not a synthetic latency budget.

### D2 — Real-Time Data & Message Bus
No Kafka. `ticker_manager.py`'s per-user `KiteTicker` → shared `StreamManager` channel over the existing WS is the right shape for this scale. Audit instead: per-connection backpressure (slow frontend client blocking tick fan-out to others?), tick-drop counters, WS reconnect/resubscribe correctness after a Zerodha-side disconnect, and whether tick JSON-encoding is CPU-heavy enough to stall the single asyncio loop under full NSE F&O tick load.

### D3 — Core Backend Architecture
FastAPI/asyncio single-process is an appropriate choice at this scale; a Go rewrite is disproportionate without proof of a bottleneck it would fix. Audit: enumerate every `asyncio.create_task` background loop in `main.py` (alert checker, signal refresher, scanners, monitors, retry workers) and confirm none makes a blocking call (sync SQLite driver, `requests`, disk I/O) that stalls the loop. Set an explicit, evidence-based trigger for ever splitting out a hot path (e.g., p99 order-submit latency > X ms sustained) rather than doing it preemptively.

### D4 — In-Memory Data Grids & Caching
Redis already exists (`cooldown_redis.py`), scoped to cross-worker cooldown state, fail-open if absent. That's the correct footprint for a single-worker deployment. Expand only when actually running multiple workers: session/instrument cache would need to move to Redis at that point (not before — premature distributed caching adds an operational dependency with no current benefit).

### D5 — Database & Ledger Scalability
"Billions of rows" doesn't apply to a personal/small-multi-tenant client. Two **real, present-day** issues instead (see Tier 0): `db_postgres.py` has hardcoded credentials and is unconditionally invoked from `main.py:1345`; there is **no migration tooling** (no alembic dir) despite a live parallel SQLAlchemy dual-write path (`db.py:286-321`, `app/persistence/sync.py`). Right-sized target: fix both, then define the actual SQLite→Postgres trigger (concurrent-writer contention on WAL, not a row-count fantasy).

### D6/D7 — UI Workspace Modularization & React Architecture
Legitimate and high-value — this is where the real product surface is. Concrete gap: **no list virtualization anywhere** (no react-window/tanstack-virtual in `package.json`) — a deep option-chain or order-book table will degrade with DOM node count as panes multiply in a multi-pane terminal layout. Audit component re-render behavior under Zustand (selector granularity — are components subscribing to the whole store or narrow slices?) and React Query cache/staleTime tuning for tick-driven vs. REST-driven data (these have very different freshness needs and shouldn't share defaults).

### D8 — State Management & UI Thread Optimization
Zustand + React Query is a sound pairing for this problem (fine-grained client state + server-state caching) — no rewrite needed. Audit for tick-storm correctness: does high-frequency WS tick dispatch batch updates (React 19's automatic batching helps, but cross-store Zustand updates from a WS handler can still fan out unnecessarily) — profile with a synthetic tick flood, not by inspection alone.

### D9 — UI Engineering & Styling Systems
Currently plain CSS-in-JS objects (`terminalUI.ts`), no Tailwind/CSS-modules/design-token layer. Given multiple UI surfaces already exist (Kite tab, main terminal, order window) and past bugs trace to styling drift (e.g. the modal-stacking `.term-root` z-index trap from prior work), a lightweight shared token layer (spacing/color/z-index scale) is worth it — but scoped to consolidating what exists, not a framework migration.

### D10 — Transactional Security & Access Management
**Mis-scoped in the brief.** SSO/2FA is Zerodha's responsibility, not Sterling's — Sterling never sees the user's Zerodha password. The actual access-control surface is `get_current_user()` (`auth.py:27`), which trusts a client-supplied `X-User-Id` header with **no verification and a default value of `"default"`**. With per-user encrypted Kite credentials sitting behind this, any caller can address another user's account by setting a header. This is the real Tier 0 finding (below), not OAuth-lifecycle theater.

### D11 — End-to-End Payload Encryption
Fernet-at-rest for stored tokens (`security.py`, `accounts.py:21,45-47`) is appropriate. Audit, don't rebuild: where does the Fernet key live and how is it rotated (env var vs. secret store), is TLS certificate verification ever disabled (`verify=False`) anywhere in the `httpx` client config, and — once D10 is fixed — does the internal WS stream require real session auth rather than the same trusted header.

### D12 — Enterprise Testing & Mathematical QA
No coverage gate exists at all (`pytest.ini` has no `pytest-cov` section). Rather than a blanket repo-wide %, gate coverage specifically on the risk-critical modules named as invariants in `CLAUDE.md`: `circuit_breaker.py`, `correlation.py`, `calibration.py`, plus margin/position-sizing math. Add property-based/edge-case tests for margin calc boundaries (zero balance, negative P&L, partial fills) — that's where a math bug actually costs money.

### D13 — E2E Test Automation
**Already exists** (`frontend/e2e/*.spec.ts`, Playwright) — the brief asked to build this from scratch, which would duplicate existing work. Real audit: which trade-lifecycle scenarios are actually covered (place/modify/cancel, AMO resubmit, session-expiry mid-day, Kite-side rate-limit response) vs. which are gaps, then fill only the gaps.

### D14 — System Resiliency & Observability
The team has already made and documented a deliberate decision *not* to run Prometheus/Grafana/Sentry (`OBSERVABILITY.md`) in favor of correlation-ID logging + an in-process metrics registry. That's a defensible choice at current scale and should be respected, not overridden by a generic "enterprise stack" mandate. Audit whether the existing lightweight system actually captures what matters operationally (order-submit latency, WS reconnect count, circuit-breaker trips, calibration drift) and define one clear, cheap escalation trigger (e.g., a hosted error tracker) for if/when account count grows — don't build ahead of that need.

### D15 — Audit Logging & Regulatory Compliance
ELK/ClickHouse "terabytes over years" doesn't fit this deployment. The real compliance frame for India-based retail algo trading via broker APIs is SEBI's algo-trading requirements around a reliable, timestamped order/trade audit trail tied to the broker's own order IDs — not log-analytics-platform scale. Right-sized fix: a dedicated **append-only** audit table (order id, broker order id, all state transitions, timestamps) with an explicit retention policy, separate from the mutable `positions`/`equity_snapshots` tables used for live state.

---

## 2. Explicitly rejected (considered, not adopted)

| Proposal | Why rejected at this scale |
|---|---|
| Kafka message bus | One process, one (or a handful of) user accounts; a shared in-process channel already does the job. Kafka adds an operational dependency with no throughput problem to solve. |
| Go microservice rewrite | No profiled bottleneck asyncio can't fix. Rewrite risk/cost is disproportionate to unproven gain. |
| CPU-pinned matching engine | Sterling has no matching engine — this describes Zerodha's job, not a client's. |
| Postgres tuned for hundreds of billions of rows | Actual scale is thousands of rows in SQLite. Solve the real SQLite gaps (migrations, the stray hardcoded-creds Postgres path) before designing for a scale that isn't coming. |
| Sterling-implemented SSO/2FA | Zerodha's login page already owns this; Sterling implementing it would be redundant and outside the OAuth flow Kite Connect actually uses. |
| ELK/ClickHouse multi-year log pipeline | Regulatory need here is a reliable audit trail, not log-analytics infrastructure at that scale. |

---

## 3. Prioritized roadmap (by criticality, not by domain number)

### Tier 0 — Security/correctness, do first (hours–days)
1. ✅ **DONE (2026-07-12)** — `db_postgres.py`'s "V4 TimescaleDB" bootstrap was vestigial dead code (hardcoded `postgres`/`password`@127.0.0.1, called every startup inside a try/except that silently fell back to SQLite — fails-safe today, not an active exposure, but dead weight + a hardcoded-creds file). Confirmed only 3 references in the whole repo (the def + one import + one call site). Deleted `app/services/db_postgres.py` and its import/call in `main.py`. Verified: `main.py` still imports cleanly, full persistence + Kite-router test subset (52 tests) still green.
2. **`get_current_user()` reads an unverified `X-User-Id` header** (`auth.py:27-31`), default `"default"`, sitting in front of per-user encrypted Kite credentials. Note: this is an intentionally documented v1 placeholder — the module's own docstring names it "the single seam where a real auth provider plugs in later" — not an undiscovered bug. Still worth closing (real server-issued session identity) before any wider multi-account rollout; scoped as its own feature-sized item, not bundled here.
3. ✅ **DONE (2026-07-12)** — No alembic migrations existed despite a live SQLAlchemy dual-write path (`app/persistence/`). Added `alembic/` scaffolding wired to `app.persistence.base.Base.metadata` + `resolve_database_url()` (targets the dedicated `sterling_orm.db` / `DATABASE_URL`, never the live `sterling_paper.db`), generated + applied a baseline migration covering `positions`/`equity_snapshots`/`mirrored_records`. Added `alembic>=1.13.0` to `requirements.txt`.
4. Confirm `STERLING_SECRET_KEY` is actually set in whatever environment Sterling runs in — `security.py` silently falls back to a hardcoded dev Fernet key if it's unset (already flagged in `docs/kite_integration.md:41`, but worth a manual check since it's not visible from the repo). Also confirm no `verify=False` anywhere in the Kite `httpx` client TLS config. Not code — an ops verification step for you to run.

### Tier 1 — High-value (days–weeks)
5. Coverage gate scoped to `circuit_breaker.py`, `correlation.py`, `calibration.py` + margin/sizing edge-case tests (zero balance, negative P&L, partial fills).
6. Order-execution hot path: idempotency/dedupe key on `place_order` retries; audit `main.py`'s `asyncio.create_task` loops for any blocking call.
7. Frontend: add virtualization (tanstack-virtual) to option-chain/order-book/watchlist tables.
8. Append-only audit table for order/trade state transitions (compliance-lite, see D15).
9. E2E scenario gap-fill: modify/cancel, AMO resubmit, mid-session token expiry, Kite rate-limit handling — audit existing Playwright specs first, only write what's missing.

### Tier 2 — Medium (weeks, no urgency)
10. WS/tick backpressure + drop-counter instrumentation in `ticker_manager.py`.
11. Zustand selector audit + React Query staleTime split (tick-driven vs. REST-driven).
12. Lightweight shared styling tokens across terminal surfaces (spacing/color/z-index).

### Tier 3 — Explicitly deferred, revisit only if the trigger fires
13. SQLite→Postgres migration — trigger: measured WAL writer contention, not a row-count target.
14. Any hot-path rewrite off Python — trigger: profiled p99 latency budget miss asyncio tuning can't close.
15. External exporters (Sentry/Prometheus/Grafana) — trigger: account/user count or on-call load that the current lightweight logging can't serve.
16. Redis expansion beyond cooldown — trigger: multi-worker deployment.
17. Kafka — no realistic trigger at this product's shape; would need a pivot to many independent high-tick-volume tenants to reconsider.

---

## 4. Self-review

- Placeholders: none — every domain resolves to either a concrete file:line audit target or an explicit rejection with reasoning.
- Internal consistency: Tier 0/1 items are all traceable to specific ground-truth findings in §0, not invented.
- Scope: this doc is the audit/roadmap only. Each Tier 0/1 item is small enough to become its own focused implementation (fix + test), not a single mega-change — recommend spinning up one dated spec (or going straight to `implement-feature`) per item when picked up.
