# Gamma Move

**Strategy ID** `gamma_move` · **Contract** A310.1 · **Status** SPECIFICATION — no code yet
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
| [A310_END_TO_END.md](A310_END_TO_END.md) | **Start here.** Provenance, the full contract, the data-path feasibility proof, an artifact-by-artifact build manifest (33 new files, 6 edits), every backend and frontend contract, the test plan, the build order and the live gate. |
| A311_RUNBOOK.md | *Not yet written* — arm, monitor, recover, kill. Due in phase P6. |
| VALIDATION_REPORT.md | *Not yet written* — and must not be, until a real replay run exists. Phase P9. |

## Provenance in one line

Transcribed from a public podcast walkthrough
([youtube.com/watch?v=W88GygpXZWI](https://youtube.com/watch?v=W88GygpXZWI),
TradeAlphaGuru, 2026-06-27, Hindi, strategy segment ~27:00–43:00), captions
cross-checked against the Hindi original because the machine translation is
unreliable on numbers and names.

## Read this before touching the config

Three of the strategy's rules were **never given numbers** in the source: how
near "near a level" is, the thresholds for the open-interest drop / volume spike
/ price gain, and the SuperTrend parameters. The shipped defaults are calibration
starting points, not observed values. They are listed in `descriptor()` under
`uncalibrated`, and the board badges every signal `UNCALIBRATED` until a
validation run replaces them.

Four winning examples were shown in the source and no losing one. Four winners
establish nothing. `enabled` defaults to `False`, `execution_mode` to `paper`,
and `live_ready` is `False` until the eight-item gate in A310 §10 is cleared.
