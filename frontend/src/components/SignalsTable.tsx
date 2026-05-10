/**
 * SignalsTable — append-only trading signal feed.
 *
 * New signals appear at the top; existing rows never reorder.
 * Scroll down to see older signals. Works like an Instagram feed.
 */
import React, { useEffect, useMemo, useRef, useState, memo } from 'react';
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

// ── Bracket Order Panel ───────────────────────────────────────────────────────

// Pseudocode §3: percent_to_price
function pctToPrice(entryPrice: number, pct: number, side: 'long'|'short', leg: 'tp'|'sl'): number {
  if (side === 'long')  return leg === 'tp' ? entryPrice * (1 + pct/100) : entryPrice * (1 - pct/100);
  return leg === 'tp' ? entryPrice * (1 - pct/100) : entryPrice * (1 + pct/100);
}

// Pseudocode §3: price_to_percent (for display)
function priceToDisplayPct(entryPrice: number, triggerPrice: number, side: 'long'|'short', leg: 'tp'|'sl'): number {
  if (side === 'long')  return leg === 'tp' ? (triggerPrice - entryPrice)/entryPrice*100 : (entryPrice - triggerPrice)/entryPrice*100;
  return leg === 'tp' ? (entryPrice - triggerPrice)/entryPrice*100 : (triggerPrice - entryPrice)/entryPrice*100;
}

// Pseudocode §4: calculate_pnl (contract_value = lotSize for futures)
function calcPnl(entry: number, exit: number, size: number, contractValue: number, side: 'long'|'short'): number {
  return (side === 'long' ? exit - entry : entry - exit) * size * contractValue;
}

// Pseudocode §2: validate bracket prices
function validateBracket(entry: number, tp: number|null, sl: number|null, side: 'long'|'short'): string|null {
  if (tp !== null && tp > 0) {
    if (side === 'long'  && tp <= entry) return 'Take Profit must be above entry for Long';
    if (side === 'short' && tp >= entry) return 'Take Profit must be below entry for Short';
  }
  if (sl !== null && sl > 0) {
    if (side === 'long'  && sl >= entry) return 'Stop Loss must be below entry for Long';
    if (side === 'short' && sl <= entry) return 'Stop Loss must be above entry for Short';
  }
  return null;
}

export interface BracketState {
  tpValue: string; setTpValue: (v: string) => void;
  slValue: string; setSlValue: (v: string) => void;
  slType: 'market'|'limit'|'trail';
  trailAmount: string;
  triggerMethod: string;
}

