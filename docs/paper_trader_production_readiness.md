# Paper Trader — Production Readiness (honest assessment)

**Status: production-grade *research/paper* infrastructure — NOT a live-money
trading system.** It is correct, crash-safe, and tested; it does not place real
orders, consume a real-time feed, or enforce live risk controls. Do not point it
at real capital until the "Remaining" section is closed.

## What the hardening fixed (this upgrade)

| Gap | Fix | Test |
|---|---|---|
| **Forming-bar repaint** (acting on an unclosed bar = lookahead) | `drop_forming_bar` — only closed bars are tradeable | `test_drop_forming_bar_*` |
| **No data-integrity guard** | `validate_universe` (staleness / gaps / completeness) + the runner **refuses to trade** on issues (`--force` to override) | `test_validate_universe_*` |
| **No funding cost** | conservative flat perp-funding drag by hold duration (`_funding_cost`, always a cost) | `test_funding_*` |
| **Non-atomic state writes** (crash mid-write corrupts the account) | `save_state` writes temp + `fsync` + `os.replace` | `test_save_state_is_atomic` |
| Paper drifting from the validated backtest | realized equity reuses `portfolio_equity_sized` (same sizing) | `test_paper_book_realized_matches_validated_sizing` |
| Live position state | `walk_positions` separates closed vs open, MTM'd | `test_*_open_position*` |

**Measured impact:** turning these on moved the as-of bar 12:00 → 08:00 (the
forming bar *was* being traded) and the realized headline **+85.4% → +71.6%** —
the earlier number was inflated by the repaint and missing funding. Hardening
made the result lower and *true*. 40 tests green.

## Remaining before real money (do NOT skip)

**Execution / integration**
- Real broker integration (Delta India order placement, auth, **secrets
  management** — no keys in code/config).
- Real-time data feed (websocket) instead of REST polling.
- **Order/position reconciliation** — broker truth vs internal state every cycle.

**Fill / cost realism**
- Real per-venue maker/taker fees, **real funding rates** (currently a flat
  conservative assumption), and realistic fills (slippage + gap-through). The
  live path already has `realistic_stop_fill` / next-bar-open logic from the
  backtest-honesty work — the paper trader does idealized first-touch.

**Risk controls (live)**
- Drawdown circuit-breaker / kill-switch, position & gross-exposure limits,
  per-trade max loss. (The app has `DrawdownCircuitBreaker` — wire it in.)
- Live-vs-backtest **divergence monitor** (alert when forward ≠ expected).

**Operations**
- Structured logging + metrics; alerting on fills, errors, DD breaches.
- Scheduler/daemon with a **file lock** and exactly-once per-bar accounting.
- Idempotent runs (re-run within a bar must not double-count).

**Strategy gate (the real blocker)**
- The book is **not deflation-provable** (DSR 0.166 < 0.5). Before real capital
  it needs either materially more forward (cross-regime) evidence or a stronger
  edge. 2025–26 is one macro (downturn) regime; the live risk is regime change.

## Honest grade

- **Correctness of the numbers:** production-grade (repaint fixed, funding
  modelled, data validated, deterministic vs backtest). ✅
- **Operational safety of the state:** production-grade (atomic, tested). ✅
- **Live trading capability:** **not built** — no broker, no real-time feed, no
  live risk controls. ❌
- **Capital-readiness of the edge:** **not proven** (DSR < 0.5). ❌

Verdict: trustworthy paper/research engine you can run on a schedule to
accumulate an honest forward record. It is *one well-scoped project* away from a
live-trading system, and that project should not start until the edge earns more
forward evidence.
