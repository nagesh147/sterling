import React from 'react';
import {
  BORDER, CheckOption, ChoiceRow, DIM, Field, MUTED, ORANGE, Section, Switch, TEXT, inputStyle,
} from './kiteSettingsPrimitives';
import { Icons } from '../../styles/kiteUI';
import { useNavigatorConfig, useResetNavigatorConfig, useSetNavigatorConfig } from '../../hooks/useNavigator';
import type { AvwapGrade, NavigatorConfigModel, NavigatorOperatingMode } from '../../types/navigator';

const GREEN = '#4caf50';
const RED = '#df514c';
const AMBER = '#f5a623';

function NumField({ label, hint, value, onChange, step = 1, min, max }: {
  label: string; hint?: string; value: number; onChange: (v: number) => void;
  step?: number; min?: number; max?: number;
}) {
  return (
    <Field label={label} hint={hint}>
      <input
        type="number" value={Number.isFinite(value) ? value : 0} step={step} min={min} max={max}
        onChange={(e) => onChange(e.target.value === '' ? 0 : Number(e.target.value))}
        style={inputStyle} aria-label={label}
      />
    </Field>
  );
}

function BoolField({ label, hint, value, onChange }: { label: string; hint?: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <Field label={label} hint={hint}>
      <Switch checked={value} label={label} onChange={() => onChange(!value)} />
    </Field>
  );
}

function GradeField({ label, hint, value, onChange }: { label: string; hint?: string; value: AvwapGrade; onChange: (v: AvwapGrade) => void }) {
  return (
    <Field label={label} hint={hint}>
      <ChoiceRow<AvwapGrade> value={value} onChange={onChange} options={[
        { value: 'B', label: 'B' }, { value: 'A', label: 'A' }, { value: 'A+', label: 'A+' },
      ]} />
    </Field>
  );
}

function set<K extends keyof NavigatorConfigModel>(
  draft: NavigatorConfigModel, key: K, patch: Partial<NavigatorConfigModel[K]>,
): NavigatorConfigModel {
  return { ...draft, [key]: { ...(draft[key] as object), ...patch } };
}

