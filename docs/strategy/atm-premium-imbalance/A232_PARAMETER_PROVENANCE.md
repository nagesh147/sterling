# A232 — Parameter Provenance

Every tunable in `ATMPremiumImbalanceConfig`, with where its value came from.
No value in this table is "optimized" — none has been through a walk-forward or
a deflated-Sharpe gate. Provenance vocabulary:

- `OBSERVED` — printed verbatim in a recording.
- `OBSERVED-DERIVED` — not printed, but forced by printed values via an identity.
- `RECONSTRUCTED` — inferred from a single arithmetic coincidence. Weak.
- `REJECTED` — was proposed, evidence contradicts it.
- `SterlingDEFAULT` — our own safety default; no counterpart in the source bot.

| Parameter | Value | Provenance | Basis |
|---|---|---|---|
| `underlying` | `SENSEX` | OBSERVED | every recording |
| `strike_policy` | `ATM_NEAREST` | OBSERVED-DERIVED | V17 printed `Strike : 77600` with `SENSEX LTP : 77638.86`; 77600 is the nearest 100-pt strike (A231/M5) |
| `expiry_policy` | `SAME_DAY` | RECONSTRUCTED | never printed. Inferred from V1/V17 straddle magnitude (~336–350 pts). V04 contradicts it (A231/M7, M8) |
| `signal_rule` | buy cheaper leg | OBSERVED | V17: CE 167.50 < PE 214.85 → bought CE |
| `difference_definition` | `PE − CE` | OBSERVED | holds on every legible line in all four recordings (A231/Q2) |
| `minimum_difference` | `0.0` (disabled) | OBSERVED-DERIVED | V17 entered on 47.35 with no threshold line printed |
| `target_points` | **`15.0`** | OBSERVED | literal `Target Hit (+15)` in V17 **and** V1; and V17's trigger fired at 149.10 vs entry 133.40 + 15 = 148.40 |
| `target_basis` | broker average fill | OBSERVED | V17 `Average Price 133.4` = `Entry : 133.4`, while the requested limit was 288.75 |
| `exit_buffer_points` | **`0.50`** | OBSERVED | V17 `149.2 → 148.7`; V1 `127.1 → 126.6`. Identical across two builds |
| `exit_reference` | `BEST_BID` (live L1 depth) | OBSERVED | V17/V1 `EXIT — LIMIT SELL AT BEST BID − BUFFER` |
| `max_entry_attempts` | `3` | OBSERVED | V17 `ENTRY ATTEMPT 1/3 — LIMIT BUY` |
| `max_trades_per_session` | `1` | OBSERVED | all recordings shut the process down after one round trip |
| `session_start` | `09:15 IST` | OBSERVED | `Waiting for Market Open (09:15 IST)...` |
| `quantity` | operator-entered | OBSERVED | `Enter Quantity : 100` (V1), 20 (V17, derived from `PnL 469.0 / 23.45`) |
| `entry_price_source` | `MANUAL_FILE` → cap at upper circuit | OBSERVED | V17 `Using manual strike price from strike_prices.txt : 288.75 (strike 77600CE)`, `MPP (Upper Circuit) : 1745.45`, `Calculated Order Price (before cap) : 288.75` |
| ~~`entry_buffer_points`~~ | ~~`10.25`~~ | **REJECTED** | See below. |
| `stop_enabled` | `false` | OBSERVED-DERIVED | no stop line, no stop field, in any recording |
| `max_hold_seconds` | `0` (disabled) | OBSERVED-DERIVED | no time-stop observed |
| `max_quote_age_ms` | `2000` | SterlingDEFAULT | the source bot has no freshness gate; we will not ship without one |
| `max_ce_pe_skew_ms` | `1000` | SterlingDEFAULT | needed for the SYNCHRONIZED research view only |
| `daily_loss_limit` | required | SterlingDEFAULT | Sterling risk invariant; absent from the source bot |

## Why `entry_buffer_points = 10.25` is rejected

The supplied specification derived it as `113.10 − 102.85` from V1 —
"entry order price = first tick + 10.25".

V17 falsifies the relationship outright, because V17 prints every term:

```
CE LTP (first tick)        : 167.50
Best Ask (live depth)      : 167.50
Order Price (sent)         : 288.75      <- from strike_prices.txt
Average Price (fill)       : 133.40      <- what we actually paid
```

- `fill − first_tick   = −34.10`
- `order − first_tick  = +121.25`
- `order − best_ask    = +121.25`

There is no `+10.25`, and no constant that reconciles V17 and V1. The order
price in V17 came from a file; the fill came from the opening auction. In V1,
`113.10` is a **fill**, so `113.10 − 102.85 = 10.25` is measured
open-auction slippage between the first observed tick and the execution — a
market outcome, not a strategy input.

Encoding 10.25 as an entry buffer would hard-code one morning's slippage into a
live order price. It is therefore not offered as a default. The entry-price
policy is a pluggable enum (see A230) so the rejected model remains
*reproducible for replay* under `FIRST_TICK_PLUS_BUFFER` without being
reachable by default.

## Consequence for the strategy's identity

The only two numbers that are stable across builds and arithmetically forced are
`target_points = 15.0` and `exit_buffer_points = 0.50`. Everything about the
entry *price* is operator-supplied, per-strike, and per-session. The alpha claim
therefore rests entirely on: *buy the cheaper ATM leg at the open and take +15
points.* That is what must be validated — not the entry price mechanics.
