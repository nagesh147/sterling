/**
 * SignalsTable — single unified trading tips table.
 * Each row is a complete, actionable trade: symbol, instrument, entry, SL, TP, time, BUY.
 * No tabs. No toggles. Just the signals.
 */
import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSignals } from '../hooks/useSignals';
import type { SignalItem } from '../hooks/useSignals';
import { usePositions } from '../hooks/usePositions';
import { api } from '../utils/api';

// ── helpers ───────────────────────────────────────────────────────────────────

function fp(v: number | null | undefined, dec = 2): string {
  if (v == null || !isFinite(v)) return '—';
  if (v >= 10_000) return '$' + v.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (v >= 100)   return '$' + v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
  return '$' + v.toFixed(4);
}

function pct(entry: number, level: number): string {
  const p = ((level - entry) / entry) * 100;
  return (p >= 0 ? '+' : '') + p.toFixed(1) + '%';
}

function fmtTime(ms: number): string {
  return new Date(ms).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
}

const STATE_PRIORITY: Record<string, number> = {
  ENTRY_ARMED_PULLBACK: 0, ENTRY_ARMED_CONTINUATION: 1,
  CONFIRMED_SETUP_ACTIVE: 2, EARLY_SETUP_ACTIVE: 3,
};

const DIR = {
  color: (d: string) => d === 'long' ? '#44cc88' : d === 'short' ? '#cc4444' : 'var(--text-faint)',
  label: (d: string) => d === 'long' ? 'BUY' : d === 'short' ? 'SELL' : '—',
  arrow: (d: string) => d === 'long' ? '▲' : d === 'short' ? '▼' : '',
};

const STATE_LABEL: Record<string, string> = {
  ENTRY_ARMED_PULLBACK: 'ARMED',
  ENTRY_ARMED_CONTINUATION: 'ARMED',
  CONFIRMED_SETUP_ACTIVE: 'CONFIRMED',
  EARLY_SETUP_ACTIVE: 'FORMING',
};

function useDirectEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      underlying: string; direction: string; instrument_type: string;
      size: number; leverage: number; order_type: string;
      stop_loss?: number | null; take_profit?: number | null;
      option_symbol?: string | null; notes: string;
    }) => api.post('/api/v1/trading/place-order', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['positions'] });
      qc.invalidateQueries({ queryKey: ['live-pnl'] });
    },
  });
}

// ── individual signal row ─────────────────────────────────────────────────────

interface TradeRow {
  id: string;
  signal: SignalItem;
  type: 'futures' | 'options';
}

