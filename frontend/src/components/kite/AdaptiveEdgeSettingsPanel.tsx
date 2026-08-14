import React from 'react';
import { Section, inputStyle, MUTED, TEXT } from './kiteSettingsPrimitives';
import { EnginePowerHeader } from './config/EnginePowerHeader';
import { SettingsDraftBar } from './config/ConfigPrimitives';
import { useAdaptiveEdgeSettings, useAdaptiveEdgeSnapshot, useSetAdaptiveEdgeSettings } from '../../hooks/useAdaptiveEdge';
import type { AdaptiveEdgeSettings } from '../../types/adaptiveEdge';

function Field({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 140 }}>
      <span style={{ fontSize: 11, fontWeight: 650, color: TEXT }}>{label}</span>
      {children}
      <span style={{ fontSize: 10, color: MUTED, lineHeight: 1.4 }}>{hint}</span>
    </label>
  );
}

function saveError(draft: AdaptiveEdgeSettings): string | null {
  if (draft.w_short >= draft.w_long) return 'W short must be less than W long.';
  if (!(draft.scalp_favorable_points <= draft.extended_favorable_points && draft.extended_favorable_points <= draft.intraday_favorable_points)) {
    return 'Mode rungs must be non-decreasing: scalp ≤ extended ≤ intraday.';
  }
  return null;
}

