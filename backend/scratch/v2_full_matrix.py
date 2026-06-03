"""SterlingV2 COMPLETE before/after matrix: all TFs x strategies x profiles.

BEFORE = long-only (the pre-V2 config) with the profile's exits, no sizing.
AFTER  = V2 entry/sizing levers: long+short (where a short mirror exists) +
         vol-targeted sizing, SAME profile exits. So each row isolates the V2
         lever effect within a fixed (TF, strategy, profile) cell.

Basis = FULL sample (matches docs/sterling_v2/baseline_report.md, which this
expands). These are descriptive, in-sample-inclusive numbers -- the OOS-validated
result is the separate before_after_report.md (only 4h ma_crossover-style books
survived out-of-sample). Cost model: 0.10% fee, 5bps slippage/fill, next-bar
fills, realized-frequency Sharpe, $500 start.

Excluded: 1m (compute-prohibitive + guaranteed fee wipeout) and Scale_Out_2R
(partial scale-out is not modeled by the single-exit leak-free harness).
Writes docs/sterling_v2/full_matrix_report.md + scratch/v2_full_matrix.csv.
"""
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from app.engines.sterling_v2 import data as D, harness as H, signals as S
from app.engines.sterling_v2.config import SimConfig
from app.engines.sterling_v2.sizing import vol_target_weights
from app.engines.sterling_v2.exits import TrailingExit
from app.engines.edge.strategies import SIGNAL_FNS

START = 500.0
TF_RULES = [("5min", "5m"), ("15min", "15m"), ("30min", "30m"), ("1h", "1h"), ("4h", "4h")]
TFS = [lab for _, lab in TF_RULES]
STRATS = list(SIGNAL_FNS.keys())  # 7
HAS_SHORT = set(S.SHORT_FNS)      # ma_crossover, breakout, price_action, smc
PROFILES = {
    "Scalping": dict(sl_mult=1.0, tp_mult=2.0),
    "Intraday": dict(sl_mult=2.0, tp_mult=3.5),
    "Aggressive": dict(sl_mult=1.5, tp_mult=4.5),
    "Intraday_Trailing": dict(sl_mult=2.0, tp_mult=3.5, trail_mult=1.5),
}


def _run(d, longs, shorts, prof, after):
    pol = TrailingExit(prof["trail_mult"], 1.0) if "trail_mult" in prof else None
    cfg = SimConfig(sl_mult=prof["sl_mult"], tp_mult=prof["tp_mult"],
                    fee_round_trip=0.001, slippage=0.0005,
                    allow_short=bool(after and shorts is not None))
    res = H.simulate(d, longs, (shorts if after else None), cfg, exit_policy=pol)
    r = res.returns
    if after and r.size:
        w = vol_target_weights(r)
        w = w / w.mean() if w.mean() > 0 else w
    else:
        w = None
    return H.compute_metrics(res, weights=w)


def main() -> None:
    recs = []
    for sym, path in D.list_symbols().items():
        base_df = D.load_symbol(path)
        for rule, tf in TF_RULES:
            d = D.resample_tf(base_df, rule)
            longs = {s: SIGNAL_FNS[s](d) for s in STRATS}
            shorts = {s: (S.short_signal(s, d) if s in HAS_SHORT else None) for s in STRATS}
            for s in STRATS:
                for pname, prof in PROFILES.items():
                    bf = _run(d, longs[s], None, prof, after=False)
                    af = _run(d, longs[s], shorts[s], prof, after=True)
                    recs.append(dict(
                        symbol=sym, tf=tf, strategy=s, profile=pname,
                        has_short=s in HAS_SHORT,
                        bf_trades=bf["trades"], bf_pf=bf["pf"], bf_sharpe=bf["sharpe"],
                        bf_net=bf["net"], bf_dd=bf["max_dd"], bf_usd=START * (1 + bf["net"]),
                        af_trades=af["trades"], af_pf=af["pf"], af_sharpe=af["sharpe"],
                        af_net=af["net"], af_dd=af["max_dd"], af_usd=START * (1 + af["net"]),
                    ))
            print(f"  done {sym} {tf}")
    df = pd.DataFrame(recs)
    csv = os.path.abspath(os.path.join(D.parquet_dir(), "scratch", "v2_full_matrix.csv"))
    df.to_csv(csv, index=False)
    _write_md(df)
    print("wrote", csv)


def _fmt(v, d=2, pct=False):
    if v is None or not np.isfinite(v):
        return "—"
    return f"{v*100:+.0f}" if pct else f"{v:.{d}f}"


