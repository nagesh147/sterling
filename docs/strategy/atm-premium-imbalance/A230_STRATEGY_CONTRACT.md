# A230 — ATM Premium Imbalance — Strategy Contract

- **Strategy id**: `atm_premium_imbalance`
- **Display name**: ATM Premium Imbalance
- **Status**: `DISABLED` — live-blocked until A274's gate passes.
- **Source of truth for evidence**: [A231](A231_FORENSIC_EVIDENCE_MATRIX.md)
- **Source of truth for values**: [A232](A232_PARAMETER_PROVENANCE.md)

This strategy is reconstructed from recordings of a third-party bot. It does not
share, alter or read any Adaptive Edge state.

## 1. Purpose

At the instant the index option market opens, buy whichever ATM leg is cheaper
and take a fixed +15 points. One trade, then stop.

The alpha claim is exactly that sentence. Everything else in this document is
execution mechanics.

## 2. Universe

| Field | Value |
|---|---|
| Underlying | Index. `SENSEX` is the only one observed; the engine accepts any configured index. |
| Legs considered | ATM CE and ATM PE of the same strike and expiry |
| Strike | nearest **available listed** strike to the underlying LTP, deterministic tie-break to the lower strike |
| Expiry | `SAME_DAY` by default (see A232 — `RECONSTRUCTED`, not observed) |

## 3. Quote model

Three views over the same tick stream. **One signal implementation** consumes a
`PremiumPairView`; the mode only decides which view is produced.

| Mode | CE/PE source | Purpose |
|---|---|---|
| `COMPATIBILITY` | independently cached last LTP per leg | reproduces the source bot exactly |
| `SYNCHRONIZED` | CE/PE aligned within `max_ce_pe_skew_ms` | research: does the async cache itself create the edge? |
| `EXECUTABLE` | CE ask / PE ask | production: what could actually be bought |

`COMPATIBILITY` is the default and must never be silently replaced by another
mode. Legs update **independently** — a tick may move one leg or both, and the
difference is recomputed from whatever pair is currently cached (A231/Q3).

`difference = PE − CE` — signed, PE minus CE (A231/Q2). Not `abs`.

## 4. Signal

```
if ce < pe:  BUY CE
elif pe < ce: BUY PE
else:         NO_TRADE
```

No indicator, no bar, no lookback, no OI, no PCR. Gates are liveness only:
both legs quoted, same strike, same expiry, quotes fresher than
`max_quote_age_ms`, session open, flat, risk authorized.

`minimum_difference` defaults to `0.0` (disabled). A PE-side entry was never
observed (A231/S4); symmetry is assumed and is flagged `UNRESOLVED`.

## 5. Entry

Marketable `LIMIT BUY`, up to `max_entry_attempts = 3`.

Limit price is produced by a pluggable policy, then **capped at the
instrument's upper circuit (MPP)** in every case:

| Policy | Price | Status |
|---|---|---|
| `MARKETABLE_ASK` | `best_ask + entry_buffer_points` | **DEFAULT** |
| `PERCENT_THROUGH` | `best_ask × (1 + entry_through_pct)` | research |
| `MANUAL_FILE` | operator table keyed by `{strike}{CE\|PE}` | reproduces V17 verbatim |
| `FIRST_TICK_PLUS_BUFFER` | `first_tick + entry_buffer_points` | **REJECTED by evidence** (A232). Retained only so the supplied spec's model stays replayable. Never a default. |

The limit is a *fill-guarantee device*, not a price target: the observed bot sent
288.75 against a 167.50 ask (A231/E4). Choosing a limit through the market does
not change the signal.

### Accounting invariant

> The entry price used for the target, for P&L and for every report is the
> **broker average fill**. Never the requested limit, never the first tick.

V17 makes the distinction unmissable: requested 288.75, filled 133.40, and every
downstream number used 133.40 (A231/E6).

### Retry state machine

```
ATTEMPT n  ──submit──▶  status?
                          ├─ FILLED   ──▶ use this fill, stop
                          ├─ REJECTED ──▶ ATTEMPT n+1
                          └─ UNKNOWN / TIMEOUT
                                └──▶ RECONCILE against broker first
                                        ├─ found FILLED     ──▶ use that fill
                                        ├─ found live       ──▶ wait, do not resubmit
                                        └─ confirmed absent ──▶ ATTEMPT n+1
```

An `UNKNOWN` order must never be followed by a new submission before
reconciliation. The source bot printed `Order not found after retries.` and
carried on (A231/E7); we do not copy that.

## 6. Exit

- Trigger: `selected_leg_price >= entry_fill + target_points`, `target_points = 15.0`.
- Order: `LIMIT SELL` at `best_bid − exit_buffer_points`, `exit_buffer_points = 0.50`.
- Both constants are `OBSERVED` and identical across two builds (A231/X1, X3).

Trigger, order price and fill are three separate recorded facts (A231/X4):

```
trigger_price, trigger_ts        <- the tick that crossed the target
exit_order_price                 <- best_bid − 0.50
exit_fill_price, exit_fill_ts    <- broker average
slippage_vs_target = exit_fill_price − target_price
```

V17: trigger 149.10, order 148.7, fill 156.85 — a fill 8.45 points *above* the
target. A design that collapses these into one number cannot represent the
observed trade.

`Points = exit_fill − entry_fill`. `PnL = Points × quantity`, where quantity is
total contracts, not lots (A231/X6).

## 7. Stops

`stop_enabled = false`, `max_hold_seconds = 0`. No stop or time-stop was
observed (A231/X7). The infrastructure exists so research can enable them
without touching the lifecycle; live use requires risk-policy approval.

## 8. Session

`max_trades_per_session = 1`. After the round trip: stop monitoring, close the
socket, go flat-and-idle for the day.

The source bot terminated its own process and crashed in its post-trade report
(A231/L5). We stop the strategy, not the application, and we do not reproduce
the crash.

## 9. Risk

Shared Sterling risk infrastructure, not strategy-local. Minimum gates: one
active position, one active entry order, one active exit order, max quantity,
max monetary risk, daily loss limit, quote freshness, broker health, and
reconciliation clean. The source bot has none of these; their absence is not
evidence that we may omit them.

## 10. Failure behaviour

| Condition | Behaviour |
|---|---|
| Quote stale beyond `max_quote_age_ms` | no entry; if in position, exit path stays armed |
| One leg never quotes | no signal (both legs required) |
| Expiry or strike unresolvable | strategy refuses to arm; loud error |
| Order status `UNKNOWN` | block new orders until reconciled |
| Reconciliation `DIVERGED` | halt strategy, require operator |
| WebSocket drop while flat | reconnect, re-subscribe, re-arm |
| WebSocket drop while in position | reconnect; exit on broker-side protection, never on a stale cache |

## 11. Not in scope

Convergence ("meeting point") exit, any indicator, multi-leg structures,
overnight holds, and any auto-sizing. The project folder name in the earliest
recording was `SENSEX_MEETING_POINT_BOT`, but the latest build is target-based;
convergence is retained only as a research-only exit policy.

## 12. Version

`contract_version = "A230.1"`. Any change to §4, §5's accounting invariant, §6
or §8 is a new contract version and re-runs the A274 gate.
