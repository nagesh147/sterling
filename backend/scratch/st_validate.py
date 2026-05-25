"""Triple SuperTrend validation harness — multi-symbol + in-sample/out-of-sample.

Loads ~2y of stored 1H/4H candles for the liquid majors, runs a config over the
full window AND a 50/50 time split (train=older half, test=newer half), and
prints aggregate profitability so we can tell genuine edge from curve-fit.

Run:  .venv/bin/python scratch/st_validate.py
"""
import sys, time
from app.services import ohlcv_store
from app.schemas.market import Candle
from app.engines.triple_st.config import default_config, StrategyMode, AssetClass
from app.engines.triple_st import backtest as bt

SYMS = ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE"]
DAYS = 730


def load(sym, res, days):
    per = {"1h": 24, "4h": 6}[res]
    since = int(time.time()) - days * 86400
    rows = ohlcv_store.get_candles(f"{sym}USD", res, limit=days * per + 400, since=since)
    return [Candle(timestamp_ms=int(r["time"]) * 1000, open=r["open"], high=r["high"],
                   low=r["low"], close=r["close"], volume=r["volume"]) for r in rows]


def slice_by_half(c1h, c4h, btc, which):
    if not c1h:
        return c1h, c4h, btc
    mid = c1h[len(c1h) // 2].timestamp_ms
    def f(arr, lo):
        return [c for c in arr if (c.timestamp_ms < mid) == lo]
    lo = which == "train"
    return f(c1h, lo), f(c4h, lo), (f(btc, lo) if btc else btc)


def run(cfg, label):
    data = {s: (load(s, "1h", DAYS), load(s, "4h", DAYS)) for s in SYMS}
    btc1h = load("BTC", "1h", DAYS)
    print(f"\n=== {label} ===")
    print(f"{'window':12s} {'trades':>7s} {'win%':>5s} {'PF':>5s} {'exp_R':>6s} {'ret%':>7s} {'maxDD%':>7s} {'avgWin':>7s} {'avgLoss':>7s}")
    for win in ("full", "train", "test"):
        agg = {"tr": 0, "w": 0, "gw": 0.0, "gl": 0.0, "rs": [], "ret": [], "dd": []}
        for s in SYMS:
            c1h, c4h = data[s]
            b = c1h if s == "BTC" else btc1h
            if win != "full":
                c1h, c4h, b = slice_by_half(c1h, c4h, b, win)
            if len(c1h) < cfg.warmup_bars + 60:
                continue
            r = bt.run_backtest(s, c1h, c4h, b, cfg, DAYS)
            st = r.stats
            agg["tr"] += st.total_trades
            agg["w"] += st.wins
            agg["ret"].append(st.total_return_pct)
            agg["dd"].append(st.max_drawdown_pct)
            for t in r.trades:
                agg["rs"].append(t.pnl_r)
                if t.pnl_usd > 0: agg["gw"] += t.pnl_usd
                else: agg["gl"] += abs(t.pnl_usd)
        tr = agg["tr"]
        wins = [x for x in agg["rs"] if x > 0]
        losses = [x for x in agg["rs"] if x <= 0]
        win_pct = 100 * agg["w"] / tr if tr else 0
        pf = agg["gw"] / agg["gl"] if agg["gl"] > 0 else 0
        exp = sum(agg["rs"]) / len(agg["rs"]) if agg["rs"] else 0
        avgw = sum(wins) / len(wins) if wins else 0
        avgl = sum(losses) / len(losses) if losses else 0
        ret = sum(agg["ret"]) / len(agg["ret"]) if agg["ret"] else 0
        dd = max(agg["dd"]) if agg["dd"] else 0
        print(f"{win:12s} {tr:7d} {win_pct:5.0f} {pf:5.2f} {exp:+6.2f} {ret:7.1f} {dd:7.0f} {avgw:+7.2f} {avgl:+7.2f}")


def resample_daily(c4h):
    """Aggregate 4H candles into 1D OHLCV (HTF for a 4H-primary run)."""
    buckets = {}
    for c in c4h:
        k = c.timestamp_ms // 86_400_000
        b = buckets.get(k)
        if b is None:
            buckets[k] = [c.timestamp_ms, c.open, c.high, c.low, c.close, c.volume]
        else:
            b[2] = max(b[2], c.high); b[3] = min(b[3], c.low); b[4] = c.close; b[5] += c.volume
    out = []
    for k in sorted(buckets):
        t, o, h, l, cl, v = buckets[k]
        out.append(Candle(timestamp_ms=k * 86_400_000, open=o, high=h, low=l, close=cl, volume=v))
    return out


def run_4h(cfg, label):
    """Run the SAME engine but on 4H as the primary timeframe, 1D as HTF."""
    print(f"\n=== {label} (4H primary / 1D HTF) ===")
    print(f"{'window':12s} {'trades':>7s} {'win%':>5s} {'PF':>5s} {'exp_R':>6s} {'ret%':>7s} {'maxDD%':>7s} {'avgWin':>7s} {'avgLoss':>7s}")
    data = {s: load(s, "4h", DAYS) for s in SYMS}
    btc4 = load("BTC", "4h", DAYS)
    for win in ("full", "train", "test"):
        agg = {"tr": 0, "w": 0, "gw": 0.0, "gl": 0.0, "rs": [], "ret": [], "dd": []}
        for s in SYMS:
            c4 = data[s]
            b = c4 if s == "BTC" else btc4
            htf = resample_daily(c4)
            if win != "full":
                mid = c4[len(c4) // 2].timestamp_ms
                lo = win == "train"
                c4 = [c for c in c4 if (c.timestamp_ms < mid) == lo]
                b = [c for c in b if (c.timestamp_ms < mid) == lo]
                htf = [c for c in htf if (c.timestamp_ms < mid) == lo]
            if len(c4) < cfg.warmup_bars + 30:
                continue
            r = bt.run_backtest(s, c4, htf, b, cfg, DAYS)
            st = r.stats
            agg["tr"] += st.total_trades; agg["w"] += st.wins
            agg["ret"].append(st.total_return_pct); agg["dd"].append(st.max_drawdown_pct)
            for t in r.trades:
                agg["rs"].append(t.pnl_r)
                if t.pnl_usd > 0: agg["gw"] += t.pnl_usd
                else: agg["gl"] += abs(t.pnl_usd)
        tr = agg["tr"]; wins = [x for x in agg["rs"] if x > 0]; losses = [x for x in agg["rs"] if x <= 0]
        win_pct = 100 * agg["w"] / tr if tr else 0
        pf = agg["gw"] / agg["gl"] if agg["gl"] > 0 else 0
        exp = sum(agg["rs"]) / len(agg["rs"]) if agg["rs"] else 0
        avgw = sum(wins) / len(wins) if wins else 0
        avgl = sum(losses) / len(losses) if losses else 0
        ret = sum(agg["ret"]) / len(agg["ret"]) if agg["ret"] else 0
        dd = max(agg["dd"]) if agg["dd"] else 0
        print(f"{win:12s} {tr:7d} {win_pct:5.0f} {pf:5.2f} {exp:+6.2f} {ret:7.1f} {dd:7.0f} {avgw:+7.2f} {avgl:+7.2f}")


if __name__ == "__main__":
    if "--1h" in sys.argv:
        cfg = default_config(); cfg.mode = StrategyMode.BALANCED
        cfg.use_dynamic_mode = False; cfg.warmup_bars = 100
        run(cfg, "1H primary — Balanced")
    for m in [StrategyMode.CONSERVATIVE, StrategyMode.BALANCED, StrategyMode.AGGRESSIVE, StrategyMode.MOMENTUM]:
        cfg = default_config(); cfg.mode = m
        cfg.use_dynamic_mode = False; cfg.warmup_bars = 60
        run_4h(cfg, m.value)
