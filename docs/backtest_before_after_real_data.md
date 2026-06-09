# Backtest Trades — Real Data, Before vs After

Real-data backtest report contrasting what the system concluded **before** this
session's changes versus **after**. The underlying trades are the same physical
reality; the changes fix *reproducibility* and *what the system believes those
trades prove*.

## Scope & method

- **Data:** real 1-minute OHLCV (`vector_store_1m_{BTC,ETH,SOL}USD.parquet`),
  resampled to 4h. BTC 4h = 2023-12-29 → 2026-05-30, **5,128 bars**.
- **Simulator:** `study.sim.simulate_idx` — long-only, enter at signal-bar
  close, first-touch intrabar SL/TP (ATR-multiple brackets), max hold 200 bars.
- **Costs:** 0.10% round-trip fee per trade. **Starting capital: $500.**
- **Profiles:** Intraday = SL 2.0·ATR / TP 3.5·ATR; Aggressive = SL 1.5·ATR /
  TP 4.5·ATR.
- **IS/OOS split:** 70% of calendar time (boundary 2025-09-07). "OOS / forward"
  is the held-out last 30% (BTC fell ~−34% over it).

## What "before / after" means

| | Before | After |
|---|---|---|
| Edge-study reproducibility | `simulate()` infinite-looped on flat no-signal bars → committed report/CSV **could not be regenerated** | Loop fixed → reproduces committed numbers exactly |
| Deflated Sharpe (DSR) | scaling bug → **0.00 for every config** (uninformative) | correct & ordered (full-grid max **0.096**) |
| Buy-and-hold benchmark | none | every config scored vs HODL (return + drawdown) |
| Forward validation | none (IS numbers taken at face value) | anchored walk-forward (select-on-past, trade-next) |
| Live admission gate | net>0 + Sharpe≥0.8 (or OOS>0) → **23 configs live** | + DSR≥0.5 + beats-hold → **0 configs live** |

---

## 1. Trade-level detail — BTC 4h `ma_crossover` Intraday (momentum)

**166 trades** · win 43.4% · PF 1.29 · expectancy **+0.49%/trade** · avg hold 20 bars
avg win +5.02% · avg loss −2.98% · biggest win +11.3% · biggest loss −6.3%
exits: **72 TP / 94 SL / 0 time**
**$500 → $976 (+95.3%)** · peak $1,210 · maxDD −27.2% · Sharpe 1.83

| # | entry → exit | bars | price | pnl | exit | equity |
|--:|---|--:|---|--:|:--:|--:|
| 1 | 2024-01-29 → 01-30 | 2 | 42,066 → 43,001 | +2.12% | TP | $511 |
| 2 | 2024-01-31 → 02-01 | 7 | 43,040 → 42,258 | −1.92% | SL | $501 |
| 3 | 2024-02-01 → 02-07 | 38 | 42,518 → 43,978 | +3.33% | TP | $518 |
| 4 | 2024-02-08 → 02-09 | 6 | 44,540 → 46,041 | +3.27% | TP | $534 |
| 5 | 2024-02-09 → 02-09 | 3 | 46,236 → 48,059 | +3.84% | TP | $555 |
| … | … | | | | | |
| 162 | 2026-05-01 → 05-04 | 16 | 77,430 → 80,229 | +3.52% | TP | $1,058 |
| 163 | 2026-05-04 → 05-04 | 1 | 79,664 → 78,378 | −1.71% | SL | $1,040 |
| 164 | 2026-05-04 → 05-16 | 70 | 79,977 → 78,264 | −2.24% | SL | $1,017 |
| 165 | 2026-05-21 → 05-22 | 9 | 77,848 → 76,488 | −1.85% | SL | $998 |
| 166 | 2026-05-25 → 05-27 | 13 | 76,990 → 75,389 | −2.18% | SL | $976 |

