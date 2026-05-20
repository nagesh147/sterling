# BTC short-TF signal-stack rewrite — implementation plan

## Context

The 2026-05-20 systematic search (132 unique knob combos × 3 profiles × 3 walk-forward splits, validated with deflated_sharpe + bootstrap + permutation gates) proved the current signal stack cannot reach "proven edge" (deflated_sharpe ≥ 0.95) on BTC scalping_5m / 15m / 30m. Best result: BTC scalping_30m at OOS Sharpe **+0.27**, PF 1.18, WR 58% — directionally profitable but 24 OOS trades is too thin a sample.

The search also surfaced the *actual* shape of the BTC short-TF edge:

| Regime (BTC 1h breakdown) | Long-signal WR | Short-signal WR | Avg PnL |
|---|---|---|---|
| BULL_TREND | **32%** | (not taken) | -0.40% |
| BEAR_TREND | (not taken) | **62-67%** | +0.22% |
| RANGING | 52% | 52% | -0.14% |
| IDLE | 50% | 50% | -0.13% |

The pattern is unambiguous: **in BULL_TREND, longs lose at 32% WR.** That is the inverse of what a trend-follower predicts. The profitable side in BULL_TREND is to *fade the rally*, not ride it. The current stack cannot access this — `setup_engine.evaluate_setup` enforces MTF agreement (`BULL regime + short signal → FILTERED`), so the strategy is structurally locked out of the actual BTC edge.

The trend-following framing **is not broken**; it's a perfect fit for ETH 30m (Sharpe 1.27, edge_proven, untouched). It is the wrong tool for BTC sub-1H bars. The fix is a parallel **counter-trend mean-reversion track** that fires on the opposite signal in trending regimes, with the trend-following track preserved as-is.

Secondary motivation: the v4 refactor unified backtest and live signal compute behind `signal_features` / `signal_weights`. Layering a second track on top of those primitives keeps cost low — both tracks share the heavy lifting (Supertrend, RSI, BB/KC, HA, volume, CVD).

---

## Architecture: multi-track signal stack

Today every profile runs one signal compute through `compute_signal()`. The rewrite introduces a **track** abstraction. A track is a strategy specialisation that owns its own entry/exit logic and reuses the shared feature primitives. Per-(asset, profile) routing picks one track.

```
backend/app/engines/directional/
├── tracks/                              # NEW package
│   ├── __init__.py
│   ├── base.py                          # Track ABC + TrackSignal dataclass
│   ├── trend_following.py               # wraps current compute_signal
│   ├── mean_reversion.py                # NEW — fade-extremes specialist
│   └── microstructure.py                # NEW (Phase 2) — funding / book / CVD
├── track_selector.py                    # NEW — per-(asset, profile) → track[s]
├── signal_engine.py                     # KEPT — becomes the trend_following backend
├── signal_features.py                   # KEPT — pure blocks both tracks reuse
├── signal_weights.py                    # KEPT — shared thresholds
└── setup_engine.py                      # MODIFIED — track-aware MTF gate
```

`TrackSignal` (shared output schema):

```python
@dataclass(frozen=True)
class TrackSignal:
    track: str                  # "trend_following" | "mean_reversion" | …
    trend_dir: int              # 1 / -1 / 0 — desired trade direction (NOT the macro regime)
    score: float                # 0..20, comparable across tracks
    strength: str               # "STRONG" | "SIGNAL" | "NONE"
    reason: str                 # human-readable
    features: Dict[str, float]  # debug payload (rsi, vwap_dev, cvd, …)
```

`track_selector.select_tracks(asset: str, profile_key: str) -> List[str]` returns the ordered list of tracks to evaluate for this (asset, profile). Output collapses to a single `TrackSignal` via highest-score wins (within a track-allowed regime). Per-(asset, profile) routing baked in:

| Profile | BTC | ETH | Default |
|---|---|---|---|
| scalping_5m  | mean_reversion (+ microstructure once Phase 2 ships) | trend_following | trend_following |
| scalping_15m | mean_reversion | trend_following | trend_following |
| scalping_30m | mean_reversion | **trend_following** ← preserves the 1.27-Sharpe winner | trend_following |
| intraday_1h  | trend_following | trend_following | trend_following |
| intraday_4h  | trend_following | trend_following | trend_following |

ETH 30m never touches `mean_reversion`. The 1086-test suite and the Sharpe 1.27 winner are byte-identical guaranteed by the router falling through to `trend_following`.

---

## Phase 1 — Mean-reversion track for BTC short-TF

