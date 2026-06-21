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

const KIND_LABEL: Record<string, string> = {
  scan_start: 'SCAN START',
  scan_done: 'SCAN DONE',
  order_placed: 'ORDER PLACED',
  order_blocked: 'ORDER BLOCKED',
  order_failed: 'ORDER FAILED',
  error: 'ERROR',
  info: 'INFO',
};

function Line({ ev, t }: { ev: ActivityEvent; t: typeof THEME.dark }) {
  const color = KIND_COLOR[ev.kind] ?? t.text;
  const label = KIND_LABEL[ev.kind] ?? ev.kind.toUpperCase();
  const isImportant = ev.kind === 'order_placed' || ev.kind === 'order_failed' || ev.kind === 'error';
  return (
    <div style={{ display: 'flex', gap: 10, padding: '3px 0', borderBottom: `1px solid ${t.border}`, alignItems: 'baseline' }}>
      <span style={{ color: t.dim, flexShrink: 0, fontSize: 10.5 }}>{hhmmss(ev.ts_ms)}</span>
      <span style={{
        color, fontWeight: 700, minWidth: 100, flexShrink: 0, fontSize: 10,
        letterSpacing: 0.4,
        background: isImportant ? `${color}18` : undefined,
        borderRadius: 3, padding: isImportant ? '1px 5px' : undefined,
      }}>{label}</span>
      <span style={{ color: t.text, whiteSpace: 'pre-wrap', fontSize: 11 }}>{ev.message}</span>
    </div>
  );
}

// Mode is persisted module-side because the layout swaps EngineTerminal between
// structurally different wrappers (e.g. minimized vs normal), which REMOUNTS this
// component. Without this, a remount would reset mode to 'normal' and the terminal
// would render full-height inside the minimized slot — looking like it went full
// screen right after the user clicked minimize.
let lastTerminalMode: 'minimized' | 'normal' | 'partial' | 'full' = 'normal';

export function EngineTerminal() {
  const { data } = useEngineActivity();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem('kite_terminal_theme') as Theme) || 'dark');
  const [mode, setModeState] = useState<'minimized' | 'normal' | 'partial' | 'full'>(lastTerminalMode);

  const setMode = (m: 'minimized' | 'normal' | 'partial' | 'full') => {
    lastTerminalMode = m;
    setModeState(m);
    window.dispatchEvent(new CustomEvent('kite-terminal-mode', { detail: m }));
  };

  useEffect(() => {
    const cb = (e: any) => { lastTerminalMode = e.detail; setModeState(e.detail); };
    window.addEventListener('kite-terminal-mode', cb);
    return () => window.removeEventListener('kite-terminal-mode', cb);
  }, []);

  const t = THEME[theme];
  const events = data?.events ?? [];

  useEffect(() => { localStorage.setItem('kite_terminal_theme', theme); }, [theme]);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [events.length]);

  const dot = data?.scanning ? k.green : data?.auto_scan ? k.blue : t.dim;

  const btnStyle = { background: 'none', border: 'none', color: t.headDim, cursor: 'pointer', padding: '2px 6px', display: 'flex', alignItems: 'center', justifyContent: 'center' };

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      // When minimized, collapse to just the footer bar (auto height) so the
      // terminal can never balloon to fill a tall container — that bug made
      // "minimize" look like it went full screen. Otherwise fill the pane.
      height: mode === 'minimized' ? 'auto' : '100%',
      flexShrink: 0,
      background: t.bg, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    }}>
      {/* HEADER */}
      {mode !== 'minimized' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '6px 14px', borderBottom: `1px solid ${t.border}`, background: t.headerBg, fontSize: 11, color: t.headDim, flexShrink: 0 }}>
          <span style={{ fontWeight: 600, color: t.headTxt }}>KITE TERMINAL</span>
          
          <span style={{ marginLeft: 'auto', color: k.orange }}>{data?.signal_count ?? 0} ready</span>
          
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title="Toggle terminal theme"
            style={{ background: 'none', border: `1px solid ${t.border}`, color: t.headDim, borderRadius: 4, padding: '1px 8px', fontSize: 11, cursor: 'pointer' }}
          >
            {theme === 'dark' ? '☀ Light' : '🌙 Dark'}
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 8 }}>
            <button onClick={() => setMode('minimized')} title="Minimize" style={btnStyle}>
              <svg width="12" height="12" viewBox="0 0 24 24"><line x1="4" y1="12" x2="20" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
            </button>
            <button onClick={() => setMode(mode === 'partial' ? 'normal' : 'partial')} title="Partial Full Screen" style={btnStyle}>
              <svg width="12" height="12" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" rx="2"/></svg>
            </button>
            <button onClick={() => setMode(mode === 'full' ? 'normal' : 'full')} title="Full Screen" style={btnStyle}>
              <svg width="12" height="12" viewBox="0 0 24 24"><path d="M4 8V4h4m8 0h4v4m0 8v4h-4m-8 0H4v-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </button>
          </div>
        </div>
      )}

      {/* LOG AREA */}
      {mode !== 'minimized' && (
        <div ref={scrollRef} style={{ flex: 1, overflow: 'auto', padding: '8px 14px', fontSize: 11.5, lineHeight: 1.5, color: t.text }}>
          {events.length === 0 ? (
            <div style={{ color: t.dim }}>Waiting for background scan… the engine scans every ~5 min automatically.</div>
          ) : (
            events.map((ev, i) => <Line key={`${ev.ts_ms}:${i}`} ev={ev} t={t} />)
          )}
        </div>
      )}

      {/* FOOTER */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '5px 14px', background: t.headerBg, fontSize: 11, color: t.headDim, marginTop: 'auto', flexShrink: 0 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 600, color: t.headTxt }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: dot, boxShadow: data?.scanning ? `0 0 5px ${k.green}` : 'none', flexShrink: 0 }} />
          TERMINAL
        </span>
        <span style={{ color: data?.scanning ? k.green : data?.auto_scan ? k.orange : t.headDim, fontWeight: data?.scanning ? 600 : 400 }}>
          {data?.scanning ? data?.scanning_label || 'scanning…' : data?.auto_scan ? 'auto' : 'idle'}
        </span>
        {!data?.scanning && <span style={{ color: t.dim }}>last {data?.last_scan_ms ? hhmmss(data.last_scan_ms) : '—'}</span>}
        {!data?.scanning && data?.auto_scan && <span style={{ color: t.dim }}>next {fmtCountdown(data?.next_scan_ms ?? 0)}</span>}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          {(data?.signal_count ?? 0) > 0 && <span style={{ color: k.orange, fontWeight: 600 }}>{data?.signal_count} ready</span>}
          {mode === 'minimized' && (
            <button onClick={() => setMode('normal')} style={{ background: 'none', border: `1px solid ${t.border}`, color: t.headDim, borderRadius: 4, padding: '2px 8px', fontSize: 11, cursor: 'pointer' }}>
              Expand ↑
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default EngineTerminal;
