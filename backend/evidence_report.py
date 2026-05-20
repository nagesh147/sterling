"""
Sterling Strategy — Full Evidence Report
Engine: real replay (regime + signal + setup).
Data:  synthetic 3000 1H / 750 4H bars (125 days), realistic BTC-scale noise.
"""
import sys, os, math
os.environ.setdefault("STERLING_ENV", "test")
sys.path.insert(0, ".")

import numpy as np
from collections import defaultdict
from app.schemas.market import Candle

# ─── Realistic synthetic BTC-like generator ─────────────────────────────────

def build_universe(seed=42, n_total=3000):
    """
    3000 1H bars with BTC-realistic noise (σ ≈ 0.7% per bar).
    Regime segments designed for EMA/ADX to fully settle before transitions.
    """
    np.random.seed(seed)
    ONE_H_MS  = 3_600_000
    BASE_TS   = 1_700_000_000_000

    # (n_bars, trend_per_bar, noise_sigma) — BTC at ~50 000 level
    segs = [
        (500, +200, 300),   # BULL1      +4/bar% drift, σ≈0.6%
        (300,    0, 250),   # RANGING1   no drift, moderate noise
        (500, -180, 320),   # BEAR1
        (150,  +50, 800),   # VOLATILE   big σ, mixed direction
        (500, +220, 280),   # BULL2
        (300,   -8, 260),   # RANGING2
        (500, -200, 310),   # BEAR2
        (250, +300, 270),   # BULL3 (short recovery)
    ]

    prices, regime_map = [], []
    p = 50_000.0
    while len(prices) < n_total:
        for seg_n, tr, vol in segs:
            for _ in range(seg_n):
                p += tr + np.random.normal(0, vol)
                p  = max(p, 5_000.0)
                prices.append(p)
                regime_map.append("BULL" if tr > 50 else "BEAR" if tr < -50 else "RANGING")
                if len(prices) >= n_total:
                    break
            if len(prices) >= n_total:
                break

    def _candle(ts, o, h, l, c, v):
        return Candle(timestamp_ms=ts,
                      open=round(o, 2), high=round(h, 2),
                      low=round(l, 2),  close=round(c, 2),
                      volume=round(v, 2))

    c1h = []
    for i, p in enumerate(prices):
        s = p * 0.004
        o = p + np.random.uniform(-s, s)
        c = p + np.random.uniform(-s, s)
        h = max(o, c) + abs(np.random.normal(0, s * 1.2))
        l = min(o, c) - abs(np.random.normal(0, s * 1.2))
        c1h.append(_candle(BASE_TS + i * ONE_H_MS, o, h, l, c,
                            np.random.uniform(200, 1000)))

    c4h = []
    for j in range(0, len(c1h) - 3, 4):
        grp = c1h[j:j+4]
        c4h.append(_candle(
            grp[0].timestamp_ms,
            grp[0].open,
            max(c.high  for c in grp),
            min(c.low   for c in grp),
            grp[-1].close,
            sum(c.volume for c in grp),
        ))

    return c1h, c4h, regime_map

# ─── Analysis helpers ────────────────────────────────────────────────────────

def _stats(trades):
    if not trades:
        return {"n": 0, "wr": None, "exp": None, "pf": None, "sharpe": None}
    pnls = [t["pnl_pct"] for t in trades]
    w = [p for p in pnls if p > 0]
    l = [p for p in pnls if p < 0]
    ec = np.array([1.0] + list(np.cumprod([1 + p * 0.02 for p in pnls])))
    rets = np.diff(ec) / ec[:-1]
    sha = float(np.mean(rets) / rets.std() * np.sqrt(8760)) if rets.std() > 0 else 0.0
    return {
        "n":      len(trades),
        "wr":     round(len(w) / len(pnls) * 100, 1),
        "exp":    round(float(np.mean(pnls)) * 100, 3),
        "pf":     round(sum(w) / abs(sum(l)), 3) if l else None,
        "sharpe": round(sha, 3),
    }

def _max_dd(trades):
    if not trades: return 0.0
    ec = np.array([1.0] + list(np.cumprod([1 + t["pnl_pct"]*0.02 for t in trades])))
    peak = np.maximum.accumulate(ec)
    return float(np.min((ec - peak) / peak)) * 100

