# Execution — signal → order flow

All orders flow through a single integration point: the **`OrderRouter`**
(`app/services/execution/order_router.py`). It is pure orchestration (no FastAPI
dependency), deterministic across paper/shadow/live, fail-closed, and
idempotent.

## Modes

```python
class RouterMode(str, Enum):
    PAPER  = "paper"    # never calls the exchange; records a paper position
    SHADOW = "shadow"   # calls the exchange AND records a paper position (audit/diff)
    LIVE   = "live"     # calls the exchange; no paper record
```

Mode can be hot-swapped between calls (paper↔live) without reconstructing the
router.

## The pipeline

`OrderRouter.submit(req)` runs every safety primitive **in order**, fail-closed
(an uncaught guard error rejects the order — never fails open):

1. **Resolve** the underlying → instrument (`unknown_underlying` if not found).
2. **Composite safety gate** (`live_safety.assert_safe_to_trade`): kill-switch,
   daily-loss halt, and **idempotency** (duplicate minute-bucketed submissions
   return the prior `order_id`).
3. **Cooldown** per `(symbol, mode, direction)`.
4. **Portfolio bucket caps**.
5. **Microstructure veto**.
6. **Correlation penalty** — a *size multiplier* (not a veto); sized-to-zero
   rejects.
7. **Dispatch** by mode. Live additionally runs the **Greeks budget hard gate**
   (paper/shadow are intentionally not gated so you can learn from breaches).

The response is a structured `OrderRouterResponse` (`accepted`, `mode`,
`order_id`, `status` ∈ {filled, pending, duplicate, rejected}, `code`, `reason`,
…) that the API converts to HTTP.

## Dependencies are injected

The router takes a `RouterDeps` bundle of callables (`list_open_positions`,
`create_paper_position`, `cooldown_blocked`, `correlation_penalty`,
`portfolio_cap_breach`, `microstructure_veto`, `greeks_budget_gate`) and an
`instrument_resolver`. This makes the whole pipeline unit-testable with no
exchange — see `tests/test_order_router.py`.

## Adapter surface used

In live/shadow the router calls the adapter's order methods:
`get_product_id`, `set_margin_mode` (best-effort), `set_leverage` (best-effort),
`place_order` / `place_order_option`, plus `cancel_replace_stop` and
`market_reduce_close` for stop amendment and partial closes. These are exactly
the `TradingExchangeAdapter` contract — see [BROKERS.md](BROKERS.md).

## ExecutionAgent

`app/agents/execution_agent.py` wraps the router and emits bus events
(`OrderSubmitted` → `OrderAccepted`/`OrderRejected`) for PNL/reconciliation
subscribers, without duplicating any safety logic. See [docs/AGENTS.md](docs/AGENTS.md).

## Failure & retries

On an exchange error the router enqueues a `live_safety.RetryItem` (consumed by
an out-of-band worker) and returns `accepted=False, code="exchange_error"` with
the `retry_id`. The calling thread never blocks on retries.
