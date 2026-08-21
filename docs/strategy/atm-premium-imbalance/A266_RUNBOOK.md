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

### Arming

```
POST /api/v1/config/atm-premium-imbalance/arm
```

Resolves the ATM pair, subscribes both legs to the Kite ticker and arms the
session. Idempotent for the day — arming twice returns `already_armed` rather
than creating a second session that could place a second entry.

There is deliberately **no polling loop**. The strategy enters on the first
usable tick after the open (the recordings show the decision 1 ms after that
tick), which a 1-second poll cannot express. It therefore hangs off the same
Kite tick fan-out the exit monitor uses, so it runs whether or not any UI is
connected. Arming is the only scheduled act, and it is manual.

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
| Strategy armed but never signals | Read `blockers`, then the signal reason: `stale_quote`, `stale_session_quote`, `undatable_quote`, `equal_premiums`, `no_quote_pair`, `below_minimum_difference`. |
| Reason `stale_session_quote` | A leg's last trade is stamped **before** today's open — a carried-over price. Correct refusal: this is the fault that made the observed bot price 416.90 into a 356.70 market. It clears itself on the first real trade. |
| Reason `undatable_quote` | The feed sent no `last_trade_time`, which only happens outside FULL mode. Live refuses to price off a quote it cannot date. Check the subscription mode. |
| `EXECUTABLE` mode never produces a view | One leg has no ask. There is no LTP fallback by design. |
| Trade state `reconciliation_required` | An order's outcome is genuinely unknown. **Do not restart the strategy.** Reconcile the broker's order book and positions by hand first; the state machine is refusing to guess. |
| `halt: protection_cancel_failed` | The resting protective sell could not be cancelled, so the strategy refused to send a second sell. Cancel it by hand, then check the position. Two live sells against one long option is a short position. |
| `halt: protection_unacknowledged` | The protective order was not acknowledged. The position may be protected, unprotected, or double-protected. Check the broker's order book before doing anything else. |
| Entry attempts exhausted | Three attempts were rejected. No position was opened. Check reject reasons on the attempt records. |
| Exit filled far from the target | Normal and recorded. `slippage_vs_target` is stored; the observed V17 trade filled 8.45 points *above* its target. |

## WebSocket / feed loss

- **While flat**: reconnect, re-subscribe both legs, re-arm. The cache refuses
  to serve a view until both legs are present again.
- **While in position**: reconnect. Do not exit off a stale cache — the exit
  trigger reads live quotes, and a stale one can fabricate a target hit. The
  backstop is `protection_mode`: with `RESTING_TARGET_LIMIT` or `GTT` the
  exchange holds a sell at the target, so a dropped socket (or a dead process)
  still closes the position. `NONE` reproduces the observed bot and has no
  backstop at all, which is why live refuses it.

## Replay against real Kite data

```bash
cd backend && python3 -m app.services.atm_premium_imbalance_replay 2026-08-20
```

Resolves the traded contract's Kite token from the offline lake's instrument
snapshot (which preserves tokens for contracts that have since expired), pulls
minute bars from Kite historical for both legs, and compares them against what
the recording printed. Requires a **live Kite session**; Kite access tokens
expire daily.

What it checks: the index open and the ATM strike it implies, which leg was
cheaper, the selected leg's first tick, the order price the policy computes from
it, whether the target was reached and in which minute, and whether the recorded
fills lie inside their bars.

What it cannot check: the fills themselves, the bid the exit was priced off, and
tick ordering. Minute bars are a four-way summary of sixty seconds. Fills are
*bracketed* — a fill outside its bar's range is reported as a mismatch, which is
the strongest statement bars support.

Sessions: `2026-08-20` and `2026-08-21` are replayable. `2026-07-30` is **not** —
that expiry had already lapsed when the instrument snapshot was taken, so its
token cannot be resolved.

## Replay against the recordings

The golden trades are the offline replay harness:

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
- [x] **Broker-side protection for an open position** — `protection_mode` parks a sell at the target on the exchange; `validate()` refuses live without it
- [x] **A tick-driven runner** with market-hours gating, per-tenant locking and a bounded intent loop
- [ ] **Risk integration**: the daily-loss breaker and premium-at-risk ceiling are config fields but are not yet enforced by the runner; position reconciliation on startup is not implemented
- [ ] **Historical tick replay** over more than two sessions — two winning trades is not evidence of an edge
- [ ] **Walk-forward / deflated-Sharpe evaluation.** Two observed winners prove the mechanics reproduce, nothing about expectancy.
- [ ] Paper-trading parity run over a full session

## What the evidence does and does not support

It supports: the mechanics reproduce exactly. Two independent sessions, every
printed number, cross-checked against the broker's own P&L.

It does not support: that the strategy makes money. Every recorded session with
a decodable outcome was a winner, and the sessions were chosen by whoever decided
what to record. Selection bias on a sample this small is not a result. Treat
`target_points` and `exit_buffer_points` as faithfully reproduced constants, not
as optimised parameters.

Also worth remembering: two rules in this contract were *corrected* by the fifth
recording after four had agreed. Small biased samples mislead about mechanics as
readily as about profitability.
