import React from 'react';
import { k, tint } from '../../styles/kiteUI';
import {
  useEngineConfig, useEngineSignals, useRunScan, useSetEngineConfig,
} from '../../hooks/useTripleSupertrend';
import type {
  AlignmentChip, EngineConfigModel, EngineSignalRow, Moneyness, TrailTarget,
} from '../../types/kiteEngine';

interface Props {
  onSelectSignal: (sel: { token: number; underlying: string }) => void;
}

// Plain-language labels (users were confused by fast/mid/slow + "early lock").
const TRAIL_OPTS: { value: TrailTarget; label: string; hint: string }[] = [
  { value: 'fast', label: 'Tight', hint: 'Exit quickly — trails the fast SuperTrend (21,1). Locks gains sooner, more whipsaw.' },
  { value: 'mid', label: 'Balanced', hint: 'Default — trails the mid SuperTrend (14,2). Balanced hold vs. protection.' },
  { value: 'slow', label: 'Loose', hint: 'Hold longer — trails the slow SuperTrend (7,3). Rides trends further, gives back more.' },
];
const MONEY_OPTS: { value: Moneyness; hint: string }[] = [
  { value: 'ATM', hint: 'At-the-money — strike nearest spot.' },
  { value: 'ITM1', hint: 'One strike in-the-money.' },
  { value: 'ITM2', hint: 'Two strikes in-the-money.' },
];

function timeAgo(ms: number): string {
  if (!ms) return 'never';
  const s = Math.round((Date.now() - ms) / 1000);
  if (s < 60) return `${s}s ago`;
  return `${Math.floor(s / 60)}m ago`;
}

function countdown(ms: number): string {
  if (!ms) return '—';
  const s = Math.max(0, Math.round((ms - Date.now()) / 1000));
  if (s <= 0) return 'due';
  return s >= 60 ? `${Math.floor(s / 60)}m` : `${s}s`;
}

function Arrow({ v }: { v: number }) {
  const flat = v === 0;
  return <span style={{ color: flat ? k.dim : v > 0 ? k.green : k.red, fontSize: 11, fontWeight: 700 }}>{flat ? '·' : v > 0 ? '▲' : '▼'}</span>;
}

function AlignmentChips({ a }: { a: AlignmentChip }) {
  return (
    <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
      {(['fast', 'mid', 'slow'] as const).map((key) => (
        <span key={key} style={{ display: 'inline-flex', gap: 2, alignItems: 'center' }}>
          <span style={{ fontSize: 9, color: k.dim, textTransform: 'uppercase' }}>{key[0]}</span>
          <Arrow v={a[key]} />
        </span>
      ))}
    </span>
  );
}

function SignalCard({ row, onClick }: { row: EngineSignalRow; onClick: () => void }) {
  const bull = row.regime === 'BULL';
  const accent = bull ? k.green : k.red;
  return (
    <div
      onClick={onClick}
      style={{ padding: '10px 12px', borderBottom: `1px solid ${k.border}`, cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 6 }}
      onMouseEnter={(e) => (e.currentTarget.style.background = k.surfaceHover)}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: k.text }}>{row.underlying}</span>
        <span style={{ color: accent, background: tint(accent, 10), fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 3 }}>{row.regime} · {row.option_type}</span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <AlignmentChips a={row.alignment} />
        <span style={{ fontSize: 11, color: k.dim }}>SL {row.stop_loss.toFixed(1)}</span>
      </div>
      {/* option legs (one per selected moneyness) */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {row.legs.length === 0 ? (
          <span style={{ fontSize: 10, color: k.dim }}>no liquid ATM/ITM contract</span>
        ) : row.legs.map((leg) => (
          <span key={leg.option_symbol} style={{ fontSize: 10, color: k.text, background: k.surface, border: `1px solid ${k.border}`, borderRadius: 3, padding: '2px 6px' }}>
            <b style={{ color: k.orange }}>{leg.moneyness}</b> {leg.option_type} {leg.strike}
          </span>
        ))}
      </div>
    </div>
  );
}

