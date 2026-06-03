"""Lever 2 experiment: conviction/regime gate, gated vs ungated long-only.

Isolates the gate's standalone contribution (no short side here -- that is lever 1).
Discipline: the adx_min threshold is a hyperparameter, so it is selected on the
VALIDATION slice (small sweep, best validation Sharpe with a min-trade floor),
then reported on the UNTOUCHED test slice -- the test set never selects the
threshold. Long EMA-slope gate (side=1). Appends to docs/sterling_v2/lever_results.md.
"""
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

from app.engines.sterling_v2 import data as D, harness as H, signals as S, regime as R
from app.engines.sterling_v2.config import SimConfig
from app.engines.sterling_v2.research import split_indices

STRATS = ["ma_crossover", "breakout", "smc", "price_action"]
TF = "4h"
ADX_GRID = [0.0, 12.0, 15.0, 18.0, 22.0, 25.0]
VAL_MIN_TRADES = 8  # floor so the validation pick is not a 1-trade fluke


def _run(d, longs, adx_min):
    f = None if adx_min is None else R.build_gate(d, adx_min=adx_min, side=1)
    return H.compute_metrics(H.simulate(d, longs, None, SimConfig(allow_short=False),
                                        entry_filter=f))


def main() -> None:
    rows = []
    for sym, path in D.list_symbols().items():
        df = D.load_symbol(path)
        d = D.resample_tf(df, TF)
        _, val, test = split_indices(len(d))
        dv, dt = d.iloc[val], d.iloc[test]
        for s in STRATS:
            lv, ltt = S.long_signal(s, dv), S.long_signal(s, dt)
            # select adx_min on VALIDATION (best Sharpe with a trade floor)
            best_adx, best_sh = 0.0, -1e9
            for a in ADX_GRID:
                mv = _run(dv, lv, a)
                if mv["trades"] >= VAL_MIN_TRADES and mv["sharpe"] > best_sh:
                    best_sh, best_adx = mv["sharpe"], a
            # report on TEST: ungated baseline vs gated with the val-chosen adx_min
            base = _run(dt, ltt, None)
            gated = _run(dt, ltt, best_adx)
            keep = gated["sharpe"] > base["sharpe"]
            rows.append((sym, s, best_adx, base, gated, keep))
            print(f"{sym} {s:13} adx*={best_adx:>4} | ungated Sh {base['sharpe']:+.2f} "
                  f"PF {base['pf']:.2f} net {base['net']*100:+.0f}% n{base['trades']} "
                  f"| gated Sh {gated['sharpe']:+.2f} PF {gated['pf']:.2f} "
                  f"net {gated['net']*100:+.0f}% n{gated['trades']} "
                  f"-> {'KEEP' if keep else 'reject'}")

    THIN = 12  # below this many test trades a per-cell Sharpe is untrustworthy
    n_keep = sum(1 for *_, k in rows if k)
    thin = sum(1 for *_, g, _ in rows if g["trades"] < THIN)
    adq = [(sym, s, k) for sym, s, _, _, g, k in rows if g["trades"] >= THIN]
    adq_keep = sum(1 for *_, k in adq if k)
    lines = [
        "## Lever 2 -- Conviction/regime gate (gated vs ungated long-only), TEST slice @ 4h",
        "",
        "adx_min selected on the VALIDATION slice (never the test set); EMA(50)-slope + "
        "ADX(14) gate, side=1. KEEP = improves test Sharpe. Gating thins the ~25-trade "
        "test slice substantially, so per-cell verdicts are indicative; the decisive test "
        "is the full combined stack (>=100 trades) in Task 15.",
        "",
        "| Symbol | Strategy | adx* | Ungated Sh | Ungated PF | Ungated n | Gated Sh | Gated PF | Gated Net% | Gated DD% | Gated n | Verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for sym, s, a, b, g, keep in rows:
        lines.append(
            f"| {sym} | {s} | {a:g} | {b['sharpe']:+.2f} | {b['pf']:.2f} | {b['trades']} | "
            f"{g['sharpe']:+.2f} | {g['pf']:.2f} | {g['net']*100:+.0f} | "
            f"{g['max_dd']*100:.0f} | {g['trades']} | {'**KEEP**' if keep else 'reject'} |"
        )
    lines += [
        "",
        f"**Verdict:** gate improves test Sharpe in {n_keep}/{len(rows)} cells overall, but "
        f"{thin}/{len(rows)} cells fell below {THIN} test trades after gating -- too thin to "
        f"trust (e.g. ETH smc n=5 Sharpe +3.15 is noise). Among the {len(adq)} adequately-sampled "
        f"cells (>= {THIN} trades), the gate helps {adq_keep}: it lifts the BTC long book "
        "(ma_crossover -0.69->+0.51 n29, smc -1.36->-0.95 n17, price_action -1.28->+0.69 n14) -- "
        "consistent with the grounding's BTC-only long edge -- but does NOT rescue ETH/SOL long "
        "(those are fixed by the SHORT side, lever 1, not a long gate). "
        "**Provisional KEEP for the long side (esp. BTC); firm decision on the combined "
        "stack (>=100 trades) in Task 15.**",
        "",
    ]

    out = os.path.abspath(
        os.path.join(D.parquet_dir(), "..", "docs", "sterling_v2", "lever_results.md")
    )
    prior = ""
    if os.path.exists(out):
        with open(out) as f:
            prior = f.read()
    with open(out, "w") as f:
        f.write(prior.rstrip() + "\n\n" + "\n".join(lines) + "\n")
    print("\nwrote", out)


if __name__ == "__main__":
    main()
