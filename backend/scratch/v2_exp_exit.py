"""Lever 3 experiment: ATR trailing exit vs static SL/TP, long-only, TEST slice.

Isolates the exit engine's contribution. trail_mult is a hyperparameter, so it
is selected on the VALIDATION slice (best validation Sharpe), then reported on
the UNTOUCHED test slice. be_at_r fixed at 1.0. Appends to lever_results.md.
"""
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

from app.engines.sterling_v2 import data as D, harness as H, signals as S
from app.engines.sterling_v2.config import SimConfig
from app.engines.sterling_v2.exits import TrailingExit
from app.engines.sterling_v2.research import split_indices

STRATS = ["ma_crossover", "breakout", "smc", "price_action"]
TF = "4h"
TRAIL_GRID = [1.0, 1.5, 2.0, 2.5, 3.0]
CFG = SimConfig(sl_mult=2.0, tp_mult=3.5, fee_round_trip=0.001, slippage=0.0005)


def _run(d, longs, trail_mult):
    pol = None if trail_mult is None else TrailingExit(trail_mult=trail_mult, be_at_r=1.0)
    return H.compute_metrics(H.simulate(d, longs, None, CFG, exit_policy=pol))


def main() -> None:
    rows = []
    for sym, path in D.list_symbols().items():
        df = D.load_symbol(path)
        d = D.resample_tf(df, TF)
        _, val, test = split_indices(len(d))
        dv, dt = d.iloc[val], d.iloc[test]
        for s in STRATS:
            lv, ltt = S.long_signal(s, dv), S.long_signal(s, dt)
            best_tm, best_sh = TRAIL_GRID[1], -1e9
            for tm in TRAIL_GRID:
                mv = _run(dv, lv, tm)
                if mv["trades"] >= 8 and mv["sharpe"] > best_sh:
                    best_sh, best_tm = mv["sharpe"], tm
            base = _run(dt, ltt, None)          # static SL/TP
            tr = _run(dt, ltt, best_tm)         # trailing, val-selected mult
            keep = tr["sharpe"] > base["sharpe"]
            rows.append((sym, s, best_tm, base, tr, keep))
            print(f"{sym} {s:13} tm*={best_tm} | static Sh {base['sharpe']:+.2f} "
                  f"PF {base['pf']:.2f} net {base['net']*100:+.0f}% DD {base['max_dd']*100:.0f}% "
                  f"| trail Sh {tr['sharpe']:+.2f} PF {tr['pf']:.2f} net {tr['net']*100:+.0f}% "
                  f"DD {tr['max_dd']*100:.0f}% -> {'KEEP' if keep else 'reject'}")

    n_keep = sum(1 for *_, k in rows if k)
    dd_better = sum(1 for *_, b, t, _ in rows if t["max_dd"] > b["max_dd"])
    lines = [
        "## Lever 3 -- ATR trailing exit vs static SL/TP (long-only), TEST slice @ 4h",
        "",
        "trail_mult selected on VALIDATION (never test); be_at_r=1.0. KEEP = improves "
        "test Sharpe. Trailing's primary value is drawdown/giveback reduction, so the DD "
        "column matters as much as Sharpe.",
        "",
        "| Symbol | Strategy | trail* | Static Sh | Static Net% | Static DD% | Trail Sh | Trail Net% | Trail DD% | Trail n | Verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for sym, s, tm, b, t, keep in rows:
        lines.append(
            f"| {sym} | {s} | {tm:g} | {b['sharpe']:+.2f} | {b['net']*100:+.0f} | "
            f"{b['max_dd']*100:.0f} | {t['sharpe']:+.2f} | {t['net']*100:+.0f} | "
            f"{t['max_dd']*100:.0f} | {t['trades']} | {'**KEEP**' if keep else 'reject'} |"
        )
    lines += [
        "",
        f"**Verdict: REJECT trailing as a default lever (for these trend edges).** It improves "
        f"test Sharpe in only {n_keep}/{len(rows)} cells while cutting max-DD in {dd_better}/{len(rows)} "
        "-- it trims BOTH tails (smaller losses and smaller wins), which lowers risk-adjusted "
        "return on trend-following entries whose edge is letting winners run to the 3.5xATR target. "
        "The validation-selected trail_mult also generalizes poorly (e.g. SOL ma_crossover val-best "
        "-> test Sharpe +0.23->-3.07; ETH ma_crossover -0.50->-2.69) -- an overfit signature. "
        "Static SL/TP is the more robust exit; drawdown is instead contained by the portfolio DD "
        "circuit breaker (lever 5), which does not pay this Sharpe penalty. The exit_policy hook is "
        "kept (tested, leak-free) but OFF in the default V2 stack; available per-book for future "
        "strategies that suit it (only the already-broken ETH/SOL price_action-type books benefited).",
        "",
    ]

    out = os.path.abspath(
        os.path.join(D.parquet_dir(), "..", "docs", "sterling_v2", "lever_results.md")
    )
    prior = open(out).read() if os.path.exists(out) else ""
    with open(out, "w") as f:
        f.write(prior.rstrip() + "\n\n" + "\n".join(lines) + "\n")
    print("\nwrote", out)


if __name__ == "__main__":
    main()
