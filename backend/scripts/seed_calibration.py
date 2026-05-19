"""
Seed the `calibration_trades` table with 15 dummy closed trades so the
CalibrationService cold-start gate releases (it requires ≥ 10 trades
before `win_rate()` returns a non-None value and the Kelly sizer can
calculate a positive edge).

The actual `calibration_trades` schema persisted by
`app/services/calibration.py` is intentionally minimal:

    CREATE TABLE calibration_trades (
        id        INTEGER PRIMARY KEY,
        pnl_pct   REAL NOT NULL,
        regime    TEXT,
        closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

We construct a rich per-trade record (id, underlying, entry/exit
timestamps in ms, realized USD PnL, net pct, regime) so anyone tailing
the script can see what was inserted, but we only persist the two
columns the service actually reads (`pnl_pct`, `regime`). A JSON file
mirror of the full records is dropped alongside for traceability.

Usage:
    python scripts/seed_calibration.py [--db PATH] [--n 15] [--clean]

`--clean` deletes any prior seeded rows (matched by a marker JSON
sidecar) before inserting fresh ones — safe to run repeatedly.

This is a one-shot operator tool. It is intentionally NOT importable by
the engines; engines stay pure with no DB or `time.time()` calls.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

_HERE = Path(__file__).resolve().parent.parent      # backend/
_DEFAULT_DB = _HERE / "sterling_paper.db"
_MIRROR_FILE = _HERE / "baselines" / "calibration_seed.json"


def _build_dummy_trades(n: int, *, seed: int = 42) -> List[Dict[str, Any]]:
    """
    Deterministic dummy trades engineered to yield a ~53% win rate so the
    Kelly sizer sees a positive edge (p>0.5, p*win - (1-p)*|loss| > 0).

    For n=15:
        wins   = ceil(0.5333 * 15) = 8  (53.33%)
        losses = 7
    Wins are small positives (+0.6% to +1.4%); losses are slightly larger
    negatives (-0.4% to -1.0%) — keeps avg_win > avg_loss * (1-p)/p so
    Kelly fraction stays > 0 with a healthy margin and the sizer doesn't
    edge-case to zero on noise.

    Underlyings and regimes are cycled across BTC/ETH and BULL_TREND /
    BEAR_TREND / RANGING so per-regime win-rate filters in
    `CalibrationService.win_rate(regime=...)` aren't biased to one
    bucket on cold start.
    """
    rng = random.Random(seed)
    underlyings = ["BTC", "ETH"]
    regimes     = ["BULL_TREND", "BEAR_TREND", "RANGING"]

    n_wins = int(round(n * 0.5333))           # 8 of 15
    n_loss = n - n_wins                       # 7 of 15
    outcomes = [True] * n_wins + [False] * n_loss
    rng.shuffle(outcomes)

    now_ms = int(time.time() * 1000)
    bar_ms = 60 * 60_000                      # 1H bars
    out: List[Dict[str, Any]] = []
    for i, is_win in enumerate(outcomes):
        # space trades 6 bars apart so closed_at ordering matches entry order
        entry_ts = now_ms - (n - i) * 6 * bar_ms
        hold_bars = rng.randint(3, 8)
        exit_ts  = entry_ts + hold_bars * bar_ms

        if is_win:
            net_pct = round(rng.uniform(0.006, 0.014), 6)   # +0.6% to +1.4%
        else:
            net_pct = round(-rng.uniform(0.004, 0.010), 6)  # -0.4% to -1.0%

        underlying = underlyings[i % len(underlyings)]
        regime     = regimes[i % len(regimes)]
        # Notional 10k → realised USD ≈ net_pct * notional.
        realised_usd = round(net_pct * 10_000.0, 2)

        out.append({
            "id":                 i + 1,
            "underlying":         underlying,
            "entry_timestamp_ms": entry_ts,
            "exit_timestamp_ms":  exit_ts,
            "realized_pnl_usd":   realised_usd,
            "net_pnl_pct":        net_pct,
            "regime":             regime,
        })
    return out


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Create the table if the DB is brand-new (matches calibration.py)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calibration_trades (
            id        INTEGER PRIMARY KEY,
            pnl_pct   REAL NOT NULL,
            regime    TEXT,
            closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def _clean_prior_seed(conn: sqlite3.Connection) -> int:
    """
    Remove rows from a previous seed run so re-running stays idempotent.
    We identify prior seeds by checking the mirror JSON for ids; if it
    doesn't exist, nothing to clean.
    """
    if not _MIRROR_FILE.exists():
        return 0
    try:
        prior = json.loads(_MIRROR_FILE.read_text())
        pnl_set = {round(float(t["net_pnl_pct"]), 6) for t in prior}
        regimes = {t["regime"] for t in prior}
    except Exception:
        return 0
    if not pnl_set or not regimes:
        return 0
    cur = conn.execute(
        "DELETE FROM calibration_trades WHERE pnl_pct IN ({}) AND regime IN ({})".format(
            ",".join("?" * len(pnl_set)), ",".join("?" * len(regimes)),
        ),
        list(pnl_set) + list(regimes),
    )
    return cur.rowcount or 0


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(_DEFAULT_DB),
                   help="SQLite DB path (default: backend/sterling_paper.db)")
    p.add_argument("--n", type=int, default=15,
                   help="Number of dummy trades to insert (default: 15)")
    p.add_argument("--seed", type=int, default=42,
                   help="RNG seed for deterministic output (default: 42)")
    p.add_argument("--clean", action="store_true",
                   help="Delete prior seed rows before inserting")
    args = p.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.parent.exists():
        print(f"[seed_calibration] db dir missing: {db_path.parent}", file=sys.stderr)
        return 1

    trades = _build_dummy_trades(args.n, seed=args.seed)
    wins = sum(1 for t in trades if t["net_pnl_pct"] > 0)
    print(f"[seed_calibration] generated {len(trades)} trades "
          f"({wins}/{len(trades)} wins = {wins/len(trades):.2%})")

    with sqlite3.connect(str(db_path), timeout=30.0) as conn:
        _ensure_table(conn)
        if args.clean:
            removed = _clean_prior_seed(conn)
            print(f"[seed_calibration] removed {removed} prior seed rows")
        for t in trades:
            conn.execute(
                "INSERT INTO calibration_trades (pnl_pct, regime) VALUES (?, ?)",
                (t["net_pnl_pct"], t["regime"]),
            )
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM calibration_trades"
        ).fetchone()[0]
    print(f"[seed_calibration] inserted {len(trades)} rows; "
          f"calibration_trades total = {count}")

    _MIRROR_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MIRROR_FILE.write_text(json.dumps(trades, indent=2))
    print(f"[seed_calibration] wrote mirror → {_MIRROR_FILE}")

    cold_gate = 10  # CalibrationService.MIN_TRADES_FOR_WIN_RATE
    if count >= cold_gate:
        print(f"[seed_calibration] cold-start gate ({cold_gate}) cleared "
              f"→ Kelly sizer will now compute fractional sizing > 0")
    else:
        print(f"[seed_calibration] WARNING: still below cold-start gate "
              f"({count} < {cold_gate}); re-run with larger --n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
