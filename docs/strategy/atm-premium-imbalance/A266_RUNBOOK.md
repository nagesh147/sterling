# A266 — Operations Runbook

## Current status

**Live execution is blocked.** `enabled` defaults false and
`config.validate()` refuses `execution_mode="live"` unless
`quote_mode="EXECUTABLE"`, a positive `quantity` is set, and neither a
research-only entry policy nor a research-only exit policy is selected. The
readiness gate below has not been run.

## Start / stop

Settings live at **Kite → Settings → Signal engines → ATM Premium Imbalance**,
served by:

```
GET  /api/v1/config/atm-premium-imbalance
PUT  /api/v1/config/atm-premium-imbalance
GET  /api/v1/config/atm-premium-imbalance/snapshot
```

Turning it on is the `enabled` switch, applied through the draft bar. The
snapshot endpoint is the one to read when it is not doing anything: it lists
every blocker (disabled, quantity unset, instrument resolution failure) rather
than silently reporting armed.

Nothing is scheduled yet — there is no background runner. This is deliberate:
an unvalidated strategy should not have a loop that can fire.

## Paper vs live

Identical strategy object, identical state machine, identical intents. Only the
component that services intents changes. `execution_mode` is a config field, not
a code path.

Before live is even considered, `quote_mode` must be `EXECUTABLE`. Pricing a
real order off an independently cached LTP is the behaviour `COMPATIBILITY`
exists to *reproduce*, not to trade.

## Common situations

| Situation | What to do |
|---|---|
| Snapshot shows `instrument resolution failed` | Check an active Kite account exists and is connected. The BFO dump is cached 15 min; a fresh session may need one refresh. |
| `no contract expires today` | Expected under `SAME_DAY` on a non-expiry day. It refuses rather than sliding to the next expiry. Change the policy deliberately if that is what you want. |
| Strategy armed but never signals | Read `blockers`, then the signal reason: `stale_quote`, `equal_premiums`, `no_quote_pair`, `below_minimum_difference`. |
| `EXECUTABLE` mode never produces a view | One leg has no ask. There is no LTP fallback by design. |
| Trade state `reconciliation_required` | An order's outcome is genuinely unknown. **Do not restart the strategy.** Reconcile the broker's order book and positions by hand first; the state machine is refusing to guess. |
| Entry attempts exhausted | Three attempts were rejected. No position was opened. Check reject reasons on the attempt records. |
| Exit filled far from the target | Normal and recorded. `slippage_vs_target` is stored; the observed V17 trade filled 8.45 points *above* its target. |

## WebSocket / feed loss

- **While flat**: reconnect, re-subscribe both legs, re-arm. The cache refuses
  to serve a view until both legs are present again.
- **While in position**: reconnect. Do not exit off a stale cache — the exit
  trigger reads live quotes, and a stale one can fabricate a target hit. Broker-
  side protection is the correct backstop, and it does not exist yet, which is
  one reason live is blocked.

## Replay

The golden trades are the replay harness:

```bash
cd backend && PYTHONWARNINGS=ignore python3 -m pytest tests/engines/atm_premium_imbalance/ -q
```

`test_golden_trades.py` drives the live strategy object with the tick sequences
decoded from the recordings and asserts the printed numbers. Add a new recording
as a new case there — not as a new engine.

## Live-readiness gate (A274)

All must hold. None may be waived silently.

- [x] Unit, property and golden tests pass (`tests/engines/atm_premium_imbalance/`)
- [x] V17 golden trade reproduces every printed field
- [x] V1 golden trade reproduces the broker-confirmed P&L
- [x] Duplicate-order protection proven (`UNKNOWN` never resubmits)
- [x] Full backend suite green with the strategy present
- [x] Frontend typecheck and tests green
- [ ] **Broker-side protection for an open position** (no stop exists; a feed loss while long is currently unprotected)
- [ ] **A background runner** with market-hours gating and per-tenant locking
- [ ] **Risk integration**: daily-loss breaker, premium-at-risk sizing, position reconciliation on startup
- [ ] **Historical tick replay** over more than two sessions — two winning trades is not evidence of an edge
- [ ] **Walk-forward / deflated-Sharpe evaluation.** Two observed winners prove the mechanics reproduce, nothing about expectancy.
- [ ] Paper-trading parity run over a full session

## What the evidence does and does not support

It supports: the mechanics reproduce exactly. Two independent sessions, every
printed number, cross-checked against the broker's own P&L.

It does not support: that the strategy makes money. Both recorded sessions were
winners, selected by whoever chose what to record. Selection bias on a sample of
two is not a result. Treat `target_points` and `exit_buffer_points` as faithfully
reproduced constants, not as optimised parameters.
