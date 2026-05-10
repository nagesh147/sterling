/**
 * SignalsTable — append-only trading signal feed.
 *
 * New signals appear at the top; existing rows never reorder.
 * Scroll down to see older signals. Works like an Instagram feed.
 */
import React, { useMemo, useState, memo } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSignalFeed } from '../hooks/useSignalFeed';
import type { FeedEntry } from '../hooks/useSignalFeed';
import { usePositions } from '../hooks/usePositions';
import { useSignals } from '../hooks/useSignals';
import { useTradingMode } from '../hooks/useTradingMode';
import { useExchanges } from '../hooks/useExchanges';
import { useAccountSummary } from '../hooks/useAccount';
import { fpPrice, MODE_COLOR, inferModeTag } from '../utils/fmt';
import { api } from '../utils/api';

// ── helpers ───────────────────────────────────────────────────────────────────

// Delta Exchange India lot sizes (1 lot = N underlying units)
const LOT_SIZES: Record<string, { lotSize: number; unit: string }> = {
  BTC: { lotSize: 0.001, unit: 'BTC' },
  ETH: { lotSize: 0.01,  unit: 'ETH' },
  SOL: { lotSize: 1.0,   unit: 'SOL' },
};

// Resolve the display mode for an entry — old entries stamped 'all' get re-inferred.
function resolveMode(e: FeedEntry): string {
  if (e.mode !== 'all') return e.mode;
  return inferModeTag(e.adx ?? 0, e.atr_percentile ?? 0, e.score);
}

const fp = fpPrice; // local alias kept for brevity across this file

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

function tradeLabel(placing: boolean, hasOpen: boolean, isLive: boolean, side: string): string {
  if (placing) return '…';
  if (hasOpen) return 'OPEN';
  return isLive ? `${side} — LIVE` : `${side} NOW`;
}

