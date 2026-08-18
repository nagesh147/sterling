import React, { useEffect, useState } from 'react';
import { useOrbMomentumOptionsConfig, useSetOrbMomentumOptionsConfig, type OrbConfig } from '../../hooks/useOrbMomentumOptions';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#fff', border: '1px solid #e0e0e0', borderRadius: 9, padding: 18, marginBottom: 16 },
  title: { color: '#444', fontSize: 12, letterSpacing: .7, marginBottom: 14, fontWeight: 750 },
  section: { borderTop: '1px solid #eee', paddingTop: 14, marginTop: 14 },
  label: { color: '#777', fontSize: 10, letterSpacing: .55, fontWeight: 650, display: 'block', marginBottom: 5 },
  input: { minHeight: 34, background: '#fff', color: '#444', border: '1px solid #dcdcdc', borderRadius: 6, padding: '0 9px', fontFamily: 'inherit', fontSize: 11, width: '100%', boxSizing: 'border-box' as const },
  select: { minHeight: 34, background: '#fff', color: '#444', border: '1px solid #dcdcdc', borderRadius: 6, padding: '0 8px', fontFamily: 'inherit', fontSize: 11, width: '100%' },
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label style={S.label}>{label}</label>{children}</div>;
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 11, color: '#555', cursor: 'pointer' }}><input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />{label}</label>;
}

