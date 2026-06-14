import React, { useEffect, useRef, useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useEngineActivity } from '../../hooks/useTripleSupertrend';
import type { ActivityEvent } from '../../types/kiteEngine';

type Theme = 'dark' | 'light';

const THEME = {
  dark: { bg: '#0b0b0b', headerBg: '#111', border: '#1f1f1f', text: '#d8d8d8', dim: '#777', headTxt: '#eee', headDim: '#bdbdbd' },
  light: { bg: '#ffffff', headerBg: '#f9f9f9', border: '#e0e0e0', text: '#333', dim: '#9b9b9b', headTxt: '#222', headDim: '#666' },
};

const KIND_COLOR: Record<string, string> = {
  scan_start: k.dim,
  scan_done: k.blue,
  order_placed: k.green,
  order_blocked: k.amber,
  order_failed: k.red,
  error: k.red,
  info: k.dim,
};

function hhmmss(ms: number): string {
  return new Date(ms).toLocaleTimeString('en-IN', { hour12: false });
}

function fmtCountdown(nextMs: number): string {
  if (!nextMs) return '—';
  const s = Math.max(0, Math.round((nextMs - Date.now()) / 1000));
  if (s <= 0) return 'due now';
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
}

function Line({ ev, t }: { ev: ActivityEvent; t: typeof THEME.dark }) {
  const color = KIND_COLOR[ev.kind] ?? t.text;
  return (
    <div style={{ display: 'flex', gap: 10, padding: '2px 0', whiteSpace: 'nowrap' }}>
      <span style={{ color: t.dim }}>{hhmmss(ev.ts_ms)}</span>
      <span style={{ color, fontWeight: 600, minWidth: 96 }}>{ev.kind}</span>
      <span style={{ color: t.text, whiteSpace: 'pre-wrap' }}>{ev.message}</span>
    </div>
  );
}

export function EngineTerminal() {
  const { data } = useEngineActivity();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem('kite_terminal_theme') as Theme) || 'dark');
  const t = THEME[theme];
  const events = data?.events ?? [];

  useEffect(() => { localStorage.setItem('kite_terminal_theme', theme); }, [theme]);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [events.length]);

  const dot = data?.scanning ? k.green : data?.auto_scan ? k.blue : t.dim;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: t.bg, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}>
      {/* header / status bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '6px 14px', borderBottom: `1px solid ${t.border}`, background: t.headerBg, fontSize: 11, color: t.headDim }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 600, color: t.headTxt }}>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: dot, boxShadow: data?.scanning ? `0 0 6px ${k.green}` : 'none' }} />
          KITE TERMINAL
        </span>
        <span>{data?.scanning ? 'scanning…' : data?.auto_scan ? 'auto-scan ON' : 'idle'}</span>
        <span>last: {data?.last_scan_ms ? hhmmss(data.last_scan_ms) : '—'}</span>
        <span>next: {fmtCountdown(data?.next_scan_ms ?? 0)}</span>
        <span style={{ marginLeft: 'auto', color: k.orange }}>{data?.signal_count ?? 0} ready</span>
        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          title="Toggle terminal theme"
          style={{ background: 'none', border: `1px solid ${t.border}`, color: t.headDim, borderRadius: 4, padding: '1px 8px', fontSize: 11, cursor: 'pointer' }}
        >
          {theme === 'dark' ? '☀ Light' : '🌙 Dark'}
        </button>
      </div>
      {/* log */}
      <div ref={scrollRef} style={{ flex: 1, overflow: 'auto', padding: '8px 14px', fontSize: 11.5, lineHeight: 1.5, color: t.text }}>
        {events.length === 0 ? (
          <div style={{ color: t.dim }}>Waiting for background scan… the engine scans every ~5 min automatically.</div>
        ) : (
          events.map((ev, i) => <Line key={`${ev.ts_ms}:${i}`} ev={ev} t={t} />)
        )}
      </div>
    </div>
  );
}

export default EngineTerminal;
