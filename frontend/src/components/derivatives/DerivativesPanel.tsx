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
  useStudyRun,
  useStudyStatus,
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
  directional_futures: 'Trend following (futures)',
  directional_options: 'Trend following (buy options)',
  vrp_voltiming: 'Sell options when IV is high',
  skew_put: 'Sell put spreads (harvest skew)',
  gex_pinning: 'GEX pinning (range-bound)',
};

const ALPHA_SOURCE_COLORS: Record<AlphaSource, string> = {
  directional_futures: c.green,
  directional_options: c.green,
  vrp_voltiming: c.amber,
  skew_put: c.purple,
  gex_pinning: c.cyan,
};

const DEFAULT_ENGINE_CONFIG: DerivativesEngineConfig = {
  engine_mode: 'routing_gate',
  active_alpha_sources: ['directional_futures'],
  risk_postures: ['long_only'],
  validation_method: 1,
};

const MODE_DESCRIPTIONS: Record<EngineMode, string> = {
  routing_gate: "Sterling's Gate — takes directional signals and routes to futures or options using a composite score. Hard-vetoes options at high IV or wide spreads. Long calls only.",
  native: "Claude's Native — bypasses the routing gate entirely. Generates trades directly from the alpha sources you select below, in the risk posture you choose.",
};

const RISK_POSTURE_LABELS: Record<RiskPosture, string> = {
  long_only: 'Long only (buy options)',
  defined_risk: 'Defined risk (spreads / condors)',
  naked: 'Naked (short strangles, opt-in)',
};

const VALIDATION_LABELS: Record<number, string> = {
  1: '1 · calibrate-to-live', 2: '2 · real-only/forward', 3: '3 · live snapshot',
};

// ── Chip toggle (reused from SterlingEngineTab) ────────────────────────────

function ChipToggle({ label, on, onChange, color }: { label: string; on: boolean; onChange: (v: boolean) => void; color?: string }) {
  const clr = on ? (color || c.green) : c.dim;
  return (
    <button onClick={() => onChange(!on)} style={{
      fontSize: 8, fontWeight: 800, letterSpacing: '0.06em', padding: '3px 8px',
      borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit',
      border: `1px solid ${on ? alpha(clr, 0.27) : c.border}`,
      background: on ? alpha(clr, 0.13) : 'transparent',
      color: clr, transition: 'all .1s', whiteSpace: 'nowrap', textTransform: 'uppercase',
    }}>{on ? '● ' : '○ '}{label}</button>
  );
}

// ── Global engine settings ────────────────────────────────────────────

const MODE_OPTIONS: Array<{ id: EngineMode; label: string; color: string }> = [
  { id: 'routing_gate', label: "Sterling's Gate", color: c.amber },
  { id: 'native',        label: "Claude's Native", color: c.blue },
];

const POSTURE_OPTIONS: Array<{ id: RiskPosture; label: string; color: string }> = [
  { id: 'long_only',    label: 'Long only',              color: c.green },
  { id: 'defined_risk', label: 'Defined risk',           color: c.amber },
  { id: 'naked',        label: 'Naked (opt-in)',         color: c.red },
];

const VALIDATION_OPTIONS: Array<{ id: number; label: string; color: string }> = [
  { id: 1, label: 'Calibrate-to-live', color: c.cyan },
  { id: 2, label: 'Real-only/forward', color: c.dim },
  { id: 3, label: 'Live snapshot',     color: c.dim },
];

