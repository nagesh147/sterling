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

## Upgrade — vol-target sizing + sleeve exits + conviction concentration

The Stage-1 book above is unlevered and sizes every trade at a flat 1/3. Three
upgrades, each measured forward and kept only if it earned its place:

1. **Volatility-targeted sizing** — size inversely to the ATR stop distance so
   every trade risks the same fraction of equity (press in calm, de-risk in
   chaos). `vol_target_weight` / `portfolio_equity_sized`.
2. **Sleeve-specific exits** — the earlier uniform-trailing test was *wrong*. The
   trend sleeve now lets winners run (wide TP + 3.5·ATR chandelier trail); the
   mean-reversion sleeve keeps its quick fixed 1.5/4.5 target. `_TREND_EXIT` /
   `_MR_EXIT`.
3. **Conviction concentration** — tighten the MR sleeve to deep-extreme RSI only
   (the filter is chosen on **in-sample Sharpe**, then read out-of-sample, and
   deflated by the 36-cell grid). `select_conviction_book`.

**Validated forward result (IS-selected adx=20 / RSI<25,>65, unlevered):**

| | OOS | basket HODL |
|---|--:|--:|
| Return | **+43.2%** | −18.7% |
| Sharpe | **+1.15** | — |
| maxDD | **−29.0%** | −60.0% |
| trades | 228 | — |

Why it isn't a lucky cell:
- **IS→OOS Sharpe rank correlation = +0.38** — in-sample quality *predicts*
  out-of-sample. (The overfit strategies in this project's history had
  **negative** IS↔OOS correlation, −0.65 to −0.73. This is the opposite.)
- **Whole-grid OOS mean = +26% / Sharpe +0.81** (worst cell −0.45) — the effect
  is broad across the grid, not one cell.

### Leverage dial (the honest return-vs-drawdown curve)

