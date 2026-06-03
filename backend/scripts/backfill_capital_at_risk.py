"""One-time backfill: fix capital_at_risk_pct on historical SCALPING positions that
were stored with the buggy `/100k` denominator. Recompute as $-at-risk / $500 * 100
(the current scalping book). Scope strictly limited to:
  - mode == 'scalping'
  - sized_trade present with capital_at_risk_pct & max_risk_usd
  - stored value matches the buggy formula signature (carp ≈ max_risk_usd / 1000)
Swing/derivatives (sized against ~$100k, already correct) and legacy rows are skipped.
Idempotent: after the fix, carp no longer matches the buggy signature, so re-runs are no-ops.

Usage:  python backfill_capital_at_risk.py [--apply]   (default = dry run)
"""
import sqlite3, json, sys, os, time

DB = os.environ.get("STERLING_DB_PATH", "sterling_paper.db")
NAV = 500.0
APPLY = "--apply" in sys.argv
EPS = 0.011  # carp is stored round(.,2); buggy pred = max_risk/1000

con = sqlite3.connect(DB)
rows = con.execute("SELECT id, data FROM positions").fetchall()

targets, skipped_swing, skipped_legacy, already = [], 0, 0, 0
for pid, raw in rows:
    d = json.loads(raw)
    st = d.get("sized_trade")
    mode = d.get("mode")
    if not st or st.get("capital_at_risk_pct") is None or st.get("max_risk_usd") is None:
        skipped_legacy += 1
        continue
    if mode != "scalping":
        skipped_swing += 1
        continue
    carp, mr = st["capital_at_risk_pct"], st["max_risk_usd"]
    if abs(carp - round(mr / 1000.0, 2)) >= EPS:   # not the buggy signature (already fixed / other)
        already += 1
        continue
    new_carp = round(mr / NAV * 100.0, 2)
    targets.append((pid, raw, d, carp, new_carp, mr, d.get("underlying")))

print(f"DB={DB}  total={len(rows)}")
print(f"  legacy (no sized_trade)      : {skipped_legacy}")
print(f"  swing/other mode (left as-is): {skipped_swing}")
print(f"  scalping already-fixed/other : {already}")
print(f"  scalping TO BACKFILL         : {len(targets)}")
print(f"\n  sample (sym  old% -> new%   $risk):")
for pid, raw, d, carp, new_carp, mr, sym in targets[:14]:
    print(f"    {str(sym):<5} {carp:>7.2f}% -> {new_carp:>6.2f}%   ${mr:.2f}")

if not APPLY:
    print("\n[DRY RUN] no rows written. Re-run with --apply to commit.")
    sys.exit(0)

# Back up exactly the rows we will change (id + original data) before mutating.
backup = f"/tmp/positions_capital_at_risk_backup_{int(time.time())}.json"
with open(backup, "w") as fh:
    json.dump([{"id": pid, "data": raw} for pid, raw, *_ in targets], fh)
print(f"\nbacked up {len(targets)} original rows -> {backup}")

n = 0
for pid, raw, d, carp, new_carp, mr, sym in targets:
    d["sized_trade"]["capital_at_risk_pct"] = new_carp
    con.execute("UPDATE positions SET data=? WHERE id=?", (json.dumps(d), pid))
    n += 1
con.commit()
print(f"updated {n} scalping positions (capital_at_risk_pct now / ${NAV:.0f}).")
