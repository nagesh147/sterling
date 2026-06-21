import React, { useEffect, useRef, useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useEngineActivity } from '../../hooks/useTripleSupertrend';
import type { ActivityEvent } from '../../types/kiteEngine';

type Theme = 'dark' | 'light';

const THEME = {
  dark: { bg: '#0b0b0b', headerBg: '#111', border: '#1f1f1f', text: '#d8d8d8', dim: '#777', headTxt: '#eee', headDim: '#bdbdbd' },
  light: { bg: '#ffffff', headerBg: '#f9f9f9', border: '#e0e0e0', text: '#333', dim: '#9b9b9b', headTxt: '#222', headDim: '#666' },
};

// One monospace stack for the whole terminal so log lines read like real logs.
const MONO = 'ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace';

// ── Log levels (color-coded) ────────────────────────────────────────────────
// Standard severity ladder. `color` is resolved against app tokens; DEBUG falls
// back to the theme's dim grey so it recedes.
type Level = 'DEBUG' | 'INFO' | 'SUCCESS' | 'WARN' | 'ERROR';

const LEVEL_META: Record<Level, { color: string }> = {
  DEBUG:   { color: k.dim },
  INFO:    { color: k.blue },
  SUCCESS: { color: k.green },
  WARN:    { color: k.amber },
  ERROR:   { color: k.red },
};

// Each event `kind` maps to a level + a kind-specific emoji/label. `banner: true`
// kinds render as full-width section dividers rather than ordinary log lines.
const KIND_META: Record<string, { level: Level; emoji: string; label: string; banner?: boolean }> = {
  scan_start:    { level: 'INFO',    emoji: '🔍', label: 'SCAN START', banner: true },
  scan_done:     { level: 'SUCCESS', emoji: '🏁', label: 'SCAN DONE',  banner: true },
  order_placed:  { level: 'SUCCESS', emoji: '🟢', label: 'ORDER PLACED' },
  order_blocked: { level: 'WARN',    emoji: '🚧', label: 'ORDER BLOCKED' },
  order_failed:  { level: 'ERROR',   emoji: '❌', label: 'ORDER FAILED' },
  error:         { level: 'ERROR',   emoji: '💥', label: 'ERROR' },
  info:          { level: 'INFO',    emoji: '',  label: 'INFO' },
};

const SPINNER = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

// Injected once — keyframes for the indeterminate progress stripe and the
// banner sheen. Inline styles can't express @keyframes.
const KT_CSS = `
@keyframes kt-indet { 0% { transform: translateX(-100%); } 100% { transform: translateX(300%); } }
@keyframes kt-banner-in { from { opacity: 0; } to { opacity: 1; } }
`;

function hhmmss(ms: number): string {
  return new Date(ms).toLocaleTimeString('en-IN', { hour12: false });
}

function fmtCountdown(nextMs: number): string {
  if (!nextMs) return '—';
  const s = Math.max(0, Math.round((nextMs - Date.now()) / 1000));
  if (s <= 0) return 'due now';
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
}

// Pull an "x / y" fraction out of the scanning label (e.g. "Scanning 12/50…")
// for a determinate progress bar. Returns null when no fraction is present.
function parseProgress(label?: string): { done: number; total: number; pct: number } | null {
  if (!label) return null;
  const m = label.match(/(\d+)\s*\/\s*(\d+)/);
  if (!m) return null;
  const done = Number(m[1]);
  const total = Number(m[2]);
  if (!total || total < done) return null;
  return { done, total, pct: Math.min(100, Math.round((done / total) * 100)) };
}

