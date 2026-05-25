import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useSelectedUnderlying, useSetSelectedUnderlying } from '../../store/useStore';
import { useAlgoMode } from '../../hooks/useSignalAlerts';
import {
  useScalpingConfig, useSetScalpingConfig, useScalpingUniverse,
  useScalpingBacktest, useScalpingExecute, useScalpingSignals,
  type ScalpingConfig, type ScalpingSignal, type SupportResistanceLevel,
  type ScalpingExecuteResponse,
} from '../../hooks/useScalping';
import { usePositions } from '../../hooks/usePositions';
import { useLivePnl } from '../../hooks/useLivePnl';
import { useExchanges } from '../../hooks/useExchanges';
import { useStreamPrices } from '../../hooks/useAppStream';
import { ThreeColumnLayout, LeftSection, RightSection, StatCard } from '../ThreeColumnLayout';

/* ── executed-trade tracking ───────────────────────────────────────────────── */

type ExecState = { resp?: ScalpingExecuteResponse; error?: string; auto?: boolean; mode?: string };
type SignalPnl = { value: number | null; realized: boolean; status?: string };

/* ── style tokens ──────────────────────────────────────────────────────────── */

const card: React.CSSProperties = {
  background: 'var(--t-bg2)', border: '1px solid var(--t-border)',
  borderRadius: 10, overflow: 'hidden',
};
const cardHead: React.CSSProperties = {
  padding: '9px 14px', borderBottom: '1px solid var(--t-border)',
  fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--t-bright)',
  display: 'flex', alignItems: 'center', gap: 8,
};
const cardBody: React.CSSProperties = { padding: 14 };
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

function Pill({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', padding: '2px 7px',
      borderRadius: 4, background: color + '22', color, border: `1px solid ${color}44`,
      whiteSpace: 'nowrap',
    }}>{text}</span>
  );
}

function ChipToggle({ label, on, onChange }: { label: string; on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!on)} style={{
      fontSize: 10, fontWeight: 600, padding: '4px 10px', borderRadius: 12, cursor: 'pointer', fontFamily: 'inherit',
      border: `1px solid ${on ? 'var(--t-green)' : 'var(--t-border)'}`,
      background: on ? 'var(--t-green)1c' : 'transparent',
      color: on ? 'var(--t-green)' : 'var(--t-dim)', transition: 'all .1s', whiteSpace: 'nowrap',
    }}>{on ? '● ' : '○ '}{label}</button>
  );
}