function TipRow({ row, hasOpen }: { row: TradeRow; hasOpen: boolean }) {
  const { signal, type } = row;
  const [size, setSize] = useState(1);
  const [placing, setPlacing] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; msg: string } | null>(null);
  const { mutate: enter } = useDirectEntry();

  const isFutures = type === 'futures';
  const dirColor  = DIR.color(signal.direction);
  const stateLabel = STATE_LABEL[signal.state] ?? signal.state.replace(/_/g, ' ');

  const entry     = signal.spot_price ?? 0;
  const stopLoss  = signal.stop_price ?? null;
  const takeProfit = signal.target_price ?? null;
  const leverage  = signal.rec_leverage ?? 5;

  // Estimated premium for options (very rough: ~0.5% of spot × leverage factor)
  const optPremiumEst = entry > 0 ? Math.round(entry * 0.006) : null;

  const handleBuy = () => {
    if (hasOpen || placing) return;
    setPlacing(true);
    setFeedback(null);
    enter({
      underlying: signal.underlying,
      direction: signal.direction,
      instrument_type: isFutures ? 'futures' : 'options',
      size,
      leverage: isFutures ? leverage : 1,
      order_type: 'market',
      stop_loss: stopLoss,
      take_profit: takeProfit,
      option_symbol: !isFutures ? (signal.opt_symbol ?? null) : null,
      notes: `${stateLabel} · ${isFutures ? `${leverage}× futures` : signal.opt_symbol ?? 'options'}`,
    }, {
      onSuccess: () => {
        setFeedback({ ok: true, msg: '✅ Placed' });
        setPlacing(false);
        setTimeout(() => setFeedback(null), 3000);
      },
      onError: (e: unknown) => {
        setFeedback({ ok: false, msg: `❌ ${(e as Error).message}` });
        setPlacing(false);
      },
    });
  };

  return (
    <tr style={{ borderBottom: '1px solid var(--border)' }}>
      {/* TIME */}
      <td style={{ padding: '10px 12px', fontSize: 11, color: 'var(--text-dim)', whiteSpace: 'nowrap', verticalAlign: 'middle' }}>
        {fmtTime(signal.timestamp_ms)}
      </td>

      {/* SYMBOL + STATE */}
      <td style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
        <div style={{ fontSize: 14, fontWeight: 900, color: 'var(--text-primary)', letterSpacing: 1 }}>{signal.underlying}</div>
        <div style={{ fontSize: 9, color: dirColor, fontWeight: 700, letterSpacing: 0.5, marginTop: 2 }}>
          {DIR.arrow(signal.direction)} {DIR.label(signal.direction)} · {stateLabel}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 1 }}>{signal.regime.replace(/_/g, ' ')}</div>
      </td>

      {/* INSTRUMENT DETAILS */}
      <td style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
        {isFutures ? (
          <>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)' }}>
              {signal.futures_symbol ?? signal.underlying + 'USDT'}
            </div>
            <div style={{ fontSize: 10, color: '#88aaff', fontWeight: 700, marginTop: 2 }}>
              {leverage}× Leverage
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 1 }}>Perpetual Future</div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)' }}>
              {signal.opt_type === 'CE' ? 'CALL' : 'PUT'} {fp(signal.opt_strike, 0)}
            </div>
            <div style={{ fontSize: 10, color: '#f0c040', fontWeight: 700, marginTop: 2 }}>
              {signal.opt_expiry} · {signal.opt_dte} DTE
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 1 }}>
              {signal.opt_symbol ?? '—'}
            </div>
          </>
        )}
      </td>

      {/* ENTRY */}
      <td style={{ padding: '10px 12px', textAlign: 'right', verticalAlign: 'middle' }}>
        <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
          {isFutures ? fp(entry, 0) : (optPremiumEst ? `~$${optPremiumEst}` : '—')}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 2 }}>
          {isFutures ? 'Market' : 'Premium est.'}
        </div>
      </td>

      {/* STOP LOSS */}
      <td style={{ padding: '10px 12px', textAlign: 'right', verticalAlign: 'middle' }}>
        {isFutures ? (
          <>
            <div style={{ fontSize: 13, fontWeight: 800, color: '#cc4444', fontVariantNumeric: 'tabular-nums' }}>
              {fp(stopLoss, 0)}
            </div>
            <div style={{ fontSize: 9, color: '#cc444488', marginTop: 2 }}>
              {stopLoss && entry ? pct(entry, stopLoss) : '—'}
            </div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 13, fontWeight: 800, color: '#cc4444' }}>
              {optPremiumEst ? `~$${Math.round(optPremiumEst * 0.5)}` : '—'}
            </div>
            <div style={{ fontSize: 9, color: '#cc444488', marginTop: 2 }}>-50% premium</div>
          </>
        )}
      </td>

      {/* TAKE PROFIT */}
      <td style={{ padding: '10px 12px', textAlign: 'right', verticalAlign: 'middle' }}>
        {isFutures ? (
          <>
            <div style={{ fontSize: 13, fontWeight: 800, color: '#44cc88', fontVariantNumeric: 'tabular-nums' }}>
              {fp(takeProfit, 0)}
            </div>
            <div style={{ fontSize: 9, color: '#44cc8888', marginTop: 2 }}>
              {takeProfit && entry ? pct(entry, takeProfit) : '—'}
            </div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 13, fontWeight: 800, color: '#44cc88' }}>
              {optPremiumEst ? `~$${Math.round(optPremiumEst * 2)}` : '—'}
            </div>
            <div style={{ fontSize: 9, color: '#44cc8888', marginTop: 2 }}>+100% premium</div>
          </>
        )}
      </td>

      {/* SCORE */}
      <td style={{ padding: '10px 12px', textAlign: 'center', verticalAlign: 'middle' }}>
        <div style={{
          fontSize: 16, fontWeight: 900,
          color: (signal.direction === 'long' ? signal.score_long : signal.score_short) >= 75 ? '#44cc88'
               : (signal.direction === 'long' ? signal.score_long : signal.score_short) >= 55 ? '#f0c040' : 'var(--text-dim)',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {signal.direction === 'long' ? signal.score_long.toFixed(0) : signal.score_short.toFixed(0)}
        </div>
        <div style={{ fontSize: 8, color: 'var(--text-faint)' }}>/100</div>
      </td>

      {/* ACTION */}
      <td style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
          {feedback ? (
            <div style={{ fontSize: 10, color: feedback.ok ? '#44cc88' : '#cc4444', fontWeight: 700 }}>
              {feedback.msg}
            </div>
          ) : (
            <>
              {/* size control */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                <button onClick={() => setSize(s => Math.max(1, s - 1))} style={sizeBtn}>&minus;</button>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 16, textAlign: 'center', fontVariantNumeric: 'tabular-nums' }}>{size}</span>
                <button onClick={() => setSize(s => s + 1)} style={sizeBtn}>+</button>
              </div>
              <button
                onClick={handleBuy}
                disabled={hasOpen || placing || signal.direction === 'neutral'}
                style={{
                  padding: '7px 14px',
                  background: hasOpen ? 'var(--bg)' : signal.direction === 'long' ? '#0f2a0f' : '#2a0f0f',
                  color: hasOpen ? 'var(--text-faint)' : dirColor,
                  border: `1px solid ${hasOpen ? 'var(--border)' : dirColor + '88'}`,
                  borderRadius: 4, cursor: hasOpen || placing ? 'default' : 'pointer',
                  fontFamily: 'inherit', fontSize: 11, fontWeight: 800, letterSpacing: 0.5,
                  opacity: signal.direction === 'neutral' ? 0.3 : 1,
                  whiteSpace: 'nowrap',
                }}
              >
                {placing ? '…' : hasOpen ? 'OPEN' : `${DIR.label(signal.direction)} NOW`}
              </button>
            </>
          )}
        </div>
      </td>
    </tr>
  );
}