const EngineSettings: React.FC<{
  draft: DerivativesEngineConfig;
  setDraft: React.Dispatch<React.SetStateAction<DerivativesEngineConfig>>;
  defaults: DerivativesEngineConfig;
}> = ({ draft, setDraft, defaults }) => {
  const [showReport, setShowReport] = useState(false);
  const report = useStudyReport(showReport);
  const studyRun = useStudyRun();
  const [runId, setRunId] = useState<string | null>(null);
  const studyStatus = useStudyStatus(runId, !!runId);

  useEffect(() => {
    if (studyStatus.data?.status === 'complete') {
      // Refresh report by toggling
    }
  }, [studyStatus.data?.status]);

  const toggleSource = (s: AlphaSource, on: boolean) => {
    setDraft({
      ...draft,
      active_alpha_sources: on
        ? Array.from(new Set([...draft.active_alpha_sources, s]))
        : draft.active_alpha_sources.filter((x) => x !== s),
    });
  };

  const isRunning = studyStatus.data?.status === 'running' || studyStatus.data?.status === 'starting';
  const progress = studyStatus.data?.progress_pct ?? 0;

  const handleRunStudy = () => {
    studyRun.mutate(
      { validation_method: draft.validation_method },
      { onSuccess: (data) => { setRunId(data.run_id); setShowReport(true); } }
    );
  };

  const sourcesAreDefault =
    draft.active_alpha_sources.length === defaults.active_alpha_sources.length &&
    draft.active_alpha_sources.every((s) => defaults.active_alpha_sources.includes(s));

  // Normalize postures (tolerate a backend that only sent the legacy single).
  const postures: RiskPosture[] =
    draft.risk_postures ?? (draft.risk_posture ? [draft.risk_posture] : ['long_only']);
  const defaultPostures: RiskPosture[] =
    defaults.risk_postures ?? (defaults.risk_posture ? [defaults.risk_posture] : ['long_only']);

  const togglePosture = (p: RiskPosture, on: boolean) => {
    const cur = new Set(postures);
    if (on) cur.add(p); else cur.delete(p);
    // Never allow an empty posture set — fall back to long_only.
    const next = [...cur];
    setDraft({ ...draft, risk_postures: next.length ? next : ['long_only'] });
  };

  const modeChanged = draft.engine_mode !== defaults.engine_mode;
  const posturesChanged =
    postures.length !== defaultPostures.length ||
    !postures.every((p) => defaultPostures.includes(p));
  const validationChanged = draft.validation_method !== defaults.validation_method;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* ── Engine · Global: mode (single) + risk posture (multi) ─────── */}
      <div style={{ ...grpBox, gap: 8 }}>
        <div style={grpTitle}>ENGINE · GLOBAL</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span style={{ fontSize: 9, color: c.dim, letterSpacing: '0.04em' }}>MODE</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {MODE_OPTIONS.map((opt) => (
              <ChipToggle
                key={opt.id}
                label={opt.label}
                color={opt.color}
                on={draft.engine_mode === opt.id}
                onChange={() => setDraft({ ...draft, engine_mode: opt.id })}
              />
            ))}
          </div>
          {modeChanged && (
            <div style={{ fontSize: 8, color: c.dim, fontStyle: 'italic', opacity: 0.8 }}>
              Factory Default: {MODE_OPTIONS.find((o) => o.id === defaults.engine_mode)?.label}
            </div>
          )}
          <div style={{ fontSize: 8, color: c.dim, fontStyle: 'italic' }}>
            {MODE_DESCRIPTIONS[draft.engine_mode]}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginTop: 4 }}>
          <span style={{ fontSize: 9, color: c.dim, letterSpacing: '0.04em' }}>
            RISK POSTURE <span style={{ opacity: 0.7 }}>· multi-select</span>
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {POSTURE_OPTIONS.map((opt) => (
              <ChipToggle
                key={opt.id}
                label={opt.label}
                color={opt.color}
                on={postures.includes(opt.id)}
                onChange={(v) => togglePosture(opt.id, v)}
              />
            ))}
          </div>
          {posturesChanged && (
            <div style={{ fontSize: 8, color: c.dim, textAlign: 'right', opacity: 0.8 }}>
              Factory Default: {defaultPostures.map((p) => RISK_POSTURE_LABELS[p]).join(', ')}
            </div>
          )}
          {postures.includes('naked') && (
            <div style={{ fontSize: 8, color: c.red, fontStyle: 'italic' }}>
              Naked short vol — UNCAPPED tail risk; only used in a rich IV regime (IVR≥70), else steps down.
            </div>
          )}
        </div>
      </div>

      {/* ── Alpha sources (chip toggles, native-only) ─────────────────── */}
      {draft.engine_mode === 'native' && (
        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>ALPHA SOURCES</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {(Object.keys(ALPHA_SOURCE_LABELS) as AlphaSource[]).map((s) => (
              <ChipToggle
                key={s}
                label={ALPHA_SOURCE_LABELS[s]}
                color={ALPHA_SOURCE_COLORS[s]}
                on={draft.active_alpha_sources.includes(s)}
                onChange={(v) => toggleSource(s, v)}
              />
            ))}
          </div>
          {!sourcesAreDefault && (
            <div style={{ fontSize: 8, color: c.dim, textAlign: 'right', opacity: 0.8 }}>
              Factory Default: Trend following (futures) only
            </div>
          )}
        </div>
      )}

      {/* ── Validation method ─────────────────────────────────────────── */}
      <div style={{ ...grpBox, gap: 8 }}>
        <div style={grpTitle}>VALIDATION METHOD</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
          {VALIDATION_OPTIONS.map((opt) => (
            <ChipToggle
              key={opt.id}
              label={opt.label}
              color={opt.color}
              on={draft.validation_method === opt.id}
              onChange={() => setDraft({ ...draft, validation_method: opt.id as 1 | 2 | 3 })}
            />
          ))}
        </div>
        {validationChanged && (
          <div style={{ fontSize: 8, color: c.dim, textAlign: 'right', opacity: 0.8 }}>
            Factory Default: Calibrate-to-live
          </div>
        )}
        <div style={{ fontSize: 8, color: c.dim, fontStyle: 'italic' }}>
          {draft.validation_method === 1 ? 'Simulates options trades using a single live IV surface snapshot.' :
           draft.validation_method === 2 ? 'Real historical data only — requires forward IV recorder history.' :
           'Diagnostic: captures the live surface with no backtest simulation.'}
        </div>
      </div>

      {/* ── Divider ───────────────────────────────────────────────────── */}
      <div style={{ borderTop: `1px solid ${c.border}` }} />

      {/* ── Study run controls ────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button
          onClick={handleRunStudy}
          disabled={isRunning || studyRun.isPending}
          style={{
            padding: '3px 10px', borderRadius: 4,
            background: isRunning ? alpha(c.amber, 0.15) : 'transparent',
            border: `1px solid ${isRunning ? c.amber : c.border}`,
            color: isRunning ? c.amber : c.dim, fontSize: 10, fontWeight: 700,
            cursor: isRunning ? 'default' : 'pointer', fontFamily: 'inherit',
          }}>
          {isRunning ? 'Running…' : studyRun.isPending ? 'Starting…' : 'Run Study'}
        </button>
        <button
          onClick={() => setShowReport(!showReport)}
          style={{
            padding: '3px 10px', borderRadius: 4,
            background: 'transparent', border: `1px solid ${c.border}`,
            color: c.dim, fontSize: 10, fontWeight: 700, cursor: 'pointer',
            fontFamily: 'inherit',
          }}>
          {showReport ? 'Hide report' : 'View report'}
        </button>
      </div>

      {/* ── Progress bar ──────────────────────────────────────────────── */}
      {isRunning && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: c.dim }}>
            <span>{studyStatus.data?.current_stage ?? '…'}</span>
            <span>{progress.toFixed(0)}%</span>
          </div>
          <div style={{
            width: '100%', height: 4, borderRadius: 2,
            background: c.bg, border: `1px solid ${c.border}`,
            overflow: 'hidden',
          }}>
            <div style={{
              width: `${progress}%`, height: '100%',
              background: c.amber,
              transition: 'width 0.3s ease',
              borderRadius: 2,
            }} />
          </div>
          {studyStatus.data?.elapsed_seconds != null && (
            <div style={{ fontSize: 8, color: c.dim }}>
              {studyStatus.data.elapsed_seconds.toFixed(0)}s elapsed
              {studyStatus.data.n_configs > 0 && ` · ${studyStatus.data.n_configs} configs`}
            </div>
          )}
        </div>
      )}

      {/* ── Study error ───────────────────────────────────────────────── */}
      {studyStatus.data?.status === 'failed' && (
        <div style={{ fontSize: 9, color: c.red, fontStyle: 'italic' }}>
          Study failed: {studyStatus.data.error ?? 'unknown error'}
        </div>
      )}

      {/* ── Study report ──────────────────────────────────────────────── */}
      {showReport && (
        <pre style={{
          maxHeight: 280, overflow: 'auto', fontSize: 9, lineHeight: 1.5,
          color: c.dim, whiteSpace: 'pre-wrap', margin: 0,
          background: c.bg, border: `1px solid ${c.border}`, borderRadius: 4, padding: 8,
        }}>
          {report.isLoading
            ? 'loading…'
            : (report.data?.study ?? 'No study report generated yet — click "Run Study" to generate one.')}
        </pre>
      )}
    </div>
  );
};