export function TripleSupertrendPane({ onSelectSignal }: Props) {
  const { data: signals } = useEngineSignals();
  const { data: cfg } = useEngineConfig();
  const setCfg = useSetEngineConfig();
  const scan = useRunScan();

  const patch = (p: Partial<EngineConfigModel>) => { if (cfg) setCfg.mutate({ ...cfg, ...p }); };

  const toggleMoneyness = (m: Moneyness) => {
    if (!cfg) return;
    const has = cfg.strike_moneyness.includes(m);
    const next = has ? cfg.strike_moneyness.filter((x) => x !== m) : [...cfg.strike_moneyness, m];
    patch({ strike_moneyness: next.length ? next : ['ATM'] });
  };

  const toggleAuto = () => {
    if (!cfg) return;
    if (!cfg.auto_execute) {
      const ok = window.confirm('Enable AUTO-EXECUTE? Ready signals will place real ATM/ITM option BUY orders on your active Kite account (under the live-safety gate). Continue?');
      if (!ok) return;
    }
    patch({ auto_execute: !cfg.auto_execute });
  };

  const rows = signals?.rows ?? [];
  const scanning = signals?.scanning;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: k.bg, fontFamily: k.fontFamily }}>
      {/* Header + live scan status */}
      <div style={{ padding: '12px 16px', borderBottom: `1px solid ${k.border}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: k.text }}>Triple SuperTrend</span>
          <button onClick={() => scan.mutate()} disabled={scan.isPending || scanning}
            style={{ fontSize: 11, fontWeight: 500, color: k.orange, background: 'none', border: `1px solid ${k.orange}`, borderRadius: 4, padding: '3px 10px', cursor: 'pointer', opacity: (scan.isPending || scanning) ? 0.5 : 1 }}>
            {scan.isPending || scanning ? 'Scanning…' : 'Re-scan'}
          </button>
        </div>
        {/* status line — user doesn't need to click scan; it runs automatically */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, fontSize: 10.5, color: k.dim }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 7, height: 7, borderRadius: 4, background: scanning ? k.green : signals?.auto_scan ? k.blue : k.dim }} />
            {scanning ? 'scanning…' : signals?.auto_scan ? 'auto-scan on' : 'manual'}
          </span>
          <span>·  last {timeAgo(signals?.generated_ms ?? 0)}</span>
          <span>·  next {countdown(signals?.next_scan_ms ?? 0)}</span>
          <span style={{ marginLeft: 'auto', color: k.orange }}>{rows.length} ready</span>
        </div>
        <div style={{ fontSize: 9.5, color: k.dim, marginTop: 4 }}>Nifty50 / BankNifty / FinNifty / Sensex stocks + index options · 1H</div>
      </div>

      {/* Controls */}
      <div style={{ padding: '10px 16px', borderBottom: `1px solid ${k.border}`, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* trail tightness */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: k.dim, minWidth: 84 }} title="How tightly the position is trailed before exit.">Exit trailing</span>
          <div style={{ display: 'flex', gap: 4 }}>
            {TRAIL_OPTS.map((o) => {
              const active = (cfg?.trail_target ?? 'mid') === o.value;
              return (
                <button key={o.value} title={o.hint} onClick={() => patch({ trail_target: o.value })}
                  style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, cursor: 'pointer', border: `1px solid ${active ? k.orange : k.border}`, color: active ? '#fff' : k.text, background: active ? k.orange : 'none' }}>
                  {o.label}
                </button>
              );
            })}
          </div>
        </div>
        {/* strike moneyness — multi-select chips */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: k.dim, minWidth: 84 }} title="Which strikes to resolve per signal. Select one or more — never OTM.">Strikes</span>
          <div style={{ display: 'flex', gap: 4 }}>
            {MONEY_OPTS.map((o) => {
              const active = cfg?.strike_moneyness.includes(o.value) ?? false;
              return (
                <button key={o.value} title={o.hint} onClick={() => toggleMoneyness(o.value)}
                  style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, cursor: 'pointer', border: `1px solid ${active ? k.orange : k.border}`, color: active ? '#fff' : k.text, background: active ? k.orange : 'none' }}>
                  {o.value}
                </button>
              );
            })}
          </div>
        </div>
        {/* early-lock + auto-exec */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <label title="Once a trade is comfortably in profit, also exit on a slow-SuperTrend flip to lock gains earlier." style={{ fontSize: 11, color: k.dim, display: 'flex', gap: 5, alignItems: 'center', cursor: 'pointer' }}>
            <input type="checkbox" checked={cfg?.early_lock ?? false} onChange={(e) => patch({ early_lock: e.target.checked })} />
            Lock profits early
          </label>
          <label onClick={toggleAuto} title="When on, ready signals auto-place real option BUY orders (gated by live-safety)."
            style={{ fontSize: 11, fontWeight: 600, marginLeft: 'auto', display: 'flex', gap: 5, alignItems: 'center', cursor: 'pointer', color: cfg?.auto_execute ? k.orange : k.dim, background: cfg?.auto_execute ? tint(k.orange, 10) : 'transparent', padding: '3px 8px', borderRadius: 3 }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: cfg?.auto_execute ? k.orange : k.border }} />
            Auto-exec {cfg?.auto_execute ? 'ON' : 'OFF'}
          </label>
        </div>
      </div>

      {/* Signal list */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {rows.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: k.dim, fontSize: 12 }}>
            {scanning ? 'Scanning the universe…' : 'No ready setups right now. The engine re-scans automatically.'}
          </div>
        ) : (
          rows.map((row) => (
            <SignalCard key={`${row.token}:${row.option_type}`} row={row}
              onClick={() => onSelectSignal({ token: row.token, underlying: row.underlying })} />
          ))
        )}
      </div>
    </div>
  );
}

export default TripleSupertrendPane;
