/**
 * SignalsTable — append-only trading signal feed.
 *
 * New signals appear at the top; existing rows never reorder.
 * Scroll down to see older signals. Works like an Instagram feed.
 */
import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSignalFeed } from '../hooks/useSignalFeed';
import type { FeedEntry } from '../hooks/useSignalFeed';
import { usePositions } from '../hooks/usePositions';
import { api } from '../utils/api';

// ── helpers ───────────────────────────────────────────────────────────────────

function fp(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return '—';
  if (v >= 10_000) return '$' + v.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (v >= 100)   return '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 });
  return '$' + v.toFixed(2);
}

function pct(entry: number, level: number): string {
  const p = ((level - entry) / entry) * 100;
  return (p >= 0 ? '+' : '') + p.toFixed(1) + '%';
}

function fmtTime(ms: number): string {
  return new Date(ms).toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: true,
  });
}

function fmtAge(ms: number): string {
  const diff = Date.now() - ms;
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  return `${Math.floor(diff / 3_600_000)}h ago`;
}

const STATE_COLOR: Record<string, string> = {
  ENTRY_ARMED_PULLBACK: '#44aaff',
  ENTRY_ARMED_CONTINUATION: '#66ccff',
  CONFIRMED_SETUP_ACTIVE: 'var(--warning)',
  EARLY_SETUP_ACTIVE: '#f0a500',
};

const STATE_SHORT: Record<string, string> = {
  ENTRY_ARMED_PULLBACK: 'ARMED',
  ENTRY_ARMED_CONTINUATION: 'ARMED',
  CONFIRMED_SETUP_ACTIVE: 'CONFIRMED',
  EARLY_SETUP_ACTIVE: 'FORMING',
  FILTERED: 'FILTERED',
  IDLE: 'IDLE',
};

function useDirectEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: object) => api.post('/api/v1/trading/place-order', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['positions'] });
      qc.invalidateQueries({ queryKey: ['live-pnl'] });
    },
  });
}

// ── single feed row ───────────────────────────────────────────────────────────

