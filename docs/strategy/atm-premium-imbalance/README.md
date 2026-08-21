# ATM Premium Imbalance

**What it does.** At the index option market open, compares the at-the-money
call and put premiums, buys whichever is cheaper, and exits at the entry fill
plus a fixed +15 points. One trade per session.

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

The written specification's `entry_buffer_points = 10.25` is **rejected**. It was
derived from a single arithmetic coincidence in one recording; the other
recording prints every term and falsifies it. See A232.

## Parameters

Defaults reproduce the observed baseline. `enabled` is false.

| Setting | Default | Provenance |
|---|---|---|
| Underlying | SENSEX | observed |
| Expiry | SAME_DAY | reconstructed — never printed |
| Strike | nearest listed, ties to lower | observed |
| Quote mode | COMPATIBILITY | observed behaviour |
| Entry price | best ask + 0.50, capped at upper circuit | mechanism observed, formula ours |
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

- **Two sessions of evidence, both winners**, selected by whoever chose what to
  record. That is selection bias, not a result.
- The latest recording's entry block was not legible; its strike and entry order
  price remain `UNRESOLVED` (A231).
- Same-day expiry is inferred from premium magnitudes, not observed.
- A put-side entry was never observed; symmetry is assumed.
- The source bot ran on Upstox. Sterling executes through Kite, which does serve
  BSE F&O. Order-id and instrument-key formats in the evidence are Upstox's.
