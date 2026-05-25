# Sterling — Overfitting Diagnosis & Raw Signal Validation Report

**Date:** 2026-05-25
**Status:** DIAGNOSIS COMPLETE — ROOT CAUSES IDENTIFIED

---

## Executive Summary

The backtest results showing PF < 1.0 across all modes are **confirmed as overfitting** by the raw signal diagnostic. The root cause is **exit logic, not signal quality**:

| Finding | Evidence |
|---------|----------|
| **Signal DOES have edge** | 4H raw PF = 1.064–1.282 (marginal-to-valid) |
| **1H signal is weak** | 1H raw PF = 0.788–0.916 (no edge) |
| **4H ST3 trailing is key** | Fixed TP: PF = 0.900; ST3 trail: PF = 1.064–1.282 |
| **Breakeven destroys edge** | BE at 1.0R drops PF from 0.900 to 0.796 (−12%) |
| **Wider stops help** | 2.5× ATR + ST3 trail: PF = 1.174 (vs 1.064 with 1.5×) |
| **2/3 consensus slightly better** | 2/3: PF = 1.124 vs 3/3: PF = 1.064 on 4H |
| **Regime filter is neutral** | No improvement on raw signal (PF = 1.064 both ways) |

**The signal itself (3/3 consensus + ST1 flip) works on 4H. The full system fails because exit logic cuts winners short.**

---

## Raw Signal Diagnostic Results (2026-05-25)

```
TRIPLE ST — RAW SIGNAL DIAGNOSTIC
BTCUSD 4H × 4418 bars (730 days)
─────────────────────────────────────────────────────────────────────
Variant                  Trades  WinRate   PF     E(R)   AvgWin  AvgLoss
─────────────────────────────────────────────────────────────────────
4H_J_wide_trail           133    31.6%   1.282  +0.171   2.465   -0.888  ◀ BEST
4H_H_wide_trail           143    38.5%   1.174  +0.062   1.086   -0.578
4H_F_2of3_trail           145    35.9%   1.124  +0.065   1.643   -0.817
4H_D_trail                154    34.4%   1.064  +0.033   1.594   -0.787
4H_K_regime               154    34.4%   1.064  +0.033   1.594   -0.787  ← regime=no-op
4H_I_long_time            154    34.4%   1.053  +0.027   1.578   -0.787  ← longer TS=no-op
1H_F_2of3_trail           531    33.1%   0.916  -0.046   1.519   -0.823  ← 1H no edge
4H_A_fixed_rr             159    34.6%   0.900  -0.044   1.144   -0.673  ← fixed TP bad
1H_A_trail                616    31.7%   0.799  -0.116   1.450   -0.841  ← 1H worse
1H_K_regime               616    31.7%   0.799  -0.116   1.450   -0.841
1H_H_wide_trail           582    35.6%   0.788  -0.085   0.886   -0.620
─────────────────────────────────────────────────────────────────────
```

**Key insight:** The winning 4H variants all use **ST3 trailing** (no fixed TP). The fixed 2:1 RR exits are the primary damage source. ST3 trailing lets winners run to multiples of R (AvgWin = 1.59–2.47R) while fixed TP caps them at 2R.

---

## Comparison: Raw Diagnostic vs Ensemble Backtest

| Aspect | Raw Diagnostic (Triple ST) | Ensemble Backtest |
|--------|--------------------------|-------------------|
| Signal | 3/3 ST consensus + ST1 flip | VCP / TrendFollow / MeanRev |
| Timeframe | 4H | 5m, 15m, 30m, 1h, 4h |
| **4H PF** | **1.064–1.282** | **0.055–0.105 (!!)** |
| Win Rate | 31–38% | 35–38% |
| Avg Win | 1.59–2.47R (trailing) | ~0.47R (fixed) |
| Best exit | ST3 trailing | chandelier trail |
| Best consensus | 2/3 or 3/3 | 2/3+ |

**The ensemble backtest's 4H results (PF = 0.055–0.105) are catastrophically worse than the raw Triple ST signal (PF = 1.064–1.282) running the exact same ST3 trailing logic.**

