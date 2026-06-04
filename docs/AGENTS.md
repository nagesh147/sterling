# Agents

> Note: this is the **trading agents** document. The root `AGENTS.md` is the
> AI-coding-tool instruction file and is intentionally separate.

Agents are thin, named facades over existing services. Each has **one
responsibility**, takes its dependencies by injection, moves **no business
logic**, and (where relevant) communicates over the `EventBus`. They live in
`app/agents/`.

## The agents

| Agent | Wraps | Responsibility |
|---|---|---|
| `BrokerAgent` | a `TradingExchangeAdapter` | place/cancel orders; announce `OrderAccepted` |
| `MarketAgent` | a market-data adapter | normalized price / candle access |
| `StrategyAgent` | a signal generator | run strategy → `Signal`s; emit `SignalRaised` |
| `ExecutionAgent` | the `OrderRouter` | route a request; emit `OrderSubmitted/Accepted/Rejected` |
| `RiskAgent` | risk rules / `RiskEngine` | evaluate rules (fail-closed); emit `RiskBreach` |
| `PNLAgent` | — (event subscriber) | track fills & realized P&L from the bus |
| `ReconciliationAgent` | — | diff internal vs broker positions |
| `Orchestrator` | all of the above + `EventBus` | lifecycle: start/stop, heartbeat, recovery |

## Event bus

`app/bus/event_bus.py` — an in-process async pub/sub. No external broker.

```python
from app.bus.event_bus import EventBus
from app.domain.events import FillReceived

bus = EventBus()
bus.subscribe(FillReceived, handler)          # sync or async handler
await bus.publish(FillReceived(symbol="BTCUSD", side="buy", size=1, price=50000))
```

- Subscribing to a base type (e.g. `TradeEvent`) receives **all** subclasses —
  handy for audit/log sinks.
- A failing handler is **isolated** (recorded in `bus.last_errors`); it never
  blocks the publisher or other handlers.

Event taxonomy (`app/domain/events.py`): `SignalRaised`, `OrderSubmitted`,
`OrderAccepted`, `OrderRejected`, `FillReceived`, `PositionClosed`, `RiskBreach`,
`Heartbeat`.

## Reference flow

The wired, tested reference flow is **Fill → PNL**:

```python
bus = EventBus()
pnl = PNLAgent(bus=bus)                  # subscribes to FillReceived + PositionClosed
await bus.publish(FillReceived(...))     # pnl.fills grows
await bus.publish(PositionClosed(symbol="BTCUSD", realized_pnl_usd=1000))
pnl.snapshot()  # {"fills": N, "realized_pnl_usd": 1000.0}
```

`ExecutionAgent` wraps the real `OrderRouter`: `await agent.execute(req)` routes
through the full safety pipeline and emits the order-lifecycle events.

## Lifecycle

```python
orch = Orchestrator(bus=bus, heartbeat_interval=30.0)
orch.register(some_agent)        # agents may expose async start()/stop()
await orch.start()               # starts agents + heartbeat loop
await orch.stop()                # graceful, idempotent
```

## Going live

The bus + agents can be activated in the running app by setting
`enable_event_bus=true` (default **OFF**). When on, the lifespan startup creates
an `EventBus`, a `PNLAgent` + `ReconciliationAgent`, and an `Orchestrator`
(heartbeat 60s), and `paper_store.close_position` emits a `PositionClosed` via
`app/services/event_emit.py` (a flag-gated, fail-safe emitter). With the flag off
every emit is a cheap no-op, so default behavior is unchanged. Emitting from sync
code uses `EventBus.publish_sync`.

> **Status:** additive and fully tested (`tests/test_agents.py`,
> `test_event_bus.py`, `test_orchestrator.py`, `test_live_event_wiring.py`). Live
> wiring is opt-in via `enable_event_bus`; broader production flows are adopted
> incrementally (see [MIGRATION.md](../MIGRATION.md)).
