import React, { useState } from 'react';
import { card, cardHead, cardBody, c, alpha } from '../styles/terminalUI';

/* ── UI Helpers ──────────────────────────────────────────────────────────── */

function SectionCard({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={card}>
      <div style={cardHead}><span>{title}</span>{right && <span style={{ marginLeft: 'auto' }}>{right}</span>}</div>
      <div style={cardBody}>{children}</div>
    </div>
  );
}

function NumField({ label, value, step = 1, min, max, defaultVal, desc, onChange }: {
  label: string; value: number; step?: number; min?: number; max?: number; defaultVal?: number; desc?: string; onChange: (v: number) => void;
}) {
  const isDefault = defaultVal !== undefined && value === defaultVal;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 8 }}>
      <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 10, fontWeight: 600, color: 'var(--t-muted)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ color: 'var(--t-bright)' }}>{label}</span>
          {desc && <span style={{ fontSize: 9, fontWeight: 400, color: 'var(--t-dim)' }}>{desc}</span>}
        </div>
        <input
          type="number" value={value} step={step} min={min} max={max}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          style={{
            width: 68, 
            background: isDefault ? 'rgba(32, 144, 240, 0.1)' : 'var(--t-bg)', 
            border: isDefault ? '1px solid rgba(32, 144, 240, 0.3)' : '1px solid var(--t-border)',
            borderRadius: 5, 
            color: isDefault ? 'var(--t-blue)' : 'var(--t-bright)', 
            fontFamily: 'inherit', fontSize: 10,
            padding: '3px 6px', textAlign: 'right',
            transition: 'all 0.15s ease',
          }}
        />
      </label>
      {defaultVal !== undefined && !isDefault && (
        <div style={{ fontSize: 9, color: 'var(--t-muted)', textAlign: 'right', paddingRight: 2, fontStyle: 'italic', opacity: 0.8 }}>
          Factory Default: {defaultVal}
        </div>
      )}
    </div>
  );
}

function ChipToggle({ label, on, onChange, color }: { label: string; on: boolean; onChange: (v: boolean) => void; color?: string }) {
  const chC = on ? (color || 'var(--t-green)') : 'var(--t-dim)';
  return (
    <button onClick={() => onChange(!on)} style={{
      fontSize: 9, fontWeight: 800, letterSpacing: '0.06em', padding: '3px 8px',
      borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontFamily: 'inherit',
      border: `1px solid ${on ? alpha(chC, 0.27) : 'var(--t-border)'}`,
      background: on ? alpha(chC, 0.13) : 'transparent',
      color: chC, transition: 'all .1s', whiteSpace: 'nowrap', textTransform: 'uppercase',
    }}>{on ? '● ' : '○ '}{label}</button>
  );
}

function CheckField({ label, on, desc, onChange }: { label: string; on: boolean; desc?: string; onChange: (v: boolean) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, cursor: 'pointer', fontSize: 10, color: 'var(--t-bright)', marginBottom: 8 }}>
      <input type="checkbox" checked={on} onChange={(e) => onChange(e.target.checked)} style={{ marginTop: 2 }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontWeight: 600 }}>{label}</span>
        {desc && <span style={{ fontSize: 9, fontWeight: 400, color: 'var(--t-dim)' }}>{desc}</span>}
      </div>
    </label>
  );
}

/* ── Main Component ──────────────────────────────────────────────────────── */

const DEFAULT_CONFIG = {
  dsr_threshold: 0.85,
  p_loss_max: 15,
  wfa_consistency: 60,
  enable_auto_arbitration: true,
  strict_pearson_dedup: true,
  direction_allow_long: true,
  direction_allow_short: true,
  macro_trend_filter: true,
  risk_percent: 1.0,
  max_position_pct: 10,
  min_rr: 1.5,
  max_stop_atr: 3.0,
  account_equity: 10000,
  symbols: ['BTC', 'ETH', 'SOL', 'XRP'] as string[],
  disabled_symbols: [] as string[],
};

