# SterlingV2 — COMPLETE Before/After Matrix (all TFs × strategies × profiles)

**BEFORE** = long-only (pre-V2) · **AFTER** = V2 levers (long+short where a short mirror exists, + vol-targeted sizing), same profile exits. $500 start; 0.10% fee + 5bps slippage/fill; next-bar fills; realized-frequency Sharpe.

> **Basis = FULL sample** (matches `baseline_report.md`). These are descriptive, in-sample-inclusive numbers. The OOS-validated result is `before_after_report.md` — only the **4h ma_crossover** family survived out-of-sample; high in-sample numbers at sub-4h / other strategies are mostly fees-vs-noise and did **not** generalize.

> Excluded: **1m** (compute-prohibitive, guaranteed fee wipeout) and **Scale_Out_2R** (partial scale-out not modeled by the single-exit harness). Strategies without a short mirror (mean_reversion, bb_rsi_reversion, vwap_cross) run AFTER as long-only + sizing.

## Aggregate: mean AFTER metrics by timeframe

| TF | mean AFTER Sharpe | mean AFTER Net% | mean AFTER $500→ | mean BEFORE Net% |
|---|---|---|---|---|
| 5m | -23.53 | -100 | $0 | -100 |
| 15m | -6.72 | -97 | $14 | -97 |
| 30m | -3.24 | -87 | $66 | -83 |
| 1h | -1.76 | -72 | $141 | -67 |
| 4h | -0.19 | -20 | $402 | -27 |

## Aggregate: mean AFTER metrics by profile

| Profile | mean AFTER Sharpe | mean AFTER Net% | mean AFTER $500→ |
|---|---|---|---|
| Scalping | -10.77 | -81 | $97 |
| Intraday | -3.67 | -68 | $160 |
| Aggressive | -4.09 | -73 | $137 |
| Intraday_Trailing | -9.82 | -79 | $104 |

## Aggregate: mean AFTER metrics by strategy

| Strategy | short? | mean AFTER Sharpe | mean AFTER Net% | mean AFTER $500→ |
|---|---|---|---|---|
| ma_crossover | yes | -9.49 | -78 | $112 |
| mean_reversion | no | -5.04 | -77 | $117 |
| bb_rsi_reversion | no | -4.56 | -66 | $170 |
| vwap_cross | no | -5.72 | -69 | $156 |
| breakout | yes | -8.25 | -79 | $103 |
| price_action | yes | -7.36 | -77 | $114 |
| smc | yes | -9.20 | -80 | $101 |

## Top 20 configs by AFTER outcome ($500 → )

| Symbol | TF | Strategy | Profile | BF $500→ | BF Sh | AF $500→ | AF Sh | AF PF | AF DD% | AF trades |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC | 4h | ma_crossover | Intraday | $893 | +0.88 | **$1291** | +1.28 | 1.42 | -27 | 165 |
| BTC | 4h | bb_rsi_reversion | Aggressive | $954 | +0.99 | **$1240** | +1.11 | 1.71 | -18 | 92 |
| BTC | 4h | bb_rsi_reversion | Intraday | $858 | +0.89 | **$974** | +0.96 | 1.48 | -22 | 92 |
| ETH | 4h | price_action | Intraday | $281 | -0.36 | **$943** | +0.78 | 1.29 | -44 | 118 |
| BTC | 4h | bb_rsi_reversion | Intraday_Trailing | $822 | +1.09 | **$851** | +1.09 | 1.65 | -12 | 116 |
| BTC | 4h | ma_crossover | Aggressive | $572 | +0.33 | **$756** | +0.65 | 1.21 | -42 | 160 |
| ETH | 4h | smc | Intraday | $248 | -0.42 | **$755** | +0.59 | 1.16 | -65 | 183 |
| BTC | 4h | smc | Intraday | $592 | +0.38 | **$731** | +0.61 | 1.17 | -36 | 176 |
| BTC | 4h | price_action | Intraday | $456 | +0.04 | **$712** | +0.58 | 1.19 | -35 | 139 |
| BTC | 4h | vwap_cross | Intraday | $667 | +0.58 | **$697** | +0.64 | 1.26 | -23 | 94 |
| ETH | 4h | ma_crossover | Intraday | $317 | -0.21 | **$672** | +0.49 | 1.16 | -61 | 142 |
| SOL | 4h | smc | Aggressive | $567 | +0.38 | **$667** | +0.57 | 1.19 | -50 | 190 |
| ETH | 4h | breakout | Aggressive | $274 | -0.63 | **$664** | +0.49 | 1.15 | -53 | 169 |
| BTC | 4h | breakout | Intraday | $600 | +0.44 | **$602** | +0.40 | 1.11 | -42 | 166 |
| ETH | 4h | smc | Aggressive | $377 | -0.03 | **$552** | +0.34 | 1.09 | -53 | 182 |
| ETH | 4h | bb_rsi_reversion | Scalping | $565 | +0.33 | **$545** | +0.27 | 1.10 | -24 | 108 |
| BTC | 4h | ma_crossover | Intraday_Trailing | $514 | +0.18 | **$542** | +0.26 | 1.06 | -47 | 415 |
| SOL | 4h | price_action | Intraday | $172 | -0.78 | **$536** | +0.39 | 1.14 | -53 | 119 |
| SOL | 4h | vwap_cross | Intraday_Trailing | $448 | -0.01 | **$529** | +0.24 | 1.10 | -38 | 144 |
| ETH | 4h | breakout | Scalping | $322 | -0.77 | **$521** | +0.21 | 1.05 | -32 | 256 |

## Full matrix (every cell)

Each row: BEFORE → AFTER. `$` = $500 end value. `Sh` Sharpe, `DD` max drawdown.

### BTCUSD · 5m

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $0 | -71.49 | -100 | -100 | **$0** | -74.09 | -100 | -100 | 27482 |
| ma_crossover | Intraday | $0 | -18.14 | -100 | -100 | **$0** | -18.73 | -100 | -100 | 8641 |
| ma_crossover | Aggressive | $0 | -21.43 | -100 | -100 | **$0** | -22.11 | -100 | -100 | 9934 |
| ma_crossover | Intraday_Trailing | $0 | -56.24 | -100 | -100 | **$0** | -58.68 | -100 | -100 | 21401 |
| mean_reversion | Scalping | $0 | -29.49 | -100 | -100 | **$0** | -29.48 | -100 | -100 | 6629 |
| mean_reversion | Intraday | $0 | -12.20 | -100 | -100 | **$0** | -12.27 | -100 | -100 | 4796 |
| mean_reversion | Aggressive | $0 | -13.94 | -100 | -100 | **$0** | -13.98 | -100 | -100 | 5119 |
| mean_reversion | Intraday_Trailing | $0 | -27.94 | -100 | -100 | **$0** | -27.93 | -100 | -100 | 6267 |
| bb_rsi_reversion | Scalping | $0 | -25.46 | -100 | -100 | **$0** | -25.45 | -100 | -100 | 5238 |
| bb_rsi_reversion | Intraday | $0 | -11.92 | -100 | -100 | **$0** | -11.96 | -100 | -100 | 4285 |
| bb_rsi_reversion | Aggressive | $0 | -13.11 | -100 | -100 | **$0** | -13.11 | -100 | -100 | 4466 |
| bb_rsi_reversion | Intraday_Trailing | $0 | -24.19 | -100 | -100 | **$0** | -24.19 | -100 | -100 | 5017 |
| vwap_cross | Scalping | $0 | -38.77 | -100 | -100 | **$0** | -38.76 | -100 | -100 | 8938 |
| vwap_cross | Intraday | $0 | -15.27 | -100 | -100 | **$0** | -15.26 | -100 | -100 | 5441 |
| vwap_cross | Aggressive | $0 | -17.38 | -100 | -100 | **$0** | -17.38 | -100 | -100 | 6187 |
| vwap_cross | Intraday_Trailing | $0 | -35.84 | -100 | -100 | **$0** | -35.84 | -100 | -100 | 8262 |
| breakout | Scalping | $0 | -41.88 | -100 | -100 | **$0** | -57.00 | -100 | -100 | 15522 |
| breakout | Intraday | $0 | -16.31 | -100 | -100 | **$0** | -20.87 | -100 | -100 | 8931 |
| breakout | Aggressive | $0 | -18.38 | -100 | -100 | **$0** | -23.80 | -100 | -100 | 9903 |
| breakout | Intraday_Trailing | $0 | -34.90 | -100 | -100 | **$0** | -46.99 | -100 | -100 | 13706 |
| price_action | Scalping | $0 | -34.83 | -100 | -100 | **$0** | -46.08 | -100 | -100 | 14021 |
| price_action | Intraday | $0 | -13.22 | -100 | -100 | **$0** | -17.34 | -100 | -100 | 7266 |
| price_action | Aggressive | $0 | -15.01 | -100 | -100 | **$0** | -19.60 | -100 | -100 | 8109 |
| price_action | Intraday_Trailing | $0 | -34.83 | -100 | -100 | **$0** | -45.59 | -100 | -100 | 13292 |
| smc | Scalping | $0 | -49.32 | -100 | -100 | **$0** | -66.70 | -100 | -100 | 24868 |
| smc | Intraday | $0 | -16.94 | -100 | -100 | **$0** | -20.24 | -100 | -100 | 10319 |
| smc | Aggressive | $0 | -18.73 | -100 | -100 | **$0** | -22.85 | -100 | -100 | 11865 |
| smc | Intraday_Trailing | $0 | -44.16 | -100 | -100 | **$0** | -58.28 | -100 | -100 | 22308 |

