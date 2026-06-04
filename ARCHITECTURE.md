# Architecture

Sterling is a modular, broker-agnostic trading platform. This document describes
the target architecture, how the existing code maps onto it, and the rules that
keep brokers, markets, strategies, and risk rules plug-and-play.

## Layering

Dependencies point **inward**. Inner layers know nothing about outer layers.

```
            ┌─────────────────────────────────────────────┐
            │ infrastructure                               │
            │  exchange adapters · persistence · FastAPI   │
            │  market feeds · WebSocket streams            │
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

- **domain** (`app/domain/`) — pure contracts: `Signal`, `TradeEvent` + taxonomy,
  re-exported canonical schemas, and structural `Protocol`s (`BrokerProtocol`,
  `MarketAdapterProtocol`, `StrategyProtocol`, `RiskRuleProtocol`). No I/O, no
  FastAPI. This is the anti-corruption boundary.
- **application** — orchestration with no transport concerns: the `EventBus`
  (`app/bus/`), the named agents + `Orchestrator` (`app/agents/`), the
  `OrderRouter` (`app/services/execution/`), and the `RiskEngine`
  (`app/engines/risk/engine.py`).
- **infrastructure** — the outside world: exchange adapters
  (`app/services/exchanges/`), persistence (`app/services/*store*`,
  `app/persistence/` when added), and the FastAPI app (`main.py`, `app/api/`).

## Module map

| Concern | Package | Notes |
|---|---|---|
| Canonical models & interfaces | `app/domain/` | `Signal`, `TradeEvent`, Protocols |
| Event bus | `app/bus/event_bus.py` | in-process async pub/sub |
| Agents + lifecycle | `app/agents/` | thin facades + `Orchestrator` |
| Broker contract | `app/services/exchanges/trading_base.py` | `TradingExchangeAdapter` ABC |
| Broker adapters | `app/services/exchanges/adapters/` | delta_india, zerodha, binance, deribit, okx |
| Broker registry | `app/services/exchanges/registry.py` + `config/registry.json` | metadata + class resolution |
| Execution | `app/services/execution/order_router.py` | paper/shadow/live, safety pipeline |
| Risk (live primitives) | `app/services/live_safety.py`, `app/services/execution/circuit_breaker.py` | kill-switch, daily-loss, idempotency |
| Risk (engine) | `app/engines/risk/engine.py` | separated rule registry (shadow-first) |
| Observability | `app/core/observability.py`, `app/core/metrics.py` | JSON logs, correlation ids, metrics |
| Strategies | `app/engines/` | sterling_engine, directional, edge, … |
| API | `app/api/v1/` + `main.py` | FastAPI routers |
| Persistence | `app/services/db.py` (sqlite) → `app/persistence/` (SQLAlchemy, planned) | |

## Design rules (keep it plug-and-play)

1. **Strategies are broker- and market-agnostic.** They consume normalized
   market data and emit `Signal`s. They never import an adapter.
2. **Adapters implement contracts, not strategies.** A broker that supports
   orders subclasses `TradingExchangeAdapter` and is registered in
   `registry.json`. See [BROKERS.md](BROKERS.md).
3. **Execution is the only thing that talks to a broker for orders**, via the
   `OrderRouter`. See [EXECUTION.md](EXECUTION.md).
4. **Risk is separate from execution.** The safety pipeline runs inside the
   router; the `RiskEngine` is a separable rule registry. See
   [RISK_MANAGEMENT.md](RISK_MANAGEMENT.md).
5. **Avoid global state in new code** so the system can scale horizontally
   later. Inject dependencies (the `OrderRouter` and agents do this).

## Evolution / migration

The platform is being hardened in place via a strangler-fig program (additive
modules, no big-bang rewrite). The full phased plan and the zero-regression
gates are in [MIGRATION.md](MIGRATION.md). The design spec lives at
`docs/superpowers/specs/2026-06-04-modular-trading-architecture-hardening-design.md`.
