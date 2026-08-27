# F-102 calibration — the result, 2026-08-27

F-102 is the directional probability model. It is the quantity the entry gate has
been refusing on: §35 requires `ConservativeEV > 0`, ConservativeEV is
`LowerConfidenceBound(EV)`, and a bound on expected value needs a distribution
over outcomes.

It has now been fitted, twice, on real data. **Both runs are negative.**

## Run 1 — price, volume and open-interest features

| | |
|---|---|
| Data | 50,244 NIFTY-I one-minute bars, 2026-02-02 to 2026-08-18 |
| Rows | 50,168 |
| Labels | DOWN 11,204 · FLAT 28,101 · UP 10,863 |
| Majority baseline | 0.5601 |
| **Mean OOS accuracy** | **0.5484** |
| Directional calls | **0** |
| Folds | 4, purge and embargo both 15 bars = the label horizon |

Accuracy is *below* the base rate. A diagnostic on one fold explains why: the
model predicts FLAT for all 2,000 holdout rows, P(UP) never exceeds 0.283, and
P(FLAT) sits at 0.608 against a 0.560 prior. Loss converged, 1.0986 to 0.9379.
It learned the class prior and nothing conditional.

## Run 2 — the specification's own order-flow features

Run 1 only says those features have no edge. The specification's directional
signal is order flow — §8 trade state, §9 aggressor, §10 delta, §11 liquidity —
which the bar table cannot express. So run 2 uses
`structure.build_structure_series`, the engine's own feature builder, over real
bars *and* real ticks carrying bid, ask, bidqty and askqty.

| | |
|---|---|
| Window | 2026-08-06 to 2026-08-18, ~9 sessions |
| Data | 3,374 bars, 53,884 ticks |
| Rows | 3,328 |
| Majority baseline | 0.7912 |
| **Mean OOS accuracy** | **0.7068** |
| Directional calls | **0** (max confidence 0.8535, all FLAT) |
| Folds | 1 |

Again below the base rate, again no directional call. The model here *is* capable
of confidence — it reaches 0.85 — and spends all of it on FLAT.

## What this means

The entry gate stays shut, and the reason has changed from *missing* to
*measured*. `ConservativeEV` cannot be supplied because the model that would
bound it has no directional signal to bound.

That is the correct outcome of the gate, not a failure of it. F-110 declines,
and it declines for a reason there is now evidence for.

## What it does not mean

* **Not** that the Master Specification strategy has no edge. Two feature sets
  were tested at one horizon on one instrument.
* Run 2's window is nine sessions. A negative there is weaker evidence than run
  1's 6.5 months, and a positive would have needed confirming before anyone
  traded it.
* The horizon (15 bars) and the move threshold (8 bps) were chosen, not fitted.
  A different horizon is a different question and has not been asked.
* Kite ticks carry no aggressor flag, so even run 2's order-flow features are
  quote-derived rather than built from classified prints. The specification
  assumes the latter.

## Reproducing

```
python -m study.adaptive_edge.calibrate_f102
python -m study.adaptive_edge.calibrate_f102_orderflow
```

Both write JSON to `backend/study/adaptive_edge/out/`. Both use walk-forward
folds with purge and embargo set to the label horizon, and report only holdout
segments that no fitting or threshold search touched.