### BTCUSD · 15m

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $0 | -17.76 | -100 | -100 | **$0** | -18.59 | -100 | -100 | 7121 |
| ma_crossover | Intraday | $14 | -4.26 | -97 | -98 | **$14** | -4.19 | -97 | -98 | 2373 |
| ma_crossover | Aggressive | $9 | -4.90 | -98 | -98 | **$7** | -5.02 | -99 | -99 | 2625 |
| ma_crossover | Intraday_Trailing | $0 | -16.92 | -100 | -100 | **$0** | -17.94 | -100 | -100 | 6647 |
| mean_reversion | Scalping | $10 | -9.25 | -98 | -98 | **$10** | -9.32 | -98 | -98 | 1933 |
| mean_reversion | Intraday | $35 | -3.66 | -93 | -94 | **$38** | -3.54 | -92 | -94 | 1425 |
| mean_reversion | Aggressive | $17 | -4.74 | -97 | -97 | **$18** | -4.68 | -96 | -97 | 1532 |
| mean_reversion | Intraday_Trailing | $10 | -8.69 | -98 | -98 | **$10** | -8.66 | -98 | -98 | 1868 |
| bb_rsi_reversion | Scalping | $15 | -8.98 | -97 | -97 | **$15** | -9.05 | -97 | -97 | 1657 |
| bb_rsi_reversion | Intraday | $37 | -3.77 | -93 | -93 | **$36** | -3.83 | -93 | -93 | 1300 |
| bb_rsi_reversion | Aggressive | $34 | -3.94 | -93 | -94 | **$32** | -4.04 | -94 | -94 | 1354 |
| bb_rsi_reversion | Intraday_Trailing | $17 | -8.69 | -97 | -97 | **$16** | -8.86 | -97 | -97 | 1599 |
| vwap_cross | Scalping | $8 | -10.04 | -98 | -98 | **$8** | -10.03 | -98 | -98 | 2586 |
| vwap_cross | Intraday | $78 | -2.82 | -84 | -85 | **$78** | -2.83 | -84 | -85 | 1516 |
| vwap_cross | Aggressive | $50 | -3.41 | -90 | -90 | **$51** | -3.39 | -90 | -90 | 1724 |
| vwap_cross | Intraday_Trailing | $7 | -10.12 | -99 | -99 | **$7** | -10.13 | -99 | -99 | 2573 |
| breakout | Scalping | $3 | -13.40 | -99 | -99 | **$0** | -17.22 | -100 | -100 | 4486 |
| breakout | Intraday | $26 | -4.81 | -95 | -95 | **$4** | -5.90 | -99 | -99 | 2517 |
| breakout | Aggressive | $21 | -5.44 | -96 | -96 | **$2** | -7.17 | -100 | -100 | 2765 |
| breakout | Intraday_Trailing | $8 | -10.54 | -98 | -98 | **$0** | -15.07 | -100 | -100 | 4227 |
| price_action | Scalping | $3 | -10.90 | -99 | -99 | **$0** | -14.88 | -100 | -100 | 4505 |
| price_action | Intraday | $30 | -3.68 | -94 | -95 | **$9** | -4.61 | -98 | -98 | 2199 |
| price_action | Aggressive | $18 | -4.52 | -96 | -96 | **$4** | -5.71 | -99 | -99 | 2374 |
| price_action | Intraday_Trailing | $2 | -11.68 | -100 | -100 | **$0** | -15.12 | -100 | -100 | 4521 |
| smc | Scalping | $1 | -13.29 | -100 | -100 | **$0** | -17.68 | -100 | -100 | 6352 |
| smc | Intraday | $18 | -4.10 | -96 | -97 | **$3** | -5.34 | -99 | -99 | 2709 |
| smc | Aggressive | $14 | -4.45 | -97 | -98 | **$2** | -6.10 | -100 | -100 | 2936 |
| smc | Intraday_Trailing | $1 | -13.08 | -100 | -100 | **$0** | -17.94 | -100 | -100 | 6249 |

### BTCUSD · 30m

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $1 | -8.85 | -100 | -100 | **$1** | -9.06 | -100 | -100 | 3365 |
| ma_crossover | Intraday | $104 | -1.79 | -79 | -83 | **$138** | -1.40 | -72 | -79 | 1160 |
| ma_crossover | Aggressive | $89 | -1.98 | -82 | -86 | **$89** | -1.89 | -82 | -87 | 1279 |
| ma_crossover | Intraday_Trailing | $3 | -7.75 | -99 | -99 | **$2** | -8.34 | -100 | -100 | 3164 |
| mean_reversion | Scalping | $67 | -4.62 | -87 | -88 | **$71** | -4.45 | -86 | -87 | 1007 |
| mean_reversion | Intraday | $160 | -1.47 | -68 | -72 | **$180** | -1.29 | -64 | -70 | 731 |
| mean_reversion | Aggressive | $155 | -1.44 | -69 | -73 | **$167** | -1.32 | -67 | -72 | 787 |
| mean_reversion | Intraday_Trailing | $67 | -4.30 | -87 | -88 | **$69** | -4.17 | -86 | -87 | 980 |
| bb_rsi_reversion | Scalping | $69 | -5.07 | -86 | -87 | **$71** | -5.02 | -86 | -87 | 855 |
| bb_rsi_reversion | Intraday | $171 | -1.46 | -66 | -75 | **$186** | -1.32 | -63 | -74 | 663 |
| bb_rsi_reversion | Aggressive | $170 | -1.38 | -66 | -71 | **$177** | -1.32 | -65 | -71 | 719 |
| bb_rsi_reversion | Intraday_Trailing | $100 | -3.90 | -80 | -81 | **$100** | -3.88 | -80 | -81 | 828 |
| vwap_cross | Scalping | $88 | -4.17 | -82 | -83 | **$89** | -4.14 | -82 | -83 | 1179 |
| vwap_cross | Intraday | $230 | -1.11 | -54 | -60 | **$240** | -1.04 | -52 | -59 | 682 |
| vwap_cross | Aggressive | $197 | -1.30 | -61 | -63 | **$209** | -1.20 | -58 | -62 | 777 |
| vwap_cross | Intraday_Trailing | $80 | -4.44 | -84 | -84 | **$80** | -4.42 | -84 | -84 | 1148 |
| breakout | Scalping | $44 | -6.44 | -91 | -91 | **$9** | -7.36 | -98 | -98 | 2123 |
| breakout | Intraday | $85 | -2.83 | -83 | -85 | **$36** | -3.08 | -93 | -93 | 1268 |
| breakout | Aggressive | $128 | -2.21 | -74 | -77 | **$54** | -2.64 | -89 | -90 | 1292 |
| breakout | Intraday_Trailing | $55 | -5.68 | -89 | -89 | **$8** | -7.35 | -98 | -98 | 2054 |
| price_action | Scalping | $36 | -5.34 | -93 | -93 | **$5** | -7.60 | -99 | -99 | 2238 |
| price_action | Intraday | $98 | -1.99 | -80 | -84 | **$20** | -3.50 | -96 | -96 | 1125 |
| price_action | Aggressive | $123 | -1.65 | -75 | -78 | **$63** | -2.14 | -87 | -88 | 1204 |
| price_action | Intraday_Trailing | $31 | -5.62 | -94 | -94 | **$5** | -7.63 | -99 | -99 | 2257 |
| smc | Scalping | $24 | -5.69 | -95 | -96 | **$2** | -7.81 | -100 | -100 | 3003 |
| smc | Intraday | $113 | -1.70 | -77 | -83 | **$62** | -2.06 | -88 | -88 | 1340 |
| smc | Aggressive | $153 | -1.30 | -69 | -78 | **$55** | -2.15 | -89 | -89 | 1482 |
| smc | Intraday_Trailing | $25 | -5.66 | -95 | -95 | **$2** | -7.98 | -100 | -100 | 2930 |