const fmt = (v: number | null | undefined, d = 2) => (v == null || !isFinite(v) ? '—' : v.toFixed(d));
const fmtUsd = (v: number | null | undefined) => (v == null || !isFinite(v) ? '—' : '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 }));

const STRATEGY_META: Record<string, { label: string; color: string }> = {
  price_action: { label: 'PRICE ACTION', color: 'var(--t-amber)' },
  smc: { label: 'SMC', color: 'var(--t-purple)' },
  ma_crossover: { label: 'MA CROSS', color: 'var(--t-blue)' },
};

const grpBox: React.CSSProperties = { background: 'var(--t-bg)', border: '1px solid var(--t-border)', borderRadius: 8, padding: 10, display: 'flex', flexDirection: 'column', gap: 8 };
const grpTitle: React.CSSProperties = { fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--t-dim)', marginBottom: 2 };

/* ── config panel (in drawer) ─────────────────────────────────────────────── */

function ScalpingConfigPanel({ cfg, onSave, saving }: { cfg: ScalpingConfig; onSave: (c: ScalpingConfig) => void; saving: boolean }) {
  const [draft, setDraft] = useState<ScalpingConfig>(cfg);
  useEffect(() => { setDraft(cfg); }, [cfg]);
  const set = <K extends keyof ScalpingConfig>(k: K, v: ScalpingConfig[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const dirty = JSON.stringify(draft) !== JSON.stringify(cfg);

  const universeQ = useScalpingUniverse();
  const universe = universeQ.data?.symbols ?? [];
  const allMode = draft.symbols.length === 0;
  const selSet = new Set(draft.symbols);
  const toggleSym = (s: string) => setDraft((d) => {
    const cur = new Set(d.symbols);
    if (cur.has(s)) cur.delete(s); else cur.add(s);
    return { ...d, symbols: [...cur] };
  });

  return (
    <SectionCard title="SCALPING SETTINGS" right={
      <button disabled={!dirty || saving} onClick={() => onSave(draft)} style={{
        fontSize: 9, fontWeight: 700, padding: '4px 14px', borderRadius: 5, fontFamily: 'inherit',
        cursor: dirty && !saving ? 'pointer' : 'default',
        border: `1px solid ${dirty ? 'var(--t-green)' : 'var(--t-border)'}`,
        background: dirty ? 'var(--t-green)22' : 'transparent',
        color: dirty ? 'var(--t-green)' : 'var(--t-dim)',
      }}>{saving ? 'SAVING…' : dirty ? 'APPLY' : 'SAVED'}</button>
    }>
      <div style={{ ...dim, marginBottom: 12, lineHeight: 1.5 }}>
        4H structure + 15min entry — <b style={{ color: 'var(--t-bright)' }}>3 strategies</b>: Price Action, SMC, MA Crossover.
        Only triggers when price is near a key 4H S/R level.
      </div>
      <div style={{ display: 'flex', gap: 5, marginBottom: 12, flexWrap: 'wrap' }}>
        <ChipToggle label="Price Action" on={draft.enable_price_action} onChange={(v) => set('enable_price_action', v)} />
        <ChipToggle label="SMC" on={draft.enable_smc} onChange={(v) => set('enable_smc', v)} />
        <ChipToggle label="MA Crossover" on={draft.enable_ma_crossover} onChange={(v) => set('enable_ma_crossover', v)} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, alignItems: 'start' }}>
        <div style={grpBox}>
          <div style={grpTitle}>4H LEVELS</div>
          <NumField label="Min touches" value={draft.level_touches} min={2} max={10} onChange={(v) => set('level_touches', v)} />
          <NumField label="Tolerance %" value={draft.level_tolerance_pct} step={0.1} min={0.1} max={3} onChange={(v) => set('level_tolerance_pct', v)} />
        </div>
        <div style={grpBox}>
          <div style={grpTitle}>PRICE ACTION</div>
          <NumField label="Lookback" value={draft.pa_lookback} min={5} max={100} onChange={(v) => set('pa_lookback', v)} />
          <NumField label="Breakout %" value={draft.pa_breakout_pct} step={0.01} min={0.01} max={1} onChange={(v) => set('pa_breakout_pct', v)} />
        </div>
        <div style={grpBox}>
          <div style={grpTitle}>SMC</div>
          <NumField label="Imbalance ratio" value={draft.smc_imbalance_ratio} step={0.1} min={1.0} max={3.0} onChange={(v) => set('smc_imbalance_ratio', v)} />
        </div>
        <div style={grpBox}>
          <div style={grpTitle}>MA CROSSOVER</div>
          <NumField label="SMA period" value={draft.ma_fast_period} min={2} max={20} onChange={(v) => set('ma_fast_period', v)} />
          <NumField label="EMA period" value={draft.ma_slow_period} min={3} max={50} onChange={(v) => set('ma_slow_period', v)} />
        </div>
        <div style={grpBox}>
          <div style={grpTitle}>DIRECTION & RISK</div>
          <div style={{ display: 'flex', gap: 5 }}>
            <ChipToggle label="Long" on={draft.allow_long} onChange={(v) => set('allow_long', v)} />
            <ChipToggle label="Short" on={draft.allow_short} onChange={(v) => set('allow_short', v)} />
          </div>
          <NumField label="Risk % / trade" value={draft.risk_percent} step={0.05} min={0.05} max={5} onChange={(v) => set('risk_percent', v)} />
          <NumField label="Max position %" value={draft.max_position_pct} step={1} min={1} max={100} onChange={(v) => set('max_position_pct', v)} />
          <NumField label="Equity $" value={draft.account_equity} step={1000} min={100} onChange={(v) => set('account_equity', v)} />
        </div>
        <div style={{ ...grpBox, gridColumn: '1 / -1' }}>
          <div style={grpTitle}>SYMBOLS</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
            <button onClick={() => set('symbols', [] as string[])} style={{
              fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit',
              border: `1px solid ${allMode ? 'var(--t-blue)' : 'var(--t-border)'}`,
              background: allMode ? 'var(--t-bg3)' : 'transparent',
              color: allMode ? 'var(--t-blue)' : 'var(--t-dim)',
            }}>ALL</button>
            <span style={{ fontSize: 9, color: 'var(--t-dim)' }}>
              {allMode ? `all ${universe.length}` : `${draft.symbols.length} selected`}
            </span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, maxHeight: 100, overflow: 'auto' }}>
            {universe.map((s) => {
              const on = !allMode && selSet.has(s);
              return (
                <button key={s} onClick={() => toggleSym(s)} style={{
                  fontSize: 9, fontWeight: 600, padding: '2px 6px', borderRadius: 5, cursor: 'pointer', fontFamily: 'inherit',
                  border: `1px solid ${on ? 'var(--t-green)' : 'var(--t-border)'}`,
                  background: on ? 'var(--t-green)1c' : 'transparent',
                  color: on ? 'var(--t-green)' : 'var(--t-dim)',
                }}>{s}</button>
              );
            })}
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

/* ── signal card ────────────────────────────────────────────────────────────── */

function PlanCell({ label, value, color, width = 78 }: { label: string; value: string; color?: string; width?: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1, width, flexShrink: 0 }}>
      <span style={{ fontSize: 8, letterSpacing: '0.08em', color: 'var(--t-dim)', fontWeight: 600, textTransform: 'uppercase' }}>{label}</span>
      <span style={{
        fontSize: 13, fontWeight: 700, color: color || 'var(--t-bright)', lineHeight: 1.2,
        fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>{value}</span>
    </div>
  );
}

/* ── executed-trade detail (friendly summary + metrics) ────────────────────── */

const fmtTime = (ms?: number) =>
  ms ? new Date(ms).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '—';

// Backend status codes → plain-English explanations.
const EXEC_STATUS_FRIENDLY: Record<string, string> = {
  no_signal: 'No armed signal for this strategy at execution time.',
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

function MetricItem({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 60 }}>
      <span style={{ fontSize: 8, letterSpacing: '0.07em', color: 'var(--t-dim)', fontWeight: 600, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ fontSize: 11, fontWeight: 700, color: color || 'var(--t-bright)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{value}</span>
    </div>
  );
}

function ExecDetail({ execState, pnl }: { execState: ExecState; pnl?: SignalPnl & { currentSpot?: number | null } }) {
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
  const posStatus = pnl?.realized ? 'Closed' : pnl?.status ? pnl.status.replace(/_/g, ' ') : (accepted ? 'Open' : '—');

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
      {what && <span style={{ fontSize: 10, color: 'var(--t-dim)', lineHeight: 1.5, wordBreak: 'break-word' }}>{what}</span>}

      {/* copyable server IP for ip_not_whitelisted errors */}
      {serverIp && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <code style={{ fontSize: 12, fontWeight: 800, color: 'var(--t-bright)', letterSpacing: 0.5, background: 'var(--t-bg3)', padding: '2px 8px', borderRadius: 4, fontFamily: 'monospace' }}>{serverIp}</code>
          <button
            onClick={() => navigator.clipboard.writeText(serverIp)}
            style={{ fontSize: 9, fontWeight: 700, color: 'var(--t-blue)', background: 'var(--t-blue)14', border: '1px solid var(--t-blue)44', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontFamily: 'inherit' }}
          >Copy IP</button>
        </div>
      )}

      {/* metrics — shown once an order actually went through */}
      {accepted && r && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 18px', paddingTop: 1 }}>
          <MetricItem label="Direction" value={r.direction ? r.direction.toUpperCase() : '—'} color={r.direction === 'long' ? 'var(--t-green)' : 'var(--t-red)'} />
          <MetricItem label="Qty" value={r.size_units ? fmt(r.size_units, 4) : '—'} />
          <MetricItem label="Entry" value={fmtUsd(r.entry_price)} />
          {pnl?.currentSpot != null && (
            <MetricItem label="Mark" value={fmtUsd(pnl.currentSpot)} color={pnl.currentSpot > (r.entry_price ?? 0) ? 'var(--t-green)' : 'var(--t-red)'} />
          )}
          <MetricItem label="Stop" value={fmtUsd(r.stop_loss)} color="#f87171" />
          <MetricItem label="Target" value={fmtUsd(r.take_profit)} color="#fbbf24" />
          <MetricItem label="Notional" value={fmtUsd(r.notional_usd)} />
          <MetricItem
            label={pnl?.realized ? 'Realized P&L' : 'Open P&L'}
            value={pnlVal == null ? '—' : `${pnlVal >= 0 ? '+' : '−'}${fmtUsd(Math.abs(pnlVal))}`}
            color={pnlColor}
          />
          <MetricItem label="Status" value={posStatus} color={pnl?.realized ? 'var(--t-dim)' : 'var(--t-green)'} />
          <MetricItem label="Mode" value={mode} color="var(--t-blue)" />
        </div>
      )}
    </div>
  );
}

