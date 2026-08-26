# A311 — Gamma Move runbook

Operating the engine. For what it does and whether it works, read
[VALIDATION_REPORT.md](VALIDATION_REPORT.md) first — the short answer is that its
entry trigger showed **no measurable edge on its own**; the level filter is where
the edge was.

It ships **enabled** and is not locked. `enabled` is a power switch, not a safety
device: paper/live, manual/auto, the kill switch and the risk caps all apply
whatever it is set to, and they are what actually stand between this engine and
real money. **With the account LIVE and the engine on AUTO, it will trade.**

---

## 0. Paper/live and manual/auto are not settings on this page

This engine has **no `execution_mode` and no paper-only lock**, on purpose.

| Axis | Where it lives | How it reaches the order |
|---|---|---|
| PAPER / LIVE | `account.is_paper`, from the **Trading Mode** panel | `build_client` hands it to `KiteClient`, which simulates every order when set |
| MANUAL / AUTO | the engine's `auto_execute` | read by `scan_all_once`; in AUTO the scan enters armed rows itself |

Both are shared by every Kite strategy and both are **read, never stored here**.

An earlier version of this engine did carry its own `execution_mode`, defaulting
to `"paper"`. On 2026-08-26 that config read `paper` while the account it traded
through was **live** — the strategy believed one thing and the broker did
another. That is the entire argument against a second switch, and it is why the
safety rules below are unconditional instead of being attached to a mode.

---

## 1. Switching it on

**UI** · Connect → Signal engines → **Gamma Move**. The power toggle at the top
is on by default; turning it off stops this engine scanning without touching any
other. Nothing places an order while the account is in paper mode.

**API**

```bash
curl -X PUT localhost:8000/api/v1/config/gamma-move \
  -H 'Content-Type: application/json' -d '{"enabled": true}'
```

`GET /config/gamma-move/snapshot` reports `mode.is_paper` and `mode.auto_execute`
so you can confirm what will actually happen before enabling.

The background loop (`gamma_move_runner.auto_scan_loop`, registered in
`main.py`) then scans every `scan_interval_seconds` while the clock is inside
`session_start`–`session_end` on a weekday. While `enabled` is false the loop is
a no-op and costs nothing.

---

## 1a. What it scans

The same curated high-liquidity registry every other engine here scans — **14
names** — through the same field names: `scan_stocks`, `scan_all_stocks`,
`stock_contracts`, `scan_indices`. Names outside the registry are refused by
`validate()`, not silently dropped, so a typo cannot look like a quiet market.

Storage is per-engine (engines legitimately scan different universes); what is
shared is the vocabulary and the eligible set. An earlier draft had an invented
`max_universe = 150`, which was both an arbitrary number and a way past that
boundary — a 2× on a contract you cannot exit is not a 2×.

---

## 2. When it will and will not find anything

**It is silent for most of the month, by design.** NSE stock options are
monthly-only, and the source trades only the last week or two of a contract, so
`max_days_to_expiry = 14` means the engine has nothing to do until roughly the
15th. A scan at DTE 34 correctly returns zero candidates — that is the expiry
gate, not a fault.

Observed on 2026-08-26 at DTE 34: **148 names scanned → 24 sitting at a level →
0 candidates**, stage B exiting in 0.06s because no expiry qualified.

To confirm the rest of the funnel outside the window, widen the gate temporarily
and scan; the same run then produced 15 real candidates. Put it back afterwards.

---

## 3. Reading the board

Signals panel → **GAMMA MOVE** tab.

| What you see | What it means |
|---|---|
| `NOT VALIDATED` banner | Always present. It carries the calibration finding. |
| `Scanned 148 names → 24 at a level → 15 strikes → 0 armed` | The funnel, stage by stage. If stage C's request count climbs toward the universe size, the funnel ordering has been broken. |
| Origin `OI UNWIND` (green) | All three entry conditions hold. |
| Origin `OI FALLING` (amber) | Open interest is unwinding; the other two are not there. |
| Origin `QUIET` (dim) | Not the setup. |
| Flag `0.37% FROM SUP` green | Inside the proximity band — where the measured edge is. Dim means outside it. |
| Flag `9D TO EXPIRY` | The R10 window. |
| Row detail → **Trigger** | Each condition with its measured value against its configured threshold, ✓ or ✗. This is how you see *which* leg is short. |

