"""
Multi-timeframe backtest engine.
Bar-by-bar strategy replay for scalping (15M/1H) and intraday (1H/4H, 4H/1D) profiles.
Pure functions — no I/O.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional, Any, Tuple
import numpy as np

from app.schemas.market import Candle
from app.engines.directional.regime_engine import compute_regime  # noqa: F401 — back-compat
from app.engines.directional.signal_engine import compute_signal  # noqa: F401 — back-compat
from app.engines.directional.setup_engine import evaluate_setup
from app.schemas.directional import TradeState, SetupResult
from app.engines.indicators.atr import compute_atr
from app.core.logging import get_logger
log = get_logger(__name__)

from app.engines.analytics.performance import full_report
from app.engines.backtest.costs import compute_trade_costs, next_bar_open_fill, make_cost_model
from app.engines.backtest.mtf_vectorizer import vectorize_replay
# Tier A #9 — stateless veto modules wired into the backtest entry path.
from app.engines.risk import microstructure_veto as _micro_veto
from app.engines.risk import vol_of_vol_gate as _vov_gate

# Providers translate a bar index → the snapshot/history the corresponding
# veto needs. Returning None means "no data; do not veto". Pure functions —
# callers supply them; the backtest never reaches out.
MicroSnapshotProvider = Callable[[int], Optional[_micro_veto.MicroSnapshot]]
IvrHistoryProvider    = Callable[[int], Optional[List[float]]]

_FEE_RT_PCT = 0.001  # 0.10% round-trip taker


@dataclass
class TFProfile:
    label: str
    signal_tf: str
    regime_tf: str
    signal_bar_ms: int
    regime_bar_ms: int
    st_configs: List[Tuple[int, float]]
    min_signal_bars: int
    min_regime_bars: int
    fwd_labels: List[str]
    fwd_bars: List[int]      # n signal bars for each forward horizon
    hold_bars: int
    # Issue 6 — exit ATR timeframe.
    # "regime" (legacy): exits scale to regime-TF ATR; "signal": exits scale to
    # signal-TF ATR — tighter stops when signal_TF << regime_TF (e.g. 1H trades
    # under 4H regime). Default preserves legacy behavior.
    exit_atr_tf: Literal["signal", "regime"] = "regime"
    # Issue 7 — payoff mode.
    # "fixed_2r" (legacy): one-shot exit at +2R / -1R / hold_bars / trend flip.
    # "chandelier_trail": 50% partial at +1R, breakeven move, then trail rest
    # with Chandelier(N=22, mult=3.0*ATR(signal_TF)). Default preserves legacy.
    # "signal_atr_v4" (W6 fix): asymmetric exits anchored to *signal*-TF ATR.
    #   - Initial stop: 1.2 * signal_ATR (no HTF stop)
    #   - Take profit: 2.0 * signal_ATR → 50% partial + move stop to breakeven
    #   - Trail remainder: extreme - 1.5 * signal_ATR (ratchet only)
    #   - Time stop: hold_bars (legacy)
    #   - Trend-flip exit (legacy)
    # signal_atr_v4 forces signal-TF ATR even if exit_atr_tf="regime".
    payoff_mode: Literal[
        "fixed_2r", "chandelier_trail", "signal_atr_v4",
    ] = "fixed_2r"
    v4_stop_mult: float = 1.2
    v4_tp_mult: float = 2.0
    v4_trail_mult: float = 1.5
    # v4 — expected round-trip cost per trade (bps). Used by the cost-aware
    # entry gate: signal.signal_score must clear `score_min` net of an uplift
    # equal to `expected_cost_bps / 50` score-points (i.e. each 50 bps of
    # cost requires +1 score-point of conviction). Defaults are calibrated
    # from prior baselines: short TFs carry larger fee+slippage drag per
    # trade because their hold-time amortisation is shorter.
    expected_cost_bps: float = 30.0
    # v4 BTC tune — per-profile direction restriction. None / "both" trades
    # both sides (back-compat); "long_only" / "short_only" mirrors the
    # call-time direction_filter on run_mtf_backtest. Used to encode the
    # BTC bear-side asymmetry in PROFILES_BY_ASSET["BTC"][...].
    only_direction: Optional[Literal["long_only", "short_only", "both"]] = None


PROFILES: Dict[str, TFProfile] = {
    "scalping_5m": TFProfile(
        label="Scalping 5M",
        signal_tf="5m", regime_tf="15m",
        signal_bar_ms=5 * 60_000,
        regime_bar_ms=15 * 60_000,
        # Tuned for high-noise 5m bars: longer/wider ST legs to suppress flips.
        st_configs=[(7, 3.0), (14, 2.0), (21, 2.0)],
        min_signal_bars=60, min_regime_bars=40,
        fwd_labels=["15m", "1H", "4H"],
        fwd_bars=[3, 12, 48],
        hold_bars=16,
        expected_cost_bps=100.0,
        # Defaults baked into PROFILES so PROFILES_BY_ASSET overrides aren't
        # silently clobbered by run_baseline_db's call-level payoff_mode kwarg.
        payoff_mode="chandelier_trail",
        exit_atr_tf="signal",
    ),
    "scalping_15m": TFProfile(
        label="Scalping 15M",
        signal_tf="15m", regime_tf="1H",
        signal_bar_ms=15 * 60_000,
        regime_bar_ms=60 * 60_000,
        st_configs=[(7, 3.0), (14, 2.0), (21, 2.0)],
        min_signal_bars=50, min_regime_bars=30,
        fwd_labels=["1H", "4H", "12H"],
        fwd_bars=[4, 16, 48],
        hold_bars=16,
        expected_cost_bps=80.0,
        payoff_mode="chandelier_trail",
        exit_atr_tf="signal",
    ),
    "scalping_30m": TFProfile(
        label="Scalping 30M",
        signal_tf="30m", regime_tf="2H",
        signal_bar_ms=30 * 60_000,
        regime_bar_ms=2 * 60 * 60_000,
        st_configs=[(7, 3.0), (14, 2.0), (21, 2.0)],
        min_signal_bars=40, min_regime_bars=30,
        fwd_labels=["2H", "8H", "24H"],
        fwd_bars=[4, 16, 48],
        hold_bars=10,  # revert from 12; ETH 30m winner lost 0.24 Sharpe at 12.
        expected_cost_bps=60.0,
        payoff_mode="chandelier_trail",
        exit_atr_tf="signal",
    ),
    "intraday_1h": TFProfile(
        label="Intraday 1H",
        signal_tf="1H", regime_tf="4H",
        signal_bar_ms=60 * 60_000,
        regime_bar_ms=4 * 60 * 60_000,
        st_configs=[(7, 3.0), (14, 2.0), (21, 2.0)],
        min_signal_bars=30, min_regime_bars=55,
        fwd_labels=["4H", "12H", "24H"],
        fwd_bars=[4, 12, 24],
        hold_bars=8,
        expected_cost_bps=50.0,
        payoff_mode="chandelier_trail",
        exit_atr_tf="signal",
    ),
    "intraday_4h": TFProfile(
        label="Intraday 4H",
        signal_tf="4H", regime_tf="1D",
        signal_bar_ms=4 * 60 * 60_000,
        regime_bar_ms=24 * 60 * 60_000,
        st_configs=[(10, 3.0), (20, 2.0), (28, 1.5)],
        min_signal_bars=30, min_regime_bars=20,
        fwd_labels=["24H", "48H", "96H"],
        fwd_bars=[6, 12, 24],
        hold_bars=12,
        expected_cost_bps=40.0,
        payoff_mode="chandelier_trail",
        exit_atr_tf="signal",
    ),
}


# v4 BTC tune — Per-asset profile overrides. A key under PROFILES_BY_ASSET[asset]
# fully replaces PROFILES[key] when `underlying` resolves to that asset; missing
# entries fall through to PROFILES so non-BTC behaviour is byte-identical.
#
# Values come from `scripts/btc_scalping_search.py` (staged combinatorial
# search × walk-forward × deflated-Sharpe gate). The 2026-05-20 search ran
# 132 unique knob combos per profile across 3 train/test splits and confirmed:
#
#   * BTC short-TF has a clear directional asymmetry — `short_only` beats
#     `both` and `long_only` on every profile (matches the 1H regime breakdown
#     where BEAR_TREND wins 62-67% WR while BULL_TREND loses 32-44%).
#   * BTC scalping_5m did NOT find an edge regardless of knob choice (best OOS
#     Sharpe still −3.67). No 5m override is added — let it fall through to
#     PROFILES and rely on score_min in `_PROFILE_SCORE_MIN_PER_ASSET`.
#   * BTC scalping_15m: short_only short-circuits the BULL_TREND bleed
#     (OOS Sharpe improved from −1.97 → −0.75). Below the deflated_sharpe
#     gate but a clear improvement over the global default.
#   * BTC scalping_30m: short_only + signal_atr_v4 produced a *positive* OOS
#     Sharpe (+0.27) with profit_factor 1.18, win_rate 58.3% across 24 OOS
#     trades — directionally an edge but the sample is too thin to clear
#     deflated_sharpe ≥ 0.95. Codified anyway because it dominates the global
#     default (−1.31 → +0.27).
#
# The direction filter is a profile field (`only_direction`) consumed by the
# entry gate in `_replay_profile` so the override applies whenever this
# profile is used for BTC (live or backtest). See `direction_filter` kwarg
# on `run_mtf_backtest` for the call-time override.
PROFILES_BY_ASSET: Dict[str, Dict[str, TFProfile]] = {
    "BTC": {
        # v4 BTC tune (carry-over from the original short_only override that
        # produced the -1.97 → -1.34 Sharpe improvement on scalping_15m
        # before Phase 1). Routed to trend_following by the track router,
        # but the short_only direction lock + wider exits still apply.
        "scalping_15m": TFProfile(
            label="Scalping 15M (BTC)",
            signal_tf="15m", regime_tf="1H",
            signal_bar_ms=15 * 60_000,
            regime_bar_ms=60 * 60_000,
            st_configs=[(7, 3.0), (14, 2.0), (21, 2.0)],
            min_signal_bars=50, min_regime_bars=30,
            fwd_labels=["1H", "4H", "12H"],
            fwd_bars=[4, 16, 48],
            hold_bars=20,
            expected_cost_bps=80.0,
            payoff_mode="chandelier_trail",
            exit_atr_tf="signal",
            v4_stop_mult=1.2, v4_tp_mult=1.5, v4_trail_mult=1.5,
            only_direction="short_only",
        ),
        # v4 Phase 1 — mean-reversion (fade-extremes) winner from the
        # 2026-05-21 search (`baselines/btc_mr_search_20260521.json`).
        # Knobs (TFProfile fields) + FadeExtremesConfig (mr_config passed at
        # call-time by run_baseline_db / orchestrator).
        # Search OOS metrics:
        #   test_sharpe=+0.063, oos_trade_count=28 (sample below the
        #   50-trade deflated_sharpe threshold), PF/WR per the JSON.
        # Improvement vs trend_following baseline (-0.34 OOS Sharpe) = +0.40.
        "scalping_30m": TFProfile(
            label="Scalping 30M (BTC-MR-v2)",
            signal_tf="30m", regime_tf="2H",
            signal_bar_ms=30 * 60_000,
            regime_bar_ms=2 * 60 * 60_000,
            st_configs=[(7, 3.0), (14, 2.0), (21, 2.0)],
            min_signal_bars=40, min_regime_bars=30,
            fwd_labels=["2H", "8H", "24H"],
            fwd_bars=[4, 16, 48],
            # Edge-stacking pass (2026-05-21):
            #   stop=0.8 / tp=4.0 / trail=3.0 / hold=24 / signal_atr_v4
            #   + entry_hours_utc=16..22 + short_only
            # On the full series:
            #   sample_30 (16-22h, sm=10) → Sharpe 0.96, PF 1.86, WR 53%
            #   sample_66 (13-23h, sm=10) → Sharpe 0.46, PF 1.24, WR 44%
            # The 16-22 UTC window is the best quality but n is below the
            # 50-trade floor that build_report needs to compute deflated_p,
            # so the formal "edge_proven" gate cannot clear on this sample
            # alone. The 14-23 window is the compromise — enough trades to
            # cross the deflated_p sample bar, with PF 1.22 and WR 46%.
            hold_bars=24,
            expected_cost_bps=60.0,
            payoff_mode="signal_atr_v4",
            exit_atr_tf="signal",
            v4_stop_mult=0.8, v4_tp_mult=4.0, v4_trail_mult=3.0,
            only_direction="short_only",
        ),
    },
}

# Default mr_config to pass when no per-asset override is supplied.
# Mirrors the search winner + edge-stacking pass for scalping_30m. The
# orchestrator looks this up by (asset, profile_key) and passes it to
# run_mtf_backtest as `mr_config=`. (Mean-reversion signal generation was
# removed in the strategy reset; vectorize_replay is currently a neutral stub.)
MR_CONFIG_BY_ASSET: Dict[str, Dict[str, Dict[str, Any]]] = {
    "BTC": {
        "scalping_30m": {
            "rsi_extreme_high":  70.0,
            "rsi_extreme_low":   30.0,
            "vol_climax_pct":    0.92,
            "short_bias_boost":  2.0,
            # NOTE: An hour-filter (16-22 UTC) variant scored Sharpe 0.96
            # in-sample but turned negative on the second half of data —
            # classic overfit. The all-hours config (no `entry_hours_utc`)
            # was the only variant whose Sharpe stayed positive across
            # BOTH halves of the full series (H1: 1.34, H2: 0.93). Edge
            # stacking is therefore *exits-only* here: signal_atr_v4 with
            # wide TP/trail captures enough per-trade PnL that costs no
            # longer dominate. Hour filter intentionally OMITTED.
        },
    },
}


def resolve_mr_config(underlying: str, profile_key: str) -> Optional[Dict[str, Any]]:
    """Look up the persisted FadeExtremes knobs for (asset, profile).
    Returns None if no override is defined → FadeExtremesConfig defaults apply."""
    asset_key = (underlying or "").replace("USDT", "").replace("USD", "").upper()
    return MR_CONFIG_BY_ASSET.get(asset_key, {}).get(profile_key)


# Profile keys treated as "scalping" for session-hour gating and the
# trending-only regime restriction in setup_engine.
_SCALPING_PROFILE_KEYS = frozenset({"scalping_5m", "scalping_15m", "scalping_30m"})


def _is_scalping_label(label: str) -> bool:
    """True iff this profile label denotes a scalping (sub-1H) TF."""
    norm = (label or "").lower().replace(" ", "")
    return norm.startswith("scalping")


def _allowed_entry_hour_utc(ts_ms: int) -> bool:
    """
    Cost-aware session filter for scalping profiles.

    Crypto liquidity skews to US/EU sessions. Entries during the 22:00-06:59 UTC
    band suffer wider spreads and lower follow-through; baselines show this
    band is the largest contributor to scalping cost drag.

    Returns True for hours 7-21 UTC (inclusive), False for 22-06 UTC.
    """
    hour = (ts_ms // 3_600_000) % 24
    return 7 <= hour <= 21


def _fwd_return(candles: List[Candle], from_idx: int, n_bars: int) -> Optional[float]:
    to_idx = from_idx + n_bars
    if to_idx >= len(candles):
        return None
    base = candles[from_idx].close
    if base <= 0:
        return None
    return round((candles[to_idx].close - base) / base * 100.0, 4)


def _zero_result(profile: TFProfile, n_signal: int = 0, n_regime: int = 0, underlying: str = "") -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "label": profile.label,
        "signal_tf": profile.signal_tf,
        "regime_tf": profile.regime_tf,
        "underlying": underlying,
        "total_signal_bars": n_signal,
        "total_regime_bars": n_regime,
        "total_trades": 0,
        "win_rate": None,
        "sharpe": None,
        "calmar": None,
        "sortino": None,
        "profit_factor": None,
        "max_drawdown": None,
        "avg_rr": None,
        "equity_curve": [1.0, 1.0],
        "regime_breakdown": {},
    }
    for k, lbl in enumerate(profile.fwd_labels):
        result[f"fwd{k+1}_label"]          = lbl
        result[f"fwd{k+1}_long_win_rate"]  = None
        result[f"fwd{k+1}_short_win_rate"] = None
    return result


def _build_atr_series(candles: List[Candle], period: int = 14) -> np.ndarray:
    """Pre-compute ATR over the entire candle series once (Issue 15)."""
    if not candles:
        return np.array([], dtype=np.float64)
    highs = np.array([c.high for c in candles], dtype=np.float64)
    lows  = np.array([c.low  for c in candles], dtype=np.float64)
    closes = np.array([c.close for c in candles], dtype=np.float64)
    return compute_atr(highs, lows, closes, period)


def _replay_profile(
    profile: TFProfile,
    candles_signal: List[Candle],
    candles_regime: List[Candle],
    score_min: float = 0.0,
    fee_rt_pct: Optional[float] = None,
    underlying: str = "",
    *,
    structure_type: str = "futures",
    leverage: float = 1.0,
    oi: Optional[float] = None,
    funding_8h_pct: float = 0.0,
    option_spread_pct: Optional[float] = None,
    apply_slippage: bool = True,
    emit_events: bool = False,
    # Tier A #9 — optional live risk gate providers. When supplied, each
    # candidate entry is run through the stateless microstructure and
    # vol-of-vol vetoes; vetoed candidates are skipped and logged.
    micro_snapshot_provider: Optional[MicroSnapshotProvider] = None,
    ivr_history_provider:    Optional[IvrHistoryProvider]    = None,
    micro_veto_config:       Optional[_micro_veto.MicroVetoConfig]  = None,
    vov_thresholds:          Optional[_vov_gate.VolOfVolThresholds] = None,
    # v4 BTC tune — restrict entries to one side. None = both sides (back-compat).
    direction_filter:        Optional[Literal["long_only", "short_only", "both"]] = None,
    # v4 Phase 1 — multi-track support. `profile_key` lets the router resolve
    # the active track list. `active_tracks` (set by the caller) selects which
    # SignalResult source the entry loop reads from. Defaults preserve the
    # legacy trend_following-only behaviour byte-identical.
    profile_key:             Optional[str] = None,
    active_tracks:           Optional[List[str]] = None,
    mr_config:               Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Bar-by-bar trade replay for one TF profile with truthful fills and costs.

    Entry: CONFIRMED_SETUP_ACTIVE + signal_score >= score_min.
    Exit:  trend reversal | ATR-based +2R/-1R | hold_bars elapsed
           (legacy `fixed_2r`), or partial 50% at +1R + breakeven + chandelier
           trail (opt-in `chandelier_trail`).

    Fills land on the OPEN of the bar following the signal bar (no signal-bar
    close execution). Slippage, fees, perpetual funding (by actual hold time),
    and optional option half-spread are attributed via `costs.compute_trade_costs`.
    Trades record both gross and net PnL with full cost breakdown.

    When `emit_events=True`, the result includes an `events` list containing
    candidate/skip/entry/exit records in chronological order. Default output
    shape is unchanged.

    Issue 15: regime slicing was O(N) inside an O(N) loop; we now maintain a
    monotonically advancing cursor `regime_idx` and pre-compute the regime
    and signal ATR series once.
    """
    n_signal = len(candles_signal)
    n_regime = len(candles_regime)

    if fee_rt_pct is None:
        fee_rt_pct = make_cost_model(structure_type)

    if n_signal < profile.min_signal_bars or n_regime < profile.min_regime_bars:
        zero = _zero_result(profile, n_signal, n_regime, underlying=underlying)
        if emit_events:
            zero["events"] = []
        return zero

    # Lazy-import to avoid circular dependency
    if emit_events:
        from app.engines.backtest.event_ledger import EventLedger
        ledger = EventLedger()
    else:
        ledger = None

    signal_bar_ms = profile.signal_bar_ms
    regime_bar_ms = profile.regime_bar_ms

    # v4 Phase 1 — Pre-resolve the active track set. If `active_tracks` was
    # passed by `run_mtf_backtest`, honour it. Otherwise fall back to the
    # router (lets `_replay_profile` be called directly with sensible
    # defaults). The "active track" decides whether we read MR signals.
    if active_tracks is None:
        try:
            from app.engines.directional.track_selector import select_tracks
            active_tracks = select_tracks(underlying, profile_key)
        except Exception:
            active_tracks = ["trend_following"]
    _mr_active = ("mean_reversion" in active_tracks)

    # W11 — vectorise all per-bar regime/signal/indicator work in O(N) up
    # front. The replay loop below uses O(1) array lookups instead of the
    # legacy per-bar compute_regime / compute_signal calls.
    vec = vectorize_replay(
        candles_signal, candles_regime,
        signal_bar_ms=signal_bar_ms,
        regime_bar_ms=regime_bar_ms,
        st_configs=profile.st_configs,
        build_mr=_mr_active,
        mr_config=mr_config,
    )
    regime_atr_full = vec.regime_atr14
    signal_atr_full = vec.signal_atr14
    signal_atr22_full = vec.signal_atr22
    regime_ts = np.array(
        [c.timestamp_ms for c in candles_regime], dtype=np.int64,
    )

    use_signal_atr = profile.exit_atr_tf == "signal"
    use_trail = profile.payoff_mode == "chandelier_trail"
    use_v4    = profile.payoff_mode == "signal_atr_v4"
    if use_v4:
        # W6 fix mandates signal-TF ATR for stops/trail regardless of the
        # exit_atr_tf flag, so callers can't accidentally re-introduce the
        # HTF-anchored stop that caused outsized drawdowns.
        use_signal_atr = True
    # v4 exit constants (anchored to signal-TF ATR at entry).
    V4_STOP_MULT       = profile.v4_stop_mult
    V4_TP_MULT         = profile.v4_tp_mult
    V4_TRAIL_MULT      = profile.v4_trail_mult
    V4_PARTIAL_RATIO   = 0.5

    trades: List[Dict[str, Any]] = []
    in_trade      = False
    entry_bar     = 0           # index of the signal bar that triggered entry
    entry_fill_bar = 0          # index of the bar where entry actually filled
    entry_dir     = 0
    entry_price   = 0.0         # clean fill price (next bar open)
    entry_atr     = 0.0
    entry_regime  = "unknown"
    entry_ts_ms   = 0
    # Trail state (only used in chandelier_trail mode)
    trail_partial_taken = False
    trail_extreme_price = 0.0       # max high (long) / min low (short) since entry
    trail_stop_price    = 0.0
    trail_remaining_ratio = 1.0     # 1.0 then 0.5 after partial

    for i in range(profile.min_signal_bars, n_signal - 1):
        ts = candles_signal[i].timestamp_ms

        # W11 — regime_idx is now a precomputed lookup. regime and signal
        # are O(1) array lookups from the vectoriser; the per-bar
        # compute_regime / compute_signal calls have been removed.
        regime_idx = int(vec.regime_idx_at_signal[i])
        if regime_idx < profile.min_regime_bars:
            continue
        regime = vec.regimes_per_regime_bar[regime_idx - 1]
        # v4 Phase 1 — Pick the SignalResult source based on the active track.
        # MR track has its own setup state: a non-zero trend AND score > 0 in
        # mr_signals[i] means the fade-extremes gates fired (regime + RSI + BB
        # all passed). We synthesise a CONFIRMED_SETUP_ACTIVE so the entry
        # gate logic below stays identical for both tracks.
        if _mr_active and vec.mr_signals is not None:
            from app.schemas.directional import Direction
            signal = vec.mr_signals[i]
            if signal.trend != 0 and signal.signal_score > 0:
                setup = SetupResult(
                    state=TradeState.CONFIRMED_SETUP_ACTIVE,
                    direction=(Direction.LONG if signal.trend == 1 else Direction.SHORT),
                    reason=f"mean_reversion track score={signal.signal_score:.1f}",
                    macro_regime=regime.macro_regime,
                    signal_trend=signal.trend,
                )
            else:
                setup = SetupResult(
                    state=TradeState.FILTERED,
                    direction=Direction.NEUTRAL,
                    reason="mean_reversion: gates not met",
                    macro_regime=regime.macro_regime,
                    signal_trend=0,
                )
        else:
            signal = vec.signals[i]
            setup  = evaluate_setup(regime, signal, profile_label=profile.label)

        # ── Exit logic ─────────────────────────────────────────────────────────
        just_exited = False
        if in_trade:
            cur_close = candles_signal[i].close
            cur_high  = candles_signal[i].high
            cur_low   = candles_signal[i].low
            held = i - entry_bar
            gain_abs = entry_dir * (cur_close - entry_price)

            # ── W6 fix: signal-TF asymmetric exits ──────────────────────────
            # Initial 1.2x ATR stop / 2.0x ATR TP (50% partial → breakeven →
            # 1.5x ATR chandelier trail) / hold_bars / trend flip.
            if use_v4 and entry_atr > 0 and entry_price > 0:
                # Update extreme since entry (used by the 1.5x trail).
                if entry_dir == 1:
                    if cur_high > trail_extreme_price:
                        trail_extreme_price = cur_high
                else:
                    if cur_low < trail_extreme_price or trail_extreme_price == 0.0:
                        trail_extreme_price = cur_low

                # Initial stop level: entry ∓ 1.2 * ATR (stored at entry time).
                # trail_stop_price holds the active stop; pre-partial it equals
                # the initial 1.2x ATR stop; post-partial it ratchets via the
                # chandelier trail and can only tighten in the trade's favour.
                if (not trail_partial_taken) and gain_abs >= V4_TP_MULT * entry_atr:
                    # 2x ATR target hit → book V4_PARTIAL_RATIO at next-bar open
                    # and move the stop to breakeven for the remainder.
                    fill = next_bar_open_fill(candles_signal, i)
                    if fill is not None:
                        partial_px, partial_fill_bar = fill
                        partial_ts_ms = candles_signal[partial_fill_bar].timestamp_ms
                        partial_hold_hours = max(
                            0.0, (partial_ts_ms - entry_ts_ms) / 3_600_000.0
                        )
                        partial_breakdown = compute_trade_costs(
                            direction=entry_dir,
                            entry_price=entry_price,
                            exit_price=partial_px,
                            structure_type=structure_type,
                            leverage=leverage, oi=oi,
                            fee_rt_pct=fee_rt_pct * V4_PARTIAL_RATIO,
                            hold_hours=partial_hold_hours,
                            funding_8h_pct=funding_8h_pct,
                            option_spread_pct=option_spread_pct,
                            apply_slippage=apply_slippage, forced_end=False,
                        )
                        partial_trade = {
                            "pnl_pct":         partial_breakdown.net_pnl_pct * V4_PARTIAL_RATIO,
                            "gross_pnl_pct":   partial_breakdown.gross_pnl_pct * V4_PARTIAL_RATIO,
                            "net_pnl_pct":     partial_breakdown.net_pnl_pct * V4_PARTIAL_RATIO,
                            "cost_pct":        partial_breakdown.total_cost_pct * V4_PARTIAL_RATIO,
                            "slippage_pct":    partial_breakdown.slippage_pct,
                            "fee_pct":         partial_breakdown.fee_pct,
                            "funding_pct":     partial_breakdown.funding_pct,
                            "option_spread_pct": partial_breakdown.option_spread_pct,
                            "entry_price":     partial_breakdown.effective_entry_price,
                            "exit_price":      partial_breakdown.effective_exit_price,
                            "hold_hours":      partial_breakdown.hold_hours,
                            "regime":          entry_regime,
                            "entry_bar":       entry_bar,
                            "exit_bar":        partial_fill_bar,
                            "entry_ts_ms":     entry_ts_ms,
                            "exit_ts_ms":      partial_ts_ms,
                            "direction":       "long" if entry_dir == 1 else "short",
                            "forced_end":      False,
                            "partial":         True,
                            "asset":           underlying,
                            "profile":         profile.label,
                            "track":           "directional",
                        }
                        trades.append(partial_trade)
                        if ledger is not None:
                            ledger.record_exit(partial_trade)
                            ledger.record_trade(partial_trade)
                        trail_partial_taken = True
                        trail_remaining_ratio = 1.0 - V4_PARTIAL_RATIO
                        trail_stop_price = entry_price  # breakeven

                # Chandelier trail (1.5x ATR) — ratchet only after partial.
                proposed_trail = (
                    trail_extreme_price - V4_TRAIL_MULT * entry_atr if entry_dir == 1
                    else trail_extreme_price + V4_TRAIL_MULT * entry_atr
                )
                if trail_partial_taken:
                    if entry_dir == 1:
                        trail_stop_price = max(trail_stop_price, proposed_trail)
                    else:
                        trail_stop_price = (
                            min(trail_stop_price, proposed_trail)
                            if trail_stop_price > 0 else proposed_trail
                        )
                else:
                    # Pre-partial stop is fixed at entry ∓ 1.2x ATR.
                    initial_stop = (
                        entry_price - V4_STOP_MULT * entry_atr if entry_dir == 1
                        else entry_price + V4_STOP_MULT * entry_atr
                    )
                    trail_stop_price = initial_stop

                # Exit on stop hit (intrabar low/high vs current stop).
                if entry_dir == 1 and cur_low <= trail_stop_price:
                    exit_now = True
                elif entry_dir == -1 and cur_high >= trail_stop_price:
                    exit_now = True
                else:
                    exit_now = False

                # Legacy time stop.
                if not exit_now:
                    exit_now = held >= profile.hold_bars
                # Legacy trend-flip exit.
                if not exit_now:
                    if entry_dir == 1 and signal.trend == -1:
                        exit_now = True
                    elif entry_dir == -1 and signal.trend == 1:
                        exit_now = True
            # Trail/chandelier path is computed alongside legacy exits so
            # both modes follow the same hold-bars / trend-reversal guards.
            elif use_trail and entry_atr > 0 and entry_price > 0:
                # Update extreme since entry
                if entry_dir == 1:
                    if cur_high > trail_extreme_price:
                        trail_extreme_price = cur_high
                else:
                    if cur_low < trail_extreme_price or trail_extreme_price == 0.0:
                        trail_extreme_price = cur_low

                # Partial-take at +1.5R (was +1R).
                # +1R partial + breakeven was the root cause of PF=0.65 at
                # WR=55% on baseline: winners booked at ~1R against -1R losers,
                # net-negative after fees. Lifting to +1.5R restores asymmetry.
                if (not trail_partial_taken) and gain_abs >= 1.5 * entry_atr:
                    fill = next_bar_open_fill(candles_signal, i)
                    if fill is not None:
                        partial_px, partial_fill_bar = fill
                        partial_ts_ms = candles_signal[partial_fill_bar].timestamp_ms
                        partial_hold_hours = max(
                            0.0, (partial_ts_ms - entry_ts_ms) / 3_600_000.0
                        )
                        partial_breakdown = compute_trade_costs(
                            direction=entry_dir,
                            entry_price=entry_price,
                            exit_price=partial_px,
                            structure_type=structure_type,
                            leverage=leverage,
                            oi=oi,
                            fee_rt_pct=fee_rt_pct * 0.5,  # half RT for partial
                            hold_hours=partial_hold_hours,
                            funding_8h_pct=funding_8h_pct,
                            option_spread_pct=option_spread_pct,
                            apply_slippage=apply_slippage,
                            forced_end=False,
                        )
                        # Book the partial as a synthetic half-trade.
                        partial_trade = {
                            "pnl_pct":         partial_breakdown.net_pnl_pct * 0.5,
                            "gross_pnl_pct":   partial_breakdown.gross_pnl_pct * 0.5,
                            "net_pnl_pct":     partial_breakdown.net_pnl_pct * 0.5,
                            "cost_pct":        partial_breakdown.total_cost_pct * 0.5,
                            "slippage_pct":    partial_breakdown.slippage_pct,
                            "fee_pct":         partial_breakdown.fee_pct,
                            "funding_pct":     partial_breakdown.funding_pct,
                            "option_spread_pct": partial_breakdown.option_spread_pct,
                            "entry_price":     partial_breakdown.effective_entry_price,
                            "exit_price":      partial_breakdown.effective_exit_price,
                            "hold_hours":      partial_breakdown.hold_hours,
                            "regime":          entry_regime,
                            "entry_bar":       entry_bar,
                            "exit_bar":        partial_fill_bar,
                            "entry_ts_ms":     entry_ts_ms,
                            "exit_ts_ms":      partial_ts_ms,
                            "direction":       "long" if entry_dir == 1 else "short",
                            "forced_end":      False,
                            "partial":         True,
                            "asset":           underlying,
                            "profile":         profile.label,
                            "track":           "directional",
                        }
                        trades.append(partial_trade)
                        if ledger is not None:
                            ledger.record_exit(partial_trade)
                            ledger.record_trade(partial_trade)
                        trail_partial_taken = True
                        trail_remaining_ratio = 0.5
                        # Move stop to breakeven
                        trail_stop_price = entry_price

                # Chandelier trail on remaining position
                idx22 = i if i < len(signal_atr22_full) else len(signal_atr22_full) - 1
                atr22 = float(signal_atr22_full[idx22]) if (
                    idx22 >= 0 and not np.isnan(signal_atr22_full[idx22])
                ) else entry_atr
                if atr22 <= 0:
                    atr22 = entry_atr
                proposed = (
                    trail_extreme_price - 3.0 * atr22 if entry_dir == 1
                    else trail_extreme_price + 3.0 * atr22
                )
                if trail_partial_taken:
                    # After breakeven move, trail can only tighten the stop
                    if entry_dir == 1:
                        trail_stop_price = max(trail_stop_price, proposed)
                    else:
                        trail_stop_price = (
                            min(trail_stop_price, proposed) if trail_stop_price > 0
                            else proposed
                        )

                # Exit on stop hit
                if trail_partial_taken:
                    if entry_dir == 1 and cur_low <= trail_stop_price:
                        exit_now = True
                    elif entry_dir == -1 and cur_high >= trail_stop_price:
                        exit_now = True
                    else:
                        exit_now = False
                else:
                    # Pre-partial: only the original -1R stop applies
                    exit_now = gain_abs <= -entry_atr

                if not exit_now:
                    exit_now = held >= profile.hold_bars
                if not exit_now:
                    if entry_dir == 1 and signal.trend == -1:
                        exit_now = True
                    elif entry_dir == -1 and signal.trend == 1:
                        exit_now = True
            else:
                exit_now = held >= profile.hold_bars
                if not exit_now and entry_atr > 0 and entry_price > 0:
                    exit_now = gain_abs >= 2 * entry_atr or gain_abs <= -entry_atr
                if not exit_now:
                    if entry_dir == 1 and signal.trend == -1:
                        exit_now = True
                    elif entry_dir == -1 and signal.trend == 1:
                        exit_now = True

            if exit_now:
                # Exit fills at next bar open (no signal-bar close execution)
                fill = next_bar_open_fill(candles_signal, i)
                if fill is None:
                    # No future bar — defer to forced end-of-data handler below
                    pass
                else:
                    exit_px, exit_fill_bar = fill
                    exit_ts_ms = candles_signal[exit_fill_bar].timestamp_ms
                    hold_hours = max(
                        0.0, (exit_ts_ms - entry_ts_ms) / 3_600_000.0
                    )
                    rem_fee = fee_rt_pct * trail_remaining_ratio
                    breakdown = compute_trade_costs(
                        direction=entry_dir,
                        entry_price=entry_price,
                        exit_price=exit_px,
                        structure_type=structure_type,
                        leverage=leverage,
                        oi=oi,
                        fee_rt_pct=rem_fee,
                        hold_hours=hold_hours,
                        funding_8h_pct=funding_8h_pct,
                        option_spread_pct=option_spread_pct,
                        apply_slippage=apply_slippage,
                        forced_end=False,
                    )
                    trade = {
                        "pnl_pct":         breakdown.net_pnl_pct * trail_remaining_ratio,
                        "gross_pnl_pct":   breakdown.gross_pnl_pct * trail_remaining_ratio,
                        "net_pnl_pct":     breakdown.net_pnl_pct * trail_remaining_ratio,
                        "cost_pct":        breakdown.total_cost_pct * trail_remaining_ratio,
                        "slippage_pct":    breakdown.slippage_pct,
                        "fee_pct":         breakdown.fee_pct,
                        "funding_pct":     breakdown.funding_pct,
                        "option_spread_pct": breakdown.option_spread_pct,
                        "entry_price":     breakdown.effective_entry_price,
                        "exit_price":      breakdown.effective_exit_price,
                        "hold_hours":      breakdown.hold_hours,
                        "regime":          entry_regime,
                        "entry_bar":       entry_bar,
                        "exit_bar":        exit_fill_bar,
                        "entry_ts_ms":     entry_ts_ms,
                        "exit_ts_ms":      exit_ts_ms,
                        "direction":       "long" if entry_dir == 1 else "short",
                        "forced_end":      False,
                        "partial":         False,
                        "asset":           underlying,
                        "profile":         profile.label,
                        "track":           "directional",
                    }
                    trades.append(trade)
                    if ledger is not None:
                        ledger.record_exit(trade)
                        ledger.record_trade(trade)
                    in_trade    = False
                    just_exited = True
                    trail_partial_taken = False
                    trail_remaining_ratio = 1.0
                    trail_extreme_price = 0.0
                    trail_stop_price = 0.0

        # ── Entry logic ────────────────────────────────────────────────────────
        if not in_trade and not just_exited:
            sig_score = float(getattr(signal, "signal_score", 0.0) or 0.0)
            # Session-hours veto for scalping profiles: skip the 22-06 UTC band
            # where spreads widen and cost drag dominates the move.
            in_session = (
                True if not _is_scalping_label(profile.label)
                else _allowed_entry_hour_utc(ts)
            )
            # v4 — cost-aware effective score gate. Each 50 bps of expected
            # round-trip cost requires +1 score-point of signal conviction.
            # A 100-bps profile (5m scalping) needs sig_score ≥ score_min + 2;
            # a 40-bps profile (intraday_4h) needs sig_score ≥ score_min + 0.8.
            # This compensates for the cost-drag-eats-edge regime: short TFs
            # naturally need higher conviction to justify the per-trade tax.
            cost_uplift = float(profile.expected_cost_bps) / 50.0
            # MTF agreement gate: signal trend must match regime trend bias.
            # When directionally opposed, the setup_engine usually filters but
            # ranging/volatile branches can let counter-trend through; tighten
            # those by requiring an additional 2 points of conviction.
            macro_name = regime.macro_regime.value
            macro_is_bull = "BULL" in macro_name
            macro_is_bear = "BEAR" in macro_name
            mtf_disagreement = (
                (macro_is_bull and signal.trend == -1)
                or (macro_is_bear and signal.trend == 1)
            )
            mtf_uplift = 2.0 if mtf_disagreement else 0.0
            effective_score = sig_score - cost_uplift - mtf_uplift
            # v4 BTC tune — optional one-sided trading. Asymmetric assets (BTC
            # short-TF wins disproportionately on the short side) benefit from
            # disabling one direction entirely. The profile field
            # `only_direction` is the persistent setting (used by BTC overrides
            # in PROFILES_BY_ASSET) and the `direction_filter` kwarg is the
            # call-time override (used by the search driver). When BOTH are
            # set, the call-time kwarg wins (last-write semantics matches the
            # rest of the override surface).
            effective_dir = direction_filter if direction_filter is not None else profile.only_direction
            dir_ok = (
                effective_dir is None
                or effective_dir == "both"
                or (effective_dir == "long_only"  and signal.trend ==  1)
                or (effective_dir == "short_only" and signal.trend == -1)
            )
            qualifies = (
                setup.state == TradeState.CONFIRMED_SETUP_ACTIVE
                and effective_score >= score_min
                and signal.trend != 0
                and in_session
                and dir_ok
            )
            if qualifies:
                # ── Tier A #9: stateless live risk gates ────────────────
                # When providers are supplied we evaluate microstructure and
                # vol-of-vol vetoes BEFORE the next-bar fill. A veto skips the
                # trade and logs a skip event; we do not record an entry.
                veto_code: Optional[str] = None
                veto_reason: Optional[str] = None
                proposed_direction = "long" if signal.trend == 1 else "short"

                if micro_snapshot_provider is not None:
                    snap = micro_snapshot_provider(i)
                    if snap is not None:
                        m_decision = _micro_veto.evaluate(
                            direction=proposed_direction,
                            snapshot=snap,
                            config=micro_veto_config,
                        )
                        if m_decision.veto:
                            veto_code, veto_reason = m_decision.code, m_decision.reason

                if veto_code is None and ivr_history_provider is not None:
                    ivr_hist = ivr_history_provider(i)
                    if ivr_hist:
                        v_decision = _vov_gate.compute(
                            ivr_history=ivr_hist,
                            thresholds=vov_thresholds,
                        )
                        if v_decision.block_naked:
                            veto_code = "vol_of_vol_block_naked"
                            veto_reason = v_decision.reason

                if veto_code is not None:
                    if ledger is not None:
                        ledger.record_skip(
                            bar_idx=i, ts_ms=ts, asset=underlying,
                            profile=profile.label, track="directional",
                            reason=f"live_risk_gate:{veto_code}",
                            features={"detail": veto_reason or ""},
                        )
                    continue

                fill = next_bar_open_fill(candles_signal, i)
                if fill is None:
                    # Signal on the last evaluable bar with no future open —
                    # explicitly skip to avoid last-bar lookahead.
                    if ledger is not None:
                        ledger.record_skip(
                            bar_idx=i, ts_ms=ts, asset=underlying,
                            profile=profile.label, track="directional",
                            reason="no_future_bar_for_entry_fill",
                        )
                    continue
                entry_px, entry_fill_bar = fill
                in_trade       = True
                entry_bar      = i
                entry_dir      = signal.trend
                entry_price    = entry_px
                entry_ts_ms    = candles_signal[entry_fill_bar].timestamp_ms
                entry_regime   = regime.macro_regime.value
                # Issue 6 — ATR source flag-controlled.
                if use_signal_atr:
                    arr = signal_atr_full
                    # We use signal-bar i, but ATR is undefined at the very
                    # first 14 bars; we already pass min_signal_bars >= 30.
                    idx = i if i < len(arr) else len(arr) - 1
                    v = float(arr[idx]) if (idx >= 0 and not np.isnan(arr[idx])) else 0.0
                else:
                    arr = regime_atr_full
                    idx = regime_idx - 1
                    v = float(arr[idx]) if (
                        0 <= idx < len(arr) and not np.isnan(arr[idx])
                    ) else 0.0
                entry_atr = v if v > 0 else entry_price * 0.02
                # Reset trail state on entry
                trail_partial_taken = False
                trail_remaining_ratio = 1.0
                trail_extreme_price = entry_price
                trail_stop_price = 0.0
                if ledger is not None:
                    ledger.record_entry({
                        "bar_idx":   entry_fill_bar,
                        "signal_bar_idx": i,
                        "ts_ms":     entry_ts_ms,
                        "asset":     underlying,
                        "profile":   profile.label,
                        "track":     "directional",
                        "direction": "long" if entry_dir == 1 else "short",
                        "entry_price": entry_price,
                        "regime":    entry_regime,
                        "sig_score": sig_score,
                    })
            elif ledger is not None and setup.state != TradeState.CONFIRMED_SETUP_ACTIVE:
                ledger.record_skip(
                    bar_idx=i, ts_ms=ts, asset=underlying,
                    profile=profile.label, track="directional",
                    reason=f"setup_state={setup.state.value}",
                )

    # Close any open trade at end of data (no future bar — fill at last close,
    # forced end-of-data, explicitly marked).
    if in_trade:
        last_i  = n_signal - 1
        exit_px = candles_signal[last_i].close
        exit_ts_ms = candles_signal[last_i].timestamp_ms
        hold_hours = max(0.0, (exit_ts_ms - entry_ts_ms) / 3_600_000.0)
        rem_fee = fee_rt_pct * trail_remaining_ratio
        breakdown = compute_trade_costs(
            direction=entry_dir,
            entry_price=entry_price,
            exit_price=exit_px,
            structure_type=structure_type,
            leverage=leverage,
            oi=oi,
            fee_rt_pct=rem_fee,
            hold_hours=hold_hours,
            funding_8h_pct=funding_8h_pct,
            option_spread_pct=option_spread_pct,
            apply_slippage=apply_slippage,
            forced_end=True,
        )
        trade = {
            "pnl_pct":         breakdown.net_pnl_pct * trail_remaining_ratio,
            "gross_pnl_pct":   breakdown.gross_pnl_pct * trail_remaining_ratio,
            "net_pnl_pct":     breakdown.net_pnl_pct * trail_remaining_ratio,
            "cost_pct":        breakdown.total_cost_pct * trail_remaining_ratio,
            "slippage_pct":    breakdown.slippage_pct,
            "fee_pct":         breakdown.fee_pct,
            "funding_pct":     breakdown.funding_pct,
            "option_spread_pct": breakdown.option_spread_pct,
            "entry_price":     breakdown.effective_entry_price,
            "exit_price":      breakdown.effective_exit_price,
            "hold_hours":      breakdown.hold_hours,
            "regime":          entry_regime,
            "entry_bar":       entry_bar,
            "exit_bar":        last_i,
            "entry_ts_ms":     entry_ts_ms,
            "exit_ts_ms":      exit_ts_ms,
            "direction":       "long" if entry_dir == 1 else "short",
            "forced_end":      True,
            "partial":         False,
            "asset":           underlying,
            "profile":         profile.label,
            "track":           "directional",
        }
        trades.append(trade)
        if ledger is not None:
            ledger.record_exit(trade)
            ledger.record_trade(trade)

    # ── Forward-return win rates per horizon (arrow-based) ────────────────────
    # W11 — signals are precomputed by the vectoriser; pass 1 collapses to
    # a regime-cursor filter against the already-built array.
    _bar_signals: Dict[int, Any] = {}
    for j in range(profile.min_signal_bars, n_signal):
        fwd_regime_idx = int(vec.regime_idx_at_signal[j])
        if fwd_regime_idx < profile.min_regime_bars:
            continue
        _bar_signals[j] = vec.signals[j]

    # Pass 2: collect forward returns per horizon (reuses precomputed signals)
    fwd_win_rates: List[Tuple[str, Optional[float], Optional[float]]] = []
    for n_bars, lbl in zip(profile.fwd_bars, profile.fwd_labels):
        long_rets: List[float]  = []
        short_rets: List[float] = []
        for j, sig_j in _bar_signals.items():
            fwd = _fwd_return(candles_signal, j, n_bars)
            if fwd is None:
                continue
            if sig_j.green_arrow:
                long_rets.append(fwd)
            elif sig_j.red_arrow:
                short_rets.append(fwd)
        long_wr = (
            round(sum(1 for r in long_rets  if r > 0) / len(long_rets)  * 100, 1)
            if long_rets else None
        )
        short_wr = (
            round(sum(1 for r in short_rets if r < 0) / len(short_rets) * 100, 1)
            if short_rets else None
        )
        fwd_win_rates.append((lbl, long_wr, short_wr))

    # ── Build result dict ─────────────────────────────────────────────────────
    if not trades:
        result = _zero_result(profile, n_signal, n_regime, underlying=underlying)
        for k, (lbl, lwr, swr) in enumerate(fwd_win_rates):
            result[f"fwd{k+1}_label"]          = lbl
            result[f"fwd{k+1}_long_win_rate"]  = lwr
            result[f"fwd{k+1}_short_win_rate"] = swr
        if emit_events and ledger is not None:
            result["events"] = ledger.events_as_dicts()
        return result

    pnls = [t["pnl_pct"] for t in trades]
    curve = np.ones(len(pnls) + 1, dtype=np.float64)
    for idx, p in enumerate(pnls):
        curve[idx + 1] = curve[idx] * (1.0 + p)

    # Per-bar (signal-bar) timestamps for honest Sharpe — performance.full_report
    # uses these to compute calendar-time daily returns when available.
    rpt = full_report(curve, trades, signal_bar_ms=signal_bar_ms)

    gross_total = float(sum(t.get("gross_pnl_pct", t["pnl_pct"]) for t in trades))
    cost_total  = float(sum(t.get("cost_pct", 0.0) for t in trades))
    net_total   = float(sum(t["pnl_pct"] for t in trades))

    result: Dict[str, Any] = {
        "label":             profile.label,
        "signal_tf":         profile.signal_tf,
        "regime_tf":         profile.regime_tf,
        "underlying":        underlying,
        "total_signal_bars": n_signal,
        "total_regime_bars": n_regime,
        "total_trades":      len(trades),
        "win_rate":          round(rpt.win_rate * 100, 1),
        "sharpe":            round(rpt.sharpe, 3),
        "calmar":            round(rpt.calmar, 3),
        "sortino":           round(rpt.sortino, 3),
        "profit_factor":     (None if rpt.profit_factor is None
                              else (float("inf") if rpt.profit_factor == float("inf")
                                    else round(rpt.profit_factor, 3))),
        "max_drawdown":      round(rpt.max_drawdown * 100, 2),
        "avg_rr":            round(rpt.avg_rr, 3),
        "equity_curve":      [round(v, 6) for v in curve.tolist()],
        "regime_breakdown":  rpt.regime_breakdown,
        "gross_pnl_pct_sum": round(gross_total, 6),
        "cost_pct_sum":      round(cost_total, 6),
        "net_pnl_pct_sum":   round(net_total, 6),
    }
    for k, (lbl, lwr, swr) in enumerate(fwd_win_rates):
        result[f"fwd{k+1}_label"]          = lbl
        result[f"fwd{k+1}_long_win_rate"]  = lwr
        result[f"fwd{k+1}_short_win_rate"] = swr
    if emit_events and ledger is not None:
        result["events"] = ledger.events_as_dicts()
    return result