function ScalpSignalCard({ s, selected, onSelect, onExecute, executing, execState, pnl, algoOn, mode }: {
  s: ScalpingSignal; selected: boolean; onSelect: () => void; onExecute: () => void;
  executing: boolean; execState?: ExecState; pnl?: SignalPnl; algoOn?: boolean; mode?: string;
}) {
  const long = s.direction === 'long';
  const isWatch = s.entry_ok && !s.executable;
  const meta = STRATEGY_META[s.strategy] || { label: s.strategy.toUpperCase(), color: 'var(--t-dim)' };
  const dirColor = long ? 'var(--t-green)' : 'var(--t-red)';

  const resp = execState?.resp;
  const accepted = !!resp?.accepted;
  const tried = !!execState && !accepted;  // attempted but rejected or errored

  // Configured mode this trade ran in (PAPER / SHADOW / LIVE) — recorded at exec
  // time, else the currently-configured mode for the pending pill. Color-coded by risk.
  const pillMode = execState?.mode || mode || 'PAPER';
  const modeColor = modeColorOf(pillMode);

  const statusLabel = accepted ? 'EXECUTED' : s.executable ? 'ARMED' : isWatch ? 'WATCH' : 'PENDING';
  const statusColor = accepted ? 'var(--t-blue)' : s.executable ? dirColor : isWatch ? 'var(--t-blue)' : 'var(--t-dim)';

  // Signal's own setup reason — shown only until an execution attempt replaces it
  // with the richer ExecDetail block below.
  const metaReason = s.entry != null ? s.reason : null;

  const pnlVal = pnl?.value ?? null;
  const pnlColor = pnlVal == null ? 'var(--t-dim)' : pnlVal >= 0 ? 'var(--t-green)' : 'var(--t-red)';

  return (
    <div onClick={onSelect} style={{
      display: 'flex', flexDirection: 'column', gap: 7,
      padding: '12px 16px 12px 0', borderRadius: 10, cursor: 'pointer',
      border: `1px solid ${selected ? statusColor + '55' : 'var(--t-border)'}`,
      background: selected ? statusColor + '0a' : 'var(--t-bg2)',
      transition: 'border-color .12s, background .12s',
    }}>
      {/* ── main row: fixed-width columns keep values aligned across cards ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{ width: 4, alignSelf: 'stretch', minHeight: 34, borderRadius: 3, background: meta.color, flexShrink: 0 }} />
        <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--t-bright)', letterSpacing: '0.02em', width: 56, flexShrink: 0 }}>{s.underlying}</span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, width: 68, flexShrink: 0 }}>
          <span style={{ fontSize: 12, fontWeight: 800, color: dirColor, letterSpacing: '0.04em', lineHeight: 1.1 }}>
            {long ? '▲ LONG' : '▼ SHORT'}
          </span>
          <span style={{
            fontSize: 8, fontWeight: 700, letterSpacing: '0.08em', color: statusColor, lineHeight: 1,
            padding: '1px 5px', borderRadius: 3, background: statusColor + '18', alignSelf: 'flex-start',
          }}>{statusLabel}</span>
        </div>
        {s.entry != null ? (
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0 }}>
            <PlanCell label="Entry" value={fmtUsd(s.entry)} />
            <PlanCell label="Stop" value={fmtUsd(s.stop_loss)} color="#f87171" />
            <PlanCell label="Target" value={fmtUsd(s.take_profit)} color="#fbbf24" />
            <PlanCell label="Risk" value={s.risk_pct != null ? `${fmt(s.risk_pct)}%` : '—'} width={50} />
          </div>
        ) : (
          <span style={{ fontSize: 11, color: 'var(--t-dim)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.reason}</span>
        )}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0, marginLeft: s.entry != null ? 0 : 'auto' }}>
          <Pill text={meta.label} color={meta.color} />
          {s.pattern && (
            <span style={{ fontSize: 9, fontWeight: 600, color: meta.color, whiteSpace: 'nowrap', maxWidth: 96, overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {s.pattern.replace(/_/g, ' ')}
            </span>
          )}
        </div>
        {/* ── action / executed state ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, marginLeft: 'auto' }}>
          {accepted ? (
            <>
              <span style={{
                fontSize: 9, fontWeight: 800, letterSpacing: '0.06em', color: modeColor,
                padding: '4px 9px', borderRadius: 6, background: modeColor + '18',
                border: `1px solid ${modeColor}44`, whiteSpace: 'nowrap',
              }}>✓ {execState?.auto ? 'AUTO · ' : ''}{pillMode}</span>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', lineHeight: 1.1, minWidth: 56 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: pnlColor, fontVariantNumeric: 'tabular-nums' }}>
                  {pnlVal == null ? '—' : `${pnlVal >= 0 ? '+' : '−'}${fmtUsd(Math.abs(pnlVal))}`}
                </span>
                <span style={{ fontSize: 8, color: 'var(--t-dim)', letterSpacing: '0.06em' }}>
                  {pnl?.realized ? 'REALIZED' : 'OPEN P&L'}
                </span>
              </div>
            </>
          ) : s.executable && algoOn ? (
            // Algo handles execution — manual button is locked out. Pill shows the mode it runs in.
            <span title={`Algo is ON — auto-executes in ${pillMode} mode`} style={{
              fontSize: 9, fontWeight: 800, letterSpacing: '0.06em', color: modeColor,
              padding: '5px 12px', borderRadius: 6, background: modeColor + '14',
              border: `1px solid ${modeColor}44`, whiteSpace: 'nowrap',
              opacity: tried ? 0.7 : 1,
            }}>⚡ {executing ? 'AUTO…' : `AUTO · ${pillMode}`}</span>
          ) : s.executable ? (
            <button disabled={executing} onClick={(e) => { e.stopPropagation(); onExecute(); }} style={{
              fontSize: 10, fontWeight: 800, letterSpacing: '0.06em', padding: '6px 16px', borderRadius: 6,
              fontFamily: 'inherit', cursor: executing ? 'default' : 'pointer',
              color: '#fff', background: tried ? 'var(--t-amber)' : dirColor, border: 'none', lineHeight: 1,
              opacity: executing ? 0.6 : 1,
            }}>
              {executing ? '…' : tried ? 'RETRY' : 'EXECUTE'}
            </button>
          ) : null}
        </div>
      </div>

      {/* ── detail row: failure note · auto-queued hint · setup reason ──
           (full metrics for accepted trades live in the Executed Trades panel) */}
      {execState && !accepted ? (
        <div style={{ paddingLeft: 18, fontSize: 10, lineHeight: 1.5, color: 'var(--t-amber)', fontWeight: 600, wordBreak: 'break-word' }}>
          {execState.error
            ? `✕ ${friendlyError(execState.error)}`
            : `✕ ${pillMode} — ${EXEC_STATUS_FRIENDLY[execState.resp!.status] ?? friendlyError(execState.resp!.reason || execState.resp!.status)}`}
        </div>
      ) : !execState && algoOn && s.executable ? (
        <div style={{ paddingLeft: 18, fontSize: 10, lineHeight: 1.5, color: 'var(--t-green)', wordBreak: 'break-word' }}>
          ⏳ Armed — queued for auto-execution…
        </div>
      ) : metaReason ? (
        <div style={{ paddingLeft: 18, fontSize: 10, lineHeight: 1.5, color: 'var(--t-dim)', wordBreak: 'break-word' }}>
          {metaReason}
        </div>
      ) : null}
    </div>
  );
}

