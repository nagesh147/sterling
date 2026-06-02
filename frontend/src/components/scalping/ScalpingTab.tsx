import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { FuturesCandidatesTable } from '../derivatives/FuturesCandidatesTable';
import { OptionsCandidatesTable } from '../derivatives/OptionsCandidatesTable';
import { DerivativesPanel } from '../derivatives/DerivativesPanel';
import { EdgeGatePanel } from '../derivatives/EdgeGatePanel';
import { StrategyCatalogPanel } from '../derivatives/StrategyCatalogPanel';
import { DerivativesSettingsButton } from '../derivatives/DerivativesSettingsButton';
import { useDerivativesConfig, usePatchDerivativesGlobal, useResetDerivativesConfig } from '../../hooks/useDerivatives';
import { useSelectedUnderlying, useSetSelectedUnderlying } from '../../store/useStore';
import { useAlgoMode, useSetAlgoMode } from '../../hooks/useSignalAlerts';
import {
  useScalpingConfig, useSetScalpingConfig, useScalpingUniverse,
  useScalpingBacktest, useScalpingExecute, useScalpingSignals,
  useScalpingOptimize, useRunScalpingOptimize, useScalpingPresets, useScalpingDefaultConfig,
  type ScalpingConfig, type ScalpingSignal, type ScalpingProfile,
  type ScalpingExecuteResponse,
} from '../../hooks/useScalping';
import { usePositions, useClosePosition } from '../../hooks/usePositions';
import { useLivePnl } from '../../hooks/useLivePnl';
import type { PaperPosition } from '../../types';
import { useRouterMode, RouterMode } from '../../hooks/useRouterMode';
import { useTradingMode } from '../../hooks/useTradingMode';
import { useExchanges, useUpdateExchange } from '../../hooks/useExchanges';
import { useStreamPrices, useStreamStatus, useAppStream } from '../../hooks/useAppStream';
import { ThreeColumnLayout, LeftSection } from '../ThreeColumnLayout';

import { card, cardHead, cardBody, grpBox, grpTitle, chipStyle, gridStyle, tint, alpha, c } from '../../styles/terminalUI';

/* ── executed-trade tracking ───────────────────────────────────────────────── */

type ExecState = { resp?: ScalpingExecuteResponse; error?: string; auto?: boolean; mode?: string };
type SignalPnl = {
    value: number | null; realized: boolean; status?: string;
    currentSpot?: number | null;
    direction?: string; contracts?: number; leverage?: number;
    entryTimeMs?: number | null; entryPriceReal?: number | null;
    exitPriceReal?: number | null;
    initialSl?: number | null; initialTp?: number | null;
    currentSl?: number | null; currentTp?: number | null;
    trailMode?: string | null; trailState?: { current_stop: number; highest_seen: number; lowest_seen: number; breakeven_set: boolean } | null;
    orderId?: string | null; orderStatus?: string | null; mode?: string | null;
    structureType?: string;
  };

/* ── style tokens ──────────────────────────────────────────────────────────── */
/* card / cardHead / cardBody / grpBox / grpTitle now come from the shared
 * terminalUI module (single source of truth for the whole app). */

const dim: React.CSSProperties = { color: 'var(--t-dim)', fontSize: 11 };

/* ── shared components ────────────────────────────────────────────────────── */

function SectionCard({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={card}>
      <div style={cardHead}><span>{title}</span>{right && <span style={{ marginLeft: 'auto' }}>{right}</span>}</div>
      <div style={cardBody}>{children}</div>
    </div>
  );
}

function NumField({ label, value, step = 1, min, max, defaultVal, onChange }: {
  label: string; value: number; step?: number; min?: number; max?: number; defaultVal?: number; onChange: (v: number) => void;
}) {
  const isDefault = defaultVal !== undefined && value === defaultVal;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 10, fontWeight: 600, color: 'var(--t-muted)' }}>
        <span>{label}</span>
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

function TfSelect({ label, value, opts, defaultVal, onChange }: { label: string; value: string; opts: string[]; defaultVal?: string; onChange: (v: string) => void }) {
  const isDefault = defaultVal !== undefined && value === defaultVal;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 10, fontWeight: 600, color: 'var(--t-muted)' }}>
        <span>{label}</span>
        <select value={value} onChange={(e) => onChange(e.target.value)} style={{
          width: 74, 
          background: isDefault ? 'rgba(32, 144, 240, 0.1)' : 'var(--t-bg)', 
          border: isDefault ? '1px solid rgba(32, 144, 240, 0.3)' : '1px solid var(--t-border)', 
          borderRadius: 5,
          color: isDefault ? 'var(--t-blue)' : 'var(--t-bright)', 
          fontFamily: 'inherit', fontSize: 10, padding: '3px 6px', cursor: 'pointer',
          transition: 'all 0.15s ease',
        }}>
          {opts.map((o) => (
            <option key={o} value={o} style={{ background: 'var(--t-bg)', color: 'var(--t-text)' }}>
              {o}
            </option>
          ))}
        </select>
      </label>
      {defaultVal !== undefined && !isDefault && (
        <div style={{ fontSize: 9, color: 'var(--t-muted)', textAlign: 'right', paddingRight: 2, fontStyle: 'italic', opacity: 0.8 }}>
          Factory Default: {defaultVal}
        </div>
      )}
    </div>
  );
}

function Pill({ text, color, size = 9 }: { text: string; color: string; size?: number }) {
  return (
    <span style={{
      fontSize: size, letterSpacing: '0.06em', padding: '2px 0',
      borderRadius: 'var(--radius-sm)', background: alpha(color, 0.13), color, border: `1px solid ${alpha(color, 0.13)}`,
      whiteSpace: 'nowrap', display: 'inline-block', width: '100%', textAlign: 'center',
    }}>{text}</span>
  );
}