export function NavigatorSettingsPanel() {
  const { data, isLoading, error: loadError } = useNavigatorConfig();
  const setConfig = useSetNavigatorConfig();
  const resetConfig = useResetNavigatorConfig();

  const [draft, setDraft] = React.useState<NavigatorConfigModel | null>(null);
  const [baseRevision, setBaseRevision] = React.useState<number | null>(null);
  const [dirty, setDirty] = React.useState(false);
  const [conflict, setConflict] = React.useState<boolean>(false);
  const [resetConfirm, setResetConfirm] = React.useState(false);

  React.useEffect(() => {
    if (!data) return;
    if (!dirty) {
      setDraft(data.record.config);
      setBaseRevision(data.record.revision);
      setConflict(false);
    }
  }, [data, dirty]);

  if (isLoading || !draft) {
    return <div style={{ padding: 18, color: DIM, fontSize: 12 }}>Loading Navigator configuration…</div>;
  }
  if (loadError) {
    return <div style={{ padding: 18, color: RED, fontSize: 12 }}>Failed to load Navigator configuration: {String(loadError)}</div>;
  }

  const record = data!.record;
  const gateReady = record.calibration_readiness === 'ready';

  const patch = (next: NavigatorConfigModel) => {
    setDraft(next);
    setDirty(true);
  };

  const handleApply = () => {
    if (baseRevision == null || !draft) return;
    setConfig.mutate({ config: draft, expected_revision: baseRevision }, {
      onSuccess: () => setDirty(false),
      onError: (err) => {
        if (String(err.message).includes('REVISION_CONFLICT')) setConflict(true);
      },
    });
  };

  const handleReload = () => {
    if (data) {
      setDraft(data.record.config);
      setBaseRevision(data.record.revision);
    }
    setDirty(false);
    setConflict(false);
  };

  const handleReset = () => {
    if (!resetConfirm) {
      setResetConfirm(true);
      return;
    }
    resetConfig.mutate(undefined, { onSuccess: () => { setDirty(false); setResetConfirm(false); } });
  };

  const saveError = setConfig.isError && !conflict ? String(setConfig.error?.message ?? 'save failed') : null;

  return (
    <section style={{ background: '#fff', border: `1px solid ${BORDER}`, borderRadius: 9, overflow: 'hidden', marginBottom: 16, boxShadow: '0 1px 2px rgba(0,0,0,.025)' }}>
      {/* ── top band ─────────────────────────────────────────────────────── */}
      <div style={{ padding: '16px 18px', borderBottom: `1px solid ${BORDER}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ color: TEXT, fontSize: 14.5, fontWeight: 800 }}>Value-Flow Navigator</div>
            <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.5, marginTop: 3 }}>
              Anchored VWAP structure, projected ranges, volatility regime, option flow, and gamma activity —
              fused into an auditable confirmation layer over the existing Sterling signal. Off by default.
            </div>
          </div>
          <Switch
            checked={draft.enabled}
            label="Enable Navigator"
            onChange={() => patch({ ...draft, enabled: !draft.enabled })}
          />
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 14, marginTop: 14 }}>
          <div>
            <div style={{ color: DIM, fontSize: 9.5, fontWeight: 700, textTransform: 'uppercase', marginBottom: 5 }}>Mode</div>
            <ChoiceRow<NavigatorOperatingMode>
              value={draft.operating_mode}
              onChange={(mode) => {
                if (mode === 'gate' && !gateReady) return;
                patch({ ...draft, operating_mode: mode });
              }}
              options={[
                { value: 'shadow', label: 'Shadow' },
                { value: 'advisory', label: 'Advisory' },
                { value: 'gate', label: gateReady ? 'Gate' : 'Gate (locked)' },
              ]}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: gateReady ? GREEN : DIM, fontSize: 10.5 }}>
            <Icons.Pulse />
            {gateReady ? 'Calibration ready' : 'Gate unavailable — not yet calibrated'}
          </div>
          <div style={{ color: DIM, fontSize: 10.5 }}>Revision {record.revision}</div>
          {draft.enabled && record.activation_watermark_ms > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: DIM, fontSize: 10.5 }}>
              <Icons.History />
              Active since {new Date(record.activation_watermark_ms).toLocaleString()}
            </div>
          )}
          <div style={{ flex: 1 }} />
          <span aria-live="polite" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: setConfig.isPending ? MUTED : dirty ? AMBER : GREEN, fontSize: 10.5, fontWeight: 700 }}>
            <span aria-hidden style={{ width: 6, height: 6, borderRadius: '50%', background: setConfig.isPending ? '#c2c2c2' : dirty ? AMBER : GREEN }} />
            {setConfig.isPending ? 'Saving…' : dirty ? 'Unsaved changes' : 'Saved'}
          </span>
        </div>

        {conflict && (
          <div style={{ marginTop: 10, padding: '9px 11px', borderRadius: 7, background: '#fff5f0', border: `1px solid #e2b6a4`, display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
            <Icons.Warning />
            <span style={{ flex: 1, color: TEXT }}>This config changed elsewhere (another tab, or a concurrent save). Your draft is preserved — reload to compare, or Apply again to overwrite.</span>
            <button type="button" onClick={handleReload} style={{ ...pillButtonStyle }}>Reload latest</button>
          </div>
        )}
        {saveError && (
          <div style={{ marginTop: 10, padding: '9px 11px', borderRadius: 7, background: '#fff0f0', border: `1px solid #e2a4a4`, color: RED, fontSize: 11, display: 'flex', gap: 8, alignItems: 'center' }}>
            <Icons.Warning /> {saveError}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <button type="button" onClick={handleApply} disabled={!dirty || setConfig.isPending} style={{ ...applyButtonStyle, opacity: !dirty || setConfig.isPending ? 0.5 : 1 }}>
            Apply changes
          </button>
          {dirty && (
            <button type="button" onClick={handleReload} style={pillButtonStyle}>Discard draft</button>
          )}
          <div style={{ flex: 1 }} />
          <button type="button" onClick={handleReset} style={{ ...pillButtonStyle, color: resetConfirm ? RED : MUTED }}>
            <Icons.Reload /> {resetConfirm ? 'Click again to confirm reset' : 'Reset to defaults'}
          </button>
        </div>
      </div>

      {/* ── 1. instruments and timing ───────────────────────────────────── */}
      <Section title="Instruments and timing" description="What Navigator scans and the base clock it runs on." summary={`${draft.underlyings.length} underlyings · ${draft.price_timeframe}`}>
        <Field label="Engine source" hint="This build is Kite-only — no other engine can be selected.">
          <CheckOption label="Kite triple-SuperTrend" checked disabled compact />
        </Field>
        <Field label="Underlyings" hint="Mirrors the Sterling Kite Engine's own scan universe.">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {draft.underlyings.map((u) => (
              <span key={u} style={{ padding: '4px 8px', borderRadius: 5, background: '#f6f6f7', border: `1px solid ${BORDER}`, fontSize: 10.5, color: TEXT }}>{u}</span>
            ))}
            {draft.underlyings.length === 0 && <span style={{ color: DIM, fontSize: 10.5 }}>None yet — configure the Kite engine's scan universe first.</span>}
          </div>
        </Field>
        <Field label="Price timeframe" hint="Read-only in v1 — must match the Kite base engine's 1H clock.">
          <div style={{ ...inputStyle, display: 'flex', alignItems: 'center', color: DIM, width: 'auto' }}>60 minute</div>
        </Field>
        <NumField label="Flow sample interval" hint="Seconds between option-chain samples (15–300)." value={draft.flow_sample_seconds} step={5} min={15} max={300} onChange={(v) => patch({ ...draft, flow_sample_seconds: v })} />
        <NumField label="Max feature age" hint="Seconds before cached evidence is treated as stale." value={draft.max_feature_age_seconds} step={10} min={10} max={3600} onChange={(v) => patch({ ...draft, max_feature_age_seconds: v })} />
        <NumField label="Event alignment window" hint="Bars of tolerance between a base-fresh and AVWAP-fresh trigger." value={draft.event_alignment_bars} step={1} min={0} max={20} onChange={(v) => patch({ ...draft, event_alignment_bars: v })} />
        <NumField label="Entry delay after open" hint="Minutes after the official session open before entries are considered." value={draft.entry_delay_after_open_minutes} step={1} min={0} max={60} onChange={(v) => patch({ ...draft, entry_delay_after_open_minutes: v })} />
      </Section>

      {/* ── 2. AVWAP ─────────────────────────────────────────────────────── */}
      <Section title="Anchored VWAP and signal grades" description="Structure, pullback/continuation signals, and grade thresholds." summary={draft.avwap.enabled ? 'Enabled' : 'Disabled'}>
        <BoolField label="Enabled" hint="Required for gate mode." value={draft.avwap.enabled} onChange={(v) => patch(set(draft, 'avwap', { enabled: v }))} />
        <NumField label="Pivot left bars" value={draft.avwap.pivot_left_bars} min={1} max={20} onChange={(v) => patch(set(draft, 'avwap', { pivot_left_bars: v }))} />
        <NumField label="Pivot right bars" value={draft.avwap.pivot_right_bars} min={1} max={20} onChange={(v) => patch(set(draft, 'avwap', { pivot_right_bars: v }))} />
        <NumField label="Slope lookback" value={draft.avwap.slope_lookback_bars} min={2} max={50} onChange={(v) => patch(set(draft, 'avwap', { slope_lookback_bars: v }))} />
        <NumField label="Min slope (ATR/bar)" value={draft.avwap.min_slope_atr_per_bar} step={0.01} min={0} max={2} onChange={(v) => patch(set(draft, 'avwap', { min_slope_atr_per_bar: v }))} />
        <NumField label="ATR period" value={draft.avwap.atr_period} min={5} max={100} onChange={(v) => patch(set(draft, 'avwap', { atr_period: v }))} />
        <NumField label="Relative volume period" value={draft.avwap.relative_volume_period} min={5} max={200} onChange={(v) => patch(set(draft, 'avwap', { relative_volume_period: v }))} />
        <NumField label="Touch tolerance (ATR)" value={draft.avwap.touch_tolerance_atr} step={0.01} min={0.01} max={1} onChange={(v) => patch(set(draft, 'avwap', { touch_tolerance_atr: v }))} />
        <NumField label="Min body (ATR)" value={draft.avwap.min_body_atr} step={0.01} min={0} max={3} onChange={(v) => patch(set(draft, 'avwap', { min_body_atr: v }))} />
        <NumField label="Min relative volume" value={draft.avwap.min_relative_volume} step={0.05} min={0} max={10} onChange={(v) => patch(set(draft, 'avwap', { min_relative_volume: v }))} />
        <NumField label="Breakout buffer (ATR)" value={draft.avwap.breakout_buffer_atr} step={0.01} min={0} max={2} onChange={(v) => patch(set(draft, 'avwap', { breakout_buffer_atr: v }))} />
        <NumField label="Max extension (ATR)" value={draft.avwap.max_extension_atr} step={0.05} min={0.25} max={10} onChange={(v) => patch(set(draft, 'avwap', { max_extension_atr: v }))} />
        <NumField label="Cooldown bars" value={draft.avwap.cooldown_bars} min={0} max={100} onChange={(v) => patch(set(draft, 'avwap', { cooldown_bars: v }))} />
        <NumField label="Grade A+ min" value={draft.avwap.grade_a_plus_min} min={0} max={100} onChange={(v) => patch(set(draft, 'avwap', { grade_a_plus_min: v }))} />
        <NumField label="Grade A min" value={draft.avwap.grade_a_min} min={0} max={100} onChange={(v) => patch(set(draft, 'avwap', { grade_a_min: v }))} />
        <NumField label="Grade B min" value={draft.avwap.grade_b_min} min={0} max={100} onChange={(v) => patch(set(draft, 'avwap', { grade_b_min: v }))} />
        <NumField label="Stop buffer (ATR)" value={draft.avwap.stop_buffer_atr} step={0.01} min={0} max={3} onChange={(v) => patch(set(draft, 'avwap', { stop_buffer_atr: v }))} />
        <NumField label="Max stop distance (ATR)" value={draft.avwap.max_stop_distance_atr} step={0.05} min={0.1} max={20} onChange={(v) => patch(set(draft, 'avwap', { max_stop_distance_atr: v }))} />
        <NumField label="Target R multiple" value={draft.avwap.target_r} step={0.1} min={0.5} max={10} onChange={(v) => patch(set(draft, 'avwap', { target_r: v }))} />
        <BoolField label="Show session VWAP" value={draft.avwap.show_session_vwap} onChange={(v) => patch(set(draft, 'avwap', { show_session_vwap: v }))} />
        <BoolField label="Show daily range" value={draft.avwap.show_daily_range} onChange={(v) => patch(set(draft, 'avwap', { show_daily_range: v }))} />
        <BoolField label="Show weekly range" value={draft.avwap.show_weekly_range} onChange={(v) => patch(set(draft, 'avwap', { show_weekly_range: v }))} />
      </Section>

      {/* ── 3. projected ranges ──────────────────────────────────────────── */}
      <Section title="Daily and weekly ranges" description="Frozen projected ranges via rolling weighted quantiles." summary={`${Math.round(draft.ranges.target_coverage * 100)}% target coverage`}>
        <Field label="Method" hint="Versioned model — not free-form text."><div style={{ ...inputStyle, display: 'flex', alignItems: 'center', color: DIM, width: 'auto' }}>rolling_empirical_quantile_v1</div></Field>
        <NumField label="Target coverage" value={draft.ranges.target_coverage} step={0.01} min={0.01} max={0.99} onChange={(v) => patch(set(draft, 'ranges', { target_coverage: v }))} />
        <NumField label="Daily lookback sessions" value={draft.ranges.daily_lookback_sessions} min={1} onChange={(v) => patch(set(draft, 'ranges', { daily_lookback_sessions: v }))} />
        <NumField label="Daily min sessions" value={draft.ranges.daily_min_sessions} min={1} onChange={(v) => patch(set(draft, 'ranges', { daily_min_sessions: v }))} />
        <NumField label="Weekly lookback periods" value={draft.ranges.weekly_lookback_periods} min={1} onChange={(v) => patch(set(draft, 'ranges', { weekly_lookback_periods: v }))} />
        <NumField label="Weekly min periods" value={draft.ranges.weekly_min_periods} min={1} onChange={(v) => patch(set(draft, 'ranges', { weekly_min_periods: v }))} />
        <BoolField label="Condition on volatility" value={draft.ranges.condition_on_volatility} onChange={(v) => patch(set(draft, 'ranges', { condition_on_volatility: v }))} />
        <NumField label="Min condition bucket" value={draft.ranges.min_condition_bucket} min={1} onChange={(v) => patch(set(draft, 'ranges', { min_condition_bucket: v }))} />
        <NumField label="Decay" value={draft.ranges.decay} step={0.01} min={0.9} max={1} onChange={(v) => patch(set(draft, 'ranges', { decay: v }))} />
        <NumField label="Edge tolerance (ATR)" value={draft.ranges.edge_tolerance_atr} step={0.01} min={0.01} onChange={(v) => patch(set(draft, 'ranges', { edge_tolerance_atr: v }))} />
      </Section>

      {/* ── 4. volatility ────────────────────────────────────────────────── */}
      <Section title="Volatility regime" description="Expansion/compression classification and directional read." summary={draft.volatility.enabled ? 'Enabled' : 'Disabled'}>
        <BoolField label="Enabled" hint="Required for gate. Compression always forces WAIT." value={draft.volatility.enabled} onChange={(v) => patch(set(draft, 'volatility', { enabled: v }))} />
        <NumField label="ATR period" value={draft.volatility.atr_period} min={2} onChange={(v) => patch(set(draft, 'volatility', { atr_period: v }))} />
        <NumField label="RV short bars" value={draft.volatility.rv_short_bars} min={2} onChange={(v) => patch(set(draft, 'volatility', { rv_short_bars: v }))} />
        <NumField label="RV long bars" value={draft.volatility.rv_long_bars} min={2} onChange={(v) => patch(set(draft, 'volatility', { rv_long_bars: v }))} />
        <NumField label="Bollinger band period" value={draft.volatility.band_period} min={2} onChange={(v) => patch(set(draft, 'volatility', { band_period: v }))} />
        <NumField label="Band std-dev" value={draft.volatility.band_stddev} step={0.1} min={0.1} onChange={(v) => patch(set(draft, 'volatility', { band_stddev: v }))} />
        <NumField label="Percentile lookback" value={draft.volatility.percentile_lookback} min={60} onChange={(v) => patch(set(draft, 'volatility', { percentile_lookback: v }))} />
        <NumField label="Gradient bars" value={draft.volatility.gradient_bars} min={2} max={50} onChange={(v) => patch(set(draft, 'volatility', { gradient_bars: v }))} />
        <NumField label="Expansion min score" value={draft.volatility.expansion_min} min={0} max={100} onChange={(v) => patch(set(draft, 'volatility', { expansion_min: v }))} />
        <NumField label="Compression max score" value={draft.volatility.compression_max} min={0} max={100} onChange={(v) => patch(set(draft, 'volatility', { compression_max: v }))} />
        <NumField label="ADX period" value={draft.volatility.adx_period} min={2} onChange={(v) => patch(set(draft, 'volatility', { adx_period: v }))} />
        <NumField label="ADX min" value={draft.volatility.adx_min} min={0} max={100} onChange={(v) => patch(set(draft, 'volatility', { adx_min: v }))} />
        <NumField label="EMA fast period" value={draft.volatility.ema_fast_period} min={1} onChange={(v) => patch(set(draft, 'volatility', { ema_fast_period: v }))} />
        <NumField label="EMA slow period" value={draft.volatility.ema_slow_period} min={2} onChange={(v) => patch(set(draft, 'volatility', { ema_slow_period: v }))} />
        <NumField label="Trend confirm bars" value={draft.volatility.trend_confirm_bars} min={1} onChange={(v) => patch(set(draft, 'volatility', { trend_confirm_bars: v }))} />
        <NumField label="Max flip age (bars)" value={draft.volatility.max_flip_age_bars} min={1} onChange={(v) => patch(set(draft, 'volatility', { max_flip_age_bars: v }))} />
        <NumField label="Min direction confidence" value={draft.volatility.min_direction_confidence} min={0} max={100} onChange={(v) => patch(set(draft, 'volatility', { min_direction_confidence: v }))} />
      </Section>

      {/* ── 5. option flow ───────────────────────────────────────────────── */}
      <Section title="Option-flow oscillator" description="Robust-normalized activity oscillator from narrow chain samples." summary={draft.flow.mode}>
        <BoolField label="Enabled" value={draft.flow.enabled} onChange={(v) => patch(set(draft, 'flow', { enabled: v }))} />
        <Field label="Mode" hint="Dynamic (ATM-centered) is the preferred intraday default.">
          <ChoiceRow value={draft.flow.mode} onChange={(mode) => patch(set(draft, 'flow', { mode }))} options={[{ value: 'dynamic', label: 'Dynamic' }, { value: 'broad', label: 'Broad' }]} />
        </Field>
        <NumField label="Dynamic strike radius" value={draft.flow.dynamic_strike_radius} min={1} max={20} onChange={(v) => patch(set(draft, 'flow', { dynamic_strike_radius: v }))} />
        <NumField label="Broad strike radius" value={draft.flow.broad_strike_radius} min={1} max={50} onChange={(v) => patch(set(draft, 'flow', { broad_strike_radius: v }))} />
        <NumField label="Max quote age (s)" value={draft.flow.max_quote_age_seconds} min={1} onChange={(v) => patch(set(draft, 'flow', { max_quote_age_seconds: v }))} />
        <NumField label="Max sample gap (s)" value={draft.flow.max_sample_gap_seconds} min={1} onChange={(v) => patch(set(draft, 'flow', { max_sample_gap_seconds: v }))} />
        <NumField label="Min chain completeness" value={draft.flow.min_chain_completeness} step={0.05} min={0.01} max={1} onChange={(v) => patch(set(draft, 'flow', { min_chain_completeness: v }))} />
        <NumField label="Max spread %" value={draft.flow.max_spread_pct} step={0.01} min={0.01} max={1} onChange={(v) => patch(set(draft, 'flow', { max_spread_pct: v }))} />
        <NumField label="Warmup samples" value={draft.flow.warmup_samples} min={1} onChange={(v) => patch(set(draft, 'flow', { warmup_samples: v }))} />
        <NumField label="Robust window samples" value={draft.flow.robust_window_samples} min={1} onChange={(v) => patch(set(draft, 'flow', { robust_window_samples: v }))} />
        <NumField label="OI intensity weight" value={draft.flow.oi_intensity_weight} step={0.05} min={0} max={1} onChange={(v) => patch(set(draft, 'flow', { oi_intensity_weight: v }))} />
        <NumField label="Z-scale" value={draft.flow.z_scale} step={0.1} min={0.1} onChange={(v) => patch(set(draft, 'flow', { z_scale: v }))} />
        <NumField label="Zero-line hysteresis" value={draft.flow.zero_hysteresis} min={0} max={100} onChange={(v) => patch(set(draft, 'flow', { zero_hysteresis: v }))} />
        <NumField label="Strong zone (display)" value={draft.flow.strong_zone} min={0} max={100} onChange={(v) => patch(set(draft, 'flow', { strong_zone: v }))} />
        <NumField label="Extreme zone (display)" value={draft.flow.extreme_zone} min={0} max={100} onChange={(v) => patch(set(draft, 'flow', { extreme_zone: v }))} />
        <BoolField label="Require for index gate" hint="Missing index flow blocks gate eligibility." value={draft.flow.require_for_index_gate} onChange={(v) => patch(set(draft, 'flow', { require_for_index_gate: v }))} />
        <BoolField label="Allow N/A for single stocks" value={draft.flow.allow_na_for_single_stocks} onChange={(v) => patch(set(draft, 'flow', { allow_na_for_single_stocks: v }))} />
      </Section>

      {/* ── 6. gamma ─────────────────────────────────────────────────────── */}
      <Section title="Gamma activity" description="Confirmation-only. Never determines direction by itself." summary={draft.gamma.enabled ? 'Enabled' : 'Disabled'}>
        <BoolField label="Enabled" value={draft.gamma.enabled} onChange={(v) => patch(set(draft, 'gamma', { enabled: v }))} />
        <Field label="Risk-free rate" hint="Required for gamma availability — never invented. Leave blank until set.">
          <input type="number" step={0.001} value={draft.gamma.risk_free_rate ?? ''} placeholder="unset"
            onChange={(e) => patch(set(draft, 'gamma', { risk_free_rate: e.target.value === '' ? null : Number(e.target.value) }))}
            style={inputStyle} />
        </Field>
        <Field label="Dividend yield" hint="Required for gamma availability — never invented. Leave blank until set.">
          <input type="number" step={0.001} value={draft.gamma.dividend_yield ?? ''} placeholder="unset"
            onChange={(e) => patch(set(draft, 'gamma', { dividend_yield: e.target.value === '' ? null : Number(e.target.value) }))}
            style={inputStyle} />
        </Field>
        <NumField label="Min IV" value={draft.gamma.min_iv} step={0.001} min={0.001} onChange={(v) => patch(set(draft, 'gamma', { min_iv: v }))} />
        <NumField label="Max IV" value={draft.gamma.max_iv} step={0.1} min={0.1} onChange={(v) => patch(set(draft, 'gamma', { max_iv: v }))} />
        <NumField label="Robust window samples" value={draft.gamma.robust_window_samples} min={1} onChange={(v) => patch(set(draft, 'gamma', { robust_window_samples: v }))} />
        <NumField label="Min samples" value={draft.gamma.min_samples} min={1} onChange={(v) => patch(set(draft, 'gamma', { min_samples: v }))} />
        <NumField label="Blast Z min" value={draft.gamma.blast_z_min} step={0.1} min={0.1} onChange={(v) => patch(set(draft, 'gamma', { blast_z_min: v }))} />
        <NumField label="Acceleration Z min" value={draft.gamma.acceleration_z_min} step={0.1} min={0.1} onChange={(v) => patch(set(draft, 'gamma', { acceleration_z_min: v }))} />
        <BoolField label="Expiry profile enabled" value={draft.gamma.expiry_profile_enabled} onChange={(v) => patch(set(draft, 'gamma', { expiry_profile_enabled: v }))} />
        <Field label="Expiry profile start (IST)"><input type="text" value={draft.gamma.expiry_profile_start_ist} onChange={(e) => patch(set(draft, 'gamma', { expiry_profile_start_ist: e.target.value }))} style={inputStyle} /></Field>
        <BoolField label="Require flow alignment" hint="Gamma cannot determine direction on its own." value={draft.gamma.require_flow_alignment} onChange={(v) => patch(set(draft, 'gamma', { require_flow_alignment: v }))} />
        <BoolField label="Required for gate" hint="Off by default — missing gamma stays explicit and cannot boost score." value={draft.gamma.required_for_gate} onChange={(v) => patch(set(draft, 'gamma', { required_for_gate: v }))} />
      </Section>

      {/* ── 7. fusion ────────────────────────────────────────────────────── */}
      <Section title="Fusion and eligibility" description="Component weights and status thresholds. Weights must sum to 100." summary={`${draft.fusion.base_weight + draft.fusion.avwap_weight + draft.fusion.volatility_weight + draft.fusion.flow_weight + draft.fusion.gamma_weight}% total`}>
        <NumField label="Base weight" value={draft.fusion.base_weight} min={0} max={100} onChange={(v) => patch(set(draft, 'fusion', { base_weight: v }))} />
        <NumField label="AVWAP weight" value={draft.fusion.avwap_weight} min={0} max={100} onChange={(v) => patch(set(draft, 'fusion', { avwap_weight: v }))} />
        <NumField label="Volatility weight" value={draft.fusion.volatility_weight} min={0} max={100} onChange={(v) => patch(set(draft, 'fusion', { volatility_weight: v }))} />
        <NumField label="Flow weight" value={draft.fusion.flow_weight} min={0} max={100} onChange={(v) => patch(set(draft, 'fusion', { flow_weight: v }))} />
        <NumField label="Gamma weight" value={draft.fusion.gamma_weight} min={0} max={100} onChange={(v) => patch(set(draft, 'fusion', { gamma_weight: v }))} />
        <GradeField label="Min AVWAP grade to confirm" value={draft.fusion.min_avwap_grade} onChange={(v) => patch(set(draft, 'fusion', { min_avwap_grade: v }))} />
        <NumField label="Strong conflict confidence" value={draft.fusion.strong_conflict_confidence} min={0} max={100} onChange={(v) => patch(set(draft, 'fusion', { strong_conflict_confidence: v }))} />
        <NumField label="Confirmed score min" value={draft.fusion.confirmed_score_min} min={0} max={100} onChange={(v) => patch(set(draft, 'fusion', { confirmed_score_min: v }))} />
        <NumField label="High-conviction score min" value={draft.fusion.high_conviction_score_min} min={0} max={100} onChange={(v) => patch(set(draft, 'fusion', { high_conviction_score_min: v }))} />
        <BoolField label="Require fresh trigger" value={draft.fusion.require_fresh_trigger} onChange={(v) => patch(set(draft, 'fusion', { require_fresh_trigger: v }))} />
        <BoolField label="Require all gate components" hint="Expected unavailable evidence fails closed." value={draft.fusion.require_all_gate_components} onChange={(v) => patch(set(draft, 'fusion', { require_all_gate_components: v }))} />
      </Section>

      {/* ── 8. retention/diagnostics ─────────────────────────────────────── */}
      <Section title="Data retention and diagnostics" description="Storage windows for raw samples and computed features/signals." summary={`${draft.retention_raw_days}d raw · ${draft.retention_features_days}d features`}>
        <NumField label="Raw snapshot retention (days)" value={draft.retention_raw_days} min={1} max={365} onChange={(v) => patch({ ...draft, retention_raw_days: v })} />
        <NumField label="Feature/signal retention (days)" value={draft.retention_features_days} min={1} max={3650} onChange={(v) => patch({ ...draft, retention_features_days: v })} />
      </Section>
    </section>
  );
}

const pillButtonStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, border: `1px solid ${BORDER}`, background: '#fff',
  color: MUTED, borderRadius: 7, padding: '7px 12px', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
};

const applyButtonStyle: React.CSSProperties = {
  border: 'none', background: ORANGE, color: '#fff', borderRadius: 7, padding: '8px 16px',
  fontSize: 11.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
};

export default NavigatorSettingsPanel;
