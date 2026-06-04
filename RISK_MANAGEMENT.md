# Risk management & compliance

Risk is **separate from execution**. There are two complementary layers:

## 1. The live safety pipeline (authoritative today)

Embedded in the `OrderRouter` via injected guards and `app/services/live_safety.py`:

| Guard | Rejects when |
|---|---|
| Kill switch | trading globally halted |
| Daily-loss halt | realized daily loss exceeds the limit |
| Idempotency | a duplicate (symbol, dir, type, size, minute) submission |
| Cooldown | within the cooldown window for `(symbol, mode, direction)` |
| Portfolio bucket caps | a bucket's exposure cap would be breached |
| Microstructure veto | spread/liquidity unacceptable |
| Correlation penalty | size scaled below the minimum (size multiplier) |
| Greeks budget (live only) | portfolio delta/gamma/vega budget breached |

Plus the portfolio drawdown **circuit breaker**
(`app/services/execution/circuit_breaker.py`, `DrawdownCircuitBreaker`) and the
execution-level circuit breaker — see `CLAUDE.md` for the `app.state` wiring
invariants. All guards are **fail-closed**: a guard that errors rejects the order.

## 2. The RiskEngine (separable, shadow-first)

`app/engines/risk/engine.py` is a standalone, registry-driven evaluator that
pulls "should this be allowed?" out of the execution path:

```python
from app.engines.risk.engine import RiskEngine, RiskDecision

engine = RiskEngine(rules=[
    ("kill_switch", lambda ctx: "kill_switch" if ctx["halted"] else None),
    ("max_dd",      lambda ctx: RiskDecision(allowed=False, code="max_dd") if ctx["dd"] > 0.2 else None),
])
decision = engine.evaluate(context)     # fail-closed, first breach wins
```

A rule returns `None` (pass), a `str` (breach code), or a `RiskDecision`.
Evaluation short-circuits on the **first breach** (ordering matters).

### Promotion path (zero-regression)

The engine is **not authoritative yet**. It ships with `shadow_compare()`:

```python
result = engine.shadow_compare(context, authoritative_allowed)
# {"agree": bool, "engine": RiskDecision, "authoritative_allowed": bool}
```

Run it **log-only** alongside the live pipeline, collect disagreements, and only
once parity is demonstrated do you point the `OrderRouter` deps at the engine and
retire the duplicated inline checks. The fail-closed semantics are preserved
exactly. `RiskAgent` (`app/agents/risk_agent.py`) is the event-emitting wrapper.

## Compliance hooks

- **Audit:** `app/services/derivatives_audit.py` records execution decisions.
- **Regulatory / position limits:** encode as `RiskEngine` rules so they are
  centralized, named, and testable.
- Every reject carries a **machine-readable `code`** for downstream alerting.
