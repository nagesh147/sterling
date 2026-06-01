# Gate Over-Filter Analysis

Gate-passing edge combos analyzed: **6** (net>0, sharpe>=0.8, trades>=50)

Live near-ATM spread used: 1.3% (well under the 12% routing / 4% profile veto)


## Routing verdict by IVR (edge profile ivr_pct_naked_max=50)

| combo | IVR10 | IVR20 | IVR30 | IVR40 | IVR50 | IVR60 | IVR70 | IVR80 | IVR90 |
|---|---|---|---|---|---|---|---|---|---|
| BTCUSD 4h ma_crossover | fut | fut | fut | fut | OPT | fut | fut | fut | fut |
| BTCUSD 4h ma_crossover | fut | fut | fut | fut | OPT | fut | fut | fut | fut |
| BTCUSD 4h breakout | fut | fut | fut | fut | OPT | fut | fut | fut | fut |
| BTCUSD 4h smc | fut | fut | fut | fut | OPT | fut | fut | fut | fut |
| ETHUSD 4h smc | fut | fut | fut | fut | OPT | fut | fut | fut | fut |
| SOLUSD 4h smc | fut | fut | fut | fut | OPT | fut | fut | fut | fut |

## Finding

- **6/6** proven signals have their OPTIONS expression hard-vetoed once IVR exceeds the profile cap (50) — forced to futures-only regardless of signal quality.

- Median IVR at which options are denied: **60**.

- The **spread veto never binds** at the live ~1.3% spread; the **IVR cap is the binding over-filter**.

- The futures leg is NOT refused (presized edge signals pass the SL/TP solver), so a good signal is **instrument-restricted, not fully rejected** — but it loses the options expression exactly when IV is rich.

- **This is the gap the native engine fills:** at high IVR, instead of vetoing options, SELL defined-risk vol (credit spread / iron condor) to monetize the rich IV.

