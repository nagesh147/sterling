#!/usr/bin/env python3
"""
Sterling v4 — Strategy Optimizer (fast, standalone)
===================================================
Searches all combinations of scoring + voting + boost + threshold.
"""
from __future__ import annotations
import sys, os, json, time
from itertools import product
import numpy as np
from numpy.random import default_rng

TRACKS = ["trend_following", "vcp", "mean_reversion"]
REGIMES = ["bull_trend", "bear_trend", "bull_ranging", "bear_ranging", "neutral"]
N_T, N_R, N_BARS = 3, 5, 2000

_REGISTRY = {
    ("trend_following","bull_trend"):    {"sh": 1.4, "lr": 0.58, "sr": 0.41},
    ("trend_following","bear_trend"):    {"sh": 1.6, "lr": 0.38, "sr": 0.63},
    ("trend_following","bull_ranging"):  {"sh": 0.9, "lr": 0.52, "sr": 0.48},
    ("trend_following","bear_ranging"):  {"sh": 1.1, "lr": 0.46, "sr": 0.54},
    ("trend_following","neutral"):       {"sh": 0.4, "lr": 0.50, "sr": 0.50},
    ("vcp","bull_trend"):                {"sh": 1.8, "lr": 0.45, "sr": 0.67},
    ("vcp","bear_trend"):               {"sh": 1.3, "lr": 0.55, "sr": 0.58},
    ("vcp","bull_ranging"):             {"sh": 2.1, "lr": 0.62, "sr": 0.40},
    ("vcp","bear_ranging"):             {"sh": 1.9, "lr": 0.58, "sr": 0.55},
    ("vcp","neutral"):                  {"sh": 1.0, "lr": 0.55, "sr": 0.55},
    ("mean_reversion","bull_trend"):   {"sh": 1.5, "lr": 0.32, "sr": 0.65},
    ("mean_reversion","bear_trend"):   {"sh": 1.4, "lr": 0.62, "sr": 0.38},
    ("mean_reversion","bull_ranging"): {"sh": 0.6, "lr": 0.50, "sr": 0.50},
    ("mean_reversion","bear_ranging"): {"sh": 0.7, "lr": 0.48, "sr": 0.52},
    ("mean_reversion","neutral"):      {"sh": 0.3, "lr": 0.50, "sr": 0.50},
}

def track_edge(t, r, direction):
    e = _REGISTRY[(TRACKS[t], REGIMES[r])]
    return e["sh"] * (e["lr"] if direction == 1 else e["sr"])

EDGE_MAT = np.array([[track_edge(t, r, 1) for r in range(N_R)] for t in range(N_T)], dtype=np.float64)

SCHEMES  = ["walk_forward", "equal", "vcp_heavy", "adaptive"]
VOTES    = ["unweighted", "by_edge", "majority_2of3"]
SCORES   = ["mean", "max", "geometric"]
BOOSTS   = ["none", "linear_agree"]
THRESHS  = [4.0, 7.0]

ALL_CONFIGS = list(product(SCHEMES, VOTES, SCORES, BOOSTS, THRESHS))
N_CFG = len(ALL_CONFIGS)
print(f"Total configs: {N_CFG}  (N_T={N_T} N_R={N_R} N_BARS={N_BARS})", flush=True)

RW_ARR = {
    "walk_forward": np.array([[1.00,0.90,0.75,0.80,0.90],[0.85,1.00,1.00,1.00,0.95],[0.50,0.55,0.80,0.75,0.90]], dtype=np.float64),
    "equal":        np.ones((3, 5), dtype=np.float64),
    "vcp_heavy":    np.array([[0.70,0.80,0.60,0.70,0.75],[1.00,1.00,1.20,1.20,1.10],[0.40,0.50,0.60,0.60,0.70]], dtype=np.float64),
}


