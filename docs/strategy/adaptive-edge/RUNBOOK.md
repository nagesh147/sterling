# Adaptive Edge — operator runbook

What this engine does at the open, what it will and will not do with money, and
how to tell the difference between "no setup" and "broken".

## What it is today

`PAPER_READY` in A166 terms. It scans, ranks contracts, and paper-trades. It
cannot reach real money, and that is enforced in code rather than by convention.

| Gate | State | Effect |
|---|---|---|
| Formula gate | BLOCKED (`required_strategy_formula_not_implemented`) | F-101..F-114 are LOCKED in the registry |
| Promotion gate | BLOCKED (`strategy_promotion_required`) | Refuses live regardless of the account setting |
| Account paper/live | Yours | Paper is simulated inside KiteClient |
| Account manual/auto | Yours | Gates opening only, never exits |

Verify all four at any time:

```bash
curl -s localhost:8000/api/v1/config/adaptive-edge/snapshot | jq .readiness
```

## Why it is not live

The mathematics comes from an authoritative source — the Master Mathematical
Specification v1.0 in `adaptive-edge/`. The *numbers* do not, and cannot yet:
§19 forbids using any threshold that has not survived walk-forward validation,
and §51–§55 place every parameter under learning rather than specification.

So every value in `backend/app/engines/adaptive_edge/config.py` is a research
default. `CALIBRATED_FIELDS` is empty and the API publishes that, so the settings
page marks them rather than showing bare numbers an operator could reasonably
read as measured.

**Do not promote the strategy to clear the gate.** Promotion without the
calibration is just putting money on placeholder numbers with an extra step.

## At the open

Nothing to do. The scan loop starts with the server and runs every 60s, and is a
no-op outside `session_start`–`session_end` (09:20–15:10 IST by default).

Watch the board. Candidates will appear; none will be armable, and each says why:

    Uncalibrated: the entry gate needs a directional probability,
    and that model has not been fitted yet.

That is the expected state, not a fault.

## If you arm something

Entering is manual. `entry_ok` is false on every candidate — the entry gate
needs a fitted directional probability and that model does not exist yet — so
the loop will never open a position on its own. An operator can still arm one
deliberately, and that path is real:

1. Refuses early: promotion (live), daily loss cap, max positions, already held.
2. Places a limit buy under an idempotency key, so a retry after a timeout is
   refused rather than becoming a second position.
3. Persists the position **before** confirming the fill, so a crash in between
   leaves something findable.
4. Re-anchors the stop to the price that actually traded, not the limit.
5. Places a broker-side stop (GTT) unless `stop_mode` is `monitor`.

Once open it is managed without you: the tick monitor ratchets the trail up
(never down), exits on stop, target or the session boundary, and the loop
reconciles against the broker before every scan.

    POST /api/v1/config/adaptive-edge/square-off   # flatten everything, now
    POST /api/v1/config/adaptive-edge/reconcile    # re-sync against the broker
    GET  /api/v1/config/adaptive-edge/positions    # incl. broker_stop per row

`broker_stop: false` on an open row means this process is the only thing
watching it. That is survivable but you should know you are in it.

### The exit invariants

Worth knowing because they are the ones that cost money when wrong:

* The broker stop is cancelled **before** the sell goes out. Selling into an
  armed GTT is how one position gets sold twice.
* If the sell fails, the stop is re-armed. A failed exit must not quietly become
  an unprotected position.
* One exit path, one claim. The tick monitor and the square-off cannot both sell
  the same position.
* The exit reason is recorded as given, never inferred from the price — a stop
  and a square-off happen at the same number.

## Reading an empty board

The scan reports per-stage counts precisely so "nothing found" is diagnosable:

```bash
curl -s localhost:8000/api/v1/config/adaptive-edge/scan -X POST | jq '{underlyings, chains_read, listed, tradeable, skipped, dropped, errors}'
```

| Symptom | Meaning |
|---|---|
| `underlyings: 0` | No index or stock selected |
| `listed: 0` | Every contract fell outside the expiry or strike window |
| `tradeable: 0` with `dropped` populated | Contracts existed but failed liquidity — the tally says which filter |
| `errors` populated | Instrument dump, quotes, or the account is unavailable |

The classic misconfiguration is an expiry window that excludes everything, which
otherwise looks identical to a quiet market. `validate()` rejects the worst case
(`avoid_expiry_day` with `expiry_dte_max = 0`) outright.

## What tomorrow's session produces

Nothing arms, but the session is not wasted. Every candidate the scan surfaces is
recorded as an **observation** — the contract, its premium, OI, volume, spread,
spot and days to expiry, at that moment. Those rows are what the walk-forward
calibration consumes.

This is deliberate, and it is why the engine does not simply enter on the gates
it *can* evaluate. §35 needs `DirectionalEdgeOK` and both expected-value terms,
and all three come from the probability model calibration has to supply. The
remaining gates — data, liquidity, slippage, risk — would mean "enter on any
liquid contract", which is not a strategy and would fill the record with noise
instead of evidence. Calibration does not need trades; it needs observations
paired with what happened next.

Check what a day collected:

```bash
curl -s localhost:8000/api/v1/config/adaptive-edge/snapshot | jq '.session.observations'
```

Outcomes are written back onto the observation they belong to, never appended as
a second row — that would silently double the day's sample size.

## Settings

Two surfaces, one source of truth.

* `/api/v1/config/adaptive-edge` — the engine configuration the scanner and
  runner read. Authoritative.
* `/api/v1/adaptive-edge/settings` — the legacy page. Fields it shares with the
  engine config are mirrored on write; the rest belong to an earlier
  moving-average scalper and reach no engine. Those are listed in
  `inert_fields`, and the UI marks them.

The risk controls that matter — lots, stop, target, max positions, daily loss
cap, square-off — are in the **Risk and session** section, which writes to the
engine config directly.

## What would make it live

All of A166's conjunctive terms, but the one actually outstanding is
`research_validation_complete`:

1. Collect sessions on paper.
2. Walk-forward calibrate the parameters per §51–§55, honouring the purge and
   embargo boundaries (`walk_forward.build_folds`).
3. Validate out of sample; record the report.
4. Only then promote, by changing `CURRENT_STRATEGY_PROMOTION` deliberately.

Step 4 is one constant. Steps 1–3 are the work, and skipping them is the failure
mode this whole gate exists to prevent.

## Known limitation: order flow

The strategy's §8–§11 features want aggressor-classified trade prints. Kite ticks
carry no aggressor flag, so with `data_source = "kite"` those features run in a
degraded, quote-derived form. The config warns about this on every read.
`data_source = "truedata"` is the path to the real thing.