const CORE_SYMBOLS = ['BTC', 'ETH', 'SOL', 'XRP'];
const UNIVERSE = ['BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'AVAX', 'LINK', 'DOGE', 'MATIC'];

export function GrokSettingsPane() {
  const [draft, setDraft] = useState(DEFAULT_CONFIG);
  const [saving, setSaving] = useState(false);

  const stableStringify = (obj: any): string => {
    if (obj === null || typeof obj !== 'object') return JSON.stringify(obj);
    if (Array.isArray(obj)) return `[${obj.map(stableStringify).join(',')}]`;
    return `{${Object.keys(obj).sort().map(k => `"${k}":${stableStringify(obj[k])}`).join(',')}}`;
  };

  // We are dirty if draft does not equal the "saved" configuration.
  // For UI parity, we compare draft directly to DEFAULT_CONFIG since we are just mocking the save.
  // Ideally this would compare against a loaded `cfg` prop.
  const dirty = stableStringify(draft) !== stableStringify(DEFAULT_CONFIG);

  const onSave = () => {
    setSaving(true);
    setTimeout(() => {
      // Typically this would save to the backend. We'll just reset the dirty state for now by updating the "saved" config.
      // Since DEFAULT_CONFIG is static here, the UI will always show dirty if you change from defaults.
      // But we simulate the loading state to match ScalpingTab parity.
      setSaving(false);
    }, 500);
  };

  const setField = <K extends keyof typeof DEFAULT_CONFIG>(k: K, v: typeof DEFAULT_CONFIG[K]) => {
    setDraft(d => ({ ...d, [k]: v }));
  };

  const selSet = new Set(draft.symbols);
  const disabledSet = new Set(draft.disabled_symbols);

  const toggleSym = (s: string) => setDraft((d) => {
    const cur = new Set(d.symbols);
    if (cur.has(s)) cur.delete(s); else cur.add(s);
    return { ...d, symbols: [...cur] };
  });

  const toggleCore = (s: string) => setDraft((d) => {
    const dis = new Set(d.disabled_symbols);
    const syms = new Set(d.symbols);
    const active = syms.has(s) && !dis.has(s);
    if (active) {
      dis.add(s);
    } else {
      dis.delete(s);
      if (d.symbols.length > 0) syms.add(s);
    }
    return { ...d, symbols: [...syms], disabled_symbols: [...dis] };
  });

  const grpBox: React.CSSProperties = {
    background: 'var(--t-bg)', border: '1px solid var(--t-border)',
    borderRadius: 6, padding: '12px 14px',
  };
  const grpTitle: React.CSSProperties = {
    fontSize: 9, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-muted)',
    marginBottom: 12, borderBottom: '1px solid var(--t-border)', paddingBottom: 6,
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      
      {/* ── HEADER ACTIONS (DEFAULTS / SAVED) ── */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6, padding: '0 4px' }}>
        <button
          disabled={saving}
          title="Reset every field to the validated factory defaults. Review, then APPLY to save."
          onClick={() => setDraft(DEFAULT_CONFIG)}
          style={{
            fontSize: 9, fontWeight: 700, padding: '4px 12px', borderRadius: 5, fontFamily: 'inherit',
            cursor: !saving ? 'pointer' : 'default',
            border: '1px solid var(--t-border)', background: 'transparent', color: 'var(--t-dim)',
          }}>↺ DEFAULTS</button>
        <button disabled={!dirty || saving} onClick={onSave} style={{
          fontSize: 9, fontWeight: 700, padding: '4px 14px', borderRadius: 5, fontFamily: 'inherit',
          cursor: dirty && !saving ? 'pointer' : 'default',
          border: `1px solid ${dirty ? 'var(--t-green)' : 'var(--t-border)'}`,
          background: dirty ? 'var(--t-green)22' : 'transparent',
          color: dirty ? 'var(--t-green)' : 'var(--t-dim)',
        }}>{saving ? 'SAVING…' : dirty ? 'APPLY' : 'SAVED'}</button>
      </div>

      <SectionCard title="GROK ENGINE">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '4px 0' }}>
          <NumField 
            label="DSR Threshold" 
            desc="Minimum Directional Strength Ratio (0-1) required to arm a signal."
            value={draft.dsr_threshold} step={0.01} min={0.5} max={1.0} 
            defaultVal={DEFAULT_CONFIG.dsr_threshold} onChange={v => setField('dsr_threshold', v)} 
          />
          <NumField 
            label="P(Loss) Max" 
            desc="Maximum allowable probability of loss (%) from deep learning projections."
            value={draft.p_loss_max} step={1} min={1} max={50} 
            defaultVal={DEFAULT_CONFIG.p_loss_max} onChange={v => setField('p_loss_max', v)} 
          />
          <NumField 
            label="WFA Consistency" 
            desc="Minimum Walk-Forward Analysis score (0-100) across historical windows."
            value={draft.wfa_consistency} step={1} min={10} max={100} 
            defaultVal={DEFAULT_CONFIG.wfa_consistency} onChange={v => setField('wfa_consistency', v)} 
          />
        </div>
      </SectionCard>
      
      <SectionCard title="ROBUSTNESS GATES">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '4px 0' }}>
          <CheckField 
            label="Enable Auto-Arbitration" 
            desc="Allows the engine to autonomously execute signals that cross all statistical thresholds."
            on={draft.enable_auto_arbitration} onChange={v => setField('enable_auto_arbitration', v)} 
          />
          <CheckField 
            label="Strict Pearson De-duplication" 
            desc="Prevents opening multiple highly-correlated trades on the same statistical factor (e.g., blocks an ETH short if a BTC short is active)."
            on={draft.strict_pearson_dedup} onChange={v => setField('strict_pearson_dedup', v)} 
          />
        </div>
      </SectionCard>

      <div style={grpBox}>
        <div style={grpTitle}>DIRECTION & RISK</div>
        <div style={{ display: 'flex', gap: 5, marginBottom: 12, flexWrap: 'wrap' }}>
          <ChipToggle label="Long" on={draft.direction_allow_long} onChange={(v) => setField('direction_allow_long', v)} />
          <ChipToggle label="Short" on={draft.direction_allow_short} onChange={(v) => setField('direction_allow_short', v)} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <NumField label="Risk % / trade" value={draft.risk_percent} step={0.05} min={0.05} max={5} defaultVal={DEFAULT_CONFIG.risk_percent} onChange={(v) => setField('risk_percent', v)} />
          <NumField label="Max position %" value={draft.max_position_pct} step={1} min={1} max={100} defaultVal={DEFAULT_CONFIG.max_position_pct} onChange={(v) => setField('max_position_pct', v)} />
          <NumField label="Min R:R" value={draft.min_rr} step={0.1} min={0.5} max={10.0} defaultVal={DEFAULT_CONFIG.min_rr} onChange={(v) => setField('min_rr', v)} />
          <NumField label="Max Stop ATR" value={draft.max_stop_atr} step={0.5} min={1.0} max={20.0} defaultVal={DEFAULT_CONFIG.max_stop_atr} onChange={(v) => setField('max_stop_atr', v)} />
          <NumField label="Equity $" value={draft.account_equity} step={1000} min={100} defaultVal={DEFAULT_CONFIG.account_equity} onChange={(v) => setField('account_equity', v)} />
        </div>
      </div>
      
      <div style={grpBox}>
        <div style={grpTitle}>SYMBOLS (Global)</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, maxHeight: 160, overflowY: 'auto', paddingRight: 4, flexShrink: 0, marginTop: 4 }}>
          {draft.symbols.length === 0 ? (
            <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>Scanning ALL symbols. Add a symbol to restrict scanning.</span>
          ) : (
            <>
              {/* Core symbols: always shown, not deletable, toggle on/off */}
              {CORE_SYMBOLS.map((s) => (
                <ChipToggle
                  key={s}
                  label={s}
                  on={selSet.has(s) && !disabledSet.has(s)}
                  color="var(--t-blue)"
                  onChange={() => toggleCore(s)}
                />
              ))}
              {/* Optional symbols: click × to remove */}
              {draft.symbols.filter((s) => !CORE_SYMBOLS.includes(s)).map((s) => (
                <button
                  key={s}
                  onClick={() => toggleSym(s)}
                  style={{
                    fontSize: 9, fontWeight: 800, letterSpacing: '0.06em', padding: '3px 8px',
                    borderRadius: 'var(--radius-sm)', fontFamily: 'inherit',
                    background: 'var(--t-blue)15',
                    border: '1px solid var(--t-blue)44',
                    color: 'var(--t-dim)',
                    cursor: 'pointer', whiteSpace: 'nowrap', textTransform: 'uppercase'
                  }}
                  title="Click to remove"
                >
                  {s} <span style={{ marginLeft: 4, opacity: 0.6 }}>×</span>
                </button>
              ))}
            </>
          )}
        </div>

        <div style={{ marginTop: 12 }}>
          <select
            value=""
            onChange={(e) => {
              if (e.target.value) toggleSym(e.target.value);
            }}
            style={{
              width: '100%', background: 'var(--t-bg)', border: '1px solid var(--t-border)',
              borderRadius: 4, color: 'var(--t-dim)', padding: '6px 8px',
              fontFamily: 'inherit', fontSize: 11, cursor: 'pointer', outline: 'none'
            }}
          >
            <option value="" disabled>+ Search & Add optional symbols...</option>
            {UNIVERSE.filter(s => !selSet.has(s) && !CORE_SYMBOLS.includes(s)).map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

    </div>
  );
}