### BTCUSD · 1h

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $30 | -4.23 | -94 | -94 | **$25** | -4.43 | -95 | -96 | 1674 |
| ma_crossover | Intraday | $273 | -0.60 | -45 | -63 | **$331** | -0.34 | -34 | -59 | 577 |
| ma_crossover | Aggressive | $240 | -0.78 | -52 | -64 | **$248** | -0.72 | -50 | -64 | 638 |
| ma_crossover | Intraday_Trailing | $30 | -4.36 | -94 | -95 | **$26** | -4.44 | -95 | -95 | 1655 |
| mean_reversion | Scalping | $184 | -2.14 | -63 | -66 | **$188** | -2.05 | -62 | -66 | 532 |
| mean_reversion | Intraday | $222 | -0.96 | -56 | -64 | **$247** | -0.80 | -51 | -64 | 395 |
| mean_reversion | Aggressive | $219 | -0.99 | -56 | -65 | **$241** | -0.85 | -52 | -64 | 400 |
| mean_reversion | Intraday_Trailing | $152 | -2.73 | -70 | -71 | **$152** | -2.71 | -70 | -71 | 514 |
| bb_rsi_reversion | Scalping | $126 | -3.67 | -75 | -76 | **$127** | -3.62 | -75 | -76 | 432 |
| bb_rsi_reversion | Intraday | $177 | -1.44 | -65 | -71 | **$206** | -1.18 | -59 | -70 | 334 |
| bb_rsi_reversion | Aggressive | $161 | -1.60 | -68 | -75 | **$187** | -1.36 | -63 | -72 | 357 |
| bb_rsi_reversion | Intraday_Trailing | $184 | -2.49 | -63 | -67 | **$186** | -2.46 | -63 | -66 | 416 |
| vwap_cross | Scalping | $229 | -1.89 | -54 | -61 | **$233** | -1.83 | -53 | -61 | 579 |
| vwap_cross | Intraday | $320 | -0.63 | -36 | -49 | **$351** | -0.46 | -30 | -48 | 352 |
| vwap_cross | Aggressive | $331 | -0.53 | -34 | -46 | **$360** | -0.38 | -28 | -46 | 401 |
| vwap_cross | Intraday_Trailing | $206 | -2.21 | -59 | -62 | **$210** | -2.13 | -58 | -62 | 577 |
| breakout | Scalping | $122 | -3.88 | -76 | -76 | **$62** | -3.92 | -88 | -88 | 1051 |
| breakout | Intraday | $130 | -2.25 | -74 | -76 | **$146** | -1.43 | -71 | -72 | 622 |
| breakout | Aggressive | $151 | -2.08 | -70 | -72 | **$101** | -2.01 | -80 | -81 | 663 |
| breakout | Intraday_Trailing | $171 | -3.01 | -66 | -68 | **$67** | -3.86 | -87 | -87 | 1034 |
| price_action | Scalping | $167 | -2.17 | -67 | -70 | **$49** | -3.81 | -90 | -91 | 1121 |
| price_action | Intraday | $478 | +0.10 | -4 | -49 | **$160** | -1.12 | -68 | -74 | 607 |
| price_action | Aggressive | $354 | -0.29 | -29 | -53 | **$153** | -1.16 | -69 | -71 | 660 |
| price_action | Intraday_Trailing | $213 | -1.65 | -57 | -63 | **$117** | -2.27 | -77 | -79 | 1110 |
| smc | Scalping | $81 | -3.47 | -84 | -84 | **$35** | -3.94 | -93 | -93 | 1430 |
| smc | Intraday | $220 | -0.86 | -56 | -64 | **$148** | -1.12 | -70 | -72 | 682 |
| smc | Aggressive | $269 | -0.65 | -46 | -64 | **$166** | -1.04 | -67 | -78 | 768 |
| smc | Intraday_Trailing | $91 | -3.44 | -82 | -83 | **$28** | -4.57 | -94 | -94 | 1415 |

### BTCUSD · 4h

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $239 | -1.02 | -52 | -65 | **$253** | -0.90 | -49 | -65 | 427 |
| ma_crossover | Intraday | $893 | +0.88 | +79 | -28 | **$1291** | +1.28 | +158 | -27 | 165 |
| ma_crossover | Aggressive | $572 | +0.33 | +14 | -45 | **$756** | +0.65 | +51 | -42 | 160 |
| ma_crossover | Intraday_Trailing | $514 | +0.18 | +3 | -45 | **$542** | +0.26 | +8 | -47 | 415 |
| mean_reversion | Scalping | $347 | -0.74 | -31 | -42 | **$361** | -0.63 | -28 | -41 | 136 |
| mean_reversion | Intraday | $434 | -0.03 | -13 | -46 | **$471** | +0.11 | -6 | -46 | 103 |
| mean_reversion | Aggressive | $333 | -0.48 | -33 | -54 | **$338** | -0.34 | -32 | -56 | 103 |
| mean_reversion | Intraday_Trailing | $359 | -0.61 | -28 | -38 | **$360** | -0.57 | -28 | -38 | 134 |
| bb_rsi_reversion | Scalping | $513 | +0.15 | +3 | -21 | **$504** | +0.11 | +1 | -21 | 116 |
| bb_rsi_reversion | Intraday | $858 | +0.89 | +72 | -24 | **$974** | +0.96 | +95 | -22 | 92 |
| bb_rsi_reversion | Aggressive | $954 | +0.99 | +91 | -19 | **$1240** | +1.11 | +148 | -18 | 92 |
| bb_rsi_reversion | Intraday_Trailing | $822 | +1.09 | +64 | -13 | **$851** | +1.09 | +70 | -12 | 116 |
| vwap_cross | Scalping | $439 | -0.23 | -12 | -21 | **$466** | -0.08 | -7 | -21 | 145 |
| vwap_cross | Intraday | $667 | +0.58 | +33 | -25 | **$697** | +0.64 | +39 | -23 | 94 |
| vwap_cross | Aggressive | $374 | -0.31 | -25 | -42 | **$427** | -0.09 | -15 | -39 | 102 |
| vwap_cross | Intraday_Trailing | $434 | -0.27 | -13 | -21 | **$433** | -0.28 | -13 | -21 | 149 |
| breakout | Scalping | $334 | -1.06 | -33 | -39 | **$274** | -1.05 | -45 | -54 | 264 |
| breakout | Intraday | $600 | +0.44 | +20 | -29 | **$602** | +0.40 | +20 | -42 | 166 |
| breakout | Aggressive | $309 | -0.75 | -38 | -57 | **$289** | -0.50 | -42 | -68 | 177 |
| breakout | Intraday_Trailing | $408 | -0.53 | -18 | -30 | **$301** | -0.96 | -40 | -47 | 262 |
| price_action | Scalping | $278 | -1.15 | -44 | -48 | **$363** | -0.41 | -27 | -42 | 282 |
| price_action | Intraday | $456 | +0.04 | -9 | -34 | **$712** | +0.58 | +42 | -35 | 139 |
| price_action | Aggressive | $265 | -0.74 | -47 | -57 | **$312** | -0.35 | -38 | -56 | 162 |
| price_action | Intraday_Trailing | $395 | -0.33 | -21 | -40 | **$453** | +0.02 | -9 | -33 | 296 |
| smc | Scalping | $406 | -0.29 | -19 | -37 | **$287** | -0.65 | -43 | -61 | 398 |
| smc | Intraday | $592 | +0.38 | +18 | -46 | **$731** | +0.61 | +46 | -36 | 176 |
| smc | Aggressive | $424 | -0.07 | -15 | -47 | **$316** | -0.35 | -37 | -55 | 193 |
| smc | Intraday_Trailing | $457 | -0.05 | -9 | -37 | **$199** | -1.17 | -60 | -67 | 386 |

