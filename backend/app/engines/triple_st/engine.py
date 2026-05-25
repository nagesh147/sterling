"""Per-bar decision engine for the Triple SuperTrend strategy.

Pure, side-effect-free functions over a precomputed `Features` bundle, plus a
stateful `ProtectionState` for live capital protection and dynamic mode
switching. The same primitives power both the live `/evaluate` endpoint and the
historical `backtest` replay, so what you backtest is exactly what trades.

Pipeline (mirrors the PineScript spec):
    regime → triple-ST consensus → lean quality score → confluence filters →
    adaptive sizing → trade plan.  Exit logic lives in `exits` below and is
    consumed by the backtester.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from app.engines.triple_st.config import (
    AssetClass,
    AssetParams,
    HTFSource,
    ModeParams,
    StrategyMode,
    TripleSTConfig,
    ASSET_TABLE,
    MODE_TABLE,
    classify_asset,
)
from app.engines.triple_st.features import Features, HTFContext, BTCContext


CHOP_TREND = 38.2
CHOP_RANGE = 61.8


# ─────────────────────────────────────────────────────────────────────────────
# Regime
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RegimeArrays:
    is_compressed: np.ndarray
    is_high_vol: np.ndarray
    is_trending: np.ndarray
    is_choppy: np.ndarray
    post_squeeze: np.ndarray
    bb_ratio: np.ndarray


def build_regime(feat: Features, asset: AssetParams) -> RegimeArrays:
    """Compute the per-bar market-regime flags once for the whole series."""
    n = feat.n
    bb_ratio = np.ones(n)
    nz = feat.bb_width_sma50 > 0
    bb_ratio[nz] = feat.bb_width[nz] / feat.bb_width_sma50[nz]

    is_compressed = bb_ratio < asset.squeeze_threshold
    is_high_vol = (feat.atr50 > 0) & (feat.atr14 > 1.3 * feat.atr50)
    is_trending = (feat.adx >= asset.min_adx) & (feat.chop < CHOP_RANGE)
    is_choppy = (feat.chop > CHOP_RANGE) | (feat.adx < asset.min_adx * 0.6)

    # post_squeeze: the first 5 bars after a compression ends.
    post_squeeze = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if is_compressed[i - 1] and not is_compressed[i]:
            post_squeeze[i : min(n, i + 5)] = True

    return RegimeArrays(
        is_compressed=is_compressed,
        is_high_vol=is_high_vol,
        is_trending=is_trending,
        is_choppy=is_choppy,
        post_squeeze=post_squeeze,
        bb_ratio=bb_ratio,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Triple SuperTrend consensus
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ConsensusArrays:
    direction: np.ndarray       # +1 / -1 / 0  (≥ min_confirm STs agree)
    agree_count: np.ndarray     # number of STs agreeing with `direction`
    arrow_long: np.ndarray      # consensus flipped up vs previous bar
    arrow_short: np.ndarray
    st1_flip_long: np.ndarray   # ST1 (fast) flipped bullish this bar
    st1_flip_short: np.ndarray


def build_consensus(feat: Features, min_confirm: int) -> ConsensusArrays:
    n = feat.n
    trends = np.vstack(feat.st_trends)          # shape (3, n)
    longs = np.sum(trends == 1, axis=0)
    shorts = np.sum(trends == -1, axis=0)

    direction = np.zeros(n, dtype=np.int64)
    direction[longs >= min_confirm] = 1
    direction[shorts >= min_confirm] = -1
    agree = np.where(direction == 1, longs, np.where(direction == -1, shorts, 0))

    prev = np.roll(direction, 1)
    prev[0] = 0
    arrow_long = (direction == 1) & (prev != 1)
    arrow_short = (direction == -1) & (prev != -1)

    st1 = feat.st_trends[0]
    st1_prev = np.roll(st1, 1)
    st1_prev[0] = st1[0]
    st1_flip_long = (st1 == 1) & (st1_prev == -1)
    st1_flip_short = (st1 == -1) & (st1_prev == 1)

    return ConsensusArrays(
        direction=direction, agree_count=agree,
        arrow_long=arrow_long, arrow_short=arrow_short,
        st1_flip_long=st1_flip_long, st1_flip_short=st1_flip_short,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Lean Quality Score (0-112)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class QualityBreakdown:
    consensus: float = 0.0
    volume: float = 0.0
    htf: float = 0.0
    regime: float = 0.0
    momentum: float = 0.0
    bonus: float = 0.0

    @property
    def total(self) -> float:
        return max(0.0, min(112.0, self.consensus + self.volume + self.htf
                            + self.regime + self.momentum + self.bonus))


def _htf_alignment(direction: int, htf: Optional[HTFContext], ts_ms: int) -> Tuple[bool, bool]:
    """Return (supertrend_agrees, ema_agrees) for the candidate direction."""
    if htf is None:
        return False, False
    st_ok = htf.st_bias(ts_ms) == direction
    ema_ok = htf.ema_bias(ts_ms) == direction
    return st_ok, ema_ok


def lean_quality_score(
    feat: Features,
    regime: RegimeArrays,
    cons: ConsensusArrays,
    i: int,
    direction: int,
    htf: Optional[HTFContext],
) -> QualityBreakdown:
    qb = QualityBreakdown()
    count = int(cons.agree_count[i]) if cons.direction[i] == direction else 0

    qb.consensus = 30.0 if count == 3 else 18.0 if count == 2 else 0.0

    vr = float(feat.vol_ratio[i])
    qb.volume = 20.0 if vr > 1.8 else 14.0 if vr > 1.3 else 8.0 if vr > 1.0 else 0.0

    st_ok, ema_ok = _htf_alignment(direction, htf, int(feat.ts[i]))
    if st_ok and ema_ok:
        qb.htf = 25.0
    elif st_ok:
        qb.htf = 17.0
    elif ema_ok:
        qb.htf = 12.0

    adx = float(feat.adx[i])
    qb.regime = 15.0 if adx > 28 else 10.0 if adx > 20 else (5.0 if regime.is_high_vol[i] else 0.0)

    macd_accel = (
        feat.macd_hist[i] > feat.macd_hist[i - 1] if direction == 1
        else feat.macd_hist[i] < feat.macd_hist[i - 1]
    ) if i > 0 else False
    ha_confirm = bool(feat.ha_bull[i]) == (direction == 1)
    qb.momentum = 10.0 if (macd_accel and ha_confirm) else 5.0

    qb.bonus = 12.0 if regime.post_squeeze[i] else 0.0
    return qb


# ─────────────────────────────────────────────────────────────────────────────
# Confluence filters (each independently toggleable)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FilterResult:
    name: str
    passed: bool
    detail: str


def evaluate_filters(
    feat: Features,
    regime: RegimeArrays,
    i: int,
    direction: int,
    cfg: TripleSTConfig,
    asset: AssetParams,
    htf: Optional[HTFContext],
    btc: Optional[BTCContext],
) -> List[FilterResult]:
    """Return one `FilterResult` per filter. Disabled filters auto-pass."""
    res: List[FilterResult] = []
    long = direction == 1

    def add(name: str, enabled: bool, ok: bool, detail: str):
        res.append(FilterResult(name, True if not enabled else ok,
                                 "off" if not enabled else detail))

    # Heiken-Ashi body direction
    ha_ok = bool(feat.ha_bull[i]) == long
    add("ha", cfg.use_ha, ha_ok, f"HA {'bull' if feat.ha_bull[i] else 'bear'}")

    # Volume participation
    vr = float(feat.vol_ratio[i])
    add("volume", cfg.use_volume, vr > 1.0, f"vr {vr:.2f}")

    # RSI midline + asset buffer
    r = float(feat.rsi[i])
    rsi_ok = r > 50 + asset.rsi_buffer if long else r < 50 - asset.rsi_buffer
    add("rsi", cfg.use_rsi, rsi_ok, f"rsi {r:.1f}")

    # MACD histogram direction
    mh = float(feat.macd_hist[i])
    macd_ok = mh > 0 if long else mh < 0
    add("macd", cfg.use_macd, macd_ok, f"hist {mh:+.4f}")

    # Higher-timeframe bias
    st_ok, ema_ok = _htf_alignment(direction, htf, int(feat.ts[i]))
    if cfg.htf_source == HTFSource.SUPERTREND:
        htf_ok = st_ok
    elif cfg.htf_source == HTFSource.EMA:
        htf_ok = ema_ok
    else:
        htf_ok = st_ok or ema_ok
    add("htf", cfg.use_htf, htf_ok, f"st={st_ok} ema={ema_ok}")

    # BTC correlation alignment (trade with, not against, BTC's trend)
    btc_trend = btc.trend_at(int(feat.ts[i])) if btc else 0
    btc_ok = btc_trend != (-1 if long else 1)
    add("btc_corr", cfg.use_btc_corr, btc_ok, f"btc {btc_trend:+d}")

    # Volatility-spike guard — block entries during an ATR explosion
    spike = (feat.atr50[i] > 0) and (feat.atr14[i] > 2.5 * feat.atr50[i])
    add("spike_guard", cfg.use_spike_guard, not spike, "spike" if spike else "calm")

    # Market-regime filter — no entries while choppy/compressed
    regime_ok = not (regime.is_choppy[i] or regime.is_compressed[i])
    add("regime", cfg.use_regime_filter, regime_ok,
        "choppy" if regime.is_choppy[i] else "compressed" if regime.is_compressed[i] else "trending")

    # Gap protection — reject if this bar opened with an oversized gap
    gap_pct = 0.0
    if i > 0 and feat.close[i - 1] > 0:
        gap_pct = abs(feat.open[i] - feat.close[i - 1]) / feat.close[i - 1] * 100.0
    add("gap", cfg.use_gap_protection, gap_pct <= asset.gap_threshold_pct, f"gap {gap_pct:.2f}%")

    return res


# ─────────────────────────────────────────────────────────────────────────────
# Adaptive position sizing  →  trade plan
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TradePlan:
    direction: str                 # "long" | "short"
    entry: float
    stop_loss: float
    take_profit: float
    r_distance: float              # price distance of 1R (= stop distance)
    partials: List[Tuple[float, float]]   # (price, fraction)
    size_units: float              # base-asset units
    notional_usd: float
    risk_usd: float
    risk_pct: float                # % of equity at risk
    leverage: float
    rr: float                      # reward:risk of the full TP


def build_trade_plan(
    feat: Features,
    regime: RegimeArrays,
    i: int,
    direction: int,
    cfg: TripleSTConfig,
    asset: AssetParams,
    mode: ModeParams,
    size_mult: float = 1.0,
) -> TradePlan:
    """Adaptive sizing per spec §8 — ATR base, vol-regime, mode/asset, DD, short.

    `size_mult` carries the drawdown-scaling factor from `ProtectionState`.
    """
    entry = float(feat.close[i])
    base_atr = max(float(feat.atr14[i]), float(feat.atr50[i]) * 0.5)
    base_atr = max(base_atr, entry * 1e-4)          # guard against zero-ATR warmup
    stop_dist = asset.sl_mult * base_atr
    tp_dist = asset.tp_mult * base_atr

    long = direction == 1
    stop_loss = entry - stop_dist if long else entry + stop_dist
    take_profit = entry + tp_dist if long else entry - tp_dist

    # Risk budget (% of equity) with all multipliers folded in.
    vol_adj = 0.75 if regime.is_high_vol[i] else 1.0
    short_adj = asset.short_modifier if not long else 1.0
    risk_pct = cfg.risk_percent * mode.risk_mult * vol_adj * short_adj * size_mult
    risk_usd = cfg.account_equity * (risk_pct / 100.0)

    # Risk-first sizing: a full stop = exactly 1R = `risk_usd`. Notional follows
    # from the stop distance; `max_position_pct` is the *margin* budget and the
    # implied leverage is capped. When the leverage cap binds we scale the
    # position down and report the (reduced) actual risk, so R stays honest.
    MAX_LEVERAGE = 25.0
    size_units = risk_usd / stop_dist if stop_dist > 0 else 0.0
    notional = size_units * entry
    margin_budget = max(1.0, cfg.account_equity * (cfg.max_position_pct / 100.0))
    leverage = notional / margin_budget
    if leverage > MAX_LEVERAGE:
        scale = MAX_LEVERAGE / leverage
        size_units *= scale
        notional *= scale
        leverage = MAX_LEVERAGE
        risk_usd = size_units * stop_dist          # actual risk after the cap
        risk_pct = risk_usd / cfg.account_equity * 100.0
    leverage = max(1.0, leverage)

    # Partial-profit ladder: R-multiple → price.
    partials: List[Tuple[float, float]] = []
    for r_mult, frac in mode.partials:
        p = entry + r_mult * stop_dist if long else entry - r_mult * stop_dist
        partials.append((p, frac))

    rr = tp_dist / stop_dist if stop_dist > 0 else 0.0

    return TradePlan(
        direction="long" if long else "short",
        entry=round(entry, 4), stop_loss=round(stop_loss, 4),
        take_profit=round(take_profit, 4), r_distance=round(stop_dist, 6),
        partials=[(round(p, 4), f) for p, f in partials],
        size_units=round(size_units, 6), notional_usd=round(notional, 2),
        risk_usd=round(risk_usd, 2), risk_pct=round(risk_pct, 4),
        leverage=round(leverage, 2), rr=round(rr, 2),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-bar entry evaluation
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class BarSignal:
    i: int
    timestamp_ms: int
    direction: int                  # candidate direction +1/-1/0
    raw_long: bool
    raw_short: bool
    arrow: bool                     # fresh consensus flip in `direction`
    quality: QualityBreakdown
    quality_pass: bool
    filters: List[FilterResult]
    filters_pass: bool
    entry_ok: bool                  # everything aligned → arm an entry
    reason: str


def evaluate_at(
    feat: Features,
    regime: RegimeArrays,
    cons: ConsensusArrays,
    i: int,
    cfg: TripleSTConfig,
    asset: AssetParams,
    mode: ModeParams,
    htf: Optional[HTFContext],
    btc: Optional[BTCContext],
    quality_threshold: Optional[float] = None,
) -> BarSignal:
    """Evaluate entry readiness at bar `i`. Anti-repaint: only consults closed
    bars (≤ i)."""
    ts = int(feat.ts[i])
    direction = int(cons.direction[i])
    # Per-mode confirmation gate: consensus arrays are built at the loosest
    # threshold (2/3) so a single build serves every mode; here we require the
    # active mode's `min_confirm` count to actually arm.
    gated = direction != 0 and int(cons.agree_count[i]) < mode.min_confirm
    if gated:
        direction = 0
    raw_long = direction == 1
    raw_short = direction == -1
    arrow = bool(cons.arrow_long[i]) if raw_long else bool(cons.arrow_short[i]) if raw_short else False

    if direction == 0:
        reason = (f"need {mode.min_confirm}/3 ST agreement (have {int(cons.agree_count[i])})"
                  if gated else "no consensus")
        return BarSignal(i, ts, 0, False, False, False, QualityBreakdown(),
                         False, [], False, False, reason)

    qb = lean_quality_score(feat, regime, cons, i, direction, htf)
    thr = quality_threshold if quality_threshold is not None else cfg.quality_threshold
    quality_pass = (not cfg.use_quality_score) or (qb.total >= thr)

    filters = evaluate_filters(feat, regime, i, direction, cfg, asset, htf, btc)
    filters_pass = all(f.passed for f in filters)

    entry_ok = raw_long or raw_short
    entry_ok = entry_ok and quality_pass and filters_pass

    if not quality_pass:
        reason = f"quality {qb.total:.0f} < {thr:.0f}"
    elif not filters_pass:
        failed = ", ".join(f.name for f in filters if not f.passed)
        reason = f"filtered: {failed}"
    else:
        reason = f"{'long' if raw_long else 'short'} armed (Q={qb.total:.0f})"

    return BarSignal(
        i=i, timestamp_ms=ts, direction=direction,
        raw_long=raw_long, raw_short=raw_short, arrow=arrow,
        quality=qb, quality_pass=quality_pass,
        filters=filters, filters_pass=filters_pass,
        entry_ok=entry_ok, reason=reason,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Capital protection + dynamic mode switching (live + backtest)
# ─────────────────────────────────────────────────────────────────────────────


_MODE_LADDER = [StrategyMode.CONSERVATIVE, StrategyMode.BALANCED, StrategyMode.AGGRESSIVE]


@dataclass
class ProtectionState:
    """Stateful guardrails shared by the live engine and the backtester.

    Tracks equity/drawdown, daily P&L, consecutive losses, a rolling trade
    window (for win-rate-driven regime degradation and dynamic mode switching)
    and a circuit-breaker cooldown.
    """
    cfg: TripleSTConfig
    equity: float
    peak_equity: float = 0.0
    day_key: int = -1
    day_start_equity: float = 0.0
    consecutive_losses: int = 0
    cb_cooldown_until: int = 0          # bar index the circuit breaker clears
    recent_pnl_pct: List[float] = field(default_factory=list)   # rolling 20
    trades_since_switch: int = 0
    current_mode: StrategyMode = StrategyMode.BALANCED
    halt_reason: str = ""

    def __post_init__(self):
        self.peak_equity = self.equity
        self.day_start_equity = self.equity
        self.current_mode = self.cfg.mode

    # ── gating ──────────────────────────────────────────────────────────
    def can_trade(self, bar_index: int, day_key: int, btc_daily_move: float) -> Tuple[bool, str]:
        if day_key != self.day_key:
            self.day_key = day_key
            self.day_start_equity = self.equity

        # Depleted-capital guard — a real account is liquidated once margin is
        # gone; without this, as equity approaches/crosses zero the day-loss %
        # math degrades and the sim death-spirals (e.g. reckless 5%+/trade risk
        # with the quality filter off). Stop once 95% of capital is lost.
        if self.equity <= self.cfg.account_equity * 0.05:
            return False, "account depleted"

        # Daily loss limit (only meaningful while day-start equity is positive)
        if self.day_start_equity > 0:
            day_pnl_pct = (self.equity - self.day_start_equity) / self.day_start_equity * 100.0
            if day_pnl_pct <= -self.cfg.daily_loss_limit:
                return False, f"daily loss limit ({day_pnl_pct:.1f}%)"

        # Circuit breaker cooldown
        if self.cfg.use_circuit_breaker and bar_index < self.cb_cooldown_until:
            return False, "circuit breaker cooldown"

        # Black-swan BTC move
        if self.cfg.use_black_swan and abs(btc_daily_move) >= self.cfg.black_swan_pct:
            return False, f"black swan (BTC {btc_daily_move:+.1f}%)"

        return True, ""

    # ── sizing ──────────────────────────────────────────────────────────
    def size_multiplier(self) -> float:
        """Drawdown scaling — shrink size as portfolio drawdown deepens."""
        dd = (self.peak_equity - self.equity) / max(1.0, self.peak_equity)
        mult = 1.0
        for thr, m in MODE_TABLE[self.current_mode].dd_scaling:
            if dd >= thr:
                mult = m
        return mult

    def effective_quality_threshold(self) -> float:
        """Regime degradation — raise the bar when recent win rate is poor."""
        base = float(self.cfg.quality_threshold)
        if len(self.recent_pnl_pct) >= 10:
            wins = sum(1 for p in self.recent_pnl_pct if p > 0)
            wr = wins / len(self.recent_pnl_pct)
            if wr < 0.42:
                return min(95.0, base + 10.0)
        return base

    # ── trade accounting ────────────────────────────────────────────────
    def register_trade(self, pnl_usd: float, pnl_pct: float, bar_index: int):
        self.equity += pnl_usd
        self.peak_equity = max(self.peak_equity, self.equity)
        self.recent_pnl_pct.append(pnl_pct)
        if len(self.recent_pnl_pct) > 20:
            self.recent_pnl_pct.pop(0)

        if pnl_usd < 0:
            self.consecutive_losses += 1
            if self.cfg.use_circuit_breaker and self.consecutive_losses >= self.cfg.consecutive_loss_limit:
                self.cb_cooldown_until = bar_index + 12   # ~half-day on 1H
                self.consecutive_losses = 0
        else:
            self.consecutive_losses = 0

        self.trades_since_switch += 1
        if self.cfg.use_dynamic_mode:
            self._maybe_switch_mode()

    def _maybe_switch_mode(self):
        """Step-through mode switching on a rolling 20-trade window.

        Upgrade aggressiveness on strong performance, downgrade on weak — one
        ladder step at a time, no more often than every 5 trades. Momentum is a
        side-mode and is left untouched by the auto-switcher.
        """
        if self.current_mode == StrategyMode.MOMENTUM:
            return
        if self.trades_since_switch < 5 or len(self.recent_pnl_pct) < 10:
            return

        wins = sum(1 for p in self.recent_pnl_pct if p > 0)
        wr = wins / len(self.recent_pnl_pct)
        expectancy = sum(self.recent_pnl_pct) / len(self.recent_pnl_pct)
        idx = _MODE_LADDER.index(self.current_mode)

        if wr >= 0.55 and expectancy > 0 and idx < len(_MODE_LADDER) - 1:
            self.current_mode = _MODE_LADDER[idx + 1]
            self.trades_since_switch = 0
        elif (wr < 0.40 or expectancy < 0) and idx > 0:
            self.current_mode = _MODE_LADDER[idx - 1]
            self.trades_since_switch = 0


# ─────────────────────────────────────────────────────────────────────────────
# Resolution helpers
# ─────────────────────────────────────────────────────────────────────────────


def resolve_asset(cfg: TripleSTConfig, feat: Features, i: int) -> Tuple[AssetClass, AssetParams]:
    """Resolve the effective asset class (honouring auto-detect) at bar i."""
    if cfg.asset_type == AssetClass.AUTO:
        ac = classify_asset(float(feat.atr_percent[i]) if feat.n else 2.0)
    else:
        ac = cfg.asset_type
    return ac, ASSET_TABLE[ac]
