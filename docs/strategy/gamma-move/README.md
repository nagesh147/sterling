# Gamma Move

**Strategy ID** `gamma_move` · **Contract** A310.2 · **Status** BUILT, calibrated, paper-only
**Sits beside** ATM Premium Imbalance, as a peer engine in every registry.

Buys the option that writers are covering. An F&O single stock trades up into a
resistance level (or down into a support level); the strike at that level carries
the chain's heaviest open interest, because that is where the sellers are. When
spot breaks the level, those sellers cover — open interest falls, volume spikes,
and the premium rises, all on the same 15-minute bar. Because the strike is going
in-the-money at the same time, the premium accelerates faster than delta alone
explains. That acceleration is gamma, and the trade is to be long it for one to
two days.

## Documents

| Doc | What it is |
|---|---|
| [VALIDATION_REPORT.md](VALIDATION_REPORT.md) | **Start here.** What the calibration measured over 598 contracts and 193,135 real bars, what it found, and the eight-item live gate. It is the authority wherever it and A310 disagree. |
| [A310_END_TO_END.md](A310_END_TO_END.md) | The build plan: provenance, the contract, the data-path feasibility proof, the artifact manifest, every backend and frontend contract, and the funnel argument. Partly superseded — see its header. |
| [A311_RUNBOOK.md](A311_RUNBOOK.md) | Operating it: switch on, scan, arm, monitor, recover, kill. |

## Provenance in one line

Transcribed from a public podcast walkthrough
([youtube.com/watch?v=W88GygpXZWI](https://youtube.com/watch?v=W88GygpXZWI),
TradeAlphaGuru, 2026-06-27, Hindi, strategy segment ~27:00–43:00), captions
cross-checked against the Hindi original because the machine translation is
unreliable on numbers and names.

## Read this before touching the config

Three of the strategy's rules were never given numbers in the source. All three
are now **measured**, against 598 NSE stock-option contracts and 193,135
fifteen-minute bars carrying real open interest. The measurement found something
the source does not claim:

> **The entry trigger alone has no measurable edge. The level filter does.**
> 24.7% [20.9, 28.9] of triggered bars reached +30% within two sessions, against
> a 21.7% [21.5, 21.9] baseline — overlapping. Restricted to spot within 1% of a
> confirmed level: 46.2% [31.6, 61.4].

So `level_proximity_pct` is the load-bearing setting in this engine, and
widening it does not add signals of the same quality — it adds signals of
baseline quality. One more trap worth knowing before you touch anything: the
SuperTrend gate at the conventional multiplier of 3.0 measured **inverted**.
It ships at 2.0.

The engine ships **on**, and there is deliberately **no per-strategy paper/live
switch**. What stands between it and real money is the same set that guards every
Kite strategy: `account.is_paper` from the Trading Mode panel (which `KiteClient`
already acts on), the engine's `auto_execute`, the kill switch, and this engine's
own risk caps. `enabled` is a power switch, not one of those guards — an engine
shipped off just does nothing until somebody finds the toggle.

The combination to think about is **LIVE + AUTO**: an enabled engine trades then,
which is the correct reading of "enabled". The engineering guards — a stop on
every entry, a broker-side GTT under the default `stop_mode` — are unconditional
rather than attached to a mode.