### ETHUSD · 5m

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $0 | -46.64 | -100 | -100 | **$0** | -48.57 | -100 | -100 | 24118 |
| ma_crossover | Intraday | $0 | -13.12 | -100 | -100 | **$0** | -13.89 | -100 | -100 | 8249 |
| ma_crossover | Aggressive | $0 | -14.56 | -100 | -100 | **$0** | -15.28 | -100 | -100 | 9284 |
| ma_crossover | Intraday_Trailing | $0 | -39.29 | -100 | -100 | **$0** | -40.87 | -100 | -100 | 21050 |
| mean_reversion | Scalping | $0 | -18.63 | -100 | -100 | **$0** | -18.63 | -100 | -100 | 6292 |
| mean_reversion | Intraday | $0 | -9.19 | -100 | -100 | **$0** | -9.18 | -100 | -100 | 4686 |
| mean_reversion | Aggressive | $0 | -9.73 | -100 | -100 | **$0** | -9.68 | -100 | -100 | 4942 |
| mean_reversion | Intraday_Trailing | $0 | -17.95 | -100 | -100 | **$0** | -17.93 | -100 | -100 | 6026 |
| bb_rsi_reversion | Scalping | $0 | -18.32 | -100 | -100 | **$0** | -18.29 | -100 | -100 | 5218 |
| bb_rsi_reversion | Intraday | $0 | -8.75 | -100 | -100 | **$0** | -8.73 | -100 | -100 | 4174 |
| bb_rsi_reversion | Aggressive | $0 | -9.10 | -100 | -100 | **$0** | -9.04 | -100 | -100 | 4297 |
| bb_rsi_reversion | Intraday_Trailing | $0 | -16.94 | -100 | -100 | **$0** | -16.92 | -100 | -100 | 5011 |
| vwap_cross | Scalping | $0 | -28.00 | -100 | -100 | **$0** | -27.99 | -100 | -100 | 8749 |
| vwap_cross | Intraday | $0 | -10.87 | -100 | -100 | **$0** | -10.91 | -100 | -100 | 5163 |
| vwap_cross | Aggressive | $0 | -11.75 | -100 | -100 | **$0** | -11.74 | -100 | -100 | 5880 |
| vwap_cross | Intraday_Trailing | $0 | -25.51 | -100 | -100 | **$0** | -25.51 | -100 | -100 | 8142 |
| breakout | Scalping | $0 | -28.10 | -100 | -100 | **$0** | -36.40 | -100 | -100 | 13798 |
| breakout | Intraday | $0 | -9.73 | -100 | -100 | **$0** | -13.02 | -100 | -100 | 8389 |
| breakout | Aggressive | $0 | -11.78 | -100 | -100 | **$0** | -14.86 | -100 | -100 | 8952 |
| breakout | Intraday_Trailing | $0 | -24.33 | -100 | -100 | **$0** | -30.56 | -100 | -100 | 12919 |
| price_action | Scalping | $0 | -23.21 | -100 | -100 | **$0** | -30.96 | -100 | -100 | 13642 |
| price_action | Intraday | $0 | -9.80 | -100 | -100 | **$0** | -10.65 | -100 | -100 | 7026 |
| price_action | Aggressive | $0 | -10.91 | -100 | -100 | **$0** | -12.76 | -100 | -100 | 7609 |
| price_action | Intraday_Trailing | $0 | -22.58 | -100 | -100 | **$0** | -29.08 | -100 | -100 | 13255 |
| smc | Scalping | $0 | -34.48 | -100 | -100 | **$0** | -45.33 | -100 | -100 | 23073 |
| smc | Intraday | $0 | -11.31 | -100 | -100 | **$0** | -13.16 | -100 | -100 | 9596 |
| smc | Aggressive | $0 | -13.04 | -100 | -100 | **$0** | -15.42 | -100 | -100 | 10816 |
| smc | Intraday_Trailing | $0 | -30.95 | -100 | -100 | **$0** | -39.78 | -100 | -100 | 21565 |

### ETHUSD · 15m

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $0 | -12.50 | -100 | -100 | **$0** | -12.91 | -100 | -100 | 6777 |
| ma_crossover | Intraday | $10 | -3.31 | -98 | -98 | **$14** | -2.98 | -97 | -97 | 2432 |
| ma_crossover | Aggressive | $11 | -3.32 | -98 | -98 | **$9** | -3.44 | -98 | -98 | 2549 |
| ma_crossover | Intraday_Trailing | $0 | -11.90 | -100 | -100 | **$0** | -12.52 | -100 | -100 | 6617 |
| mean_reversion | Scalping | $9 | -6.75 | -98 | -98 | **$9** | -6.72 | -98 | -98 | 1979 |
| mean_reversion | Intraday | $32 | -2.58 | -94 | -94 | **$33** | -2.56 | -93 | -95 | 1458 |
| mean_reversion | Aggressive | $24 | -2.85 | -95 | -96 | **$25** | -2.80 | -95 | -96 | 1554 |
| mean_reversion | Intraday_Trailing | $11 | -6.05 | -98 | -98 | **$11** | -5.94 | -98 | -98 | 1926 |
| bb_rsi_reversion | Scalping | $18 | -5.93 | -96 | -96 | **$18** | -5.88 | -96 | -96 | 1711 |
| bb_rsi_reversion | Intraday | $38 | -2.49 | -92 | -93 | **$39** | -2.46 | -92 | -93 | 1350 |
| bb_rsi_reversion | Aggressive | $28 | -2.96 | -94 | -95 | **$30** | -2.90 | -94 | -95 | 1407 |
| bb_rsi_reversion | Intraday_Trailing | $26 | -4.91 | -95 | -95 | **$27** | -4.75 | -95 | -95 | 1659 |
| vwap_cross | Scalping | $8 | -7.43 | -98 | -98 | **$8** | -7.41 | -98 | -98 | 2551 |
| vwap_cross | Intraday | $65 | -2.25 | -87 | -89 | **$67** | -2.22 | -87 | -88 | 1476 |
| vwap_cross | Aggressive | $29 | -3.10 | -94 | -95 | **$32** | -3.00 | -94 | -94 | 1705 |
| vwap_cross | Intraday_Trailing | $9 | -6.86 | -98 | -98 | **$9** | -6.81 | -98 | -98 | 2498 |
| breakout | Scalping | $6 | -8.44 | -99 | -99 | **$0** | -9.92 | -100 | -100 | 4098 |
| breakout | Intraday | $38 | -3.02 | -92 | -93 | **$15** | -2.94 | -97 | -97 | 2410 |
| breakout | Aggressive | $37 | -3.21 | -93 | -93 | **$17** | -2.90 | -97 | -97 | 2488 |
| breakout | Intraday_Trailing | $14 | -7.05 | -97 | -97 | **$1** | -8.76 | -100 | -100 | 3964 |
| price_action | Scalping | $2 | -7.81 | -100 | -100 | **$0** | -9.43 | -100 | -100 | 4440 |
| price_action | Intraday | $29 | -2.44 | -94 | -96 | **$15** | -2.65 | -97 | -98 | 2202 |
| price_action | Aggressive | $13 | -3.36 | -97 | -98 | **$17** | -2.58 | -97 | -97 | 2374 |
| price_action | Intraday_Trailing | $2 | -7.79 | -100 | -100 | **$0** | -9.35 | -100 | -100 | 4534 |
| smc | Scalping | $1 | -9.01 | -100 | -100 | **$0** | -10.79 | -100 | -100 | 6256 |
| smc | Intraday | $28 | -2.44 | -94 | -96 | **$15** | -2.51 | -97 | -97 | 2624 |
| smc | Aggressive | $17 | -2.95 | -97 | -97 | **$13** | -2.62 | -97 | -98 | 2878 |
| smc | Intraday_Trailing | $1 | -8.36 | -100 | -100 | **$0** | -10.94 | -100 | -100 | 6100 |