**IN-SAMPLE $1,098 (+119.5%, 115 tr) → OUT-OF-SAMPLE $445 (−11.0%, 51 tr).**
The advertised +95% is entirely in-sample; forward it *loses* money. Note the
tail (#162–166): a string of stop-outs bleeding equity down — the regime turned
and the momentum edge inverted.

## 2. Trade-level detail — BTC 4h `bb_rsi_reversion` Aggressive (mean-reversion)

**92 trades** · win 32.6% · PF 1.53 · expectancy **+0.89%/trade** · avg hold 25 bars
avg win +7.82% · avg loss −2.47% · biggest win +19.1% · biggest loss −4.5%
exits: **28 TP / 62 SL / 2 time**
**$500 → $997 (+99.3%)** · peak $1,030 · maxDD −18.8% · Sharpe 2.62

| # | entry → exit | bars | price | pnl | exit | equity |
|--:|---|--:|---|--:|:--:|--:|
| 1 | 2024-02-17 → 02-26 | 52 | 51,404 → 54,331 | +5.59% | TP | $528 |
| 2 | 2024-03-15 → 03-16 | 8 | 68,204 → 65,498 | −4.07% | SL | $506 |
| 3 | 2024-03-20 → 03-26 | 36 | 63,008 → 71,583 | +13.51% | TP | $575 |
| 4 | 2024-04-02 → 04-08 | 34 | 65,932 → 72,204 | +9.41% | TP | $629 |
| 5 | 2024-04-13 → 04-13 | 4 | 67,168 → 65,143 | −3.11% | SL | $609 |
| … | … | | | | | |
| 88 | 2026-03-27 → 04-07 | 66 | 66,371 → 70,990 | +6.86% | TP | $984 |
| 89 | 2026-04-20 → 04-22 | 13 | 74,594 → 78,126 | +4.63% | TP | $1,030 |
| 90 | 2026-05-13 → 05-16 | 15 | 79,602 → 78,348 | −1.67% | SL | $1,013 |
| 91 | 2026-05-23 → 05-27 | 26 | 75,487 → 74,282 | −1.70% | SL | $995 |
| 92 | 2026-05-28 → 05-30 | 11 | 73,487 → 73,636 | +0.10% | time | $997 |

**IN-SAMPLE $949 (+89.8%, 64 tr) → OUT-OF-SAMPLE $525 (+5.0%, 28 tr).**
Profile = low win rate (32.6%) but fat winners (avg +7.82% vs −2.47%). Unlike
momentum, it stayed **positive forward** while BTC fell — defensive, the one
real lead — but +5% over 9 months is Sharpe ≈ 0.

## 3. Reference: BTC buy-and-hold, same data, $500

Full period **$500 → $861 (+72.1%)**, maxDD ≈ −50%. Over the OOS window alone:
**−34%**. So forward, momentum (−11%) beat a falling BTC but still lost; mean-rev
(+5%) beat it and stayed green.

---

## 4. Config-level — what goes live, before vs after

Live feed reads `robustness_scan_results.csv` (525 configs, real data).

**BEFORE** gate (`net>0, OOS Sharpe>0, P(loss)≤35%`): **23 configs admitted.**
$500/config median **$696**; beats buy-and-hold only **11/23**; mean DSR **0.027**.

Top of what would have traded live:

| symbol·tf | strategy / profile | n | $500 | DSR | beats hold |
|---|---|--:|--:|--:|:--:|
| BTC 4h | bb_rsi_reversion / Aggressive | 92 | $997 (+99.3%) | 0.096 | ✅ |
| BTC 4h | ma_crossover / Intraday | 166 | $976 (+95.3%) | 0.062 | ✅ |
| BTC 4h | ma_crossover / Intraday_Trailing | 166 | $976 (+95.3%) | 0.062 | ✅ |
| BTC 4h | ma_crossover / Scale_Out_2R | 143 | $933 (+86.7%) | 0.052 | ✅ |
| BTC 4h | bb_rsi_reversion / Intraday | 93 | $881 (+76.3%) | 0.055 | ✅ |
| BTC 4h | vwap_cross / Intraday | 94 | $738 (+47.6%) | 0.027 | ❌ |

Note how redundant it is (the same 2–3 ideas in different SL/TP costumes) and
that several don't even beat hold.

**AFTER** gate (`+ DSR≥0.5 + beats buy-and-hold`): **0 configs admitted.**
Full-grid DSR ranges 0.000–0.096 — *nothing* is within 5× of the 0.5 bar.
(39 configs are net-positive, 99 beat hold, but none survive deflation.)

## 5. Forward proof — anchored walk-forward ($500, params chosen on past only)

| TF | WF $500 | Sharpe | n | DSR | BTC HODL (same span) |
|---|--:|--:|--:|--:|--:|
| 1h | $497 (−0.6%) | 0.11 | 59 | 0.003 | $436 (−12.7%) |
| 2h | $579 (+15.8%) | 4.14 | 19 | 0.040 | $439 (−12.3%) |
| 4h | $554 (+10.7%) | 1.83 | 23 | 0.012 | $439 (−12.3%) |

Cross-symbol (final BTC-selected params on OOS spans never used in selection):
ETH +19.6%, SOL +20.1% (SOL fell −38%). Real, but n too small → DSR ≪ 0.5.

---

## Verdict

- **Before:** the system reported a stable of "+76% to +99% on $500" winners and
  would have put **23** of them live — numbers that were (a) not reproducible
  and (b) pure in-sample. Run forward, the flagship momentum config turns
  **+119% IS into −11% OOS**.
- **After:** the same real trades, scored honestly — deflated for the 525-config
  search, benchmarked to buy-and-hold, and walk-forward tested — admit **0**
  configs. $500 is preserved in cash rather than chasing mirages.
- **The one real lead** is higher-timeframe mean-reversion (`bb_rsi_reversion`):
  positive and hold-beating out-of-sample and cross-symbol, but unprovable here
  (too few trades). Path to prove it: a 15–30 coin basket at 2h/4h — see
  [mean_reversion_sleeve_plan.md](mean_reversion_sleeve_plan.md).