function BadgeColumn({ meta, profile }: { meta: { label: string; color: string }; profile?: string }) {
  return (
    <div style={{ width: 90, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--t-dim)', whiteSpace: 'nowrap' }}>{meta.label}</span>
      {profile && (
        <span style={{ fontSize: 9, fontWeight: 600, letterSpacing: '0.06em', color: 'var(--t-muted)', whiteSpace: 'nowrap' }}>
          [{profile.toUpperCase()}]
        </span>
      )}
    </div>
  );
}

function ChipToggle({ label, on, onChange, color }: { label: string; on: boolean; onChange: (v: boolean) => void; color?: string }) {
  const c = on ? (color || 'var(--t-green)') : 'var(--t-dim)';
  return (
    <button onClick={() => onChange(!on)} style={{
      fontSize: 9, fontWeight: 800, letterSpacing: '0.06em', padding: '3px 8px',
      borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontFamily: 'inherit',
      border: `1px solid ${on ? alpha(c, 0.27) : 'var(--t-border)'}`,
      background: on ? alpha(c, 0.13) : 'transparent',
      color: c, transition: 'all .1s', whiteSpace: 'nowrap', textTransform: 'uppercase',
    }}>{on ? '● ' : '○ '}{label}</button>
  );
}

const fmt = (v: number | null | undefined, d = 2) => (v == null || !isFinite(v) ? '—' : v.toFixed(d));
const fmtUsd = (v: number | null | undefined) => (v == null || !isFinite(v) ? '—' : '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 }));

// Recover the strategy slug from a position's note tag, e.g.
// "[SCALP-PRICE_ACTION] short …" → "price_action". This is what lets us
// reconstruct executed rows from real positions rather than localStorage.
const SCALP_TAG_RE = /\[SCALP-([A-Z_]+)\]/;
const stratFromNotes = (notes?: string | null): string | null => {
  const m = SCALP_TAG_RE.exec(notes || '');
  return m ? m[1].toLowerCase() : null;
};

// The setup details (direction / pattern / level) are embedded in the position
// notes at execute time, e.g. "[SCALP-MA_CROSSOVER] [AUTO] short
// sma_cross_below_ema near resistance 3217". Parse them back so reconstructed
// executed rows show the same "sma cross below ema / double top" column as live
// scan rows — keeping the table consistent across paper / shadow / live.
const parseScalpNotes = (notes?: string | null): {
  direction: string; pattern: string; level_type: string; near_level: number | null;
} => {
  // Strip every bracket tag ([PAPER]/[LIVE], [SCALP-…], [AUTO], …) to leave just
  // "short sma_cross_below_ema near resistance 3217".
  const body = (notes || '').replace(/\[[^\]]*\]/g, '').trim();
  const m = /^(long|short)\s+(\S+)\s+near\s+(\S+)\s+([\d.]+)/.exec(body);
  if (!m) return { direction: '', pattern: '', level_type: '', near_level: null };
  return { direction: m[1], pattern: m[2], level_type: m[3], near_level: parseFloat(m[4]) };
};

const STRATEGY_META: Record<string, { label: string; color: string }> = {
  price_action: { label: 'PRICE ACTION', color: 'var(--t-amber)' },
  smc: { label: 'SMC', color: 'var(--t-purple)' },
  ma_crossover: { label: 'MA CROSS', color: 'var(--t-blue)' },
  mean_reversion: { label: 'MEAN REV', color: 'var(--t-cyan)' },
  breakout: { label: 'BREAKOUT', color: 'var(--t-green)' },
  delta_gamma: { label: 'DELTA GAMMA', color: 'var(--t-pink)' },
};


/* ── config panel (in drawer) ─────────────────────────────────────────────── */

function ScalpingConfigPanel({ cfg, onSave, saving }: { cfg: ScalpingConfig; onSave: (c: ScalpingConfig) => void; saving: boolean }) {
  const [draft, setDraft] = useState<ScalpingConfig>(cfg);
  useEffect(() => { setDraft(cfg); }, [cfg]);
  
  const profileKeys = Object.keys(draft.profiles || {});
  const [activeTab, setActiveTab] = useState<string>(profileKeys[0] || 'intraday');

  const activeProfile = draft.profiles?.[activeTab];
  const setProfileField = <K extends keyof ScalpingProfile>(k: K, v: ScalpingProfile[K]) => {
    setDraft((d) => ({
      ...d,
      profiles: {
        ...d.profiles,
        [activeTab]: {
          ...d.profiles[activeTab],
          [k]: v
        }
      }
    }));
  };
  const setRootField = <K extends keyof ScalpingConfig>(k: K, v: ScalpingConfig[K]) => setDraft((d) => ({ ...d, [k]: v }));

  const stableStringify = (obj: any): string => {
    if (obj === null || typeof obj !== 'object') return JSON.stringify(obj);
    if (Array.isArray(obj)) return `[${obj.map(stableStringify).join(',')}]`;
    return `{${Object.keys(obj).sort().map(k => `"${k}":${stableStringify(obj[k])}`).join(',')}}`;
  };
  const dirty = stableStringify(draft) !== stableStringify(cfg);

  const universeQ = useScalpingUniverse();
  const universe = universeQ.data?.symbols ?? [];
  const presets = useScalpingPresets().data;
  const defaultCfg = useScalpingDefaultConfig().data?.config;
  const allMode = draft.symbols.length === 0;
  const selSet = new Set(draft.symbols);
  const toggleSym = (s: string) => setDraft((d) => {
    const cur = new Set(d.symbols);
    if (cur.has(s)) cur.delete(s); else cur.add(s);
    return { ...d, symbols: [...cur] };
  });

  return (
    <SectionCard title="Sterling SETTINGS" right={
      <span style={{ display: 'inline-flex', gap: 6 }}>
        <button
          disabled={!defaultCfg || saving}
          title="Reset every field to the validated factory defaults. Review, then APPLY to save."
          onClick={() => { 
            if (defaultCfg) {
              setDraft({
                ...defaultCfg,
                active_profiles: defaultCfg.active_profiles, // Overwrite with new optimized profile list
                symbols: draft.symbols,
              });
              // Reset the active tab to the first newly loaded profile
              if (defaultCfg.active_profiles?.length > 0) {
                setActiveTab(defaultCfg.active_profiles[0]);
              }
            }
          }}
          style={{
            fontSize: 9, fontWeight: 700, padding: '4px 12px', borderRadius: 5, fontFamily: 'inherit',
            cursor: defaultCfg && !saving ? 'pointer' : 'default',
            border: '1px solid var(--t-border)', background: 'transparent', color: 'var(--t-dim)',
          }}>↺ DEFAULTS</button>
        <button disabled={!dirty || saving} onClick={() => onSave(draft)} style={{
          fontSize: 9, fontWeight: 700, padding: '4px 14px', borderRadius: 5, fontFamily: 'inherit',
          cursor: dirty && !saving ? 'pointer' : 'default',
          border: `1px solid ${dirty ? 'var(--t-green)' : 'var(--t-border)'}`,
          background: dirty ? 'var(--t-green)22' : 'transparent',
          color: dirty ? 'var(--t-green)' : 'var(--t-dim)',
        }}>{saving ? 'SAVING…' : dirty ? 'APPLY' : 'SAVED'}</button>
      </span>
    }>
      <div style={{ 
        background: draft.use_optimized ? 'var(--t-blue)14' : 'var(--t-amber)14', 
        border: `1px solid ${draft.use_optimized ? 'var(--t-blue)44' : 'var(--t-amber)44'}`, 
        padding: '10px 12px', borderRadius: 6, marginBottom: 16, fontSize: 10, 
        color: draft.use_optimized ? 'var(--t-blue)' : 'var(--t-amber)', lineHeight: 1.5,
        display: 'flex', flexDirection: 'column', gap: 8
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>{draft.use_optimized ? '🤖 INSTITUTIONAL WFO ACTIVE' : '👤 RETAIL MODE ACTIVE'}</strong>
            <ChipToggle label="AI Gatekeeper" on={draft.use_optimized ?? false} onChange={(v) => setRootField('use_optimized', v)} />
        </div>
        {draft.use_optimized ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span><strong>Institutional WFO Active:</strong> The backend is mathematically enforcing the <strong>Edge Whitelist</strong> to protect your capital. It structurally blocks all trades except those verified by our vector simulations.</span>
              <span style={{ color: 'var(--t-green)', fontWeight: 600 }}>💡 TOP PICKS ENFORCED: The Gatekeeper currently routes you into the highest-edge environments discovered: BTC 4H MA-Crossover (+95% net edge), ETH 2H/4H SMC (+46% net edge), and BTC 1H Price Action. We highly recommend leaving this enabled.</span>
            </div>
        ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span><strong>Retail Mode Active:</strong> The AI Gatekeeper is bypassed. The scanner will strictly execute <strong>exactly what you configure below</strong>.</span>
              <span style={{ color: 'var(--t-red)', fontWeight: 600 }}>⚠️ WARNING: Recent vector testing proved that unrestricted Retail Mode generates up to 3.3 million noise trades across 1m/5m/15m timeframes, destroying edge via fees and slippage. We HIGHLY RECOMMEND enabling the AI Gatekeeper for live accounts.</span>
            </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 5, marginBottom: 12, flexWrap: 'wrap' }}>
        {profileKeys.map(p => (
          <ChipToggle 
            key={p} 
            label={`Run ${p.toUpperCase()}`} 
            on={(draft.active_profiles || []).includes(p)} 
            onChange={(on) => {
              const cur = new Set(draft.active_profiles);
              if (on) cur.add(p); else cur.delete(p);
              setRootField('active_profiles', [...cur]);
            }} 
          />
        ))}
      </div>

      <div style={{ display: 'flex', gap: 6, borderBottom: '1px solid var(--t-border)', paddingBottom: 10, marginBottom: 12 }}>
        {profileKeys.map(p => (
          <button key={p} onClick={() => setActiveTab(p)} style={{
            fontSize: 10, fontWeight: 800, padding: '4px 12px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
            border: `1px solid ${activeTab === p ? 'var(--t-blue)' : 'var(--t-border)'}`,
            background: activeTab === p ? 'var(--t-bg3)' : 'transparent',
            color: activeTab === p ? 'var(--t-blue)' : 'var(--t-dim)',
          }}>{p.toUpperCase()}</button>
        ))}
      </div>

      {activeProfile && (
        <>
          {(() => {
            const defP = defaultCfg?.profiles?.[activeTab];
            return (
              <>
                <div style={{ display: 'flex', gap: 5, marginBottom: 12, flexWrap: 'wrap' }}>
                  <ChipToggle label="Price Action" color="var(--t-amber)" on={activeProfile.enable_price_action} onChange={(v) => setProfileField('enable_price_action', v)} />
                  <ChipToggle label="SMC" color="var(--t-purple)" on={activeProfile.enable_smc} onChange={(v) => setProfileField('enable_smc', v)} />
                  <ChipToggle label="MA Crossover" color="var(--t-blue)" on={activeProfile.enable_ma_crossover} onChange={(v) => setProfileField('enable_ma_crossover', v)} />
                  <ChipToggle label="Mean Reversion" color="var(--t-cyan)" on={activeProfile.enable_mean_reversion} onChange={(v) => setProfileField('enable_mean_reversion', v)} />
                  <ChipToggle label="Breakout" color="var(--t-green)" on={activeProfile.enable_breakout} onChange={(v) => setProfileField('enable_breakout', v)} />
                  <ChipToggle label="Delta-Gamma" color="var(--t-pink)" on={activeProfile.enable_delta_gamma} onChange={(v) => setProfileField('enable_delta_gamma', v)} />
                </div>

                <div style={gridStyle()}>
                  {draft.use_optimized ? (
                    <div style={{ ...grpBox, gridColumn: '1 / -1', textAlign: 'center', padding: '24px 12px', background: 'var(--t-bg2)', border: '1px dashed var(--t-blue)44' }}>
                      <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--t-blue)', marginBottom: 8, letterSpacing: '0.05em' }}>🔒 STRATEGY LOGIC MANAGED BY AI</div>
                      <div style={{ fontSize: 10, color: 'var(--t-muted)', lineHeight: 1.5, maxWidth: 400, margin: '0 auto' }}>
                        The Walk-Forward Optimizer is currently overriding manual thresholds for Timeframes, SMC, MA Crossover, Mean Reversion, Breakout, and Delta-Gamma. 
                        It calculates dynamic expectancy limits in real-time. Turn off the AI Gatekeeper above to unlock manual overrides.
                      </div>
                    </div>
                  ) : (
                    <>
                      <div style={grpBox}>
                        <div style={grpTitle}>TIMEFRAMES</div>
                        <TfSelect label="Structure" value={activeProfile.macro_timeframe} opts={['1h', '2h', '4h']} defaultVal={defP?.macro_timeframe} onChange={(v) => setProfileField('macro_timeframe', v)} />
                        <TfSelect label="Entry" value={activeProfile.execution_timeframe} opts={['1m', '5m', '15m', '30m']} defaultVal={defP?.execution_timeframe} onChange={(v) => setProfileField('execution_timeframe', v)} />
                      </div>
                      <div style={grpBox}>
                        <div style={grpTitle}>STRUCTURE LEVELS</div>
                        <NumField label="Min touches" value={activeProfile.level_touches} min={2} max={10} defaultVal={defP?.level_touches} onChange={(v) => setProfileField('level_touches', v)} />
                        <NumField label="Tolerance %" value={activeProfile.level_tolerance_pct} step={0.1} min={0.1} max={3} defaultVal={defP?.level_tolerance_pct} onChange={(v) => setProfileField('level_tolerance_pct', v)} />
                      </div>
                      <div style={grpBox}>
                        <div style={grpTitle}>PRICE ACTION</div>
                        <NumField label="Lookback" value={activeProfile.pa_lookback_bars} min={5} max={100} defaultVal={defP?.pa_lookback_bars} onChange={(v) => setProfileField('pa_lookback_bars', v)} />
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                            <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>Confirm bars</span>
                            <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
                              {[1, 3, 5].map((n) => {
                                const on = activeProfile.pa_confirm_bars === n;
                                const isDef = defP && n === defP.pa_confirm_bars;
                                return (
                                  <button key={n} onClick={() => setProfileField('pa_confirm_bars', n)} style={{
                                    fontSize: 10, fontWeight: 700, padding: '3px 9px', borderRadius: 5, cursor: 'pointer', fontFamily: 'inherit',
                                    border: `1px solid ${on ? (isDef ? 'rgba(32, 144, 240, 0.4)' : 'var(--t-border)') : 'transparent'}`,
                                    background: on ? (isDef ? 'rgba(32, 144, 240, 0.1)' : 'var(--t-bg3)') : 'transparent',
                                    color: on ? (isDef ? 'var(--t-blue)' : 'var(--t-bright)') : 'var(--t-dim)',
                                    transition: 'all 0.15s ease',
                                  }}>{n}</button>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                      </div>
                      <div style={grpBox}>
                        <div style={grpTitle}>SMC</div>
                        <NumField label="Imbalance ratio" value={activeProfile.smc_imbalance_ratio} step={0.1} min={1.0} max={3.0} defaultVal={defP?.smc_imbalance_ratio} onChange={(v) => setProfileField('smc_imbalance_ratio', v)} />
                      </div>
                      <div style={grpBox}>
                        <div style={grpTitle}>MA CROSSOVER</div>
                        <NumField label="SMA period" value={activeProfile.ma_fast_sma} min={2} max={20} defaultVal={defP?.ma_fast_sma} onChange={(v) => setProfileField('ma_fast_sma', v)} />
                        <NumField label="EMA period" value={activeProfile.ma_slow_ema} min={3} max={50} defaultVal={defP?.ma_slow_ema} onChange={(v) => setProfileField('ma_slow_ema', v)} />
                      </div>
                      <div style={grpBox}>
                        <div style={grpTitle}>MEAN REVERSION</div>
                        <NumField label="Z-Score Window" value={activeProfile.mr_zscore_window} min={5} max={100} defaultVal={defP?.mr_zscore_window} onChange={(v) => setProfileField('mr_zscore_window', v)} />
                        <NumField label="Z-Score Threshold" value={activeProfile.mr_zscore_threshold} step={0.1} min={1.0} max={5.0} defaultVal={defP?.mr_zscore_threshold} onChange={(v) => setProfileField('mr_zscore_threshold', v)} />
                      </div>
                      <div style={grpBox}>
                        <div style={grpTitle}>BREAKOUT</div>
                        <NumField label="RSI Long Threshold" value={activeProfile.bo_rsi_long_threshold} step={1} min={50} max={90} defaultVal={defP?.bo_rsi_long_threshold} onChange={(v) => setProfileField('bo_rsi_long_threshold', v)} />
                        <NumField label="RSI Short Threshold" value={activeProfile.bo_rsi_short_threshold} step={1} min={10} max={50} defaultVal={defP?.bo_rsi_short_threshold} onChange={(v) => setProfileField('bo_rsi_short_threshold', v)} />
                      </div>
                      <div style={grpBox}>
                        <div style={grpTitle}>DELTA-GAMMA</div>
                        <NumField label="GEX Flip Threshold" value={activeProfile.dg_gex_flip_threshold} step={0.1} min={-5.0} max={5.0} defaultVal={defP?.dg_gex_flip_threshold} onChange={(v) => setProfileField('dg_gex_flip_threshold', v)} />
                        <NumField label="Wall Proximity %" value={activeProfile.dg_wall_proximity_pct} step={0.001} min={0.001} max={0.05} defaultVal={defP?.dg_wall_proximity_pct} onChange={(v) => setProfileField('dg_wall_proximity_pct', v)} />
                        <div style={{ marginTop: 4 }}>
                          <ChipToggle label="Filter Breakouts by Gamma" on={activeProfile.dg_filter_breakouts} onChange={(v) => setProfileField('dg_filter_breakouts', v)} />
                        </div>
                      </div>
                    </>
                  )}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, gridColumn: '1 / -1' }}>
                    <div style={grpBox}>
                      <div style={grpTitle}>DIRECTION & RISK</div>
                      {draft.use_optimized && !activeProfile.macro_trend_filter && (
                        <div style={{
                          padding: '8px 10px', marginBottom: 8, borderRadius: 6,
                          background: 'var(--t-amber)14', border: '1px solid var(--t-amber)44',
                          fontSize: 10, color: 'var(--t-amber)', lineHeight: 1.4
                        }}>
                          <strong>⚠️ Trend Filter is OFF:</strong> It is highly recommended to leave the Trend Filter ON when the AI Gatekeeper is active. Walk-Forward Optimization generally assumes you are trading with the broader structural trend.
                        </div>
                      )}
                      <div style={{ display: 'flex', gap: 5, marginBottom: 12, flexWrap: 'wrap' }}>
                        <ChipToggle label="Long" on={activeProfile.allow_long} onChange={(v) => setProfileField('allow_long', v)} />
                        <ChipToggle label="Short" on={activeProfile.allow_short} onChange={(v) => setProfileField('allow_short', v)} />
                        <ChipToggle label="Trend filter" on={activeProfile.macro_trend_filter} onChange={(v) => setProfileField('macro_trend_filter', v)} />
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <NumField label="Risk % / trade" value={activeProfile.risk_percent} step={0.05} min={0.05} max={5} defaultVal={defP?.risk_percent} onChange={(v) => setProfileField('risk_percent', v)} />
                        <NumField label="Max position %" value={activeProfile.max_position_pct} step={1} min={1} max={100} defaultVal={defP?.max_position_pct} onChange={(v) => setProfileField('max_position_pct', v)} />
                        <NumField label="Min R:R" value={activeProfile.min_rr} step={0.1} min={0.5} max={10.0} defaultVal={defP?.min_rr} onChange={(v) => setProfileField('min_rr', v)} />
                        <NumField label="Max Stop ATR" value={activeProfile.max_stop_atr} step={0.5} min={1.0} max={20.0} defaultVal={defP?.max_stop_atr} onChange={(v) => setProfileField('max_stop_atr', v)} />
                        <NumField label="Equity $" value={activeProfile.account_equity} step={1000} min={100} defaultVal={defP?.account_equity} onChange={(v) => setProfileField('account_equity', v)} />
                      </div>
                    </div>
                    
                    <div style={grpBox}>
                      <div style={grpTitle}>SYMBOLS (Global)</div>
                    
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, maxHeight: 160, overflowY: 'auto', paddingRight: 4, flexShrink: 0, marginTop: 4 }}>
                      {draft.symbols.length === 0 ? (
                        <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>Scanning ALL symbols. Add a symbol to restrict scanning.</span>
                      ) : (
                        draft.symbols.map((s) => {
                          const isLocked = ['BTC', 'ETH', 'SOL'].includes(s);
                          return (
                            <button 
                              key={s} 
                              onClick={() => !isLocked && toggleSym(s)} 
                              style={{ 
                                ...chipStyle(true), 
                                background: 'var(--t-blue)15', 
                                borderColor: 'var(--t-blue)44',
                                cursor: isLocked ? 'default' : 'pointer',
                              }}
                              title={isLocked ? "Core symbols cannot be removed" : "Click to remove"}
                            >
                              {s} 
                              {!isLocked && <span style={{ marginLeft: 4, opacity: 0.6 }}>×</span>}
                              {isLocked && <span style={{ marginLeft: 4, opacity: 0.4 }}>🔒</span>}
                            </button>
                          );
                        })
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
                        {universe.filter(s => !selSet.has(s)).map(s => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
                </div>
              </>
            );
          })()}
        </>
      )}
    </SectionCard>
  );
}

/* ── signal card ────────────────────────────────────────────────────────────── */

function PlanCell({ value, color, width = 78 }: { value: React.ReactNode; color?: string; width?: number | string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', width, minWidth: 0, flexShrink: 0, justifyContent: 'center' }}>
      <span style={{
        fontSize: 13, fontWeight: 700, color: color || 'var(--t-bright)', lineHeight: 1.2,
        fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>{value}</span>
    </div>
  );
}

/** Stop/Target cell: live (trailed) value on top, with the original struck through
 *  and the points moved beneath it once the trail / dynamic-TP has shifted the level. */
function PlanLevelCell({ initial, current, color, width = 96, favorableUp, badges }: {
  initial: number | null | undefined; current: number | null | undefined;
  color?: string; width?: number | string; favorableUp?: boolean; badges?: React.ReactNode;
}) {
  const moved = current != null && initial != null && Math.abs(current - initial) > 1e-6;
  const shown = current ?? initial;
  const diff = moved ? (current! - initial!) : 0;
  // "good" = moved in the trade's favour (stop ratcheting up / target extending for a long).
  const good = favorableUp ? diff > 0 : diff < 0;
  const sign = diff >= 0 ? '+' : '−';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', width, minWidth: 0, flexShrink: 0, justifyContent: 'center' }}>
      <span style={{
        fontSize: 11, fontWeight: 400, color: color || 'var(--t-bright)', lineHeight: 1.15,
        fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        display: 'flex', alignItems: 'center', gap: 4,
      }}>{fmtUsd(shown)}{badges}</span>
      {moved && (
        <span style={{ fontSize: 9, lineHeight: 1.25, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', color: 'var(--t-dim)' }}>
          <span style={{ textDecoration: 'line-through', opacity: 0.65 }}>{fmtUsd(initial)}</span>{' '}
          <span style={{ color: good ? 'var(--t-green)' : 'var(--t-red)', fontWeight: 700 }}>{sign}{Math.abs(diff).toFixed(1)}</span>
        </span>
      )}
    </div>
  );
}

/* Single source of truth for the signals "table" columns. The header and every
 * row render from this one spec via CSS grid, so the columns can never drift
 * apart. The `plan` columns (the trade plan) are shown only when at least one
 * armed/executed signal exists — header and rows both honour `showPlan`, so a
 * "Watching-only" list collapses the plan columns in lockstep. */
type SignalCol = {
  key: string; label: string; width: string;
  plan?: boolean; action?: boolean; dir?: boolean; pattern?: boolean; align?: 'center' | 'left' | 'right';
  pnl?: boolean; pnlType?: boolean;
};
// Flexible columns (minmax + fr) absorb the spare width so the table fills the
// center column instead of crowding to the left. Fixed columns stay fixed.
const SIGNAL_COLS: SignalCol[] = [
  { key: 'accent',   label: '',                 width: '4px' },
  { key: 'symbol',   label: 'Symbol',           width: 'minmax(50px, 0.7fr)' },
  { key: 'id',       label: 'ID',               width: 'minmax(36px, 0.4fr)' },
  { key: 'time',     label: 'Time',             width: 'minmax(56px, 0.8fr)' },
  { key: 'status',   label: 'Status',           width: 'minmax(60px, 0.8fr)' },
  { key: 'dir',      label: 'Direction',        width: 'minmax(70px, 1fr)',  dir: true },
  { key: 'entry',    label: 'Entry',            width: 'minmax(70px, 1fr)',  plan: true },
  { key: 'current',  label: 'Current',          width: 'minmax(90px, 1.2fr)', plan: true },
  { key: 'stop',     label: 'Stop',             width: 'minmax(70px, 1fr)',  plan: true },
  { key: 'target',   label: 'Target',           width: 'minmax(70px, 1fr)',  plan: true },
  { key: 'risk',     label: 'Risk',             width: 'minmax(46px, 0.6fr)',  plan: true },
  { key: 'strategy', label: 'Strategy',         width: 'minmax(70px, 0.8fr)' },
  { key: 'pattern',  label: 'Pattern',          width: 'minmax(90px, 1fr)', align: 'center', pattern: true },
  { key: 'profile',  label: 'Profile',          width: 'minmax(50px, 0.5fr)' },
  { key: 'pnl',      label: 'P&L',              width: 'minmax(70px, 0.9fr)', align: 'right', pnl: true },
  { key: 'type',     label: '',                 width: 'minmax(60px, 0.7fr)', align: 'right', pnlType: true },
  { key: 'action',   label: 'Action',           width: 'minmax(110px, 1fr)', action: true },
];
const PLAN_COL_SPAN = SIGNAL_COLS.filter((c) => c.plan).length;

// Columns for the rendered signals <table> — drops the thin accent marker (the
// strategy colour now lives in the Strategy pill). The signals table mirrors the
// derivatives candidate tables' <thead>/<td> structure so all tables look alike.
// Profile and pattern are surfaced in the expanded row details, not as their own columns.
const TABLE_COLS = SIGNAL_COLS.filter((col) => col.key !== 'accent' && col.key !== 'profile' && col.key !== 'pattern');
const TABLE_COL_COUNT = TABLE_COLS.length;

// Fixed table-layout column widths (percent of table width). With
// `table-layout: fixed` these freeze the columns, so live value updates
// (price, P&L, trailed stops) never reflow the table. Keyed by SIGNAL_COLS key.
const SIGNAL_COL_PCT: Record<string, string> = {
  symbol: '6%', id: '4%', time: '5%', status: '5%', dir: '5%',
  entry: '7%', current: '11%', stop: '7%', target: '7%', risk: '4%',
  strategy: '5%', pnl: '7%', type: '6%', action: '21%',
};

// Which optional columns are visible. Plan = an armed/executed signal exists;
// Action = a row can act; Dir = a row has a long/short bias. Each is dropped
// when empty so the table never shows an all-"—" or dead column.
type ColFlags = { plan: boolean; action: boolean; dir: boolean; pattern?: boolean };
const showCol = (c: SignalCol, f: ColFlags) =>
  (f.plan || !c.plan) && (f.action || !c.action) && (f.dir || !c.dir) && (f.pattern !== false || !c.pattern);

// Experiment toggle: when true, every column (except the thin accent bar) gets
// an equal share of the width. Flip to false to restore the tailored per-column
// widths in SIGNAL_COLS.
const UNIFORM_COLS = false;

/** Shared grid style for the header row and every card's main row — identical
 *  template + gap guarantees the columns line up. */
function signalRowGrid(f: ColFlags): React.CSSProperties {
  const cols = SIGNAL_COLS.filter((c) => showCol(c, f));
  return {
    display: 'grid',
    gridTemplateColumns: cols
      .map((c) => (c.key === 'accent' ? c.width : UNIFORM_COLS ? 'minmax(0, 1fr)' : c.width))
      .join(' '),
    columnGap: 12,
    alignItems: 'center',
  };
}

function SignalTableHeader({ flags }: { flags: ColFlags }) {
  // Matches the derivatives candidate-table <thead>: recessed surface strip,
  // 9px uppercase dim labels, single bottom border.
  return (
    <div style={{
      ...signalRowGrid(flags), padding: '6px 16px 6px 0',
      background: 'var(--t-bg2)', borderBottom: '1px solid var(--t-border)',
    }}>
      {SIGNAL_COLS.filter((c) => showCol(c, flags)).map((c) => (
        <span key={c.key} style={{
          fontSize: 9, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.08em',
          textTransform: 'uppercase', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          textAlign: c.align ?? 'left',
        }}>{c.label}</span>
      ))}
    </div>
  );
}

/* ── executed-trade detail (friendly summary + metrics) ────────────────────── */

const fmtTime = (ms?: number) =>
  ms ? new Date(ms).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '—';

/** Format raw backend reason strings for user-friendly display:
 *  - "SMA({fast}) crossed above EMA({slow})" → "SMA(10) crossed above EMA(20)"
 *  - "bullish imbalance engulfing prior bearish candle after inducement below 4H support 83"
 *    → "Bullish imbalance engulfing prior bearish candle after inducement below 4H support 83"
 *  - "Watching: near 4H support @ 83" → "Near 4H support @ 83"
 *  - "near 4H support @ 83" → "Near 4H support @ 83"
 *  - "SMAbelow EMA" → "SMA below EMA"
 *  - "sma_cross_below_ema" → "sma cross below ema" (handled by replaceAlready)
 */
function formatReason(raw: string): string {
  let s = raw
    .replace(/^Watching:\s*/i, '')
    .replace(/^SMA(\d+)/i, (_, n) => `SMA(${n})`)
    .replace(/^EMA(\d+)/i, (_, n) => `EMA(${n})`)
    .replace(/SMAbelow/i, 'SMA below')
    .replace(/SMAabove/i, 'SMA above')
    .replace(/SMA\b(?!\()/i, 'SMA ')
    .replace(/EMA\b(?!\()/i, 'EMA ')
    .replace(/\s+@\s+/, ' @ ');
  // Capitalize first letter
  s = s.charAt(0).toUpperCase() + s.slice(1);
  return s;
}

// Backend status codes → plain-English explanations.
const EXEC_STATUS_FRIENDLY: Record<string, string> = {
  no_signal: 'No signal was ready to trade for this strategy at execution time.',
  no_plan: 'The signal had no complete trade plan (missing entry or stop).',
  size_too_small: 'Risk-based position size came out below 1 contract.',
  rejected: 'The order was rejected by the exchange.',
  error: 'The order could not be routed.',
};

// Three configured trading modes: PAPER (no keys), SHADOW (keys + paper), LIVE (keys + real).
const MODE_META: Record<string, { color: string; glyph: string }> = {
  LIVE:   { color: 'var(--t-amber)', glyph: '●' },
  SHADOW: { color: 'var(--t-blue)',  glyph: '◑' },
  PAPER:  { color: 'var(--t-green)', glyph: '◐' },
};
const modeColorOf = (m: string) => MODE_META[m]?.color ?? 'var(--t-dim)';

const MODE_HINT: Record<RouterMode, string> = {
  paper: 'No exchange call — pure simulation.',
  shadow: 'Keys present, but orders are simulated (no real fill).',
  live: 'Real money — orders execute on the exchange.',
};

/** Inline paper / shadow / live selector wired to the authoritative router mode.
 *  Switching to LIVE is routed through the parent so it can show a confirm modal. */
function ModeSelector({ mode, onChange }: { mode: RouterMode; onChange: (m: RouterMode) => void }) {
  const pick = (m: RouterMode) => {
    if (m === mode) return;
    onChange(m);
  };
  return (
    <div style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 3, background: 'var(--t-bg2)', border: '1px solid var(--t-border)', borderRadius: 6, padding: 2 }}>
      {(['paper', 'shadow', 'live'] as RouterMode[]).map((m) => {
        const active = mode === m;
        const c = modeColorOf(m.toUpperCase());
        return (
          <button
            key={m}
            onClick={() => pick(m)}
            title={MODE_HINT[m]}
            style={{
              padding: '3px 10px', borderRadius: 4, cursor: active ? 'default' : 'pointer', fontFamily: 'inherit',
              fontSize: 9, fontWeight: active ? 700 : 500, letterSpacing: '0.08em', textTransform: 'uppercase',
              border: `1px solid ${active ? c + '88' : 'transparent'}`,
              background: active ? c + '20' : 'transparent',
              color: active ? c : 'var(--t-dim)', transition: 'all .12s',
            }}
          >
            {MODE_META[m.toUpperCase()]?.glyph} {m}
          </button>
        );
      })}
    </div>
  );
}

/** Confirmation modal shown before switching the router to LIVE (real money). */
function GoLiveModal({ fromMode, hasCreds, onConfirm, onCancel }: { fromMode: RouterMode; hasCreds: boolean; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
      style={{ position: 'fixed', inset: 0, background: 'var(--surface-overlay)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
    >
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 6, padding: '22px 24px', width: 400,
      }}>
        <div style={{ fontSize: 15, fontWeight: 900, color: 'var(--t-amber)', marginBottom: 6 }}>⚡ Switch to LIVE trading</div>
        <div style={{ fontSize: 11, color: 'var(--t-dim)', lineHeight: 1.6, marginBottom: 16 }}>
          Signals will execute with <b style={{ color: 'var(--t-bright)' }}>real money</b> on the exchange instead of paper.
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 18 }}>
          {[
            ['💸', 'Orders place real funds on Delta Exchange'],
            ['⚙️', 'This also switches the exchange account from Paper to Live'],
            ['🛑', 'Kill switch & daily-loss limits still apply'],
          ].map(([icon, text]) => (
            <div key={text} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 11, color: 'var(--t-bright)' }}>
              <span style={{ fontSize: 13, flexShrink: 0 }}>{icon}</span>
              <span style={{ lineHeight: 1.5 }}>{text}</span>
            </div>
          ))}
        </div>
        {!hasCreds && (
          <div style={{
            display: 'flex', gap: 8, alignItems: 'flex-start', padding: '8px 10px', marginBottom: 16,
            borderRadius: 6, background: 'var(--t-red)14', border: '1px solid var(--t-red)44',
            fontSize: 10.5, color: 'var(--t-red)', lineHeight: 1.5,
          }}>
            <span>⚠️</span>
            <span>No live credentials configured. Add your Delta Exchange API keys first (Exchange settings) — live trading can't be enabled without them.</span>
          </div>
        )}
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={onCancel} style={{
            flex: 1, padding: '10px 0', background: 'transparent', color: 'var(--t-dim)',
            border: '1px solid var(--t-border)', borderRadius: 7, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
          }}>Stay {fromMode.charAt(0).toUpperCase() + fromMode.slice(1)}</button>
          <button onClick={onConfirm} disabled={!hasCreds} style={{
            flex: 2, padding: '10px 0', background: hasCreds ? 'var(--t-amber)' : 'var(--t-border)',
            color: hasCreds ? '#000' : 'var(--t-dim)', border: 'none',
            borderRadius: 7, cursor: hasCreds ? 'pointer' : 'not-allowed', fontFamily: 'inherit', fontSize: 12, fontWeight: 800, letterSpacing: '0.06em',
          }}>▶ Go Live</button>
        </div>
      </div>
    </div>
  );
}

// The API surfaces some errors as a JSON blob in `detail` — pull out the human part.
function friendlyError(raw?: string): string {
  if (!raw) return 'Execution failed.';
  let msg = raw.trim();
  if (msg.startsWith('{')) {
    try {
      const o = JSON.parse(msg) as Record<string, string>;
      msg = o.error || o.detail || o.message || o.reason || msg;
    } catch { /* not JSON — keep raw */ }
  }
  return msg;
}

// Why an execution didn't go through — always surface the specific reason the
// backend/exchange returned (e.g. "Insufficient margin", "Exchange is in Paper"),
// falling back to the friendly status label only when no reason is given.
function failureReason(es: ExecState): string {
  if (es.error) return friendlyError(es.error);
  const r = es.resp;
  if (!r) return 'Execution failed.';
  const specific = (r.reason || '').trim();
  if (r.status === 'rejected' || r.status === 'error') {
    return specific ? friendlyError(specific) : (EXEC_STATUS_FRIENDLY[r.status] ?? r.status);
  }
  return EXEC_STATUS_FRIENDLY[r.status] ?? friendlyError(specific || r.status);
}

function extractServerIp(raw?: string): string | null {
  if (!raw) return null;
  try {
    const o = JSON.parse(raw.trim()) as Record<string, string>;
    return o.server_ip || null;
  } catch {
    const m = raw.match(/add server IP\s+(\d+\.\d+\.\d+\.\d+)/i);
    return m ? m[1] : null;
  }
}

function MetricItem({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 60 }}>
      <span style={{ fontSize: 9, letterSpacing: '0.07em', color: 'var(--t-dim)', fontWeight: 600, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ fontSize: 11, fontWeight: 700, color: color || 'var(--t-bright)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{value}</span>
    </div>
  );
}

function ExecDetail({ execState, pnl, profile, pattern }: { execState: ExecState; pnl?: SignalPnl; profile?: string; pattern?: string }) {
  const r = execState.resp;
  const err = execState.error;
  const accepted = !!r?.accepted;
  const mode = execState.mode || (r?.mode ? r.mode.toUpperCase() : '');
  const src = execState.auto ? 'Auto' : 'Manual';

  let icon: string, hColor: string, headline: string;
  if (err) { icon = '✕'; hColor = 'var(--t-red)'; headline = `${src} execution hit an error`; }
  else if (accepted) { icon = '✓'; hColor = 'var(--t-green)'; headline = `${src}-executed on ${mode}`; }
  else { icon = '✕'; hColor = 'var(--t-amber)'; headline = `${src} execution didn't go through${mode ? ` on ${mode}` : ''}`; }

  const what = err ? friendlyError(err) : (r ? (EXEC_STATUS_FRIENDLY[r.status] ?? friendlyError(r.reason || r.status)) : '');
  const serverIp = err ? extractServerIp(err) : null;

  const pnlVal = pnl?.value ?? null;
  const pnlColor = pnlVal == null ? 'var(--t-dim)' : pnlVal >= 0 ? 'var(--t-green)' : 'var(--t-red)';

  return (
    <div
      onClick={(e) => e.stopPropagation()}
      style={{
        marginLeft: 18, padding: '9px 11px', borderRadius: 8,
        background: 'var(--t-bg)', border: `1px solid ${hColor}33`,
        display: 'flex', flexDirection: 'column', gap: 6,
      }}
    >
      {/* headline + timestamp */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: hColor, letterSpacing: '0.02em' }}>{icon} {headline}</span>
        <span style={{ fontSize: 9, color: 'var(--t-dim)', fontVariantNumeric: 'tabular-nums' }}>{fmtTime(r?.timestamp_ms)}</span>
      </div>

      {/* what happened */}
      {what && <span style={{ fontSize: 11, color: 'var(--t-dim)', lineHeight: 1.5, wordBreak: 'break-word' }}>{what}</span>}

      {/* copyable server IP for ip_not_whitelisted errors */}
      {serverIp && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <code style={{ fontSize: 11, fontWeight: 800, color: 'var(--t-bright)', letterSpacing: 0.5, background: 'var(--t-bg3)', padding: '2px 8px', borderRadius: 4, fontFamily: 'monospace' }}>{serverIp}</code>
          <button
            onClick={() => navigator.clipboard.writeText(serverIp)}
            style={{ fontSize: 9, fontWeight: 700, color: 'var(--t-blue)', background: 'var(--t-blue)14', border: '1px solid var(--t-blue)44', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontFamily: 'inherit' }}
          >Copy IP</button>
        </div>
      )}

      {/* metrics — shown once an order actually went through */}
      {accepted && r && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 18px', paddingTop: 1 }}>
          <MetricItem label="Qty" value={r.size_units ? fmt(r.size_units, 4) : '—'} />
          <MetricItem label="Entry" value={fmtUsd(pnl?.entryPriceReal ?? r.entry_price)} />
          {pnl?.realized && pnl?.exitPriceReal != null && (
            <MetricItem label="Exit" value={fmtUsd(pnl.exitPriceReal)} />
          )}
          {pnl?.currentSpot != null && (() => {
            const entryPx = pnl?.entryPriceReal ?? r.entry_price ?? 0;
            const diff = pnl.currentSpot - entryPx;
            const fav = pnl.direction === 'short' ? diff < 0 : diff > 0;
            const diffColor = diff === 0 ? 'var(--t-dim)' : fav ? 'var(--t-green)' : 'var(--t-red)';
            const sign = diff >= 0 ? '+' : '−';
            const currentValNode = (
              <span>
                {fmtUsd(pnl.currentSpot)} <span style={{ fontSize: 9, opacity: 0.7, fontWeight: 600 }}>({sign}{Math.abs(diff).toFixed(2)})</span>
              </span>
            );
            return (
              <MetricItem label="Current" value={currentValNode} color={diffColor} />
            );
          })()}
          <MetricItem label="Initial SL" value={fmtUsd(pnl?.initialSl ?? r.stop_loss)} color="var(--t-red)" />
          {pnl?.currentSl != null && pnl.currentSl !== pnl?.initialSl && (
            <MetricItem label="Trail SL" value={fmtUsd(pnl.currentSl)} color="var(--t-amber)" />
          )}
          <MetricItem label="Target" value={
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              {fmtUsd(pnl?.initialTp ?? r.take_profit)}
              {r.tp_source && r.tp_source.includes('fallback') && (
                <span title="Target determined by fallback Risk-Reward" style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: '0.04em' }}>[RR]</span>
              )}
              {r.tp_source && r.tp_source.includes('swing') && (
                <span title="Target determined by dynamic swing padding" style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: '0.04em' }}>[SW]</span>
              )}
              {r.tp_source === 'structural_level' && (
                <span title="Target determined by structural level" style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: '0.04em' }}>[LVL]</span>
              )}
            </div>
          } color="var(--t-amber)" />
          <MetricItem label="Notional" value={fmtUsd(r.notional_usd)} />
          <MetricItem
            label={pnl?.realized ? 'Realized P&L' : 'Open P&L'}
            value={pnlVal == null ? '—' : `${pnlVal >= 0 ? '+' : '−'}${fmtUsd(Math.abs(pnlVal))}`}
            color={pnlColor}
          />
          {pnl?.trailMode && pnl.trailMode !== 'off' && (
            <MetricItem label="Trail" value={pnl.trailMode ?? '—'} color="var(--t-blue)" />
          )}
          {pnl?.orderStatus && (
            <MetricItem label="Order" value={pnl.orderStatus} color={pnl.orderStatus === 'filled' ? 'var(--t-green)' : 'var(--t-amber)'} />
          )}
          <MetricItem label="Mode" value={mode} color="var(--t-blue)" />
          {profile && <MetricItem label="Profile" value={profile} color="var(--t-bright)" />}
          {pattern && <MetricItem label="Pattern" value={pattern.replace(/_/g, ' ')} color="var(--t-amber)" />}
        </div>
      )}
    </div>
  );
}