### ETHUSD · 30m

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $2 | -6.23 | -100 | -100 | **$2** | -6.23 | -100 | -100 | 3227 |
| ma_crossover | Intraday | $59 | -1.76 | -88 | -91 | **$39** | -2.08 | -92 | -94 | 1210 |
| ma_crossover | Aggressive | $59 | -1.83 | -88 | -91 | **$46** | -1.96 | -91 | -93 | 1225 |
| ma_crossover | Intraday_Trailing | $2 | -5.95 | -100 | -100 | **$2** | -6.23 | -100 | -100 | 3199 |
| mean_reversion | Scalping | $56 | -3.54 | -89 | -90 | **$57** | -3.45 | -89 | -90 | 998 |
| mean_reversion | Intraday | $54 | -2.10 | -89 | -91 | **$56** | -2.04 | -89 | -91 | 737 |
| mean_reversion | Aggressive | $98 | -1.46 | -80 | -84 | **$106** | -1.35 | -79 | -83 | 777 |
| mean_reversion | Intraday_Trailing | $50 | -3.62 | -90 | -91 | **$55** | -3.34 | -89 | -91 | 977 |
| bb_rsi_reversion | Scalping | $61 | -3.64 | -88 | -88 | **$61** | -3.57 | -88 | -88 | 870 |
| bb_rsi_reversion | Intraday | $66 | -1.94 | -87 | -89 | **$71** | -1.85 | -86 | -88 | 693 |
| bb_rsi_reversion | Aggressive | $92 | -1.62 | -82 | -86 | **$99** | -1.52 | -80 | -85 | 730 |
| bb_rsi_reversion | Intraday_Trailing | $70 | -3.43 | -86 | -88 | **$69** | -3.39 | -86 | -88 | 847 |
| vwap_cross | Scalping | $81 | -3.21 | -84 | -85 | **$81** | -3.19 | -84 | -85 | 1139 |
| vwap_cross | Intraday | $176 | -1.08 | -65 | -71 | **$181** | -1.05 | -64 | -70 | 699 |
| vwap_cross | Aggressive | $90 | -1.93 | -82 | -84 | **$92** | -1.89 | -82 | -84 | 781 |
| vwap_cross | Intraday_Trailing | $89 | -3.03 | -82 | -84 | **$92** | -2.93 | -82 | -84 | 1128 |
| breakout | Scalping | $54 | -4.29 | -89 | -90 | **$10** | -5.22 | -98 | -98 | 2000 |
| breakout | Intraday | $99 | -1.87 | -80 | -81 | **$69** | -1.60 | -86 | -87 | 1220 |
| breakout | Aggressive | $164 | -1.25 | -67 | -69 | **$119** | -1.13 | -76 | -77 | 1226 |
| breakout | Intraday_Trailing | $83 | -3.52 | -83 | -84 | **$29** | -3.50 | -94 | -94 | 1956 |
| price_action | Scalping | $48 | -3.37 | -90 | -91 | **$7** | -4.89 | -99 | -99 | 2314 |
| price_action | Intraday | $83 | -1.50 | -83 | -86 | **$19** | -2.49 | -96 | -97 | 1195 |
| price_action | Aggressive | $108 | -1.31 | -78 | -82 | **$36** | -2.06 | -93 | -93 | 1238 |
| price_action | Intraday_Trailing | $69 | -2.65 | -86 | -88 | **$10** | -4.30 | -98 | -98 | 2350 |
| smc | Scalping | $19 | -4.39 | -96 | -96 | **$2** | -5.55 | -100 | -100 | 2929 |
| smc | Intraday | $140 | -0.96 | -72 | -82 | **$139** | -0.74 | -72 | -74 | 1294 |
| smc | Aggressive | $128 | -1.09 | -74 | -82 | **$70** | -1.32 | -86 | -87 | 1442 |
| smc | Intraday_Trailing | $31 | -3.77 | -94 | -95 | **$4** | -4.87 | -99 | -99 | 2923 |

### ETHUSD · 1h

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $12 | -4.18 | -98 | -98 | **$11** | -4.09 | -98 | -98 | 1653 |
| ma_crossover | Intraday | $138 | -0.97 | -72 | -79 | **$195** | -0.63 | -61 | -72 | 602 |
| ma_crossover | Aggressive | $94 | -1.37 | -81 | -86 | **$126** | -1.02 | -75 | -82 | 651 |
| ma_crossover | Intraday_Trailing | $16 | -3.76 | -97 | -97 | **$14** | -3.67 | -97 | -98 | 1645 |
| mean_reversion | Scalping | $138 | -1.90 | -72 | -76 | **$142** | -1.82 | -72 | -75 | 547 |
| mean_reversion | Intraday | $213 | -0.66 | -57 | -65 | **$252** | -0.47 | -50 | -62 | 397 |
| mean_reversion | Aggressive | $249 | -0.52 | -50 | -60 | **$315** | -0.25 | -37 | -56 | 407 |
| mean_reversion | Intraday_Trailing | $132 | -2.19 | -74 | -77 | **$139** | -2.07 | -72 | -75 | 516 |
| bb_rsi_reversion | Scalping | $229 | -1.21 | -54 | -63 | **$236** | -1.14 | -53 | -62 | 438 |
| bb_rsi_reversion | Intraday | $124 | -1.26 | -75 | -80 | **$135** | -1.15 | -73 | -79 | 343 |
| bb_rsi_reversion | Aggressive | $112 | -1.47 | -78 | -82 | **$124** | -1.33 | -75 | -81 | 357 |
| bb_rsi_reversion | Intraday_Trailing | $207 | -1.40 | -59 | -65 | **$223** | -1.19 | -55 | -65 | 431 |
| vwap_cross | Scalping | $140 | -2.21 | -72 | -73 | **$146** | -2.10 | -71 | -73 | 591 |
| vwap_cross | Intraday | $211 | -0.82 | -58 | -75 | **$231** | -0.70 | -54 | -74 | 374 |
| vwap_cross | Aggressive | $146 | -1.29 | -71 | -78 | **$154** | -1.21 | -69 | -77 | 409 |
| vwap_cross | Intraday_Trailing | $135 | -2.18 | -73 | -75 | **$136** | -2.16 | -73 | -75 | 593 |
| breakout | Scalping | $192 | -1.76 | -62 | -63 | **$61** | -2.73 | -88 | -88 | 994 |
| breakout | Intraday | $220 | -0.85 | -56 | -59 | **$142** | -0.90 | -72 | -74 | 636 |
| breakout | Aggressive | $210 | -0.97 | -58 | -64 | **$208** | -0.58 | -58 | -64 | 641 |
| breakout | Intraday_Trailing | $203 | -1.68 | -59 | -64 | **$88** | -2.16 | -82 | -83 | 986 |
| price_action | Scalping | $104 | -2.13 | -79 | -81 | **$43** | -2.79 | -91 | -92 | 1138 |
| price_action | Intraday | $121 | -1.15 | -76 | -80 | **$18** | -2.69 | -96 | -96 | 584 |
| price_action | Aggressive | $88 | -1.57 | -82 | -85 | **$20** | -2.72 | -96 | -96 | 618 |
| price_action | Intraday_Trailing | $87 | -2.47 | -83 | -83 | **$20** | -3.92 | -96 | -96 | 1187 |
| smc | Scalping | $91 | -2.22 | -82 | -82 | **$25** | -3.09 | -95 | -95 | 1417 |
| smc | Intraday | $112 | -1.18 | -78 | -82 | **$134** | -0.76 | -73 | -83 | 678 |
| smc | Aggressive | $176 | -0.79 | -65 | -72 | **$272** | -0.23 | -46 | -62 | 694 |
| smc | Intraday_Trailing | $118 | -2.02 | -76 | -78 | **$66** | -2.04 | -87 | -87 | 1398 |

