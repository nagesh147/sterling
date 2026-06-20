# Phase-0 validation — Kite directional vehicles (real data)

Backs the shipped defaults + UI `validated ✓ / experimental ⚠` badges. Same
7.5y real 1H index data, same IS(70%)/OOS(30%) split + Spearman harness as
`docs/kite_st_permutation_backtest.md`. Premium is BS-modelled (caveat unchanged);
deep-ITM is the least IV-sensitive region so model error is smallest there.

## Baseline (from the permutation report)
OTM/ATM long options: **0 / 60 configs OOS-positive.** The failure case.

## 0a — Deep-ITM depth (`kite_st_deep_itm_results.csv`)
| Index | best depth | OOS ret | OOS PF |
|---|---|---:|---:|
| NIFTY 50 | ITM5 | −3.3% | 0.99 |
| NIFTY BANK | ITM5 | +182.6% | 1.26 |
| NIFTY FIN SERVICE | ITM15 | +44.5% | 1.28 |
| SENSEX | ITM5 | +95.3% | 1.09 |

**3 / 4 indices OOS-positive** (NIFTY ~breakeven). Deep-ITM flips the OTM result.
→ **deep_itm_options = validated ✓.** Shipped default `itm_depth=ITM10` (safe
middle; ITM5 was frequently best — per-index optima are in the CSV).

## 0b — Futures / delta-1 (`kite_st_futures_results.csv`)
| Index | full PF | OOS ret | OOS PF |
|---|---:|---:|---:|
| NIFTY 50 | 1.30 | +17.5% | 1.12 |
| NIFTY BANK | 1.31 | +30.3% | 1.08 |
| NIFTY FIN SERVICE | 1.18 | −31.3% | 0.85 |
| SENSEX | 1.19 | +48.5% | 1.10 |

**3 / 4 OOS-positive** (FINNIFTY the laggard). → **futures = validated ✓** but
**opt-in** (margin + overnight gap risk; `enabled_vehicles` excludes it by default).

## 0c — Entry filters (`kite_st_filters_results.csv`)
ADX≥25–30 (± ATR-percentile) lifts OOS PF to **1.1–2.0**, BUT OOS trade counts
collapse to **n=12–29** — far below the ≥100/index small-sample gate.
→ **Not validated.** Shipped as **opt-in, default off** (`adx_min`/`atr_pct_min`
= None). Promising; must be paper-validated before trusting.

## Shipped defaults (consistent with the above)
- `directional_mode=False` → existing engine, untouched.
- `vehicle="otm_options"`, `enabled_vehicles=[otm_options, deep_itm_options]` →
  options-only by default; futures opt-in.
- Filters off; `wire_risk_infra=False`.

## Honest caveats
- Premium BS-modelled; absolute OOS returns illustrate the *mechanism* (deep-ITM ≫
  OTM), not guaranteed P&L. Paper-mode precedes any live capital.
- Edge is modest (PF ~1.1–1.3). Nothing here clears a deflated-Sharpe bar.