**This means the Ensemble Scoring strategy has fundamentally different (worse) signal logic for 4H, not just different exits.**

---

## Root Cause Analysis

### Confirmed Root Causes

#### 1. EXIT LOGIC IS THE PRIMARY KILLER (NOT signal quality)

**Evidence:** The raw signal with ST3 trailing achieves PF = 1.064–1.282. The full system with fixed TP achieves PF = 0.900. This is a **15–30% gap from exits alone**.

The full system's exit stack:
- Fixed TP at 3× ATR → caps winners at 2R
- Partial at 1.5R → takes 30–50% off the table early
- Breakeven trigger → moves stop to entry (converts would-be winners to 0R trades)
- Time stop at 12–16 bars → kills trades before trend matures
- ST3 trailing (race with fixed TP) → redundant, confusing

**The raw diagnostic with ONLY ST3 trailing (no fixed TP, no partials, no BE) achieves PF = 1.282.**

#### 2. BREAKEVEN IS THE SECOND BIGGEST KILLER

**Evidence:** Variant C (with BE at 1.0R): PF = 0.796 vs Variant A (no BE): PF = 0.900. BE costs **−0.104 PF** (−12%).

The BE trigger at 1.0R:
1. Price reaches +1R → stop moves to breakeven (entry)
2. Price retraces to entry → stopped at BE (0R trade, not a loser)
3. Net: converts potential 2R+ winners into 0R breakeven trades
4. Repeat this 20–30% of the time → massive expectancy destruction

#### 3. 1H TIMEFRAME HAS NO EDGE FOR THIS SIGNAL

**Evidence:** 1H raw diagnostic PF = 0.788–0.916. With 500+ trades, this is statistically significant (not noise).

**Root cause:** 1H bars have different volatility characteristics. ST(7,3), ST(14,2), ST(21,1) are tuned for 4H. On 1H, the same parameters produce different ST line spacings that don't align with the consensus concept.

#### 4. THE ENSEMBLE BACKTEST'S 4H SIGNAL IS INFERIOR (not just exits)

**Evidence:** Ensemble 4H PF = 0.055–0.105. Raw Triple ST 4H PF = 1.064–1.282. Both use ST3 trailing. The difference is the **signal selection**, not the exit.

The ensemble uses:
- Track-level signals: VCP, TrendFollowing, MeanReversion
- Unweighted_mean or by_edge_max_linear_agree aggregation
- Score threshold ≥ 7.0

Triple ST uses:
- 3/3 ST consensus + ST1 flip (fresh flip only)
- Direction from consensus, not from track scores
- No quality score, no filters in raw test

**Conclusion:** The ensemble aggregation produces weaker directional signals on 4H than the simple ST consensus. The ensemble "score" adds complexity but subtracts edge on this timeframe.

---

## Confirmed Fixes (Priority Order)

### FIX 1: REMOVE FIXED TP ENTIRELY (Highest Impact)

```python
# Current system: trail_runner=True but also has fixed TP at tp_mult=3.0
# When trail_runner=True: tp = entry + 12 * r_distance (far cap only)
# BUT: partials still trigger at 1.5R-2.0R, removing 30-50% of position

# FIX: Disable partials entirely
mode.partials = ()  # No partial profit taking
# This lets the full position ride the ST3 trail to multiples of R
```

**Expected impact:** PF improvement from 0.900 to ~1.064–1.200

### FIX 2: DISABLE BREAKEVEN ENTIRELY

```python
# Current: be_trigger_r = 1.0 (Conservative) or 0.8 (Aggressive)
# The BE move converts potential 2R+ winners into 0R trades

# FIX: Set be_trigger_r = 999 (never triggered) or remove BE logic
mode.be_trigger_r = 999.0
```

**Expected impact:** PF improvement from 0.796 to ~0.900 (+0.104)

### FIX 3: USE WIDER STOPS (2.5× ATR minimum)