export function OrbMomentumOptionsSettingsPanel() {
  const q = useOrbMomentumOptionsConfig();
  const save = useSetOrbMomentumOptionsConfig();
  const [draft, setDraft] = useState<OrbConfig | null>(null);
  useEffect(() => { if (q.data?.config) setDraft(q.data.config); }, [q.data]);
  if (!draft) return <div style={S.card}>{q.isError ? 'Unable to load ORB Momentum Options settings.' : 'Loading ORB Momentum Options settings…'}</div>;
  const set = <K extends keyof OrbConfig>(key: K, value: OrbConfig[K]) => setDraft(d => d ? ({ ...d, [key]: value }) : d);
  const dirty = JSON.stringify(draft) !== JSON.stringify(q.data?.config);
  const saveDraft = () => save.mutate({ ...draft, instruments: draft.instruments });

  return <div style={S.card}>
    <div style={{ ...S.title, display: 'flex', alignItems: 'center' }}>
      <span>ORB MOMENTUM OPTIONS</span>
      <span style={{ marginLeft: 'auto', fontSize: 9, color: '#999' }}>BUY OPTIONS ONLY</span>
    </div>

    <div style={{ display: 'grid', gap: 12 }}>
      <Check label="Enable strategy" checked={draft.enabled} onChange={v => set('enabled', v)} />
      <div style={S.section}>
        <div style={S.title}>MARKET DATA & UNIVERSE</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <Field label="Data source"><select style={S.select} value={draft.data_source} onChange={e => set('data_source', e.target.value as OrbConfig['data_source'])}><option value="kite">Zerodha Kite</option><option value="truedata">TrueData</option></select></Field>
          <Field label="Universe"><select style={S.select} value={draft.universe} onChange={e => set('universe', e.target.value)}><option value="FNO">F&O</option><option value="INDEX">Indices only</option><option value="STOCK">F&O stocks only</option></select></Field>
          <Field label="Instrument types"><select style={S.select} value={draft.instrument_types.join(',')} onChange={e => set('instrument_types', e.target.value.split(',').map(x => x.trim()).filter(Boolean))}><option value="INDEX,STOCK">Indices + Stocks</option><option value="INDEX">Indices</option><option value="STOCK">Stocks</option></select></Field>
          <Field label="Selected instruments"><input style={S.input} value={draft.instruments.join(', ')} placeholder="All F&O (blank) or RELIANCE, SBIN" onChange={e => set('instruments', e.target.value.split(',').map(x => x.trim().toUpperCase()).filter(Boolean))} /></Field>
        </div>
      </div>

      <div style={S.section}>
        <div style={S.title}>OPTION CONTRACT SELECTION</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <Field label="Expiry"><select style={S.select} value={draft.expiry_preference} onChange={e => set('expiry_preference', e.target.value as OrbConfig['expiry_preference'])}><option value="NEAREST">Nearest</option><option value="WEEKLY">Weekly</option><option value="MONTHLY">Monthly</option><option value="DTE_RANGE">DTE range</option></select></Field>
          <Field label="Strike"><select style={S.select} value={draft.option_moneyness} onChange={e => set('option_moneyness', e.target.value as OrbConfig['option_moneyness'])}><option value="ATM">ATM</option><option value="ITM">ITM</option></select></Field>
          <Field label="Minimum DTE"><input style={S.input} type="number" min={0} value={draft.expiry_dte_min} onChange={e => set('expiry_dte_min', Number(e.target.value))} /></Field>
          <Field label="Maximum DTE"><input style={S.input} type="number" min={0} value={draft.expiry_dte_max} onChange={e => set('expiry_dte_max', Number(e.target.value))} /></Field>
          <Field label="ITM steps"><input style={S.input} type="number" min={1} value={draft.option_steps_itm} onChange={e => set('option_steps_itm', Number(e.target.value))} /></Field>
          <div style={{ display: 'flex', alignItems: 'end', paddingBottom: 5 }}><Check label="Avoid expiry day" checked={draft.avoid_expiry_day} onChange={v => set('avoid_expiry_day', v)} /></div>
        </div>
        <div style={{ marginTop: 10, padding: '8px 10px', border: '1px solid #e7e7e7', borderRadius: 6, color: '#777', fontSize: 10 }}>
          Directional mapping is fixed: bullish underlying → <b>BUY CE</b>; bearish underlying → <b>BUY PE</b>. Option selling is not supported by this strategy.
        </div>
      </div>

      <div style={S.section}>
        <div style={S.title}>ORB & ENTRY</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          <Field label="Interval"><input style={S.input} type="number" min={1} value={draft.interval_minutes} onChange={e => set('interval_minutes', Number(e.target.value))} /></Field>
          <Field label="Opening range (min)"><input style={S.input} type="number" min={5} value={draft.opening_range_minutes} onChange={e => set('opening_range_minutes', Number(e.target.value))} /></Field>
          <Field label="Entry start"><input style={S.input} type="time" value={draft.entry_start} onChange={e => set('entry_start', e.target.value)} /></Field>
          <Field label="Entry end"><input style={S.input} type="time" value={draft.entry_end} onChange={e => set('entry_end', e.target.value)} /></Field>
        </div>
      </div>

      <div style={S.section}>
        <div style={S.title}>RISK & LIMITS</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
          <Field label="Max risk / trade (₹)"><input style={S.input} type="number" min={1} value={draft.max_risk_inr} onChange={e => set('max_risk_inr', Number(e.target.value))} /></Field>
          <Field label="Max trades / day"><input style={S.input} type="number" min={1} value={draft.max_trades_per_day} onChange={e => set('max_trades_per_day', Number(e.target.value))} /></Field>
          <Field label="Max signals / day"><input style={S.input} type="number" min={1} value={draft.max_signals_per_day} onChange={e => set('max_signals_per_day', Number(e.target.value))} /></Field>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
        <button disabled={!dirty || save.isPending} onClick={saveDraft} style={{ minHeight: 34, background: dirty ? '#f06428' : '#f3f3f3', color: dirty ? '#fff' : '#999', border: '1px solid #ddd', borderRadius: 6, padding: '0 14px', cursor: dirty ? 'pointer' : 'default', fontWeight: 700, fontFamily: 'inherit', fontSize: 11 }}>{save.isPending ? 'Saving…' : 'APPLY'}</button>
        {save.isSuccess && <span style={{ fontSize: 10, color: '#4caf50' }}>Saved</span>}
        {save.isError && <span style={{ fontSize: 10, color: '#c9433e' }}>Save failed</span>}
      </div>
    </div>
  </div>;
}
