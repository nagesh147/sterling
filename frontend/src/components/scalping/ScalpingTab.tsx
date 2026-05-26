import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useSelectedUnderlying, useSetSelectedUnderlying } from '../../store/useStore';
import { useAlgoMode } from '../../hooks/useSignalAlerts';
import {
  useScalpingConfig, useSetScalpingConfig, useScalpingUniverse,
  useScalpingBacktest, useScalpingExecute, useScalpingSignals,
  type ScalpingConfig, type ScalpingSignal,
  type ScalpingExecuteResponse,
} from '../../hooks/useScalping';
import { usePositions } from '../../hooks/usePositions';
import { useLivePnl } from '../../hooks/useLivePnl';
import type { PaperPosition } from '../../types';
import { useRouterMode, RouterMode } from '../../hooks/useRouterMode';
import { useTradingMode } from '../../hooks/useTradingMode';
import { useExchanges, useUpdateExchange } from '../../hooks/useExchanges';
import { useStreamPrices } from '../../hooks/useAppStream';
import { ThreeColumnLayout, LeftSection, RightSection } from '../ThreeColumnLayout';
import { card, cardHead, cardBody, grpBox, grpTitle, chipStyle, gridStyle, tint } from '../../styles/terminalUI';

/* ── executed-trade tracking ───────────────────────────────────────────────── */

type ExecState = { resp?: ScalpingExecuteResponse; error?: string; auto?: boolean; mode?: string };
type SignalPnl = {
    value: number | null; realized: boolean; status?: string;
    currentSpot?: number | null;
    direction?: string; contracts?: number; leverage?: number;
    entryTimeMs?: number | null; entryPriceReal?: number | null;
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
      background: on ? tint('var(--t-green)') : 'transparent',
      color: on ? 'var(--t-green)' : 'var(--t-dim)', transition: 'all .1s', whiteSpace: 'nowrap',
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

const STRATEGY_META: Record<string, { label: string; color: string }> = {
  price_action: { label: 'PRICE ACTION', color: 'var(--t-amber)' },
  smc: { label: 'SMC', color: 'var(--t-purple)' },
  ma_crossover: { label: 'MA CROSS', color: 'var(--t-blue)' },
};


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
      <div style={gridStyle()}>
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
          <div style={{ display: 'flex', gap: 5, marginBottom: 4 }}>
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
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 120, overflow: 'auto', paddingRight: 4 }}>
            {universe.map((s) => {
              const on = !allMode && selSet.has(s);
              return (
                <button key={s} onClick={() => toggleSym(s)} style={chipStyle(on)}>{s}</button>
              );
            })}
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

/* ── signal card ────────────────────────────────────────────────────────────── */

function PlanCell({ value, color, width = 78 }: { value: React.ReactNode; color?: string; width?: number | string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', width, flexShrink: 0, justifyContent: 'center' }}>
      <span style={{
        fontSize: 13, fontWeight: 700, color: color || 'var(--t-bright)', lineHeight: 1.2,
        fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>{value}</span>
    </div>
  );
}

function SignalTableHeader() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 20,
      padding: '4px 16px 6px 0',
      marginBottom: 2,
    }}>
      <div style={{ width: 4, flexShrink: 0 }} />
      <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 56, flexShrink: 0, textTransform: 'uppercase' }}>Symbol</span>
      <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 68, flexShrink: 0, textTransform: 'uppercase' }}>Type</span>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexShrink: 0 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 78, flexShrink: 0, textTransform: 'uppercase' }}>Entry</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 110, flexShrink: 0, textTransform: 'uppercase' }}>Current</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 78, flexShrink: 0, textTransform: 'uppercase' }}>Stop</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 78, flexShrink: 0, textTransform: 'uppercase' }}>Target</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', width: 50, flexShrink: 0, textTransform: 'uppercase' }}>Risk</span>
      </div>
      <div style={{ width: 150, flexShrink: 0, marginLeft: 'auto' }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>Strategy / Mode</span>
      </div>
    </div>
  );
}

/* ── executed-trade detail (friendly summary + metrics) ────────────────────── */

const fmtTime = (ms?: number) =>
  ms ? new Date(ms).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '—';

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
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.78)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
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
      <span style={{ fontSize: 8, letterSpacing: '0.07em', color: 'var(--t-dim)', fontWeight: 600, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ fontSize: 11, fontWeight: 700, color: color || 'var(--t-bright)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{value}</span>
    </div>
  );
}