def run_mtf_backtest(
    underlying: str,
    candles_15m: List[Candle],
    candles_1h:  List[Candle],
    candles_4h:  List[Candle],
    c_1d:        Optional[List[Candle]] = None,
    profiles:    Optional[List[str]]    = None,
    score_min:   float = 0.0,
    *,
    candles_5m:  Optional[List[Candle]] = None,
    candles_30m: Optional[List[Candle]] = None,
    candles_2h:  Optional[List[Candle]] = None,
    structure_type: str = "futures",
    leverage: float = 1.0,
    oi: Optional[float] = None,
    funding_8h_pct: float = 0.0,
    option_spread_pct: Optional[float] = None,
    apply_slippage: bool = True,
    emit_events: bool = False,
    exit_atr_tf: Optional[Literal["signal", "regime"]] = None,
    payoff_mode: Optional[Literal["fixed_2r", "chandelier_trail"]] = None,
    # Tier A #9 — same shape as `_replay_profile`. Applied to every profile.
    micro_snapshot_provider: Optional[MicroSnapshotProvider] = None,
    ivr_history_provider:    Optional[IvrHistoryProvider]    = None,
    micro_veto_config:       Optional[_micro_veto.MicroVetoConfig]  = None,
    vov_thresholds:          Optional[_vov_gate.VolOfVolThresholds] = None,
    # v4 BTC tune — per-profile field overrides applied via dataclasses.replace
    # without mutating PROFILES. Shape: {profile_key: {"v4_trail_mult": 2.5, ...}}.
    # Used by the BTC scalping search driver; ignored when None.
    profile_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    # v4 BTC tune — direction filter threaded into every profile's entry gate.
    # None / "both" = trade both sides (back-compat); "long_only" / "short_only"
    # disables the other side. Applied uniformly across profiles in this call.
    direction_filter: Optional[Literal["long_only", "short_only", "both"]] = None,
    # v4 Phase 1 — Mean-reversion track config. Passed through to
    # vectorize_replay (currently a neutral stub after the strategy reset).
    # Defaults preserve all current call-sites.
    mr_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Run all (or selected) TF profiles and return a comparison dict.
    Keys: profile key -> result dict (metrics + equity_curve).

    New cost parameters (Phase 1) thread through to `_replay_profile`:
      - leverage, oi      : drive tiered slippage model
      - funding_8h_pct    : signed funding rate; cost = direction * rate * hold/8
      - option_spread_pct : optional round-trip bid/ask half-spread cost (None=ignore)
      - apply_slippage    : disable to inspect zero-slippage variants
      - emit_events       : opt-in research event ledger (default off → unchanged shape)
      - exit_atr_tf       : Issue 6 — when set, overrides the per-profile default
                            ("regime" preserves legacy; "signal" tightens stops to
                            the entry timeframe).
      - payoff_mode       : Issue 7 — when set, overrides the per-profile default
                            ("fixed_2r" preserves legacy 2R/-1R; "chandelier_trail"
                            takes 50% at +1R, breakeven, then trails the remainder).
    """
    _candle_map: Dict[str, Tuple[List[Candle], List[Candle]]] = {
        "scalping_5m":  (candles_5m or [],  candles_15m),
        "scalping_15m": (candles_15m,        candles_1h),
        "scalping_30m": (candles_30m or [],  candles_2h or []),
        "intraday_1h":  (candles_1h,         candles_4h),
        "intraday_4h":  (candles_4h,         c_1d or []),
    }
    run_keys = profiles if profiles is not None else list(PROFILES.keys())
    results: Dict[str, Dict[str, Any]] = {}

    # v4 BTC tune — derive the asset key from `underlying` so PROFILES_BY_ASSET
    # can shadow specific (asset, profile_key) pairs. Strips the quote suffix
    # so "BTCUSD" and "BTC" both resolve to "BTC". Non-BTC assets see no entry
    # and fall through to PROFILES unchanged.
    asset_key = (underlying or "").replace("USDT", "").replace("USD", "").upper()

    for key in run_keys:
        if key not in PROFILES:
            continue
        # Per-asset shadow lookup; fall back to PROFILES when absent.
        profile = PROFILES_BY_ASSET.get(asset_key, {}).get(key) or PROFILES[key]
        # Apply caller-side overrides without mutating the module-level singleton.
        overrides: Dict[str, Any] = {}
        if exit_atr_tf is not None:
            overrides["exit_atr_tf"] = exit_atr_tf
        if payoff_mode is not None:
            overrides["payoff_mode"] = payoff_mode
        if profile_overrides and key in profile_overrides:
            # v4 BTC tune — merge search-driver overrides last so they win.
            overrides.update(profile_overrides[key])
        if overrides:
            from dataclasses import replace as _dc_replace
            profile = _dc_replace(profile, **overrides)
        sig_candles, reg_candles = _candle_map.get(key, ([], []))
        if not sig_candles:
            log.warning("Profile %s: empty signal candles for %s — skipping", key, underlying)
        if not reg_candles:
            log.warning("Profile %s: empty regime candles for %s — skipping", key, underlying)
        # v4 Phase 1 — resolve track routing here so a single source of truth
        # picks the active tracks. The router handles asset/profile lookup +
        # YAML config + programmatic overrides.
        try:
            from app.engines.directional.track_selector import select_tracks as _select
            tracks_for = _select(underlying, key)
        except Exception:
            tracks_for = ["trend_following"]
        # v4 Phase 1 — if MR is active and the caller didn't pass an explicit
        # mr_config, look up the persisted per-(asset, profile) tuning.
        effective_mr_config = mr_config
        if effective_mr_config is None and "mean_reversion" in tracks_for:
            effective_mr_config = resolve_mr_config(underlying, key)
        results[key] = _replay_profile(
            profile, sig_candles, reg_candles,
            score_min=score_min, underlying=underlying,
            structure_type=structure_type,
            leverage=leverage, oi=oi,
            funding_8h_pct=funding_8h_pct,
            option_spread_pct=option_spread_pct,
            apply_slippage=apply_slippage,
            emit_events=emit_events,
            micro_snapshot_provider=micro_snapshot_provider,
            ivr_history_provider=ivr_history_provider,
            micro_veto_config=micro_veto_config,
            vov_thresholds=vov_thresholds,
            direction_filter=direction_filter,
            profile_key=key,
            active_tracks=tracks_for,
            mr_config=effective_mr_config,
        )

    return results
