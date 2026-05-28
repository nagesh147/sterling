import React, { useState } from 'react';
import { useStatArbConfig, useSetStatArbConfig, useStatArbScan } from '../../hooks/useStatArb';
import { useLivePnl } from '../../hooks/useLivePnl';
import { ThreeColumnLayout, LeftSection, RightSection } from '../ThreeColumnLayout';
import { card, cardHead, cardBody, grpBox, grpTitle, chipStyle, gridStyle, tint, alpha } from '../../styles/terminalUI';
import { useTradingMode } from '../../hooks/useTradingMode';
import { useRouterMode, RouterMode } from '../../hooks/useRouterMode';
import type { StatArbConfig, StatArbSignal, StatArbPairConfig } from '../../hooks/useStatArb';

/* ── style tokens ──────────────────────────────────────────────────────────── */
const dim: React.CSSProperties = { color: 'var(--t-dim)', fontSize: 11 };

function NumField({ label, value, step = 1, min, max, onChange }: {
  label: string; value: number; step?: number; min?: number; max?: number; onChange: (v: number) => void;
}) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 10, color: 'var(--t-dim)' }}>
      {label}
      <input
        type="number" value={value} step={step} min={min} max={max}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{
          width: 68, background: 'var(--t-bg)', border: '1px solid var(--t-border)',
          borderRadius: 5, color: 'var(--t-bright)', fontFamily: 'inherit', fontSize: 10,
          padding: '3px 6px', textAlign: 'right',
        }}
      />
    </label>
  );
}

function TfSelect({ label, value, opts, onChange }: { label: string; value: string; opts: string[]; onChange: (v: string) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 10, color: 'var(--t-dim)' }}>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} style={{
        width: 74, background: 'var(--t-bg)', border: '1px solid var(--t-border)', borderRadius: 5,
        color: 'var(--t-bright)', fontFamily: 'inherit', fontSize: 10, padding: '3px 6px', cursor: 'pointer',
      }}>
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

function ChipToggle({ label, on, onChange }: { label: string; on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!on)} style={{
      fontSize: 10, fontWeight: 600, padding: '4px 10px', borderRadius: 'var(--radius-pill)', cursor: 'pointer', fontFamily: 'inherit',
      border: `1px solid ${on ? 'var(--t-green)' : 'var(--t-border)'}`,
      background: on ? tint('var(--t-green)') : 'transparent',
      color: on ? 'var(--t-green)' : 'var(--t-dim)', transition: 'all .1s', whiteSpace: 'nowrap',
    }}>{on ? '● ' : '○ '}{label}</button>
  );
}

function Pill({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', padding: '2px 6px',
      borderRadius: 'var(--radius-sm)', background: alpha(color, 0.13), color, border: `1px solid ${alpha(color, 0.27)}`,
      whiteSpace: 'nowrap', display: 'inline-block', textAlign: 'center',
    }}>{text}</span>
  );
}

