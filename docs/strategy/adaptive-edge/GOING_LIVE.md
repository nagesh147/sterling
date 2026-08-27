# Going live — what runs, and what it is allowed to do

The engine is live. It scans, forecasts, measures, records, and manages
positions. It is **not** permitted to open one, and it will not be until its own
record says it should.

That is the design, not a limitation waiting to be removed.

## Why the gate exists

Every offline conclusion about this strategy failed, and each time for the same
reason.

| Attempt | Result | What was missing |
|---|---|---|
| Directional model (F-102) | no edge, 0 directional calls on 50k bars | nothing — direction is not there |
| Long straddle | needs implied below realised; index options rarely offer it | option prices |
| Short volatility | study measured a payoff mostly not listed | option prices |

The pattern is the third column. Implied volatility is the fact the strategy
turns on, and **no store here holds option price history** — not the local
SQLite, not the pendrive lake, which is index and cash bars only.

It is trivially available live. So the engine measures it every scan, whether or
not it intends to trade, and the gate opens on that record rather than on an
argument from history.

## What runs every scan

```text
bars          -> volatility forecast          (validated: 119/120 instruments, +0.29 OOS)
option chain  -> implied volatility           (inverted from the quoted ATM straddle)
              -> implied / realised           <- the fact every study was missing
              -> defined-risk structure priced at the MEASURED ratio
              -> recorded, resolved after the horizon
```

Nothing about that is conditional on intending to trade. The gate can only ever
open by learning from decisions the engine declined to act on.

## What the gate requires

Three bars, each present because a specific way of being wrong was already met
while building this:

* **400 observations.** A short-volatility payoff is heavily left-skewed, so a
  small sample is systematically flattering — the losses have not happened yet.
* **20 distinct sessions.** Volatility clusters. Four hundred readings from three
  days describe one regime, not a strategy.
* **A positive 95% lower bound, not a positive mean.** The mean of a sample that
  could equally have been noise is not evidence, and the mean cannot tell them
  apart. The interval is computed on the session count rather than the reading
  count, because intraday readings inside one session are not independent.

```bash
curl -s localhost:8000/api/v1/config/adaptive-edge/evidence | jq
```

Reports observations, sessions, mean, lower bound, median implied/realised, win
rate, and what is still outstanding.

## What happens if you try to arm before then

```json
{"ok": false, "reason": "evidence gate: 137 of 400 observations — a left-skewed payoff flatters a small sample"}
```

The gate fails closed on an unreadable store as well: "cannot tell" never
resolves to "go ahead".

## What is already enforced regardless

* Live execution is refused while the strategy is unpromoted, whatever the
  account says.
* Every structure this engine prices is defined-risk. `wing_sd <= 0` raises;
  there is no naked path.
* Entry, protection, exit, reconcile and square-off are complete and tested —
  the machinery is ready for the moment the evidence is.

## What would make it trade

Run it. Twenty sessions of scanning produces the record. If the measured
implied-to-realised premium and the outcomes clear the bar, the gate opens by
itself and the engine trades on evidence it gathered rather than on a backtest
of a payoff that was not for sale.

If they do not clear it, the gate stays shut — and that is the same answer,
arrived at honestly, for a fraction of the money that finding out the other way
would have cost.