A `watching` row always carries a reason. If one ever does not, that is a bug —
`GammaSignal.__post_init__` is supposed to make it impossible.

---

## 4. Taking a trade

Armed rows show a **Buy** button in the row detail. It calls
`POST /config/gamma-move/arm` with the signal id, which re-checks admission
(strategy enabled, position cap, daily trade cap, daily loss limit, not already
holding it) before placing anything. A refusal comes back as a sentence on the
board, not an exception.

In paper mode the order goes to `PaperBrokerPort` and fills at the limit. Nothing
reaches Zerodha.

---

## 5. Monitoring an open position

Positions are driven by ticks (`on_ticks`), subscribed in **MODE_FULL** under the
owner tag `gamma_move` — full mode because the open-interest fields only appear
in full packets, and the owner tag because releasing untagged would pull ticks
out from under another engine's protection monitor.

Exit paths, worst first: `stop` → `trail` → `target` → `time_stop` →
`session_end`. Each position carries an `exiting` claim that the first path to
fire takes; without it two paths would both send a sell. On exit the broker GTT
is cancelled **before** the sell is sent — selling while a trigger is still armed
is how one position gets sold twice — and re-armed if the sell fails.

### What protects a position

`stop_mode` decides, with the same vocabulary as the SuperTrend engine:

| mode | GTT at Zerodha | our tick loop | if this process dies |
|---|---|---|---|
| `both` *(default)* | yes | yes | the GTT still exits |
| `broker` | yes | no | the GTT still exits |
| `monitor` | no | yes | **nothing exits** |

The board says which one a position is actually in: `GTT ARMED` (green) or
`NO BROKER STOP` (amber). A GTT that fails to place is logged and noted rather
than being fatal — but it is never silent, because "protected" and "protected
only while this process lives" are different states.

### Durability

Positions are persisted to `gamma_move_positions_{uid}` on every change, and the
loop reconciles against the broker before its first scan. A restart that started
scanning before knowing what it held could open a second position in the same
contract; an in-memory guard would not have survived the restart either.

`status` distinguishes `pending` (order sent, no fill confirmed) from `open`
(the broker confirmed it). The board shows `UNCONFIRMED` for the first. When the
fill comes in worse than the limit, the stop moves with it — leaving it where it
was would silently widen the risk past what the sizer allowed.

---

## 6. Recovery

**A position the engine does not know about.** `snapshot` lists it under
`orphan_positions` and adds a blocker naming it. Adopt it so something is
watching:

```bash
curl -X POST localhost:8000/api/v1/config/gamma-move/adopt \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"RELIANCE26SEP1300CE","quantity":500,"entry_price":53.0}'
```

Adoption sets a stop at `stop_percent` below the stated entry and subscribes the
contract. It requires the contract to be in the current scan.

**A restart.** In-memory session state is lost; positions at the broker are not.
Check `orphan_positions` after every restart while holding anything.

**A stuck exit.** If a sell is rejected the `exiting` claim is released so a later
tick retries, and the failure is appended to `session.notes`. Repeated failures
mean flatten it manually at the broker, then `clear(uid)`.

---

## 7. Killing it

```bash
curl -X PUT localhost:8000/api/v1/config/gamma-move \
  -H 'Content-Type: application/json' -d '{"enabled": false}'
```

This stops scanning. **It does not close open positions** — the tick monitor
keeps watching them out, which is what you want. To stand the engine down
entirely, close the positions first, then disable.

The strategy also halts itself for the day when realised losses reach
`daily_loss_limit_inr`; `session_status(uid).halt_reason` says so and every
admission is refused until the day rolls.

---

## 8. Re-running the calibration

Needed whenever a threshold is questioned, and required before the live gate.
See VALIDATION_REPORT §6. The first opportunity to measure **inside** the expiry
window is mid-September.