def run_one_config(cfg, rng):
    scheme, vote, score, boost, thresh = cfg

    # dims: (track=3, regime=5, bar=2000) — consistent ordering
    scores_raw = rng.normal(10.0, 4.0, size=(N_T, N_R, N_BARS))
    dirs_raw   = rng.choice([-1, 0, 1], size=(N_T, N_R, N_BARS), p=[0.35, 0.25, 0.40])
    edge_arr   = np.broadcast_to(EDGE_MAT[:, :, None], (N_T, N_R, N_BARS)).copy()
    rw         = RW_ARR.get(scheme, np.ones((3, 5), dtype=np.float64))

    pos_mask = dirs_raw != 0
    n_active = pos_mask.sum(axis=0).clip(min=1)  # (5, 2000) — over tracks

    if score == "mean":
        sc = np.where(pos_mask, scores_raw, 0.0).mean(axis=0)
    elif score == "max":
        sc = scores_raw.max(axis=0)
    else:
        sc = np.exp(np.where(pos_mask, np.log(np.maximum(scores_raw, 0.01)), 0.0).sum(axis=0) / n_active)

    if boost == "linear_agree":
        ref_dir = dirs_raw[0:1, :, :]
        n_agree = ((dirs_raw == ref_dir) & (dirs_raw != 0)).sum(axis=0)
        bst = np.where(n_agree >= 3, 0.30, np.where(n_agree == 2, 0.15, 0.0))
    else:
        bst = np.zeros((N_R, N_BARS))

    composite = sc * (1.0 + bst)  # (5, 2000)

    if vote == "unweighted":
        dv = np.sign(dirs_raw.sum(axis=0))
    elif vote == "by_edge":
        dv = np.sign((dirs_raw.astype(float) * edge_arr).sum(axis=0))
    else:
        pos_m = (dirs_raw == 1).sum(axis=0)
        neg_m = (dirs_raw == -1).sum(axis=0)
        dv = np.where(pos_m >= 2, 1, np.where(neg_m >= 2, -1, 0))

    any_fired = dirs_raw.any(axis=0)
    valid = (composite >= thresh) & any_fired

    if not valid.any():
        return {"exp_sharpe": -999.0, "exp_wr": 0.0, "edge_per_trade": 0.0,
                "avg_score": 0.0, "dir_conf": 0.0, "agree_count": 0, "valid_trades": 0,
                "config": {"scheme": scheme, "vote": vote, "score": score,
                           "boost": boost, "threshold": thresh}}

    comp_v = composite[valid]
    dv_v   = dv[valid]

    avg_score = float(comp_v.mean())
    dir_conf  = float(np.mean(np.abs(dv_v)) / 3.0)

    # Agree count: for each valid bar, count tracks agreeing with ensemble
    # valid is (5, 2000), dv is (5, 2000), dirs_raw is (3, 5, 2000)
    # dv_v is 1D (N_valid,) from dv[valid]
    # Compute: for each valid position, how many tracks agree with dv?
    # Vectorised: create a (N_valid, 3) comparison
    valid_locs = np.argwhere(valid)  # (N_valid, 2) → (row, col) = (regime, bar)
    if len(valid_locs) > 0:
        ens_dirs = dv[valid_locs[:, 0], valid_locs[:, 1]]  # (N_valid,)
        track_dirs = dirs_raw[:, valid_locs[:, 0], valid_locs[:, 1]]  # (3, N_valid)
        agree_count_arr = (track_dirs == ens_dirs[None, :]).sum(axis=0)  # (N_valid,)
        agree_count = int(np.median(agree_count_arr)) if len(agree_count_arr) > 0 else 0
    else:
        agree_count = 0

    # Edge per trade: mean edge of agreeing tracks per valid bar
    if len(valid_locs) > 0:
        ens_dirs = dv[valid_locs[:, 0], valid_locs[:, 1]]
        track_dirs = dirs_raw[:, valid_locs[:, 0], valid_locs[:, 1]]  # (3, N_valid)
        ens_dirs_safe = np.where(ens_dirs == 0, 999, ens_dirs)  # replace 0 so != comparison works
        agreeing_mask = track_dirs == ens_dirs_safe[None, :]  # (3, N_valid)
        agreeing_edges = np.where(agreeing_mask, EDGE_MAT[:, valid_locs[:, 0]], 0.0)  # (3, N_valid)
        edges_per_bar = agreeing_edges.sum(axis=0) / agreeing_mask.sum(axis=0).clip(min=1)  # (N_valid,)
        avg_edge = float(np.mean(edges_per_bar))
    else:
        avg_edge = 0.5
    exp_sharpe = avg_edge * dir_conf * (avg_score / 10.0)
    exp_wr = float(np.clip(0.5 + avg_edge / 3.0, 0.30, 0.75))

    return {
        "config": {"scheme": scheme, "vote": vote, "score": score,
                   "boost": boost, "threshold": thresh},
        "exp_sharpe": round(exp_sharpe, 4), "exp_wr": round(exp_wr, 4),
        "edge_per_trade": round(avg_edge, 4), "avg_score": round(avg_score, 3),
        "dir_conf": round(dir_conf, 3), "agree_count": agree_count,
        "valid_trades": int(valid.sum()),
    }