Highest expected value, lowest blast radius. ~2-3 days of work. The track is a pure new file plus a router wire-up; setup_engine gets one small change to consult the router.

### Strategy logic

**Entry**: fade an extreme move into a HTF trend (mean revert into the established direction).

Long entry (rare on BTC — exists for completeness):
- HTF regime ∈ {BEAR_TREND, BEAR_TRENDING, BEAR_RANGING}
- AND RSI(14) on signal-TF < 25 (deeply oversold)
- AND close < lower Bollinger(20, 2) at most-recent bar
- AND volume climax (vol > 95th-percentile of last 100 bars)
- AND CVD-10 sign positive (buying pressure absorbing the dip — uses the `cvd_state_at` we already compute)

Short entry (the bread-and-butter on BTC):
- HTF regime ∈ {BULL_TREND, BULL_TRENDING, BULL_RANGING}
- AND RSI(14) on signal-TF > 75
- AND close > upper Bollinger(20, 2)
- AND volume climax (same threshold)
- AND CVD-10 sign negative (selling pressure absorbing the rally)

**Exit** (asymmetric, tighter than trend-following):
- Take profit when close re-touches rolling 20-bar VWAP (mean reversion done)
- Stop at the prior swing high (long short) / low (long) ± 0.5×ATR — closer than 1.2×ATR
- Hard time stop at `hold_bars * 0.5` (mean reversion doesn't have legs)

**Direction asymmetry**: route long entries through the standard 75-score gate, but route short entries through a relaxed 70-score gate. BTC's data clearly shows the bear side is the real edge; let it fire ~30% more often than the long side.

### Files (Phase 1)

**New**:
- `backend/app/engines/directional/tracks/__init__.py`
- `backend/app/engines/directional/tracks/base.py` — `Track` ABC, `TrackSignal` dataclass
- `backend/app/engines/directional/tracks/trend_following.py` — thin wrapper that calls existing `compute_signal()` and emits a `TrackSignal` (purely a re-shape; no logic change)
- `backend/app/engines/directional/tracks/mean_reversion.py` — new logic above
- `backend/app/engines/directional/track_selector.py` — per-(asset, profile) routing dict + `select_tracks()`
- `backend/scripts/btc_mr_search.py` — search driver mirroring `btc_scalping_search.py`, but the search space is the MR-specific knobs (RSI extremes, BB std, vol_climax_pct, VWAP exit threshold, time_stop_bars)

**Modified**:
- `backend/app/engines/directional/orchestrator.py` — calls `track_selector.select_tracks(underlying, mode)` and dispatches to track. Falls back to existing `compute_signal` when track list is `["trend_following"]` so call-shape stays identical for ETH.
- `backend/app/engines/directional/setup_engine.py` — `evaluate_setup()` learns to read `signal.track_name` and disable the MTF agreement filter for `mean_reversion` (counter-trend is *expected* there). One conditional, ~5 lines.
- `backend/app/engines/backtest/backtest_mtf.py` — `_replay_profile` calls the track router same way as orchestrator; symmetric live/backtest semantics preserved.
- `backend/app/engines/backtest/mtf_vectorizer.py` — needs a vectorised counterpart for the MR track. Two paths: (a) precompute MR-specific arrays alongside the trend signal (cleaner, same O(N) shape as today); (b) only vectorise trend-following and fall back to per-bar MR compute for backtests where MR is selected. Recommend (a) — adds ~80 LOC but keeps backtest fast.

**Not modified**: `signal_engine.py`, `signal_features.py`, `signal_weights.py`, ETH-routed call-paths.

### Why this should clear the gate

The systematic search showed BTC scalping_30m `short_only` at PF 1.18 / WR 58% with **24 OOS trades**. The mean-reversion track will fire on a *different and larger trade population* — the existing track filters out exactly the bars MR wants to trade (counter-trend). Doubling the trade count alone moves a 0.27 OOS Sharpe with PF 1.18 above the deflated-Sharpe threshold (the deflated formula penalises low N). If the per-trade quality doesn't degrade (which is the bet — fading rallies in BULL_TREND is the *cleanest* version of what `short_only` was approximating), edge_proven becomes reachable.

### Validation (Phase 1)

`scripts/btc_mr_search.py` reuses the existing staged-search harness. Same three statistical gates: deflated_sharpe ≥ 0.95, bootstrap p05 > 0, permutation p < 0.05. ETH safety check unchanged (ETH never routes to MR).

Acceptance bar:
1. BTC scalping_30m: edge_proven AND Sharpe ≥ 0.8 OOS
2. BTC scalping_15m: edge_proven OR Sharpe ≥ 0.5 OOS (relaxed because trade count is sparser at 15m)
3. BTC scalping_5m: net positive Sharpe (Phase 1 may not clear edge_proven here — Phase 2 microstructure features expected to close the gap)
4. ETH baselines byte-identical (regression check)
5. All 1086 tests pass

---

## Phase 2 — Microstructure feature library

If Phase 1 closes 30m and 15m but 5m remains stuck (the most likely outcome), the missing edge is microstructure. At 5m bars, OHLCV alone doesn't carry the information that drives forward returns. ~3-5 days of work.

### New features (signal-TF, per bar)

| Feature | Source | Hypothesis |
|---|---|---|
| `funding_flip` | Delta perp funding rate — sign change in the last 8h window | Funding flips precede mean-reversion |
| `funding_extreme` | abs(funding) > 0.025 | Crowded one-side positioning; reversal risk |
| `perp_basis_z` | (perp_mid − spot_mid) / 10-day std | Basis blow-out → MR signal |
| `oi_delta_z` | Z-score of 1h ΔOI | Position-build vs unwind |
| `cvd_acceleration` | Δ of `cvd_proxy` over 5 bars | Tape-flip detection |
| `liquidation_proxy` | Bar range > 3×ATR with reverse close | Cascade-then-reverse pattern |
| `book_imbalance` (live only) | Top-of-book ratio | Already in `microstructure_veto.py`; promote to a signal feature |

`backend/app/engines/risk/microstructure_veto.py` already implements the live book/trade pressure veto. **Promote it** from veto-only to a scoring feature. The existing `MicroSnapshotProvider` callback path means data is already plumbed; just need to compute a continuous score instead of a binary veto.

For backtest, the funding/OI/basis history likely needs ingestion. Check `backend/app/services/funding.py` (already used for cost drag) and `backend/app/services/delta_candle_fetcher.py` for what's wired vs what needs adding. If perp basis isn't fetched, that's the bottleneck — without it Phase 2 is roughly half-power.

### Files (Phase 2)

**New**:
- `backend/app/engines/directional/tracks/microstructure.py` — feature compute + scoring layer
- `backend/app/services/microstructure_history.py` — funding/OI history loader (if not already present)
- `backend/app/engines/backtest/microstructure_vectorizer.py` — vectorised compute for backtests

**Modified**:
- `mean_reversion.py` (Phase 1) — gains a `microstructure_score` input it can weight into its final score
- `track_selector.py` — `microstructure` becomes an additional track that augments mean_reversion via score-blending (not a separate track in routing — blended)

### Validation (Phase 2)

Same statistical gates. Acceptance: BTC scalping_5m clears edge_proven OR closes the Sharpe gap to ≥ 0 net.

---

## Phase 3 — ML ensemble track (optional, high-overfit-risk)

Only ship if Phase 1+2 fail to deliver edge_proven on at least 2 of 3 BTC short-TF profiles. ~1 week. **High overfitting risk** — needs aggressive walk-forward + deflated-Sharpe gating; do not skip the rigour.

### Design

- Per-(asset, profile) classifier — separate model for BTC 5m, BTC 15m, BTC 30m
- Library choice: **xgboost** (sklearn-compatible, handles missing features, fast train/predict, well-understood overfit profile)
- Feature set: every flag and continuous value already computed by `signal_features` and `microstructure.py`, plus engineered ratios (e.g. RSI × ATR_pct)
- Label: `forward_return_at_hold_bars > 2 × expected_cost_pct` (binary)
- Output: `prob(profitable)` used as a soft gate AND as a tie-breaker

### Critical constraints

1. **Walk-forward only** — no IID cross-validation, no single train/test split. Use `engines/analytics/walk_forward.py` patterns.
2. **Deflated-Sharpe correction** with `n_trials_search = total_model_variants_evaluated`. ML pipelines hit hundreds of hyper-parameter combos; the deflate hurdle climbs accordingly.
3. **Feature stability check**: feature importance must be reasonably stable across walk-forward splits. Unstable feature importance = the model is fitting noise.
4. **Permutation feature importance** (sklearn has it) — confirms each retained feature contributes generalisable signal, not bar-leak.
5. **Track ranking floor**: ML must beat both Phase 1 (MR) and Phase 2 (MR + microstructure) on the same OOS data. Otherwise the ML track is dead weight.

### Files (Phase 3)

**New**:
- `backend/app/engines/ml/feature_library.py` — feature extraction from signal_features + microstructure
- `backend/app/engines/ml/labeler.py` — bar labeling for forward return
- `backend/app/engines/ml/walk_forward_train.py` — wrapper around xgboost with WF discipline
- `backend/app/engines/directional/tracks/ml_ensemble.py` — track that loads a fitted model and emits `TrackSignal`
- `backend/app/services/model_store.py` — disk persistence of fitted models per (asset, profile)
- `backend/scripts/btc_ml_train.py` — training script that produces a model file + a calibration report

**Modified**:
- `track_selector.py` — `ml_ensemble` as an additional track, blended with mean_reversion via probability weighting

**Dependencies**: `xgboost`, `scikit-learn` — add to `requirements.txt`. Both pure Python and already in the v4 ecosystem.

### Risk callout

The largest failure mode here is a model that looks brilliant in backtest and dies in live. Mitigations:
- Always shadow-trade ML signals for 30 days before promoting to live (existing `OrderRouter` shadow mode)
- Refuse to fit a model with fewer than 1000 labeled samples per class
- Refuse to deploy a model whose deflated_sharpe doesn't clear 0.99 (one notch above the 0.95 bar)

---

## Phase 4 — Per-track risk budgeting

Once two tracks coexist, position sizing needs to account for inter-track correlation. The existing `engines/risk/correlation.py` and `regime_adaptive_sizer.py` were designed for cross-asset; extending them for cross-track is small (~1 day) but necessary.

Rule: when both MR and trend_following tracks fire simultaneously on the same instrument (rare but possible — e.g. both fade-rip and ride-trend signals on a long bar), the second-firing track gets a 0.5× size multiplier. Prevents accidental position doubling.

---

## Validation strategy (cross-cutting)

Every phase ends with the same three-gate validation, identical to what `btc_scalping_search.py` already uses:

1. **Deflated Sharpe ≥ 0.95** — multiple-comparisons corrected with the actual search size
2. **Bootstrap Sharpe 5th-percentile > 0** — 2000 resamples
3. **Permutation null p < 0.05** — 2000 sign-flips

Plus the **ETH safety check** runs at start and end of every search/baseline (ETH 30m baseline must match pre to within 1e-9). This guarantees the trend-following winner never regresses.

Plus the full `pytest tests/` sweep (1086 tests) must continue to pass after every phase.

---

## Migration & revert

Each phase is **additive**:

- Phase 1 ships the track abstraction. If MR underperforms, set `track_selector` BTC routes back to `["trend_following"]` — system reverts to today's behaviour.
- Phase 2 augments MR. If microstructure data is unavailable, MR runs without it (degrades to Phase 1).
- Phase 3 is opt-in via routing. If ML overfits, drop `ml_ensemble` from the route list.
- Phase 4 size multipliers only activate when ≥2 tracks coexist; single-track profiles unaffected.

`git revert <phase commit>` restores the prior state in every case. ETH paths fall through to `trend_following` and are byte-identical guaranteed by the routing default.

---

## Wall-clock estimate

| Phase | Build | Search/calibrate | Validate | Subtotal |
|---|---|---|---|---|
| 1 (mean-reversion) | 1.5 d | 0.5 d | 0.5 d | **2.5 d** |
| 2 (microstructure) | 2 d | 1 d | 1 d | **4 d** |
| 3 (ML ensemble) | 3 d | 2 d | 1 d | **6 d** |
| 4 (risk budgeting) | 0.5 d | — | 0.5 d | **1 d** |
| **Total** | | | | **~14 d** |

Phase 1 alone is expected to deliver edge_proven on BTC scalping_30m and likely scalping_15m. That's the high-value, low-risk slice. Phases 2-3 are needed only to reach edge_proven on scalping_5m where the cost-to-volatility ratio is most adverse.

---

## Open questions to resolve before kick-off

1. **Microstructure data availability**: does `sterling_paper.db` contain funding-rate history and perp-basis history? If not, Phase 2 needs an ingestion step from Delta exchange APIs.
2. **ML dependencies**: OK to add `xgboost` + `scikit-learn` to `requirements.txt`? Adds ~50MB but those are the only credible libraries for this work.
3. **Live integration**: should MR signals be eligible for live trading after Phase 1, or kept paper-only until Phase 2 microstructure validation also passes? (Recommend paper-only for the first 30 days regardless.)
4. **Asset scope**: Phase 1 routes only BTC short-TF to MR. Should we open the routing dict to per-call config so other altcoins (SOL, AVAX, etc.) can opt in later without code changes?
