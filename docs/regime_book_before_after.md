# Regime Book — Before / After, Real Data

What the strategy rework actually bought, measured forward (out-of-sample) on the
same $500 real data, through the same unflattering harness (deflated Sharpe,
buy-and-hold beat, walk-forward). Spec:
`docs/superpowers/specs/2026-06-09-regime-book-rework-design.md`. Plan:
`docs/superpowers/plans/2026-06-09-regime-book-rework.md`. Code:
`backend/study/regime_book.py` (research only — nothing wired live).

## Method

- **Data:** real 1-min OHLCV → 4h, BTC + ETH + SOL pooled into one $500 book.
- **OOS span:** the held-out last 50% of calendar time (the basket fell −18.7%
  over it; BTC alone ~−34%).
- **Sim:** `study.sim.simulate_idx` — first-touch ATR SL/TP, 0.10% round-trip
  fee, long **and** short. Bracket = Aggressive (SL 1.5·ATR / TP 4.5·ATR).
- **Book:** capped-concurrency portfolio (≤3 open, one per name), each trade
  risks 1/3 of equity. Benchmark = equal-weight 3-coin buy-and-hold basket.
- **Regime gate:** leak-free ADX(14) ≥ threshold + SMA(50) slope sign →
  +1 uptrend (momentum long), −1 downtrend (momentum short), 0 range
  (mean-reversion long+short). The single tunable knob is the ADX threshold.
- **Leak-free:** classifier and signals use only past bars (unit-tested); the
  ADX threshold is selected on **in-sample only** for the headline number.

## The progression (each lever measured forward)

| Config | $end | OOS ret | Sharpe | maxDD | n | DSR | beats HODL |
|---|--:|--:|--:|--:|--:|--:|:--:|
| BEFORE — ungated, single position (cap 1) | $396 | −20.8% | −0.34 | −50.1% | 114 | 0.0005 | no |
| + Pooling (shorts, cap 3, no gate) | $449 | −10.1% | −0.14 | −25.9% | 355 | 0.0006 | YES |
| + Regime gate, adx=20 | **$587** | **+17.4%** | **+0.60** | −25.8% | 298 | 0.0082 | YES |
| + Regime gate, adx=25 | $479 | −4.1% | +0.02 | −35.3% | 309 | 0.0012 | YES |
| + Regime gate, adx=30 | $578 | +15.6% | +0.56 | −25.3% | 293 | 0.0073 | YES |
| + Trailing 2·ATR (on adx=20) | $445 | −11.0% | −0.17 | −31.0% | 530 | 0.0005 | — |

Basket HODL over the same OOS span: **−18.7%, maxDD −60.0%.**

### What each lever did

1. **Pooling the 3 symbols (cap1 → cap3)** is the cleanest win and has **zero
   tunable knobs**: it halved drawdown (−50% → −26%) and cut the loss in half
   (−20.8% → −10.1%) by diversifying regime exposure. Pure structure, no
   overfitting surface.
2. **The regime gate** flips the book from losing to **beating HODL on both
   axes** — more return AND less than half the drawdown. At adx=20: +17.4% vs
   the basket's −18.7% (a +36-point swing) at −26% vs −60% drawdown.
3. **Trailing stops were tested and rejected.** On the strong adx=20 base the
   fixed wide bracket (+17.4%) beat every trailing variant (1.5/2.0/3.0·ATR, all
   negative). Trailing doubles trade count but chops the fat winners this
   mean-reversion-heavy book lives on. It failed the "beat the simpler version
   OOS" test → **cut**.

## Honest read on the regime knob (no lookahead on selection)

The ADX threshold is non-monotonic across the OOS span (20 ✓, 25 ✗, 30 ✓), so
picking "20" by eyeballing OOS would be selection-on-test. Selecting the
threshold on **in-sample Sharpe only** removes that bias:

| adx | IS Sharpe (selection signal) | → OOS ret | OOS Sharpe |
|--:|--:|--:|--:|
| **20** | **+1.13** (best IS → chosen) | **+17.4%** | **+0.60** |
| 25 | +0.45 | −4.1% | +0.02 |
| 30 | −0.49 | +15.6% | +0.56 |

The rule "pick the best in-sample threshold" lands on adx=20 — which is also the
best out-of-sample. The honest, lookahead-free headline is therefore **+17.4% /
Sharpe 0.60**. Even the *unbiased average across all three thresholds* is
**+9.6% / Sharpe 0.40** — still clearly forward-positive and HODL-beating.

## The deflation verdict (unchanged discipline)

Best DSR across everything is **0.0082** — roughly **60× below the 0.5 bar**.
With only 3 symbols, pooled n tops out near 300 and the per-trade edge is too
weak to survive multiple-testing correction. **Nothing here is
deflation-provable.**

## Verdict

The rework is a **real, honest improvement in forward economics, not in
provability**:

- It turned a −20.8% / −50%-drawdown book into a **+17.4% / −26%-drawdown** book
  that beats an equal-weight HODL basket (−18.7% / −60%) on **both** return and
  drawdown, in a bear tape — driven by two defensible structural changes
  (multi-symbol pooling + a regime gate), with the gate's threshold validated
  in-sample so the number isn't lookahead-tainted.
- It **cut** a lever (trailing stops) that failed to beat the simpler version —
  the discipline that was missing before.
- It is still **not DSR-provable** (best 0.008 ≪ 0.5). The path to provability
  remains sample size: more symbols. With 3 coins, this is as far as honest
  forward edge goes — a book worth paper-trading and watching, not yet a book
  the deflation gate would clear.

Nothing is wired live. The live edge gate still admits 0 — correctly.
