> **⚠️ DEPRECATED — superseded 2026-06-03.** Canonical derivatives/options metrics now live in **[Report 1 — Baseline §6](./STERLING_TRADING_REPORT_BASELINE.md)**. Kept for provenance/audit only.

# Derivatives Edge Study

Generated: 2026-06-02 04:11:28 UTC
Surface snapshot: no live snapshot

## Summary

- **0** of **0** configs survive the robustness gate (0.0%)
- Gate: net return > 0, OOS Sharpe > 0, Monte Carlo p(loss) ≤ 35%
- Options results are **modeled** (BSM, calibrated to live surface) unless marked 'real'

## Futures vs Options

**No configs survived the robustness gate** — the study did not find a validated edge in either instrument class at the default thresholds.


## Top Survivors (by OOS Sharpe)

*(none survived the robustness gate)*


## Gate Over-Filter Audit

*(no gate audit data — study may not have completed the audit stage)*


## Caveats

- **Options P&L is modeled** (constant-IV BSM, calibrated to a single live surface snapshot). A genuine historical IV series for vol-*timing* does not yet exist — the forward IV recorder must accrue data before vol-percentile-based strategies can be honestly backtested.
- **Futures P&L is real** (bar-by-bar from actual 1m OHLCV data).
- Sub-15m timeframes confirmed fee-death in prior runs and are excluded.
- The routing gate was replayed against a live surface snapshot — gate behaviour may differ under different vol regimes.
- CPCV uses N=6 groups, K=2 test groups, embargo=2×hold_bars.

## Output Files

- `/home/nageshmadaram/Sterling/derivatives_study_results.csv` — full Stage A grid
- `/home/nageshmadaram/Sterling/derivatives_study_survivors.csv` — robustness-gated survivors
- `/home/nageshmadaram/Sterling/derivatives_gate_overfilter.csv` — IVR routing sweep