### ETHUSD · 4h

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $209 | -0.80 | -58 | -71 | **$203** | -0.78 | -59 | -73 | 433 |
| ma_crossover | Intraday | $317 | -0.21 | -37 | -68 | **$672** | +0.49 | +34 | -61 | 142 |
| ma_crossover | Aggressive | $230 | -0.49 | -54 | -71 | **$306** | -0.16 | -39 | -70 | 180 |
| ma_crossover | Intraday_Trailing | $185 | -0.93 | -63 | -74 | **$214** | -0.72 | -57 | -71 | 431 |
| mean_reversion | Scalping | $238 | -1.17 | -52 | -55 | **$173** | -1.34 | -65 | -66 | 127 |
| mean_reversion | Intraday | $196 | -0.80 | -61 | -59 | **$159** | -0.81 | -68 | -63 | 85 |
| mean_reversion | Aggressive | $222 | -0.66 | -56 | -60 | **$138** | -0.61 | -72 | -75 | 89 |
| mean_reversion | Intraday_Trailing | $237 | -1.41 | -53 | -51 | **$238** | -1.32 | -52 | -50 | 118 |
| bb_rsi_reversion | Scalping | $565 | +0.33 | +13 | -26 | **$545** | +0.27 | +9 | -24 | 108 |
| bb_rsi_reversion | Intraday | $243 | -0.62 | -51 | -50 | **$236** | -0.59 | -53 | -46 | 78 |
| bb_rsi_reversion | Aggressive | $402 | -0.03 | -20 | -34 | **$487** | +0.22 | -3 | -29 | 84 |
| bb_rsi_reversion | Intraday_Trailing | $433 | -0.16 | -13 | -24 | **$438** | -0.14 | -12 | -24 | 106 |
| vwap_cross | Scalping | $434 | -0.13 | -13 | -41 | **$476** | +0.04 | -5 | -40 | 154 |
| vwap_cross | Intraday | $190 | -1.08 | -62 | -67 | **$218** | -0.73 | -56 | -68 | 89 |
| vwap_cross | Aggressive | $201 | -0.99 | -60 | -62 | **$198** | -0.94 | -60 | -61 | 107 |
| vwap_cross | Intraday_Trailing | $334 | -0.60 | -33 | -50 | **$383** | -0.31 | -23 | -48 | 160 |
| breakout | Scalping | $322 | -0.77 | -36 | -38 | **$521** | +0.21 | +4 | -32 | 256 |
| breakout | Intraday | $259 | -0.69 | -48 | -57 | **$315** | -0.19 | -37 | -64 | 158 |
| breakout | Aggressive | $274 | -0.63 | -45 | -59 | **$664** | +0.49 | +33 | -53 | 169 |
| breakout | Intraday_Trailing | $418 | -0.27 | -16 | -33 | **$418** | -0.08 | -16 | -37 | 254 |
| price_action | Scalping | $440 | -0.04 | -12 | -39 | **$511** | +0.21 | +2 | -36 | 291 |
| price_action | Intraday | $281 | -0.36 | -44 | -54 | **$943** | +0.78 | +89 | -44 | 118 |
| price_action | Aggressive | $259 | -0.46 | -48 | -56 | **$288** | -0.23 | -42 | -59 | 124 |
| price_action | Intraday_Trailing | $373 | -0.39 | -25 | -38 | **$397** | -0.09 | -21 | -58 | 294 |
| smc | Scalping | $552 | +0.29 | +10 | -34 | **$315** | -0.28 | -37 | -46 | 385 |
| smc | Intraday | $248 | -0.42 | -50 | -63 | **$755** | +0.59 | +51 | -65 | 183 |
| smc | Aggressive | $377 | -0.03 | -25 | -58 | **$552** | +0.34 | +10 | -53 | 182 |
| smc | Intraday_Trailing | $279 | -0.69 | -44 | -55 | **$146** | -1.15 | -71 | -71 | 384 |

### SOLUSD · 5m

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $0 | -37.28 | -100 | -100 | **$0** | -38.49 | -100 | -100 | 23050 |
| ma_crossover | Intraday | $0 | -11.20 | -100 | -100 | **$0** | -11.42 | -100 | -100 | 8484 |
| ma_crossover | Aggressive | $0 | -11.54 | -100 | -100 | **$0** | -11.69 | -100 | -100 | 9169 |
| ma_crossover | Intraday_Trailing | $0 | -32.07 | -100 | -100 | **$0** | -33.12 | -100 | -100 | 20212 |
| mean_reversion | Scalping | $0 | -17.04 | -100 | -100 | **$0** | -17.04 | -100 | -100 | 6111 |
| mean_reversion | Intraday | $0 | -7.92 | -100 | -100 | **$0** | -7.90 | -100 | -100 | 4751 |
| mean_reversion | Aggressive | $0 | -8.12 | -100 | -100 | **$0** | -7.88 | -100 | -100 | 5037 |
| mean_reversion | Intraday_Trailing | $0 | -16.32 | -100 | -100 | **$0** | -16.39 | -100 | -100 | 5883 |
| bb_rsi_reversion | Scalping | $0 | -14.79 | -100 | -100 | **$0** | -14.78 | -100 | -100 | 5034 |
| bb_rsi_reversion | Intraday | $0 | -8.08 | -100 | -100 | **$0** | -8.10 | -100 | -100 | 4174 |
| bb_rsi_reversion | Aggressive | $0 | -8.05 | -100 | -100 | **$0** | -7.88 | -100 | -100 | 4355 |
| bb_rsi_reversion | Intraday_Trailing | $0 | -12.63 | -100 | -100 | **$0** | -12.66 | -100 | -100 | 4810 |
| vwap_cross | Scalping | $0 | -21.39 | -100 | -100 | **$0** | -21.38 | -100 | -100 | 8001 |
| vwap_cross | Intraday | $0 | -8.51 | -100 | -100 | **$0** | -8.50 | -100 | -100 | 5059 |
| vwap_cross | Aggressive | $0 | -8.93 | -100 | -100 | **$0** | -8.88 | -100 | -100 | 5586 |
| vwap_cross | Intraday_Trailing | $0 | -19.30 | -100 | -100 | **$0** | -19.36 | -100 | -100 | 7592 |
| breakout | Scalping | $0 | -24.36 | -100 | -100 | **$0** | -32.01 | -100 | -100 | 14335 |
| breakout | Intraday | $0 | -10.29 | -100 | -100 | **$0** | -12.19 | -100 | -100 | 8593 |
| breakout | Aggressive | $0 | -10.44 | -100 | -100 | **$0** | -12.31 | -100 | -100 | 9004 |
| breakout | Intraday_Trailing | $0 | -20.30 | -100 | -100 | **$0** | -27.48 | -100 | -100 | 13201 |
| price_action | Scalping | $0 | -19.82 | -100 | -100 | **$0** | -24.55 | -100 | -100 | 11687 |
| price_action | Intraday | $0 | -8.60 | -100 | -100 | **$0** | -9.26 | -100 | -100 | 6557 |
| price_action | Aggressive | $0 | -9.75 | -100 | -100 | **$0** | -11.47 | -100 | -100 | 6946 |
| price_action | Intraday_Trailing | $0 | -18.81 | -100 | -100 | **$0** | -24.47 | -100 | -100 | 11390 |
| smc | Scalping | $0 | -29.81 | -100 | -100 | **$0** | -37.93 | -100 | -100 | 23088 |
| smc | Intraday | $0 | -10.42 | -100 | -100 | **$0** | -11.88 | -100 | -100 | 10218 |
| smc | Aggressive | $0 | -11.54 | -100 | -100 | **$0** | -13.84 | -100 | -100 | 11170 |
| smc | Intraday_Trailing | $0 | -25.74 | -100 | -100 | **$0** | -33.81 | -100 | -100 | 21406 |

