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

## 5. What is NOT yet tested — `kite_st_exit_sweep.py` (ready to run)

The existing sweep only tested the 3 fixed ST lines. The new script holds entry
fixed and sweeps the **exit mechanics**, SuperTrends only, IS/OOS + Spearman, on
both a delta-1 lens (isolates the exit) and a costed ATM-options lens:

    trail_period   × 10 / 14 / 21        (decoupled from the entry triple)
    trail_mult     × 0.75 / 1.0 / 1.5 / 2.0
    time_stop_bars × off / 48            (cap the hold → attack theta directly)
    breakeven_R    × off / 1.0R          (lift stop to entry once +1R)

Run (needs a logged-in Kite account in the DB; caches to `study/kite_cache/`):

    cd backend && python -m study.kite_st_exit_sweep

It answers the open questions: is a trail tighter/looser than `fast` better once
premium whipsaw + costs are paid, and do a time-stop or breakeven help on options?
Numbers are intentionally **not** included here — they require a live data pull.

## 6. Exit-counter (`exit_mode`) addendum — shipped later, NOT yet measured

A later change added a configurable **`exit_mode`** (`one_red` / `two_red` /
`three_red` / `three_red_signal`): exit once that many of the three STs are red
against the position (`engines/common/exit_counter.py`; live in `scanner.is_active`
+ `monitor.on_tick`). The default was set to **`two_red`**. Two problems, both open:

1. **`two_red` is asserted, not measured.** Unlike the `mid→fast` decision above
   (7.5y IS/OOS), no sweep backs `two_red` — `docs/kite_exit_counter_prod_rollout.md`
   argues it qualitatively ("balanced") with zero numbers, and `kite_st_exit_sweep.py`
   never tested the red-count modes. **`kite_st_exit_mode_sweep.py`** (new) fills the
   gap: entry fixed, sweep the four modes on the delta1 + costed-options lenses,
   IS/OOS. Run it before trusting any default but `one_red`.

2. **`two_red`+ is shadowed in the live path → effective exit ≈ `one_red`.** The stop
   is the tightest still-green line (`regime.best_trail_line_value`), meant to step
   OUT (loosen) to `mid`/`slow` as tighter lines flip so the trade can reach a 2-/3-red
   exit. But `positions.update_stop` ratchets the premium stop UP-only and REJECTS
   that loosening, pinning it near the peak `fast` level — so the price-trail breach
   fires around the first (`fast`) flip and pre-empts the counter. Net: the `exit_mode`
   knob barely moves live behaviour. Reconcile the ratchet with the stepping-out stop
   before the counter means anything.
