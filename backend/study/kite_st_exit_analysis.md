# Sterling Kite Engine — exit / SL / trailing analysis

Scope: the **exit side only** (initial SL, trailing stop, exit trigger). Entry
(triple Heikin-Ashi SuperTrend full-alignment) is held fixed — it is assumed good.
Goal: find the best exit using **SuperTrends only**, no new indicators, grounded in
real data (no fabricated numbers).

## 1. What the exit actually is today

Three mechanisms exist; only two are live:

1. **Trailing stop = the `trail_target` SuperTrend line.** SL at entry = that line;
   each 5-min scan ratchets it monotonically (`positions.update_stop`); the **tick
   monitor** market-exits the instant premium breaches it (`positions.should_exit`).
   With the default `scan_source="derivatives"`, the line is computed on **each
   option's own premium chart** — so the live stop is a trailing premium-SuperTrend.
2. **Broker GTT** at the same level — survives disconnects, trailed each scan.
3. **`engine.manage()` early-lock / slow-flip exit — DEAD CODE.** It is never called
   in production (the scanner recomputes the regime directly; `grep '.manage(' app/`
   is empty).

## 2. Real-data findings (existing 7.5y 1H sweep, IS 70% / OOS 30%)

From `kite_st_sweep_results.csv` / `kite_st_analysis.json` — real index candles, BS
premium, full Indian F&O costs. Not re-generated here; re-analysed:

| Finding | Evidence |
|---|---|
| **`early_lock` is 100% inert** | P&L spread across off / 0.5R / 1.0R / 1.5R = **0.0 in all 60 cells**. It keys off the *slow* (widest) ST, which always flips *after* the trail target has already exited → the branch never fires. |
| **`fast` trail = most robust; `slow` = strictly worst** | Signal-isolation (delta-1, theta stripped): `fast` is OOS-positive on **4/4** indices (+9.8 / +3.4 / +10.9 / +8.9 %, PF 1.04–1.16); `mid` 3/4; `slow` **negative on 4/4** (−11 to −22 %). On the costed-options lens, mean OOS: fast −92 % > mid −116 % > slow −313 %. |
| **The exit is not the binding constraint — the vehicle is** | Long OTM/ATM options: **0 / 60 configs OOS-positive** (theta). The *same* entries+exit on delta-1 are OOS-positive; deep-ITM / futures (validated ✓, `kite_st_phase0_report.md`) flip it positive. |

## 3. Decision (shipped on this branch)

- **`trail_target` default `mid` → `fast`** (`config.py`, `schemas.py`, frontend
  fallbacks). `fast` is the tightest band → most OOS-robust exit and banks the move
  faster → less theta bleed on long options. `mid` / `slow` stay user-selectable.
- **Early-lock removed.** Dead `manage()` branch deleted (kept the tested trail-flip
  exit); config/API field marked DEPRECATED + inert; the no-op UI toggle removed.
- **No new indicator added.** SuperTrends alone are sufficient for the exit.

## 4. Self-critique (attacking the recommendation)

- **`fast` is validated on the underlying-ST / delta-1 path.** The *live default*
  path trails the SuperTrend on the **option premium** (noisier: vega + gamma +
  spread). A mult-1.0 trail there may **whipsaw** and bleed the ~1% × 2 slippage.
  On the costed-options lens `fast` vs `mid` is closer (per-index split 2/2), though
  mean OOS still favours `fast`. → **Paper-validate on live premium before trusting.**
- **OOS = one contiguous regime.** A uniformly negative options OOS is partly a
  regime artefact, not only overfit.
- **Do NOT add a profit-target.** Win rate is ~31%; the system lives on fat-tail
  winners. A fixed TP would clip them and turn the edge negative. (Confirm via §5.)
- **Honest ceiling:** no SuperTrend exit makes long OTM options OOS-robust. Pair the
  `fast` trail with **deep-ITM or futures** (delta ≈ 1, low theta) to realise the edge.

## 5. Exit-mechanics sweep — RUN (`kite_st_exit_sweep.py`, 2026-07-16 real data)

Entry fixed; swept trail_period {10,14,21} × trail_mult {0.75,1.0,1.5,2.0} ×
time_stop {off,48} × breakeven {off,1.0R}, IS/OOS + Spearman, delta-1 + costed-options
lenses, on the fresh 7.5y pull (`study/kite_st_exit_sweep_results.csv`).

| lens | shipped baseline (p21,m1.0) | best config | IS→OOS Spearman |
|---|---:|---|---:|
| delta1 | +4.0% | p21, m0.75, tstop48 → **+10.3%** (3/4 +) | **−0.20** |
| options | −134.0% | p10, m0.75, tstop48 → **−31.7%** | **−0.19** |

Two findings, opposite in how much to trust them:
1. **Rankings don't generalize — Spearman is negative.** The tighter `m0.75` optimum is
   overfit; **NOT adopted** — the validated `fast`/m1.0 trail stays. (Chasing the top
   cell would be the textbook error.)
2. **A ~48-bar time-stop is the one robust, cross-lens win** — cuts the options-lens
   mean OOS loss −134% → ~−32% (caps theta). **Shipped as opt-in `time_stop_bars`
   (default off)**; enforced by `service._time_stop_positions`. Off by default because
   the delta-1 gain is marginal and it mainly helps the long-OTM vehicle.

Breakeven-at-1R barely moved anything (on ≈ off). No SuperTrend exit makes long
OTM/ATM options OOS-positive — the vehicle is still the binding constraint.

## 6. Exit-counter (`exit_mode`) addendum — shipped later, NOT yet measured

A later change added a configurable **`exit_mode`** (`one_red` / `two_red` /
`three_red` / `three_red_signal`): exit once that many of the three STs are red
against the position (`engines/common/exit_counter.py`; live in `scanner.is_active`
+ `monitor.on_tick`). The default was set to **`two_red`**. Both open problems are
now RESOLVED:

1. **`two_red` was asserted, not measured — now MEASURED, and it loses.**
   `kite_st_exit_mode_sweep.py` was run on the real 7.5y 1H data (IS 70% / OOS 30%,
   4 indices, both lenses). Mean OOS return by mode:

   | exit_mode | delta1 OOS | idx + | options OOS | ~trades/idx |
   |---|---:|---:|---:|---:|
   | **one_red** | **+4.0%** | **3/4** | **−134.0%** | 554 |
   | two_red | −6.4% | 1/4 | −184.5% | 355 |
   | three_red | −18.4% | 0/4 | −338.1% | 200 |
   | three_red_signal | −18.4% | 0/4 | −338.1% | 200 |

   **`one_red` is best on both lenses; tighter is strictly better.** The shipped
   default was changed **`two_red` → `one_red`** (`config.py`, `schemas.py`).
   (Artifact: `kite_st_exit_mode_sweep_results.csv`.)

2. **The ratchet-vs-stepout tension is moot given (1).** The monotonic fast-line
   ratchet (`positions.update_stop`) pinned the live stop near the tightest flip →
   live exits were already ≈ `one_red` — which the sweep now says is the *right*
   place to be. The opt-in `exit_aligned_trail` (widen the stop to honour a looser
   mode) was built but, per (1), is **not recommended**; it stays default-OFF.