### SOLUSD · 15m

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $0 | -10.45 | -100 | -100 | **$0** | -10.78 | -100 | -100 | 6673 |
| ma_crossover | Intraday | $7 | -3.17 | -99 | -99 | **$8** | -2.87 | -98 | -98 | 2469 |
| ma_crossover | Aggressive | $5 | -3.38 | -99 | -99 | **$7** | -3.08 | -99 | -99 | 2612 |
| ma_crossover | Intraday_Trailing | $0 | -10.64 | -100 | -100 | **$0** | -10.80 | -100 | -100 | 6339 |
| mean_reversion | Scalping | $11 | -5.74 | -98 | -98 | **$11** | -5.68 | -98 | -98 | 1907 |
| mean_reversion | Intraday | $25 | -2.46 | -95 | -96 | **$25** | -2.42 | -95 | -96 | 1446 |
| mean_reversion | Aggressive | $29 | -2.29 | -94 | -95 | **$29** | -2.18 | -94 | -95 | 1539 |
| mean_reversion | Intraday_Trailing | $10 | -5.98 | -98 | -98 | **$9** | -6.06 | -98 | -98 | 1845 |
| bb_rsi_reversion | Scalping | $20 | -5.31 | -96 | -96 | **$19** | -5.37 | -96 | -97 | 1623 |
| bb_rsi_reversion | Intraday | $18 | -2.95 | -96 | -97 | **$18** | -2.91 | -96 | -97 | 1319 |
| bb_rsi_reversion | Aggressive | $17 | -3.06 | -97 | -97 | **$18** | -2.90 | -96 | -97 | 1376 |
| bb_rsi_reversion | Intraday_Trailing | $21 | -5.23 | -96 | -97 | **$20** | -5.35 | -96 | -97 | 1552 |
| vwap_cross | Scalping | $17 | -5.08 | -97 | -97 | **$17** | -5.13 | -97 | -97 | 2389 |
| vwap_cross | Intraday | $74 | -1.71 | -85 | -85 | **$71** | -1.75 | -86 | -86 | 1474 |
| vwap_cross | Aggressive | $59 | -1.87 | -88 | -88 | **$55** | -1.91 | -89 | -89 | 1634 |
| vwap_cross | Intraday_Trailing | $19 | -4.76 | -96 | -96 | **$18** | -4.78 | -96 | -96 | 2346 |
| breakout | Scalping | $9 | -6.60 | -98 | -98 | **$0** | -8.74 | -100 | -100 | 4277 |
| breakout | Intraday | $21 | -3.23 | -96 | -96 | **$6** | -3.19 | -99 | -99 | 2453 |
| breakout | Aggressive | $14 | -3.78 | -97 | -97 | **$3** | -3.69 | -99 | -99 | 2606 |
| breakout | Intraday_Trailing | $4 | -8.38 | -99 | -99 | **$0** | -9.50 | -100 | -100 | 4142 |
| price_action | Scalping | $3 | -6.83 | -99 | -99 | **$0** | -8.47 | -100 | -100 | 4066 |
| price_action | Intraday | $6 | -3.80 | -99 | -99 | **$4** | -3.47 | -99 | -99 | 2120 |
| price_action | Aggressive | $7 | -3.57 | -99 | -99 | **$3** | -3.61 | -99 | -100 | 2295 |
| price_action | Intraday_Trailing | $3 | -7.19 | -99 | -100 | **$0** | -8.83 | -100 | -100 | 4080 |
| smc | Scalping | $1 | -7.12 | -100 | -100 | **$0** | -8.59 | -100 | -100 | 6337 |
| smc | Intraday | $12 | -2.71 | -98 | -98 | **$7** | -2.54 | -99 | -99 | 2766 |
| smc | Aggressive | $7 | -3.20 | -99 | -99 | **$4** | -2.96 | -99 | -99 | 3000 |
| smc | Intraday_Trailing | $1 | -7.70 | -100 | -100 | **$0** | -9.72 | -100 | -100 | 6173 |

### SOLUSD · 30m

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $4 | -4.64 | -99 | -99 | **$2** | -4.85 | -100 | -100 | 3181 |
| ma_crossover | Intraday | $41 | -1.73 | -92 | -92 | **$28** | -1.98 | -94 | -94 | 1200 |
| ma_crossover | Aggressive | $68 | -1.35 | -86 | -86 | **$66** | -1.24 | -87 | -87 | 1212 |
| ma_crossover | Intraday_Trailing | $3 | -4.81 | -99 | -99 | **$3** | -4.76 | -99 | -99 | 3073 |
| mean_reversion | Scalping | $36 | -4.04 | -93 | -93 | **$33** | -4.16 | -93 | -94 | 988 |
| mean_reversion | Intraday | $75 | -1.56 | -85 | -89 | **$67** | -1.66 | -87 | -89 | 757 |
| mean_reversion | Aggressive | $91 | -1.30 | -82 | -87 | **$86** | -1.35 | -83 | -87 | 805 |
| mean_reversion | Intraday_Trailing | $56 | -3.12 | -89 | -90 | **$52** | -3.19 | -90 | -90 | 964 |
| bb_rsi_reversion | Scalping | $110 | -2.26 | -78 | -80 | **$105** | -2.30 | -79 | -81 | 841 |
| bb_rsi_reversion | Intraday | $125 | -1.03 | -75 | -80 | **$119** | -1.04 | -76 | -81 | 665 |
| bb_rsi_reversion | Aggressive | $133 | -1.02 | -73 | -81 | **$137** | -0.97 | -73 | -80 | 702 |
| bb_rsi_reversion | Intraday_Trailing | $106 | -2.26 | -79 | -81 | **$103** | -2.28 | -79 | -80 | 812 |
| vwap_cross | Scalping | $169 | -1.51 | -66 | -67 | **$168** | -1.52 | -66 | -67 | 1121 |
| vwap_cross | Intraday | $163 | -0.93 | -67 | -69 | **$153** | -0.98 | -69 | -71 | 705 |
| vwap_cross | Aggressive | $144 | -1.03 | -71 | -72 | **$139** | -1.05 | -72 | -72 | 769 |
| vwap_cross | Intraday_Trailing | $220 | -1.10 | -56 | -56 | **$216** | -1.12 | -57 | -57 | 1094 |
| breakout | Scalping | $43 | -4.04 | -91 | -92 | **$7** | -4.82 | -99 | -99 | 2071 |
| breakout | Intraday | $78 | -1.80 | -84 | -85 | **$58** | -1.41 | -88 | -91 | 1200 |
| breakout | Aggressive | $87 | -1.77 | -83 | -82 | **$30** | -1.97 | -94 | -95 | 1290 |
| breakout | Intraday_Trailing | $73 | -3.25 | -85 | -85 | **$15** | -3.91 | -97 | -97 | 1983 |
| price_action | Scalping | $44 | -3.08 | -91 | -92 | **$13** | -3.78 | -97 | -98 | 2061 |
| price_action | Intraday | $121 | -0.99 | -76 | -84 | **$65** | -1.26 | -87 | -90 | 1077 |
| price_action | Aggressive | $153 | -0.79 | -69 | -80 | **$38** | -1.76 | -92 | -94 | 1175 |
| price_action | Intraday_Trailing | $40 | -3.17 | -92 | -92 | **$10** | -4.11 | -98 | -98 | 2102 |
| smc | Scalping | $9 | -4.76 | -98 | -98 | **$1** | -5.23 | -100 | -100 | 3084 |
| smc | Intraday | $24 | -2.27 | -95 | -95 | **$15** | -2.11 | -97 | -97 | 1375 |
| smc | Aggressive | $13 | -2.95 | -97 | -98 | **$11** | -2.42 | -98 | -98 | 1452 |
| smc | Intraday_Trailing | $18 | -4.09 | -96 | -97 | **$1** | -5.47 | -100 | -100 | 3019 |