function BracketPanel({
  spotPrice, direction, lotSize, size,
  tpValue, setTpValue, slValue, setSlValue,
  defaultTp, defaultSl,
  onStateChange,
}: {
  spotPrice: number; direction: 'long'|'short';
  lotSize: number; size: number;
  tpValue: string; setTpValue: (v: string) => void;
  slValue: string; setSlValue: (v: string) => void;
  defaultTp: number; defaultSl: number;
  onStateChange?: (s: { slType: string; trailAmount: string; triggerMethod: string }) => void;
}) {
  const [slType, setSlType]           = useState<'market'|'limit'|'trail'>('market');
  const [slLimitPrice, setSlLimitPrice] = useState('');
  const [tpLimitPrice, setTpLimitPrice] = useState('');
  const [trailAmount, setTrailAmount]  = useState('');
  const [triggerMethod, setTriggerMethod] = useState<'mark_price'|'last_traded_price'|'spot_price'>('mark_price');
  const [dismissed, setDismissed]     = useState(false);

  // Notify parent of state changes for submitOrder
  useEffect(() => { onStateChange?.({ slType, trailAmount, triggerMethod }); }, [slType, trailAmount, triggerMethod]);

  const tpNum = parseFloat(tpValue) || 0;
  const slNum = parseFloat(slValue) || 0;
  const tpPct = tpNum > 0 ? priceToDisplayPct(spotPrice, tpNum, direction, 'tp').toFixed(2) : null;
  const slPct = slNum > 0 ? priceToDisplayPct(spotPrice, slNum, direction, 'sl').toFixed(2) : null;
  const validErr = validateBracket(spotPrice, tpNum || null, slNum || null, direction);

  // PnL: pseudocode §4 — contract_value = lotSize
  const exitPnl = tpNum > 0 ? calcPnl(spotPrice, tpNum, size, lotSize, direction) : null;
  const stopPnl = slNum > 0 ? calcPnl(spotPrice, slNum, size, lotSize, direction) : null;

  const inpStyle: React.CSSProperties = {
    flex: 1, background: 'none', border: 'none', outline: 'none',
    color: 'var(--text-primary)', fontFamily: 'inherit',
    fontSize: 13, fontWeight: 700, padding: '8px 0', fontVariantNumeric: 'tabular-nums',
  };
  const rowStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', background: 'var(--bg-input)',
    border: '1px solid var(--border)', borderRadius: 5, padding: '0 10px', marginBottom: 6,
  };
  const pctBtn = (label: string, onClick: () => void): React.ReactNode => (
    <button key={label} onClick={onClick} style={{
      flex: 1, padding: '4px 0', borderRadius: 4, fontSize: 9, fontWeight: 600,
      background: 'var(--bg-input)', color: 'var(--text-faint)',
      border: '1px solid var(--border)', cursor: 'pointer', fontFamily: 'inherit',
    }}>{label}</button>
  );

  return (
    <div style={{ marginTop: 8, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>

      {/* Entry / Trigger method */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Entry Price</span>
        <select value={triggerMethod} onChange={e => setTriggerMethod(e.target.value as typeof triggerMethod)}
          style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text-muted)', fontFamily: 'inherit', fontSize: 10, padding: '2px 6px', cursor: 'pointer', outline: 'none' }}>
          <option value="mark_price">Trigger: Mark ({spotPrice.toLocaleString('en-US', { maximumFractionDigits: 1 })})</option>
          <option value="last_traded_price">Trigger: Last Traded</option>
          <option value="spot_price">Trigger: Spot</option>
        </select>
      </div>

      {/* Info banner */}
      {!dismissed && (
        <div style={{ padding: '7px 12px', background: '#f0730018', borderBottom: '1px solid #f0730033', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <span style={{ fontSize: 10, color: '#f07300', lineHeight: 1.5, fontWeight: 600 }}>
            Now use underlying index price to trigger TP/SL orders
          </span>
          <button onClick={() => setDismissed(true)} style={{ background: 'none', border: 'none', color: '#f07300', cursor: 'pointer', fontSize: 14, padding: 0, flexShrink: 0 }}>✕</button>
        </div>
      )}

      {/* Validation error */}
      {validErr && (
        <div style={{ padding: '6px 12px', background: 'var(--danger)15', borderBottom: '1px solid var(--danger)33', fontSize: 10, color: 'var(--danger)', fontWeight: 600 }}>
          ⚠ {validErr}
        </div>
      )}

      {/* ── Take Profit ── */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 700 }}>Take Profit</span>
          {tpPct !== null && <span style={{ fontSize: 10, color: tpNum > 0 ? 'var(--accent)' : 'var(--text-faint)' }}>+{tpPct}%</span>}
        </div>
        <div style={rowStyle}>
          <span style={{ fontSize: 10, color: 'var(--text-faint)', marginRight: 6 }}>Trigger</span>
          <input type="number" value={tpValue} onChange={e => setTpValue(e.target.value)}
            placeholder={String(defaultTp)} style={inpStyle} />
          <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>USD</span>
        </div>
        <div style={{ display: 'flex', gap: 4, marginBottom: tpLimitPrice !== '' ? 6 : 0 }}>
          {['0.25','0.5','1','2'].map(p => pctBtn(`${p}%`, () => setTpValue(String(Math.round(pctToPrice(spotPrice, parseFloat(p), direction, 'tp'))))))}
          {pctBtn('0%', () => setTpValue(''))}
        </div>
      </div>

      {/* ── Stop Loss ── */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--danger)', fontWeight: 700 }}>Stop Loss</span>
          <div style={{ display: 'flex', gap: 2 }}>
            {(['market','limit','trail'] as const).map(t => (
              <button key={t} onClick={() => setSlType(t)} style={{
                padding: '2px 8px', borderRadius: 4, fontSize: 9, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
                background: slType === t ? '#f0730020' : 'transparent',
                color: slType === t ? '#f07300' : 'var(--text-faint)',
                border: `1px solid ${slType === t ? '#f0730055' : 'var(--border)'}`,
              }}>{t.charAt(0).toUpperCase() + t.slice(1)}</button>
            ))}
          </div>
        </div>
        {slPct !== null && <div style={{ fontSize: 10, color: slNum > 0 ? 'var(--danger)' : 'var(--text-faint)', marginBottom: 4, textAlign: 'right' }}>−{slPct}%</div>}

        {slType === 'trail' ? (
          <div style={rowStyle}>
            <span style={{ fontSize: 10, color: 'var(--text-faint)', marginRight: 6 }}>Trail Amount</span>
            <input type="number" value={trailAmount} onChange={e => setTrailAmount(e.target.value)}
              placeholder="e.g. 500" style={inpStyle} />
            <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>USD</span>
          </div>
        ) : (
          <>
            <div style={rowStyle}>
              <span style={{ fontSize: 10, color: 'var(--text-faint)', marginRight: 6 }}>Trigger</span>
              <input type="number" value={slValue} onChange={e => setSlValue(e.target.value)}
                placeholder={String(defaultSl)} style={inpStyle} />
              <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>USD</span>
            </div>
            {slType === 'limit' && (
              <div style={{ ...rowStyle, marginTop: 4 }}>
                <span style={{ fontSize: 10, color: 'var(--text-faint)', marginRight: 6 }}>Limit</span>
                <input type="number" value={slLimitPrice} onChange={e => setSlLimitPrice(e.target.value)}
                  placeholder="Limit price" style={inpStyle} />
                <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>USD</span>
              </div>
            )}
            <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
              {['0.25','0.5','1','2'].map(p => pctBtn(`${p}%`, () => setSlValue(String(Math.round(pctToPrice(spotPrice, parseFloat(p), direction, 'sl'))))))}
              {pctBtn('0%', () => setSlValue(''))}
            </div>
          </>
        )}
      </div>

      {/* ── PnL preview (§4) ── */}
      <div style={{ padding: '8px 12px', display: 'flex', gap: 0 }}>
        {([
          { label: 'Exit PnL', val: exitPnl, good: true },
          { label: 'Stop PnL', val: stopPnl, good: false },
        ]).map(({ label, val, good }) => (
          <div key={label} style={{ flex: 1 }}>
            <div style={{ fontSize: 10, color: 'var(--text-faint)', borderBottom: '1px dashed var(--border)', paddingBottom: 2, marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 12, fontWeight: 700, fontVariantNumeric: 'tabular-nums',
              color: val === null ? 'var(--text-faint)' : (val >= 0 ? 'var(--accent)' : 'var(--danger)') }}>
              {val === null ? '—' : `${val >= 0 ? '+' : ''}$${Math.abs(val).toFixed(2)}`}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
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
  const LOT_LEVERAGES = [5, 10, 20, 50, 100];

  const isFutures = entry.type === 'futures';
  const lotInfo   = LOT_SIZES[entry.underlying] ?? { lotSize: 1, unit: entry.underlying };
  const spotPrice = entry.currentPrice ?? entry.entry;

  // Snap initial leverage to nearest valid tier
  const snapLev = (l: number) => LOT_LEVERAGES.reduce((a, b) => Math.abs(b - l) < Math.abs(a - l) ? b : a);

  const [leverage, setLeverage]     = useState(() => snapLev(entry.leverage));
  const [direction, setDirection]   = useState<'long'|'short'>(entry.direction as 'long'|'short');
  const [currency, setCurrency]     = useState<'USD'|'INR'>('INR');  // default INR
  const [qtyValue, setQtyValue]     = useState(() => String(Math.round(spotPrice * lotInfo.lotSize)));
  const [qtyUnit, setQtyUnit]       = useState<'lot'|'usd'|string>('usd'); // default USD
  const [orderType, setOrderType]   = useState<'market'|'limit'>('limit'); // default Limit
  const [limitPrice, setLimitPrice] = useState(() => String(Math.round(spotPrice))); // start at current price
  const [showBracket, setShowBracket] = useState(true);
  const [feedback, setFeedback]     = useState('');
  const [placing, setPlacing]       = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [modalStatus, setModalStatus] = useState<{ type: 'idle'|'pending'|'success'|'error'; msg: string }>({ type: 'idle', msg: '' });

  // Editable SL/TP — recompute defaults when direction changes
  const atr = spotPrice * (entry.adx > 0 ? 0.015 : 0.02);
  const defaultSl = useMemo(() => {
    if (!isFutures) return entry.stopLoss ?? 0;
    const dist = Math.abs(spotPrice - (entry.stopLoss ?? spotPrice - atr));
    return Math.round(direction === 'long' ? spotPrice - dist : spotPrice + dist);
  }, [direction, spotPrice, entry.stopLoss, isFutures, atr]);
  const defaultTp = useMemo(() => {
    if (!isFutures) return entry.takeProfit ?? 0;
    const dist = Math.abs((entry.takeProfit ?? spotPrice + atr * 2) - spotPrice);
    return Math.round(direction === 'long' ? spotPrice + dist : spotPrice - dist);
  }, [direction, spotPrice, entry.takeProfit, isFutures, atr]);
  const [slValue, setSlValue] = useState(() => String(Math.round(entry.stopLoss ?? defaultSl)));
  const [tpValue, setTpValue] = useState(() => String(Math.round(entry.takeProfit ?? defaultTp)));
  // Sync defaults when direction flips
  useEffect(() => { setSlValue(String(defaultSl)); setTpValue(String(defaultTp)); }, [defaultSl, defaultTp]);

  const { mutate: trade } = useDirectEntry();
  const bracketRef = useRef({ slType: 'market', trailAmount: '', triggerMethod: 'mark_price' });

  const USD_INR = 84.5;

  const size = useMemo(() => {
    const n = parseFloat(qtyValue) || 0;
    if (qtyUnit === 'lot') return Math.max(1, Math.round(n));
    if (qtyUnit === 'usd') return Math.max(1, Math.round(n / (spotPrice * lotInfo.lotSize)));
    return Math.max(1, Math.round(n / lotInfo.lotSize));
  }, [qtyValue, qtyUnit, spotPrice, lotInfo.lotSize]);

  const dirColor  = direction === 'long' ? 'var(--accent)' : 'var(--danger)';
  const side      = direction === 'long' ? 'BUY' : 'SELL';
  const arrow     = direction === 'long' ? '▲' : '▼';
  const stColor   = STATE_COLOR[entry.currentState] ?? 'var(--text-dim)';
  const stLabel   = STATE_SHORT[entry.currentState] ?? '—';

  const livePnl = entry.currentPrice && entry.entry
    ? (entry.direction === 'long'
        ? (entry.currentPrice - entry.entry) / entry.entry * 100
        : (entry.entry - entry.currentPrice) / entry.entry * 100)
    : null;

  const optPrem = isFutures ? null : Math.round(entry.entry * 0.01);

  // Order economics
  const notionalUsd   = isFutures ? spotPrice * size * lotInfo.lotSize : (optPrem ?? 0) * size;
  const marginUsd     = isFutures ? notionalUsd / leverage : notionalUsd;
  // Delta Exchange India fees: maker 0.02%, taker 0.05% + 18% GST
  const feeRate       = orderType === 'limit' ? 0.0002 : 0.0005;
  const feeUsd        = notionalUsd * feeRate;
  const gstUsd        = feeUsd * 0.18;
  const totalCostUsd  = marginUsd + feeUsd + gstUsd;
  const insufficientFunds = availFunds !== null && totalCostUsd > availFunds;

  const fmtCost = (usd: number) => {
    const v = currency === 'INR' ? usd * USD_INR : usd;
    const sym = currency === 'INR' ? '₹' : '$';
    return `${sym}${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
  };

  // Leverage cycle helpers (only valid tiers)
  const levUp   = () => { const i = LOT_LEVERAGES.indexOf(leverage); if (i < LOT_LEVERAGES.length - 1) setLeverage(LOT_LEVERAGES[i + 1]); };
  const levDown = () => { const i = LOT_LEVERAGES.indexOf(leverage); if (i > 0) setLeverage(LOT_LEVERAGES[i - 1]); };

  // Limit price step (tick size based on instrument)
  const priceStep = spotPrice > 10000 ? 0.5 : spotPrice > 100 ? 0.05 : 0.001;

  // Qty hint
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
      direction,
      instrument_type: entry.type,
      size,
      leverage,
      order_type: orderType,
      limit_price: orderType === 'limit' && limitPrice ? parseFloat(limitPrice) : undefined,
      // Bracket fields from BracketPanel state
      take_profit: parseFloat(tpValue) > 0 ? parseFloat(tpValue) : undefined,
      stop_loss: bracketRef.current.slType !== 'trail' && parseFloat(slValue) > 0 ? parseFloat(slValue) : undefined,
      stop_loss_order_type: bracketRef.current.slType === 'limit' ? 'limit_order' : 'market_order',
      trail_amount: bracketRef.current.slType === 'trail' && bracketRef.current.trailAmount ? parseFloat(bracketRef.current.trailAmount) : undefined,
      bracket_trigger_method: bracketRef.current.triggerMethod,
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
            { label: 'STOP LOSS', val: isFutures ? fp(entry.stopLoss) : `~$${optPrem ? Math.round(optPrem * 0.5) : '—'}`, color: 'var(--danger)', sub: entry.stopLoss && isFutures ? pct(entry.entry, entry.stopLoss) : '-50%' },
            { label: 'TAKE PROFIT', val: isFutures ? fp(entry.takeProfit) : `~$${optPrem ? Math.round(optPrem * 2) : '—'}`, color: 'var(--accent)', sub: entry.takeProfit && isFutures ? pct(entry.entry, entry.takeProfit) : '+100%' },
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
              background: hasOpen ? 'var(--bg)' : entry.direction === 'long' ? '#003d2e' : '#3d0014',
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
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 10, width: 340,
            boxShadow: '0 12px 48px rgba(0,0,0,0.6)',
            overflow: 'hidden',
          }}
        >
          {/* ── contract + close ── */}
          <div style={{ padding: '12px 16px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
              <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
                {isFutures ? entry.futuresSymbol : `${entry.optType === 'CE' ? 'CALL' : 'PUT'} ${fp(entry.optStrike)}`}
              </span>
              <span style={{
                fontSize: 8, fontWeight: 700, letterSpacing: 0.5, flexShrink: 0,
                color: isLive ? 'var(--accent)' : '#88aaff',
                background: isLive ? 'var(--accent)15' : '#88aaff15',
                border: `1px solid ${isLive ? 'var(--accent)33' : '#88aaff33'}`,
                borderRadius: 3, padding: '1px 5px',
              }}>{isLive ? '● LIVE' : 'PAPER'}</span>
            </div>
            <button onClick={modalStatus.type === 'pending' ? undefined : closeModal}
              style={{ background: 'none', border: 'none', color: 'var(--text-faint)', cursor: 'pointer', fontSize: 16, lineHeight: 1, padding: '4px', flexShrink: 0 }}>✕</button>
          </div>

          {/* ── Buy | Long / Sell | Short tabs ── */}
          <div style={{ display: 'flex', margin: '12px 16px 0', borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)' }}>
            {(['long','short'] as const).map(d => {
              const active = d === direction;
              const col    = d === 'long' ? 'var(--accent)' : 'var(--danger)';
              const bg     = active ? (d === 'long' ? 'var(--accent)18' : 'var(--danger)18') : 'transparent';
              return (
                <button key={d} onClick={() => setDirection(d)} style={{
                  flex: 1, textAlign: 'center', padding: '10px 0',
                  background: bg, color: active ? col : 'var(--text-faint)',
                  fontWeight: 800, fontSize: 13, letterSpacing: 0.3,
                  border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                  borderRight: d === 'long' ? '1px solid var(--border)' : 'none',
                }}>
                  {d === 'long' ? 'Buy | Long' : 'Sell | Short'}
                </button>
              );
            })}
          </div>

          <div style={{ padding: '0 16px 16px' }}>

          {/* ── Leverage row ── */}
          {isFutures && (
            <div style={{ marginTop: 12, padding: '10px 12px', background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Leverage</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <button onClick={levDown} disabled={LOT_LEVERAGES.indexOf(leverage) === 0} style={{ ...sBtn, opacity: LOT_LEVERAGES.indexOf(leverage) === 0 ? 0.3 : 1 }}>&minus;</button>
                  <span style={{ fontSize: 15, fontWeight: 800, minWidth: 44, textAlign: 'center', fontVariantNumeric: 'tabular-nums',
                    color: leverage !== snapLev(entry.leverage) ? '#f0c040' : dirColor }}>
                    {leverage}×
                  </span>
                  <button onClick={levUp} disabled={LOT_LEVERAGES.indexOf(leverage) === LOT_LEVERAGES.length - 1} style={{ ...sBtn, opacity: LOT_LEVERAGES.indexOf(leverage) === LOT_LEVERAGES.length - 1 ? 0.3 : 1 }}>+</button>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                {LOT_LEVERAGES.map(l => (
                  <button key={l} onClick={() => setLeverage(l)} style={{
                    flex: 1, padding: '4px 0', borderRadius: 4, fontFamily: 'inherit',
                    fontSize: 10, fontWeight: 700, cursor: 'pointer',
                    background: leverage === l ? 'var(--accent)15' : 'var(--bg-input)',
                    color: leverage === l ? 'var(--accent)' : 'var(--text-faint)',
                    border: `1px solid ${leverage === l ? 'var(--accent)44' : 'var(--border)'}`,
                  }}>{l}×</button>
                ))}
              </div>
              {leverage !== entry.leverage && (
                <div style={{ marginTop: 6, fontSize: 9, color: '#f0c040' }}>
                  Signal suggests {entry.leverage}× (ADX {entry.adx?.toFixed(0)}) — higher leverage increases risk
                </div>
              )}
            </div>
          )}

          {/* ── Override warning ── */}
          {direction !== entry.direction && (
            <div style={{
              marginTop: 10, padding: '8px 12px',
              background: '#2a1800', border: '1px solid #f0c04044',
              borderLeft: '3px solid #f0c040',
              borderRadius: 5, display: 'flex', gap: 8, alignItems: 'flex-start',
            }}>
              <span style={{ fontSize: 13, flexShrink: 0 }}>⚠️</span>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#f0c040', marginBottom: 2 }}>
                  Going against the signal
                </div>
                <div style={{ fontSize: 10, color: '#c8941a', lineHeight: 1.5 }}>
                  The signal recommends <strong style={{ color: '#f0c040' }}>
                    {entry.direction === 'long' ? 'BUY (Long)' : 'SELL (Short)'}
                  </strong>. You've switched to <strong style={{ color: 'var(--danger)' }}>
                    {direction === 'long' ? 'BUY (Long)' : 'SELL (Short)'}
                  </strong>. Proceed only if you have a specific reason to counter-trade.
                </div>
              </div>
            </div>
          )}

          {/* ── Order type tabs ── */}
          <div style={{ display: 'flex', marginTop: 12, borderBottom: '1px solid var(--border)' }}>
            {(['market','limit'] as const).map(t => (
              <button key={t} onClick={() => setOrderType(t)} style={{
                background: 'none', border: 'none', padding: '7px 14px',
                fontFamily: 'inherit', fontSize: 12, fontWeight: 700, cursor: 'pointer',
                color: orderType === t ? dirColor : 'var(--text-faint)',
                borderBottom: orderType === t ? `2px solid ${dirColor}` : '2px solid transparent',
                marginBottom: -1,
              }}>{t === 'market' ? 'Market' : 'Limit'}</button>
            ))}
          </div>

          {/* ── Price ── */}
          <div style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{orderType === 'limit' ? 'Limit Price' : 'Market Price'}</span>
              {orderType === 'market' && <span style={{ fontSize: 11, color: 'var(--text-faint)', fontVariantNumeric: 'tabular-nums' }}>~{fp(spotPrice)}</span>}
            </div>
            {orderType === 'limit' ? (
              <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-input)', border: '1px solid var(--border-light)', borderRadius: 6, padding: '0 8px 0 12px' }}>
                <input type="number" value={limitPrice} onChange={e => setLimitPrice(e.target.value)}
                  style={{ flex: 1, background: 'none', border: 'none', color: 'var(--text-primary)', fontFamily: 'inherit', fontSize: 14, fontWeight: 700, padding: '9px 0', outline: 'none', fontVariantNumeric: 'tabular-nums' }} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1, marginRight: 4 }}>
                  <button onClick={() => setLimitPrice(p => String(Math.round((parseFloat(p) || spotPrice) + priceStep)))}
                    style={{ ...sBtn, height: 14, fontSize: 9, lineHeight: 1 }}>▲</button>
                  <button onClick={() => setLimitPrice(p => String(Math.max(0, Math.round((parseFloat(p) || spotPrice) - priceStep))))}
                    style={{ ...sBtn, height: 14, fontSize: 9, lineHeight: 1 }}>▼</button>
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-faint)', flexShrink: 0 }}>USD</span>
              </div>
            ) : (
              <div style={{ padding: '9px 12px', background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#f0c040', fontSize: 13, fontWeight: 700 }}>{fp(spotPrice)}</span>
                <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>Best {direction === 'long' ? 'Ask' : 'Bid'} · Market</span>
              </div>
            )}
          </div>

          {/* ── Quantity ── */}
          <div style={{ marginTop: 12 }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Quantity</span>
            <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-input)', border: '1px solid var(--border-light)', borderRadius: 6, padding: '0 12px', marginTop: 5 }}>
              <input type="number" min="1" step={qtyUnit === 'lot' ? 1 : undefined} value={qtyValue}
                onChange={e => setQtyValue(e.target.value)}
                style={{ flex: 1, background: 'none', border: 'none', color: 'var(--text-primary)', fontFamily: 'inherit', fontSize: 14, fontWeight: 700, padding: '9px 0', outline: 'none', fontVariantNumeric: 'tabular-nums' }} />
              <select value={qtyUnit} onChange={e => { setQtyUnit(e.target.value); setQtyValue('1'); }}
                style={{ background: 'none', border: 'none', color: '#f0c040', fontFamily: 'inherit', fontSize: 11, fontWeight: 700, cursor: 'pointer', outline: 'none', padding: '0 0 0 4px' }}>
                <option value="lot">Lot</option>
                <option value="usd">USD</option>
                <option value={lotInfo.unit}>{lotInfo.unit}</option>
              </select>
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 4 }}>1 Lot = {lotInfo.lotSize} {lotInfo.unit}</div>
            <div style={{ display: 'flex', gap: 4, marginTop: 7 }}>
              {[10,25,50,75,100].map(pct => {
                // Calculate USD amount = pct% of available funds (or 10× notional as fallback)
                const usdAtPct = availFunds
                  ? availFunds * leverage * (pct / 100)   // pct of purchasing power
                  : notionalUsd * (pct / 100);
                return (
                  <button key={pct} onClick={() => {
                    setQtyUnit('usd');
                    setQtyValue(String(Math.round(usdAtPct)));
                  }} style={{ flex: 1, padding: '5px 0', borderRadius: 4, background: 'var(--bg-input)', color: 'var(--text-dim)', border: '1px solid var(--border)', fontSize: 10, fontFamily: 'inherit', cursor: 'pointer', fontWeight: 600 }}>
                    {pct}%
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── Bracket Order ── */}
          <div style={{ marginTop: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)', textDecoration: 'underline dotted', textDecorationColor: 'var(--border)' }}>Bracket Order</span>
            <button onClick={() => setShowBracket(b => !b)}
              style={{ background: 'none', border: '1px solid #f0c04055', borderRadius: 5, padding: '4px 10px', color: '#f0c040', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>
              {showBracket ? '− Remove' : '+ Add TP/SL'}
            </button>
          </div>
          {showBracket && <BracketPanel
            spotPrice={spotPrice} direction={direction}
            lotSize={lotInfo.lotSize} size={size}
            tpValue={tpValue} setTpValue={setTpValue}
            slValue={slValue} setSlValue={setSlValue}
            defaultTp={defaultTp} defaultSl={defaultSl}
            onStateChange={s => { bracketRef.current = s as typeof bracketRef.current; }}
          />}

          {/* ── Economics breakdown ── */}
          <div style={{ marginTop: 14, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)', overflow: 'hidden' }}>
            {([
              { label: 'Notional', val: fmtCost(notionalUsd) },
              { label: `Fee (${orderType === 'limit' ? 'Maker 0.02%' : 'Taker 0.05%'})`, val: fmtCost(feeUsd) },
              { label: 'GST (18% on fee)', val: fmtCost(gstUsd) },
              { label: 'Funds req.', val: fmtCost(totalCostUsd), bold: true, warn: insufficientFunds },
            ]).map(({ label, val, bold, warn }) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 12px', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>{label}</span>
                <span style={{ fontSize: 11, fontWeight: bold ? 700 : 400, color: warn ? 'var(--danger)' : bold ? 'var(--text-primary)' : 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{val}</span>
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 12px' }}>
              <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>Available Margin</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 700, fontVariantNumeric: 'tabular-nums',
                  color: availFunds === null ? 'var(--text-faint)' : insufficientFunds ? 'var(--danger)' : 'var(--accent)' }}>
                  {availFunds !== null ? fmtCost(availFunds) : isLive ? '—' : 'Paper'}
                </span>
                <div style={{ display: 'flex', background: 'var(--bg-input)', borderRadius: 4, overflow: 'hidden', border: '1px solid var(--border)' }}>
                  {(['USD','INR'] as const).map(c => (
                    <button key={c} onClick={() => setCurrency(c)} style={{
                      padding: '2px 6px', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                      fontSize: 9, fontWeight: 700,
                      background: currency === c ? 'var(--bg-card)' : 'transparent',
                      color: currency === c ? (c === 'INR' ? '#f0c040' : '#88aaff') : 'var(--text-faint)',
                    }}>{c}</button>
                  ))}
                </div>
              </div>
            </div>
          </div>
          {insufficientFunds && (
            <div style={{ fontSize: 9, color: 'var(--danger)', textAlign: 'right', marginTop: 4 }}>
              Need {fmtCost(totalCostUsd - (availFunds ?? 0))} more —{' '}
              <a href="https://www.delta.exchange/app/account/deposit" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 700 }}>Deposit ↗</a>
            </div>
          )}


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
                background: insufficientFunds || modalStatus.type === 'pending'
                  ? 'var(--bg-input)'
                  : direction === 'long' ? 'var(--accent)' : 'var(--danger)',
                color: insufficientFunds || modalStatus.type === 'pending'
                  ? 'var(--text-faint)' : '#fff',
                fontFamily: 'inherit', fontSize: 15, fontWeight: 900,
                cursor: insufficientFunds || modalStatus.type === 'pending' ? 'not-allowed' : 'pointer',
                letterSpacing: 0.5, transition: 'background 0.15s',
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