const fmt = (v: number | null | undefined, d = 2) => (v == null || !isFinite(v) ? '—' : v.toFixed(d));
const fmtUsd = (v: number | null | undefined) => (v == null || !isFinite(v) ? '—' : '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 }));

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

/* ── config panel ─────────────────────────────────────────────────────────── */

function StatArbConfigPanel({ cfg, onSave, saving }: { cfg: StatArbConfig; onSave: (c: StatArbConfig) => void; saving: boolean }) {
  const [draft, setDraft] = useState<StatArbConfig>(cfg);
  
  // Keep draft in sync if external cfg changes and we aren't dirty
  React.useEffect(() => {
    if (JSON.stringify(draft) === JSON.stringify(cfg)) return;
    // Don't auto-override if the user is editing, but maybe we want to force it?
    // Doing standard sync for now.
    setDraft(cfg);
  }, [cfg]);

  const setRootField = <K extends keyof StatArbConfig>(k: K, v: StatArbConfig[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const dirty = JSON.stringify(draft) !== JSON.stringify(cfg);

  return (
    <div style={card}>
      <div style={cardHead}>
        <span>ENGINE SETTINGS</span>
        <span style={{ display: 'inline-flex', gap: 6, marginLeft: 'auto' }}>
          <button disabled={!dirty || saving} onClick={() => onSave(draft)} style={{
            fontSize: 9, fontWeight: 700, padding: '4px 14px', borderRadius: 5, fontFamily: 'inherit',
            cursor: dirty && !saving ? 'pointer' : 'default',
            border: `1px solid ${dirty ? 'var(--t-green)' : 'var(--t-border)'}`,
            background: dirty ? 'var(--t-green)22' : 'transparent',
            color: dirty ? 'var(--t-green)' : 'var(--t-dim)',
          }}>{saving ? 'SAVING…' : dirty ? 'APPLY' : 'SAVED'}</button>
        </span>
      </div>
      <div style={cardBody}>
        <div style={{ display: 'flex', gap: 5, marginBottom: 12, flexWrap: 'wrap' }}>
          <ChipToggle label="Engine Enabled" on={draft.enabled} onChange={(v) => setRootField('enabled', v)} />
          <ChipToggle label="Auto Trading (Router Hook)" on={draft.auto_trade} onChange={(v) => setRootField('auto_trade', v)} />
        </div>

        <div style={gridStyle()}>
          <div style={grpBox}>
            <div style={grpTitle}>TIMEFRAME & DATA</div>
            <TfSelect label="Resolution" value={draft.timeframe} opts={['1m', '5m', '15m', '1h', '4h', '1d']} onChange={(v) => setRootField('timeframe', v)} />
            <NumField label="Lookback (Bars)" value={draft.lookback_bars} min={10} max={2000} step={10} onChange={(v) => setRootField('lookback_bars', v)} />
          </div>
          
          <div style={grpBox}>
            <div style={grpTitle}>Z-SCORE THRESHOLDS</div>
            <NumField label="Entry Z" value={draft.entry_z_score} min={0.5} max={5} step={0.1} onChange={(v) => setRootField('entry_z_score', v)} />
            <NumField label="Exit Z" value={draft.exit_z_score} min={0} max={2} step={0.1} onChange={(v) => setRootField('exit_z_score', v)} />
            <NumField label="Stop Loss Z" value={draft.stop_loss_z_score} min={1} max={10} step={0.1} onChange={(v) => setRootField('stop_loss_z_score', v)} />
          </div>

          <div style={grpBox}>
            <div style={grpTitle}>RISK / ALLOCATION</div>
            <NumField label="Max Position (USD)" value={draft.max_position_usd} min={100} max={100000} step={100} onChange={(v) => setRootField('max_position_usd', v)} />
          </div>
        </div>

        <div style={{ ...grpBox, marginTop: 12 }}>
          <div style={grpTitle}>CONFIGURED PAIRS</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 160, overflowY: 'auto', paddingRight: 4, flexShrink: 0, marginTop: 8 }}>
            {draft.pairs.map((p, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', background: 'var(--t-bg3)', borderRadius: 6, border: '1px solid var(--t-border)' }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--t-bright)' }}>{p.name}</span>
                <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>
                  X: {p.asset_x} | Y: {p.asset_y} {p.asset_z ? `| Z: ${p.asset_z}` : ''}
                </span>
                <ChipToggle label={p.enabled ? "Active" : "Paused"} on={p.enabled} onChange={(v) => {
                  const newPairs = [...draft.pairs];
                  newPairs[i].enabled = v;
                  setRootField('pairs', newPairs);
                }} />
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}

function SignalCell({ value, color, width = 78 }: { value: React.ReactNode; color?: string; width?: number | string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', width, flexShrink: 0, justifyContent: 'center' }}>
      <span style={{
        fontSize: 13, fontWeight: 700, color: color || 'var(--t-bright)', lineHeight: 1.2,
        fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>{value}</span>
    </div>
  );
}

function StatArbSignalsTable({ signals }: { signals: StatArbSignal[] }) {
  return (
    <div style={card}>
      <div style={cardHead}>
        <span>LIVE SPREADS & SIGNALS</span>
      </div>
      <div style={{ ...cardBody, padding: '0 16px 16px 16px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 20,
          padding: '8px 0', borderBottom: '1px solid var(--t-border)',
          marginBottom: 8,
        }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 120, flexShrink: 0, textTransform: 'uppercase' }}>Pair</span>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 90, flexShrink: 0, textTransform: 'uppercase' }}>State</span>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 80, flexShrink: 0, textTransform: 'uppercase' }}>Action</span>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 80, flexShrink: 0, textTransform: 'uppercase', textAlign: 'right' }}>Z-Score</span>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 100, flexShrink: 0, textTransform: 'uppercase', textAlign: 'right' }}>Spread</span>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 80, flexShrink: 0, textTransform: 'uppercase', textAlign: 'right' }}>StdDev</span>
        </div>
        
        {(!signals || signals.length === 0) ? (
          <div style={{ padding: '20px 0', textAlign: 'center', fontSize: 11, color: 'var(--t-dim)' }}>
            No stat arb signals available. Ensure engine is enabled and data is populated.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {signals.map((s, i) => {
              const zColor = Math.abs(s.current_z) >= 2.0 ? (s.current_z > 0 ? 'var(--t-red)' : 'var(--t-green)') : 'var(--t-dim)';
              const stateColor = s.state === 'armed' ? 'var(--t-amber)' : (s.state.includes('active') ? 'var(--t-blue)' : 'var(--t-dim)');
              
              let actionColor = 'var(--t-dim)';
              if (s.action === 'ENTRY_LONG') actionColor = 'var(--t-green)';
              else if (s.action === 'ENTRY_SHORT') actionColor = 'var(--t-red)';
              else if (s.action === 'EXIT') actionColor = 'var(--t-amber)';

              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 20,
                  padding: '8px 0', borderBottom: '1px solid var(--t-border)',
                }}>
                  <SignalCell value={s.pair_name} width={120} />
                  <div style={{ width: 90, flexShrink: 0 }}><Pill text={s.state} color={stateColor} /></div>
                  <div style={{ width: 80, flexShrink: 0 }}><Pill text={s.action} color={actionColor} /></div>
                  
                  <div style={{ width: 80, flexShrink: 0, textAlign: 'right' }}>
                    <span style={{ fontSize: 14, fontWeight: 800, color: zColor, fontVariantNumeric: 'tabular-nums' }}>
                      {fmt(s.current_z, 2)}
                    </span>
                  </div>
                  
                  <div style={{ width: 100, flexShrink: 0, textAlign: 'right' }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--t-bright)', fontVariantNumeric: 'tabular-nums' }}>
                      {fmt(s.current_spread, 4)}
                    </span>
                  </div>
                  
                  <div style={{ width: 80, flexShrink: 0, textAlign: 'right' }}>
                    <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--t-dim)', fontVariantNumeric: 'tabular-nums' }}>
                      {fmt(s.std_dev, 4)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export function StatArbTab() {
  const { data: configResp } = useStatArbConfig();
  const setConfigMutation = useSetStatArbConfig();
  const { data: scanResp } = useStatArbScan();
  const { mode: routerMode, setMode: setRouterMode } = useRouterMode();
  const { data: pnlData } = useLivePnl();
  
  const handleSaveConfig = (c: StatArbConfig) => {
    setConfigMutation.mutate(c);
  };

  return (
    <ThreeColumnLayout
      leftNav={[
        { id: 'statarb', label: 'Stat Arb', color: 'var(--t-blue)' },
      ]}
      activeNav="statarb"
      onNavClick={() => {}}
      centerHeader={
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
            <div>
              <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Statistical Arbitrage</div>
              <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 1 }}>3D Spread engine • Execution router</div>
            </div>
            <ModeSelector mode={routerMode} onChange={setRouterMode} />
          </div>
        </>
      }
      centerContent={
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {configResp && (
            <StatArbConfigPanel cfg={configResp.config} onSave={handleSaveConfig} saving={setConfigMutation.isPending} />
          )}
          <StatArbSignalsTable signals={scanResp?.signals ?? []} />
        </div>
      }
      rightSidebar={
        <RightSection label="Engine Status">
           <div style={card}>
            <div style={cardHead}>OVERVIEW</div>
            <div style={{ ...cardBody, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 11, color: 'var(--t-dim)' }}>Engine state</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: configResp?.config?.enabled ? 'var(--t-green)' : 'var(--t-red)' }}>
                  {configResp?.config?.enabled ? 'ACTIVE' : 'PAUSED'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 11, color: 'var(--t-dim)' }}>Auto Trading</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: configResp?.config?.auto_trade ? 'var(--t-green)' : 'var(--t-dim)' }}>
                  {configResp?.config?.auto_trade ? 'ON' : 'OFF'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 11, color: 'var(--t-dim)' }}>Armed Signals</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--t-amber)' }}>{scanResp?.armed_count ?? 0}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 11, color: 'var(--t-dim)' }}>Active Pairs</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--t-bright)' }}>
                  {configResp?.config?.pairs?.filter(p => p.enabled)?.length ?? 0} / {configResp?.config?.pairs?.length ?? 0}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--t-border)', paddingTop: 10, marginTop: 4 }}>
                <span style={{ fontSize: 11, color: 'var(--t-dim)' }}>Realized Spread PnL</span>
                <span style={{ fontSize: 12, fontWeight: 800, color: (pnlData?.total_realized_pnl_usd ?? 0) >= 0 ? 'var(--t-green)' : 'var(--t-red)' }}>
                  {fmtUsd(pnlData?.total_realized_pnl_usd ?? 0)}
                </span>
              </div>
            </div>
           </div>
        </RightSection>
      }
    />
  );
}
