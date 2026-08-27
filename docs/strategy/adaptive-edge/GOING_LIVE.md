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

---

# The paper run — 2026-08-27

Ran the production modules over the pendrive lake (NIFTY 50, 45,750 minute bars,
122 sessions) to answer how often the gate clears. It separates cleanly into a
part the lake can settle and a part only a live session can.

## What the lake settles: the tape filter

| | |
|---|---|
| non-overlapping decision points | 1,462 |
| passed the forecast-percentile floor | **391 = 26.7%** |

That figure is independent of option prices — it is purely how often the tape is
in the top of its own forecast distribution. **Roughly one decision in four
reaches the point where premium even matters.**

Over 122 sessions that is about three decisions a session on one underlying, so
the evidence gate's 400-observation bar is around four to five months on NIFTY
alone, or a few weeks across a normal multi-index universe.

## What the lake cannot settle, and why the replay's P&L was discarded

The replay also produced P&L for each implied-to-realised ratio, and those
numbers are not reported here because they are wrong in a way already documented:
`evaluate()` derives its credit from `sqrt(horizon)`, which prices an option
**expiring at the horizon**. Real options mostly do not, and a dated one held for
thirty minutes collects a fraction of a percent of its premium rather than all
of it.

That assumption has now been removed from anything that can trade:

* `from_quotes()` is the runtime path. The credit is the **quoted straddle**, so
  no assumed ratio reaches a decision.
* It **refuses** a contract whose life outlasts the hold — `minutes_to_expiry >
  horizon + 1` raises. Premium collection is only the payoff when the option
  settles at the end of the hold; anything else is a mark-to-market on gamma and
  theta, a different trade with a different sign.
* `evaluate()` remains for study work and its docstring says what it models.

The practical consequence: **this strategy trades near-expiry contracts held to
settlement.** That is not a preference, it is the only configuration in which the
payoff being priced is the payoff being taken.

## What is still needed for the real answer

Option prices, which exist in no store here. The lake's catalogue *knows* the
contracts — 17,881 NIFTY calls and 17,964 puts across eight expiries, with lot
sizes — but **zero option bars have been downloaded**, and the stored Kite
session has expired.

```text
kitelake catalogue : 92,065 CE/PE instruments known
option bars in lake: 0
kite session       : expired (tokens die at 06:00 IST)
```

Reconnect Kite and two things become possible at once: the lake can backfill
option bars for a proper historical answer, and the live engine starts recording
real implied-versus-realised readings every scan. Until then the gate is shut on
a sample size it has no way to reach.
