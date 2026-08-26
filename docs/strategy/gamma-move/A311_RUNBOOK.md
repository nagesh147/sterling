# A311 — Gamma Move runbook

Operating the engine. For what it does and whether it works, read
[VALIDATION_REPORT.md](VALIDATION_REPORT.md) first — the short answer is that it
is **not validated**, ships disabled and paper-only, and live mode is refused by
`validate()`.

---

## 1. Switching it on

**UI** · Connect → Signal engines → **Gamma Move**. The power toggle at the top
enables scanning; nothing places an order in paper mode.

**API**

```bash
curl -X PUT localhost:8000/api/v1/config/gamma-move \
  -H 'Content-Type: application/json' -d '{"enabled": true}'
```

The background loop (`gamma_move_runner.auto_scan_loop`, registered in
`main.py`) then scans every `scan_interval_seconds` while the clock is inside
`session_start`–`session_end` on a weekday. While `enabled` is false the loop is
a no-op and costs nothing.

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
fire takes; without it two paths would both send a sell.

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