export function AdaptiveEdgeSettingsPanel() {
  const { data, isLoading, error } = useAdaptiveEdgeSettings();
  const snapshot = useAdaptiveEdgeSnapshot();
  const save = useSetAdaptiveEdgeSettings();
  const [draft, setDraft] = React.useState<AdaptiveEdgeSettings | null>(null);
  const [dirty, setDirty] = React.useState(false);

  React.useEffect(() => {
    if (data && !dirty) setDraft(data.settings);
  }, [data, dirty]);

  if (isLoading || !draft) {
    return <div style={{ padding: 18, color: MUTED, fontSize: 12 }}>Loading Adaptive Edge settings…</div>;
  }
  if (error) {
    return <div style={{ padding: 18, color: '#c9433e', fontSize: 12 }}>Failed to load Adaptive Edge settings.</div>;
  }

  const patch = (partial: Partial<AdaptiveEdgeSettings>) => {
    setDraft({ ...draft, ...partial });
    setDirty(true);
  };
  const invalid = saveError(draft);

  return (
    <>
      <SettingsDraftBar
        dirty={dirty}
        saving={save.isPending}
        onApply={() => { if (!invalid) save.mutate(draft, { onSuccess: () => setDirty(false) }); }}
        onDiscard={() => { if (data) { setDraft(data.settings); setDirty(false); } }}
        onReset={() => { if (data) { setDraft(data.settings); setDirty(false); } }}
      />
      <EnginePowerHeader
        name="Adaptive Edge"
        tagline="Score, modes, protection and structure."
        on={draft.enabled}
        liveOn={!!data?.settings.enabled}
        busy={save.isPending}
        onToggle={() => patch({ enabled: !draft.enabled })}
        runningNote="The Adaptive Edge board is on."
        offNote="The Adaptive Edge board is off. The last snapshot can still be inspected."
      />

      {invalid && (
        <div style={{ margin: '0 0 16px', padding: '10px 12px', borderRadius: 8, background: '#fff6f5', border: '1px solid #f0d2c2', color: '#c9433e', fontSize: 12, lineHeight: 1.5 }}>
          {invalid}
        </div>
      )}

      <Section title="Instrument & windows" description="Trial F-101 lookbacks. Not a production freeze." summary={`${draft.symbol} · ${draft.w_short}/${draft.w_long}`} persistKey="ae-windows" defaultOpen>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', padding: '4px 2px 10px' }}>
          <Field label="Symbol" hint="TrueData symbol, usually NIFTY-I.">
            <input style={{ ...inputStyle, width: 120 }} value={draft.symbol} onChange={(e) => patch({ symbol: e.target.value })} />
          </Field>
          <Field label="W short" hint="Volatility short window.">
            <input style={inputStyle} type="number" value={draft.w_short} onChange={(e) => patch({ w_short: Number(e.target.value) })} />
          </Field>
          <Field label="W long" hint="Must be greater than W short.">
            <input style={inputStyle} type="number" value={draft.w_long} onChange={(e) => patch({ w_long: Number(e.target.value) })} />
          </Field>
        </div>
      </Section>

      <Section title="Structure" description="Session profile bin and opening-range window. Research convention, not a recovered F-formula." summary={`${draft.tick_size} pt · IB ${draft.ib_minutes}m`} persistKey="ae-structure">
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', padding: '4px 2px 10px' }}>
          <Field label="Tick size" hint="Profile bin size in points.">
            <input style={inputStyle} type="number" value={draft.tick_size} onChange={(e) => patch({ tick_size: Number(e.target.value) })} />
          </Field>
          <Field label="IB minutes" hint="Opening-range / initial balance.">
            <input style={inputStyle} type="number" value={draft.ib_minutes} onChange={(e) => patch({ ib_minutes: Number(e.target.value) })} />
          </Field>
        </div>
      </Section>

      <Section title="Protection policy" description="Explicit A177 distances. Not recovered F-112." summary={`${draft.stop_points} / ${draft.trail_points} / ${draft.profit_lock_activation_points}`} persistKey="ae-protection">
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', padding: '4px 2px 10px' }}>
          <Field label="Stop points" hint="Hard stop from entry.">
            <input style={inputStyle} type="number" value={draft.stop_points} onChange={(e) => patch({ stop_points: Number(e.target.value) })} />
          </Field>
          <Field label="Trail points" hint="Behind the best price.">
            <input style={inputStyle} type="number" value={draft.trail_points} onChange={(e) => patch({ trail_points: Number(e.target.value) })} />
          </Field>
          <Field label="Lock arm" hint="Profit before lock turns on.">
            <input style={inputStyle} type="number" value={draft.profit_lock_activation_points} onChange={(e) => patch({ profit_lock_activation_points: Number(e.target.value) })} />
          </Field>
          <Field label="Lock offset" hint="Kept off the extreme.">
            <input style={inputStyle} type="number" value={draft.profit_lock_offset_points} onChange={(e) => patch({ profit_lock_offset_points: Number(e.target.value) })} />
          </Field>
        </div>
      </Section>

      <Section title="Mode rungs" description="MICRO to SCALP to EXTENDED_SCALP to INTRADAY. Explicit research policy, not learned F-104." summary={`${draft.persistence_bars} bars · ${draft.scalp_favorable_points}/${draft.extended_favorable_points}/${draft.intraday_favorable_points}`} persistKey="ae-modes">
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', padding: '4px 2px 10px' }}>
          <Field label="Persistence bars" hint="Hysteresis before a mode change.">
            <input style={inputStyle} type="number" value={draft.persistence_bars} onChange={(e) => patch({ persistence_bars: Number(e.target.value) })} />
          </Field>
          <Field label="Scalp +" hint="Favorable points for SCALP.">
            <input style={inputStyle} type="number" value={draft.scalp_favorable_points} onChange={(e) => patch({ scalp_favorable_points: Number(e.target.value) })} />
          </Field>
          <Field label="Extended +" hint="Favorable points for EXTENDED_SCALP.">
            <input style={inputStyle} type="number" value={draft.extended_favorable_points} onChange={(e) => patch({ extended_favorable_points: Number(e.target.value) })} />
          </Field>
          <Field label="Intraday +" hint="Favorable points for INTRADAY.">
            <input style={inputStyle} type="number" value={draft.intraday_favorable_points} onChange={(e) => patch({ intraday_favorable_points: Number(e.target.value) })} />
          </Field>
        </div>
      </Section>

      <Section
        title="Readiness"
        description="Live snapshot of what the research path has and what stays blocked."
        summary={snapshot.data?.software_complete ? 'software complete · gate blocked' : 'waiting on snapshot'}
        persistKey="ae-readiness"
      >
        <div style={{ padding: '4px 2px 10px', display: 'grid', gap: 6 }}>
          {(snapshot.data?.readiness ?? []).map((item) => (
            <div key={item.name} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12 }}>
              <span style={{ color: TEXT }}>{item.name.split('_').join(' ')}</span>
              <span style={{ color: item.ready ? '#2e7d32' : '#b85c00' }}>{item.ready ? 'ready' : 'blocked'}</span>
            </div>
          ))}
          {!snapshot.data && <div style={{ color: MUTED, fontSize: 12 }}>Snapshot not loaded yet.</div>}
        </div>
      </Section>
    </>
  );
}

export default AdaptiveEdgeSettingsPanel;