interface DerivStrategyTab {
  id: string;
  label: string;
}

interface Props {
  strategy: string;
  /** When provided, a strategy-selector tab strip renders at the top of the
   *  panel (above the engine-global block). Omitted by call sites that don't
   *  need it (e.g. single-strategy tabs). */
  strategies?: DerivStrategyTab[];
  onStrategyChange?: (id: string) => void;
}

export const DerivativesPanel: React.FC<Props> = ({ strategy, strategies, onStrategyChange }) => {
  const cfg = useDerivativesConfig();
  const patch = usePatchDerivativesProfile();
  const ec = useDerivativesEngineConfig();
  const patchEngine = usePatchDerivativesEngineConfig();

  const persisted = cfg.data?.profiles?.[strategy];
  const defaults = cfg.data?.defaults?.[strategy];
  const [draft, setDraft] = useState<StrategyDerivativesProfile | null>(persisted ?? null);

  const persistedEngine = ec.data ?? DEFAULT_ENGINE_CONFIG;
  const [engineDraft, setEngineDraft] = useState<DerivativesEngineConfig>(persistedEngine);

  useEffect(() => {
    if (persisted) setDraft(persisted);
  }, [persisted]);

  useEffect(() => {
    if (ec.data) setEngineDraft(ec.data);
  }, [ec.data]);

  if (!draft) {
    return <div style={{ ...card, padding: 16, fontSize: 11, color: c.dim }}>Loading derivatives profile…</div>;
  }

  const set = <K extends keyof StrategyDerivativesProfile>(k: K, v: StrategyDerivativesProfile[K]) =>
    setDraft({ ...draft, [k]: v });

  const profileDirty = JSON.stringify(draft) !== JSON.stringify(persisted);
  const engineDirty = JSON.stringify(engineDraft) !== JSON.stringify(persistedEngine);
  const dirty = profileDirty || engineDirty;

  const handleApply = () => {
    if (profileDirty) patch.mutate({ strategy, profile: draft });
    if (engineDirty) patchEngine.mutate(engineDraft);
  };

  const handleReset = () => {
    if (persisted) setDraft(persisted);
    setEngineDraft(persistedEngine);
  };

  return (
    <div style={card}>
      <div style={cardHead}>
        <span>{strategy.replace('scalping/', '').toUpperCase().replace(/_/g, ' ')}</span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button
            onClick={handleReset}
            disabled={!dirty}
            style={{
              padding: '4px 10px', borderRadius: 5,
              background: 'transparent',
              border: `1px solid ${c.border}`,
              color: c.dim, fontSize: 10, fontWeight: 700,
              letterSpacing: '0.06em', cursor: dirty ? 'pointer' : 'default',
              fontFamily: 'inherit',
            }}>
            ↺ DEFAULTS
          </button>
          <button
            disabled={!dirty || patch.isPending || patchEngine.isPending}
            onClick={handleApply}
            style={{
              padding: '4px 10px', borderRadius: 5,
              background: dirty ? alpha(c.blue, 0.15) : 'transparent',
              border: `1px solid ${dirty ? alpha(c.blue, 0.4) : c.border}`,
              color: dirty ? c.blue : c.dim, fontSize: 10, fontWeight: 700,
              letterSpacing: '0.06em', cursor: dirty ? 'pointer' : 'default',
              fontFamily: 'inherit',
            }}>
            {patch.isPending || patchEngine.isPending ? 'SAVING…' : dirty ? 'APPLY' : 'SAVED'}
          </button>
        </span>
      </div>
      <div style={{ ...cardBody, display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* Strategy selector tabs (above the engine-global block) */}
        {strategies && onStrategyChange && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', borderBottom: `1px solid ${c.border}`, paddingBottom: 10 }}>
            {strategies.map((s) => {
              const active = strategy === s.id;
              return (
                <button key={s.id} onClick={() => onStrategyChange(s.id)} style={{
                  fontSize: 10, fontWeight: 800, padding: '4px 12px', borderRadius: 6,
                  cursor: 'pointer', fontFamily: 'inherit',
                  border: `1px solid ${active ? c.blue : c.border}`,
                  background: active ? alpha(c.blue, 0.12) : 'transparent',
                  color: active ? c.blue : c.dim,
                }}>{s.label}</button>
              );
            })}
          </div>
        )}

        {/* Global engine mode + alpha sources + risk posture */}
        <EngineSettings draft={engineDraft} setDraft={setEngineDraft} defaults={DEFAULT_ENGINE_CONFIG} />

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
