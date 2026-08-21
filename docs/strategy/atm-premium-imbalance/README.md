# ATM Premium Imbalance

**What it does.** At the index option market open, compares the at-the-money
call and put premiums, buys whichever is cheaper, and exits at the entry fill
plus a fixed +15 points. One trade per session. Both directions are observed:
the call is bought when it is cheaper, the put when it is.

**What it does not do.** No indicators. No stop loss. No time stop. No
convergence exit. No auto-sizing. It is one comparison and one target.

## Documents

| File | Contents |
|---|---|
| [A230_STRATEGY_CONTRACT.md](A230_STRATEGY_CONTRACT.md) | The rules the code must honour |
| [A231_FORENSIC_EVIDENCE_MATRIX.md](A231_FORENSIC_EVIDENCE_MATRIX.md) | Every rule traced to the frame it came from |
| [A232_PARAMETER_PROVENANCE.md](A232_PARAMETER_PROVENANCE.md) | Where each default came from, and what was rejected |
| [A265_ARCHITECTURE.md](A265_ARCHITECTURE.md) | Modules, data flow, state machines, failure paths |
| [A266_RUNBOOK.md](A266_RUNBOOK.md) | Operating it, and the live-readiness gate |

## Provenance, stated plainly

This strategy was reverse-engineered from four screen recordings of a
third-party bot. It was not designed here and it has not been validated.

Two constants are directly evidenced and identical across two builds of the
source bot:

- **target = entry fill + 15.0 points**
- **exit limit = best bid − 0.50**

Everything about the *entry price* was operator-supplied per session (the source
bot read a hand-maintained `strike_prices.txt`), so it is a configurable policy
here rather than a discovered rule. The default, `best_ask + buffer`, expresses
the *mechanism* that was observed — a limit deliberately through the market so it
fills like a market order — without hard-coding one morning's numbers.

The written specification's `entry_buffer_points = 10.25` is **correct**, and this
README previously said otherwise. The 2026-08-20 entry block prints
`First Tick Price : 102.85`, `Buffer : 10.25`, `Order Price : 113.1` under a
heading of `FIRST-TICK ENTRY ATTEMPT 1/3`. There are two real entry paths — an
operator price file, and `first_tick + buffer` — and the two sessions I first
compared happened to exercise different ones. See A232 for the full correction.

## Parameters

Defaults reproduce the observed baseline. `enabled` is false.

| Setting | Default | Provenance |
|---|---|---|
| Underlying | SENSEX | observed |
| Expiry | NEAREST | observed (monthly traded on a non-expiry day) |
| Strike | nearest listed, ties to lower | observed |
| Quote mode | COMPATIBILITY | observed behaviour |
| Entry price | `first_tick + 10.25`, capped at upper circuit (or an operator price file) | observed |
| Max entry attempts | 3 | observed |
| Target | +15.0 points off the fill | observed |
| Exit | best bid − 0.50 | observed |
| Stop / time stop | off | none observed |
| Trades per session | 1 | observed |

## Risk

Buying a same-day-expiry at-the-money option at the open is one of the most
volatile trades available. The premium can halve in seconds; in the observed
V17 session the bought leg fell from 133 to 86 before reaching its target. The
maximum loss is the whole premium.

The source bot had no stop, no daily-loss limit, no position reconciliation and
no quote-freshness gate. Those absences are not evidence that we may omit them —
`max_quote_age_ms` and `daily_loss_limit_inr` are ours, and the missing
broker-side protection for an open position is one reason live is blocked.

## Data requirements

Per-leg option ticks with LTP **and** L1 depth (bid/ask), plus the index LTP.
Timestamps must be preserved per leg: the asynchronous CE/PE cache is the
behaviour being reproduced, and a synchronised snapshot would erase it.

Tick data is authoritative for replay. One-minute bars can support broad
validation but cannot evidence asynchronous tick behaviour.

## Limitations

- **Three sessions with a decodable outcome, all winners**, selected by whoever
  chose what to record. That is selection bias, not a result.
- The latest recording's entry block was not legible; its strike and entry order
  price remain `UNRESOLVED` (A231).
- The 2026-08-21 session's strike is unresolved (the notification truncates it).
- Three rules in the contract were corrected by later recordings after earlier
  ones had agreed. Small samples mislead about mechanics, not just profit.
- The source bot ran on Upstox. Sterling executes through Kite, which does serve
  BSE F&O. Order-id and instrument-key formats in the evidence are Upstox's.