// ── Section banner (scan_start / scan_done) ─────────────────────────────────
function Banner({ ev, t }: { ev: ActivityEvent; t: typeof THEME.dark }) {
  const meta = KIND_META[ev.kind]!;
  const color = LEVEL_META[meta.level].color;
  const rule = { flex: 1, height: 1, background: `linear-gradient(90deg, transparent, ${color}55)` };
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0 6px',
      animation: 'kt-banner-in .2s ease',
    }}>
      <span style={{ ...rule, background: `linear-gradient(90deg, transparent, ${color}55)` }} />
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 6, flexShrink: 0,
        color, fontWeight: 700, fontSize: 10.5, letterSpacing: 0.6,
        background: `${color}1a`, border: `1px solid ${color}40`, borderRadius: 999, padding: '2px 10px',
      }}>
        <span>{meta.emoji}</span>
        <span>{meta.label}</span>
        <span style={{ color: t.dim, fontWeight: 500, letterSpacing: 0 }}>· {hhmmss(ev.ts_ms)}</span>
      </span>
      {ev.message
        ? <span style={{ color: t.dim, fontSize: 10.5, flexShrink: 0, maxWidth: '45%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.message}</span>
        : null}
      <span style={{ ...rule, background: `linear-gradient(90deg, ${color}55, transparent)` }} />
    </div>
  );
}

// ── Ordinary log line ───────────────────────────────────────────────────────
// Rendered like a real terminal log: monospace, dim timestamp, color-coded level
// token, then the message — plain text, no UI pills.
function Line({ ev, t }: { ev: ActivityEvent; t: typeof THEME.dark }) {
  const meta = KIND_META[ev.kind] ?? { level: 'INFO' as Level, emoji: '', label: ev.kind.toUpperCase() };
  const color = LEVEL_META[meta.level].color;
  const isImportant = meta.level === 'ERROR' || meta.level === 'WARN' || ev.kind === 'order_placed';
  return (
    <div style={{
      display: 'flex', gap: 10, padding: '1px 0 1px 8px', alignItems: 'baseline',
      borderLeft: `2px solid ${isImportant ? color : 'transparent'}`,
      background: isImportant ? `${color}0d` : undefined,
      fontFamily: MONO, fontSize: 12, lineHeight: 1.55,
    }}>
      <span style={{ color: t.dim, flexShrink: 0 }}>{hhmmss(ev.ts_ms)}</span>
      <span style={{ flexShrink: 0, color, fontWeight: 700 }}>
        {meta.emoji ? `${meta.emoji} ` : ''}{meta.level}
      </span>
      <span style={{ color: t.text, whiteSpace: 'pre-wrap', minWidth: 0 }}>{ev.message}</span>
    </div>
  );
}

