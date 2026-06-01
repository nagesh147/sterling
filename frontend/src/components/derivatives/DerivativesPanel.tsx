/**
 * DerivativesPanel — per-strategy profile editor surfaced inside the
 * SETTINGS drawer. Scoped to a single strategy slug; renders the knobs
 * that change selector behaviour AND the master `enabled` toggle that
 * flips the strategy from legacy futures path → DerivativesSelector.
 *
 * Knobs surfaced:
 *  - enabled            (master switch, default OFF on first install)
 *  - instrument_bias    (auto / futures / options)
 *  - target_delta + tolerance
 *  - dte_min/preferred/max
 *  - leverage_cap
 *  - max_premium_pct_of_account
 *  - funding_cost_max_pct_of_R
 *  - min_oi / max_spread_pct / ivr_pct_naked_max
 *
 * Save fires /api/v1/derivatives/config (POST) and invalidates the
 * candidates query so the table reflects the new profile immediately.
 */
import React, { useEffect, useState } from 'react';
import { c, alpha, card, cardHead, cardBody, grpBox, grpTitle } from '../../styles/terminalUI';
import {
  AlphaSource,
  DerivativesEngineConfig,
  EngineMode,
  RiskPosture,
  StrategyDerivativesProfile,
  useDerivativesConfig,
  useDerivativesEngineConfig,
  usePatchDerivativesEngineConfig,
  usePatchDerivativesProfile,
  useStudyReport,
} from '../../hooks/useDerivatives';

const NumRow: React.FC<{ label: string; value: number; defaultVal?: number; step?: number; min?: number; max?: number; onChange: (v: number) => void }> = ({ label, value, defaultVal, step = 0.01, min, max, onChange }) => {
  const isDefault = defaultVal !== undefined && value === defaultVal;
  return (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
    <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 11, color: c.dim }}>
      {label}
      <input
        type="number" step={step} min={min} max={max} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{
          width: 90, 
          background: isDefault ? alpha(c.blue, 0.1) : c.bg, 
          border: isDefault ? `1px solid ${alpha(c.blue, 0.3)}` : `1px solid ${c.border}`,
          borderRadius: 4, 
          color: isDefault ? c.blue : c.bright, 
          padding: '3px 6px',
          fontFamily: 'inherit', fontSize: 11, textAlign: 'right',
          transition: 'all 0.15s ease',
        }}
      />
    </label>
    {defaultVal !== undefined && !isDefault && (
      <div style={{ fontSize: 8, color: c.dim, textAlign: 'right', paddingRight: 2, fontStyle: 'italic', opacity: 0.8 }}>
        Factory Default: {defaultVal}
      </div>
    )}
  </div>
);
}

const SelectRow: React.FC<{ label: string; value: string; defaultVal?: string; options: string[]; onChange: (v: string) => void }> = ({ label, value, defaultVal, options, onChange }) => {
  const isDefault = defaultVal !== undefined && value === defaultVal;
  return (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
    <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 11, color: c.dim }}>
      {label}
      <select
        value={value} onChange={(e) => onChange(e.target.value)}
        style={{
          width: 90, 
          background: isDefault ? alpha(c.blue, 0.1) : c.bg, 
          border: isDefault ? `1px solid ${alpha(c.blue, 0.3)}` : `1px solid ${c.border}`,
          borderRadius: 4, 
          color: isDefault ? c.blue : c.bright, 
          padding: '3px 6px',
          fontFamily: 'inherit', fontSize: 11, cursor: 'pointer',
          transition: 'all 0.15s ease',
        }}>
        {options.map((o) => <option key={o} value={o} style={{ background: c.bg, color: c.bright }}>{o}</option>)}
      </select>
    </label>
    {defaultVal !== undefined && !isDefault && (
      <div style={{ fontSize: 8, color: c.dim, textAlign: 'right', paddingRight: 2, fontStyle: 'italic', opacity: 0.8 }}>
        Factory Default: {defaultVal}
      </div>
    )}
  </div>
);
}

const ALPHA_SOURCE_LABELS: Record<AlphaSource, string> = {
  directional_futures: 'Directional (futures)',
  directional_options: 'Directional (long options)',
  vrp_voltiming: 'VRP / vol-timing',
  skew_put: 'Skew (put-side)',
  gex_pinning: 'GEX / pinning',
};

// Global engine settings (routing_gate ↔ native + alpha sources + risk posture).
// Distinct from the per-strategy profile knobs below; reads/writes /config/engine.
const VALIDATION_LABELS: Record<number, string> = {
  1: '1 · calibrate-to-live', 2: '2 · real-only/forward', 3: '3 · live snapshot',
};