const sizeBtn: React.CSSProperties = {
  width: 20, height: 20, borderRadius: 3, border: '1px solid var(--border)',
  background: 'var(--bg)', color: 'var(--text-muted)',
  cursor: 'pointer', fontFamily: 'inherit', fontSize: 13, lineHeight: '18px',
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0,
};

// ── main table ────────────────────────────────────────────────────────────────

export function SignalsTable() {
  const { data, isLoading } = useSignals();
  const { data: posData } = usePositions();

  const openByUnderlying: Record<string, number> = {};
  (posData?.positions ?? []).forEach(p => {
    if (p.status === 'open' || p.status === 'partially_closed')
      openByUnderlying[p.underlying] = (openByUnderlying[p.underlying] ?? 0) + 1;
  });

  // Build rows: filter actionable signals, generate futures + options rows
  const rows: TradeRow[] = [];
  const signals = (data?.signals ?? [])
    .filter(s => s.fresh && s.direction !== 'neutral' && STATE_PRIORITY[s.state] !== undefined)
    .sort((a, b) => (STATE_PRIORITY[a.state] ?? 9) - (STATE_PRIORITY[b.state] ?? 9));

  for (const s of signals) {
    rows.push({ id: `${s.underlying}_futures`, signal: s, type: 'futures' });
    if (s.has_options && s.opt_symbol) {
      rows.push({ id: `${s.underlying}_options`, signal: s, type: 'options' });
    }
  }

  const ts = data?.timestamp_ms
    ? new Date(data.timestamp_ms).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })
    : '';

  return (
    <div style={{ marginBottom: 16, borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)' }}>

      {/* header */}
      <div style={{
        background: '#14291a', borderBottom: '1px solid #1e3a22',
        padding: '10px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: '#44cc88', fontSize: 12, fontWeight: 900, letterSpacing: 2 }}>● LIVE SIGNALS</span>
          {rows.length > 0 && (
            <span style={{
              fontSize: 10, color: '#f0c040', fontWeight: 700,
              background: '#f0c04018', border: '1px solid #f0c04044',
              borderRadius: 3, padding: '1px 8px',
            }}>
              {rows.length} tips
            </span>
          )}
        </div>
        <span style={{ fontSize: 10, color: '#1e3a22', fontVariantNumeric: 'tabular-nums' }}>
          {isLoading ? 'refreshing…' : ts}
        </span>
      </div>

      {/* no signals state */}
      {!isLoading && rows.length === 0 && (
        <div style={{ background: 'var(--bg-card)', padding: '28px 20px', textAlign: 'center' }}>
          <div style={{ fontSize: 13, color: 'var(--text-faint)', marginBottom: 6 }}>
            No actionable signals right now
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>
            Watching {data?.signals?.filter(s => s.fresh)?.length ?? 0} instruments · signals generate when regime + price align
          </div>
        </div>
      )}

      {/* table */}
      {rows.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', background: 'var(--bg-card)' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                {['TIME', 'SYMBOL', 'INSTRUMENT', 'ENTRY', 'STOP LOSS', 'TAKE PROFIT', 'SCORE', 'ACTION'].map(h => (
                  <th key={h} style={{
                    padding: '8px 12px', fontSize: 9, color: 'var(--text-faint)',
                    letterSpacing: 1.5, fontWeight: 700, textAlign: h === 'ACTION' ? 'center' : h === 'SCORE' ? 'center' : h === 'ENTRY' || h === 'STOP LOSS' || h === 'TAKE PROFIT' ? 'right' : 'left',
                    background: 'var(--bg)', whiteSpace: 'nowrap',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <React.Fragment key={row.id}>
                  {/* separator between different underlyings */}
                  {i > 0 && rows[i - 1].signal.underlying !== row.signal.underlying && (
                    <tr><td colSpan={8} style={{ height: 1, background: 'var(--border-light)', padding: 0 }} /></tr>
                  )}
                  <TipRow row={row} hasOpen={(openByUnderlying[row.signal.underlying] ?? 0) > 0} />
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* footer */}
      <div style={{
        padding: '7px 14px', background: 'var(--bg)',
        borderTop: '1px solid var(--border)',
        display: 'flex', gap: 16, fontSize: 9, color: 'var(--text-faint)',
      }}>
        <span>SL/TP based on ATR · 2:1 R:R</span>
        <span>·</span>
        <span>Options premium estimated · verify on exchange before trading</span>
        <span>·</span>
        <span>Paper mode unless Delta India credentials configured</span>
      </div>
    </div>
  );
}
