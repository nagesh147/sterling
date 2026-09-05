"""Read-only audit of cached broker OHLC. Never synthesizes prices or submits orders.

Run from repo root:
PYTHONPATH=backend backend/.venv/bin/python backend/study/kite_production_audit.py
"""
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import numpy as np
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions
from app.engines.sterling_kite_engine.exits import resolve_exit

ROOT=Path(__file__).resolve().parents[2]
NAMES={'256265':'NIFTY 50','260105':'NIFTY BANK','257801':'NIFTY FIN SERVICE','265':'SENSEX'}
def iso(ms): return datetime.fromtimestamp(int(ms)/1000,timezone.utc).isoformat()
def main():
    report={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
       'code_base_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       'verdict':'NO_GO','data_kind':'cached broker index OHLC; not option execution evidence',
       'provenance_limit':'Existing kite_data.py cache; no original response receipt or signed acquisition manifest.',
       'config':asdict(SterlingKiteEngineConfig()),'datasets':[],
       'limitations':['No modeled premiums or generated market prices used.',
         'Index prices are not executable option/futures prices; no profitability claim.',
         'No expired option chain, point-in-time universe, bid/ask or fills in these caches.',
         'No live order submitted; historical defaults not optimized on this sample.']}
    cfg=SterlingKiteEngineConfig()
    for p in sorted((ROOT/'backend/study/kite_cache').glob('*_1H.npz')):
        with np.load(p,allow_pickle=False) as z: a={k:z[k] for k in ('ts','o','h','l','c','v')}
        n=len(a['ts']); good=(np.isfinite(np.column_stack(list(a.values()))).all(axis=1)
             & (a['l']>0) & (a['h']>=np.maximum(a['o'],a['c']))
             & (a['l']<=np.minimum(a['o'],a['c'])) & (a['v']>=0))
        r=compute_regime(a['o'],a['h'],a['l'],a['c'],cfg); longs,shorts=entry_transitions(r)
        violations=0;checks=0
        for end in range(cfg.warmup+2,n,max(1,n//100)):
            prefix=compute_regime(*(a[k][:end] for k in ('o','h','l','c')),cfg)
            lp,sp=entry_transitions(prefix)
            violations+=int(lp[-1]!=longs[end-1] or sp[-1]!=shorts[end-1]);checks+=1
        # Quantify impact of the old bug using the SAME observed bars, not generated prices.
        old=compute_regime(a['o'],a['h'],a['l'],a['c'],cfg)
        old.raw_low=old.basis_low;old.raw_high=old.basis_high
        changed=0;entries=0
        for direction,mask in [('long',longs),('short',shorts)]:
            for start in np.flatnonzero(mask):
                end=min(int(start)+240,n-1)
                corrected=resolve_exit(r,direction,int(start),end,cfg,longs,shorts)[0]
                prior=resolve_exit(old,direction,int(start),end,cfg,longs,shorts)[0]
                changed+=int(corrected!=prior);entries+=1
        row={'path':str(p.relative_to(ROOT)),'sha256':sha256(p.read_bytes()).hexdigest(),
             'instrument':NAMES[p.stem.split('_')[0]],'bars':n,'first_utc':iso(a['ts'][0]),
             'last_utc':iso(a['ts'][-1]),'invalid_bars':int((~good).sum()),
             'nonincreasing_timestamps':int((np.diff(a['ts'])<=0).sum()),
             'zero_volume_bars':int((a['v']==0).sum()),'long_transitions':int(longs.sum()),
             'short_transitions':int(shorts.sum()),'prefix_checks':checks,'prefix_violations':violations,
             'entry_exit_comparisons_240bar_horizon':entries,'exits_changed_raw_vs_ha_extrema':changed,
             'post_cas_bars':int((a['ts']>=1785705000000).sum())}
        report['datasets'].append(row)
    report['total_bars']=sum(x['bars'] for x in report['datasets'])
    for rel in ['app/services/kite_engine/scanner.py','app/services/kite_engine/backtest.py','app/engines/sterling_kite_engine/regime.py','app/engines/sterling_kite_engine/exits.py']:
        report.setdefault('code_sha256',{})[rel]=sha256((ROOT/'backend'/rel).read_bytes()).hexdigest()
    out=ROOT/'docs/audits/2026-09-05-kite-real-data-audit.json'
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'artifact':str(out),'total_bars':report['total_bars'],
        'datasets':[{k:x[k] for k in ('instrument','bars','last_utc','invalid_bars','prefix_violations','exits_changed_raw_vs_ha_extrema','post_cas_bars')} for x in report['datasets']]}))
if __name__=='__main__':main()
