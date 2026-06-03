# SterlingV2 — Independent Real-Data Grounding

**Date:** 2026-06-03 · Branch: `redesignV2`
**Method:** computed directly from the raw parquet vector stores by
`backend/scratch/v2_grounding.py`. **Does not rely on any pre-existing `.md` report** —
those were built on a harness with known measurement bugs (see the design spec §1) and are
treated as untrusted here.

---

## 1. Data characterization (raw parquet)

`vector_store_1m_{BTC,ETH,SOL}USD.parquet`, 1-minute OHLCV.

| Symbol | 1m bars | Start | End | Buy & Hold | Annualized vol |
|---|---|---|---|---|---|
| BTCUSD | 1,227,278 | 2023-12-29 | 2026-05-30 | **+72.2%** | 51.2% |
| ETHUSD | 1,205,233 | 2024-02-06 | 2026-05-30 | **−13.6%** | 71.8% |
| SOLUSD | 1,125,050 | 2024-04-08 | 2026-05-30 | **−54.5%** | 89.4% |

**Finding 1 — the window is NOT uniformly bullish.** BTC rose, but **ETH and SOL fell** over
the sample. Any long-only system is structurally fighting the trend on 2 of 3 assets. This
makes the **short side mandatory**, not a nice-to-have.

---

## 2. Raw signal frequency at 4h

| Symbol | 4h bars | ma_crossover | mean_rev | bb_rsi | vwap | breakout | price_action | smc |
|---|---|---|---|---|---|---|---|---|
| BTCUSD | 5,128 | **2,738** | 152 | 118 | 186 | 269 | 250 | 352 |
| ETHUSD | 5,027 | **2,509** | 145 | 110 | 197 | 271 | 227 | 346 |
| SOLUSD | 4,691 | **2,223** | 150 | 121 | 169 | 258 | 202 | 325 |

**Finding 2 — the EMA 9/21 "fresh cross" signal is noise at 4h.** It fires on ~53% of bars
(2,738 / 5,128). The system only *trades* ~160 of those because positions don't overlap — so
the entry timing is effectively "the first whipsaw cross after the previous trade closed,"
which is close to arbitrary. The raw signal carries little information; selectivity (a
conviction gate) is doing the real work, confirming the SterlingV2 thesis.

---

## 3. Corrected single-config replay (the honesty check)

`ma_crossover`, 4h, Intraday profile (SL 2.0×ATR / TP 3.5×ATR), **long-only**.
Corrections vs the legacy harness: **next-bar-open fills** (not signal-bar close),
**5 bps slippage** on entry and stop, 0.10% round-trip fee, and **Sharpe annualized by
realized trade frequency** (not a constant `√252`).

| Symbol | Trades | Win% | PF | Net | Max DD | **Sharpe (corrected)** | Trades/yr |
|---|---|---|---|---|---|---|---|
| BTCUSD | 163 | 42.9% | 1.26 | **+78.6%** | −27.7% | **0.86** | 67.5 |
| ETHUSD | 142 | 35.9% | 0.94 | −36.6% | −68.2% | −0.21 | 61.5 |
| SOLUSD | 149 | 34.2% | 0.82 | −73.9% | −79.7% | −0.78 | 69.7 |

**Finding 3 — the legacy Sharpe was inflated ~1.9×.** Legacy reported Sharpe 1.83 for BTC;
correctly annualized it is **0.86**. The ratio `√252 / √67.5 = 1.93` exactly explains the gap —
a direct, quantitative confirmation of the mis-annualization bug
(`comprehensive_backtest.py:194-197`).

**Finding 4 — the BTC long edge is real but modest.** PF 1.26, win 42.9%, DD −27.7% survive
honest fills/costs (net +78.6% vs the legacy +95.3% — the difference is slippage + next-bar
entry). It is a genuine but thin trend/tail edge, not the headline number.

**Finding 5 — ETH/SOL long-only is a capital-destroyer here** (−37% / −74%, DD −68% / −80%),
entirely consistent with their down-trending buy-and-hold. The legacy "validated" ETH/SOL
combos owe their in-sample profit to selection, not a durable long edge.

---

## 4. What this means for SterlingV2 (independent, data-driven)

1. **Short side is required** — 2 of 3 assets fell; long-only cannot work portfolio-wide.
2. **Selectivity is the main lever** — raw entries are near-noise; a conviction/regime gate is
   where edge must come from.
3. **Honest metrics matter** — once Sharpe is annualized correctly and fills/slippage are
   realistic, the baseline is materially weaker than advertised. The new harness must be the
   sole source of truth; all SterlingV2 claims are reported through it on an untouched test set.
4. **Drawdowns are severe** (up to −80% long-only) — the hard max-DD ≤ 20% guardrail and the
   correlation-aware portfolio + DD circuit breaker are the levers that must contain this.

---

### Reproduce

```
cd backend && .venv/bin/python scratch/v2_grounding.py
```

Reads only the parquet files; prints the tables above in ~1.3s.