// memo: skip re-render when entry object reference, hasOpen, and onDismiss are unchanged.
// Combined with the setFeed same-ref optimisation, this eliminates re-renders of
// unchanged rows on every 15s poll — the main GC pressure source.
const FeedRow = memo(function FeedRow({ entry, hasOpen, isLive, availFunds, showModeTag, onDismiss }: {
  entry: FeedEntry;
  hasOpen: boolean;
  isLive: boolean;
  availFunds: number | null;
  showModeTag: boolean;       // true only in ALL mode — redundant otherwise
  onDismiss: () => void;
}) {
  const [leverage, setLeverage]     = useState(entry.leverage);
  const [currency, setCurrency]     = useState<'USD'|'INR'>('USD');
  const [qtyValue, setQtyValue]     = useState('1');
  const [qtyUnit, setQtyUnit]       = useState<'lot'|'usd'|string>('lot');
  const [orderType, setOrderType]   = useState<'market'|'limit'>('market');
  const [limitPrice, setLimitPrice] = useState('');
  const [showBracket, setShowBracket] = useState(false);
  const [feedback, setFeedback]     = useState('');   // row-level (post-dismiss)
  const [placing, setPlacing]       = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [modalStatus, setModalStatus] = useState<{ type: 'idle'|'pending'|'success'|'error'; msg: string }>({ type: 'idle', msg: '' });
  const { mutate: trade }           = useDirectEntry();

  const USD_INR   = 84.5; // approximate; shown as estimate only
  const lotInfo   = LOT_SIZES[entry.underlying] ?? { lotSize: 1, unit: entry.underlying };
  const spotPrice = entry.currentPrice ?? entry.entry;

  const size = useMemo(() => {
    const n = parseFloat(qtyValue) || 0;
    if (qtyUnit === 'lot') return Math.max(1, Math.round(n));
    if (qtyUnit === 'usd') return Math.max(1, Math.round(n / (spotPrice * lotInfo.lotSize)));
    return Math.max(1, Math.round(n / lotInfo.lotSize));
  }, [qtyValue, qtyUnit, spotPrice, lotInfo.lotSize]);

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
  const optPrem = isFutures ? null : Math.round(entry.entry * 0.01);
  const optSL   = optPrem ? Math.round(optPrem * 0.5) : null;
  const optTP   = optPrem ? Math.round(optPrem * 2) : null;

  // Order cost: margin = (notional / leverage) for futures; premium for options
  const notionalUsd  = isFutures ? spotPrice * size * lotInfo.lotSize : (optPrem ?? 0) * size;
  const marginUsd    = isFutures ? notionalUsd / leverage : notionalUsd;
  // availFunds is passed as a prop — lifted to parent to avoid one hook per row
  const insufficientFunds = availFunds !== null && marginUsd > availFunds;

  const fmtCost = (usd: number) => {
    const v = currency === 'INR' ? usd * USD_INR : usd;
    const sym = currency === 'INR' ? '₹' : '$';
    return `${sym}${v.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
  };

  // Qty hint: what the current qty equals in other units
  const qtyLots = size;
  const qtyInUnderlying = (qtyLots * lotInfo.lotSize).toFixed(
    lotInfo.lotSize < 0.01 ? 4 : lotInfo.lotSize < 1 ? 3 : 1
  );
  const qtyInUsd = (qtyLots * lotInfo.lotSize * spotPrice).toLocaleString('en-US', { maximumFractionDigits: 0 });

  const closeModal = () => {
    setShowConfirm(false);
    setModalStatus({ type: 'idle', msg: '' });
  };

  const submitOrder = () => {
    // Keep modal open — user sees status inside it
    setModalStatus({ type: 'pending', msg: 'Placing order…' });
    setPlacing(true);
    trade({
      underlying: entry.underlying,
      direction: entry.direction,
      instrument_type: entry.type,
      size,
      leverage,
      order_type: orderType,
      limit_price: orderType === 'limit' && limitPrice ? parseFloat(limitPrice) : undefined,
      stop_loss: entry.stopLoss,
      take_profit: entry.takeProfit,
      option_symbol: !isFutures ? entry.optSymbol : null,
      notes: `Feed entry — ${stLabel}`,
    }, {
      onSuccess: (data: any) => {
        const orderId = data?.order_id ?? data?.paper_position_id ?? '';
        const mode    = data?.mode === 'live' ? 'Live' : 'Paper';
        setModalStatus({ type: 'success', msg: `${mode} order placed${orderId ? ` · ID ${orderId}` : ''}` });
        setPlacing(false);
        setFeedback('✅ Placed');
      },
      onError: (e: unknown) => {
        const msg = (e as Error).message ?? 'Unknown error';
        setModalStatus({ type: 'error', msg });
        setPlacing(false);
      },
    });
  };

  const handleTrade = () => {
    if (hasOpen || placing) return;
    setModalStatus({ type: 'idle', msg: '' });
    setShowConfirm(true);
  };

  return (
    <>
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
            {showModeTag && entry.mode && (() => {
              const tag = resolveMode(entry);
              const tagColor = MODE_COLOR[tag] ?? 'var(--text-dim)';
              return (
                <span style={{ marginLeft: 6, fontSize: 8, fontWeight: 700,
                  color: tagColor, background: 'rgba(0,0,0,0.3)', borderRadius: 2, padding: '1px 4px',
                }}>
                  {tag.toUpperCase()}
                </span>
              );
            })()}
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
        width: 100, flexShrink: 0, padding: '12px 10px',
        borderLeft: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', gap: 6, justifyContent: 'center',
      }}>
        {feedback ? (
          <div style={{ fontSize: 10, color: feedback.startsWith('✅') ? 'var(--accent)' : 'var(--danger)', textAlign: 'center', fontWeight: 700 }}>
            {feedback}
          </div>
        ) : (
          <button
            onClick={handleTrade}
            disabled={hasOpen || placing}
            style={{
              padding: '9px 0', borderRadius: 4, cursor: hasOpen ? 'default' : 'pointer',
              background: hasOpen ? 'var(--bg)' : bgDark,
              color: hasOpen ? 'var(--text-faint)' : dirColor,
              border: `1px solid ${hasOpen ? 'var(--border)' : dirColor + 'cc'}`,
              fontFamily: 'inherit', fontSize: 10, fontWeight: 800, letterSpacing: 0.5,
              opacity: placing ? 0.6 : 1,
            }}
          >
            {tradeLabel(placing, hasOpen, isLive, side)}
          </button>
        )}
      </div>
    </div>

    {/* ── Order confirmation modal ─────────────────────────────────── */}
    {showConfirm && (
      <div
        onClick={modalStatus.type === 'pending' ? undefined : closeModal}
        style={{
          position: 'fixed', inset: 0, zIndex: 4000,
          background: 'rgba(0,0,0,0.75)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <div
          onClick={e => e.stopPropagation()}
          style={{
            background: '#151b1e',
            border: '1px solid #2a3038',
            borderRadius: 10, width: 340,
            boxShadow: '0 12px 48px rgba(0,0,0,0.7)',
            overflow: 'hidden',
          }}
        >
          {/* ── contract + close ── */}
          <div style={{ padding: '10px 16px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--text-primary)' }}>
                {isFutures ? entry.futuresSymbol : `${entry.optType === 'CE' ? 'CALL' : 'PUT'} ${fp(entry.optStrike)}`}
              </span>
              <span style={{
                fontSize: 8, fontWeight: 700, letterSpacing: 0.5,
                color: isLive ? 'var(--accent)' : '#88aaff',
                background: isLive ? 'var(--accent)15' : '#88aaff15',
                border: `1px solid ${isLive ? 'var(--accent)33' : '#88aaff33'}`,
                borderRadius: 3, padding: '1px 5px',
              }}>
                {isLive ? '● LIVE' : 'PAPER'}
              </span>
            </div>
            <button
              onClick={modalStatus.type === 'pending' ? undefined : closeModal}
              style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: 16, lineHeight: 1, padding: '4px' }}
            >✕</button>
          </div>

          {/* ── Buy | Long / Sell | Short tabs ── */}
          <div style={{ display: 'flex', margin: '12px 16px 0', borderRadius: 6, overflow: 'hidden', border: '1px solid #2a3038' }}>
            {(['long','short'] as const).map(d => {
              const active = d === entry.direction;
              const col    = d === 'long' ? '#1ed760' : '#ff4757';
              const bg     = active ? (d === 'long' ? '#0d2e1a' : '#2e0d12') : 'transparent';
              return (
                <div key={d} style={{
                  flex: 1, textAlign: 'center', padding: '10px 0',
                  background: bg,
                  color: active ? col : '#555',
                  fontWeight: 800, fontSize: 13, letterSpacing: 0.3,
                  cursor: 'default',
                  borderRight: d === 'long' ? '1px solid #2a3038' : 'none',
                }}>
                  {d === 'long' ? 'Buy | Long' : 'Sell | Short'}
                </div>
              );
            })}
          </div>

          <div style={{ padding: '0 16px 16px' }}>

          {/* ── Leverage row ── */}
          {isFutures && (
            <div style={{ marginTop: 12, padding: '10px 12px', background: '#1c2228', borderRadius: 6, border: '1px solid #2a3038' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 12, color: '#aaa' }}>Leverage</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <button onClick={() => setLeverage(l => Math.max(1, l - 1))} style={{ ...sBtn, background: '#252d35' }}>&minus;</button>
                  <span style={{
                    fontSize: 15, fontWeight: 800, minWidth: 44, textAlign: 'center',
                    color: leverage !== entry.leverage ? '#f0c040' : '#1ed760',
                    fontVariantNumeric: 'tabular-nums',
                  }}>{leverage}×</span>
                  <button onClick={() => setLeverage(l => Math.min(100, l + 1))} style={{ ...sBtn, background: '#252d35' }}>+</button>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                {[5,10,20,50,100].map(l => (
                  <button key={l} onClick={() => setLeverage(l)} style={{
                    flex: 1, padding: '4px 0', borderRadius: 4, fontFamily: 'inherit',
                    fontSize: 10, fontWeight: 700, cursor: 'pointer',
                    background: leverage === l ? '#253020' : '#252d35',
                    color: leverage === l ? '#1ed760' : '#666',
                    border: `1px solid ${leverage === l ? '#1ed76044' : '#2a3038'}`,
                  }}>{l}×</button>
                ))}
              </div>
              {leverage !== entry.leverage && (
                <div style={{ marginTop: 6, fontSize: 9, color: '#f0c040' }}>
                  Signal suggests {entry.leverage}× (ADX {entry.adx?.toFixed(0)}) — higher leverage increases liquidation risk
                </div>
              )}
            </div>
          )}

          {/* ── Order type tabs ── */}
          <div style={{ display: 'flex', gap: 0, marginTop: 12, borderBottom: '1px solid #2a3038' }}>
            {(['market','limit'] as const).map(t => (
              <button key={t} onClick={() => setOrderType(t)} style={{
                background: 'none', border: 'none', padding: '7px 14px',
                fontFamily: 'inherit', fontSize: 12, fontWeight: 700, cursor: 'pointer',
                color: orderType === t ? '#1ed760' : '#555',
                borderBottom: orderType === t ? '2px solid #1ed760' : '2px solid transparent',
                marginBottom: -1,
              }}>
                {t === 'market' ? 'Market' : 'Limit'}
              </button>
            ))}
          </div>

          {/* ── Price row ── */}
          <div style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: '#aaa' }}>{orderType === 'limit' ? 'Limit Price' : 'Market Price'}</span>
              {orderType === 'market' && (
                <span style={{ fontSize: 11, color: '#555' }}>
                  ~{fp(entry.currentPrice ?? entry.entry)}
                </span>
              )}
            </div>
            {orderType === 'limit' ? (
              <div style={{ display: 'flex', alignItems: 'center', background: '#1c2228', border: '1px solid #2a3038', borderRadius: 6, padding: '0 12px' }}>
                <input
                  type="number" value={limitPrice}
                  onChange={e => setLimitPrice(e.target.value)}
                  placeholder={String(Math.round(entry.currentPrice ?? entry.entry))}
                  style={{ flex: 1, background: 'none', border: 'none', color: 'var(--text-primary)', fontFamily: 'inherit', fontSize: 14, fontWeight: 700, padding: '9px 0', outline: 'none', fontVariantNumeric: 'tabular-nums' }}
                />
                <span style={{ fontSize: 11, color: '#555', flexShrink: 0 }}>USD</span>
              </div>
            ) : (
              <div style={{ padding: '9px 12px', background: '#1c2228', border: '1px solid #2a3038', borderRadius: 6, color: '#f0c040', fontSize: 13, fontWeight: 700 }}>
                Best {entry.direction === 'long' ? 'Ask' : 'Bid'} &nbsp;<span style={{ color: '#666', fontWeight: 400, fontSize: 11 }}>USD</span>
              </div>
            )}
          </div>

          {/* ── Quantity ── */}
          <div style={{ marginTop: 12 }}>
            <span style={{ fontSize: 12, color: '#aaa' }}>Quantity</span>
            <div style={{ display: 'flex', alignItems: 'center', background: '#1c2228', border: '1px solid #2a3038', borderRadius: 6, padding: '0 12px', marginTop: 6 }}>
              <input
                type="number" min="1" step={qtyUnit === 'lot' ? 1 : undefined}
                value={qtyValue}
                onChange={e => setQtyValue(e.target.value)}
                style={{ flex: 1, background: 'none', border: 'none', color: 'var(--text-primary)', fontFamily: 'inherit', fontSize: 14, fontWeight: 700, padding: '9px 0', outline: 'none', fontVariantNumeric: 'tabular-nums' }}
              />
              <select value={qtyUnit} onChange={e => { setQtyUnit(e.target.value); setQtyValue('1'); }}
                style={{ background: 'none', border: 'none', color: '#f0c040', fontFamily: 'inherit', fontSize: 11, fontWeight: 700, cursor: 'pointer', outline: 'none', padding: '0 0 0 4px' }}>
                <option value="lot" style={{ background: '#1c2228' }}>Lot ▾</option>
                <option value="usd" style={{ background: '#1c2228' }}>USD ▾</option>
                <option value={lotInfo.unit} style={{ background: '#1c2228' }}>{lotInfo.unit} ▾</option>
              </select>
            </div>
            <div style={{ fontSize: 9, color: '#555', marginTop: 4 }}>1 Lot = {lotInfo.lotSize} {lotInfo.unit}</div>
            {/* % quick buttons */}
            <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
              {[10,25,50,75,100].map(pct => {
                const lotsAtPct = availFunds && isFutures
                  ? Math.max(1, Math.floor((availFunds * pct / 100) / ((spotPrice * lotInfo.lotSize) / leverage)))
                  : null;
                return (
                  <button key={pct} onClick={() => {
                    setQtyUnit('lot');
                    setQtyValue(lotsAtPct ? String(lotsAtPct) : String(Math.max(1, Math.round(pct / 100 * 10))));
                  }} style={{
                    flex: 1, padding: '5px 0', borderRadius: 4,
                    background: '#252d35', color: '#777',
                    border: '1px solid #2a3038', fontSize: 10,
                    fontFamily: 'inherit', cursor: 'pointer', fontWeight: 600,
                  }}>{pct}%</button>
                );
              })}
            </div>
          </div>

          {/* ── Bracket Order / TP·SL ── */}
          <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: '#aaa', borderBottom: '1px dashed #444' }}>Bracket Order</span>
            <button
              onClick={() => setShowBracket(b => !b)}
              style={{ background: 'none', border: '1px solid #f0c04055', borderRadius: 5, padding: '4px 10px', color: '#f0c040', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              {showBracket ? '− Remove TP/SL' : '+ Add TP/SL'}
            </button>
          </div>
          {showBracket && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
              {[
                { label: 'Take Profit', val: fp(entry.takeProfit), color: 'var(--accent)' },
                { label: 'Stop Loss',   val: fp(entry.stopLoss),   color: 'var(--danger)' },
              ].map(({ label, val, color }) => (
                <div key={label} style={{ background: '#1c2228', border: '1px solid #2a3038', borderRadius: 6, padding: '8px 10px' }}>
                  <div style={{ fontSize: 9, color: '#555', marginBottom: 3 }}>{label}</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color, fontVariantNumeric: 'tabular-nums' }}>{val}</div>
                </div>
              ))}
            </div>
          )}

          {/* ── Funds req / Available margin ── */}
          <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ fontSize: 12, color: '#aaa', borderBottom: '1px dashed #444' }}>Funds req.</span>
                <span style={{ fontSize: 12, cursor: 'pointer', color: '#888' }} title="Reload">↻</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: insufficientFunds ? 'var(--danger)' : 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                  {fmtCost(marginUsd)}
                </span>
                {/* USD/INR pill */}
                <div style={{ display: 'flex', background: '#1c2228', borderRadius: 4, overflow: 'hidden', border: '1px solid #2a3038' }}>
                  {(['USD','INR'] as const).map(c => (
                    <button key={c} onClick={() => setCurrency(c)} style={{
                      padding: '2px 7px', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                      fontSize: 9, fontWeight: 700,
                      background: currency === c ? (c === 'INR' ? '#251800' : '#0d1a26') : 'transparent',
                      color: currency === c ? (c === 'INR' ? '#f0c040' : '#88aaff') : '#555',
                    }}>{c}</button>
                  ))}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: '#aaa' }}>Available Margin</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: insufficientFunds ? 'var(--danger)' : '#ccc', fontVariantNumeric: 'tabular-nums' }}>
                {availFunds !== null ? fmtCost(availFunds) : '—'}
              </span>
            </div>
            {insufficientFunds && (
              <div style={{ fontSize: 9, color: 'var(--danger)', textAlign: 'right' }}>
                Need {fmtCost(marginUsd - (availFunds ?? 0))} more —{' '}
                <a href="https://www.delta.exchange/app/account/deposit" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Deposit ↗</a>
              </div>
            )}
          </div>


          {/* status banner */}
          {modalStatus.type !== 'idle' && (
            <div style={{
              marginTop: 12, padding: '10px 12px', borderRadius: 6,
              border: `1px solid ${modalStatus.type === 'success' ? '#1ed76033' : modalStatus.type === 'error' ? '#ff475733' : '#2a3038'}`,
              background: modalStatus.type === 'success' ? '#0a1f12' : modalStatus.type === 'error' ? '#1f0a0a' : '#1c2228',
              display: 'flex', alignItems: 'flex-start', gap: 8,
            }}>
              <span style={{ fontSize: 14, flexShrink: 0 }}>
                {modalStatus.type === 'pending' ? '⏳' : modalStatus.type === 'success' ? '✅' : '❌'}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 2,
                  color: modalStatus.type === 'success' ? '#1ed760' : modalStatus.type === 'error' ? '#ff4757' : '#888' }}>
                  {modalStatus.type === 'pending' ? 'Placing order…' : modalStatus.type === 'success' ? 'Order placed ✓' : 'Order failed'}
                </div>
                <div style={{ fontSize: 10, color: '#777', lineHeight: 1.6, wordBreak: 'break-word' }}>{modalStatus.msg}</div>
                {modalStatus.type === 'error' && modalStatus.msg.toLowerCase().includes('insufficient margin') && (
                  <a href="https://www.delta.exchange/app/account/deposit" target="_blank" rel="noopener noreferrer"
                    style={{ display: 'inline-block', marginTop: 6, fontSize: 10, fontWeight: 700, color: '#1ed760', textDecoration: 'none', background: '#0a2010', border: '1px solid #1ed76033', borderRadius: 4, padding: '4px 10px' }}>
                    Deposit Funds ↗
                  </a>
                )}
              </div>
            </div>
          )}

          </div>{/* end padded inner */}

          {/* ── Big action button (full width, no padding) ── */}
          {modalStatus.type === 'success' ? (
            <button onClick={closeModal} style={{
              width: '100%', padding: '14px 0', background: '#1c2228',
              color: '#1ed760', border: 'none', borderTop: '1px solid #2a3038',
              fontFamily: 'inherit', fontSize: 14, fontWeight: 800, cursor: 'pointer', letterSpacing: 0.5,
            }}>Done</button>
          ) : (
            <button
              onClick={modalStatus.type === 'pending' ? undefined : submitOrder}
              disabled={insufficientFunds || modalStatus.type === 'pending'}
              style={{
                width: '100%', padding: '15px 0', border: 'none',
                background: insufficientFunds ? '#1c2228'
                  : modalStatus.type === 'pending' ? '#1c2228'
                  : entry.direction === 'long' ? '#1ed760' : '#ff4757',
                color: insufficientFunds || modalStatus.type === 'pending'
                  ? '#555' : '#000',
                fontFamily: 'inherit', fontSize: 15, fontWeight: 900,
                cursor: insufficientFunds || modalStatus.type === 'pending' ? 'not-allowed' : 'pointer',
                letterSpacing: 0.5, transition: 'opacity 0.15s',
                opacity: modalStatus.type === 'pending' ? 0.7 : 1,
              }}
            >
              {modalStatus.type === 'pending' ? 'Placing…'
                : modalStatus.type === 'error' ? `Retry ${side}`
                : `${side}${isLive ? '' : ' (Paper)'}`}
            </button>
          )}
        </div>
      </div>
    )}
    </>
  );
});

const sBtn: React.CSSProperties = {
  width: 20, height: 20, borderRadius: 3, border: '1px solid var(--border)',
  background: 'var(--bg)', color: 'var(--text-muted)',
  cursor: 'pointer', fontFamily: 'inherit', fontSize: 13,
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0,
};

// ── main component ────────────────────────────────────────────────────────────

export function SignalsTable() {
  const { feed, dismiss }   = useSignalFeed();
  const { data: signals }             = useSignals();
  const { data: modeData }            = useTradingMode();
  const { data: exData }              = useExchanges();
  const { data: acctData }            = useAccountSummary(); // single subscription here, passed as prop
  const currentMode = modeData?.name ?? '';

  const delta       = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);
  const isLive      = !!(delta?.has_credentials && !delta.is_paper);
  const posMode     = isLive ? 'live' : 'paper';
  const availFunds  = acctData?.portfolio?.margin_available ?? null;

  // Only count positions matching current paper/live mode to correctly gate BUY NOW
  const { data: posData } = usePositions(posMode);

  const openByUnderlying: Record<string, number> = {};
  (posData?.positions ?? []).forEach(p => {
    if (p.status === 'open' || p.status === 'partially_closed')
      openByUnderlying[p.underlying] = (openByUnderlying[p.underlying] ?? 0) + 1;
  });

  // Show only entries for the active mode; 'all' shows every entry regardless of mode.
  const visible = feed.filter(e =>
    !e.dismissed &&
    (currentMode === 'all' || !currentMode || resolveMode(e) === currentMode)
  );
  const active  = visible.filter(e =>
    ['ENTRY_ARMED_PULLBACK','ENTRY_ARMED_CONTINUATION','CONFIRMED_SETUP_ACTIVE','EARLY_SETUP_ACTIVE']
      .includes(e.currentState)
  ).length;

  return (
    <div style={{ marginBottom: 16, borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)' }}>

      {/* header */}
      <div style={{
        background: isLive ? 'linear-gradient(90deg, #071a14, #071a14)' : 'linear-gradient(90deg, #0d1230, #071a14)',
        borderBottom: `1px solid ${isLive ? 'var(--accent)22' : '#4466bb22'}`,
        padding: '10px 14px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: 'var(--accent)', fontSize: 12, fontWeight: 900, letterSpacing: 2 }}>
            ● LIVE SIGNALS
          </span>
          {/* paper/live badge */}
          <span style={{
            fontSize: 9, fontWeight: 700, letterSpacing: 1,
            color: isLive ? 'var(--accent)' : '#88aaff',
            background: isLive ? 'var(--accent)18' : '#88aaff18',
            border: `1px solid ${isLive ? 'var(--accent)44' : '#88aaff44'}`,
            borderRadius: 3, padding: '1px 6px',
          }}>
            {isLive ? '● LIVE' : 'PAPER'}
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
      </div>

      {/* empty state — show current snapshot so user knows why feed is quiet */}
      {visible.length === 0 && (
        <div style={{ background: 'var(--bg-card)', padding: '20px 16px' }}>
          {(() => {
            const fresh = (signals?.signals ?? []).filter(s => s.fresh);
            const modeLabel = currentMode ? currentMode.charAt(0).toUpperCase() + currentMode.slice(1) : '';

            // Determine why there are no signals
            const allIdle     = fresh.length > 0 && fresh.every(s => s.regime === 'IDLE');
            const allFiltered = fresh.length > 0 && fresh.every(s => s.state === 'FILTERED' || s.state === 'IDLE');
            const avgAtr      = fresh.length > 0
              ? fresh.reduce((a, s) => a + (s.atr_percentile ?? 50), 0) / fresh.length
              : 50;
            const cooldownActive = allIdle || avgAtr < 30;

            let headline = `No ${modeLabel} signals right now`;
            let reason   = 'Waiting for market conditions to meet entry criteria.';
            let badge    = { text: 'MARKET CONDITION', color: 'var(--text-faint)' };

            if (fresh.length === 0) {
              headline = 'Fetching live data…';
              reason   = 'Signals compute every 30s.';
              badge    = { text: 'LOADING', color: 'var(--text-faint)' };
            } else if (cooldownActive) {
              headline = `Low volatility — ${modeLabel} signals paused`;
              reason   = `Market ATR is in the bottom 30th percentile. ${modeLabel} mode requires stronger price movement before entries are valid.`;
              badge    = { text: 'COOLDOWN', color: '#f0c040' };
            } else if (allFiltered) {
              headline = `No ${modeLabel} trend detected`;
              reason   = `ADX and regime filters for ${modeLabel} mode aren't met. Signals fire when the trend strengthens.`;
              badge    = { text: 'FILTERED', color: 'var(--text-faint)' };
            }

            return (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{
                    fontSize: 9, fontWeight: 700, letterSpacing: 1,
                    color: badge.color, background: badge.color + '18',
                    border: `1px solid ${badge.color}44`,
                    borderRadius: 3, padding: '2px 6px',
                  }}>{badge.text}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)' }}>{headline}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 12 }}>{reason}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {fresh.map(s => {
                    const stateColor: Record<string, string> = {
                      ENTRY_ARMED_PULLBACK: '#44cc88', ENTRY_ARMED_CONTINUATION: '#66ccff',
                      CONFIRMED_SETUP_ACTIVE: '#f0c040', EARLY_SETUP_ACTIVE: '#f0a500',
                      FILTERED: 'var(--text-faint)', IDLE: 'var(--border-light)',
                    };
                    const c = stateColor[s.state] ?? 'var(--text-faint)';
                    return (
                      <span key={s.underlying} style={{
                        fontSize: 10, padding: '3px 8px', borderRadius: 4,
                        background: c + '18', border: `1px solid ${c}44`, color: c, fontWeight: 700,
                      }}>
                        {s.underlying} · {s.state.replace(/_/g, ' ')}
                        {s.atr_percentile != null ? ` · ATR${Math.round(s.atr_percentile)}%` : ''}
                      </span>
                    );
                  })}
                </div>
              </>
            );
          })()}
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
              isLive={isLive}
              availFunds={availFunds}
              showModeTag={currentMode === 'all'}
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
