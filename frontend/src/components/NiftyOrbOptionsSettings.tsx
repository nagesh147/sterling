import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

interface OrbConfig {
  enabled: boolean;
  underlying: string;
  interval_minutes: number;
  opening_range_minutes: number;
  entry_start: string;
  entry_end: string;
  min_breakout_atr: number;
  volume_multiplier: number;
  vwap_slope_lookback: number;
  trend_lookback: number;
  atr_period: number;
  stop_buffer_atr: number;
  trail_atr: number;
  target_r: number;
  option_moneyness: string;
  option_steps_itm: number;
  max_risk_inr: number;
  max_trades_per_day: number;
  avoid_expiry_day: boolean;
  expiry_selection: string;
  execution_broker: string;
  data_source: 'kite' | 'truedata';
}

const inputStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', background: 'var(--t-bg)', color: 'var(--t-bright)',
  border: '1px solid var(--t-border)', borderRadius: 6, padding: '7px 10px', fontFamily: 'monospace', fontSize: 12,
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <div style={{ marginBottom: 24 }}><div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}><span style={{ fontSize: 10, fontWeight: 500, letterSpacing: '0.14em', color: 'var(--t-bright)', textTransform: 'uppercase' }}>{title}</span><div style={{ flex: 1, height: 1, background: 'var(--t-border)' }} /></div>{children}</div>;
}

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return <div style={{ marginBottom: 12 }}><div style={{ fontSize: 9, fontWeight: 500, color: 'var(--t-dim)', letterSpacing: '0.08em', marginBottom: 4, textTransform: 'uppercase' }}>{label}</div>{children}{hint && <div style={{ fontSize: 9, color: 'var(--t-dim)', marginTop: 4 }}>{hint}</div>}</div>;
}