const EngineSettings: React.FC = () => {
  const ec = useDerivativesEngineConfig();
  const patchEngine = usePatchDerivativesEngineConfig();
  const [showReport, setShowReport] = useState(false);
  const report = useStudyReport(showReport);
  const cfg = ec.data;
  if (!cfg) return null;

  const update = (p: Partial<DerivativesEngineConfig>) => patchEngine.mutate({ ...cfg, ...p });
  const toggleSource = (s: AlphaSource, on: boolean) =>
    update({
      active_alpha_sources: on
        ? Array.from(new Set([...cfg.active_alpha_sources, s]))
        : cfg.active_alpha_sources.filter((x) => x !== s),
    });

  return (
    <div style={{ ...grpBox, gap: 8 }}>
      <div style={grpTitle}>ENGINE · GLOBAL</div>
      <SelectRow label="Mode" value={cfg.engine_mode} options={['routing_gate', 'native']}
        onChange={(v) => update({ engine_mode: v as EngineMode })} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {(Object.keys(ALPHA_SOURCE_LABELS) as AlphaSource[]).map((s) => (
          <label key={s} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 11, color: c.dim }}>
            {ALPHA_SOURCE_LABELS[s]}
            <input type="checkbox" checked={cfg.active_alpha_sources.includes(s)}
              onChange={(e) => toggleSource(s, e.target.checked)} />
          </label>
        ))}
      </div>
      <SelectRow label="Risk posture" value={cfg.risk_posture} options={['long_only', 'defined_risk', 'naked']}
        onChange={(v) => update({ risk_posture: v as RiskPosture })} />
      {cfg.risk_posture === 'naked' && (
        <div style={{ fontSize: 9, color: c.red, fontStyle: 'italic' }}>
          Naked short vol — uncapped tail risk (Phase 2d; falls back to long-only until then)
        </div>
      )}
      {cfg.risk_posture === 'naked' && (
        <div style={{ fontSize: 9, color: c.dim, fontStyle: 'italic' }}>
          Naked is gated to a rich IV regime (IVR≥70); otherwise falls back to defined-risk.
        </div>
      )}
      <SelectRow label="Validation method" value={String(cfg.validation_method)}
        options={['1', '2', '3']}
        onChange={(v) => update({ validation_method: Number(v) as 1 | 2 | 3 })} />
      <div style={{ fontSize: 9, color: c.dim }}>{VALIDATION_LABELS[cfg.validation_method]}</div>
      <button
        onClick={() => setShowReport(!showReport)}
        style={{
          padding: '3px 10px', borderRadius: 4, alignSelf: 'flex-start',
          background: 'transparent', border: `1px solid ${c.border}`,
          color: c.dim, fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
        }}>
        {showReport ? 'Hide study report' : 'View study report'}
      </button>
      {showReport && (
        <pre style={{
          maxHeight: 280, overflow: 'auto', fontSize: 9, lineHeight: 1.5,
          color: c.dim, whiteSpace: 'pre-wrap', margin: 0,
          background: c.bg, border: `1px solid ${c.border}`, borderRadius: 4, padding: 8,
        }}>
          {report.isLoading
            ? 'loading…'
            : (report.data?.study ?? 'No study report generated yet — run the Phase 1 study.')}
        </pre>
      )}
    </div>
  );
};

interface Props {
  strategy: string;
}