const fmtSigned = (v: number) => `${v >= 0 ? '+' : '−'}${fmtUsd(Math.abs(v))}`;

/* ── consolidated P&L across every executed trade — one summary row ─────────── */
function ConsolidatedRow({ count, totalPnl, openPnl, realizedPnl, notional, wins, losses }: {
  count: number; totalPnl: number; openPnl: number; realizedPnl: number;
  notional: number; wins: number; losses: number;
}) {
  const clr = totalPnl >= 0 ? 'var(--t-green)' : 'var(--t-red)';
  const Stat = ({ label, value, color }: { label: string; value: string; color?: string }) => (
    <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.05 }}>
      <span style={{ fontSize: 12, fontWeight: 800, color: color || 'var(--t-bright)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
      <span style={{ fontSize: 8, color: 'var(--t-dim)', fontWeight: 700, letterSpacing: '0.07em' }}>{label}</span>
    </div>
  );
  return (
    <tr style={{ borderTop: '2px solid var(--t-border)', background: alpha(clr, 0.05) }}>
      <td colSpan={TABLE_COL_COUNT} style={{ padding: '8px 12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 60, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.06em', color: clr }}>Σ</span>
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.05 }}>
            <span style={{ fontSize: 17, fontWeight: 900, color: clr, fontVariantNumeric: 'tabular-nums' }}>{fmtSigned(totalPnl)}</span>
            <span style={{ fontSize: 9, fontWeight: 600, color: 'var(--t-muted)', letterSpacing: '0.07em' }}>TOTAL P&L · {count}</span>
          </div>
          <Stat label="OPEN" value={fmtSigned(openPnl)} color={openPnl >= 0 ? 'var(--t-green)' : 'var(--t-red)'} />
          <Stat label="REALIZED" value={fmtSigned(realizedPnl)} color={realizedPnl >= 0 ? 'var(--t-green)' : 'var(--t-red)'} />
          <Stat label="WIN / LOSS" value={`${wins} / ${losses}`} color={wins >= losses ? 'var(--t-green)' : 'var(--t-red)'} />
        </div>
      </td>
    </tr>
  );
}

/** Thin labelled divider used to group the signal list into sections.
 *  Click to expand/collapse when collapsible=true. */
function ListGroupHeader({ label, count, color, collapsible, defaultOpen, onToggle }: {
  label: string; count?: number; color?: string;
  collapsible?: boolean; defaultOpen?: boolean; onToggle?: (open: boolean) => void;
}) {
  const c = color || 'var(--t-dim)';
  const [open, setOpen] = React.useState(defaultOpen !== false);
  const handleClick = () => {
    const next = !open;
    setOpen(next);
    onToggle?.(next);
  };
  return (
    <div onClick={collapsible ? handleClick : undefined} style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '14px 4px 6px', marginTop: 6,
      cursor: collapsible ? 'pointer' : 'default',
      userSelect: 'none',
    }}>
      {collapsible && <span style={{ fontSize: 9, color: 'var(--t-dim)', width: 12, flexShrink: 0 }}>{open ? '▼' : '▶'}</span>}
      <span style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.14em', color: c, textTransform: 'uppercase' }}>{label}</span>
      {count != null && (
        <span style={{
          fontSize: 9, fontWeight: 700, color: c, background: alpha(c, 0.11),
          borderRadius: 9, padding: '0 6px', lineHeight: '15px',
        }}>{count}</span>
      )}
      <div style={{ flex: 1, height: 1, background: 'var(--t-border)', opacity: 0.5 }} />
    </div>
  );
}

