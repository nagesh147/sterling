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
  StrategyDerivativesProfile,
  useDerivativesConfig,
  usePatchDerivativesProfile,
} from '../../hooks/useDerivatives';

const NumRow: React.FC<{ label: string; value: number; step?: number; min?: number; max?: number; onChange: (v: number) => void }> = ({ label, value, step = 0.01, min, max, onChange }) => (
  <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 11, color: c.dim }}>
    {label}
    <input
      type="number" step={step} min={min} max={max} value={value}
      onChange={(e) => onChange(parseFloat(e.target.value))}
      style={{
        width: 90, background: c.bg, border: `1px solid ${c.border}`,
        borderRadius: 4, color: c.bright, padding: '3px 6px',
        fontFamily: 'inherit', fontSize: 11, textAlign: 'right',
      }}
    />
  </label>
);

const SelectRow: React.FC<{ label: string; value: string; options: string[]; onChange: (v: string) => void }> = ({ label, value, options, onChange }) => (
  <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 11, color: c.dim }}>
    {label}
    <select
      value={value} onChange={(e) => onChange(e.target.value)}
      style={{
        width: 90, background: c.bg, border: `1px solid ${c.border}`,
        borderRadius: 4, color: c.bright, padding: '3px 6px',
        fontFamily: 'inherit', fontSize: 11, cursor: 'pointer',
      }}>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  </label>
);

interface Props {
  strategy: string;
}

export const DerivativesPanel: React.FC<Props> = ({ strategy }) => {
  const cfg = useDerivativesConfig();
  const patch = usePatchDerivativesProfile();

  const persisted = cfg.data?.profiles?.[strategy];
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

  return (
    <div style={card}>
      <div style={cardHead}>
        <span>DERIVATIVES · {strategy.toUpperCase()}</span>
        <span style={{ marginLeft: 'auto' }}>
          <button
            disabled={!dirty || patch.isPending}
            onClick={() => patch.mutate(draft)}
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

        {/* Master switch */}
        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>MASTER</div>
          <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: c.bright }}>
            <span>
              Profile enabled
              <span style={{ marginLeft: 6, fontSize: 9, color: c.dim, fontWeight: 400 }}>
                — when OFF, this strategy bypasses the selector and uses the legacy futures path
              </span>
            </span>
            <button
              onClick={() => set('enabled', !draft.enabled)}
              style={{
                padding: '4px 12px', borderRadius: 5, cursor: 'pointer',
                background: draft.enabled ? alpha(c.green, 0.15) : 'transparent',
                border: `1px solid ${draft.enabled ? alpha(c.green, 0.4) : c.border}`,
                color: draft.enabled ? c.green : c.dim, fontSize: 11, fontWeight: 800,
                letterSpacing: '0.08em', fontFamily: 'inherit',
              }}>
              {draft.enabled ? '● ON' : '○ OFF'}
            </button>
          </label>
        </div>

        {/* Auto-execute toggles — gate per-leg auto-fire when algo is ON. */}
        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>AUTO-EXECUTE (WHEN ALGO ON)</div>
          {(['auto_execute_futures', 'auto_execute_options'] as const).map((flagKey) => {
            const on = draft[flagKey];
            const label = flagKey === 'auto_execute_futures' ? 'Futures' : 'Options';
            return (
              <label key={flagKey} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: c.bright }}>
                <span>
                  {label}
                  <span style={{ marginLeft: 6, fontSize: 9, color: c.dim, fontWeight: 400 }}>
                    — when ON, scanner fires {label.toLowerCase()} rows automatically
                  </span>
                </span>
                <button
                  onClick={() => set(flagKey, !on)}
                  style={{
                    padding: '4px 12px', borderRadius: 5, cursor: 'pointer',
                    background: on ? alpha(c.amber, 0.15) : 'transparent',
                    border: `1px solid ${on ? alpha(c.amber, 0.4) : c.border}`,
                    color: on ? c.amber : c.dim, fontSize: 11, fontWeight: 800,
                    letterSpacing: '0.08em', fontFamily: 'inherit',
                  }}>
                  {on ? '● AUTO' : '○ MANUAL'}
                </button>
              </label>
            );
          })}
          <div style={{ fontSize: 9, color: c.dim, marginTop: 2 }}>
            Both default OFF. Auto-execute requires both: master `enabled` AND the per-leg toggle.
          </div>
        </div>

        {/* Instrument selection */}
        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>INSTRUMENT</div>
          <SelectRow label="Bias" value={draft.instrument_bias} options={['auto', 'futures', 'options']} onChange={(v) => set('instrument_bias', v as any)} />
          <NumRow label="Target delta" step={0.05} min={0} max={1} value={draft.target_delta} onChange={(v) => set('target_delta', v)} />
          <NumRow label="Delta tolerance" step={0.025} min={0} max={0.5} value={draft.target_delta_tolerance} onChange={(v) => set('target_delta_tolerance', v)} />
        </div>

        {/* Expiry / hold */}
        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>EXPIRY · HOLD</div>
          <NumRow label="DTE min" step={1} min={0} value={draft.dte_min} onChange={(v) => set('dte_min', Math.round(v))} />
          <NumRow label="DTE preferred" step={1} min={0} value={draft.dte_preferred} onChange={(v) => set('dte_preferred', Math.round(v))} />
          <NumRow label="DTE max" step={1} min={0} value={draft.dte_max} onChange={(v) => set('dte_max', Math.round(v))} />
          <NumRow label="Expected hold (min)" step={5} min={1} value={draft.expected_hold_minutes} onChange={(v) => set('expected_hold_minutes', Math.round(v))} />
          <NumRow label="Force-close mins before expiry" step={5} min={0} value={draft.expiry_close_minutes_before} onChange={(v) => set('expiry_close_minutes_before', Math.round(v))} />
        </div>

        {/* Sizing + risk caps */}
        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>RISK · SIZING</div>
          <NumRow label="Leverage cap (×)" step={1} min={1} value={draft.leverage_cap} onChange={(v) => set('leverage_cap', v)} />
          <NumRow label="Max premium % of NAV" step={0.005} min={0} max={0.1} value={draft.max_premium_pct_of_account} onChange={(v) => set('max_premium_pct_of_account', v)} />
          <NumRow label="Funding cost / R cap" step={0.05} min={0} max={1} value={draft.funding_cost_max_pct_of_R} onChange={(v) => set('funding_cost_max_pct_of_R', v)} />
        </div>

        {/* Liquidity floors */}
        <div style={{ ...grpBox, gap: 8 }}>
          <div style={grpTitle}>LIQUIDITY FLOORS</div>
          <NumRow label="Min OI" step={10} min={0} value={draft.min_oi} onChange={(v) => set('min_oi', v)} />
          <NumRow label="Max spread %" step={0.005} min={0} max={0.5} value={draft.max_spread_pct} onChange={(v) => set('max_spread_pct', v)} />
          <NumRow label="IVR cap (naked %)" step={5} min={0} max={100} value={draft.ivr_pct_naked_max} onChange={(v) => set('ivr_pct_naked_max', Math.round(v))} />
        </div>

      </div>
    </div>
  );
};