export function NiftyOrbOptionsSettings() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<{ config: OrbConfig }>({
    queryKey: ['nifty-orb-options-config'],
    queryFn: () => api.get('/api/v1/config/nifty-orb-options'),
    staleTime: 30_000,
  });
  const [draft, setDraft] = React.useState<Partial<OrbConfig>>({});
  const cfg = { ...(data?.config || {}), ...draft } as OrbConfig;
  const update = useMutation({
    mutationFn: (body: Partial<OrbConfig>) => api.put('/api/v1/config/nifty-orb-options', body),
    onSuccess: result => { qc.setQueryData(['nifty-orb-options-config'], result); setDraft({}); },
  });

  if (isLoading || !data) return <div style={{ color: 'var(--t-dim)', fontSize: 10 }}>Loading NIFTY ORB configuration…</div>;
  const set = (key: keyof OrbConfig, value: unknown) => setDraft(d => ({ ...d, [key]: value }));
  const dirty = Object.keys(draft).length > 0;

  return <>
    <Section title="NIFTY ORB + VWAP OPTIONS">
      <div style={{ padding: '10px 12px', background: 'var(--t-bg2)', border: '1px solid var(--t-border)', borderRadius: 5, marginBottom: 14, fontSize: 10, color: 'var(--t-dim)', lineHeight: 1.6 }}>
        Signal is generated from NIFTY 50. CE/PE is the execution vehicle. Data source affects market data only; execution remains Zerodha Kite. Paper/Live and Manual/Auto are controlled by the universal Trading Mode panel.
      </div>
      <Field label="STRATEGY"><button onClick={() => set('enabled', !cfg.enabled)} style={{ ...inputStyle, textAlign: 'left', color: cfg.enabled ? 'var(--t-green)' : 'var(--t-dim)', cursor: 'pointer' }}>{cfg.enabled ? 'ON — SIGNAL ENGINE ACTIVE' : 'OFF — DISABLED'}</button></Field>
      <Field label="DATA SOURCE" hint="Default: Zerodha Kite"><select value={cfg.data_source} onChange={e => set('data_source', e.target.value)} style={inputStyle}><option value="kite">Zerodha Kite</option><option value="truedata">TrueData</option></select></Field>
      <Field label="INTERVAL"><select value={cfg.interval_minutes} onChange={e => set('interval_minutes', Number(e.target.value))} style={inputStyle}>{[1,3,5,10,15].map(v => <option key={v} value={v}>{v} minute</option>)}</select></Field>
      <Field label="OPENING RANGE"><select value={cfg.opening_range_minutes} onChange={e => set('opening_range_minutes', Number(e.target.value))} style={inputStyle}>{[5,10,15,20,30].map(v => <option key={v} value={v}>{v} minutes</option>)}</select></Field>
      <Field label="ENTRY WINDOW"><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}><input type="time" value={cfg.entry_start} onChange={e => set('entry_start', e.target.value)} style={inputStyle}/><input type="time" value={cfg.entry_end} onChange={e => set('entry_end', e.target.value)} style={inputStyle}/></div></Field>
    </Section>

    <Section title="SIGNAL FILTERS">
      <Field label="MIN BREAKOUT / ATR"><input type="number" step="0.05" value={cfg.min_breakout_atr} onChange={e => set('min_breakout_atr', Number(e.target.value))} style={inputStyle}/></Field>
      <Field label="VOLUME MULTIPLIER"><input type="number" step="0.05" value={cfg.volume_multiplier} onChange={e => set('volume_multiplier', Number(e.target.value))} style={inputStyle}/></Field>
      <Field label="ATR PERIOD"><input type="number" min={5} max={100} value={cfg.atr_period} onChange={e => set('atr_period', Number(e.target.value))} style={inputStyle}/></Field>
      <Field label="TARGET (R)"><input type="number" step="0.25" min={0.5} value={cfg.target_r} onChange={e => set('target_r', Number(e.target.value))} style={inputStyle}/></Field>
    </Section>

    <Section title="OPTION + RISK">
      <Field label="OPTION MONEINESS"><select value={cfg.option_moneyness} onChange={e => set('option_moneyness', e.target.value)} style={inputStyle}><option value="ATM">ATM</option><option value="ITM">ITM</option></select></Field>
      {cfg.option_moneyness === 'ITM' && <Field label="ITM STEPS"><input type="number" min={1} max={3} value={cfg.option_steps_itm} onChange={e => set('option_steps_itm', Number(e.target.value))} style={inputStyle}/></Field>}
      <Field label="MAX RISK / TRADE (INR)"><input type="number" step="500" min={500} value={cfg.max_risk_inr} onChange={e => set('max_risk_inr', Number(e.target.value))} style={inputStyle}/></Field>
      <Field label="MAX TRADES / DAY"><input type="number" min={1} max={10} value={cfg.max_trades_per_day} onChange={e => set('max_trades_per_day', Number(e.target.value))} style={inputStyle}/></Field>
      <Field label="EXPIRY DAY"><button onClick={() => set('avoid_expiry_day', !cfg.avoid_expiry_day)} style={{ ...inputStyle, textAlign: 'left', cursor: 'pointer', color: cfg.avoid_expiry_day ? 'var(--t-green)' : 'var(--t-dim)' }}>{cfg.avoid_expiry_day ? 'AVOID' : 'ALLOW'}</button></Field>
    </Section>

    <Section title="EXECUTION">
      <Field label="BROKER"><input value="ZERODHA KITE" readOnly style={{ ...inputStyle, color: 'var(--t-blue)' }}/></Field>
      <div style={{ fontSize: 9, color: 'var(--t-dim)', lineHeight: 1.6 }}>This strategy does not own an execution-mode switch. The active Kite account's universal Paper/Live setting determines where orders go, while the universal Manual/Auto setting determines who places them.</div>
    </Section>

    <button onClick={() => update.mutate(draft)} disabled={!dirty || update.isPending} style={{ width: '100%', padding: '9px 0', borderRadius: 5, border: '1px solid var(--t-border)', background: dirty ? 'var(--t-bg2)' : 'transparent', color: dirty ? 'var(--t-bright)' : 'var(--t-dim)', cursor: dirty ? 'pointer' : 'not-allowed', fontFamily: 'inherit', fontSize: 10, fontWeight: 600, letterSpacing: '0.1em' }}>{update.isPending ? 'SAVING…' : dirty ? 'SAVE NIFTY ORB SETTINGS' : 'SAVED'}</button>
    {update.isError && <div style={{ marginTop: 8, color: 'var(--t-red)', fontSize: 10 }}>{(update.error as Error).message}</div>}
  </>;
}