/* ── executed trades panel — persistent log with full metrics + live P&L ───── */

type ExecEntry = { key: string; sym: string; strategy: string; es: ExecState; pnl?: SignalPnl };

const modeOfEntry = (e: ExecEntry) => (e.es.mode || e.es.resp?.mode || 'PAPER').toUpperCase();

function ExecutedRow({ e }: { e: ExecEntry }) {
  const m = STRATEGY_META[e.strategy] || { label: e.strategy.toUpperCase(), color: 'var(--t-dim)' };
  const dir = e.es.resp?.direction;
  return (
    <div style={{ border: '1px solid var(--t-border)', borderRadius: 8, overflow: 'hidden', background: 'var(--t-bg2)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 12px' }}>
        <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--t-bright)' }}>{e.sym}</span>
        <Pill text={m.label} color={m.color} />
        {dir && <span style={{ fontSize: 11, fontWeight: 800, color: dir === 'long' ? 'var(--t-green)' : 'var(--t-red)' }}>{dir === 'long' ? '▲ LONG' : '▼ SHORT'}</span>}
      </div>
      <ExecDetail execState={e.es} pnl={e.pnl} />
    </div>
  );
}

function ExecutedTradesPanel({ entries, currentMode }: { entries: ExecEntry[]; currentMode: string }) {
  if (!entries.length) return null;

  const filtered = entries.filter((e) => {
    const m = (e.es.mode || e.es.resp?.mode || 'PAPER').toUpperCase();
    return m === currentMode || !currentMode;
  });
  if (!filtered.length) return null;

  const sortItems = (items: ExecEntry[]) => [...items].sort((a, b) => {
    const av = a.es.resp?.accepted ? 0 : 1, bv = b.es.resp?.accepted ? 0 : 1;
    if (av !== bv) return av - bv;
    return (b.es.resp?.timestamp_ms ?? 0) - (a.es.resp?.timestamp_ms ?? 0);
  });

  const sorted = sortItems(filtered);

  return (
    <div style={card}>
      <div style={cardHead}>
        <span>EXECUTED TRADES</span>
        <span style={{ marginLeft: 'auto', fontSize: 9, color: 'var(--t-dim)' }}>{sorted.length}</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 12 }}>
        {sorted.map((e) => <ExecutedRow key={e.key} e={e} />)}
      </div>
    </div>
  );
}