def _write_md(df: pd.DataFrame) -> None:
    L = ["# SterlingV2 — COMPLETE Before/After Matrix (all TFs × strategies × profiles)", "",
         "**BEFORE** = long-only (pre-V2) · **AFTER** = V2 levers (long+short where a short "
         "mirror exists, + vol-targeted sizing), same profile exits. $500 start; 0.10% fee + "
         "5bps slippage/fill; next-bar fills; realized-frequency Sharpe.", "",
         "> **Basis = FULL sample** (matches `baseline_report.md`). These are descriptive, "
         "in-sample-inclusive numbers. The OOS-validated result is `before_after_report.md` — "
         "only the **4h ma_crossover** family survived out-of-sample; high in-sample numbers at "
         "sub-4h / other strategies are mostly fees-vs-noise and did **not** generalize.", "",
         "> Excluded: **1m** (compute-prohibitive, guaranteed fee wipeout) and **Scale_Out_2R** "
         "(partial scale-out not modeled by the single-exit harness). Strategies without a short "
         "mirror (mean_reversion, bb_rsi_reversion, vwap_cross) run AFTER as long-only + sizing.", ""]

    # ---- aggregates ----
    L += ["## Aggregate: mean AFTER metrics by timeframe", "",
          "| TF | mean AFTER Sharpe | mean AFTER Net% | mean AFTER $500→ | mean BEFORE Net% |",
          "|---|---|---|---|---|"]
    for tf in TFS:
        g = df[df.tf == tf]
        L.append(f"| {tf} | {g.af_sharpe.mean():+.2f} | {g.af_net.mean()*100:+.0f} | "
                 f"${g.af_usd.mean():.0f} | {g.bf_net.mean()*100:+.0f} |")

    L += ["", "## Aggregate: mean AFTER metrics by profile", "",
          "| Profile | mean AFTER Sharpe | mean AFTER Net% | mean AFTER $500→ |",
          "|---|---|---|---|"]
    for p in PROFILES:
        g = df[df.profile == p]
        L.append(f"| {p} | {g.af_sharpe.mean():+.2f} | {g.af_net.mean()*100:+.0f} | ${g.af_usd.mean():.0f} |")

    L += ["", "## Aggregate: mean AFTER metrics by strategy", "",
          "| Strategy | short? | mean AFTER Sharpe | mean AFTER Net% | mean AFTER $500→ |",
          "|---|---|---|---|---|"]
    for s in STRATS:
        g = df[df.strategy == s]
        L.append(f"| {s} | {'yes' if s in HAS_SHORT else 'no'} | {g.af_sharpe.mean():+.2f} | "
                 f"{g.af_net.mean()*100:+.0f} | ${g.af_usd.mean():.0f} |")

    # ---- top configs by AFTER $500 ----
    top = df.sort_values("af_usd", ascending=False).head(20)
    L += ["", "## Top 20 configs by AFTER outcome ($500 → )", "",
          "| Symbol | TF | Strategy | Profile | BF $500→ | BF Sh | AF $500→ | AF Sh | AF PF | AF DD% | AF trades |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in top.iterrows():
        L.append(f"| {r.symbol[:3]} | {r.tf} | {r.strategy} | {r.profile} | ${r.bf_usd:.0f} | "
                 f"{r.bf_sharpe:+.2f} | **${r.af_usd:.0f}** | {r.af_sharpe:+.2f} | {r.af_pf:.2f} | "
                 f"{r.af_dd*100:.0f} | {int(r.af_trades)} |")

    # ---- full matrix per symbol x TF ----
    L += ["", "## Full matrix (every cell)", "",
          "Each row: BEFORE → AFTER. `$` = $500 end value. `Sh` Sharpe, `DD` max drawdown.", ""]
    for sym in df.symbol.unique():
        for tf in TFS:
            g = df[(df.symbol == sym) & (df.tf == tf)]
            if g.empty:
                continue
            L += [f"### {sym} · {tf}", "",
                  "| Strategy | Profile | BF $ | BF Sh | BF Net% | BF DD% | AF $ | AF Sh | AF Net% | AF DD% | AF n |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
            for _, r in g.iterrows():
                L.append(f"| {r.strategy} | {r.profile} | ${r.bf_usd:.0f} | {r.bf_sharpe:+.2f} | "
                         f"{r.bf_net*100:+.0f} | {r.bf_dd*100:.0f} | **${r.af_usd:.0f}** | "
                         f"{r.af_sharpe:+.2f} | {r.af_net*100:+.0f} | {r.af_dd*100:.0f} | {int(r.af_trades)} |")
            L.append("")

    out = os.path.abspath(os.path.join(D.parquet_dir(), "..", "docs", "sterling_v2",
                                       "full_matrix_report.md"))
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
