# Full-Cycle Stress Test — Does the Edge Survive a Bull?

The honest skeptic's objection to the conviction book was: *"Your whole track record
is one regime — the 2025-26 downturn where the short sleeves did the work. Nobody has
seen this survive a sustained bull."* This test answers it by extending the data back
to 2020 and re-running the **exact** book (`study.regime_book.select_conviction_book`,
unchanged) so the out-of-sample half now contains a real bull.

Data: real Binance 4h, BTC/ETH 2020-01-01→2026-06-10 (14,116 bars), SOL 2020-08-11→
(12,778). OOS = held-out last 50% of each symbol's calendar (≈ **2023-03 → 2026**),
which contains the **2023-24 BTC bull (~$16k→$73k)** and the 2025 downturn. Reproduce:
`cd backend && .venv/bin/python -m study.fullcycle_stress`.

## Pre-registered verdict criteria (frozen BEFORE the run)

**SURVIVE** only if ALL: OOS Sharpe > 0 · beats basket HODL · IS→OOS rank-corr ≥ 0
· no catastrophic year (short sleeves don't bleed out a bull). **Bonus:** DSR rises
above the prior 0.327. **KILL** if OOS Sharpe ≤ 0, IS→OOS corr < 0, or it blows up
in a bull year.

## Result — SURVIVES (all criteria met)

| | Full-cycle book | basket HODL | prior (2024-26 only) |
|---|--:|--:|--:|
| OOS return | **+150.7%** | +92.8% | +75.8% |
| OOS maxDD | **−30.4%** | **−68.5%** | −29% |
| OOS Sharpe | 1.16 | — | 1.57 |
| **DSR (grid=36)** | **0.394** | — | 0.327 |
| IS→OOS rank-corr | **+0.82** | — | +0.38 |
| OOS trades | 570 | — | 242 |

**Beats HODL on BOTH axes over a full round-trip cycle** (more return, < half the
drawdown). DSR rose 0.327 → **0.394** purely from more history + regime diversity
(same 36-cell grid, same IS-only selection — no tuning). IS→OOS correlation
strengthened to **+0.82** (in-sample quality strongly predicts out-of-sample — the
*opposite* of overfitting). Whole-grid OOS Sharpe mean +0.97 (broad, not one cell).

## Per-year regime readout — the killer objection, answered

Chosen params (adx=20, RSI<25/>70) over the full history, $500, 1×:

| Year | Book return | Sharpe | n | maxDD | Basket HODL | Regime |
|---|--:|--:|--:|--:|--:|---|
| 2020 | +100.0% | 2.74 | 149 | −23.0% | +239% | bull |
| 2021 | **+74.4%** | 2.24 | 174 | −19.5% | **+3652%** | **mania bull** |
| 2022 | **+16.3%** | 0.87 | 152 | −28.6% | **−75.6%** | brutal bear |
| 2023 | +64.7% | 1.81 | 176 | −19.3% | +389% | bull |
| 2024 | +63.2% | 1.78 | 178 | −24.2% | +84% | bull |
| 2025 | **−19.1%** | −0.56 | 190 | −28.3% | −17.5% | chop (the blemish) |
| 2026* | +68.0% | 3.64 | 83 | −28.1% | −41% | bear |

**It makes money in every bull year and did not blow up in the 2021 mania** (+74%
while the basket did +3652% — it doesn't out-run a raging bull, but it stays strongly
positive). It is **positive in the worst bear** (2022: +16% while HODL lost 76%).
Full-history compounded: **$500 → $7,405 (+1,381%), Sharpe 1.67, n=1,102, maxDD
−30.4%.**

## Honest caveats (the edge is stronger, still not bulletproof)

- **DSR 0.394 is still < 0.5** — closer, more credible, but *not yet
  deflation-provable*. The math still says "likely real, not proven."
- **2025 lost −19%** — one whipsaw year (≈ HODL's −17.5%). The book is not invincible;
  it has a bad-regime year.
- **It underperforms raw HODL inside a single raging bull** (2021: +74% vs +3652%). Its
  edge is *risk-adjusted and round-trip* (Sharpe, drawdown), not "beat HODL every year."
- Still 3 coins; fills/slippage on a live $500 account remain untested.

## Verdict

The killer objection is **defeated**: the book survives — and beats HODL on both axes
over — a full bull+bear+bull+bear cycle, with DSR rising to 0.394 and IS→OOS
correlation strengthening to +0.82. This is the most convincing evidence the project
has produced. It is materially *more* trustworthy than the single-regime result, while
remaining honest that DSR < 0.5 (not provable) and 2025 was a losing year.
