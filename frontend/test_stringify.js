const stableStringify = (obj) => {
  if (obj === null || typeof obj !== 'object') return JSON.stringify(obj);
  if (Array.isArray(obj)) return `[${obj.map(stableStringify).join(',')}]`;
  return `{${Object.keys(obj).sort().map(k => `"${k}":${stableStringify(obj[k])}`).join(',')}}`;
};

const draft = {
  active_profiles: [],
  profiles: {},
  use_optimized: true,
  tiered_tp: { enabled: true, tp1_r_multiple: 1.5, tp1_size_pct: 0.3, move_to_be_at_tp1: true },
  symbols: [],
  warmup_bars_4h: 50,
  warmup_bars_15m: 60
};

const cfg = {
  "active_profiles": [],
  "profiles": {},
  "use_optimized": true,
  "tiered_tp": {
    "enabled": true,
    "tp1_r_multiple": 1.5,
    "tp1_size_pct": 0.3,
    "move_to_be_at_tp1": true
  },
  "symbols": [],
  "warmup_bars_4h": 50,
  "warmup_bars_15m": 60
};

console.log(stableStringify(draft) === stableStringify(cfg));