export const DerivativesPanel: React.FC<Props> = ({ strategy }) => {
  const cfg = useDerivativesConfig();
  const patch = usePatchDerivativesProfile();

  const persisted = cfg.data?.profiles?.[strategy];
  const defaults = cfg.data?.defaults?.[strategy];
  const [draft, setDraft] = useState<StrategyDerivativesProfile | null>(persisted ?? null);

  useEffect(() => {
    if (persisted) setDraft(persisted);
  }, [persisted]);

  if (!draft) {
    return <div style={{ ...card, padding: 16, fontSize: 11, color: c.dim }}>Loading derivatives profile…</div>;
  }

  const set = <K extends keyof StrategyDerivativesProfile>(k: K, v: StrategyDerivativesProfile[K]) =>
    setDraft({ ...draft, [k]: v });

  const dirty = JSON.stringify(draft) !== JSON.stringify(persisted);
  const defaultsResettable = !!defaults && JSON.stringify({
    ...defaults,
    enabled: draft.enabled,
    auto_execute_futures: draft.auto_execute_futures,
    auto_execute_options: draft.auto_execute_options,
  }) !== JSON.stringify(draft);

  return (
    <div style={card}>
      <div style={cardHead}>
        <span>{strategy.replace('scalping/', '').toUpperCase().replace(/_/g, ' ')}</span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button
            disabled={!defaultsResettable}
            onClick={() => defaults && setDraft({ 
              ...defaults, 
              enabled: draft.enabled, 
              auto_execute_futures: draft.auto_execute_futures, 
              auto_execute_options: draft.auto_execute_options 
            })}
            style={{
              padding: '4px 10px', borderRadius: 5,
              background: 'transparent',
              border: `1px solid ${c.border}`,
              color: c.dim, fontSize: 10, fontWeight: 700,
              letterSpacing: '0.06em', cursor: defaultsResettable ? 'pointer' : 'default',
              fontFamily: 'inherit',
            }}>
            STRATEGY DEFAULTS
          </button>
          <button
            disabled={!dirty || patch.isPending}
            onClick={() => patch.mutate({ strategy, profile: draft })}
            style={{
              padding: '4px 10px', borderRadius: 5,
              background: dirty ? alpha(c.blue, 0.15) : 'transparent',
              border: `1px solid ${dirty ? alpha(c.blue, 0.4) : c.border}`,
              color: dirty ? c.blue : c.dim, fontSize: 10, fontWeight: 700,
              letterSpacing: '0.06em', cursor: dirty ? 'pointer' : 'default',
              fontFamily: 'inherit',
            }}>
            {patch.isPending ? 'SAVING…' : dirty ? 'APPLY' : 'SAVED'}
          </button>
        </span>
      </div>
      <div style={{ ...cardBody, display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* Global engine mode + alpha sources + risk posture */}
        <EngineSettings />

        {/* Instrument selection */}
        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>INSTRUMENT</div>
          <SelectRow label="Bias" defaultVal={defaults?.instrument_bias} value={draft.instrument_bias} options={['auto', 'futures', 'options']} onChange={(v) => set('instrument_bias', v as any)} />
          <NumRow label="Target delta" defaultVal={defaults?.target_delta} step={0.05} min={0} max={1} value={draft.target_delta} onChange={(v) => set('target_delta', v)} />
          <NumRow label="Delta tolerance" defaultVal={defaults?.target_delta_tolerance} step={0.025} min={0} max={0.5} value={draft.target_delta_tolerance} onChange={(v) => set('target_delta_tolerance', v)} />
        </div>

        {/* Expiry / hold */}
        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>EXPIRY · HOLD</div>
          <NumRow label="DTE min" defaultVal={defaults?.dte_min} step={1} min={0} value={draft.dte_min} onChange={(v) => set('dte_min', Math.round(v))} />
          <NumRow label="DTE preferred" defaultVal={defaults?.dte_preferred} step={1} min={0} value={draft.dte_preferred} onChange={(v) => set('dte_preferred', Math.round(v))} />
          <NumRow label="DTE max" defaultVal={defaults?.dte_max} step={1} min={0} value={draft.dte_max} onChange={(v) => set('dte_max', Math.round(v))} />
          <NumRow label="Expected hold (min)" defaultVal={defaults?.expected_hold_minutes} step={5} min={1} value={draft.expected_hold_minutes} onChange={(v) => set('expected_hold_minutes', Math.round(v))} />
          <NumRow label="Force-close mins before expiry" defaultVal={defaults?.expiry_close_minutes_before} step={5} min={0} value={draft.expiry_close_minutes_before} onChange={(v) => set('expiry_close_minutes_before', Math.round(v))} />
        </div>

        {/* Sizing + risk caps */}
        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>RISK · SIZING</div>
          <NumRow label="Leverage cap (×)" defaultVal={defaults?.leverage_cap} step={1} min={1} value={draft.leverage_cap} onChange={(v) => set('leverage_cap', v)} />
          <NumRow label="Max premium % of NAV" defaultVal={defaults?.max_premium_pct_of_account} step={0.005} min={0} max={0.1} value={draft.max_premium_pct_of_account} onChange={(v) => set('max_premium_pct_of_account', v)} />
          <NumRow label="Funding cost / R cap" defaultVal={defaults?.funding_cost_max_pct_of_R} step={0.05} min={0} max={1} value={draft.funding_cost_max_pct_of_R} onChange={(v) => set('funding_cost_max_pct_of_R', v)} />
        </div>

        {/* Liquidity floors */}
        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>LIQUIDITY FLOORS</div>
          <NumRow label="Min OI" defaultVal={defaults?.min_oi} step={10} min={0} value={draft.min_oi} onChange={(v) => set('min_oi', v)} />
          <NumRow label="Max spread %" defaultVal={defaults?.max_spread_pct} step={0.005} min={0} max={0.5} value={draft.max_spread_pct} onChange={(v) => set('max_spread_pct', v)} />
          <NumRow label="IVR cap (naked %)" defaultVal={defaults?.ivr_pct_naked_max} step={5} min={0} max={100} value={draft.ivr_pct_naked_max} onChange={(v) => set('ivr_pct_naked_max', Math.round(v))} />
        </div>

      </div>
    </div>
  );
};
