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

## Second hardening pass — operational safety (this upgrade)

Everything above keeps the *numbers* honest; this pass keeps the *account* safe
to run unattended. New isolated, tested primitives in `study/paper_safety.py`,
wired into the runner (`paper_trader.main`):

| Gap | Fix | Test |
|---|---|---|
| **No drawdown kill-switch** (account could keep adding risk in a slide) | `update_kill_switch` + `apply_kill_switch` — trips FLAT (drops open positions, equity → realized-only) when forward equity falls `--dd-threshold` (def 25%) below the high-water-mark; **latches with hysteresis**, re-arms only within `--dd-recover` (def 10%) of peak; `--reset-breaker` clears manually | `test_kill_switch_*`, `test_apply_kill_switch_*` |
| **No concurrency guard** (two cron firings could corrupt state) | `run_lock` — exclusive non-blocking `flock`; a second runner skips | `test_run_lock_is_exclusive` |
| **Redundant intra-bar work / re-alerts** | `should_run` — exactly-once-per-bar: do nothing until a new 4h bar closes (`asof` persisted in state) | `test_should_run_only_on_new_closed_bar` |
| Unattended operation | `study/paper_cron.sh` — safe-to-over-fire wrapper (lock + new-bar guard make it a no-op between bars); documented crontab line | (shell wrapper) |

**Verified live:** first run armed the breaker at a new high-water-mark
($882.95, drawdown +0.0%); an immediate `--no-refresh` re-run printed *"No new
closed bar since last run … nothing to do"* (exactly-once working); breaker +
`asof` persisted to `state.json`. **49 tests green** (9 new safety tests).

The breaker is a **paper-grade** control: it acts on the recomputed paper book,
not live broker equity. For real money it must be re-tied to the broker's
truth — but the trip/latch logic and the run-safety are now in place and tested.

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
- ~~Drawdown circuit-breaker / kill-switch~~ ✅ **done** (paper-grade; re-tie to
  broker equity for real money). Still missing: position & gross-exposure
  limits, per-trade max-loss enforcement on the *live* path.
- Live-vs-backtest **divergence monitor** (alert when forward ≠ expected).

**Operations**
- ~~File lock + exactly-once per-bar~~ ✅ **done** (`run_lock` / `should_run`);
  ~~scheduler wrapper~~ ✅ **done** (`paper_cron.sh`).
- Structured logging + metrics; alerting on fills, errors, DD breaches (the cron
  wrapper logs to a file — not structured/alerting yet).

**Strategy gate (the real blocker)**
- The book is **not deflation-provable** (DSR 0.166 < 0.5). Before real capital
  it needs either materially more forward (cross-regime) evidence or a stronger
  edge. 2025–26 is one macro (downturn) regime; the live risk is regime change.

## Honest grade

- **Correctness of the numbers:** production-grade (repaint fixed, funding
  modelled, data validated, deterministic vs backtest). ✅
- **Operational safety of the state:** production-grade (atomic writes, exclusive
  run-lock, exactly-once-per-bar, drawdown kill-switch — all tested). ✅
- **Live trading capability:** **not built** — no broker, no real-time feed. The
  kill-switch is paper-grade (acts on the recomputed book, not broker equity);
  no live position/exposure limits or divergence monitor. ❌
- **Capital-readiness of the edge:** **not proven** (DSR < 0.5). ❌

Verdict: trustworthy paper/research engine you can run on a schedule to
accumulate an honest forward record. It is *one well-scoped project* away from a
live-trading system, and that project should not start until the edge earns more
forward evidence.