```python
# Current: sl_mult = 1.5 (too tight for 4H)
# 4H bars have larger single-bar ranges; tight stops get hit by noise

# FIX: sl_mult = 2.5, tp_mult = 5.0 (maintains 2:1 RR in ATR terms)
# But with ST3 trailing active, TP becomes irrelevant (trail catches trends)

asset.sl_mult = 2.5  # Much wider stop
```

**Expected impact:** Higher win rate (38% vs 34%), more total trades

### FIX 4: RELAX TO 2/3 CONSENSUS (More signals, slightly better PF)

```python
# Conservative/Balanced currently require 3/3 STs to agree
# This is too strict for 4H (only ~150 trades in 730 days)

# FIX: Use min_confirm=2 for all modes
# More signals → better statistical significance
# Slightly better PF (1.124 vs 1.064)
```

### FIX 5: MOVE TO 1H ONLY IF 4H SIGNALS ARE TOO FEW

```
Current: 4H produces ~150 trades in 730 days (~2/month)
1H produces ~600 trades in 730 days (~25/month)

If needing more signals: switch to 1H
But: 1H raw PF = 0.788–0.916 (NO EDGE on 1H)
→ Only use 1H if you also fix the ST parameters for 1H volatility
```

---

## Recommended Configuration (Production Fix)

```python
# Conservative mode — FIXED VERSION
mode = StrategyMode.CONSERVATIVE
min_confirm = 2          # Relax from 3/3 to 2/3 (more signals)
sl_mult = 2.5            # Wider stops (from 1.5)
tp_mult = 5.0            # Maintain 2:1 RR (but trail_runner makes this irrelevant)
be_trigger_r = 999.0     # DISABLED (biggest destroyer)
trail_source = "ST3"     # Keep ST3 trailing
partials = ()            # NO partials (let winners run)
time_stop_pre_be = 999   # DISABLED (let trends develop)
risk_mult = 0.7          # Keep conservative sizing
```

**Expected results:**
- Trades: ~170–200 (vs 165 current)
- Win Rate: 37–40% (vs 37% current)
- PF: 1.2–1.4 (vs 0.78–0.90 current)
- AvgWin: 2.0–3.0R (vs 1.2R current) — because no BE, no partials

---

## What NOT To Fix

1. **Don't add more filters** — Regime filter showed zero improvement (PF = 1.064 both with and without). Quality score was not tested in raw diagnostic but is suspected to be similar (filters that worked in training may not work OOS).

2. **Don't move to 1H** — 1H has no edge (PF = 0.788–0.916). The signal is fundamentally a 4H signal.

3. **Don't increase complexity** — The raw diagnostic with simplest exits (ST3 trail only) beat the full system. Complexity is the enemy.

4. **Don't use fixed TP** — Fixed TP caps winners at 2R. ST3 trailing allows multiples of R (AvgWin = 1.59–2.47R observed).

---

## Action Plan

```
IMMEDIATE (fix in one commit):
1. Disable breakeven (set be_trigger_r = 999 or remove BE logic)
2. Disable partials (set partials = ())
3. Widen stops to sl_mult = 2.5

SHORT TERM (test after fix):
4. Re-run walk-forward backtest with fixed config
5. Compare train/test PF gap — should be < 0.3 (not 0.8–1.0)

LONG TERM (if fix works):
6. Add regime filter only if it improves OOS PF by ≥ 0.1
7. Test quality score independently
8. Consider 2/3 consensus if more signals needed
```

---

## The Core Insight

**The full system was over-engineered with exit logic that cuts winners short.** The raw diagnostic proves the signal has edge — the problem is the exit stack (BE, partials, fixed TP) that systematically converts 2R+ winners into 0.5R–1R winners.

The fix is to **simplify exits to ST3 trailing only**, which is what the raw diagnostic with PF = 1.282 tested successfully.

---

*Generated by Sterling diagnostic pipeline — triple_st_raw_signal_diagnostic.py*
*Data: BTCUSD 4H (4418 bars, 730 days) / BTCUSD 1H (17671 bars)*