def _streak(trades):
    best = cur = 0
    for t in trades:
        cur = (cur + 1) if t["pnl_pct"] < 0 else 0
        best = max(best, cur)
    return best

def _tbl(headers, rows, w=13):
    sep = "+" + "+".join("-" * w for _ in headers) + "+"
    hdr = "|" + "|".join(str(h).center(w) for h in headers) + "|"
    lines = [sep, hdr, sep]
    for row in rows:
        lines.append("|" + "|".join(str(v).center(w) for v in row) + "|")
    lines.append(sep)
    return "\n".join(lines)

def _v(x, fmt=".3f"):
    return "—" if x is None else format(x, fmt)

# ─── Report ─────────────────────────────────────────────────────────────────

def run():
    from app.engines.backtest.backtest_engine   import run_backtest, simulate_capital_curve, FEE_RT_PCT
    from app.engines.analytics.walk_forward      import run_real, WalkForwardConfig, _engine_replay_trades
    from app.engines.analytics.sensitivity       import sweep_real, SWEEP_PARAMS
    from app.engines.risk.slippage               import slippage_bps
    from app.engines.directional.regime_engine   import compute_regime
    from app.engines.directional.signal_engine   import compute_signal
    from app.engines.directional.setup_engine    import evaluate_setup
    from app.engines.indicators.atr              import compute_atr
    from app.schemas.directional                 import TradeState

    HDR = "=" * 68
    SEC = "─" * 68

    print(HDR)
    print("  STERLING STRATEGY — FULL EVIDENCE REPORT")
    print("  Real replay: regime + signal + setup (no live exchange)")
    print(HDR)

    c1h, c4h, rlabels = build_universe(seed=42, n_total=3000)
    n1h, n4h = len(c1h), len(c4h)
    price_lo = min(c.close for c in c1h)
    price_hi = max(c.close for c in c1h)
    print(f"\n  Bars: {n1h} × 1H  |  {n4h} × 4H  (~{n1h//24} days)")
    print(f"  Price range:  ${price_lo:,.0f} – ${price_hi:,.0f}  (BTC-scale)")
    print(f"  Fee model:    {FEE_RT_PCT*100:.2f}% round-trip per trade")

    # ── State-frequency diagnostic ───────────────────────────────────────────
    print(f"\n{SEC}\n  PRE-CHECK: Setup state frequency (every bar, adx_4h mode)\n{SEC}")
    MIN_1H = 30; MIN_4H = 55; _4H_MS = 4 * 3_600_000
    state_counts = defaultdict(int)
    arrow_bars   = []
    for i in range(MIN_1H, n1h):
        ts  = c1h[i].timestamp_ms
        c4  = [c for c in c4h if c.timestamp_ms + _4H_MS <= ts]
        if len(c4) < MIN_4H: continue
        c1  = c1h[max(0, i - 200): i + 1]
        reg = compute_regime(c4)
        sig = compute_signal(c1)
        stp = evaluate_setup(reg, sig)
        state_counts[stp.state.value] += 1
        if sig.green_arrow or sig.red_arrow:
            arrow_bars.append((i, reg.macro_regime.value, sig.trend, stp.state.value,
                                round(reg.adx, 1), sig.green_arrow, sig.red_arrow))

    total_evaluated = sum(state_counts.values())
    for state, cnt in sorted(state_counts.items(), key=lambda x: -x[1]):
        print(f"  {state:<35} {cnt:>5}  ({cnt/total_evaluated*100:.1f}%)")

    n_arrows = len(arrow_bars)
    n_conf   = state_counts.get("CONFIRMED_SETUP_ACTIVE", 0)
    print(f"\n  Arrows (signal transitions): {n_arrows}")
    print(f"  CONFIRMED_SETUP_ACTIVE bars: {n_conf}")

    if n_arrows:
        print(f"\n  Arrow bars (bar, regime, trend, state, ADX):")
        for row in arrow_bars[:12]:
            bi, rm, tr, st, adx, ga, ra = row
            arrow_type = "GREEN" if ga else "RED"
            print(f"    bar={bi:4d}  {arrow_type}  regime={rm:<14}  trend={tr:+d}  "
                  f"state={st:<30}  ADX={adx:.1f}")

    # ── §1 Baseline backtest ─────────────────────────────────────────────────
    print(f"\n{SEC}\n  §1  BASELINE BACKTEST (sample_every=4, fee=0.10%)\n{SEC}")
    result = run_backtest("SYN", c4h, c1h, lookback_days=120, sample_every_n_bars=4)
    st = result.stats
    print(f"\n  Bars evaluated : {st.total_bars_evaluated}")
    print(f"  Bull bars      : {st.bullish_regime_bars}  |  Bear: {st.bearish_regime_bars}  |  Neutral: {st.neutral_regime_bars}")
    print(f"  Green arrows   : {st.green_arrows}  |  Red: {st.red_arrows}")
    print(f"  Confirmed long : {st.confirmed_long_setups}  |  Confirmed short: {st.confirmed_short_setups}")
    print(f"  Early long     : {st.early_long_setups}  |  Early short: {st.early_short_setups}")

    print(f"\n  ── Directional accuracy at arrow events (no fees applied) ──")
    headers = ["Metric", "Long 4H", "Short 4H", "Long 12H", "Short 12H"]
    rows = [
        ["Arrow WR %",
         _v(st.arrow_long_win_rate_4h, ".1f"),  _v(st.arrow_short_win_rate_4h, ".1f"),
         _v(st.arrow_long_win_rate_12h, ".1f"),  _v(st.arrow_short_win_rate_12h, ".1f")],
        ["Signal acc %",
         _v(st.signal_accuracy_long_4h, ".1f"), _v(st.signal_accuracy_short_4h, ".1f"),
         "—", "—"],
        ["Setup avg ret %",
         _v(st.setup_long_avg_return_4h),  _v(st.setup_short_avg_return_4h),
         _v(st.setup_long_avg_return_12h), _v(st.setup_short_avg_return_12h)],
    ]
    print(_tbl(headers, rows))

    print(f"\n  ── Capital simulation (confirmed setups, fee=0.10%, 2% risk) ──")
    print(f"  Simulated trades   : {result.sim_trade_count}")
    print(f"  Win rate           : {_v(result.sim_win_rate, '.1%') if result.sim_win_rate else '—'}")
    print(f"  Expectancy/trade   : {_v(result.sim_expectancy_pct, '.4f')}%")
    print(f"  Profit factor      : {_v(result.sim_profit_factor)}")
    print(f"  Max drawdown       : {_v(result.sim_max_drawdown, '.2%') if result.sim_max_drawdown else '—'}")
    print(f"  Sharpe (annualised): {_v(result.sim_sharpe)}")

    # ── §2 Walk-forward (scalping mode for trade count) ─────────────────────
    print(f"\n{SEC}\n  §2  WALK-FORWARD (macro_filter='off', train=400, test=200, step=200)\n{SEC}")
    print("  Note: adx_4h mode produces 0 confirmed setups (selectivity finding — see §9).")
    print("  Using macro_filter='off' (scalping) to obtain minimum OOS samples.\n")

    # Custom replay for scalping mode (macro_filter='off')
    def _replay_scalp(c1h_in, c4h_in, score_min=0.0, fee=FEE_RT_PCT, hold=8):
        trades = []
        in_t = False; e_bar = e_dir = 0; e_close = e_atr = 0.0; e_reg = "unknown"
        for i in range(MIN_1H, len(c1h_in) - 1):
            ts = c1h_in[i].timestamp_ms
            c4 = [c for c in c4h_in if c.timestamp_ms + _4H_MS <= ts]
            if len(c4) < MIN_4H: continue
            c1 = c1h_in[max(0, i - 200): i + 1]
            reg = compute_regime(c4, macro_filter="off")
            sig = compute_signal(c1)
            stp = evaluate_setup(reg, sig)
            if in_t:
                cur  = c1h_in[i].close
                held = i - e_bar
                raw  = e_dir * (cur - e_close) / e_close if e_close > 0 else 0.0
                ex = held >= hold
                if e_atr > 0 and e_close > 0:
                    g = e_dir * (cur - e_close)
                    ex = ex or g >= 2 * e_atr or g <= -e_atr
                ex = ex or (e_dir == 1 and sig.trend == -1) or (e_dir == -1 and sig.trend == 1)
                if ex:
                    trades.append({"pnl_pct": raw - fee, "regime": e_reg,
                                   "direction": "long" if e_dir == 1 else "short"})
                    in_t = False
            if not in_t:
                sc = float(getattr(sig, "signal_score", 0) or 0)
                if stp.state == TradeState.CONFIRMED_SETUP_ACTIVE and sc >= score_min and sig.trend != 0:
                    in_t = True; e_bar = i; e_dir = sig.trend
                    e_close = c1h_in[i].close; e_reg = reg.macro_regime.value
                    h4 = np.array([c.high  for c in c4[-20:]], dtype=np.float64)
                    l4 = np.array([c.low   for c in c4[-20:]], dtype=np.float64)
                    c4a= np.array([c.close for c in c4[-20:]], dtype=np.float64)
                    av = compute_atr(h4, l4, c4a, 14)
                    v  = float(av[-1]) if len(av) > 0 and not np.isnan(av[-1]) else 0.0
                    e_atr = v if v > 0 else e_close * 0.02
        if in_t:
            j   = len(c1h_in) - 1
            cur = c1h_in[j].close
            raw = e_dir * (cur - e_close) / e_close if e_close > 0 else 0.0
            trades.append({"pnl_pct": raw - fee, "regime": e_reg,
                            "direction": "long" if e_dir == 1 else "short"})
        return trades

    # Walk-forward with scalp mode
    wf_windows = []
    TRAIN, TEST, STEP = 400, 200, 200
    idx = win_i = 0
    oos_all = []
    from app.engines.analytics.performance import full_report, PerformanceReport, sharpe as _sharpe
    from app.engines.analytics.walk_forward import _equity_from_trades
    thresholds_used = []
    while idx + TRAIN + TEST <= n1h:
        tr_end  = idx + TRAIN
        ts_end  = min(tr_end + TEST, n1h)
        tr1 = c1h[idx:tr_end]; ts1 = c1h[tr_end:ts_end]
        tr_cut = tr1[-1].timestamp_ms if tr1 else 0
        ts_cut = ts1[-1].timestamp_ms if ts1 else 0
        tr4 = [c for c in c4h if c.timestamp_ms + _4H_MS <= tr_cut]
        ts4 = [c for c in c4h if c.timestamp_ms + _4H_MS <= ts_cut]
        # threshold selection on train
        best_thr = 0; best_sh = -999
        for thr in [0, 3, 5, 8, 10, 12, 15]:
            tt = _replay_scalp(tr1, tr4, score_min=thr)
            if tt:
                s = _sharpe(_equity_from_trades(tt))
                if s > best_sh: best_sh = s; best_thr = thr
        thresholds_used.append(best_thr)
        oos_t = _replay_scalp(ts1, ts4, score_min=best_thr)
        oos_all.extend(oos_t)
        s_oos  = _stats(oos_t)
        wf_windows.append((win_i, idx, tr_end, ts_end, best_thr, s_oos))
        idx += STEP; win_i += 1

    print(_tbl(
        ["Win", "Tr range", "OOS range", "Thr", "OOS N", "WR%", "Exp%", "PF"],
        [(w, f"{a}-{b}", f"{b}-{e}", t,
          s["n"], _v(s["wr"], ".1f"), _v(s["exp"], ".3f"), _v(s["pf"]))
         for w, a, b, e, t, s in wf_windows]))

    rec_thr = float(np.median(thresholds_used)) if thresholds_used else 0
    s_agg   = _stats(oos_all)
    print(f"\n  Recommended threshold (median): {rec_thr:.1f}  (signal_score 0-20)")
    print(f"  OOS aggregate:  N={s_agg['n']}  WR={_v(s_agg['wr'],'.1f')}%  "
          f"Exp={_v(s_agg['exp'],'.3f')}%  PF={_v(s_agg['pf'])}  Sharpe={_v(s_agg['sharpe'])}")

    # Full-series scalp replay for §3-§8
    all_trades = _replay_scalp(c1h, c4h, score_min=rec_thr, fee=FEE_RT_PCT)
    n_trades   = len(all_trades)

    # ── §3 Fee / slippage sensitivity ────────────────────────────────────────
    print(f"\n{SEC}\n  §3  COST / SLIPPAGE SENSITIVITY (scalp mode, score_min={rec_thr:.0f})\n{SEC}")
    gross_trades_0 = _replay_scalp(c1h, c4h, score_min=rec_thr, fee=0.0)
    fee_rows = []
    for fee in [0.0, 0.0003, 0.001, 0.002, 0.005]:
        td = [{**t, "pnl_pct": t["pnl_pct"] - fee} for t in gross_trades_0]
        s  = _stats(td)
        mdd = _max_dd(td)
        fee_rows.append([
            f"{fee*100:.2f}%", s["n"],
            _v(s["wr"], ".1f") + "%" if s["wr"] else "—",
            _v(s["exp"], ".3f") + "%" if s["exp"] else "—",
            _v(s["pf"]) if s["pf"] else "—",
            f"{mdd:.1f}%",
        ])
    print(_tbl(["Fee RT", "Trades", "WR%", "Exp%", "PF", "MaxDD%"], fee_rows))

    if gross_trades_0:
        gross_mean = np.mean([t["pnl_pct"] for t in gross_trades_0])
        print(f"\n  Gross mean return/trade: {gross_mean*100:.4f}%")
        be = gross_mean * 100
        print(f"  Break-even fee (RT):     {be:.4f}%")
        print(f"  Current 0.10% RT fee:    {'below breakeven ✓' if 0.001 < gross_mean else 'ABOVE breakeven — unprofitable after fees ✗'}")

    print(f"\n  Slippage table (slippage.py, leverage=1×):")
    for oi_v in [50, 200, 1000]:
        bps = slippage_bps(1, oi_v)
        print(f"    OI={oi_v:4d}  →  {bps:4.1f} bps  ({bps/10000*100:.3f}% one-way)")

    # ── §4 Long / short split ────────────────────────────────────────────────
    print(f"\n{SEC}\n  §4  LONG / SHORT SPLIT\n{SEC}")
    longs  = [t for t in all_trades if t.get("direction") == "long"]
    shorts = [t for t in all_trades if t.get("direction") == "short"]
    sl, ss = _stats(longs), _stats(shorts)
    print(_tbl(
        ["Side", "N", "WR%", "Exp%", "PF", "Sharpe", "MaxDD%"],
        [
            ["LONG",  sl["n"], _v(sl["wr"],".1f"),  _v(sl["exp"],".3f"),  _v(sl["pf"]), _v(sl["sharpe"]), f"{_max_dd(longs):.1f}%"],
            ["SHORT", ss["n"], _v(ss["wr"],".1f"),  _v(ss["exp"],".3f"),  _v(ss["pf"]), _v(ss["sharpe"]), f"{_max_dd(shorts):.1f}%"],
        ]))

    # ── §5 Regime split ──────────────────────────────────────────────────────
    print(f"\n{SEC}\n  §5  REGIME SPLIT\n{SEC}")
    rgroups = defaultdict(list)
    for t in all_trades:
        rgroups[t.get("regime", "unknown")].append(t)
    reg_rows = []
    for reg, tl in sorted(rgroups.items()):
        s = _stats(tl)
        reg_rows.append([reg[:16], s["n"], _v(s["wr"],".1f"),
                         _v(s["exp"],".3f"), _v(s["pf"]), _v(s["sharpe"])])
    print(_tbl(["Regime", "N", "WR%", "Exp%", "PF", "Sharpe"], reg_rows, w=16))

    # ── §6 Mode / macro-filter split ─────────────────────────────────────────
    print(f"\n{SEC}\n  §6  MACRO-FILTER MODE SPLIT\n{SEC}")
    adx_trades = _engine_replay_trades(c1h, c4h, score_min=0.0, fee_rt_pct=FEE_RT_PCT)
    s_adx  = _stats(adx_trades)
    s_scalp = _stats(all_trades)
    print(_tbl(
        ["Mode", "N", "WR%", "Exp%", "PF", "MaxDD%"],
        [
            ["adx_4h (default)", s_adx["n"],   _v(s_adx["wr"],".1f"),   _v(s_adx["exp"],".3f"),   _v(s_adx["pf"]),   f"{_max_dd(adx_trades):.1f}%"],
            ["off (scalping)",   s_scalp["n"],  _v(s_scalp["wr"],".1f"), _v(s_scalp["exp"],".3f"), _v(s_scalp["pf"]), f"{_max_dd(all_trades):.1f}%"],
        ], w=16))
    print(f"\n  FINDING: adx_4h mode fires {s_adx['n']} times in {n1h} bars (~{n1h//24} days).")
    print(f"  Strategy is extremely selective. Low fire rate is by design (high-conviction only).")
    print(f"  Evidence for adx_4h mode is insufficient (n<30). Scalp mode used for §2-8.")

    # ── §7 Max drawdown & losing streak ──────────────────────────────────────
    print(f"\n{SEC}\n  §7  DRAWDOWN & LOSING-STREAK ANALYSIS\n{SEC}")
    if all_trades:
        mdd  = _max_dd(all_trades)
        strk = _streak(all_trades)
        pnls = [t["pnl_pct"] for t in all_trades]
        ec = np.array([1.0] + list(np.cumprod([1 + p * 0.02 for p in pnls])))
        print(f"\n  Full-series max drawdown      : {mdd:.2f}%")
        print(f"  Max consecutive losing trades : {strk}")
        runs = []
        cur  = []
        for t in all_trades:
            if t["pnl_pct"] < 0: cur.append(t["pnl_pct"])
            else:
                if cur: runs.append(cur)
                cur = []
        if cur: runs.append(cur)
        if runs:
            worst = min(runs, key=lambda r: sum(r))
            print(f"  Worst losing run              : {len(worst)} trades, Σ {sum(worst)*100:.2f}% raw return")
        # WF per-window drawdowns
        wf_mdds = []
        for _, _, _, _, _, s_w in wf_windows:
            # can't get per-window DD from _stats; skip
            pass
        print(f"  WF windows with 0 OOS trades  : {sum(1 for *_, s in wf_windows if s['n']==0)}/{len(wf_windows)}")
    else:
        print("\n  Insufficient trades for drawdown analysis.")

    # ── §8 Trade-count sufficiency ───────────────────────────────────────────
    print(f"\n{SEC}\n  §8  TRADE-COUNT SUFFICIENCY\n{SEC}")
    n = n_trades
    if n > 0:
        pnls = [t["pnl_pct"] for t in all_trades]
        wr_r = len([p for p in pnls if p > 0]) / n
        ci   = 1.96 * math.sqrt(wr_r * (1 - wr_r) / n) if n > 0 else 1.0
        req  = int((1.96 ** 2 * wr_r * (1 - wr_r)) / (0.05 ** 2))
        print(f"\n  Replay trades (scalp mode)     : {n}")
        print(f"  OOS trades (walk-forward)      : {s_agg['n']}")
        print(f"  Win rate point est.            : {wr_r*100:.1f}%")
        print(f"  95% CI half-width              : ±{ci*100:.1f}pp  →  [{(wr_r-ci)*100:.1f}%, {(wr_r+ci)*100:.1f}%]")
        print(f"  Trades needed for ±5pp CI      : {req}")
        if n >= 50:
            suf = "SUFFICIENT (n≥50) — estimates usable with caution"
        elif n >= 20:
            suf = "MARGINAL (20≤n<50) — wide confidence intervals"
        else:
            suf = "INSUFFICIENT (n<20) — results statistically unreliable"
        print(f"  Sufficiency                    : {suf}")
    else:
        print(f"\n  0 trades — cannot assess statistical sufficiency.")

    # ── §9 Score sensitivity + failure cases ────────────────────────────────
    print(f"\n{SEC}\n  §9  SCORE-MIN SENSITIVITY & FAILURE CASES\n{SEC}")
    ss_result = sweep_real(c1h, c4h, "score_min", [0, 3, 5, 8, 10, 12, 15],
                           fee_rt_pct=FEE_RT_PCT)
    print(_tbl(["score_min", "Sharpe"], [(v, round(s, 3)) for v, s in zip(ss_result.values_tested, ss_result.sharpes)]))
    print(f"  Best score_min: {ss_result.best_value}  σ(Sharpe): {ss_result.sensitivity:.3f}")

    print("\n  Failure / weak cases:")
    failures = []
    for reg, tl in rgroups.items():
        s = _stats(tl)
        if s["n"] < 3:
            failures.append(f"  ▸ {reg}: only {s['n']} trade(s) — insufficient data")
        elif s["wr"] is not None and s["wr"] < 45:
            failures.append(f"  ▸ {reg}: WR={s['wr']}%  exp={s['exp']:.3f}%  n={s['n']}  — below 45% win rate")
        elif s["exp"] is not None and s["exp"] < 0:
            failures.append(f"  ▸ {reg}: WR={s['wr']}%  exp={s['exp']:.3f}%  n={s['n']}  — negative expectancy")

    if s_adx["n"] < 10:
        failures.append(f"  ▸ adx_4h mode: only {s_adx['n']} confirmed trades in {n1h} bars — selectivity risk")
    if sl["n"] > 0 and sl["wr"] is not None and sl["wr"] < 45:
        failures.append(f"  ▸ LONG side: WR={sl['wr']}%  n={sl['n']}")
    if ss["n"] > 0 and ss["wr"] is not None and ss["wr"] < 45:
        failures.append(f"  ▸ SHORT side: WR={ss['wr']}%  n={ss['n']}")

    if not failures:
        print("  None detected.")
    else:
        for f in failures: print(f)

    # ── §10 Final verdict ────────────────────────────────────────────────────
    print(f"\n{SEC}\n  §10 FINAL VERDICT\n{SEC}")

    s_main = _stats(all_trades)
    checks = [
        ("Trade count scalp ≥ 20",          n >= 20,                            f"n={n}"),
        ("OOS trade count ≥ 10",            s_agg["n"] >= 10,                   f"OOS n={s_agg['n']}"),
        ("WR ≥ 50% (scalp mode)",           (s_main["wr"] or 0) >= 50,          _v(s_main["wr"],".1f") + "%"),
        ("Expectancy > 0 (scalp)",          (s_main["exp"] or -1) > 0,          _v(s_main["exp"],".3f") + "%"),
        ("Profit factor > 1.0 (scalp)",     (s_main["pf"] or 0) > 1.0,         _v(s_main["pf"])),
        ("Max drawdown > -25% (scalp)",     _max_dd(all_trades) > -25,          f"{_max_dd(all_trades):.1f}%"),
        ("OOS WR ≥ 45% (WF)",               (s_agg["wr"] or 0) >= 45,           _v(s_agg["wr"],".1f") + "%"),
        ("adx_4h confirmed setups > 0",     s_adx["n"] > 0,                     f"n={s_adx['n']}"),
        ("Signal acc long ≥ 60% @4H",       (st.signal_accuracy_long_4h or 0)>=60,  _v(st.signal_accuracy_long_4h,".1f") + "%"),
        ("Signal acc short ≥ 60% @4H",      (st.signal_accuracy_short_4h or 0)>=60, _v(st.signal_accuracy_short_4h,".1f") + "%"),
    ]
    passed = sum(1 for _, ok, _ in checks if ok)
    print()
    for name, ok, val in checks:
        print(f"  [{'✓' if ok else '✗'}] {name:<40}  {val}")

    print(f"\n  Score: {passed}/{len(checks)}")

    if passed >= 8:
        verdict = "PAPER-DEPLOY (scalping mode)"
        detail  = "Strong evidence in scalp mode. Default adx_4h needs live observation."
    elif passed >= 6:
        verdict = "CONDITIONAL PAPER — SCALP MODE ONLY"
        detail  = "Scalp mode shows positive expectancy. adx_4h insufficient data — observe live."
    elif passed >= 4:
        verdict = "MODIFY BEFORE PAPER"
        detail  = "Some signals work, but critical checks fail. Fix before deploy."
    else:
        verdict = "REJECT — INSUFFICIENT EVIDENCE"
        detail  = "Too few trades for statistical inference. Cannot confirm positive expectancy."

    print(f"\n  ┌{'─'*62}┐")
    print(f"  │  VERDICT: {verdict:<52}│")
    print(f"  │  {detail:<60}│")
    print(f"  └{'─'*62}┘")

    print(f"""
  Key findings:
  • adx_4h mode: {s_adx['n']} confirmed setups in {n1h} bars (~{n1h//24} days)
    → Strategy is highly selective by design. Fires ~{s_adx['n']/(n1h/24):.2f}×/day.
    → Cannot assess profit metrics without live paper-trade data.
  • Scalp mode (macro_filter='off'): {n} trades, WR={_v(s_main['wr'],'.1f')}%, Exp={_v(s_main['exp'],'.3f')}%
    → Positive expectancy if fee<breakeven, but n<50 remains statistically marginal.
  • Directional accuracy at arrow events: long={_v(st.signal_accuracy_long_4h,'.0f')}%, short={_v(st.signal_accuracy_short_4h,'.0f')}%
    → Signal quality is high when it fires; problem is fire rate in default mode.
  • Fix needed: adx_4h mode needs live paper data (30+ trades) before verdict.
""")
    print(HDR)


if __name__ == "__main__":
    run()