function FeedRow({ entry, hasOpen, onDismiss }: {
  entry: FeedEntry;
  hasOpen: boolean;
  onDismiss: () => void;
}) {
  const [size, setSize] = useState(1);
  const [feedback, setFeedback] = useState('');
  const [placing, setPlacing] = useState(false);
  const { mutate: trade } = useDirectEntry();

  const isFutures = entry.type === 'futures';
  const dirColor  = entry.direction === 'long' ? 'var(--accent)' : 'var(--danger)';
  const bgDark    = entry.direction === 'long' ? '#003d2e' : '#3d0014';
  const side      = entry.direction === 'long' ? 'BUY' : 'SELL';
  const arrow     = entry.direction === 'long' ? '▲' : '▼';
  const stColor   = STATE_COLOR[entry.currentState] ?? 'var(--text-dim)';
  const stLabel   = STATE_SHORT[entry.currentState] ?? '—';

  // Live P&L vs entry
  const livePnl = entry.currentPrice && entry.entry
    ? (entry.direction === 'long'
        ? (entry.currentPrice - entry.entry) / entry.entry * 100
        : (entry.entry - entry.currentPrice) / entry.entry * 100)
    : null;

  // Options premium estimate
  const optPrem    = isFutures ? null : Math.round(entry.entry * 0.01);
  const optSL      = optPrem ? Math.round(optPrem * 0.5) : null;
  const optTP      = optPrem ? Math.round(optPrem * 2) : null;

  const handleTrade = () => {
    if (hasOpen || placing) return;
    setPlacing(true);
    trade({
      underlying: entry.underlying,
      direction: entry.direction,
      instrument_type: entry.type,
      size,
      leverage: entry.leverage,
      order_type: 'market',
      stop_loss: entry.stopLoss,
      take_profit: entry.takeProfit,
      option_symbol: !isFutures ? entry.optSymbol : null,
      notes: `Feed entry — ${stLabel}`,
    }, {
      onSuccess: () => { setFeedback('✅ Placed'); setPlacing(false); },
      onError: (e: unknown) => { setFeedback(`❌ ${(e as Error).message}`); setPlacing(false); },
    });
  };

  return (
    <div style={{
      display: 'flex', gap: 0, alignItems: 'stretch',
      borderLeft: `3px solid ${dirColor}`,
      borderBottom: '1px solid var(--border)',
      background: entry.dismissed ? 'var(--bg)' : 'var(--bg-card)',
      opacity: entry.dismissed ? 0.4 : 1,
      transition: 'opacity 0.3s',
    }}>
      {/* LEFT — time + symbol */}
      <div style={{ width: 130, flexShrink: 0, padding: '12px 10px 12px 12px', borderRight: '1px solid var(--border)' }}>
        <div style={{ fontSize: 10, color: 'var(--text-faint)', marginBottom: 2 }}>{fmtTime(entry.entryAt)}</div>
        <div style={{ fontSize: 14, fontWeight: 900, color: 'var(--text-primary)', letterSpacing: 0.5 }}>{entry.underlying}</div>
        <div style={{ fontSize: 10, fontWeight: 700, color: dirColor, marginTop: 2 }}>
          {arrow} {side}
        </div>
        <div style={{ fontSize: 8, color: stColor, marginTop: 3, letterSpacing: 0.5, fontWeight: 700 }}>{stLabel}</div>
        <div style={{ fontSize: 8, color: 'var(--text-faint)', marginTop: 2 }}>{fmtAge(entry.entryAt)}</div>
      </div>

      {/* CENTRE — instrument + prices */}
      <div style={{ flex: 1, padding: '12px 10px', minWidth: 0 }}>
        {/* instrument */}
        <div style={{ marginBottom: 8 }}>
          {isFutures ? (
            <span style={{ fontSize: 11, color: '#88aaff', fontWeight: 700 }}>
              {entry.futuresSymbol} · {entry.leverage}× lev
            </span>
          ) : (
            <span style={{ fontSize: 11, color: 'var(--warning)', fontWeight: 700 }}>
              {entry.optType === 'CE' ? 'CALL' : 'PUT'} {fp(entry.optStrike)} · {entry.optExpiry} · {entry.optDte} DTE
            </span>
          )}
          <span style={{ marginLeft: 8, fontSize: 9, color: 'var(--text-faint)' }}>
            {entry.regime.replace(/_/g, ' ')} · Score {entry.score}
          </span>
        </div>

        {/* price grid */}
        <div style={{ display: 'flex', gap: 8 }}>
          {[
            { label: 'ENTRY', val: isFutures ? fp(entry.entry) : `~$${optPrem}`, color: 'var(--text-primary)', sub: '' },
            { label: 'STOP LOSS', val: isFutures ? fp(entry.stopLoss) : `~$${optSL}`, color: 'var(--danger)', sub: entry.stopLoss && isFutures ? pct(entry.entry, entry.stopLoss) : '-50%' },
            { label: 'TAKE PROFIT', val: isFutures ? fp(entry.takeProfit) : `~$${optTP}`, color: 'var(--accent)', sub: entry.takeProfit && isFutures ? pct(entry.entry, entry.takeProfit) : '+100%' },
          ].map(({ label, val, color, sub }) => (
            <div key={label} style={{
              background: 'var(--bg)', border: '1px solid var(--border)',
              borderRadius: 4, padding: '5px 8px', textAlign: 'center', minWidth: 70,
            }}>
              <div style={{ fontSize: 7, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 2 }}>{label}</div>
              <div style={{ fontSize: 12, fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>{val}</div>
              {sub && <div style={{ fontSize: 8, color: 'var(--text-dim)' }}>{sub}</div>}
            </div>
          ))}

          {/* Live price — only meaningful for futures (options premium ≠ spot price) */}
          {isFutures && entry.currentPrice && (
            <div style={{
              background: 'var(--bg)', border: `1px solid ${livePnl != null && livePnl >= 0 ? '#00d4aa44' : '#ff475744'}`,
              borderRadius: 4, padding: '5px 8px', textAlign: 'center', minWidth: 70,
            }}>
              <div style={{ fontSize: 7, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 2 }}>NOW</div>
              <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                {fp(entry.currentPrice)}
              </div>
              {livePnl != null && (
                <div style={{
                  fontSize: 8, fontWeight: 700,
                  color: livePnl >= 0 ? 'var(--accent)' : 'var(--danger)',
                }}>
                  {livePnl >= 0 ? '+' : ''}{livePnl.toFixed(1)}%
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* RIGHT — action */}
      <div style={{
        width: 110, flexShrink: 0, padding: '12px 10px',
        borderLeft: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', gap: 6, justifyContent: 'center',
      }}>
        {feedback ? (
          <div style={{ fontSize: 10, color: feedback.startsWith('✅') ? 'var(--accent)' : 'var(--danger)', textAlign: 'center', fontWeight: 700 }}>
            {feedback}
          </div>
        ) : (
          <>
            {/* size */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'center' }}>
              <button onClick={() => setSize(s => Math.max(1, s - 1))} style={sBtn}>&minus;</button>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 16, textAlign: 'center' }}>{size}</span>
              <button onClick={() => setSize(s => s + 1)} style={sBtn}>+</button>
            </div>
            {/* trade */}
            <button
              onClick={handleTrade}
              disabled={hasOpen || placing}
              style={{
                padding: '7px 0', borderRadius: 4, cursor: hasOpen ? 'default' : 'pointer',
                background: hasOpen ? 'var(--bg)' : bgDark,
                color: hasOpen ? 'var(--text-faint)' : dirColor,
                border: `1px solid ${hasOpen ? 'var(--border)' : dirColor + 'cc'}`,
                fontFamily: 'inherit', fontSize: 10, fontWeight: 800, letterSpacing: 0.5,
                opacity: placing ? 0.6 : 1,
              }}
            >
              {placing ? '…' : hasOpen ? 'OPEN' : `${side} NOW`}
            </button>
            {/* dismiss */}
            <button
              onClick={onDismiss}
              style={{
                padding: '3px 0', background: 'none',
                border: '1px solid var(--border)', borderRadius: 3,
                color: 'var(--text-faint)', cursor: 'pointer',
                fontFamily: 'inherit', fontSize: 9,
              }}
            >
              dismiss
            </button>
          </>
        )}
      </div>
    </div>
  );
}

const sBtn: React.CSSProperties = {
  width: 20, height: 20, borderRadius: 3, border: '1px solid var(--border)',
  background: 'var(--bg)', color: 'var(--text-muted)',
  cursor: 'pointer', fontFamily: 'inherit', fontSize: 13,
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0,
};

// ── main component ────────────────────────────────────────────────────────────

export function SignalsTable() {
  const { feed, dismiss, clearAll } = useSignalFeed();
  const { data: posData } = usePositions();

  const openByUnderlying: Record<string, number> = {};
  (posData?.positions ?? []).forEach(p => {
    if (p.status === 'open' || p.status === 'partially_closed')
      openByUnderlying[p.underlying] = (openByUnderlying[p.underlying] ?? 0) + 1;
  });

  const visible = feed.filter(e => !e.dismissed);
  const active  = visible.filter(e =>
    ['ENTRY_ARMED_PULLBACK','ENTRY_ARMED_CONTINUATION','CONFIRMED_SETUP_ACTIVE','EARLY_SETUP_ACTIVE']
      .includes(e.currentState)
  ).length;

  return (
    <div style={{ marginBottom: 16, borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)' }}>

      {/* header */}
      <div style={{
        background: 'linear-gradient(90deg, #071a14, #0a1f2e)',
        borderBottom: '1px solid var(--border)',
        padding: '10px 14px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: 'var(--accent)', fontSize: 12, fontWeight: 900, letterSpacing: 2 }}>
            ● LIVE SIGNALS
          </span>
          {active > 0 && (
            <span style={{
              fontSize: 10, fontWeight: 700, color: 'var(--warning)',
              background: 'rgba(255,165,2,0.12)', border: '1px solid rgba(255,165,2,0.3)',
              borderRadius: 3, padding: '1px 7px',
            }}>
              {active} actionable
            </span>
          )}
          {visible.length > 0 && (
            <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>
              {visible.length} in feed
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>newest ↑ · scroll for history</span>
          {feed.length > 0 && (
            <button
              onClick={clearAll}
              style={{
                background: 'none', border: '1px solid var(--border)',
                color: 'var(--text-faint)', borderRadius: 3, padding: '2px 8px',
                cursor: 'pointer', fontFamily: 'inherit', fontSize: 9,
              }}
            >
              clear
            </button>
          )}
        </div>
      </div>

      {/* empty state */}
      {visible.length === 0 && (
        <div style={{
          background: 'var(--bg-card)', padding: '32px 20px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 13, color: 'var(--text-faint)', marginBottom: 8 }}>
            Watching for signals…
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>
            New signals appear here instantly. Scroll down to see history.
          </div>
        </div>
      )}

      {/* scrollable feed */}
      {visible.length > 0 && (
        <div style={{ maxHeight: 520, overflowY: 'auto', scrollbarWidth: 'thin' }}>
          {visible.map(entry => (
            <FeedRow
              key={entry.id}
              entry={entry}
              hasOpen={(openByUnderlying[entry.underlying] ?? 0) > 0}
              onDismiss={() => dismiss(entry.id)}
            />
          ))}
        </div>
      )}

      {/* footer */}
      <div style={{
        padding: '6px 14px', background: 'var(--bg)',
        borderTop: '1px solid var(--border)',
        fontSize: 9, color: 'var(--text-faint)', display: 'flex', gap: 12,
      }}>
        <span>Prices frozen at signal time · NOW column = live price</span>
        <span>·</span>
        <span>Options premium estimated · verify on exchange</span>
        <span>·</span>
        <span>Paper unless Delta India credentials set</span>
      </div>
    </div>
  );
}