function ExecDetail({ execState, pnl }: { execState: ExecState; pnl?: SignalPnl }) {
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
          <MetricItem label="Qty" value={r.size_units ? fmt(r.size_units, 4) : '—'} />
          <MetricItem label="Entry" value={fmtUsd(pnl?.entryPriceReal ?? r.entry_price)} />
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
          <MetricItem label="Initial SL" value={fmtUsd(pnl?.initialSl ?? r.stop_loss)} color="#f87171" />
          {pnl?.currentSl != null && pnl.currentSl !== pnl?.initialSl && (
            <MetricItem label="Trail SL" value={fmtUsd(pnl.currentSl)} color="#fb923c" />
          )}
          <MetricItem label="Target" value={fmtUsd(pnl?.initialTp ?? r.take_profit)} color="var(--t-amber)" />
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
          <MetricItem label="Status" value={posStatus} color={pnl?.realized ? 'var(--t-dim)' : 'var(--t-green)'} />
          <MetricItem label="Mode" value={mode} color="var(--t-blue)" />
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
  const c = totalPnl >= 0 ? 'var(--t-green)' : 'var(--t-red)';
  const Stat = ({ label, value, color }: { label: string; value: string; color?: string }) => (
    <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.05 }}>
      <span style={{ fontSize: 12, fontWeight: 800, color: color || 'var(--t-bright)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
      <span style={{ fontSize: 8, color: 'var(--t-dim)', fontWeight: 700, letterSpacing: '0.07em' }}>{label}</span>
    </div>
  );
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 22, flexWrap: 'wrap',
      padding: '10px 16px', borderRadius: 10,
      border: `1px solid ${c}44`, background: `${c}0c`,
    }}>
      <span style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.06em', color: c }}>Σ</span>
      <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.05 }}>
        <span style={{ fontSize: 17, fontWeight: 900, color: c, fontVariantNumeric: 'tabular-nums' }}>{fmtSigned(totalPnl)}</span>
        <span style={{ fontSize: 8, color: 'var(--t-dim)', fontWeight: 700, letterSpacing: '0.07em' }}>TOTAL P&L · {count}</span>
      </div>
      <Stat label="OPEN" value={fmtSigned(openPnl)} color={openPnl >= 0 ? 'var(--t-green)' : 'var(--t-red)'} />
      <Stat label="REALIZED" value={fmtSigned(realizedPnl)} color={realizedPnl >= 0 ? 'var(--t-green)' : 'var(--t-red)'} />
      <Stat label="WIN / LOSS" value={`${wins} / ${losses}`} color={wins >= losses ? 'var(--t-green)' : 'var(--t-red)'} />
    </div>
  );
}

/** Thin labelled divider used to group the signal list into sections. */
function ListGroupHeader({ label, count, color }: { label: string; count?: number; color?: string }) {
  const c = color || 'var(--t-dim)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '2px 2px', marginTop: 2 }}>
      <span style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.14em', color: c, textTransform: 'uppercase' }}>{label}</span>
      {count != null && (
        <span style={{
          fontSize: 9, fontWeight: 700, color: c, background: c + '1c',
          borderRadius: 9, padding: '0 6px', lineHeight: '15px',
        }}>{count}</span>
      )}
      <div style={{ flex: 1, height: 1, background: 'var(--t-border)' }} />
    </div>
  );
}