/* ── 4H levels — grouped by symbol, per-symbol expand/collapse ─────────────── */

function SymbolLevelGroup({ sym, levels }: { sym: string; levels: SupportResistanceLevel[] }) {
  const [open, setOpen] = useState(false);
  const supports = levels.filter((l) => l.level_type === 'support').length;
  const resist = levels.length - supports;
  return (
    <div style={{ border: '1px solid var(--t-border)', borderRadius: 6, overflow: 'hidden', background: 'var(--t-bg)' }}>
      <button onClick={() => setOpen((o) => !o)} style={{
        display: 'flex', alignItems: 'center', gap: 6, width: '100%', padding: '5px 8px',
        background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
      }}>
        <span style={{
          fontSize: 8, color: 'var(--t-dim)', width: 8, lineHeight: 1,
          transition: 'transform .12s', transform: open ? 'none' : 'rotate(-90deg)',
        }}>▼</span>
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--t-bright)' }}>{sym}</span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 5, fontSize: 9 }}>
          {supports > 0 && <span style={{ color: 'var(--t-green)' }}>▲{supports}</span>}
          {resist > 0 && <span style={{ color: 'var(--t-red)' }}>▼{resist}</span>}
        </span>
      </button>
      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, padding: '2px 8px 7px 22px' }}>
          {levels.map((l, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10 }}>
              <span style={{ fontSize: 9, color: l.level_type === 'support' ? 'var(--t-green)' : 'var(--t-red)', fontWeight: 700 }}>
                {l.level_type === 'support' ? '▲' : '▼'}
              </span>
              <span style={{ fontWeight: 700, color: 'var(--t-bright)', fontVariantNumeric: 'tabular-nums' }}>{fmtUsd(l.price)}</span>
              <span style={{ color: 'var(--t-dim)', fontSize: 9 }}>×{l.touches}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function GroupedLevels({ levels }: { levels: SupportResistanceLevel[] }) {
  const groups = useMemo(() => {
    const m = new Map<string, SupportResistanceLevel[]>();
    for (const l of levels) {
      const k = l.underlying || '—';
      const arr = m.get(k);
      if (arr) arr.push(l); else m.set(k, [l]);
    }
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [levels]);

  if (groups.length === 0) return <div style={{ ...dim, fontSize: 10 }}>No levels found</div>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {groups.map(([sym, lvls]) => <SymbolLevelGroup key={sym} sym={sym} levels={lvls} />)}
    </div>
  );
}

/* ── backtest panel ─────────────────────────────────────────────────────────── */

const LOOKBACK_PRESETS_BT: [string, number][] = [['1M', 30], ['3M', 90], ['6M', 180]];

function ScalpBacktestPanel({ underlying }: { underlying: string }) {
  const [lookback, setLookback] = useState(90);
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
        <button disabled={bt.isPending} onClick={() => bt.mutate({ underlying, lookback_days: lookback })} style={{
          fontSize: 9, fontWeight: 700, padding: '3px 10px', borderRadius: 5, fontFamily: 'inherit', cursor: 'pointer',
          border: '1px solid var(--t-blue)', background: 'var(--t-bg3)', color: 'var(--t-blue)',
        }}>{bt.isPending ? 'RUNNING…' : 'RUN'}</button>
      </span>
    }>
      {bt.isError && <div style={{ color: 'var(--t-red)', fontSize: 10 }}>{bt.error.message}</div>}
      {!res && !bt.isPending && <div style={dim}>Run a backtest — 4H structure + 15min entry replay.</div>}
      {res && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
            <Stat label="TRADES" value={String(res.total_trades)} />
            <Stat label="WIN RATE" value={`${fmt(res.win_rate * 100, 0)}%`} color={res.win_rate >= 0.5 ? 'var(--t-green)' : 'var(--t-red)'} />
            <Stat label="RETURN" value={`${fmt(res.total_return_pct, 1)}%`} color={res.total_return_pct >= 0 ? 'var(--t-green)' : 'var(--t-red)'} />
            <Stat label="MAX DD" value={`${fmt(res.max_drawdown_pct, 1)}%`} color="var(--t-amber)" />
          </div>
          {res.trades.length > 0 && (
            <div style={{ maxHeight: 140, overflow: 'auto', border: '1px solid var(--t-border)', borderRadius: 6 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10 }}>
                <thead>
                  <tr style={{ color: 'var(--t-dim)', textAlign: 'left' }}>
                    {['Strat', 'Dir', 'Entry', 'Exit', 'R', 'Exit'].map((h) => (
                      <th key={h} style={{ padding: '3px 6px', position: 'sticky', top: 0, background: 'var(--t-bg2)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {res.trades.slice(-30).reverse().map((t, i) => (
                    <tr key={i} style={{ borderTop: '1px solid var(--t-border)' }}>
                      <td style={{ padding: '2px 6px' }}><Pill text={t.strategy.replace('_', ' ').toUpperCase()} color={STRATEGY_META[t.strategy]?.color || 'var(--t-dim)'} /></td>
                      <td style={{ padding: '2px 6px', color: t.direction === 'long' ? 'var(--t-green)' : 'var(--t-red)' }}>{t.direction === 'long' ? 'L' : 'S'}</td>
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
      )}
    </SectionCard>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: 8, letterSpacing: '0.08em', color: 'var(--t-dim)', fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 700, color: color || 'var(--t-bright)' }}>{value}</div>
    </div>
  );
}

/* ── main tab: 3-column layout ─────────────────────────────────────────────── */

export function ScalpingTab() {
  const selected = useSelectedUnderlying();
  const setSelected = useSetSelectedUnderlying();
  const cfgQ = useScalpingConfig();
  const setCfg = useSetScalpingConfig();
  const [drawer, setDrawer] = useState(false);
  const [stratFilter, setStratFilter] = useState<string>(() => localStorage.getItem('scalp.stratFilter') || 'all');
  const [armedOnly, setArmedOnly] = useState(() => localStorage.getItem('scalp.armedOnly') === '1');
  const [activeStat, setActiveStat] = useState<string>(() => (localStorage.getItem('scalp.armedOnly') === '1' ? 'armed' : 'scanned'));
  const scanQ = useScalpingSignals(armedOnly);
  const exec = useScalpingExecute();
  const [execKeys, setExecKeys] = useState<Set<string>>(new Set());  // in-flight (supports concurrent auto-exec)
  const [execStates, setExecStates] = useState<Record<string, ExecState>>({});
  const cfg = cfgQ.data?.config;
  const algoOn = useAlgoMode().data?.enabled ?? false;
  const autoExecRef = useRef<Set<string>>(new Set());   // auto-attempted this algo session
  const acceptedRef = useRef<Set<string>>(new Set());   // ever accepted — never re-execute

  // Current configured trading mode (drives AUTO · PAPER / LIVE labels). Mirrors PaperLiveToggle:
  //   is_paper → PAPER · !is_paper → LIVE.
  const exQ = useExchanges();
  const delta = exQ.data?.exchanges.find((e) => e.name === 'delta_india' && e.is_active);
  const tradeMode = delta?.is_paper ? 'PAPER' : 'LIVE';

  // Positions + live P&L feed the executed-trade rows (paper and live alike).
  const positions = usePositions().data?.positions ?? [];
  const livePnl = useLivePnl().data?.positions ?? [];
  const streamPrices = useStreamPrices();
  const pnlByPos = useMemo(() => new Map(livePnl.map((p) => [p.position_id, p])), [livePnl]);

  const pnlFor = (r: ScalpingExecuteResponse): SignalPnl & { currentSpot?: number | null } => {
    let pos = r.paper_position_id ? positions.find((p) => p.id === r.paper_position_id) : undefined;
    if (!pos && r.order_id) pos = positions.find((p) => p.order_id === r.order_id);
    if (!pos) return { value: null, realized: false };
    const realized = pos.status === 'closed';
    const live = pnlByPos.get(pos.id);
    const value = realized
      ? (pos.realized_pnl_usd ?? live?.realized_pnl_usd ?? null)
      : (live?.estimated_pnl_usd ?? null);
    return { value, realized, status: pos.status, currentSpot: live?.current_spot ?? null };
  };

  // mutateAsync (not mutate) is essential here: the auto-exec loop fires several
  // executions on one shared mutation observer, and mutate()'s per-call callbacks
  // only fire for the LAST call — leaving the rest stuck "queued". The promise
  // returned by mutateAsync resolves independently for each call.
  const onExecute = (sym: string, strategy: string, auto = false) => {
    const key = `${sym}-${strategy}`;
    setExecKeys((s) => new Set(s).add(key));
    exec.mutateAsync({ underlying: sym, strategy })
      .then((r) => { setExecStates((m) => ({ ...m, [key]: { resp: r, auto, mode: tradeMode } })); if (r.accepted) acceptedRef.current.add(key); })
      .catch((e: Error) => { setExecStates((m) => ({ ...m, [key]: { error: e.message, auto, mode: tradeMode } })); })
      .finally(() => { setExecKeys((s) => { const n = new Set(s); n.delete(key); return n; }); });
  };

  const data = scanQ.data;
  let signals = data?.signals ?? [];
  if (stratFilter !== 'all') {
    signals = signals.filter((s) => s.strategy === stratFilter);
  }
  const armed = signals.filter((s) => s.entry_ok).length;
  const levels = data?.levels ?? [];

  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setDrawer(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawer]);

  // Persist sidebar selections (Armed-only filter + active strategy nav) across reloads.
  useEffect(() => { localStorage.setItem('scalp.stratFilter', stratFilter); }, [stratFilter]);
  useEffect(() => { localStorage.setItem('scalp.armedOnly', armedOnly ? '1' : '0'); }, [armedOnly]);

  // Algo auto-execution: while Algo is ON, every executable signal is fired
  // automatically. The /scalping/execute endpoint routes through the active
  // Paper/Live mode, so this trades paper or live depending on that toggle.
  // De-duped per symbol+strategy so the 30s rescan never re-fires the same setup.
  // Re-fires on tradeMode change so signals re-execute after a mode switch.
  useEffect(() => {
    if (!algoOn) return;
    for (const s of data?.signals ?? []) {
      if (!s.executable) continue;
      const key = `${s.underlying}-${s.strategy}`;
      if (acceptedRef.current.has(key)) continue;  // never re-execute a filled trade
      if (autoExecRef.current.has(key)) continue;  // already attempted this session
      autoExecRef.current.add(key);
      onExecute(s.underlying, s.strategy, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [algoOn, data, tradeMode]);

  // Forget de-dupe keys once Algo is switched off, so re-enabling starts fresh.
  useEffect(() => { if (!algoOn) autoExecRef.current.clear(); }, [algoOn]);

  // When trading mode changes, clear executions from the old mode so stale
  // PAPER exec states don't persist as "EXECUTED" after switching to LIVE (or vice versa).
  // Also clear autoExecRef so the algo loop re-fires signals in the new mode.
  useEffect(() => {
    setExecStates((prev) => {
      const filtered = Object.fromEntries(
        Object.entries(prev).filter(([, es]) => (es.mode || 'PAPER') === tradeMode),
      );
      return Object.keys(filtered).length === Object.keys(prev).length ? prev : filtered;
    });
    acceptedRef.current.clear();
    autoExecRef.current.clear();
  }, [tradeMode]);

  const allSignals = data?.signals ?? [];
  const longs = signals.filter((s) => s.direction === 'long');
  const shorts = signals.filter((s) => s.direction === 'short');
  const enabledStrategies = cfgQ.data?.config ? [cfgQ.data.config.enable_price_action, cfgQ.data.config.enable_smc, cfgQ.data.config.enable_ma_crossover].filter(Boolean).length : 0;

  const navItems = [
    { id: 'all', label: 'All Strategies', color: 'var(--t-bright)', count: allSignals.length },
    { id: 'price_action', label: 'Price Action', color: 'var(--t-amber)', count: allSignals.filter((s) => s.strategy === 'price_action').length },
    { id: 'smc', label: 'Smart Money', color: 'var(--t-purple)', count: allSignals.filter((s) => s.strategy === 'smc').length },
    { id: 'ma_crossover', label: 'MA Crossover', color: 'var(--t-blue)', count: allSignals.filter((s) => s.strategy === 'ma_crossover').length },
  ];

  const btUnderlying = (selected?.split('-')[0]) || cfg?.symbols?.[0] || 'BTC';

  // Every execution this session — rendered in the persistent Executed Trades
  // panel so metrics + live P&L stay visible even after a setup leaves the scan.
  const executedEntries: ExecEntry[] = Object.entries(execStates).map(([key, es]) => {
    const dash = key.indexOf('-');
    return {
      key,
      sym: key.slice(0, dash),
      strategy: key.slice(dash + 1),
      es,
      pnl: es.resp?.accepted ? pnlFor(es.resp) : undefined,
    };
  });

  return (
    <>
    <ThreeColumnLayout
      leftNav={navItems}
      activeNav={stratFilter}
      onNavClick={setStratFilter}
      leftSidebar={<>
        <LeftSection label="Filter" collapsible defaultOpen>
          <button onClick={() => { const v = !armedOnly; setArmedOnly(v); setActiveStat(v ? 'armed' : 'scanned'); }} style={{
            display: 'flex', alignItems: 'center', gap: 8, width: '100%',
            padding: '7px 10px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
            border: `1px solid ${armedOnly ? 'var(--t-green)44' : 'var(--t-border)'}`,
            background: armedOnly ? 'var(--t-green)16' : 'transparent',
            color: armedOnly ? 'var(--t-green)' : 'var(--t-dim)', transition: 'all .1s',
          }}>
            <span style={{ fontSize: 12 }}>{armedOnly ? '●' : '○'}</span>
            <span style={{ fontSize: 11, fontWeight: 600 }}>Armed only</span>
          </button>
        </LeftSection>
        <LeftSection label="4H Key Levels" border={false} collapsible defaultOpen={false}>
          <GroupedLevels levels={levels} />
        </LeftSection>
      </>}
      centerHeader={<>
        <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Scalping</div>
        <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 1 }}>
          4H structure · 15min entry · {scanQ.isFetching ? 'scanning…' : 'auto-refresh'}
        </div>
        {algoOn && (
          <span style={{
            marginLeft: 'auto', fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
            padding: '3px 9px', borderRadius: 5, whiteSpace: 'nowrap',
            background: 'var(--t-green)1c', color: 'var(--t-green)', border: '1px solid var(--t-green)44',
          }}>⚡ ALGO AUTO-EXEC</span>
        )}
      </>}
      centerContent={<>
        {scanQ.isError && <div style={{ color: 'var(--t-red)', fontSize: 11 }}>{(scanQ.error as Error).message}</div>}
        {scanQ.isLoading && <div style={{ ...dim, padding: '40px 0', textAlign: 'center' }}>scanning…</div>}
        <ExecutedTradesPanel entries={executedEntries} currentMode={tradeMode} />
        {data && signals.length === 0 && (
          <div style={{ ...dim, padding: '40px 0', textAlign: 'center' }}>
            {armedOnly ? 'No armed signals — clear the filter to see all.' : 'No signals on this data source.'}
          </div>
        )}
        {signals.map((s) => {
          const key = `${s.underlying}-${s.strategy}`;
          const es = execStates[key];
          return (
            <ScalpSignalCard
              key={key} s={s}
              selected={selected === key}
              onSelect={() => setSelected(key)}
              onExecute={() => onExecute(s.underlying, s.strategy)}
              executing={execKeys.has(key)}
              execState={es}
              pnl={es?.resp?.accepted ? pnlFor(es.resp) : undefined}
              algoOn={algoOn}
              mode={tradeMode}
            />
          );
        })}
        {data && signals.length > 0 && (
          <div style={{ fontSize: 10, color: 'var(--t-dim)', lineHeight: 1.5, paddingTop: 4 }}>
            <b style={{ color: 'var(--t-amber)' }}>PA</b> pattern breakout · <b style={{ color: 'var(--t-purple)' }}>SMC</b> inducement + imbalance · <b style={{ color: 'var(--t-blue)' }}>MA</b> SMA/EMA cross · EXECUTE routes through Paper/Live mode
          </div>
        )}
      </>}
      rightSidebar={<>
        <RightSection label="Settings" collapsible defaultOpen={false}>
          <button onClick={() => setDrawer(true)} style={{
            display: 'flex', alignItems: 'center', gap: 8, width: '100%',
            padding: '7px 10px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
            border: '1px solid var(--t-border)', background: 'transparent',
            color: 'var(--t-dim)', transition: 'all .1s',
          }}>
            <span style={{ fontSize: 13 }}>⚙</span>
            <span style={{ fontSize: 11, fontWeight: 600 }}>Settings & Backtest</span>
          </button>
        </RightSection>
        <RightSection label="Summary" collapsible>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            <StatCard
              label="ARMED" value={armed} color={armed > 0 ? 'var(--t-green)' : undefined}
              active={activeStat === 'armed'}
              onClick={() => { setActiveStat('armed'); setArmedOnly(true); }}
            />
            <StatCard
              label="SCANNED" value={signals.length}
              active={activeStat === 'scanned'}
              onClick={() => { setActiveStat('scanned'); setArmedOnly(false); }}
            />
            <StatCard
              label="LEVELS" value={levels.length}
              active={activeStat === 'levels'}
              onClick={() => setActiveStat('levels')}
            />
            <StatCard
              label="STRATEGIES" value={enabledStrategies || '—'}
              active={activeStat === 'strategies'}
              onClick={() => { setActiveStat('strategies'); setDrawer(true); }}
            />
          </div>
        </RightSection>
        <RightSection label="By Strategy" collapsible>
          {Object.entries(STRATEGY_META).map(([key, meta]) => {
            const count = allSignals.filter((s) => s.strategy === key).length;
            const armedHere = allSignals.filter((s) => s.strategy === key && s.entry_ok).length;
            return (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--t-border)' }}>
                <div style={{ width: 6, height: 6, borderRadius: 3, background: meta.color, flexShrink: 0 }} />
                <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--t-bright)', flex: 1 }}>{meta.label}</span>
                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-bright)' }}>{count}</span>
                <span style={{ fontSize: 9, color: 'var(--t-green)' }}>{armedHere > 0 ? `${armedHere} armed` : ''}</span>
              </div>
            );
          })}
        </RightSection>
        <RightSection label="Direction Breakdown" border={false} collapsible>
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ background: 'var(--t-bg)', border: '1px solid var(--t-border)', borderRadius: 6, padding: '8px 10px', flex: 1 }}>
              <div style={{ fontSize: 9, color: 'var(--t-green)', fontWeight: 600 }}>▲ LONG</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--t-green)' }}>{longs.length}</div>
            </div>
            <div style={{ background: 'var(--t-bg)', border: '1px solid var(--t-border)', borderRadius: 6, padding: '8px 10px', flex: 1 }}>
              <div style={{ fontSize: 9, color: 'var(--t-red)', fontWeight: 600 }}>▼ SHORT</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--t-red)' }}>{shorts.length}</div>
            </div>
          </div>
        </RightSection>
      </>}
    >
    </ThreeColumnLayout>

    {drawer && (
      <div onClick={() => setDrawer(false)} style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'flex-end',
      }}>
        <div onClick={(e) => e.stopPropagation()} style={{
          width: 'min(700px, 94vw)', height: '100%', background: 'var(--t-bg)',
          borderLeft: '1px solid var(--t-border)', overflow: 'auto', padding: 16,
          display: 'flex', flexDirection: 'column', gap: 12,
          boxShadow: '-8px 0 32px rgba(0,0,0,0.45)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Settings &amp; Backtest</span>
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
          <ScalpBacktestPanel underlying={btUnderlying} />
        </div>
      </div>
    )}
    </>
  );
}

export default ScalpingTab;