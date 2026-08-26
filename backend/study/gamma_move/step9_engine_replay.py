"""Run the shipped engine over the calibration data. End-to-end proof."""
from __future__ import annotations
import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.engines.gamma_move import (Candle, GammaMoveConfig, OICandle, SpotLevel,
                                    StrikeCandidate, InstrumentRef, find_levels,
                                    live_levels, regime_of, replay_contract, summarise)

OUT = Path(__file__).parent / "out"
opt = json.loads((OUT / "bars.json").read_text())
spot = json.loads((OUT / "spot_daily.json").read_text())
IST = timezone(timedelta(hours=5, minutes=30))

def ms(iso): return int(datetime.fromisoformat(iso).timestamp() * 1000)

# The sample sits at DTE 34-103, outside the strategy's own expiry window, so the
# window is widened HERE ONLY -- otherwise the engine correctly refuses every bar
# and the replay proves nothing about the rest of the machinery.
cfg = GammaMoveConfig(enabled=True, min_days_to_expiry=1, max_days_to_expiry=120,
                      max_premium_at_risk_inr=200_000, capital_inr=2_000_000)

results, considered = [], 0
for sym, rec in list(opt.items()):
    meta = rec["meta"]
    name = meta["underlying"]
    if name not in spot:
        continue
    sc = [Candle(ts_ms=ms(b["date"]), open=b["open"], high=b["high"], low=b["low"],
                 close=b["close"]) for b in spot[name]]
    if len(sc) < 60:
        continue
    levels = find_levels(sc, pivot_lookback=cfg.pivot_lookback,
                         cluster_pct=cfg.level_cluster_pct,
                         min_touches=cfg.min_level_touches,
                         window=cfg.level_lookback_days)
    px = sc[-1].close
    kind = "resistance" if meta["option_type"] == "CE" else "support"
    near = [l for l in live_levels(levels, px, cfg.level_proximity_pct) if l.kind == kind]
    considered += 1
    if not near:
        continue                       # the level gate, doing its job
    bars = [OICandle(ts_ms=ms(b["date"]), open=b["open"], high=b["high"], low=b["low"],
                     close=b["close"], volume=b["volume"], oi=b["oi"])
            for b in rec["bars"] if (b.get("oi") or 0) > 0 and (b.get("close") or 0) > 0]
    if len(bars) < 60:
        continue
    inst = InstrumentRef(instrument_id=str(meta["token"]), tradingsymbol=sym,
                         option_type=meta["option_type"], strike=meta["strike"],
                         expiry=meta["expiry"], lot_size=meta["lot_size"],
                         tick_size=meta["tick_size"])
    cand = StrikeCandidate(underlying=name, level=near[0], instrument=inst,
                           oi=int(meta["oi"]), days_to_expiry=34, spot=px,
                           premium=meta["ltp"])
    reg = regime_of(sc, cfg)
    regimes = {b["date"][:10]: reg for b in rec["bars"]}
    results.append(replay_contract(cand, bars, cfg, regime_by_day=regimes))

print(f"contracts considered: {considered}")
print(f"passed the level gate: {len(results)}")
s = summarise(results)
for k, v in s.items():
    print(f"  {k}: {v}")
refusals = {}
for r in results:
    for e in r["events"]:
        if e["kind"] == "refused":
            refusals[e["reason"]] = refusals.get(e["reason"], 0) + 1
print("refusal reasons:", dict(sorted(refusals.items(), key=lambda kv: -kv[1])[:5]))