if __name__ == "__main__":
    t0 = time.time()
    print("Running strategy search...", flush=True)

    results = []
    for ci, cfg in enumerate(ALL_CONFIGS):
        if ci % 20 == 0:
            elapsed = time.time() - t0
            per_cfg = elapsed / max(ci, 1)
            eta = per_cfg * (N_CFG - ci)
            print(f"  {ci}/{N_CFG} ({100*ci/N_CFG:.0f}%) {elapsed:.1f}s elapsed, ETA {eta:.0f}s", flush=True)
        rng = default_rng(ci + 42)
        r = run_one_config(cfg, rng)
        results.append(r)

    print(f"\nSimulation done: {time.time()-t0:.1f}s", flush=True)

    valid_results = [r for r in results if r["exp_sharpe"] > -100]
    valid_results.sort(key=lambda x: x["exp_sharpe"], reverse=True)

    print(f"Valid: {len(valid_results)}/{len(results)}", flush=True)

    baseline_cfg = {"scheme": "walk_forward", "vote": "unweighted", "score": "mean",
                    "boost": "none", "threshold": 7.0}
    baseline = next((r for r in valid_results if r["config"] == baseline_cfg), None)

    print("\n" + "=" * 90)
    print(" STRATEGY RANKINGS BY EXPECTED SHARPE")
    print("=" * 90)
    print(f"{'Rank':<5}{'ExpSh':>7}{'ExpWR':>7}{'Edge':>6}{'Sc':>5}{'DC':>5}{'AC':>5}{'Trades':>7}  Config")
    print("-" * 90)
    for i, r in enumerate(valid_results):
        cfg = r["config"]
        name = (f"{cfg['scheme'][:4]}/{cfg['vote'][:6]}/{cfg['score'][:6]}/"
                f"{cfg['boost'][:6]}/thr{cfg['threshold']}")
        marker = " ◄BASELINE" if cfg == baseline_cfg else ""
        print(f"{i+1:<5}{r['exp_sharpe']:>7.4f}{r['exp_wr']:>7.1%}{r['edge_per_trade']:>6.3f}"
              f"{r['avg_score']:>5.1f}{r['dir_conf']:>5.2f}{r['agree_count']:>5}{r['valid_trades']:>7}  {name}{marker}")

    if baseline:
        print(f"\nBASELINE: Sharpe={baseline['exp_sharpe']:.4f} WR={baseline['exp_wr']:.1%} Edge={baseline['edge_per_trade']:.3f}")
    if valid_results:
        best = valid_results[0]
        print(f"BEST:    Sharpe={best['exp_sharpe']:.4f} WR={best['exp_wr']:.1%} Edge={best['edge_per_trade']:.3f}")
        if baseline:
            print(f"\nDelta: Sharpe {best['exp_sharpe']-baseline['exp_sharpe']:+.4f} | WR {best['exp_wr']-baseline['exp_wr']:+.1%} | Edge {best['edge_per_trade']-baseline['edge_per_trade']:+.3f}")

    out = os.path.join(os.path.dirname(__file__), "strategy_search_results.json")
    with open(out, "w") as f:
        json.dump({"best": valid_results[0] if valid_results else None,
                   "baseline": baseline, "all": valid_results}, f, indent=2, default=str)
    print(f"\nSaved → {out}  ({time.time()-t0:.1f}s total)", flush=True)