### SOLUSD · 1h

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $48 | -2.13 | -90 | -90 | **$45** | -2.04 | -91 | -91 | 1560 |
| ma_crossover | Intraday | $165 | -0.62 | -67 | -75 | **$125** | -0.80 | -75 | -77 | 586 |
| ma_crossover | Aggressive | $220 | -0.39 | -56 | -77 | **$242** | -0.19 | -52 | -78 | 593 |
| ma_crossover | Intraday_Trailing | $40 | -2.32 | -92 | -92 | **$38** | -2.24 | -92 | -93 | 1549 |
| mean_reversion | Scalping | $140 | -1.68 | -72 | -74 | **$129** | -1.75 | -74 | -76 | 502 |
| mean_reversion | Intraday | $240 | -0.43 | -52 | -62 | **$207** | -0.54 | -59 | -67 | 377 |
| mean_reversion | Aggressive | $260 | -0.34 | -48 | -62 | **$226** | -0.44 | -55 | -66 | 391 |
| mean_reversion | Intraday_Trailing | $200 | -1.02 | -60 | -61 | **$188** | -1.06 | -62 | -63 | 493 |
| bb_rsi_reversion | Scalping | $169 | -1.60 | -66 | -74 | **$170** | -1.57 | -66 | -73 | 425 |
| bb_rsi_reversion | Intraday | $214 | -0.59 | -57 | -68 | **$211** | -0.54 | -58 | -67 | 337 |
| bb_rsi_reversion | Aggressive | $199 | -0.66 | -60 | -72 | **$208** | -0.52 | -58 | -72 | 366 |
| bb_rsi_reversion | Intraday_Trailing | $257 | -0.92 | -49 | -51 | **$252** | -0.93 | -50 | -52 | 408 |
| vwap_cross | Scalping | $188 | -1.38 | -62 | -69 | **$182** | -1.45 | -64 | -69 | 559 |
| vwap_cross | Intraday | $240 | -0.51 | -52 | -62 | **$194** | -0.69 | -61 | -67 | 355 |
| vwap_cross | Aggressive | $200 | -0.73 | -60 | -64 | **$181** | -0.75 | -64 | -67 | 396 |
| vwap_cross | Intraday_Trailing | $179 | -1.41 | -64 | -70 | **$176** | -1.43 | -65 | -69 | 558 |
| breakout | Scalping | $107 | -2.49 | -79 | -78 | **$48** | -2.59 | -90 | -91 | 995 |
| breakout | Intraday | $88 | -1.64 | -82 | -83 | **$70** | -1.23 | -86 | -88 | 620 |
| breakout | Aggressive | $173 | -1.01 | -65 | -67 | **$67** | -1.38 | -87 | -90 | 635 |
| breakout | Intraday_Trailing | $174 | -1.69 | -65 | -68 | **$41** | -2.89 | -92 | -92 | 996 |
| price_action | Scalping | $145 | -1.49 | -71 | -75 | **$43** | -2.39 | -91 | -92 | 1094 |
| price_action | Intraday | $238 | -0.42 | -52 | -69 | **$161** | -0.56 | -68 | -86 | 564 |
| price_action | Aggressive | $138 | -0.91 | -72 | -81 | **$66** | -1.24 | -87 | -90 | 593 |
| price_action | Intraday_Trailing | $171 | -1.20 | -66 | -70 | **$126** | -1.18 | -75 | -80 | 1109 |
| smc | Scalping | $45 | -2.90 | -91 | -91 | **$16** | -2.96 | -97 | -97 | 1462 |
| smc | Intraday | $103 | -1.05 | -79 | -79 | **$170** | -0.45 | -66 | -78 | 673 |
| smc | Aggressive | $97 | -1.17 | -81 | -80 | **$53** | -1.35 | -89 | -90 | 727 |
| smc | Intraday_Trailing | $49 | -2.82 | -90 | -90 | **$17** | -2.98 | -97 | -97 | 1428 |

### SOLUSD · 4h

| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |
|---|---|---|---|---|---|---|---|---|---|---|
| ma_crossover | Scalping | $110 | -1.34 | -78 | -81 | **$120** | -1.14 | -76 | -81 | 404 |
| ma_crossover | Intraday | $130 | -0.79 | -74 | -80 | **$118** | -0.59 | -76 | -81 | 154 |
| ma_crossover | Aggressive | $195 | -0.51 | -61 | -71 | **$198** | -0.22 | -60 | -77 | 165 |
| ma_crossover | Intraday_Trailing | $162 | -0.94 | -68 | -72 | **$119** | -1.19 | -76 | -80 | 392 |
| mean_reversion | Scalping | $395 | -0.17 | -21 | -44 | **$408** | -0.07 | -18 | -42 | 132 |
| mean_reversion | Intraday | $243 | -0.42 | -51 | -55 | **$115** | -0.66 | -77 | -70 | 90 |
| mean_reversion | Aggressive | $347 | -0.08 | -31 | -55 | **$205** | -0.26 | -59 | -58 | 99 |
| mean_reversion | Intraday_Trailing | $383 | -0.23 | -23 | -41 | **$396** | -0.18 | -21 | -39 | 131 |
| bb_rsi_reversion | Scalping | $433 | -0.04 | -13 | -38 | **$484** | +0.14 | -3 | -35 | 116 |
| bb_rsi_reversion | Intraday | $177 | -0.77 | -65 | -68 | **$106** | -0.87 | -79 | -75 | 83 |
| bb_rsi_reversion | Aggressive | $173 | -0.87 | -65 | -66 | **$153** | -0.68 | -69 | -66 | 87 |
| bb_rsi_reversion | Intraday_Trailing | $334 | -0.46 | -33 | -40 | **$310** | -0.54 | -38 | -39 | 114 |
| vwap_cross | Scalping | $329 | -0.52 | -34 | -49 | **$388** | -0.19 | -22 | -48 | 135 |
| vwap_cross | Intraday | $262 | -0.41 | -48 | -62 | **$251** | -0.20 | -50 | -65 | 93 |
| vwap_cross | Aggressive | $218 | -0.63 | -56 | -67 | **$201** | -0.42 | -60 | -67 | 100 |
| vwap_cross | Intraday_Trailing | $448 | -0.01 | -10 | -39 | **$529** | +0.24 | +6 | -38 | 144 |
| breakout | Scalping | $306 | -0.76 | -39 | -51 | **$201** | -0.81 | -60 | -66 | 261 |
| breakout | Intraday | $382 | -0.09 | -24 | -54 | **$518** | +0.36 | +4 | -68 | 155 |
| breakout | Aggressive | $193 | -0.99 | -61 | -70 | **$217** | -0.15 | -57 | -83 | 169 |
| breakout | Intraday_Trailing | $368 | -0.41 | -26 | -45 | **$266** | -0.51 | -47 | -64 | 257 |
| price_action | Scalping | $282 | -0.62 | -44 | -51 | **$201** | -0.69 | -60 | -79 | 272 |
| price_action | Intraday | $172 | -0.78 | -66 | -72 | **$536** | +0.39 | +7 | -53 | 119 |
| price_action | Aggressive | $221 | -0.58 | -56 | -64 | **$472** | +0.30 | -6 | -67 | 141 |
| price_action | Intraday_Trailing | $356 | -0.37 | -29 | -48 | **$350** | -0.18 | -30 | -63 | 273 |
| smc | Scalping | $448 | +0.04 | -10 | -59 | **$233** | -0.45 | -53 | -66 | 358 |
| smc | Intraday | $293 | -0.18 | -41 | -57 | **$99** | -0.42 | -80 | -87 | 177 |
| smc | Aggressive | $567 | +0.38 | +13 | -51 | **$667** | +0.57 | +33 | -50 | 190 |
| smc | Intraday_Trailing | $380 | -0.22 | -24 | -49 | **$203** | -0.59 | -59 | -68 | 368 |