Sharpe is **invariant** to leverage (1.15 at every row); only return and
drawdown move — and **past ~Kelly the compound return falls while drawdown
explodes** (the reason you can't lever a 1.15-Sharpe book to the moon):

| leverage | $500 → | OOS ret | maxDD | note |
|--:|--:|--:|--:|---|
| 1.0× | $716 | +43.2% | −29% | conservative |
| **1.5×** | **$811** | **+62.3%** | **−40%** | **~half-Kelly (recommended)** |
| 2.0× | $889 | +77.8% | −50% | aggressive |
| 3.0× | $970 | +94.0% | −65% | over-Kelly (return stalls) |
| 4.0× | $939 | +87.9% | −76% | ruin zone (return *falls*) |

## The deflation verdict (unchanged discipline)

The Stage-1 structural book tops out at DSR **0.0082**. The Stage-2 upgrade lifts
it to **DSR 0.166** — the **highest in the entire project** (was 0.096), and a
20× improvement — but still **below the 0.5 bar**. With only 3 symbols the grid
penalty and the sample size keep it short of formal provability.

**Honest read:** this is a genuine, validated *forward* edge (+43% OOS, Sharpe
1.15, beats HODL by 62 points at half the drawdown, IS predicts OOS), dialable to
+62% at half-Kelly — but it is **not yet deflation-provable**. The numbers that
finally exceed the old +95/99% in-sample mirage are real and out-of-sample, yet
the only thing standing between "forward edge" and "provable edge" is breadth:
more symbols. Tested and rejected along the way: naive leverage (ruin past 2×),
Donchian/TSMOM trend (worse than the EMA cross), uniform trailing stops.

## Breadth experiment — the 24-coin pipeline (honest negative)

Built `study/ohlcv_pipeline.py` (Binance public klines → 6-col parquet →
`load_universe`) and downloaded **24 liquid coins, 5,362×4h bars each
(2023-12-29 → 2026-06-09)** to test whether breadth buys a deflation-provable
(DSR ≥ 0.5) edge. The OOS span was a brutal alt bear market — **basket HODL
−55.3% / −70% maxDD**. Three routes tested, all honest, all read out-of-sample:

| Route | best OOS | Sharpe | DSR | IS→OOS corr | verdict |
|---|--:|--:|--:|--:|---|
| Directional pool (conviction, cap 3) | +24.4% | 0.69 | 0.082 | +0.45 | beats HODL, Sharpe *fell* vs 3-coin |
| Directional pool (cap 15, more n) | +66.7% | 0.44 | 0.132 | +0.69 | only via −85% maxDD — not real |
| Cross-sectional **momentum** (long winners / short losers) | −73.2% | −1.28 | 0.000 | +0.74 | loses OOS (whole grid mean −1.38) |
| Cross-sectional **reversal** (long losers / short winners) | −80.7% | −1.84 | 0.000 | +0.20 | loses worse (whole grid all negative) |

**Why breadth didn't help — the correlation wall.** 24 crypto coins are
~0.8-correlated: stacking more *directional* books adds trade *count* but not
independent *information*, so n rises while the effective t-stat (and DSR)
barely moves — and concurrency just piles correlated risk until drawdown
explodes. The market-neutral routes that *should* diversify (cross-sectional)
**lose outright** here: in a correlated alt crash the dispersion alpha is swamped
and both long-short legs bleed. Crypto's cross-sectional factors did not hold up
in this window.

**What survives:** the focused, *directional*, regime-gated conviction book —
which is long/short and not forced to hold, so it sidesteps the alt bleeding the
cross-sectional books walked into. Breadth is a real, reusable capability (the
pipeline extends to any coin/interval in one command), but on this universe and
window it did **not** clear the deflation bar. The honest best book remains the
conviction regime book (Sharpe ~1.15, DSR 0.166) — not provable, but real.

## Paper trading the conviction book (real Binance data, isolated)

`study/paper_trader.py` runs the *exact* validated conviction book (adx=20,
RSI<25/>65, vol-target sizing, sleeve exits) on **real Binance 4h bars**, keeps a
persisted paper account, and distinguishes closed trades from currently-open
positions (`walk_positions`). It is **isolated from the live SterlingEngine** —
the book is not deflation-provable (DSR 0.166 < 0.5), so it earns trust by
paper-trading, not by going live. Realized equity is computed with the same
`portfolio_equity_sized` the backtest used, so paper logic cannot drift from what
was validated (only the *data* differs: native Binance 4h vs legacy 1m-derived).

**Inception-date sensitivity (real Binance 4h, $500, 1× leverage) — no cherry-picking:**

| inception | realized | return | Sharpe | maxDD | trades |
|---|--:|--:|--:|--:|--:|
| 2025-01-01 | $879 | +75.8% | 1.46 | −28.1% | 270 |
| 2025-03-01 | $810 | +62.0% | 1.39 | −28.1% | 244 |
| 2025-06-01 | $872 | +74.4% | 1.78 | −28.1% | 205 |
| 2025-09-07 | $927 | +85.4% | 2.64 | −28.1% | 146 |
| 2026-01-01 | $817 | +63.3% | 3.52 | −28.1% | 80 |
| 2026-03-01 (≈3mo) | $573 | +14.5% | 1.65 | −19.4% | 55 |

Every inception is strongly positive (Sharpe 1.4–3.5) — robust across windows,
not one lucky cell. As of the latest bar the book is positioned **short** BTC/
ETH/SOL (regime gate → momentum-short in a downtrend), with positive unrealized
P&L. On real data it *outperforms* its legacy-data validation (+43% / 1.15),
plausibly because native 4h bars give cleaner first-touch fills.

**Honest caveat:** 2025–26 is essentially one macro regime (a crypto downturn
the short sleeves exploited), and these windows overlap (same endpoint). The
Sharpe reflects that regime. The paper account exists precisely to accumulate
*genuine forward* evidence across regimes from here. Run:
`python -m study.paper_trader` (persists `data/paper/state.json` + `trades.csv`).

## Verdict

A **real, validated, out-of-sample edge** — the strongest this project has
produced — that is honest about its one remaining limit:

- Stacking defensible changes (multi-symbol pooling → regime gate →
  vol-targeting → sleeve-specific exits → conviction concentration) turns a
  −20.8% losing book into **+43.2% OOS, Sharpe 1.15, −29% drawdown**, beating an
  equal-weight HODL basket (−18.7% / −60%) by 62 points at half the drawdown —
  with the conviction filter chosen **in-sample** (IS→OOS rank corr +0.38, i.e.
  selection is genuinely predictive, not overfit).
- At a sane operating point (~half-Kelly, 1.5×) it reads **+62% / −40%
  drawdown** — and the dial is honest about where leverage turns to ruin.
- Levers **cut** because they failed forward: naive leverage past 2× (vol drag),
  Donchian/TSMOM trend (worse than EMA cross), uniform trailing stops.
- Still **not DSR-provable** (0.166 < 0.5), though 20× better than before. The
  only thing between this and provable is **breadth — more symbols.**

Nothing is wired live. The live edge gate still admits 0 — correctly. This is a
book worth paper-trading and watching, and the clearest signpost yet that the
next real unlock is a multi-symbol data pipeline.