// ── Progress bar ─────────────────────────────────────────────────────────────
function ProgressBar({ label, t }: { label?: string; t: typeof THEME.dark }) {
  const prog = parseProgress(label);
  return (
    <div style={{ position: 'relative', height: 3, background: t.border, overflow: 'hidden', flexShrink: 0 }}>
      {prog ? (
        <div style={{
          height: '100%', width: `${prog.pct}%`, background: k.green,
          boxShadow: `0 0 6px ${k.green}`, transition: 'width .35s ease',
        }} />
      ) : (
        // Indeterminate: a travelling stripe.
        <div style={{
          position: 'absolute', top: 0, left: 0, height: '100%', width: '35%',
          background: `linear-gradient(90deg, transparent, ${k.green}, transparent)`,
          animation: 'kt-indet 1.1s linear infinite',
        }} />
      )}
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
  const [spin, setSpin] = useState(0);
  // Client-side clear: hide every event up to this timestamp. New events still
  // stream in (server is the source of truth) — this just clears the view.
  const [clearedBefore, setClearedBefore] = useState(0);

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
  const events = (data?.events ?? []).filter((ev) => ev.ts_ms > clearedBefore);
  const scanning = !!data?.scanning;

  const clearLog = () => {
    const latest = (data?.events ?? []).reduce((m, ev) => Math.max(m, ev.ts_ms), 0);
    setClearedBefore(latest || clearedBefore + 1);
  };

  // Spinner animation — only ticks while a scan is in flight.
  useEffect(() => {
    if (!scanning) { setSpin(0); return; }
    const id = setInterval(() => setSpin((s) => (s + 1) % SPINNER.length), 90);
    return () => clearInterval(id);
  }, [scanning]);

  useEffect(() => { localStorage.setItem('kite_terminal_theme', theme); }, [theme]);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [events.length]);

  const dot = scanning ? k.green : data?.auto_scan ? k.blue : t.dim;
  const spinner = SPINNER[spin];

  const btnStyle = { background: 'none', border: 'none', color: t.headDim, cursor: 'pointer', padding: '2px 6px', display: 'flex', alignItems: 'center', justifyContent: 'center' };

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      // When minimized, collapse to just the footer bar (auto height) so the
      // terminal can never balloon to fill a tall container — that bug made
      // "minimize" look like it went full screen. Otherwise fill the pane.
      height: mode === 'minimized' ? 'auto' : '100%',
      flexShrink: 0,
      background: t.bg, fontFamily: MONO,
    }}>
      <style>{KT_CSS}</style>
      {/* HEADER */}
      {mode !== 'minimized' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '6px 14px', borderBottom: `1px solid ${t.border}`, background: t.headerBg, fontSize: 11, color: t.headDim, flexShrink: 0 }}>
          <span style={{ fontWeight: 600, color: t.headTxt, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span>🖥️</span> KITE TERMINAL
          </span>

          <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 'auto' }}>
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

      {/* PROGRESS BAR — visible only while scanning */}
      {mode !== 'minimized' && scanning && <ProgressBar label={data?.scanning_label} t={t} />}

      {/* LOG AREA */}
      {mode !== 'minimized' && (
        <div ref={scrollRef} style={{ flex: 1, overflow: 'auto', padding: '8px 14px', fontSize: 12, lineHeight: 1.55, color: t.text, fontFamily: MONO }}>
          {events.length === 0 ? (
            <div style={{ color: t.dim, fontFamily: MONO }}>⏳ Waiting for background scan… the engine scans every ~5 min automatically.</div>
          ) : (
            events.map((ev, i) =>
              KIND_META[ev.kind]?.banner
                ? <Banner key={`${ev.ts_ms}:${i}`} ev={ev} t={t} />
                : <Line key={`${ev.ts_ms}:${i}`} ev={ev} t={t} />
            )
          )}
        </div>
      )}

      {/* FOOTER */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '5px 14px', background: t.headerBg, fontSize: 11, color: t.headDim, marginTop: 'auto', flexShrink: 0 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 600, color: t.headTxt }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: dot, boxShadow: scanning ? `0 0 5px ${k.green}` : 'none', flexShrink: 0 }} />
          TERMINAL
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: scanning ? k.green : data?.auto_scan ? k.orange : t.headDim, fontWeight: scanning ? 600 : 400 }}>
          {scanning && <span style={{ fontSize: 12, lineHeight: 1 }}>{spinner}</span>}
          {scanning ? data?.scanning_label || 'scanning…' : data?.auto_scan ? '🤖 auto' : '💤 idle'}
        </span>
        {!scanning && <span style={{ color: t.dim }}>🕐 last {data?.last_scan_ms ? hhmmss(data.last_scan_ms) : '—'}</span>}
        {!scanning && data?.auto_scan && <span style={{ color: t.dim }}>⏭️ next {fmtCountdown(data?.next_scan_ms ?? 0)}</span>}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          {(data?.signal_count ?? 0) > 0 && <span style={{ color: k.orange, fontWeight: 600 }}>🎯 {data?.signal_count} ready</span>}
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title="Toggle terminal theme"
            style={{ background: 'none', border: `1px solid ${t.border}`, color: t.headDim, borderRadius: 4, padding: '1px 8px', fontSize: 11, cursor: 'pointer' }}
          >
            {theme === 'dark' ? '☀ Light' : '🌙 Dark'}
          </button>
          <button
            onClick={clearLog}
            title="Clear terminal"
            disabled={events.length === 0}
            style={{ background: 'none', border: `1px solid ${t.border}`, color: t.headDim, borderRadius: 4, padding: '2px 6px', cursor: events.length === 0 ? 'default' : 'pointer', opacity: events.length === 0 ? 0.4 : 1, display: 'flex', alignItems: 'center' }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" />
            </svg>
          </button>
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