// Visible execution log — proves whether ready signals are firing in the current
// mode (and, when they don't, why the backend rejected them).
function ExecLog({ entries, mode }: {
  entries: { ts: number; key: string; mode: string; ok: boolean; status: string; reason: string; auto: boolean }[];
  mode: string;
}) {
  if (entries.length === 0) {
    return (
      <div style={{ fontSize: 10, color: 'var(--t-dim)', lineHeight: 1.5, padding: 16 }}>
        No execution attempts this session. With <b style={{ color: 'var(--t-bright)' }}>Algo ON</b>, every ready
        signal fires here and its result (mode · status · reason) is logged — so you can confirm <b style={{ color: 'var(--t-bright)' }}>{mode}</b> is
        actually placing orders, or see exactly why one was rejected.
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16 }}>
      {entries.map((e, i) => {
        const col = e.ok ? 'var(--t-green)' : e.status === 'already_open' ? 'var(--t-blue)' : 'var(--t-red)';
        const dash = e.key.indexOf('-');
        const sym = dash >= 0 ? e.key.slice(0, dash) : e.key;
        const strat = dash >= 0 ? e.key.slice(dash + 1) : '';
        const bg = e.ok ? col + '16' : 'var(--t-bg)';
        const borderColor = e.ok ? col + '44' : 'var(--t-border)';
        return (
          <div key={i} style={{ 
            display: 'flex', flexDirection: 'column', gap: 7,
            padding: '12px 16px 12px 0', borderRadius: 10,
            border: `1px solid ${borderColor}`,
            background: bg,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
              <div style={{ width: 4, alignSelf: 'stretch', minHeight: 34, borderRadius: 3, background: col, flexShrink: 0 }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--t-bright)', letterSpacing: '0.02em' }}>{sym}</span>
                  <span style={{ fontSize: 11, color: 'var(--t-dim)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{strat.replace(/_/g, ' ').toUpperCase()}</span>
                  <span style={{ marginLeft: 'auto', color: modeColorOf(e.mode), fontWeight: 800, fontSize: 9, letterSpacing: '0.06em', padding: '3px 8px', borderRadius: 6, background: modeColorOf(e.mode) + '18', border: `1px solid ${modeColorOf(e.mode)}44`, whiteSpace: 'nowrap' }}>
                    {e.auto ? 'AUTO · ' : ''}{e.mode}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: col, fontWeight: 800, fontSize: 10, letterSpacing: '0.04em' }}>{e.ok ? '✓' : '✕'} {e.status.toUpperCase()}</span>
                  <span style={{ marginLeft: 'auto', color: 'var(--t-dim)', fontVariantNumeric: 'tabular-nums', fontSize: 9 }}>
                    {new Date(e.ts).toLocaleTimeString()}
                  </span>
                </div>
                {e.reason && <div style={{ color: 'var(--t-amber)', fontSize: 10, lineHeight: 1.4, marginTop: 4, fontWeight: 600, wordBreak: 'break-word' }}>✕ {e.mode} — {e.reason}</div>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ScalpSignalCard({ s, selected, expanded, onSelect, onExecute, executing, execState, pnl, algoOn, mode, macroMode }: {
  s: ScalpingSignal; selected: boolean; expanded?: boolean; onSelect: () => void; onExecute: () => void;
  executing: boolean; execState?: ExecState; pnl?: SignalPnl; algoOn?: boolean; mode?: string; macroMode?: string;
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

  const statusLabel = accepted ? 'EXECUTED' : s.executable ? 'READY' : isWatch ? 'WATCH' : 'PENDING';
  const statusColor = accepted ? 'var(--t-blue)' : s.executable ? dirColor : isWatch ? 'var(--t-blue)' : 'var(--t-dim)';

  // Signal's own setup reason — shown only until an execution attempt replaces it
  // with the richer ExecDetail block below.
  const metaReason = s.entry != null ? s.reason : null;

  const pnlVal = pnl?.value ?? null;
  const pnlColor = pnlVal == null ? 'var(--t-dim)' : pnlVal >= 0 ? 'var(--t-green)' : 'var(--t-red)';

  // Live current price next to Entry — live mark for executed trades, else the
  // latest scan close. Colored by whether price has moved the position's way.
  const currentPx = pnl?.currentSpot ?? (s.close || null);

  const displayEntry = accepted ? (pnl?.entryPriceReal ?? resp?.entry_price ?? s.entry) : s.entry;
  const displaySl = accepted ? (pnl?.currentSl ?? pnl?.initialSl ?? resp?.stop_loss ?? s.stop_loss) : s.stop_loss;
  const displayTp = accepted ? (pnl?.currentTp ?? pnl?.initialTp ?? resp?.take_profit ?? s.take_profit) : s.take_profit;
  const hasPlan = displayEntry != null;

  const currentColor = currentPx == null || displayEntry == null
    ? 'var(--t-bright)'
    : (long ? currentPx >= displayEntry : currentPx <= displayEntry) ? 'var(--t-green)' : 'var(--t-red)';

  let currentValNode: React.ReactNode = '—';
  if (currentPx != null) {
    if (displayEntry != null) {
      const diff = long ? (currentPx - displayEntry) : (displayEntry - currentPx);
      const sign = diff >= 0 ? '+' : '−';
      currentValNode = (
        <span>
          {fmtUsd(currentPx)} <span style={{ fontSize: 10, opacity: 0.7, fontWeight: 600 }}>({sign}{Math.abs(diff).toFixed(1)})</span>
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
  const isOpen = accepted && !!expanded;
  const bg = isOpen ? statusColor + '16' : selected ? 'rgba(0,0,0,0.16)' : 'var(--t-bg2)';
  const borderColor = isOpen ? statusColor + '66' : selected ? statusColor + '2e' : 'var(--t-border)';

  return (
    <div onClick={onSelect} style={{
      display: 'flex', flexDirection: 'column', gap: 7,
      padding: '12px 16px 12px 0', borderRadius: 10, cursor: 'pointer',
      border: `1px solid ${borderColor}`,
      background: bg,
      transition: 'border-color .12s, background .12s',
    }}>
      {/* ── main row: fixed-width columns keep values aligned across cards ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <div style={{ width: 4, alignSelf: 'stretch', minHeight: 34, borderRadius: 3, background: meta.color, flexShrink: 0 }} />
        <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--t-bright)', letterSpacing: '0.02em', width: 56, flexShrink: 0 }}>{s.underlying}</span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, width: 68, flexShrink: 0 }}>
          <span style={{ fontSize: 12, fontWeight: 800, color: dirColor, letterSpacing: '0.04em', lineHeight: 1.1 }}>
            {long ? '▲ LONG' : '▼ SHORT'}
          </span>
          {!accepted && (
            <span style={{
              fontSize: 8, fontWeight: 700, letterSpacing: '0.08em', color: statusColor, lineHeight: 1,
              padding: '1px 5px', borderRadius: 3, background: statusColor + '18', alignSelf: 'flex-start',
            }}>{statusLabel}</span>
          )}
        </div>
        {hasPlan ? (
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexShrink: 0 }}>
            <PlanCell value={fmtUsd(displayEntry)} />
            <PlanCell value={currentValNode} color={currentColor} width={110} />
            <PlanCell value={fmtUsd(displaySl)} color="#f87171" />
            <PlanCell value={fmtUsd(displayTp)} color="var(--t-amber)" />
            <PlanCell value={s.risk_pct != null ? `${fmt(s.risk_pct)}%` : '—'} width={50} />
          </div>
        ) : (
          <span style={{ fontSize: 11, color: 'var(--t-dim)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.reason}</span>
        )}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0, marginLeft: hasPlan ? 0 : 'auto' }}>
          {/* fixed-width pill column so the pattern text lines up across rows.
              Strategy tag + the macro trading mode it ran under, e.g. SMC [SWING]. */}
          <div style={{ width: 150, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Pill text={meta.label} color={meta.color} />
            {macroMode && (
              <span style={{ fontSize: 8, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--t-dim)', whiteSpace: 'nowrap' }}>
                [{macroMode}]
              </span>
            )}
          </div>
          {s.pattern && (
            <span style={{ fontSize: 9, fontWeight: 600, color: meta.color, whiteSpace: 'nowrap', width: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {s.pattern.replace(/_/g, ' ')}
            </span>
          )}
          <span style={{ fontSize: 9, color: 'var(--t-dim)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', marginLeft: 8 }}>
            {fmtTime(s.timestamp_ms)}
          </span>
        </div>
        {/* ── action / executed glance — mode · P&L · expand chevron, all on this row ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, marginLeft: 'auto' }}>
          {accepted ? (
            <>
              <span style={{
                fontSize: 9, fontWeight: 800, letterSpacing: '0.06em', color: modeColor,
                padding: '4px 9px', borderRadius: 6, background: modeColor + '18',
                border: `1px solid ${modeColor}44`, whiteSpace: 'nowrap',
              }}>✓ {execState?.auto ? 'AUTO · ' : ''}{pillMode}</span>
              {execState?.auto && execState?.resp?.telegram_alert_sent && (
                <span title="Signal alert sent to Telegram" style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: '#a78bfa',
                  flexShrink: 0,
                }} />
              )}
              {!isOpen && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', lineHeight: 1.05, minWidth: 64 }}>
                  <span style={{ fontSize: 14, fontWeight: 800, color: pnlColor, fontVariantNumeric: 'tabular-nums' }}>
                    {pnlVal == null ? '—' : `${pnlVal >= 0 ? '+' : '−'}${fmtUsd(Math.abs(pnlVal))}`}
                  </span>
                  <span style={{ fontSize: 8, color: 'var(--t-dim)', letterSpacing: '0.06em', fontWeight: 700 }}>
                    {pnl?.realized ? 'REALIZED' : 'OPEN P&L'}
                  </span>
                </div>
              )}
              <span style={{ fontSize: 9, color: 'var(--t-dim)', width: 10, textAlign: 'center', transition: 'transform .15s', transform: expanded ? 'rotate(180deg)' : 'none', display: 'inline-block' }}>▼</span>
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

      {/* ── second line — only for NON-executed states (executed glance is on the main row) ──
           failure note · auto-queued hint · setup reason */}
      {execState && !accepted ? (
        <div style={{ paddingLeft: 18, fontSize: 10, lineHeight: 1.5, color: 'var(--t-amber)', fontWeight: 600, wordBreak: 'break-word' }}>
          ✕ {pillMode} — {failureReason(execState)}
        </div>
      ) : !execState && algoOn && s.executable ? (
        <div style={{ paddingLeft: 18, fontSize: 10, lineHeight: 1.5, color: 'var(--t-green)', wordBreak: 'break-word' }}>
          ⚡ Auto-executing in {pillMode}…
        </div>
      ) : metaReason && !accepted ? (
        <div style={{ paddingLeft: 18, fontSize: 10, lineHeight: 1.5, color: 'var(--t-dim)', wordBreak: 'break-word' }}>
          {metaReason}
        </div>
      ) : null}

      {/* expand-on-click: full execution metrics for an executed trade */}
      {accepted && expanded && execState && <ExecDetail execState={execState} pnl={pnl} />}
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
  const scanQ = useScalpingSignals(armedOnly);
  const exec = useScalpingExecute();
  const [execKeys, setExecKeys] = useState<Set<string>>(new Set());  // in-flight (supports concurrent auto-exec)
  // Executions persist across reloads and across mode switches; each entry carries
  // the mode it actually ran in (es.mode), so the view can stay segregated per mode.
  const [execStates, setExecStates] = useState<Record<string, ExecState>>(() => {
    try { return JSON.parse(localStorage.getItem('scalp.execStates') || '{}'); } catch { return {}; }
  });
  const [expandedKey, setExpandedKey] = useState<string | null>(null);  // which executed row shows full metrics
  const [liveConfirm, setLiveConfirm] = useState(false);                 // gate the paper/shadow→live switch behind a modal
  // Visible execution log — every execute attempt (accepted OR rejected/errored)
  // with the mode it ran in and the backend reason. Makes "is live actually
  // firing?" answerable at a glance instead of guessing.
  type ExecLogEntry = { ts: number; key: string; mode: string; ok: boolean; status: string; reason: string; auto: boolean };
  const [execLog, setExecLog] = useState<ExecLogEntry[]>(() => {
    try { return JSON.parse(localStorage.getItem('scalp.execLog') || '[]'); } catch { return []; }
  });
  const logExec = (e: ExecLogEntry) => setExecLog((l) => [e, ...l].slice(0, 40));
  const cfg = cfgQ.data?.config;
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
      initialSl: live?.initial_sl ?? pos.initial_sl, initialTp: live?.initial_tp ?? pos.initial_tp,
      currentSl: live?.current_sl ?? pos.current_sl, currentTp: live?.current_tp ?? pos.current_tp,
      trailMode: live?.trail_mode ?? pos.trail_mode, trailState: live?.trail_state as SignalPnl['trailState'],
      orderId: live?.order_id ?? pos.order_id, orderStatus: live?.order_status ?? pos.order_status,
      mode: live?.mode, structureType: live?.structure_type,
    };
  };

  // Synthesize a signal-row + execution-record from a real position so it renders
  // with the executed (rich) layout: entry/stop/target come straight off the fill.
  const signalFromPos = (pos: PaperPosition, strategy: string): ScalpingSignal => ({
    underlying: pos.underlying, close: pos.entry_spot_price ?? 0,
    strategy, direction: (pos.sized_trade?.structure?.direction as string) ?? 'none',
    near_level: null, level_type: '', pattern: '', reason: pos.notes || '',
    entry: pos.entry_spot_price ?? null, stop_loss: pos.initial_sl ?? null, take_profit: pos.initial_tp ?? null,
    risk_pct: pos.sized_trade?.capital_at_risk_pct ?? null,
    leverage: pos.sized_trade?.structure?.leverage ?? null,
    size_units: pos.sized_trade?.contracts ?? null,
    notional_usd: pos.sized_trade?.position_value ?? null,
    entry_ok: true, executable: false, timestamp_ms: pos.entry_timestamp_ms ?? 0, error: null,
  });
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
  const onExecute = (sym: string, strategy: string, auto = false) => {
    const key = `${sym}-${strategy}`;
    setExecKeys((s) => new Set(s).add(key));
    exec.mutateAsync({ underlying: sym, strategy, auto })
      // Tie the record to the mode the backend ACTUALLY ran in (r.mode), not the
      // mode picker — so a live order is stored as LIVE, shadow as SHADOW, etc.
      .then((r) => { const ranMode = (r.mode || tradeMode).toUpperCase(); setExecStates((m) => ({ ...m, [key]: { resp: r, auto, mode: ranMode } })); if (r.accepted) acceptedRef.current.add(key); logExec({ ts: Date.now(), key, mode: ranMode, ok: !!r.accepted, status: r.status, reason: r.reason, auto }); })
      .catch((e: Error) => { setExecStates((m) => ({ ...m, [key]: { error: e.message, auto, mode: tradeMode } })); logExec({ ts: Date.now(), key, mode: tradeMode, ok: false, status: 'error', reason: e.message, auto }); })
      .finally(() => { setExecKeys((s) => { const n = new Set(s); n.delete(key); return n; }); });
  };

  const data = scanQ.data;
  let signals = data?.signals ?? [];
  if (stratFilter !== 'all') {
    signals = signals.filter((s) => s.strategy === stratFilter);
  }

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
      .filter((p) => stratFilter === 'all' || stratFromNotes(p.notes) === stratFilter)
      .sort((a, b) => {
        const ao = a.status !== 'closed' ? 1 : 0, bo = b.status !== 'closed' ? 1 : 0;
        if (ao !== bo) return bo - ao;                         // open positions before closed
        return (b.entry_timestamp_ms ?? 0) - (a.entry_timestamp_ms ?? 0);  // newest first
      }),
    [positions, wantPaper, stratFilter],
  );

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
    .filter((s) => !openSetupKeys.has(`${s.underlying}-${s.strategy}`))
    .map((s) => {
      const key = `${s.underlying}-${s.strategy}`;
      const es = modeExecStates[key];
      // Surface ONLY a rejection/error record inline (for the failure reason). An
      // ACCEPTED record means a position opened — that's its own row from
      // positions (above), and once it CLOSES the setup is free to re-arm, so a
      // stale accept must never suppress the EXECUTE button on a live signal.
      const feedbackEs = es && !es.resp?.accepted ? es : undefined;
      return { key, s, es: feedbackEs, pnl: undefined, executed: false, macroMode };
    });

  const executedSignals: Row[] = executedRows;       // real open/closed positions for this book
  const restSignals: Row[] = scanRows;               // live scan signals (button when ready & algo off)
  const displaySignals: Row[] = [...executedSignals, ...restSignals];

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

  // Persist sidebar selections (Armed-only filter + active strategy nav) across reloads.
  useEffect(() => { localStorage.setItem('scalp.stratFilter', stratFilter); }, [stratFilter]);
  useEffect(() => { localStorage.setItem('scalp.armedOnly', armedOnly ? '1' : '0'); }, [armedOnly]);
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
      onExecute(s.underlying, s.strategy, true);
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

  const allSignals = data?.signals ?? [];

  const navItems = [
    { id: 'all', label: 'All Strategies', color: 'var(--t-bright)', count: allSignals.length },
    { id: 'price_action', label: 'Price Action', color: 'var(--t-amber)', count: allSignals.filter((s) => s.strategy === 'price_action').length },
    { id: 'smc', label: 'Smart Money', color: 'var(--t-purple)', count: allSignals.filter((s) => s.strategy === 'smc').length },
    { id: 'ma_crossover', label: 'MA Crossover', color: 'var(--t-blue)', count: allSignals.filter((s) => s.strategy === 'ma_crossover').length },
  ];

  const btUnderlying = (selected?.split('-')[0]) || cfg?.symbols?.[0] || 'BTC';

  const renderSignalCard = (row: Row) => (
    <ScalpSignalCard
      key={row.key} s={row.s}
      selected={selected === row.key}
      expanded={expandedKey === row.key}
      onSelect={() => { setSelected(row.key); setExpandedKey((k) => (k === row.key ? null : row.key)); }}
      onExecute={() => onExecute(row.s.underlying, row.s.strategy)}
      executing={execKeys.has(`${row.s.underlying}-${row.s.strategy}`)}
      execState={row.es}
      pnl={row.pnl}
      algoOn={algoOn}
      mode={tradeMode}
      macroMode={row.macroMode}
    />
  );

  return (
    <>
    <ThreeColumnLayout
      leftNav={navItems}
      activeNav={stratFilter}
      onNavClick={setStratFilter}
      leftSidebar={<>
        <LeftSection label="Ready Only" collapsible defaultOpen>
          <button onClick={() => { const v = !armedOnly; setArmedOnly(v); }} style={{
            display: 'flex', alignItems: 'center', gap: 8, width: '100%',
            padding: '7px 10px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
            border: `1px solid ${armedOnly ? 'var(--t-green)44' : 'var(--t-border)'}`,
            background: armedOnly ? 'var(--t-green)16' : 'transparent',
            color: armedOnly ? 'var(--t-green)' : 'var(--t-dim)', transition: 'all .1s',
          }}>
            <span style={{ fontSize: 12 }}>{armedOnly ? '●' : '○'}</span>
            <span style={{ fontSize: 11, fontWeight: 600 }}>Ready only</span>
          </button>
        </LeftSection>
      </>}
      centerHeader={<>
        <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Scalping</div>
        <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 1 }}>
          4H structure · 15min entry · {scanQ.isFetching ? 'scanning…' : 'auto-refresh'}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
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
            {scanQ.isError && <div style={{ color: 'var(--t-red)', fontSize: 11 }}>{(scanQ.error as Error).message}</div>}
            {scanQ.isLoading && <div style={{ ...dim, padding: '40px 0', textAlign: 'center' }}>scanning…</div>}
            {data && displaySignals.length === 0 && (
              <div style={{ ...dim, padding: '40px 0', textAlign: 'center' }}>
                {armedOnly ? 'No ready signals — clear the filter to see all.' : 'No signals on this data source.'}
              </div>
            )}
            {executedSignals.length > 0 && (
              <>
                <ListGroupHeader label="Executed" count={executedSignals.length} color="var(--t-blue)" />
                <SignalTableHeader />
              </>
            )}
            {executedSignals.map(renderSignalCard)}
            {executedSignals.length > 0 && (
              <ConsolidatedRow count={executedSignals.length} {...consolidated} />
            )}
            {restSignals.length > 0 && (
              <>
                <ListGroupHeader label={armedOnly ? 'Ready Signals' : 'Signals'} count={restSignals.length} />
                <SignalTableHeader />
              </>
            )}
            {restSignals.map(renderSignalCard)}
            {data && displaySignals.length > 0 && (
              <div style={{ fontSize: 10, color: 'var(--t-dim)', lineHeight: 1.5, paddingTop: 4 }}>
                <b style={{ color: 'var(--t-amber)' }}>PA</b> pattern breakout · <b style={{ color: 'var(--t-purple)' }}>SMC</b> inducement + imbalance · <b style={{ color: 'var(--t-blue)' }}>MA</b> SMA/EMA cross · EXECUTE routes through Paper/Live mode
              </div>
            )}
          </div>
      }
      rightSidebar={<>
        <RightSection label="Settings" collapsible defaultOpen={true}>
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
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
          <div style={{
            padding: '10px 14px', borderBottom: '1px solid var(--t-border)',
            fontSize: 9, fontWeight: 700, letterSpacing: '0.12em',
            color: 'var(--t-dim)', textTransform: 'uppercase',
          }}>
            Execution Log · {tradeMode}
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <ExecLog entries={execLog} mode={tradeMode} />
          </div>
        </div>
      </>}
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
        background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'flex-end',
      }}>
        <div onClick={(e) => e.stopPropagation()} style={{
          width: 'min(700px, 94vw)', height: '100%', background: 'var(--t-bg)',
          borderLeft: '1px solid var(--t-border)', overflow: 'auto', padding: 16,
          display: 'flex', flexDirection: 'column', gap: 12,
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