// Visible execution log — proves whether ready signals are firing in the current
// mode (and, when they don't, why the backend rejected them).
function ExecLog({ entries, mode }: {
  entries: { ts: number; key: string; mode: string; ok: boolean; status: string; reason: string; auto: boolean }[];
  mode: string;
}) {
  const [expandedIndices, setExpandedIndices] = useState<Set<number>>(new Set());

  if (entries.length === 0) {
    return (
      <div style={{ fontSize: 10, color: 'var(--t-dim)', lineHeight: 1.5, padding: '6px 14px' }}>
        No execution attempts yet. With <b style={{ color: 'var(--t-bright)' }}>Algo ON</b>, every ready signal
        fires here ({mode}) — confirm orders are placed, or see why one was rejected.
      </div>
    );
  }
  // Status → colour. ok = green, already-open = blue, soft "didn't fire" reasons
  // = amber, hard errors/rejections = red.
  const statusCol = (e: { ok: boolean; status: string }) =>
    e.ok ? 'var(--t-green)'
    : e.status === 'already_open' ? 'var(--t-blue)'
    : ['no_signal', 'no_plan', 'size_too_small'].includes(e.status) ? 'var(--t-amber)'
    : 'var(--t-red)';

  const toggle = (i: number) => {
    setExpandedIndices(prev => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {entries.map((e, i) => {
        const col = statusCol(e);
        const dash = e.key.indexOf('-');
        const sym = dash >= 0 ? e.key.slice(0, dash) : e.key;
        const strat = (dash >= 0 ? e.key.slice(dash + 1) : '').replace(/_/g, ' ');
        const mc = e.auto ? 'var(--t-cyan)' : modeColorOf(e.mode);
        return (
          <div key={i} style={{ 
            display: 'flex', flexDirection: 'column', 
            borderLeft: `2px solid ${col}`, background: e.ok ? alpha(col, 0.07) : 'transparent',
            borderBottom: expandedIndices.has(i) ? '1px solid var(--t-border)' : 'none',
          }}>
            <div 
              onClick={() => e.reason && toggle(i)}
              title={e.reason ? "Click to view details" : e.status}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '4px 14px 4px 12px',
                fontSize: 10, lineHeight: 1.3, whiteSpace: 'nowrap', overflow: 'hidden',
                cursor: e.reason ? 'pointer' : 'default',
                transition: 'background 0.1s',
              }}
              onMouseEnter={(ev) => e.reason && (ev.currentTarget.style.background = 'var(--t-bg3)')}
              onMouseLeave={(ev) => e.reason && (ev.currentTarget.style.background = 'transparent')}
            >
              <span style={{ color: col, fontWeight: 600, fontSize: 10, width: 9, textAlign: 'center', flexShrink: 0 }}>{e.ok ? '✓' : e.status === 'already_open' ? '•' : '✕'}</span>
              <span style={{ color: 'var(--t-bright)', fontWeight: 600, flexShrink: 0 }}>{sym}</span>
              <span style={{ color: 'var(--t-muted)', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 }}>{strat}</span>
              <span style={{ marginLeft: 'auto', color: col, fontWeight: 600, fontSize: 10, letterSpacing: '0.03em', textTransform: 'uppercase', flexShrink: 0 }}>{e.status.replace(/_/g, ' ')}</span>
              <span style={{ color: mc, fontWeight: 600, fontSize: 10, letterSpacing: '0.04em', flexShrink: 0 }}>{e.auto ? 'A·' : ''}{e.mode}</span>
              <span style={{ color: 'var(--t-muted)', fontVariantNumeric: 'tabular-nums', fontSize: 10, flexShrink: 0 }}>{new Date(e.ts).toLocaleTimeString('en-US', { hour12: false })}</span>
            </div>
            {expandedIndices.has(i) && e.reason && (
              <div style={{
                padding: '4px 14px 8px 32px', fontSize: 9, color: 'var(--t-dim)', 
                whiteSpace: 'normal', wordBreak: 'break-word', lineHeight: 1.5,
              }}>
                <span style={{ color: 'var(--t-amber)', fontWeight: 700 }}>REASON:</span> {e.reason}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ScalpSignalCard({ s, selected, expanded, onSelect, onExecute, executing, execState, pnl, algoOn, mode, macroMode, showPlan, showAction, showDirection, showPattern, livePx }: {
  s: ScalpingSignal; selected: boolean; expanded?: boolean; onSelect: () => void; onExecute: () => void;
  executing: boolean; execState?: ExecState; pnl?: SignalPnl; algoOn?: boolean; mode?: string; macroMode?: string;
  showPlan?: boolean; showAction?: boolean; showDirection?: boolean; showPattern?: boolean;
  livePx?: number | null;
}) {
  const long = s.direction === 'long';
  const short = s.direction === 'short';
  const isWatch = s.entry_ok && !s.executable;
  const meta = STRATEGY_META[s.strategy] || { label: s.strategy.toUpperCase(), color: 'var(--t-dim)' };
  // Color/label strictly by direction — never assume SHORT for a non-long row
  // (a directionless "near level" row must not render as SHORT).
  const dirColor = long ? 'var(--t-green)' : short ? 'var(--t-red)' : 'var(--t-dim)';
  // No directional bias yet (a "near level / watching" row) → em-dash, not a
  // fake direction. The level/awaiting context lives in Status + Level columns.
  const dirLabel = long ? '▲ LONG' : short ? '▼ SHORT' : '—';

  const resp = execState?.resp;
  const accepted = !!resp?.accepted;
  const tried = !!execState && !accepted;  // attempted but rejected or errored

  // Configured mode this trade ran in (PAPER / SHADOW / LIVE) — recorded at exec
  // time, else the currently-configured mode for the pending pill. Color-coded by risk.
  const pillMode = execState?.mode || mode || 'PAPER';
  const modeColor = modeColorOf(pillMode);
  // An algo-opened position that's still open while Algo is OFF: it keeps running
  // to SL/TP but won't re-enter — flag it so the provenance reads "paused".
  const pausedAuto = !!execState?.auto && algoOn === false && pnl != null && pnl.realized === false;

  let statusLabel = 'PENDING';
  let statusColor = 'var(--t-dim)';
  if (accepted) {
    if (pnl?.realized) {
      statusLabel = 'CLOSED';
      statusColor = 'var(--t-dim)';
    } else {
      statusLabel = 'OPEN';
      statusColor = 'var(--t-blue)';
    }
  } else if (s.executable) {
    statusLabel = 'READY';
    statusColor = dirColor;
  } else if (isWatch) {
    statusLabel = 'WATCH';
    statusColor = 'var(--t-blue)';
  }

  // Stable ID derived from underlying, strategy, and timestamp for easier tracking
  const sigIdStr = `${s.underlying}-${s.strategy}-${s.timestamp_ms}`;
  const sigIdHash = Array.from(sigIdStr).reduce((h, c) => Math.imul(31, h) + c.charCodeAt(0) | 0, 0);
  const sigId = Math.abs(sigIdHash).toString(16).substring(0, 5).toUpperCase();

  // Signal's own setup reason
  const metaReason = s.reason;

  const pnlVal = pnl?.value ?? null;
  const pnlColor = pnlVal == null ? 'var(--t-dim)' : pnlVal >= 0 ? 'var(--t-green)' : 'var(--t-red)';

  // Live current price next to Entry — live mark for executed trades, else the
  // latest scan close. Colored by whether price has moved the position's way.
  const currentPx = livePx ?? pnl?.currentSpot ?? (s.close || null);

  const displayEntry = accepted ? (pnl?.entryPriceReal ?? resp?.entry_price ?? s.entry) : s.entry;
  // Initial (entry-time) vs trailed (live) stop & target. The row shows the live
  // value, the original struck through, and the points moved once the trailing
  // stop / dynamic TP has shifted them. Scan (non-executed) rows have only the
  // initial level, so no trail is shown.
  const initialSl = accepted ? (pnl?.initialSl ?? resp?.stop_loss ?? s.stop_loss) : s.stop_loss;
  const trailSl = accepted ? (pnl?.currentSl ?? null) : null;
  const initialTp = accepted ? (pnl?.initialTp ?? resp?.take_profit ?? s.take_profit) : s.take_profit;
  const trailTp = accepted ? (pnl?.currentTp ?? null) : null;
  const hasPlan = displayEntry != null;

  let currentColor = 'var(--t-bright)';
  let currentValNode: React.ReactNode = '—';
  
  if (currentPx != null) {
    if (displayEntry != null) {
      const diff = long ? (currentPx - displayEntry) : (displayEntry - currentPx);
      const roundedDiff = parseFloat(diff.toFixed(1));
      
      if (Math.abs(roundedDiff) === 0) {
        currentColor = 'var(--t-bright)';
      } else {
        currentColor = roundedDiff > 0 ? 'var(--t-green)' : 'var(--t-red)';
      }
      
      const sign = roundedDiff > 0 ? '+' : roundedDiff < 0 ? '−' : '';
      currentValNode = (
        <span>
          {fmtUsd(currentPx)} <span style={{ fontSize: 11, opacity: 0.7, fontWeight: 400 }}>({sign}{Math.abs(roundedDiff).toFixed(1)})</span>
        </span>
      );
    } else {
      currentValNode = fmtUsd(currentPx);
    }
  }

  // Two highlight levels: a strong colored tint while the row is open (expanded),
  // and a darker/recessed tone for the last-interacted row once collapsed.
  // A translucent black darkens in BOTH themes (a theme bg var would flip lighter
  // in the light theme), keeping the collapsed row visibly recessed vs the cards.
  const isOpen = !!expanded;
  const isClosed = accepted && pnl?.realized;
  const isLive = accepted && !pnl?.realized;
  const bg = isClosed ? alpha('var(--t-amber)', 0.05) : isLive ? alpha('var(--t-green)', 0.05) : isOpen ? alpha(statusColor, 0.09) : selected ? 'var(--t-bg)' : 'var(--t-bg2)';
  const borderColor = isClosed ? alpha('var(--t-amber)', 0.15) : isLive ? alpha('var(--t-green)', 0.15) : isOpen ? alpha(statusColor, 0.40) : selected ? alpha(statusColor, 0.18) : 'var(--t-border)';

  const positionOverlayData = displayEntry != null ? {
    entry: displayEntry,
    stop: trailSl ?? initialSl,
    target: initialTp ?? 0,
  } : undefined;

  // Cell styles mirror the derivatives candidate tables' <td>.
  const td: React.CSSProperties = { padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' };
  const tdNum: React.CSSProperties = { ...td, fontVariantNumeric: 'tabular-nums' };

  const tpBadges = (
    <>
      {s.tp_source && s.tp_source.includes('fallback') && (
        <span title="Target determined by fallback Risk-Reward" style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: '0.04em' }}>[RR]</span>
      )}
      {s.tp_source && s.tp_source.includes('swing') && (
        <span title="Target determined by dynamic swing padding" style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: '0.04em' }}>[SW]</span>
      )}
      {s.tp_source === 'structural_level' && (
        <span title="Target determined by structural level" style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: '0.04em' }}>[LVL]</span>
      )}
    </>
  );

  const hintNode = execState && !accepted ? (
    <div style={{ padding: '4px 8px 8px 8px', fontSize: 11, lineHeight: 1.5, color: 'var(--t-amber)', fontWeight: 600, wordBreak: 'break-word' }}>
      ✕ {pillMode} — {failureReason(execState)}
    </div>
  ) : !execState && algoOn && s.executable ? (
    <div style={{ padding: '4px 8px 8px 8px', fontSize: 11, lineHeight: 1.5, color: 'var(--t-green)', wordBreak: 'break-word' }}>
      ⚡ Auto-executing in {pillMode}…
    </div>
  ) : null;

  const expandedContent = expanded && ((accepted && execState) || !accepted);
  const hasDetail = !!hintNode || !!expandedContent;

  return (
    <>
      <tr onClick={onSelect} style={{
        cursor: 'pointer', background: bg, color: 'var(--t-text)',
        // Flush table row matching the derivatives candidate tables: a single
        // bottom divider; open/closed/live/selected state reads from the bg tint.
        borderBottom: hasDetail ? 'none' : '1px solid var(--t-br2, var(--border-light))',
        transition: 'background .12s',
      }}>
        {/* symbol — direction arrow + underlying, like the futures table */}
        <td style={{ ...td, fontWeight: 700, color: 'var(--t-bright)' }}>
          <span style={{ color: long ? 'var(--t-green)' : short ? 'var(--t-red)' : 'var(--t-dim)' }}>
            {long ? '▲' : short ? '▼' : '–'}
          </span>{' '}{s.underlying}
        </td>
        {/* id — stable hex hash for tracking */}
        <td style={{ ...tdNum, fontSize: 9, color: 'var(--t-dim)', fontFamily: 'monospace' }}>{sigId}</td>
        {/* time */}
        <td style={{ ...tdNum, color: 'var(--t-text)' }}>{fmtTime(s.timestamp_ms)}</td>
        {/* status */}
        <td style={td}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: statusColor }}>{statusLabel}</span>
        </td>
        {/* direction */}
        <td style={td}>
          <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', color: (long || short) ? dirColor : 'var(--t-dim)' }}>{dirLabel}</span>
        </td>
        {/* entry */}
        <td style={tdNum}>{hasPlan ? fmtUsd(displayEntry) : '—'}</td>
        {/* current */}
        <td style={{ ...tdNum, color: hasPlan ? currentColor : 'var(--t-dim)' }}>{hasPlan ? currentValNode : '—'}</td>
        {/* stop */}
        <td style={tdNum}>
          {hasPlan ? <PlanLevelCell initial={initialSl} current={trailSl} color="var(--t-red)" favorableUp={long} width="auto" /> : '—'}
        </td>
        {/* target */}
        <td style={tdNum}>
          {hasPlan ? <PlanLevelCell initial={initialTp} current={trailTp} color="var(--t-amber)" favorableUp={long} width="auto" badges={tpBadges} /> : '—'}
        </td>
        {/* risk */}
        <td style={tdNum}>{hasPlan && s.risk_pct != null ? `${fmt(s.risk_pct)}%` : '—'}</td>
        {/* strategy */}
        <td style={{ ...td, fontSize: 10, fontWeight: 600, color: c.muted, whiteSpace: 'nowrap' }}>{meta.label}</td>
        {/* pnl */}
        <td style={{ ...tdNum, textAlign: 'right' }}>
          {accepted && !isOpen && (
            <span style={{ fontSize: 11, fontWeight: 700, color: pnlColor, fontVariantNumeric: 'tabular-nums' }}>
              {pnlVal == null ? '—' : `${pnlVal >= 0 ? '+' : '−'}${fmtUsd(Math.abs(pnlVal))}`}
            </span>
          )}
        </td>
        {/* type — realized/unrealized label */}
        <td style={{ ...td, fontSize: 9, fontWeight: 600, color: 'var(--t-dim)', textAlign: 'right' }}>
          {accepted && !isOpen && (
            <span>{pnl?.realized ? 'REALIZED' : 'OPEN P&L'}</span>
          )}
        </td>
        {/* action */}
        <td style={{ ...td, textAlign: 'right' }}>
          {accepted ? (
            <span title={pausedAuto ? 'Opened by Algo, which is now OFF — runs to SL/TP, no re-entry' : undefined} style={{
              fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: pausedAuto ? 'var(--t-amber)' : modeColor,
              padding: '4px 9px', borderRadius: 'var(--radius-md)', background: pausedAuto ? tint('var(--t-amber)', 12) : alpha(modeColor, 0.09),
              border: `1px solid ${pausedAuto ? 'var(--t-amber)44' : alpha(modeColor, 0.27)}`, whiteSpace: 'nowrap',
              textAlign: 'center', minWidth: 80,
            }}>✓ {execState?.auto ? 'AUTO·' : ''}{pillMode}{pausedAuto ? ' ⏸' : ''}</span>
          ) : s.executable && algoOn ? (
            <span title={`Algo is ON — auto-executes in ${pillMode} mode`} style={{
              fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: modeColor,
              padding: '5px 12px', borderRadius: 'var(--radius-md)', background: alpha(modeColor, 0.08),
              border: `1px solid ${alpha(modeColor, 0.27)}`, whiteSpace: 'nowrap',
              opacity: tried ? 0.7 : 1, minWidth: 80, textAlign: 'center',
            }}>⚡ {executing ? 'AUTO…' : `AUTO·${pillMode}`}</span>
          ) : s.executable ? (
            <button disabled={executing} onClick={(e) => { e.stopPropagation(); onExecute(); }} style={{
              fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', padding: '6px 16px', borderRadius: 6,
              fontFamily: 'inherit', cursor: executing ? 'default' : 'pointer',
              color: '#fff', background: tried ? 'var(--t-amber)' : dirColor, border: 'none', lineHeight: 1,
              opacity: executing ? 0.6 : 1, minWidth: 80, textAlign: 'center',
            }}>
              {executing ? '…' : tried ? 'RETRY' : 'EXECUTE'}
            </button>
          ) : null}
          {accepted && (
            <span style={{ fontSize: 11, color: 'var(--t-dim)', width: 10, textAlign: 'center', display: 'inline-block', marginLeft: 6 }}>{expanded ? '▴' : '▾'}</span>
          )}
        </td>
      </tr>

      {hasDetail && (
        <tr style={{ background: bg, borderBottom: '1px solid var(--t-br2, var(--border-light))' }}>
          <td colSpan={TABLE_COL_COUNT} style={{ padding: 0 }}>
            {hintNode}
            {accepted && expanded && execState && <ExecDetail execState={execState} pnl={pnl} profile={macroMode} pattern={s.pattern} />}
            {!accepted && expanded && (
              <div style={{ padding: '12px 14px', fontSize: 11, color: 'var(--t-text)', lineHeight: 1.5, background: 'rgba(0,0,0,0.1)', borderTop: '1px solid var(--t-border)', whiteSpace: 'normal', wordBreak: 'break-word' }}>
                <div style={{ color: 'var(--t-dim)', fontWeight: 600, marginBottom: metaReason ? 4 : 0, display: 'flex', gap: 12 }}>
                  <span>SIGNAL TIME: <span style={{ color: 'var(--t-muted)' }}>{fmtTime(s.timestamp_ms)}</span></span>
                </div>
                <div style={{ display: 'flex', gap: 16, marginBottom: metaReason ? 4 : 0 }}>
                  {macroMode && <span style={{ color: 'var(--t-dim)', fontWeight: 600 }}>PROFILE: <span style={{ color: 'var(--t-bright)', fontWeight: 400 }}>{macroMode}</span></span>}
                  {s.pattern && <span style={{ color: 'var(--t-dim)', fontWeight: 600 }}>PATTERN: <span style={{ color: meta.color, fontWeight: 400 }}>{s.pattern.replace(/_/g, ' ')}</span></span>}
                </div>
                {metaReason && <div><span style={{ color: 'var(--t-dim)', fontWeight: 600 }}>DETAILS:</span> {formatReason(metaReason)}</div>}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

/* ── backtest panel ─────────────────────────────────────────────────────────── */

const LOOKBACK_PRESETS_BT: [string, number][] = [['1M', 30], ['3M', 90], ['6M', 180]];

function ScalpBacktestPanel({ initialUnderlying }: { initialUnderlying: string }) {
  const [lookback, setLookback] = useState(90);
  const [localUnderlying, setLocalUnderlying] = useState(initialUnderlying);
  const universeQ = useScalpingUniverse();
  const universe = universeQ.data?.symbols ?? [];
  const bt = useScalpingBacktest();
  const res = bt.data;

  const hdrBtn = (active: boolean): React.CSSProperties => ({
    padding: '3px 8px', borderRadius: 5, fontSize: 9, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
    border: `1px solid ${active ? 'var(--t-blue)' : 'var(--t-border)'}`,
    background: active ? 'var(--t-bg3)' : 'transparent',
    color: active ? 'var(--t-blue)' : 'var(--t-dim)',
  });

  return (
    <SectionCard title="BACKTEST" right={
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {LOOKBACK_PRESETS_BT.map(([lbl, d]) => (
          <button key={d} onClick={() => setLookback(d)} style={hdrBtn(lookback === d)}>{lbl}</button>
        ))}
        <select 
          value={localUnderlying} 
          onChange={e => setLocalUnderlying(e.target.value)}
          style={{
            background: 'var(--t-bg2)', border: '1px solid var(--t-border)', color: 'var(--t-bright)',
            padding: '2px 6px', borderRadius: 4, fontSize: 10, outline: 'none'
          }}
        >
          {universe.includes(localUnderlying) ? null : <option value={localUnderlying}>{localUnderlying}</option>}
          {universe.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button disabled={bt.isPending} onClick={() => bt.mutate({ underlying: localUnderlying, lookback_days: lookback })} style={{
          fontSize: 9, fontWeight: 700, padding: '3px 10px', borderRadius: 5, fontFamily: 'inherit', cursor: 'pointer',
          border: '1px solid var(--t-blue)', background: 'var(--t-bg3)', color: 'var(--t-blue)',
        }}>{bt.isPending ? 'RUNNING…' : 'RUN'}</button>
      </span>
    }>
      {bt.isError && <div style={{ color: 'var(--t-red)', fontSize: 10 }}>{bt.error.message}</div>}
      {!res && !bt.isPending && <div style={dim}>Run a backtest — 4H structure + 15min entry replay.</div>}
      {res && (() => {
        const sq = res.sample_quality;
        const cov = res.regime_coverage;
        const oos = res.oos;
        const sqColor = sq?.label === 'robust' || sq?.label === 'adequate' ? 'var(--t-green)'
          : sq?.label === 'thin' ? 'var(--t-amber)'
          : sq?.label === 'no_trades' ? 'var(--t-dim)' : 'var(--t-red)';
        const pf = res.profit_factor;
        const oosColor = oos?.generalises ? 'var(--t-green)' : 'var(--t-amber)';
        return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Sample-size adequacy — a backtest under ~100 trades is unreliable. */}
          {sq && (
            <div style={{
              fontSize: 10, lineHeight: 1.45, padding: '5px 9px', borderRadius: 'var(--radius-md)',
              color: sqColor, background: alpha(sqColor, 0.08), border: `1px solid ${alpha(sqColor, 0.27)}`,
            }}>
              <b style={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>{sq.label}</b> sample
              {' · '}{res.total_trades} trades — {sq.note}
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
            <Stat label="TRADES" value={String(res.total_trades)} />
            <Stat label="WIN RATE" value={`${fmt(res.win_rate * 100, 0)}%`} color={res.win_rate >= 0.5 ? 'var(--t-green)' : 'var(--t-red)'} />
            <Stat label="RETURN (net)" value={`${fmt(res.total_return_pct, 1)}%`} color={res.total_return_pct >= 0 ? 'var(--t-green)' : 'var(--t-red)'} />
            <Stat label="MAX DD" value={`${fmt(res.max_drawdown_pct, 1)}%`} color="var(--t-amber)" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
            <Stat label="EXPECTANCY" value={`${(res.expectancy_r ?? 0) >= 0 ? '+' : ''}${fmt(res.expectancy_r ?? 0, 2)}R`} color={(res.expectancy_r ?? 0) >= 0 ? 'var(--t-green)' : 'var(--t-red)'} />
            <Stat label="PROFIT FACTOR" value={pf == null ? '—' : fmt(pf, 2)} color={pf != null && pf >= 1 ? 'var(--t-green)' : 'var(--t-red)'} />
            <Stat label="AVG COST" value={`${fmt(res.avg_cost_r ?? 0, 2)}R`} color="var(--t-dim)" />
          </div>

          {/* Regime coverage — does the window span both a bull and a bear leg? */}
          {cov && (
            <div style={{ fontSize: 9.5, color: 'var(--t-dim)', lineHeight: 1.5 }}>
              <span style={{ color: cov.covers_bull_and_bear ? 'var(--t-green)' : 'var(--t-amber)' }}>
                {cov.covers_bull_and_bear ? '✓ spans bull + bear' : '⚠ single-regime window'}
              </span>
              {' · '}bull {fmt(cov.bull_pct, 0)}% · bear {fmt(cov.bear_pct, 0)}% · chop {fmt(cov.chop_pct, 0)}%
              {Object.keys(cov.by_regime || {}).length > 0 && (
                <span>{'  ·  '}{Object.entries(cov.by_regime).map(([r, s]) =>
                  `${r}: ${s.trade_count}t ${fmt(s.win_rate * 100, 0)}%w ${s.avg_r >= 0 ? '+' : ''}${fmt(s.avg_r, 2)}R`
                ).join(' / ')}</span>
              )}
            </div>
          )}

          {/* In-sample vs out-of-sample — does the edge generalise or curve-fit? */}
          {oos && (
            <div style={{
              fontSize: 10, lineHeight: 1.45, padding: '5px 9px', borderRadius: 'var(--radius-md)',
              color: oosColor, background: alpha(oosColor, 0.08), border: `1px solid ${alpha(oosColor, 0.27)}`,
            }}>
              {oos.generalises ? '✓ GENERALISES' : '⚠ DOES NOT GENERALISE'}
              {' · '}IS PF {oos.is_pf == null ? '—' : fmt(oos.is_pf, 2)} (n{oos.n_is})
              {' → '}OOS PF {oos.oos_pf == null ? '—' : fmt(oos.oos_pf, 2)} (n{oos.n_oos})
              <div style={{ color: 'var(--t-dim)', marginTop: 2 }}>{oos.note}</div>
            </div>
          )}

          {res.trades.length > 0 && (
            <div style={{ maxHeight: 140, overflow: 'auto', border: '1px solid var(--t-border)', borderRadius: 6 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10 }}>
                <thead>
                  <tr style={{ color: 'var(--t-dim)', textAlign: 'left' }}>
                    {['Strat', 'Dir', 'Regime', 'Entry', 'Exit', 'Net R', 'Exit'].map((h) => (
                      <th key={h} style={{ padding: '3px 6px', position: 'sticky', top: 0, background: 'var(--t-bg2)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {res.trades.slice(-30).reverse().map((t, i) => (
                    <tr key={i} style={{ borderTop: '1px solid var(--t-border)' }}>
                      <td style={{ padding: '2px 6px', fontSize: 10, fontWeight: 700, color: STRATEGY_META[t.strategy]?.color || 'var(--t-dim)', whiteSpace: 'nowrap' }}>{t.strategy.replace('_', ' ').toUpperCase()}</td>
                      <td style={{ padding: '2px 6px', color: t.direction === 'long' ? 'var(--t-green)' : 'var(--t-red)' }}>{t.direction === 'long' ? 'L' : 'S'}</td>
                      <td style={{ padding: '2px 6px', color: 'var(--t-dim)' }}>{t.regime || '—'}</td>
                      <td style={{ padding: '2px 6px', color: 'var(--t-dim)' }}>{fmtUsd(t.entry_price)}</td>
                      <td style={{ padding: '2px 6px', color: 'var(--t-dim)' }}>{fmtUsd(t.exit_price)}</td>
                      <td style={{ padding: '2px 6px', fontWeight: 700, color: t.pnl_r >= 0 ? 'var(--t-green)' : 'var(--t-red)' }}>{t.pnl_r >= 0 ? '+' : ''}{fmt(t.pnl_r, 2)}</td>
                      <td style={{ padding: '2px 6px', color: 'var(--t-dim)' }}>{t.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        );
      })()}
    </SectionCard>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: 9, letterSpacing: '0.06em', color: 'var(--t-muted)', fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 700, color: color || 'var(--t-bright)' }}>{value}</div>
    </div>
  );
}

/* ── main tab: 3-column layout ─────────────────────────────────────────────── */



const getSignalStatus = (s: ScalpingSignal) => {
  if (s.direction === 'long' || s.direction === 'short') {
    return s.entry_ok ? 'ready' : 'pending';
  }
  if (s.near_level != null) return 'watching';
  return 'other';
};

/* Live, console-styled activity feed for the right rail — replaces the static
 * execution log. Sourced entirely from data already streaming to the UI (no
 * backend change): SSE connect/disconnect, the directional scan, and the
 * scalping scan (passed in via `scanInfo`). Keeps the last 200 lines, autoscrolls. */
type ExecEvent = { ts: number; key: string; mode: string; ok: boolean; status: string; reason: string; auto: boolean };
function TerminalLog({ scanInfo, lastExec }: {
  scanInfo?: { count?: number; armed?: number; ts?: number };
  lastExec?: ExecEvent;
}) {
  type Line = { id: number; t: number; emoji: string; msg: string; color: string; count: number };
  const [lines, setLines] = useState<Line[]>([]);
  const idRef = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);
  const push = useCallback((emoji: string, msg: string, color: string) => {
    setLines((l) => {
      const last = l[l.length - 1];
      if (last && last.emoji === emoji && last.msg === msg) {
        return [...l.slice(0, -1), { ...last, t: Date.now(), count: last.count + 1 }];
      }
      return [...l.slice(-199), { id: idRef.current++, t: Date.now(), emoji, msg, color, count: 1 }];
    });
  }, []);

  useEffect(() => { push('🚀', 'Live activity feed started', 'var(--t-blue)'); }, [push]);

  const status = useStreamStatus();
  useEffect(() => {
    if (status === 'connected') push('🟢', 'Connected — live data is flowing', 'var(--t-green)');
    else if (status === 'connecting') push('🟡', 'Connecting to the live feed…', 'var(--t-amber)');
    else push('🔴', 'Disconnected — retrying…', 'var(--t-red)');
  }, [status, push]);

  const sig = useAppStream<{ signals?: { entry_ok?: boolean }[]; timestamp_ms?: number }>('signals');
  const sigTs = sig.data?.timestamp_ms;
  useEffect(() => {
    if (sigTs == null) return;
    const arr = sig.data?.signals ?? [];
    const armed = arr.filter((x) => x.entry_ok).length;
    push('📡', `Market scan · ${arr.length} signals · ${armed} armed`, 'var(--t-dim)');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sigTs]);

  const scalpTs = scanInfo?.ts;
  useEffect(() => {
    if (scalpTs == null) return;
    const armed = scanInfo?.armed ?? 0;
    const count = scanInfo?.count ?? 0;
    if (armed > 0) push('🎯', `${armed} setup${armed === 1 ? '' : 's'} ready to trade · ${count} scanned`, 'var(--t-green)');
    else push('🔍', `Scanned ${count} signal${count === 1 ? '' : 's'} · none ready yet`, 'var(--t-text)');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scalpTs]);

  // Execution events — fired when a (manual or algo) trade is attempted. Seeded
  // to the newest existing entry so prior history isn't replayed on mount.
  const lastExecTs = lastExec?.ts;
  const seenExecRef = useRef<number | undefined>(lastExec?.ts);
  useEffect(() => {
    if (lastExecTs == null || seenExecRef.current === lastExecTs || !lastExec) return;
    seenExecRef.current = lastExecTs;
    const dash = lastExec.key.indexOf('-');
    const sym = dash >= 0 ? lastExec.key.slice(0, dash) : lastExec.key;
    const strat = (dash >= 0 ? lastExec.key.slice(dash + 1) : '').replace(/_/g, ' ');
    const who = lastExec.auto ? 'Algo' : 'Manual';
    if (lastExec.ok) {
      const m = lastExec.mode.toUpperCase();
      if (m === 'PAPER') push('🟣', `${who} paper trade placed: ${sym} ${strat}`, 'var(--t-purple)');
      else if (m === 'LIVE') push('✅', `${who} LIVE order placed: ${sym} ${strat}`, 'var(--t-green)');
      else push('👁️', `${who} ${m.toLowerCase()} trade logged: ${sym} ${strat}`, 'var(--t-blue)');
    } else if (lastExec.status === 'already_open') {
      push('🔁', `${sym} ${strat} already open — skipped`, 'var(--t-blue)');
    } else {
      push('⚠️', `${sym} ${strat} not placed: ${lastExec.reason || lastExec.status.replace(/_/g, ' ')}`, 'var(--t-amber)');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastExecTs]);

  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }); }, [lines]);

  const head = status === 'connected'
    ? { e: '🟢', t: 'Online', c: 'var(--t-green)' }
    : status === 'connecting'
    ? { e: '🟡', t: 'Connecting', c: 'var(--t-amber)' }
    : { e: '🔴', t: 'Offline', c: 'var(--t-red)' };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <div style={{
        padding: '10px 14px', borderBottom: '1px solid var(--t-border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', color: 'var(--t-bright)', textTransform: 'uppercase' }}>
          🖥️ Live Terminal
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10, fontWeight: 600, color: head.c }}>
          {head.e} {head.t}
        </span>
      </div>
      <div style={{
        flex: 1, overflowY: 'auto', padding: '8px 12px',
        fontFamily: 'inherit', fontSize: 11, lineHeight: 1.7,
      }}>
        {lines.length === 0 ? (
          <div style={{ color: 'var(--t-dim)' }}>⏳ Waiting for activity…</div>
        ) : lines.map((ln) => (
          <div key={ln.id} style={{ display: 'flex', gap: 7, alignItems: 'baseline' }}>
            <span style={{ color: 'var(--t-muted)', fontVariantNumeric: 'tabular-nums', flexShrink: 0, fontSize: 10 }}>
              {new Date(ln.t).toLocaleTimeString('en-US', { hour12: false })}
            </span>
            <span style={{ flexShrink: 0 }}>{ln.emoji}</span>
            <span style={{ color: ln.color, fontWeight: 600, minWidth: 0, wordBreak: 'break-word' }}>
              {ln.msg}{ln.count > 1 && <span style={{ color: 'var(--t-dim)', fontWeight: 400, marginLeft: 6 }}>({ln.count})</span>}
            </span>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}

function SettingsTrigger({ onClick }: { onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, width: '100%',
        padding: '10px 12px', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontFamily: 'inherit',
        border: '1px solid var(--t-border)',
        background: hover ? alpha('var(--t-border)', 0.3) : 'transparent',
        color: hover ? 'var(--t-bright)' : 'var(--t-dim)', transition: 'all .1s',
      }}
    >
      <span style={{ fontSize: 12 }}>⚙</span>
      <span style={{ fontSize: 11, fontWeight: 600 }}>Global Strategy Config</span>
    </button>
  );
}

function DerivativesTrigger({ onClick }: { onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, width: '100%',
        padding: '10px 12px', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontFamily: 'inherit',
        border: '1px solid var(--t-border)',
        background: hover ? alpha('var(--t-border)', 0.3) : 'transparent',
        color: hover ? 'var(--t-bright)' : 'var(--t-dim)', transition: 'all .1s',
      }}
    >
    <span style={{ fontSize: 12 }}>⚡</span>
      <span style={{ fontSize: 11, fontWeight: 600 }}>Global Derivatives Config</span>
    </button>
  );
}

function StrategyCatalogTrigger({ onClick }: { onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, width: '100%',
        padding: '10px 12px', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontFamily: 'inherit',
        border: '1px solid var(--t-border)',
        background: hover ? alpha('var(--t-border)', 0.3) : 'transparent',
        color: hover ? 'var(--t-bright)' : 'var(--t-dim)', transition: 'all .1s',
      }}
    >
      <span style={{ fontSize: 13 }}>📚</span>
      <span style={{ fontSize: 12, fontWeight: 700 }}>WHAT'S RUNNING</span>
    </button>
  );
}

function EdgeGateTrigger({ onClick }: { onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, width: '100%',
        padding: '10px 12px', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontFamily: 'inherit',
        border: '1px solid var(--t-border)',
        background: hover ? alpha('var(--t-border)', 0.3) : 'transparent',
        color: hover ? 'var(--t-bright)' : 'var(--t-dim)', transition: 'all .1s',
      }}
    >
      <span style={{ fontSize: 12 }}>🛡️</span>
      <span style={{ fontSize: 11, fontWeight: 600 }}>Edge Gate Admission</span>
    </button>
  );
}
export function ScalpingTab() {
  const selected = useSelectedUnderlying();
  const setSelected = useSetSelectedUnderlying();
  const cfgQ = useScalpingConfig();
  const cfg = cfgQ.data?.config;
  const derivConfig = useDerivativesConfig();
  const derivPatchGlobal = usePatchDerivativesGlobal();
  const derivResetAll = useResetDerivativesConfig();

  const globalDerivEnabled = useMemo(() => {
    if (!derivConfig.data?.profiles) return false;
    return Object.values(derivConfig.data.profiles).every(p => p.enabled);
  }, [derivConfig.data]);
  const globalDerivFutAuto = useMemo(() => {
    if (!derivConfig.data?.profiles) return false;
    return Object.values(derivConfig.data.profiles).every(p => p.auto_execute_futures);
  }, [derivConfig.data]);
  const globalDerivOptAuto = useMemo(() => {
    if (!derivConfig.data?.profiles) return false;
    return Object.values(derivConfig.data.profiles).every(p => p.auto_execute_options);
  }, [derivConfig.data]);
  const anyWfoActive = cfg ? cfg.use_optimized : false;
  const setCfg = useSetScalpingConfig();
  const [drawer, setDrawer] = useState(false);
  const [derivDrawer, setDerivDrawer] = useState(false);
  
  const [globalDraft, setGlobalDraft] = useState<{enabled: boolean, fut: boolean, opt: boolean} | null>(null);
  useEffect(() => {
    if (derivDrawer) {
      setGlobalDraft({ enabled: globalDerivEnabled, fut: globalDerivFutAuto, opt: globalDerivOptAuto });
    }
  }, [derivDrawer, globalDerivEnabled, globalDerivFutAuto, globalDerivOptAuto]);

  const globalDirty = globalDraft && (
    globalDraft.enabled !== globalDerivEnabled ||
    globalDraft.fut !== globalDerivFutAuto ||
    globalDraft.opt !== globalDerivOptAuto
  );
  const [catalogDrawer, setCatalogDrawer] = useState(false);
  const [edgeGateDrawer, setEdgeGateDrawer] = useState(false);
  const [derivStrategy, setDerivStrategy] = useState<string>('scalping/price_action');
  const [stratFilter, setStratFilter] = useState<string>(() => localStorage.getItem('scalp.stratFilter') || 'all');
  const [profileFilter, setProfileFilter] = useState<string>(() => localStorage.getItem('scalp.profileFilter') || 'all');
  const [statusFilter, setStatusFilter] = useState<string>(() => localStorage.getItem('scalp.statusFilter') || 'all');
  const scanQ = useScalpingSignals(false);
  const exec = useScalpingExecute();
  const [execKeys, setExecKeys] = useState<Set<string>>(new Set());  // in-flight (supports concurrent auto-exec)
  // Executions persist across reloads and across mode switches; each entry carries
  // the mode it actually ran in (es.mode), so the view can stay segregated per mode.
  const [execStates, setExecStates] = useState<Record<string, ExecState>>(() => {
    try { return JSON.parse(localStorage.getItem('scalp.execStates') || '{}'); } catch { return {}; }
  });
  const [expandedKey, setExpandedKey] = useState<string | null>(null);  // which executed row shows full metrics
  const [selectedRowKey, setSelectedRowKey] = useState<string | null>(null); // which row is highlighted
  const [spotExpanded, setSpotExpanded] = useState<boolean>(true);
  const [liveConfirm, setLiveConfirm] = useState(false);                 // gate the paper/shadow→live switch behind a modal
  // Visible execution log — every execute attempt (accepted OR rejected/errored)
  // with the mode it ran in and the backend reason. Makes "is live actually
  // firing?" answerable at a glance instead of guessing.
  type ExecLogEntry = { ts: number; key: string; mode: string; ok: boolean; status: string; reason: string; auto: boolean };
  const [execLog, setExecLog] = useState<ExecLogEntry[]>(() => {
    try { return JSON.parse(localStorage.getItem('scalp.execLog') || '[]'); } catch { return []; }
  });
  const logExec = (e: ExecLogEntry) => setExecLog((l) => [e, ...l].slice(0, 40));
  const algoOn = useAlgoMode().data?.enabled ?? false;
  const autoExecRef = useRef<Set<string>>(new Set());   // auto-attempted this algo session
  const acceptedRef = useRef<Set<string>>(new Set());   // ever accepted — never re-execute

  // Authoritative trading mode (paper / shadow / live). Drives the AUTO · <MODE>
  // labels and the order routing on the backend. Selectable inline in the header.
  const { mode: routerMode, setMode: setRouterMode } = useRouterMode();
  const tradeMode = routerMode.toUpperCase();
  // Active macro trading mode (scalping / intraday / swing / positional) — shown
  // in [brackets] next to each strategy tag. Executed rows use the mode the trade
  // was recorded under; live scan rows use the current active mode.
  const macroMode = (useTradingMode().data?.name ?? '').toUpperCase();
  // The exchange account's is_paper flag is the OTHER half of "live" — real orders
  // need router=live AND is_paper=false. The mode picker manages both so the two
  // controls can't disagree (which caused "in live but exchange is paper").
  const exQ = useExchanges();
  const updateExchange = useUpdateExchange();
  const delta = exQ.data?.exchanges.find((e) => e.name === 'delta_india' && e.is_active);
  const hasLiveCreds = !!delta?.has_credentials;

  const onModeSelect = (m: RouterMode) => {
    if (m === 'live') { setLiveConfirm(true); return; }   // gated behind confirm modal
    setRouterMode(m);
    // Leaving live → return the exchange to paper so the two controls stay in sync.
    if (delta && !delta.is_paper) updateExchange.mutate({ id: delta.id, is_paper: true });
  };

  const confirmGoLive = async () => {
    setLiveConfirm(false);
    // Flip the exchange to live alongside the router so real orders are actually placed.
    if (delta && hasLiveCreds && delta.is_paper) {
      await updateExchange.mutateAsync({ id: delta.id, is_paper: false });
    }
    await setRouterMode('live');
  };

  // Positions + live P&L feed the executed-trade rows (paper and live alike).
  const positions = usePositions().data?.positions ?? [];
  const livePnl = useLivePnl().data?.positions ?? [];
  const streamPrices = useStreamPrices();
  const pnlByPos = useMemo(() => new Map(livePnl.map((p) => [p.position_id, p])), [livePnl]);
  const setAlgo = useSetAlgoMode();
  const closePos = useClosePosition();

  const pnlFor = (r: ScalpingExecuteResponse): SignalPnl => {
    let pos = r.paper_position_id ? positions.find((p) => p.id === r.paper_position_id) : undefined;
    if (!pos && r.order_id) pos = positions.find((p) => p.order_id === r.order_id);
    if (!pos) return { value: null, realized: false };
    const realized = pos.status === 'closed';
    const live = pnlByPos.get(pos.id);
    const value = realized
      ? (pos.realized_pnl_usd ?? live?.realized_pnl_usd ?? null)
      : (live?.estimated_pnl_usd ?? null);
    return {
      value, realized, status: pos.status, currentSpot: live?.current_spot ?? null,
      direction: live?.direction, contracts: live?.contracts, leverage: live?.leverage,
      entryTimeMs: live?.entry_timestamp_ms, entryPriceReal: live?.entry_price_real,
      initialSl: live?.initial_sl, initialTp: live?.initial_tp,
      currentSl: live?.current_sl, currentTp: live?.current_tp,
      trailMode: live?.trail_mode, trailState: live?.trail_state as SignalPnl['trailState'],
      orderId: live?.order_id, orderStatus: live?.order_status,
      mode: live?.mode, structureType: live?.structure_type,
    };
  };

  // P&L straight from a real position (open or closed) — same shape as pnlFor but
  // sourced from the position itself, so rows survive reloads and show up even when
  // there's no localStorage execution record (e.g. trades placed in another session).
  const pnlForPos = (pos: PaperPosition): SignalPnl => {
    const realized = pos.status === 'closed';
    const live = pnlByPos.get(pos.id);
    const value = realized
      ? (pos.realized_pnl_usd ?? live?.realized_pnl_usd ?? null)
      : (live?.estimated_pnl_usd ?? null);
    return {
      value, realized, status: pos.status, currentSpot: live?.current_spot ?? null,
      direction: live?.direction ?? (pos.sized_trade?.structure?.direction as string | undefined),
      contracts: live?.contracts, leverage: live?.leverage,
      entryTimeMs: live?.entry_timestamp_ms ?? pos.entry_timestamp_ms,
      entryPriceReal: live?.entry_price_real ?? pos.entry_spot_price,
      exitPriceReal: pos.exit_spot_price ?? null,
      initialSl: live?.initial_sl ?? pos.initial_sl, initialTp: live?.initial_tp ?? pos.initial_tp,
      currentSl: live?.current_sl ?? pos.current_sl, currentTp: live?.current_tp ?? pos.current_tp,
      trailMode: live?.trail_mode ?? pos.trail_mode, trailState: live?.trail_state as SignalPnl['trailState'],
      orderId: live?.order_id ?? pos.order_id, orderStatus: live?.order_status ?? pos.order_status,
      mode: live?.mode, structureType: live?.structure_type,
    };
  };

  // Synthesize a signal-row + execution-record from a real position so it renders
  // with the executed (rich) layout: entry/stop/target come straight off the fill.
  const signalFromPos = (pos: PaperPosition, strategy: string): ScalpingSignal => {
   const nd = parseScalpNotes(pos.notes);
   return ({
    underlying: pos.underlying, close: pos.entry_spot_price ?? 0,
    strategy, direction: (pos.sized_trade?.structure?.direction as string) || nd.direction || 'none',
    near_level: nd.near_level, level_type: nd.level_type, pattern: nd.pattern, reason: pos.notes || '',
    entry: pos.entry_spot_price ?? null, stop_loss: pos.initial_sl ?? null, take_profit: pos.initial_tp ?? null,
    risk_pct: pos.sized_trade?.capital_at_risk_pct ?? null,
    leverage: pos.sized_trade?.structure?.leverage ?? null,
    size_units: pos.sized_trade?.contracts ?? null,
    notional_usd: pos.sized_trade?.position_value ?? null,
    entry_ok: true, executable: false, timestamp_ms: pos.entry_timestamp_ms ?? 0, error: null,
    profile: pos.mode || 'intraday',
  });
  };
  const execStateFromPos = (pos: PaperPosition, strategy: string): ExecState => {
    // Execution mode pill is PAPER vs LIVE — derived from the book (is_paper).
    // NOT pos.mode, which is the macro *trading* mode (scalping/intraday/swing/…)
    // and would mislabel the pill as e.g. "SWING".
    const modeStr = pos.is_paper ? 'PAPER' : 'LIVE';
    // The [AUTO] tag in the notes (set at execute time) marks algo-placed trades,
    // so reconstructed rows consistently show "AUTO · <MODE>" like fresh ones.
    const auto = /\[AUTO\]/.test(pos.notes || '');
    return {
      mode: modeStr, auto,
      resp: {
        accepted: true, mode: modeStr.toLowerCase(),
        underlying: pos.underlying, strategy,
        direction: (pos.sized_trade?.structure?.direction as string) ?? 'none',
        size_units: pos.sized_trade?.contracts ?? 0,
        notional_usd: pos.sized_trade?.position_value ?? 0,
        entry_price: pos.entry_spot_price ?? null,
        stop_loss: pos.initial_sl ?? null, take_profit: pos.initial_tp ?? null,
        order_id: pos.order_id ?? null, paper_position_id: pos.id,
        status: pos.status, reason: '', timestamp_ms: pos.entry_timestamp_ms ?? 0,
        telegram_alert_sent: false,
      },
    };
  };

  // mutateAsync (not mutate) is essential here: the auto-exec loop fires several
  // executions on one shared mutation observer, and mutate()'s per-call callbacks
  // only fire for the LAST call — leaving the rest stuck "queued". The promise
  // returned by mutateAsync resolves independently for each call.
  const onExecute = (sym: string, strategy: string, auto = false, override_entry: number | null = null, override_stop: number | null = null) => {
    const key = `${sym}-${strategy}`;
    setExecKeys((s) => new Set(s).add(key));
    exec.mutateAsync({ underlying: sym, strategy, auto, override_entry, override_stop })
      // Tie an ACCEPTED record to the book it actually landed in (r.mode) — a live
      // order stores as LIVE, shadow/paper as their own book. A REJECTION never ran
      // in any book: the backend hardcodes mode="paper" on its early-return rejects,
      // so trusting r.mode here files a shadow/live rejection under "PAPER", which
      // modeExecStates then filters out of the current view — leaving the card stuck
      // on "⚡ Auto-executing…" with the real reason (e.g. size_too_small) hidden.
      // Tag rejections with the mode the user actually attempted in (tradeMode).
      .then((r) => { const ranMode = (r.accepted ? (r.mode || tradeMode) : tradeMode).toUpperCase(); setExecStates((m) => ({ ...m, [key]: { resp: r, auto, mode: ranMode } })); if (r.accepted) acceptedRef.current.add(key); logExec({ ts: Date.now(), key, mode: ranMode, ok: !!r.accepted, status: r.status, reason: r.reason, auto }); })
      .catch((e: Error) => { setExecStates((m) => ({ ...m, [key]: { error: e.message, auto, mode: tradeMode } })); logExec({ ts: Date.now(), key, mode: tradeMode, ok: false, status: 'error', reason: e.message, auto }); })
      .finally(() => { setExecKeys((s) => { const n = new Set(s); n.delete(key); return n; }); });
  };

  const data = scanQ.data;

  const statusScoped = (data?.signals ?? []).filter((s) => 
    (stratFilter === 'all' || s.strategy === stratFilter) &&
    (profileFilter === 'all' || s.profile === profileFilter) &&
    (statusFilter === 'all' ? getSignalStatus(s) !== 'other' : getSignalStatus(s) === statusFilter)
  );

  // Actionable rows have a direction (READY = executable, WATCH = armed-not-tradeable,
  // PENDING = pattern found but risk-rejected). long/short kept even when entry_ok is
  // false so "skipped: stop too wide / cramped R:R" near-misses stay visible.
  const signals = statusScoped.filter((s) => s.direction === 'long' || s.direction === 'short');
  // In-progress / watching: price is AT a 4H level but no pattern has confirmed yet
  // (direction "none" + a near_level). These aren't tradeable, but they show what's
  // brewing — sorted by proximity to the level (closest to triggering first). The
  // pure-noise "none" rows (no nearby level / insufficient data) are excluded.
  const watchingSignals = statusScoped
    .filter((s) => s.direction === 'none' && s.near_level != null)
    .sort((a, b) => {
      const pa = a.close && a.near_level ? Math.abs(a.close - a.near_level) / a.close : 1;
      const pb = b.close && b.near_level ? Math.abs(b.close - b.near_level) / b.close : 1;
      return pa - pb;
    });

  // Current-mode view of executions. execStates keeps ALL modes (persisted), but
  // the list only shows trades that ran in the mode you're currently in — so
  // paper / shadow / live each see only their own executions.
  const modeExecStates = useMemo(
    () => Object.fromEntries(Object.entries(execStates).filter(([, es]) => (es.mode || 'PAPER') === tradeMode)),
    [execStates, tradeMode],
  );

  // ── Executed rows are derived from REAL backend positions, not localStorage ──
  // Scoped to the current book: LIVE shows is_paper=false fills, PAPER/SHADOW show
  // is_paper=true. So live trades — including ones placed by the algo or from
  // another browser session — render with full entry/stop/target/P&L just like
  // paper. Each position is its own row (keyed by id) so repeated trades on the
  // same setup don't collapse. localStorage execStates is kept only as transient
  // feedback for a row you just clicked, before its position streams in.
  type Row = { key: string; s: ScalpingSignal; es?: ExecState; pnl?: SignalPnl; executed: boolean; macroMode: string };
  const wantPaper = tradeMode !== 'LIVE';

  const scalpPositions = useMemo(
    () => positions
      .filter((p) => stratFromNotes(p.notes) && (!!p.is_paper === wantPaper))
      .filter((p) => {
        if (stratFilter !== 'all' && stratFromNotes(p.notes) !== stratFilter) return false;
        // Position notes don't currently contain the profile, so we allow them through the profile filter.
        return true;
      })
      .sort((a, b) => {
        const ao = a.status !== 'closed' ? 1 : 0, bo = b.status !== 'closed' ? 1 : 0;
        if (ao !== bo) return bo - ao;                         // open positions before closed
        return (b.entry_timestamp_ms ?? 0) - (a.entry_timestamp_ms ?? 0);  // newest first
      }),
    [positions, wantPaper, stratFilter, profileFilter],
  );

  // Open auto-trades still running in the current book (ignores the strategy
  // filter — the "Algo paused" banner reflects ALL of them). When Algo is OFF
  // these keep being managed to SL/TP by the backend monitor, but won't re-enter.
  const openAutoPos = useMemo(
    () => positions.filter((p) =>
      p.status !== 'closed' &&
      (!!p.is_paper === wantPaper) &&
      stratFromNotes(p.notes) &&
      /\[AUTO\]/.test(p.notes || '')),
    [positions, wantPaper],
  );
  const resumeAlgo = () => setAlgo.mutate(true);
  const closeAllAuto = () => {
    for (const p of openAutoPos) {
      const spot = pnlByPos.get(p.id)?.current_spot ?? streamPrices[p.underlying] ?? p.entry_spot_price ?? 0;
      if (spot > 0) closePos.mutate({ id: p.id, exit_spot_price: spot });
    }
  };

  const executedRows: Row[] = scalpPositions.map((p) => {
    const strat = stratFromNotes(p.notes) as string;
    return {
      key: p.id, s: signalFromPos(p, strat), es: execStateFromPos(p, strat),
      pnl: pnlForPos(p), executed: true, macroMode: (p.mode || macroMode || '').toUpperCase(),
    };
  });

  // A setup with an OPEN position in this book is already shown above — drop its
  // scan row so we don't show a duplicate "READY" line for a live trade.
  const openSetupKeys = new Set(
    scalpPositions.filter((p) => p.status !== 'closed').map((p) => `${p.underlying}-${stratFromNotes(p.notes)}`),
  );

  const scanRows: Row[] = signals
    .filter((s) => !openSetupKeys.has(`${s.underlying}-${s.strategy}`) && !acceptedRef.current.has(`${s.underlying}-${s.strategy}`))
    .map((s) => {
      const key = `${s.underlying}-${s.strategy}`;
      const es = modeExecStates[key];
      // Surface ONLY a rejection/error record inline (for the failure reason). An
      // ACCEPTED record means a position opened — that's its own row from
      // positions (above), and once it CLOSES the setup is free to re-arm, so a
      // stale accept must never suppress the EXECUTE button on a live signal.
      const feedbackEs = es && !es.resp?.accepted ? es : undefined;
      return { key, s, es: feedbackEs, pnl: undefined, executed: false, macroMode: s.profile };
    });

  // In-progress rows — price at a 4H level, no confirmed pattern yet (not tradeable).
  const watchingRows: Row[] = watchingSignals
    .filter((s) => !openSetupKeys.has(`${s.underlying}-${s.strategy}`))
    .map((s) => ({ key: `${s.underlying}-${s.strategy}-watch`, s, es: undefined, pnl: undefined, executed: false, macroMode: s.profile }));

  const executedSignals: Row[] = executedRows;       // real open/closed positions for this book
  const restSignals: Row[] = scanRows;               // live scan signals (button when ready & algo off)
  const displaySignals: Row[] = [...executedSignals, ...restSignals, ...watchingRows];

  // Show the trade-plan columns (Entry/Current/Stop/Target/Risk) only when at
  // least one armed/executed signal exists. The header AND every card must
  // agree on this, or the plan-width block in the cards drifts the later
  // columns out from under their headers (a "Watching-only" list hid the plan
  // header but the cards still reserved its width). Single source of truth:
  const showPlan = executedSignals.length + restSignals.length > 0;
  // The Action column is dropped entirely when no row can act (a Watching-only
  // list) — an always-empty column is just dead space. A row acts when it's an
  // executed position or a currently-executable signal.
  const showAction = executedSignals.length > 0 || restSignals.some((r) => r.s.executable);
  // The Direction column is dropped when no row has a long/short bias yet (every
  // value would be "—") — e.g. a list of "near level / watching" rows.
  const showDirection = displaySignals.some((r) => r.s.direction === 'long' || r.s.direction === 'short');

  // Active profile's timeframes, for the compact header badge (replaces the
  // wordy "4H structure · 15min entry" subtitle — and reflects the real config
  // instead of hardcoded values).
  const _activeProf = cfg?.profiles?.[cfg?.active_profiles?.[0] ?? ''];
  const tfBadge = cfg?.use_optimized 
    ? '🤖 WFO DYNAMIC' 
    : `${(_activeProf?.macro_timeframe ?? '4h').toUpperCase()} → ${(_activeProf?.execution_timeframe ?? '15m').toUpperCase()}`;

  const selectedRow = displaySignals.find(r => r.key === selectedRowKey);
  const displayStrat = (stratFilter !== 'all') ? stratFilter : (selectedRow ? selectedRow.s.strategy : null);
  const displayProf = (profileFilter !== 'all') ? profileFilter : (selectedRow ? selectedRow.s.profile : null);

  let stratLine1 = "";
  let stratName = "";
  if (displayStrat === 'price_action') {
    stratName = "PRICE ACTION";
    stratLine1 = "Breakout from 5 strict patterns (Double Bottom/Triangles) with 1:2 Risk.";
  } else if (displayStrat === 'smc') {
    stratName = "SMC";
    stratLine1 = "Hunts for Orderblocks, FVGs, and Liquidity Sweeps.";
  } else if (displayStrat === 'ma_crossover') {
    stratName = "MA CROSSOVER";
    stratLine1 = "Trend-following via moving average momentum shifts.";
  } else if (displayStrat === 'mean_reversion') {
    stratName = "MEAN REVERSION";
    stratLine1 = "Fades overextended price action back to the mean.";
  } else if (displayStrat === 'breakout') {
    stratName = "BREAKOUT";
    stratLine1 = "Enters on high-volume breaches of key support/resistance.";
  } else {
    stratName = "GLOBAL";
    stratLine1 = "Select a specific signal row or filter by strategy to view execution logic.";
  }

  const profName = displayProf ? displayProf.toUpperCase() : 'MULTI-PROFILE';
  const stratLine2 = cfg?.use_optimized 
    ? <span style={{ color: 'var(--t-green)' }}>💡 WFO Active: Mathematically enforcing top-tier edge on {profName}.</span>
    : <span style={{ color: 'var(--t-red)', fontWeight: 600 }}>⚠️ WARNING (RETAIL MODE): Unrestricted execution. Vector tests prove sub-1H noise trades destroy capital via fees. ENABLE AI GATEKEEPER!</span>;

  // Consolidated totals across the current mode's executed trades.
  const consolidated = executedSignals.reduce((acc, row) => {
    const v = row.pnl?.value ?? 0;
    acc.totalPnl += v;
    if (row.pnl?.realized) acc.realizedPnl += v; else acc.openPnl += v;
    acc.notional += row.es?.resp?.notional_usd ?? 0;
    if (v > 0) acc.wins += 1; else if (v < 0) acc.losses += 1;
    return acc;
  }, { totalPnl: 0, openPnl: 0, realizedPnl: 0, notional: 0, wins: 0, losses: 0 });

  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setDrawer(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawer]);

  // Persist sidebar selections across reloads.
  useEffect(() => { localStorage.setItem('scalp.stratFilter', stratFilter); }, [stratFilter]);
  useEffect(() => { localStorage.setItem('scalp.profileFilter', profileFilter); }, [profileFilter]);
  useEffect(() => { localStorage.setItem('scalp.statusFilter', statusFilter); }, [statusFilter]);
  // Persist executions (all modes) so the executed rows survive a reload.
  useEffect(() => {
    try { localStorage.setItem('scalp.execStates', JSON.stringify(execStates)); } catch { /* quota */ }
  }, [execStates]);
  useEffect(() => {
    try { localStorage.setItem('scalp.execLog', JSON.stringify(execLog)); } catch { /* quota */ }
  }, [execLog]);

  // Algo auto-execution: while Algo is ON, EVERY ready (executable) signal is
  // fired immediately. The /scalping/execute endpoint routes through the active
  // Paper/Shadow/Live mode. Runaway is prevented at the source — the backend
  // refuses to open a second position on the same symbol+strategy — so no
  // frontend position cap is needed; every distinct ready setup executes.
  // De-duped per symbol+strategy so the 30s rescan never re-fires the same setup.
  useEffect(() => {
    if (!algoOn) return;
    for (const s of data?.signals ?? []) {
      if (!s.executable) continue;
      const key = `${s.underlying}-${s.strategy}`;
      if (acceptedRef.current.has(key)) continue;  // never re-execute a filled trade
      if (autoExecRef.current.has(key)) continue;  // already attempted this session
      autoExecRef.current.add(key);
      onExecute(s.underlying, s.strategy, true, s.entry ?? null, s.stop_loss ?? null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [algoOn, data, tradeMode]);

  // Forget de-dupe keys once Algo is switched off, so re-enabling starts fresh.
  useEffect(() => { if (!algoOn) autoExecRef.current.clear(); }, [algoOn]);

  // On mode change (and on mount/reload), re-scope the de-dup refs to the current
  // mode WITHOUT deleting executions — every mode keeps its own trades. Only trades
  // accepted in THIS mode block re-execution; the auto-exec loop starts fresh.
  useEffect(() => {
    acceptedRef.current = new Set(
      Object.entries(execStates)
        .filter(([, es]) => (es.mode || 'PAPER') === tradeMode && es.resp?.accepted)
        .map(([k]) => k),
    );
    autoExecRef.current.clear();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tradeMode]);

  // Once an executed position CLOSES, free its signal for re-entry WITHOUT deleting
  // the record — clearing the dedup refs lets the algo re-enter (and the card shows
  // a Re-enter button) while the closed trade's realized P&L stays counted in the
  // consolidated total. (Deleting it here made the total drop realized P&L.)
  useEffect(() => {
    for (const [k, es] of Object.entries(execStates)) {
      if (es.resp?.accepted && pnlFor(es.resp).realized) {
        acceptedRef.current.delete(k);
        autoExecRef.current.delete(k);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positions]);

  const isStrategyEnabled = (s: ScalpingSignal) => {
    const p = cfg?.profiles?.[s.profile];
    if (!p) return true;
    if (s.strategy === 'price_action') return p.enable_price_action;
    if (s.strategy === 'smc') return p.enable_smc;
    if (s.strategy === 'ma_crossover') return p.enable_ma_crossover;
    if (s.strategy === 'mean_reversion') return p.enable_mean_reversion;
    if (s.strategy === 'breakout') return p.enable_breakout;
    if (s.strategy === 'delta_gamma') return p.enable_delta_gamma;
    return true;
  };

  const baseSignals = (data?.signals ?? []).filter(s => getSignalStatus(s) !== 'other' && isStrategyEnabled(s));

  const stratNavItems = [
    { id: 'all', label: 'All Strategies', color: 'var(--t-bright)', count: baseSignals.filter((s) => (profileFilter === 'all' || s.profile === profileFilter) && (statusFilter === 'all' || getSignalStatus(s) === statusFilter)).length },
    { id: 'price_action', label: 'Price Action', color: 'var(--t-amber)', count: baseSignals.filter((s) => s.strategy === 'price_action' && (profileFilter === 'all' || s.profile === profileFilter) && (statusFilter === 'all' || getSignalStatus(s) === statusFilter)).length },
    { id: 'smc', label: 'Smart Money', color: 'var(--t-purple)', count: baseSignals.filter((s) => s.strategy === 'smc' && (profileFilter === 'all' || s.profile === profileFilter) && (statusFilter === 'all' || getSignalStatus(s) === statusFilter)).length },
    { id: 'ma_crossover', label: 'MA Crossover', color: 'var(--t-blue)', count: baseSignals.filter((s) => s.strategy === 'ma_crossover' && (profileFilter === 'all' || s.profile === profileFilter) && (statusFilter === 'all' || getSignalStatus(s) === statusFilter)).length },
    { id: 'mean_reversion', label: 'Mean Reversion', color: 'var(--t-cyan)', count: baseSignals.filter((s) => s.strategy === 'mean_reversion' && (profileFilter === 'all' || s.profile === profileFilter) && (statusFilter === 'all' || getSignalStatus(s) === statusFilter)).length },
    { id: 'breakout', label: 'Breakout', color: 'var(--t-green)', count: baseSignals.filter((s) => s.strategy === 'breakout' && (profileFilter === 'all' || s.profile === profileFilter) && (statusFilter === 'all' || getSignalStatus(s) === statusFilter)).length },
  ];

  const profileNavItems = [
    { id: 'all', label: 'All Profiles', color: 'var(--t-bright)', count: baseSignals.filter((s) => (stratFilter === 'all' || s.strategy === stratFilter) && (statusFilter === 'all' || getSignalStatus(s) === statusFilter)).length },
    { id: 'intraday', label: 'Intraday', color: 'var(--t-cyan)', count: baseSignals.filter((s) => s.profile === 'intraday' && (stratFilter === 'all' || s.strategy === stratFilter) && (statusFilter === 'all' || getSignalStatus(s) === statusFilter)).length },
    { id: 'scalping', label: 'Scalping', color: 'var(--t-orange)', count: baseSignals.filter((s) => s.profile === 'scalping' && (stratFilter === 'all' || s.strategy === stratFilter) && (statusFilter === 'all' || getSignalStatus(s) === statusFilter)).length },
    { id: 'aggressive', label: 'Aggressive', color: 'var(--t-red)', count: baseSignals.filter((s) => s.profile === 'aggressive' && (stratFilter === 'all' || s.strategy === stratFilter) && (statusFilter === 'all' || getSignalStatus(s) === statusFilter)).length },
  ];

  const statusNavItems = [
    { id: 'all', label: 'All Statuses', color: 'var(--t-bright)', count: baseSignals.filter((s) => (stratFilter === 'all' || s.strategy === stratFilter) && (profileFilter === 'all' || s.profile === profileFilter)).length },
    { id: 'ready', label: 'Ready (Armed)', color: 'var(--t-green)', count: baseSignals.filter((s) => getSignalStatus(s) === 'ready' && (stratFilter === 'all' || s.strategy === stratFilter) && (profileFilter === 'all' || s.profile === profileFilter)).length },
    { id: 'pending', label: 'Pending (Setup)', color: 'var(--t-amber)', count: baseSignals.filter((s) => getSignalStatus(s) === 'pending' && (stratFilter === 'all' || s.strategy === stratFilter) && (profileFilter === 'all' || s.profile === profileFilter)).length },
    { id: 'watching', label: 'Watching (Levels)', color: 'var(--t-blue)', count: baseSignals.filter((s) => getSignalStatus(s) === 'watching' && (stratFilter === 'all' || s.strategy === stratFilter) && (profileFilter === 'all' || s.profile === profileFilter)).length },
  ];

  const renderNavGroup = (items: {id: string, label: string, color: string, count?: number}[], active: string, onClick: (id: string) => void) => (
    <>
      {items.map((item) => {
        const isActive = active === item.id;
        return (
          <button key={item.id} onClick={() => onClick(item.id)} style={{
            display: 'flex', alignItems: 'center', gap: 10, width: '100%',
            padding: '10px 12px', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit',
            background: isActive ? `var(--t-bg)` : 'transparent',
            border: isActive ? `1px solid var(--t-border)` : '1px solid transparent',
            color: isActive ? item.color : 'var(--t-muted)',
            marginBottom: 4, transition: 'all .2s ease',
            transform: isActive ? 'translateX(2px)' : 'none'
          }}>
            <div style={{ width: 8, height: 8, borderRadius: 4, background: item.color, flexShrink: 0, opacity: isActive ? 1 : 0.6 }} />
            <span style={{ fontSize: 11, fontWeight: isActive ? 700 : 600, letterSpacing: '0.02em' }}>{item.label}</span>
            {item.count != null && <span style={{ marginLeft: 'auto', fontSize: 10, fontWeight: 700, opacity: 0.8 }}>{item.count}</span>}
          </button>
        );
      })}
    </>
  );

  const btUnderlying = selected || cfg?.symbols?.[0] || 'BTC';

  const renderCardWithFlags = (row: Row, flags: ColFlags) => (
    <ScalpSignalCard
      key={row.key} s={row.s}
      selected={selectedRowKey === row.key}
      expanded={expandedKey === row.key}
      onSelect={() => { 
        setSelected(row.s.underlying); 
        setSelectedRowKey(row.key); 
        setExpandedKey((k) => (k === row.key ? null : row.key)); 
      }}
      onExecute={() => onExecute(row.s.underlying, row.s.strategy, false, row.s.entry ?? null, row.s.stop_loss ?? null)}
      executing={execKeys.has(`${row.s.underlying}-${row.s.strategy}`)}
      execState={row.es}
      pnl={row.pnl}
      algoOn={algoOn}
      mode={tradeMode}
      macroMode={row.macroMode}
      showPlan={flags.plan}
      showAction={flags.action}
      showDirection={flags.dir}
      showPattern={flags.pattern}
      livePx={streamPrices?.[row.s.underlying]}
    />
  );

  return (
    <>
    <ThreeColumnLayout
      leftWidth={300}
      rightWidth={380}
      leftSidebar={<>
        <LeftSection label="Tools" collapsible defaultOpen>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <SettingsTrigger onClick={() => setDrawer(true)} />
            <DerivativesTrigger onClick={() => setDerivDrawer(true)} />
            <StrategyCatalogTrigger onClick={() => setCatalogDrawer(true)} />
            <EdgeGateTrigger onClick={() => setEdgeGateDrawer(true)} />
          </div>
        </LeftSection>
        <LeftSection label="Strategies" collapsible defaultOpen>
          {renderNavGroup(stratNavItems, stratFilter, setStratFilter)}
        </LeftSection>
        <LeftSection label="Profiles" collapsible defaultOpen>
          {renderNavGroup(profileNavItems, profileFilter, setProfileFilter)}
        </LeftSection>
        <LeftSection label="Status" collapsible defaultOpen>
          {renderNavGroup(statusNavItems, statusFilter, setStatusFilter)}
        </LeftSection>
        <LeftSection label={`Execution Log · ${tradeMode}`} collapsible defaultOpen={execLog.length > 0} border={false}>
          {execLog.length > 0 && (
            <button onClick={() => setExecLog([])} style={{
              background: 'transparent', border: '1px solid var(--t-border)', color: 'var(--t-muted)',
              fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', cursor: 'pointer', fontFamily: 'inherit',
              textTransform: 'uppercase', padding: '2px 8px', borderRadius: 4, marginBottom: 8,
            }}>Clear</button>
          )}
          <div style={{ maxHeight: 360, overflow: 'auto', margin: '0 -14px' }}>
            <ExecLog entries={execLog} mode={tradeMode} />
          </div>
        </LeftSection>
      </>}
      centerHeader={<>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '4px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <span style={{ fontSize: 16, fontWeight: 700, letterSpacing: '0.04em', color: 'var(--t-bright)' }}>Sterling Engine</span>
            
            <span style={{
              fontSize: 9, fontWeight: 600, letterSpacing: '0.06em', color: cfg?.use_optimized ? 'var(--t-blue)' : 'var(--t-text)', whiteSpace: 'nowrap',
              padding: '2px 7px', borderRadius: 'var(--radius-xs)', border: `1px solid ${cfg?.use_optimized ? 'var(--t-blue)40' : 'var(--t-border)'}`, 
              background: cfg?.use_optimized ? 'var(--t-blue)10' : 'var(--t-bg2)'
            }}>{tfBadge}</span>

            <span title="Live scan auto-refreshes every ~30s" style={{
              display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 9, fontWeight: 700,
              color: scanQ.isFetching ? 'var(--t-amber)' : 'var(--t-green)',
            }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor' }} />
              {scanQ.isFetching ? 'scanning' : 'live'}
            </span>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', fontSize: 11, lineHeight: 1.4, color: 'var(--t-muted)' }}>
            <div><strong style={{ color: 'var(--t-text)' }}>{stratName}:</strong> {stratLine1}</div>
            <div>{stratLine2}</div>
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontSize: 9, fontWeight: 600, letterSpacing: '0.06em',
            padding: '3px 9px', borderRadius: 5, whiteSpace: 'nowrap',
            background: anyWfoActive ? 'var(--t-blue)14' : 'var(--t-border)',
            color: anyWfoActive ? 'var(--t-blue)' : 'var(--t-dim)', 
            border: `1px solid ${anyWfoActive ? 'var(--t-blue)44' : 'transparent'}`,
          }}>{anyWfoActive ? '🤖 WFO: ON' : '👤 WFO: OFF'}</span>
          {algoOn && (
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
              padding: '3px 9px', borderRadius: 5, whiteSpace: 'nowrap',
              background: tint('var(--t-green)'), color: 'var(--t-green)', border: '1px solid var(--t-green)44',
            }}>⚡ ALGO AUTO-EXEC</span>
          )}
          <ModeSelector mode={routerMode} onChange={onModeSelect} />
        </div>
      </>}
      centerContent={
        <div style={{ height: '100%', overflowY: 'auto' }}>
            {/* Algo paused — open auto-trades remain (managed to SL/TP, no re-entry). */}
            {!algoOn && openAutoPos.length > 0 && (
              <div style={{
                position: 'sticky', top: 0, zIndex: 5,
                display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
                padding: '9px 14px', borderRadius: 8, marginBottom: 8,
                border: `1px solid ${tint('var(--t-amber)', 45)}`,
                background: 'var(--t-bg2)',
              }}>
                <span style={{ fontSize: 13 }}>⏸</span>
                <span style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-amber)' }}>ALGO OFF</span>
                <span style={{ fontSize: 11, color: 'var(--t-text)' }}>
                  {openAutoPos.length} auto-trade{openAutoPos.length > 1 ? 's' : ''} still open ({tradeMode}) — being managed to SL/TP, but <b style={{ color: 'var(--t-bright)' }}>no re-entry</b> until Algo is back on.
                </span>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                  <button onClick={resumeAlgo} disabled={setAlgo.isPending} style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.04em', padding: '4px 12px', borderRadius: 6,
                    fontFamily: 'inherit', cursor: 'pointer', color: 'var(--t-green)',
                    background: tint('var(--t-green)', 14), border: '1px solid var(--t-green)44',
                  }}>{setAlgo.isPending ? '…' : '▶ Resume Algo'}</button>
                  <button onClick={closeAllAuto} disabled={closePos.isPending} style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.04em', padding: '4px 12px', borderRadius: 6,
                    fontFamily: 'inherit', cursor: 'pointer', color: 'var(--t-red)',
                    background: tint('var(--t-red)', 12), border: '1px solid var(--t-red)44',
                  }}>Close all</button>
                </div>
              </div>
            )}
            {scanQ.isError && (
              <div style={{
                margin: '20px 0',
                padding: '20px',
                border: '1px solid var(--t-red)33',
                borderRadius: 12,
                background: 'linear-gradient(180deg, var(--t-red)0c 0%, transparent 100%)',
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
                backdropFilter: 'blur(10px)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ 
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    width: 24, height: 24, borderRadius: '50%', 
                    background: 'var(--t-red)1c', color: 'var(--t-red)', 
                    fontSize: 12, fontWeight: 900 
                  }}>✕</div>
                  <div style={{ color: 'var(--t-red)', fontSize: 13, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                    Engine Disconnected
                  </div>
                </div>
                
                {((scanQ.error as Error).message === 'Failed to fetch' || (scanQ.error as Error).message.includes('Failed to fetch')) ? (
                  <div style={{ paddingLeft: 34, display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ color: 'var(--t-dim)', fontSize: 12, lineHeight: 1.5 }}>
                      The local routing engine is unreachable. Please verify that the <strong style={{ color: 'var(--t-bright)', fontWeight: 600 }}>Python backend</strong> is currently running in your terminal.
                    </div>
                    
                    <div style={{
                      background: 'var(--bg-d)', 
                      border: '1px solid var(--t-border)',
                      borderRadius: 6,
                      padding: '12px 16px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 16
                    }}>
                      <code style={{ 
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                        fontSize: 11,
                        color: 'var(--t-bright)',
                        userSelect: 'all',
                        whiteSpace: 'nowrap',
                        overflowX: 'auto',
                      }}>
                        <span style={{ color: 'var(--t-dim)', userSelect: 'none' }}>$ </span>
                        cd backend && source .venv/bin/activate && uvicorn main:app --reload
                      </code>
                    </div>
                  </div>
                ) : (
                  <div style={{ paddingLeft: 34, color: 'var(--t-dim)', fontSize: 12, lineHeight: 1.5 }}>
                    {(scanQ.error as Error).message}
                  </div>
                )}
              </div>
            )}
            {scanQ.isLoading && <div style={{ ...dim, padding: '40px 0', textAlign: 'center' }}>scanning…</div>}
            <div style={card}>
              <div 
                style={{ ...cardHead, cursor: 'pointer', userSelect: 'none' }}
                onClick={() => setSpotExpanded(!spotExpanded)}
              >
                <span style={{ marginRight: 6, fontSize: 10, color: 'var(--t-dim)' }}>{spotExpanded ? '▾' : '▸'}</span>
                <span>SPOT · INDEX </span>
                <span style={{ marginLeft: 8, fontSize: 9, color: 'var(--t-dim)', letterSpacing: 0 }}>
                  underlying directional algorithms
                  {stratFilter !== 'all' ? ` · ${stratFilter}` : ''}
                </span>
                <span style={{ marginLeft: 'auto', fontSize: 9, color: 'var(--t-dim)' }}>
                  {displaySignals.length} active
                </span>
              </div>
              
              {spotExpanded && (
                data && displaySignals.length === 0 ? (
                  <div style={{ padding: 24, fontSize: 10, color: 'var(--t-dim)', textAlign: 'center' }}>
                    {statusFilter === 'ready' ? 'No ready signals — clear the filter to see all.' : 'No spot signals on this data source.'}
                  </div>
                ) : (
                  <div style={{ ...cardBody, padding: 0, overflowX: 'auto' }}>
                    <table style={{ width: '100%', minWidth: 920, tableLayout: 'fixed', borderCollapse: 'collapse', fontSize: 11 }}>
                      <colgroup>
                        {TABLE_COLS.map((col) => (
                          <col key={col.key} style={{ width: SIGNAL_COL_PCT[col.key] }} />
                        ))}
                      </colgroup>
                      <thead>
                        <tr style={{
                          background: c.surface, color: c.muted,
                          fontSize: 9, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase',
                        }}>
                          {TABLE_COLS.map((col) => (
                            <th key={col.key} style={{
                              padding: '5px 8px', verticalAlign: 'middle',
                              textAlign: col.align ?? (col.key === 'action' ? 'right' : 'left'),
                              borderBottom: `1px solid ${c.border}`, whiteSpace: 'nowrap',
                            }}>{col.label}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {executedSignals.map(r => renderCardWithFlags(r, { plan: true, action: true, dir: true }))}
                        {executedSignals.length > 0 && (
                          <ConsolidatedRow count={executedSignals.length} {...consolidated} />
                        )}
                        {restSignals.map(r => renderCardWithFlags(r, { plan: true, action: true, dir: true }))}
                        {watchingRows.map(r => renderCardWithFlags(r, { plan: true, action: true, dir: true, pattern: false }))}
                      </tbody>
                    </table>
                    {data && displaySignals.length > 0 && (
                      <div style={{ fontSize: 10, color: 'var(--t-dim)', lineHeight: 1.5, padding: '10px 12px 8px 12px' }}>
                        <b style={{ color: 'var(--t-amber)' }}>PA</b> pattern breakout · <b style={{ color: 'var(--t-purple)' }}>SMC</b> inducement + imbalance · <b style={{ color: 'var(--t-blue)' }}>MA</b> SMA/EMA cross · <b style={{ color: 'var(--t-dim)' }}>Watching</b> = at a level, no pattern yet · EXECUTE routes through Paper/Live mode
                      </div>
                    )}
                  </div>
                )
              )}
            </div>

            {/* Phase 4 + auto-exec: two parallel derivatives tables (futures
                + options) populated by the background scanner. EXECUTE
                is manual when algo is OFF; the scanner auto-fires per
                strategy profile when algo is ON. */}
            <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr', gap: 12 }}>
              <FuturesCandidatesTable strategy={stratFilter !== 'all' ? stratFilter : undefined} />
              <OptionsCandidatesTable strategy={stratFilter !== 'all' ? stratFilter : undefined} />
            </div>
          </div>
      }
      rightSidebar={
        <TerminalLog scanInfo={{ count: data?.count, armed: data?.armed_count, ts: data?.timestamp_ms }} lastExec={execLog[0]} />
      }
    >
    </ThreeColumnLayout>

    {liveConfirm && (
      <GoLiveModal
        fromMode={routerMode}
        hasCreds={hasLiveCreds}
        onConfirm={confirmGoLive}
        onCancel={() => setLiveConfirm(false)}
      />
    )}

    {drawer && (
      <div onClick={() => setDrawer(false)} style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'var(--surface-overlay)', display: 'flex', justifyContent: 'flex-start',
      }}>
        <div onClick={(e) => e.stopPropagation()} style={{
          width: 'min(700px, 94vw)', height: '100%', maxHeight: '100vh', background: 'var(--t-bg)', boxSizing: 'border-box',
          borderRight: '1px solid var(--t-border)', overflowY: 'auto', padding: 16,
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Global Strategy Config</span>
            <button onClick={() => setDrawer(false)} title="Close (Esc)" style={{
              marginLeft: 'auto', fontSize: 16, lineHeight: 1, background: 'none',
              border: '1px solid var(--t-border)', borderRadius: 6, color: 'var(--t-dim)',
              width: 30, height: 30, cursor: 'pointer', fontFamily: 'inherit',
            }}>×</button>
          </div>
          {cfg && (
            <ScalpingConfigPanel
              cfg={cfg}
              saving={setCfg.isPending}
              onSave={(c) => setCfg.mutate(c)}
            />
          )}
          </div>
        </div>
      </div>
    )}

    {derivDrawer && (
      <div onClick={() => setDerivDrawer(false)} style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'var(--surface-overlay)', display: 'flex', justifyContent: 'flex-start',
      }}>
        <div onClick={(e) => e.stopPropagation()} style={{
          width: 'min(700px, 94vw)', height: '100%', maxHeight: '100vh', background: 'var(--t-bg)', boxSizing: 'border-box',
          borderRight: '1px solid var(--t-border)', overflowY: 'auto', padding: 16,
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Derivatives Config</span>
              <button onClick={() => setDerivDrawer(false)} title="Close (Esc)" style={{
                marginLeft: 'auto', fontSize: 16, lineHeight: 1, background: 'none',
                border: '1px solid var(--t-border)', borderRadius: 6, color: 'var(--t-dim)',
                width: 30, height: 30, cursor: 'pointer', fontFamily: 'inherit',
              }}>×</button>
            </div>
            
            <div style={{ marginTop: 12, padding: 12, background: 'var(--t-bg3)', borderRadius: 8, border: '1px solid var(--t-border)' }}>
              <div style={{ marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--t-bright)', letterSpacing: '0.04em' }}>
                  ROUTING CONFIG
                </span>
              </div>

              {/* GLOBAL Auto Execute Controls */}
              <div style={{ ...grpBox, gap: 12, marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={grpTitle}>GLOBAL SETTINGS</div>
                  <button
                    disabled={!globalDirty || derivPatchGlobal.isPending}
                    onClick={() => {
                      if (globalDraft) {
                        derivPatchGlobal.mutate({
                          enabled: globalDraft.enabled,
                          auto_execute_futures: globalDraft.fut,
                          auto_execute_options: globalDraft.opt
                        });
                      }
                    }}
                    style={{
                      padding: '4px 10px', borderRadius: 5,
                      background: globalDirty ? alpha('var(--t-blue)', 0.15) : 'transparent',
                      border: `1px solid ${globalDirty ? alpha('var(--t-blue)', 0.4) : 'var(--t-border)'}`,
                      color: globalDirty ? 'var(--t-blue)' : 'var(--t-dim)', fontSize: 10, fontWeight: 700,
                      letterSpacing: '0.06em', cursor: globalDirty ? 'pointer' : 'default',
                      fontFamily: 'inherit',
                    }}>
                    {derivPatchGlobal.isPending ? 'SAVING…' : globalDirty ? 'APPLY' : 'SAVED'}
                  </button>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingBottom: 10 }}>
                  <ChipToggle 
                    label="Auto - Futures" 
                    color="var(--t-green)"
                    on={globalDraft?.fut ?? false} 
                    onChange={(v) => setGlobalDraft(prev => prev ? { ...prev, fut: v, enabled: v || prev.opt } : null)} 
                  />
                  <ChipToggle 
                    label="Auto - Options" 
                    color="var(--t-green)"
                    on={globalDraft?.opt ?? false} 
                    onChange={(v) => setGlobalDraft(prev => prev ? { ...prev, opt: v, enabled: v || prev.fut } : null)} 
                  />
                </div>
              </div>
              
              <DerivativesPanel
                strategy={derivStrategy}
                strategies={[
                  { id: 'scalping/price_action', label: 'PRICE ACTION' },
                  { id: 'scalping/smc', label: 'SMC' },
                  { id: 'scalping/ma_crossover', label: 'MA CROSSOVER' },
                  { id: 'scalping/mean_reversion', label: 'MEAN REVERSION' },
                  { id: 'scalping/breakout', label: 'BREAKOUT' },
                  { id: 'scalping/delta_gamma', label: 'DELTA GAMMA' },
                ]}
                onStrategyChange={setDerivStrategy}
              />
            </div>
          </div>
        </div>
      </div>
    )}

    {catalogDrawer && (
      <div onClick={() => setCatalogDrawer(false)} style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'var(--surface-overlay)', display: 'flex', justifyContent: 'flex-start',
      }}>
        <div onClick={(e) => e.stopPropagation()} style={{
          width: 'min(700px, 94vw)', height: '100%', maxHeight: '100vh', background: 'var(--t-bg)', boxSizing: 'border-box',
          borderRight: '1px solid var(--t-border)', overflowY: 'auto', padding: 16,
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>WHAT'S RUNNING</span>
              <button onClick={() => setCatalogDrawer(false)} title="Close (Esc)" style={{
                marginLeft: 'auto', fontSize: 16, lineHeight: 1, background: 'none',
                border: '1px solid var(--t-border)', borderRadius: 6, color: 'var(--t-dim)',
                width: 30, height: 30, cursor: 'pointer', fontFamily: 'inherit',
              }}>×</button>
            </div>
            <StrategyCatalogPanel />
          </div>
        </div>
      </div>
    )}

    {edgeGateDrawer && (
      <div onClick={() => setEdgeGateDrawer(false)} style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'var(--surface-overlay)', display: 'flex', justifyContent: 'flex-start',
      }}>
        <div onClick={(e) => e.stopPropagation()} style={{
          width: 'min(700px, 94vw)', height: '100%', maxHeight: '100vh', background: 'var(--t-bg)', boxSizing: 'border-box',
          borderRight: '1px solid var(--t-border)', overflowY: 'auto', padding: 16,
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Edge Gate Admission</span>
              <button onClick={() => setEdgeGateDrawer(false)} title="Close (Esc)" style={{
                marginLeft: 'auto', fontSize: 16, lineHeight: 1, background: 'none',
                border: '1px solid var(--t-border)', borderRadius: 6, color: 'var(--t-dim)',
                width: 30, height: 30, cursor: 'pointer', fontFamily: 'inherit',
              }}>×</button>
            </div>
            <EdgeGatePanel />
          </div>
        </div>
      </div>
    )}
    </>
  );
}

export default ScalpingTab;