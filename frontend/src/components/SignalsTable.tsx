/**
 * SignalsTable — append-only trading signal feed.
 *
 * New signals appear at the top; existing rows never reorder.
 * Scroll down to see older signals. Works like an Instagram feed.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState, memo } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSignalFeed } from '../hooks/useSignalFeed';
import type { FeedEntry } from '../hooks/useSignalFeed';
import type { StreamStatus } from '../hooks/useAllSignalsStream';
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

// ── Stream connection indicator ───────────────────────────────────────────────

function StreamBadge({ status }: { status: StreamStatus }) {
  const dotColor =
    status === 'connected'    ? '#1ed760' :
    status === 'connecting'   ? '#f0c040' :
    /* disconnected */          '#ff4757';

  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{
        display: 'inline-block',
        width: 6, height: 6,
        borderRadius: '50%',
        background: dotColor,
        flexShrink: 0,
        boxShadow: status === 'connected' ? `0 0 4px ${dotColor}` : 'none',
      }} />
      {status === 'disconnected' && (
        <span style={{ fontSize: 8, color: '#ff4757', fontWeight: 700, letterSpacing: 0.3 }}>
          reconnecting…
        </span>
      )}
    </span>
  );
}

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

function tradeLabel(placing: boolean, hasOpen: boolean, actionLabel: string): string {
  if (placing) return '…';
  if (hasOpen) return 'OPEN';
  return actionLabel;
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

// memo: skip re-render when entry object reference, hasOpen, and dismiss are unchanged.
// Combined with the setFeed same-ref optimisation, this eliminates re-renders of
// unchanged rows on every 15s poll — the main GC pressure source.
const FeedRow = memo(function FeedRow({ entry, hasOpen, isLive, availFunds, showModeTag, dismiss }: {
  entry: FeedEntry;
  hasOpen: boolean;
  isLive: boolean;
  availFunds: number | null;
  showModeTag: boolean;
  dismiss: (id: string) => void;  // stable ref — memo works correctly
}) {
  // Stable dismiss callback for this entry — won't change between renders
  const onDismiss = useCallback(() => dismiss(entry.id), [dismiss, entry.id]);
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
  const [orderType, setOrderType]   = useState<'market'|'limit'|'maker'>('limit'); // default Limit
  const [timeInForce, setTimeInForce] = useState<'gtc'|'ioc'>('gtc');
  const [reduceOnly, setReduceOnly]   = useState(false);
  const [scalperMode, setScalperMode] = useState(false);
  const [scalperSecs, setScalerSecs]  = useState(30); // auto-cancel after N seconds
  const [limitPrice, setLimitPrice] = useState(() => String(Math.round(spotPrice))); // start at current price
  const [showBracket, setShowBracket] = useState(true);
  const [feedback, setFeedback]     = useState('');
  const [placing, setPlacing]       = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [modalStatus, setModalStatus] = useState<{ type: 'idle'|'pending'|'success'|'error'; msg: string }>({ type: 'idle', msg: '' });

  // SL/TP — scale with leverage to maintain constant dollar risk at stop.
  // Base distances are anchored to entry.entry at entry.leverage (the signal's recommendation).
  // When leverage changes: new_dist = base_dist * recLev / newLeverage (inversely proportional).
  const recLev  = entry.leverage || 5;
  const entryRef = entry.entry;  // signal price, not current price (avoids drift)

  const baseSlDist = useMemo(() => {
    if (!isFutures) return 0;
    if (entry.stopLoss && entry.stopLoss > 0)
      return Math.abs(entryRef - entry.stopLoss);
    // Fallback: 2% of spot
    return spotPrice * 0.02;
  }, [isFutures, entryRef, entry.stopLoss, spotPrice]);

  const baseTpDist = useMemo(() => {
    if (!isFutures) return 0;
    if (entry.takeProfit && entry.takeProfit > 0)
      return Math.abs(entry.takeProfit - entryRef);
    // Fallback: 2× SL distance (2:1 R:R)
    return baseSlDist * 2;
  }, [isFutures, entryRef, entry.takeProfit, baseSlDist]);

  const defaultSl = useMemo(() => {
    if (!isFutures) return entry.stopLoss ?? 0;
    const dist = recLev > 0 && leverage > 0
      ? baseSlDist * recLev / leverage
      : baseSlDist;
    return Math.round(direction === 'long' ? spotPrice - dist : spotPrice + dist);
  }, [isFutures, direction, spotPrice, baseSlDist, recLev, leverage, entry.stopLoss]);

  const defaultTp = useMemo(() => {
    if (!isFutures) return entry.takeProfit ?? 0;
    const dist = recLev > 0 && leverage > 0
      ? baseTpDist * recLev / leverage
      : baseTpDist;
    return Math.round(direction === 'long' ? spotPrice + dist : spotPrice - dist);
  }, [isFutures, direction, spotPrice, baseTpDist, recLev, leverage, entry.takeProfit]);

  const [slValue, setSlValue] = useState(() => String(Math.round(entry.stopLoss ?? defaultSl)));
  const [tpValue, setTpValue] = useState(() => String(Math.round(entry.takeProfit ?? defaultTp)));
  // Sync inputs when direction OR leverage changes
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
  // For options, direction is encoded in CE/PE symbol — always BUY the option.
  // SELL would mean writing naked options, which is a completely different strategy.
  const side      = isFutures ? (direction === 'long' ? 'BUY' : 'SELL') : 'BUY';
  const arrow     = direction === 'long' ? '▲' : '▼';

  // Descriptive action label: "SELL FUTURES" or "BUY PUT $80,500 · 150526"
  const tradeActionLabel = (() => {
    if (!isFutures && entry.optType && entry.optStrike) {
      const typeStr   = entry.optType === 'CE' ? 'CALL' : 'PUT';
      const strikeStr = fp(entry.optStrike);
      const expiry    = entry.optExpiry ?? '';
      return `BUY ${typeStr} ${strikeStr} · ${expiry}`;
    }
    return `${side} FUTURES`;
  })();
  const stColor   = STATE_COLOR[entry.currentState] ?? 'var(--text-dim)';
  const stLabel   = STATE_SHORT[entry.currentState] ?? '—';

  const livePnl = entry.currentPrice && entry.entry
    ? (entry.direction === 'long'
        ? (entry.currentPrice - entry.entry) / entry.entry * 100
        : (entry.entry - entry.currentPrice) / entry.entry * 100)
    : null;

  // ── 1-second wire: live SL/TP distance from CURRENT price + tick flash ──
  // Recomputed every render (cheap) so the user sees these % counters move
  // every time the SSE prices event lands a new spot for this underlying.
  const liveSlDist = (isFutures && entry.currentPrice && entry.stopLoss)
    ? (entry.direction === 'long'
        ? (entry.currentPrice - entry.stopLoss) / entry.currentPrice * 100
        : (entry.stopLoss - entry.currentPrice) / entry.currentPrice * 100)
    : null;
  const liveTpDist = (isFutures && entry.currentPrice && entry.takeProfit)
    ? (entry.direction === 'long'
        ? (entry.takeProfit - entry.currentPrice) / entry.currentPrice * 100
        : (entry.currentPrice - entry.takeProfit) / entry.currentPrice * 100)
    : null;

  // Price-tick flash — animates the NOW cell green-up / red-down when
  // currentPrice changes. Confirms the 1-s wire visually without polling.
  const prevPriceRef = useRef<number | null>(null);
  const [tickClass, setTickClass] = useState<'price-flash-up' | 'price-flash-down' | ''>('');
  useEffect(() => {
    const cp = entry.currentPrice;
    if (cp == null || prevPriceRef.current == null) {
      prevPriceRef.current = cp ?? null;
      return;
    }
    if (cp === prevPriceRef.current) return;
    setTickClass(cp > prevPriceRef.current ? 'price-flash-up' : 'price-flash-down');
    prevPriceRef.current = cp;
    const t = setTimeout(() => setTickClass(''), 420);
    return () => clearTimeout(t);
  }, [entry.currentPrice]);

  const optPrem = isFutures ? null : Math.round(entry.entry * 0.01);

  // Order economics
  const notionalUsd   = isFutures ? spotPrice * size * lotInfo.lotSize : (optPrem ?? 0) * size;
  const marginUsd     = isFutures ? notionalUsd / leverage : notionalUsd;

  // ── Delta Exchange India fee schedule (from /v2/products/{symbol}) ──────────
  // Taker rate: 0.05% | Maker rate: 0.02% | Maker-Only (post-only): 0% (rebate eligible)
  // VIP discount applied on gross commission before GST.
  // GST (18%) is NOT in the API — applied externally per Indian statutory requirement.
  // Source: official Delta Exchange API documentation.
  const TAKER_RATE    = 0.0005;   // 0.05%
  const MAKER_RATE    = 0.0002;   // 0.02%
  const MAKER_REBATE  = 0.0;      // 0% for post-only (maker-only) — rebate eligible
  const GST_RATE      = 0.18;     // 18% GST on exchange commission

  const feeRole = orderType === 'market' ? 'taker' : orderType === 'maker' ? 'maker-rebate' : 'maker';
  const grossRate = orderType === 'market' ? TAKER_RATE
                  : orderType === 'maker'  ? MAKER_REBATE
                  : MAKER_RATE;

  const grossFeeUsd   = notionalUsd * grossRate;
  const feeUsd        = grossFeeUsd;   // VIP discount would reduce this — shown separately if known
  const gstUsd        = feeUsd * GST_RATE;
  const feeRate       = grossRate;     // kept for backward-compat with downstream uses
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
      order_type: orderType,   // "market" | "limit" | "maker" (backend resolves "maker" → limit+post_only)
      limit_price: orderType !== 'market' && limitPrice ? parseFloat(limitPrice) : undefined,
      time_in_force: timeInForce,
      post_only: orderType === 'maker',
      reduce_only: reduceOnly,
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
        // Scalper auto-cancel: if order still unfilled after scalperSecs, cancel it
        if (scalperMode && orderId && data?.mode === 'live') {
          const underlying = entry.underlying;
          setTimeout(async () => {
            try {
              // The product_id lookup is server-side; we just call cancel-all as fallback
              await fetch(`/api/v1/trading/cancel-order/${orderId}?product_id=0`, { method: 'DELETE' });
            } catch { /* ignore if already filled */ }
          }, scalperSecs * 1000);
          setFeedback(`⚡ Scalper: auto-cancels in ${scalperSecs}s if unfilled`);
        }
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
    if (scalperMode) {
      // Scalper: skip confirmation, fire immediately
      submitOrder();
      return;
    }
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
      transition: 'opacity 0.3s, background 0.1s',
    }}>
      {/* LEFT — time + symbol */}
      <div style={{ width: 150, flexShrink: 0, padding: '14px 12px 14px 14px', borderRight: '1px solid var(--border)' }}>
        <div style={{ fontSize: 9, color: 'var(--text-faint)', marginBottom: 2 }}>{fmtTime(entry.entryAt)}</div>
        <div style={{ fontSize: 16, fontWeight: 900, color: 'var(--text-primary)', letterSpacing: 1 }}>{entry.underlying}</div>
        <div style={{ fontSize: 11, fontWeight: 800, color: dirColor, marginTop: 2 }}>
          {arrow} {side}
        </div>
        <div style={{ fontSize: 9, color: stColor, marginTop: 4, letterSpacing: 0.5, fontWeight: 700 }}>{stLabel}</div>
        <div style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 2 }}>{fmtAge(entry.entryAt)}</div>
        <div
          title={`Signal ID: ${entry.signalId} — click to copy`}
          onClick={() => entry.signalId && navigator.clipboard?.writeText(entry.signalId)}
          style={{
            marginTop: 6, display: 'flex', alignItems: 'center', gap: 4,
            background: 'var(--bg)', border: '1px solid var(--border)',
            borderRadius: 3, padding: '3px 6px', cursor: 'pointer',
            width: 'fit-content',
          }}
        >
          <span style={{ fontSize: 7, color: 'var(--text-faint)', letterSpacing: 1, textTransform: 'uppercase', flexShrink: 0 }}>ID</span>
          <span style={{
            fontSize: 10, fontFamily: 'monospace', fontWeight: 800,
            color: 'var(--text-primary)', letterSpacing: 1,
          }}>
            {entry.signalId ?? '—'}
          </span>
        </div>
      </div>

      {/* CENTRE — instrument + prices */}
      <div style={{ flex: 1, padding: '14px 12px', minWidth: 0 }}>
        {/* instrument */}
        <div style={{ marginBottom: 8 }}>
          {isFutures ? (
            <span style={{ fontSize: 12, color: '#88aaff', fontWeight: 700 }}>
              {entry.futuresSymbol} · {entry.leverage}× lev
            </span>
          ) : (
            <span style={{ fontSize: 12, color: 'var(--warning)', fontWeight: 700 }}>
              {entry.optType === 'CE' ? 'CALL' : 'PUT'} {fp(entry.optStrike)} · {entry.optExpiry} · {entry.optDte} DTE
            </span>
          )}
          <span style={{ marginLeft: 8, fontSize: 9, color: 'var(--text-faint)' }}>
            {entry.regime.replace(/_/g, ' ')} · Score {entry.score}
            {entry.refreshedAt && (
              <span style={{ marginLeft: 6, fontSize: 8, color: 'var(--accent)', opacity: 0.7 }}>
                · SL/TP live
              </span>
            )}
            {entry.signalStrength === 'STRONG' && (
              <span
                title="STRONG = ≥75% confluence on the 1H signal stack"
                style={{
                  marginLeft: 6, fontSize: 8, fontWeight: 800, letterSpacing: 0.5,
                  color: '#f0c040', background: '#3a2a08',
                  border: '1px solid #f0c04055', borderRadius: 2, padding: '1px 4px',
                  cursor: 'help',
                }}
              >
                STRONG
              </span>
            )}
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

        {/* G2: MTF chip strip — 4H / 1H / 15m breakdown */}
        {entry.mtf && (
          <div
            style={{ display: 'flex', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}
            title={entry.mtf.alignment_label}
          >
            {([
              ['4H',  entry.mtf.macro_4h,      entry.mtf.macro_ok,  20],
              ['1H',  entry.mtf.signal_1h,     entry.mtf.signal_ok, 20],
              ['15m', entry.mtf.execution_15m, entry.mtf.exec_ok,   15],
            ] as [string, number, boolean, number][]).map(([label, val, ok, max]) => (
              <span
                key={label}
                style={{
                  fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
                  padding: '1px 6px', borderRadius: 3,
                  background: ok ? 'rgba(29,215,96,0.10)' : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${ok ? 'var(--accent)55' : 'var(--border)'}`,
                  color: ok ? 'var(--accent)' : 'var(--text-faint)',
                  fontFamily: 'monospace',
                }}
              >
                {label} {val.toFixed(0)}/{max}
              </span>
            ))}
            {entry.vetoReason && (
              <span
                title={entry.vetoReason}
                style={{
                  fontSize: 9, padding: '1px 6px', borderRadius: 3,
                  background: 'rgba(255,71,87,0.10)',
                  border: '1px solid var(--danger)55',
                  color: 'var(--danger)', cursor: 'help',
                }}
              >
                ✕ {entry.vetoReason.slice(0, 40)}{entry.vetoReason.length > 40 ? '…' : ''}
              </span>
            )}
          </div>
        )}

        {/* price grid */}
        <div style={{ display: 'flex', gap: 8 }}>
          {(() => {
            // Points tightened: always positive when SL improved
            const slDiff = entry.slImproved && entry.initialStopLoss != null && entry.stopLoss != null && isFutures
              ? Math.abs(entry.initialStopLoss - entry.stopLoss)
              : null;
            const fmtPts = (d: number) =>
              d >= 100 ? `${Math.round(d)} pts` :
              d >= 10  ? `${d.toFixed(1)} pts`  :
                         `${d.toFixed(2)} pts`;

            return ([
              { label: 'ENTRY',       val: isFutures ? fp(entry.entry)      : `~$${optPrem}`,                                   color: 'var(--text-primary)', sub: '',                                                                             glow: false, initSl: null,                                                                                                                                  diff: null },
              { label: 'STOP LOSS',   val: isFutures ? fp(entry.stopLoss)   : `~$${optPrem ? Math.round(optPrem * 0.5) : '—'}`, color: 'var(--danger)',        sub: entry.stopLoss && isFutures ? pct(entry.entry, entry.stopLoss) : '-50%',      glow: !!entry.slImproved, initSl: entry.slImproved && entry.initialStopLoss != null && isFutures ? fp(entry.initialStopLoss) : null, diff: slDiff != null ? fmtPts(slDiff) : null },
              { label: 'TAKE PROFIT', val: isFutures ? fp(entry.takeProfit) : `~$${optPrem ? Math.round(optPrem * 2) : '—'}`,   color: 'var(--accent)',        sub: entry.takeProfit && isFutures ? pct(entry.entry, entry.takeProfit) : '+100%', glow: false, initSl: null,                                                                                                                                  diff: null },
            ] as { label: string; val: string; color: string; sub: string; glow: boolean; initSl: string | null; diff: string | null }[])
            .map(({ label, val, color, sub, glow, initSl, diff }) => (
              <div key={label} style={{
                background: glow ? 'rgba(29,215,96,0.06)' : 'var(--bg)',
                border: `1px solid ${glow ? 'var(--accent)55' : 'var(--border)'}`,
                borderRadius: 4, padding: '7px 10px', textAlign: 'center', minWidth: 80,
              }}>
                <div style={{ fontSize: 8, color: 'var(--text-faint)', letterSpacing: 1.2, marginBottom: 2 }}>
                  {label}{glow && <span style={{ marginLeft: 3, color: 'var(--accent)', fontWeight: 900 }}>↑</span>}
                </div>
                <div style={{ fontSize: 13, fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>{val}</div>
                {initSl && (
                  <div style={{ fontSize: 7, color: 'var(--text-faint)', marginTop: 1, textDecoration: 'line-through', fontVariantNumeric: 'tabular-nums' }}>
                    {initSl}
                  </div>
                )}
                {diff && (
                  <div style={{ fontSize: 7, color: 'var(--accent)', fontWeight: 700, marginTop: 1, fontVariantNumeric: 'tabular-nums' }}>
                    +{diff}
                  </div>
                )}
                {!initSl && !diff && sub && <div style={{ fontSize: 8, color: 'var(--text-dim)' }}>{sub}</div>}
                {/* 1-second wire: distance from CURRENT price (updates each price tick) */}
                {label === 'STOP LOSS' && liveSlDist != null && (
                  <div
                    title="Live distance from current spot to stop. Negative = price already through stop."
                    style={{
                      fontSize: 7, color: liveSlDist > 0 ? 'var(--text-faint)' : 'var(--danger)',
                      fontVariantNumeric: 'tabular-nums', marginTop: 1,
                    }}
                  >
                    now {liveSlDist >= 0 ? '+' : ''}{liveSlDist.toFixed(2)}%
                  </div>
                )}
                {label === 'TAKE PROFIT' && liveTpDist != null && (
                  <div
                    title="Live distance from current spot to target."
                    style={{
                      fontSize: 7, color: liveTpDist > 0 ? 'var(--text-faint)' : 'var(--accent)',
                      fontVariantNumeric: 'tabular-nums', marginTop: 1,
                    }}
                  >
                    now {liveTpDist >= 0 ? '+' : ''}{liveTpDist.toFixed(2)}%
                  </div>
                )}
              </div>
            ));
          })()}

          {/* Live price — only meaningful for futures (options premium ≠ spot price) */}
          {isFutures && entry.currentPrice && (
            <div
              className={`live-price-cell ${tickClass}`}
              style={{
                background: 'var(--bg)',
                border: `1px solid ${livePnl != null && livePnl >= 0 ? '#00d4aa44' : '#ff475744'}`,
                borderRadius: 4, padding: '7px 10px', textAlign: 'center', minWidth: 80,
              }}
              title="NOW = live spot price · updates every 1 s from SSE prices event"
            >
              <div style={{ fontSize: 8, color: 'var(--text-faint)', letterSpacing: 1.2, marginBottom: 2 }}>NOW</div>
              <div style={{ fontSize: 14, fontWeight: 900, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                {fp(entry.currentPrice)}
              </div>
              {livePnl != null && (
                <div style={{
                  fontSize: 8, fontWeight: 700,
                  color: livePnl >= 0 ? 'var(--accent)' : 'var(--danger)',
                }}>
                  {livePnl >= 0 ? '+' : ''}{livePnl.toFixed(2)}%
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* RIGHT — action */}
      <div style={{
        width: 130, flexShrink: 0, padding: '14px 10px',
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
              padding: '11px 0', borderRadius: 4, cursor: hasOpen ? 'default' : 'pointer',
              background: hasOpen ? 'var(--bg)' : entry.direction === 'long' ? '#003d2e' : '#3d0014',
              color: hasOpen ? 'var(--text-faint)' : dirColor,
              border: `1px solid ${hasOpen ? 'var(--border)' : dirColor + 'cc'}`,
              fontFamily: 'inherit', fontSize: 11, fontWeight: 900, letterSpacing: 0.5,
              opacity: placing ? 0.6 : 1,
            }}
          >
            {tradeLabel(placing, hasOpen, tradeActionLabel)}
          </button>
        )}
      </div>
    </div>

    {/* ── Order confirmation modal — side-by-side layout ─────────── */}
    {showConfirm && (
      <div
        onClick={e => { if (e.target === e.currentTarget && modalStatus.type !== 'pending') closeModal(); }}
        style={{
          position: 'fixed', inset: 0, zIndex: 4000,
          background: 'rgba(0,0,0,0.82)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 16,
        }}
      >
        <div style={{
          background: 'var(--bg-card)',
          border: `1px solid ${dirColor}44`,
          borderRadius: 12,
          width: 760, maxWidth: '98vw',
          boxShadow: `0 24px 80px rgba(0,0,0,0.7), 0 0 0 1px ${dirColor}22`,
          overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
          maxHeight: '94vh',
        }}>

          {/* ══ HEADER ══════════════════════════════════════════════════ */}
          <div style={{
            background: direction === 'long'
              ? 'linear-gradient(135deg, #002a1e 0%, #001a12 100%)'
              : 'linear-gradient(135deg, #2a0010 0%, #1a0008 100%)',
            borderBottom: `1px solid ${dirColor}33`,
            padding: '14px 20px',
            display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
          }}>
            {/* Direction indicator */}
            <div style={{
              width: 36, height: 36, borderRadius: 8, flexShrink: 0,
              background: dirColor + '20',
              border: `1px solid ${dirColor}55`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 16, color: dirColor, fontWeight: 900,
            }}>
              {direction === 'long' ? '▲' : '▼'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                <span style={{ fontSize: 15, fontWeight: 900, color: 'var(--text-primary)', letterSpacing: 0.5 }}>
                  {isFutures ? entry.futuresSymbol : `${entry.optType === 'CE' ? 'CALL' : 'PUT'} ${fp(entry.optStrike)}`}
                </span>
                <span style={{
                  fontSize: 9, fontWeight: 800, letterSpacing: 0.8,
                  color: isLive ? 'var(--accent)' : '#88aaff',
                  background: isLive ? 'var(--accent)15' : '#88aaff15',
                  border: `1px solid ${isLive ? 'var(--accent)44' : '#88aaff44'}`,
                  borderRadius: 4, padding: '2px 7px',
                }}>{isLive ? '● LIVE' : '◎ PAPER'}</span>
                {entry.regime && (
                  <span style={{ fontSize: 9, color: 'var(--text-faint)', background: 'rgba(255,255,255,0.06)', borderRadius: 3, padding: '1px 6px' }}>
                    {entry.regime.replace(/_/g, ' ')}
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>
                {direction === 'long' ? 'BUY LONG' : 'SELL SHORT'} · Score {entry.score} · ADX {entry.adx?.toFixed(0) ?? '—'}
              </div>
            </div>
            {/* Current price */}
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ fontSize: 18, fontWeight: 900, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                {fp(spotPrice)}
              </div>
              <div style={{ fontSize: 9, color: 'var(--text-faint)' }}>SPOT PRICE</div>
            </div>
            <button onClick={modalStatus.type === 'pending' ? undefined : closeModal} style={{
              background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)',
              color: 'var(--text-muted)', cursor: 'pointer', borderRadius: 6,
              width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 14, flexShrink: 0,
            }}>✕</button>
          </div>

          {/* ══ DIRECTION TABS (full width) ═════════════════════════════ */}
          <div style={{ display: 'flex', background: 'var(--bg)', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
            {(['long','short'] as const).map(d => {
              const active = d === direction;
              const col    = d === 'long' ? 'var(--accent)' : 'var(--danger)';
              return (
                <button key={d} onClick={() => setDirection(d)} style={{
                  flex: 1, padding: '11px 0', textAlign: 'center',
                  background: active ? (d === 'long' ? 'rgba(0,212,170,0.1)' : 'rgba(255,71,87,0.1)') : 'transparent',
                  color: active ? col : 'var(--text-dim)',
                  fontWeight: 900, fontSize: 13, letterSpacing: 0.5,
                  border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                  borderBottom: active ? `2px solid ${col}` : '2px solid transparent',
                  borderRight: d === 'long' ? '1px solid var(--border)' : 'none',
                  transition: 'all 0.12s',
                }}>
                  {d === 'long' ? '▲ BUY / LONG' : '▼ SELL / SHORT'}
                </button>
              );
            })}
          </div>

          {/* ══ SIDE-BY-SIDE BODY ════════════════════════════════════════ */}
          <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>

            {/* ── LEFT PANEL: Order parameters ── */}
            <div style={{
              width: '50%', borderRight: '1px solid var(--border)',
              overflowY: 'auto', padding: '16px',
              display: 'flex', flexDirection: 'column', gap: 14,
            }}>

              {/* Override warning */}
              {direction !== entry.direction && (
                <div style={{
                  padding: '8px 12px', borderLeft: '3px solid #f0c040',
                  background: '#f0c04010', border: '1px solid #f0c04033',
                  borderRadius: 6, display: 'flex', gap: 8, alignItems: 'flex-start',
                }}>
                  <span style={{ fontSize: 12, flexShrink: 0 }}>⚠</span>
                  <div style={{ fontSize: 10, color: '#c8941a', lineHeight: 1.5 }}>
                    Signal recommends <strong style={{ color: '#f0c040' }}>
                      {entry.direction === 'long' ? 'BUY' : 'SELL'}
                    </strong> — you're counter-trading.
                  </div>
                </div>
              )}

              {/* Leverage */}
              {isFutures && (
                <div>
                  <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 8 }}>LEVERAGE</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <button onClick={levDown} disabled={LOT_LEVERAGES.indexOf(leverage) === 0}
                      style={{ ...sBtn, width: 28, height: 28, opacity: LOT_LEVERAGES.indexOf(leverage) === 0 ? 0.3 : 1 }}>&minus;</button>
                    <span style={{
                      flex: 1, textAlign: 'center', fontSize: 22, fontWeight: 900,
                      fontVariantNumeric: 'tabular-nums',
                      color: leverage !== snapLev(entry.leverage) ? '#f0c040' : dirColor,
                    }}>{leverage}×</span>
                    <button onClick={levUp} disabled={LOT_LEVERAGES.indexOf(leverage) === LOT_LEVERAGES.length - 1}
                      style={{ ...sBtn, width: 28, height: 28, opacity: LOT_LEVERAGES.indexOf(leverage) === LOT_LEVERAGES.length - 1 ? 0.3 : 1 }}>+</button>
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {LOT_LEVERAGES.map(l => (
                      <button key={l} onClick={() => setLeverage(l)} style={{
                        flex: 1, padding: '6px 0', borderRadius: 5, fontFamily: 'inherit',
                        fontSize: 11, fontWeight: 700, cursor: 'pointer',
                        background: leverage === l ? dirColor + '20' : 'var(--bg)',
                        color: leverage === l ? dirColor : 'var(--text-faint)',
                        border: `1px solid ${leverage === l ? dirColor + '66' : 'var(--border)'}`,
                        transition: 'all 0.1s',
                      }}>{l}×</button>
                    ))}
                  </div>
                  {leverage !== entry.leverage && (
                    <div style={{ marginTop: 5, fontSize: 9, color: '#f0c040' }}>
                      Signal suggests {entry.leverage}× — higher leverage increases risk
                    </div>
                  )}
                </div>
              )}

              {/* Order type */}
              <div>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 8 }}>ORDER TYPE</div>
                <div style={{ display: 'flex', background: 'var(--bg)', borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)' }}>
                  {([
                    { id: 'market', label: 'Market' },
                    { id: 'limit',  label: 'Limit'  },
                    { id: 'maker',  label: 'Maker', hint: 'Post-only — 0% fee, rebate eligible' },
                  ] as { id: string; label: string; hint?: string }[]).map((t, i) => (
                    <button key={t.id} onClick={() => setOrderType(t.id as typeof orderType)} title={t.hint} style={{
                      flex: 1, padding: '8px 0', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                      fontSize: 11, fontWeight: 700, letterSpacing: 0.3,
                      background: orderType === t.id ? dirColor + '18' : 'transparent',
                      color: orderType === t.id ? dirColor : 'var(--text-faint)',
                      borderRight: i < 2 ? '1px solid var(--border)' : 'none',
                      transition: 'all 0.1s',
                    }}>{t.label}</button>
                  ))}
                </div>
              </div>

              {/* Price */}
              <div>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 8 }}>
                  {orderType === 'market' ? 'MARKET PRICE' : 'LIMIT PRICE'}
                </div>
                {orderType === 'limit' || orderType === 'maker' ? (
                  <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg)', border: `1px solid ${dirColor}55`, borderRadius: 7, padding: '0 10px 0 14px' }}>
                    <input type="number" value={limitPrice} onChange={e => setLimitPrice(e.target.value)}
                      style={{ flex: 1, background: 'none', border: 'none', color: 'var(--text-primary)', fontFamily: 'inherit', fontSize: 16, fontWeight: 800, padding: '10px 0', outline: 'none', fontVariantNumeric: 'tabular-nums' }} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginRight: 6 }}>
                      <button onClick={() => setLimitPrice(p => String(Math.round((parseFloat(p) || spotPrice) + priceStep)))}
                        style={{ ...sBtn, height: 14, fontSize: 9 }}>▲</button>
                      <button onClick={() => setLimitPrice(p => String(Math.max(0, Math.round((parseFloat(p) || spotPrice) - priceStep))))}
                        style={{ ...sBtn, height: 14, fontSize: 9 }}>▼</button>
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>USD</span>
                  </div>
                ) : (
                  <div style={{ padding: '10px 14px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 7, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: dirColor, fontSize: 16, fontWeight: 800, fontVariantNumeric: 'tabular-nums' }}>{fp(spotPrice)}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>Best {direction === 'long' ? 'Ask' : 'Bid'}</span>
                  </div>
                )}
              </div>

              {/* Quantity */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-faint)', letterSpacing: 1 }}>QUANTITY</span>
                  <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>1 Lot = {lotInfo.lotSize} {lotInfo.unit}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 7, padding: '0 12px' }}>
                  <input type="number" min="1" step={qtyUnit === 'lot' ? 1 : undefined} value={qtyValue}
                    onChange={e => setQtyValue(e.target.value)}
                    style={{ flex: 1, background: 'none', border: 'none', color: 'var(--text-primary)', fontFamily: 'inherit', fontSize: 16, fontWeight: 800, padding: '10px 0', outline: 'none', fontVariantNumeric: 'tabular-nums' }} />
                  <select value={qtyUnit} onChange={e => { setQtyUnit(e.target.value); setQtyValue('1'); }}
                    style={{ background: 'none', border: 'none', color: '#f0c040', fontFamily: 'inherit', fontSize: 11, fontWeight: 700, cursor: 'pointer', outline: 'none' }}>
                    <option value="lot">Lot</option>
                    <option value="usd">USD</option>
                    <option value={lotInfo.unit}>{lotInfo.unit}</option>
                  </select>
                </div>
                <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
                  {[10,25,50,75,100].map(pct => {
                    const usdAtPct = availFunds
                      ? availFunds * leverage * (pct / 100)
                      : notionalUsd * (pct / 100);
                    return (
                      <button key={pct} onClick={() => { setQtyUnit('usd'); setQtyValue(String(Math.round(usdAtPct))); }}
                        style={{ flex: 1, padding: '6px 0', borderRadius: 5, background: 'var(--bg)', color: 'var(--text-dim)', border: '1px solid var(--border)', fontSize: 10, fontFamily: 'inherit', cursor: 'pointer', fontWeight: 700, transition: 'all 0.1s' }}>
                        {pct}%
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Order options */}
              <div>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 8 }}>ORDER OPTIONS</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' as const, alignItems: 'center' }}>
                  {orderType !== 'market' && (
                    <div style={{ display: 'flex', background: 'var(--bg)', borderRadius: 5, overflow: 'hidden', border: '1px solid var(--border)' }}>
                      {(['gtc','ioc'] as const).map(t => (
                        <button key={t} onClick={() => setTimeInForce(t)} style={{
                          padding: '5px 10px', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                          fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
                          background: timeInForce === t ? 'var(--bg-card)' : 'transparent',
                          color: timeInForce === t ? 'var(--text-primary)' : 'var(--text-faint)',
                        }} title={t === 'gtc' ? 'Good Till Cancel' : 'Immediate Or Cancel'}>
                          {t.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  )}
                  <button onClick={() => setReduceOnly(r => !r)} style={{
                    padding: '5px 10px', borderRadius: 5, fontFamily: 'inherit', fontSize: 10, fontWeight: 700, cursor: 'pointer',
                    background: reduceOnly ? 'var(--accent)15' : 'var(--bg)',
                    color: reduceOnly ? 'var(--accent)' : 'var(--text-faint)',
                    border: `1px solid ${reduceOnly ? 'var(--accent)44' : 'var(--border)'}`,
                  }} title="Close-only">
                    {reduceOnly ? '✓ Reduce Only' : 'Reduce Only'}
                  </button>
                  <button onClick={() => setScalperMode(s => !s)} style={{
                    padding: '5px 10px', borderRadius: 5, fontFamily: 'inherit', fontSize: 10, fontWeight: 700, cursor: 'pointer',
                    background: scalperMode ? '#f0c04015' : 'var(--bg)',
                    color: scalperMode ? '#f0c040' : 'var(--text-faint)',
                    border: `1px solid ${scalperMode ? '#f0c04044' : 'var(--border)'}`,
                  }}>
                    {scalperMode ? `⚡ ${scalperSecs}s` : '⚡ Scalper'}
                  </button>
                  {scalperMode && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <input type="range" min={5} max={300} step={5} value={scalperSecs}
                        onChange={e => setScalerSecs(parseInt(e.target.value))}
                        style={{ width: 60, accentColor: '#f0c040' }} />
                      <span style={{ fontSize: 9, color: '#f0c040' }}>{scalperSecs}s</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* ── RIGHT PANEL: Bracket + Economics ── */}
            <div style={{
              width: '50%',
              overflowY: 'auto', padding: '16px',
              display: 'flex', flexDirection: 'column', gap: 14,
              background: 'rgba(0,0,0,0.15)',
            }}>

              {/* Bracket Order — always visible */}
              <div>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 8 }}>BRACKET ORDER (TP / SL)</div>
                <BracketPanel
                  spotPrice={spotPrice} direction={direction}
                  lotSize={lotInfo.lotSize} size={size}
                  tpValue={tpValue} setTpValue={setTpValue}
                  slValue={slValue} setSlValue={setSlValue}
                  defaultTp={defaultTp} defaultSl={defaultSl}
                  onStateChange={s => { bracketRef.current = s as typeof bracketRef.current; }}
                />
              </div>

              {/* Economics */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-faint)', letterSpacing: 1 }}>ORDER ECONOMICS</span>
                  <div style={{ display: 'flex', background: 'var(--bg-input)', borderRadius: 4, overflow: 'hidden', border: '1px solid var(--border)' }}>
                    {(['USD','INR'] as const).map(c => (
                      <button key={c} onClick={() => setCurrency(c)} style={{
                        padding: '2px 8px', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                        fontSize: 9, fontWeight: 700,
                        background: currency === c ? 'var(--bg-card)' : 'transparent',
                        color: currency === c ? (c === 'INR' ? '#f0c040' : '#88aaff') : 'var(--text-faint)',
                      }}>{c}</button>
                    ))}
                  </div>
                </div>
                <div style={{ background: 'var(--bg)', borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden' }}>
                  {([
                    { label: 'Notional value', val: fmtCost(notionalUsd), dim: true },
                    { label: `Fee · ${feeRole === 'taker' ? 'Taker 0.05%' : feeRole === 'maker-rebate' ? 'Maker 0% (rebate)' : 'Maker 0.02%'}`,
                      val: feeUsd > 0 ? fmtCost(feeUsd) : 'Rebate eligible', dim: true },
                    { label: 'GST 18% (est.)', val: fmtCost(gstUsd), dim: true },
                    { label: 'Margin required', val: fmtCost(marginUsd) },
                    { label: 'Total required', val: fmtCost(totalCostUsd), bold: true, warn: insufficientFunds },
                  ] as {label:string;val:string;bold?:boolean;warn?:boolean;dim?:boolean}[])
                  .map(({ label, val, bold, warn, dim }) => (
                    <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 12px', borderBottom: '1px solid var(--border)' }}>
                      <span style={{ fontSize: 11, color: dim ? 'var(--text-dim)' : 'var(--text-faint)' }}>{label}</span>
                      <span style={{ fontSize: 11, fontWeight: bold ? 800 : 500, fontVariantNumeric: 'tabular-nums',
                        color: warn ? 'var(--danger)' : bold ? 'var(--text-primary)' : 'var(--text-muted)' }}>{val}</span>
                    </div>
                  ))}
                  {/* Available funds row */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 12px' }}>
                    <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>Available</span>
                    <span style={{ fontSize: 12, fontWeight: 800, fontVariantNumeric: 'tabular-nums',
                      color: availFunds === null ? 'var(--text-faint)' : insufficientFunds ? 'var(--danger)' : 'var(--accent)' }}>
                      {availFunds !== null ? fmtCost(availFunds) : isLive ? '—' : 'Paper'}
                    </span>
                  </div>
                </div>
                {insufficientFunds && (
                  <div style={{ marginTop: 6, fontSize: 10, color: 'var(--danger)', textAlign: 'right' }}>
                    Need {fmtCost(totalCostUsd - (availFunds ?? 0))} more —{' '}
                    <a href="https://www.delta.exchange/app/account/deposit" target="_blank" rel="noopener noreferrer"
                      style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 700 }}>Deposit ↗</a>
                  </div>
                )}
              </div>

              {/* Status banner */}
              {modalStatus.type !== 'idle' && (
                <div style={{
                  padding: '10px 14px', borderRadius: 8,
                  border: `1px solid ${modalStatus.type === 'success' ? '#1ed76044' : modalStatus.type === 'error' ? '#ff475744' : 'var(--border)'}`,
                  background: modalStatus.type === 'success' ? '#0a1f12' : modalStatus.type === 'error' ? '#1f0a0a' : 'var(--bg)',
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                }}>
                  <span style={{ fontSize: 16, flexShrink: 0, lineHeight: 1.3 }}>
                    {modalStatus.type === 'pending' ? '⏳' : modalStatus.type === 'success' ? '✅' : '❌'}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 3,
                      color: modalStatus.type === 'success' ? '#1ed760' : modalStatus.type === 'error' ? '#ff4757' : 'var(--text-muted)' }}>
                      {modalStatus.type === 'pending' ? 'Placing order…' : modalStatus.type === 'success' ? 'Order placed ✓' : 'Order failed'}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-dim)', lineHeight: 1.6, wordBreak: 'break-word' }}>{modalStatus.msg}</div>
                    {modalStatus.type === 'error' && modalStatus.msg.toLowerCase().includes('insufficient margin') && (
                      <a href="https://www.delta.exchange/app/account/deposit" target="_blank" rel="noopener noreferrer"
                        style={{ display: 'inline-block', marginTop: 6, fontSize: 10, fontWeight: 700, color: '#1ed760', textDecoration: 'none', background: '#0a2010', border: '1px solid #1ed76033', borderRadius: 4, padding: '4px 10px' }}>
                        Deposit Funds ↗
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ══ ACTION BUTTON (full width) ══════════════════════════════ */}
          {modalStatus.type === 'success' ? (
            <button onClick={closeModal} style={{
              width: '100%', padding: '16px 0', background: '#0a1f12',
              color: '#1ed760', border: 'none', borderTop: '1px solid #1ed76033',
              fontFamily: 'inherit', fontSize: 14, fontWeight: 900, cursor: 'pointer', letterSpacing: 1,
              flexShrink: 0,
            }}>✓ Done</button>
          ) : (
            <button
              onClick={modalStatus.type === 'pending' ? undefined : submitOrder}
              disabled={insufficientFunds || modalStatus.type === 'pending'}
              style={{
                width: '100%', padding: '17px 0', border: 'none', flexShrink: 0,
                background: insufficientFunds || modalStatus.type === 'pending'
                  ? 'var(--bg-input)'
                  : direction === 'long'
                    ? 'linear-gradient(90deg, #00c87a, #00d4aa)'
                    : 'linear-gradient(90deg, #e02030, #ff4757)',
                color: insufficientFunds || modalStatus.type === 'pending' ? 'var(--text-faint)' : '#fff',
                fontFamily: 'inherit', fontSize: 15, fontWeight: 900, letterSpacing: 1,
                cursor: insufficientFunds || modalStatus.type === 'pending' ? 'not-allowed' : 'pointer',
                borderTop: '1px solid var(--border)',
                transition: 'opacity 0.15s',
                opacity: modalStatus.type === 'pending' ? 0.7 : 1,
                textShadow: '0 1px 2px rgba(0,0,0,0.3)',
              }}
            >
              {modalStatus.type === 'pending' ? 'Placing order…'
                : modalStatus.type === 'error' ? 'Retry Order'
                : `${tradeActionLabel}${isLive ? '' : '  (Paper)'}`}
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

// ── shared state hook (React Query deduplicates across both panels) ────────────

function useSignalsPanelState() {
  const { feed, dismiss, streamStatus } = useSignalFeed();
  const { data: signals }               = useSignals();
  const { data: modeData }            = useTradingMode();
  const { data: exData }              = useExchanges();
  const { data: acctData }            = useAccountSummary();
  const currentMode = modeData?.name ?? '';

  const delta      = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);
  const isLive     = !!(delta?.has_credentials && !delta.is_paper);
  const posMode    = isLive ? 'live' : 'paper';
  const availFunds = acctData?.portfolio?.margin_available ?? null;

  const { data: posData } = usePositions(posMode);

  const positions = posData?.positions;
  const openByUnderlying = useMemo(() => {
    const map: Record<string, number> = {};
    (positions ?? []).forEach(p => {
      if (p.status === 'open' || p.status === 'partially_closed')
        map[p.underlying] = (map[p.underlying] ?? 0) + 1;
    });
    return map;
  }, [positions]);

  return { feed, dismiss, signals, streamStatus, currentMode, isLive, availFunds, openByUnderlying };
}

type PanelState = ReturnType<typeof useSignalsPanelState>;

type FeedFilter  = 'active' | 'armed' | 'expired' | 'all';
type ModeFilter  = 'all' | 'scalping' | 'intraday' | 'swing' | 'positional';
type TrackFilter = 'all' | 'latest' | 'legacy';

const ARMED_STATES = new Set([
  'ENTRY_ARMED_PULLBACK', 'ENTRY_ARMED_CONTINUATION', 'CONFIRMED_SETUP_ACTIVE',
]);

// ── feed body: empty-state + rows + footer (no outer wrapper, no header) ──────

function SignalsFeedBody({
  type, state, filter, localMode, localTrack,
}: {
  type: 'futures' | 'options';
  state: PanelState;
  filter: FeedFilter;
  localMode: ModeFilter;
  localTrack: TrackFilter;
}) {
  const { feed, dismiss, signals, isLive, availFunds, openByUnderlying } = state;
  // localMode='all' means show every mode; otherwise filter to matching mode.
  // This overrides the global currentMode so the pills are truly independent.
  const effectiveMode = localMode === 'all' ? '' : localMode;

  const isFut = type === 'futures';

  // Dedup at render time: if feed transiently contains duplicates (race between
  // stream events), never show more than one card per (underlying, direction).
  // Track filter applied via REST signals data (has `track` field) matching feed entries.
  const trackSignalSet = (() => {
    if (localTrack === 'all') return null;
    const s = signals?.signals ?? [];
    const allowed = new Set(s.filter((sig: any) => sig.track === localTrack).map((sig: any) => sig.underlying));
    return allowed;
  })();
  const visible = (() => {
    const seen = new Set<string>();
    return feed.filter(e => {
      if (e.type !== type) return false;
      // Track filter
      if (trackSignalSet && !trackSignalSet.has(e.underlying)) return false;
      // Local mode filter (overrides global)
      if (effectiveMode && resolveMode(e) !== effectiveMode) return false;
      // Status filter
      if (filter === 'expired')  { if (!e.dismissed) return false; }
      else if (filter === 'armed') { if (e.dismissed || !ARMED_STATES.has(e.currentState)) return false; }
      else if (filter === 'active') { if (e.dismissed) return false; }
      // 'all': show everything
      const key = `${e.underlying}_${resolveMode(e)}_${e.direction}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  })();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      {/* empty state */}
      {visible.length === 0 && (
        <div style={{ background: 'var(--bg-card)', padding: '20px 16px' }}>
          {(() => {
            const fresh = (signals?.signals ?? []).filter((s: any) => s.fresh &&
              (type === 'options' ? s.has_options : true));
            const modeLabel = effectiveMode
              ? effectiveMode.charAt(0).toUpperCase() + effectiveMode.slice(1)
              : '';
            const allIdle        = fresh.length > 0 && fresh.every((s: any) => s.regime === 'IDLE');
            const allFiltered    = fresh.length > 0 && fresh.every((s: any) => s.state === 'FILTERED' || s.state === 'IDLE');
            const avgAtr         = fresh.length > 0
              ? fresh.reduce((a: number, s: any) => a + (s.atr_percentile ?? 50), 0) / fresh.length
              : 50;
            const cooldownActive = allIdle || avgAtr < 30;

            let headline = `No ${modeLabel} ${type} signals right now`;
            let reason   = isFut
              ? 'Watching for supertrend + regime alignment on futures.'
              : 'Watching for CE/PE setups on option-enabled instruments.';
            let badge    = { text: 'WAITING', color: 'var(--text-faint)' };

            if (fresh.length === 0) {
              headline = 'Fetching live data…';
              reason   = 'Signals compute every 30s.';
              badge    = { text: 'LOADING', color: 'var(--text-faint)' };
            } else if (cooldownActive) {
              headline = 'Low volatility — signals paused';
              reason   = 'ATR below 30th percentile. Stronger move needed.';
              badge    = { text: 'COOLDOWN', color: '#f0c040' };
            } else if (allFiltered) {
              headline = `No ${type} trend detected`;
              reason   = 'Regime/ADX filters not met. Fires when trend strengthens.';
              badge    = { text: 'FILTERED', color: 'var(--text-faint)' };
            }

            return (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{
                    fontSize: 9, fontWeight: 700, letterSpacing: 1,
                    color: badge.color, background: badge.color + '18',
                    border: `1px solid ${badge.color}44`, borderRadius: 3, padding: '2px 6px',
                  }}>{badge.text}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)' }}>{headline}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 12 }}>{reason}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {fresh.map((s: any) => {
                    const stateColor: Record<string, string> = {
                      ENTRY_ARMED_PULLBACK: '#44cc88', ENTRY_ARMED_CONTINUATION: '#66ccff',
                      CONFIRMED_SETUP_ACTIVE: '#f0c040', EARLY_SETUP_ACTIVE: '#f0a500',
                      FILTERED: 'var(--text-faint)', IDLE: 'var(--border-light)',
                    };
                    const c = stateColor[s.state] ?? 'var(--text-faint)';
                    // G1: explain *why* this row is filtered. Use the backend
                    // veto_reason when present; otherwise fall back to a
                    // regime/ADX/signal-score hint built from snap fields.
                    const tip = (s.state === 'FILTERED' || s.state === 'IDLE')
                      ? (s.veto_reason
                        ?? (s.regime === 'IDLE'
                          ? `IDLE regime — ATR ${s.atr_percentile?.toFixed?.(0) ?? '?'}% (cooldown)`
                          : `No setup — ADX ${s.adx?.toFixed?.(0) ?? '?'} / signal score ${s.signal_score?.toFixed?.(0) ?? '?'}/20`))
                      : `${s.state.replace(/_/g, ' ')} — score ${(s.score_long || s.score_short || 0).toFixed(0)}/100`;
                    return (
                      <span
                        key={s.underlying}
                        title={tip}
                        style={{
                          fontSize: 10, padding: '3px 8px', borderRadius: 4,
                          background: c + '18', border: `1px solid ${c}44`, color: c, fontWeight: 700,
                          cursor: 'help',
                        }}
                      >
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
        <div className="signal-feed-scroll" style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          {visible.map(entry => (
            <FeedRow
              key={entry.id}
              entry={entry}
              hasOpen={(openByUnderlying[entry.underlying] ?? 0) > 0}
              isLive={isLive}
              availFunds={availFunds}
              showModeTag={localMode === 'all'}
              dismiss={dismiss}
            />
          ))}
        </div>
      )}

      {/* footer */}
      <div style={{
        padding: '5px 14px', background: 'var(--bg)',
        borderTop: '1px solid var(--border)',
        fontSize: 9, color: 'var(--text-faint)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0,
      }}>
        <span>
          {isFut
            ? 'Prices frozen at signal time · NOW = live · Leverage pre-set on Delta'
            : 'Premium estimated · verify on exchange · Strike = nearest round'}
        </span>
        {filter === 'expired' && (
          <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>
            Showing dismissed signals
          </span>
        )}
      </div>
    </div>
  );
}

// Standalone wrapper (for direct use outside the tabbed component)
function SignalsFeedPanel({ type }: { type: 'futures' | 'options' }) {
  const state = useSignalsPanelState();
  return (
    <div style={{ borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)' }}>
      <SignalsFeedBody type={type} state={state} filter="active" localMode="all" localTrack="all" />
    </div>
  );
}

// ── public exports ────────────────────────────────────────────────────────────

// ── tabbed public component ───────────────────────────────────────────────────

export function SignalsTable() {
  const [tab,       setTab]       = React.useState<'futures' | 'options'>('futures');
  const [filter,    setFilter]    = React.useState<FeedFilter>('active');
  const [localMode, setLocalMode] = React.useState<ModeFilter>('all');

  // Single hook instance — both tab-bar counts and SignalsFeedBody share this state.
  const state = useSignalsPanelState();
  const { feed, signals, streamStatus } = state;

  const effectiveMode = localMode === 'all' ? '' : localMode;

  // Count helpers
  const countByFilter = (type: 'futures' | 'options', f: FeedFilter) =>
    feed.filter(e => {
      if (e.type !== type) return false;
      if (effectiveMode && resolveMode(e) !== effectiveMode) return false;
      if (f === 'expired')  return e.dismissed;
      if (f === 'armed')    return !e.dismissed && ARMED_STATES.has(e.currentState);
      if (f === 'active')   return !e.dismissed;
      return true; // 'all'
    }).length;

  const countByMode = (type: 'futures' | 'options', m: ModeFilter) =>
    feed.filter(e => {
      if (e.type !== type || e.dismissed) return false;
      return m === 'all' ? true : resolveMode(e) === m;
    }).length;

  const futArmed = countByFilter('futures', 'armed');
  const optArmed = countByFilter('options', 'armed');

  const INSTRUMENT_TABS: Array<{ id: 'futures' | 'options'; label: string; icon: string; accent: string; armed: number }> = [
    { id: 'futures', label: 'FUTURES', icon: '▣', accent: 'var(--accent)', armed: futArmed },
    { id: 'options', label: 'OPTIONS', icon: '◈', accent: '#a78bfa',      armed: optArmed },
  ];

  const hasOptAlert = tab === 'futures' && optArmed > 0;
  const freshCount  = (signals?.signals ?? []).filter((s: any) => s.fresh).length;

  const MODE_PILLS: Array<{ id: ModeFilter; label: string }> = [
    { id: 'all',        label: 'ALL' },
    { id: 'scalping',   label: 'SCALPING' },
    { id: 'intraday',   label: 'INTRADAY' },
    { id: 'swing',      label: 'SWING' },
    { id: 'positional', label: 'POSITIONAL' },
  ];

  const TRACK_PILLS: Array<{ id: 'all' | 'latest' | 'legacy'; label: string; color: string }> = [
    { id: 'all',     label: 'ALL',     color: 'var(--text-dim)' },
    { id: 'latest',  label: 'LATEST',  color: '#f59e0b' },
    { id: 'legacy',  label: 'LEGACY',  color: '#8b5cf6' },
  ];

  const [localTrack, setLocalTrack] = React.useState<TrackFilter>('all');

  const STATUS_PILLS: Array<{ id: FeedFilter; label: string }> = [
    { id: 'active',  label: 'ACTIVE' },
    { id: 'armed',   label: 'ARMED' },
    { id: 'all',     label: 'ALL' },
    { id: 'expired', label: 'EXPIRED' },
  ];

  const pillBase = (active: boolean): React.CSSProperties => ({
    padding: '3px 10px',
    borderRadius: 5,
    fontSize: 9,
    fontWeight: 600,
    letterSpacing: '0.07em',
    cursor: 'pointer',
    fontFamily: 'inherit',
    border: active ? '1px solid var(--border-light)' : '1px solid transparent',
    background: active ? 'var(--bg-card)' : 'transparent',
    color: active ? 'var(--text-primary)' : 'var(--text-dim)',
    transition: 'all 0.1s',
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', borderRadius: 0, overflow: 'hidden', border: 'none', borderBottom: '1px solid var(--border)' }}>

      {/* ── Header bar ── */}
      <div style={{
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border)',
        padding: '10px 14px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--text-primary)' }}>
            SIGNAL FEED
          </span>
          <StreamBadge status={streamStatus} />
          {freshCount > 0 && (
            <span style={{
              fontSize: 9, fontWeight: 600, color: 'var(--accent)',
              background: 'var(--accent)14', borderRadius: 4, padding: '2px 7px',
            }}>
              {freshCount} live
            </span>
          )}
        </div>
        {/* Instrument type tabs */}
        <div style={{ display: 'flex', gap: 4 }}>
          {INSTRUMENT_TABS.map(t => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                style={{
                  padding: '4px 14px',
                  borderRadius: 6,
                  border: active ? `1px solid ${t.accent}40` : '1px solid transparent',
                  background: active ? t.accent + '12' : 'transparent',
                  color: active ? t.accent : 'var(--text-dim)',
                  fontFamily: 'inherit', fontSize: 10, fontWeight: 700,
                  letterSpacing: '0.08em', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 6,
                  transition: 'all 0.1s',
                }}
              >
                {t.icon} {t.label}
                {t.armed > 0 && (
                  <span style={{
                    fontSize: 9, fontWeight: 800,
                    color: 'var(--warning)', background: 'var(--warning)18',
                    borderRadius: 10, padding: '1px 6px',
                  }}>{t.armed}</span>
                )}
                {t.id === 'options' && hasOptAlert && !active && (
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#a78bfa', boxShadow: '0 0 4px #a78bfa' }} />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Dual filter row: mode pills LEFT · status pills RIGHT ── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 14px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg)',
        gap: 8,
      }}>
        {/* LEFT — trading mode */}
        <div style={{ display: 'flex', gap: 2 }}>
          {MODE_PILLS.map(m => {
            const cnt    = countByMode(tab, m.id);
            const active = localMode === m.id;
            return (
              <button key={m.id} onClick={() => setLocalMode(m.id)} style={pillBase(active)}>
                {m.label}
                {cnt > 0 && (
                  <span style={{ marginLeft: 4, color: 'var(--text-faint)', fontWeight: 400 }}>{cnt}</span>
                )}
              </button>
            );
          })}
        </div>

        {/* Subtle vertical divider */}
        <div style={{ width: 1, height: 16, background: 'var(--border)', flexShrink: 0 }} />

        {/* Track filter */}
        <div style={{ display: 'flex', gap: 2 }}>
          {TRACK_PILLS.map(t => {
            const cnt = (signals?.signals ?? []).filter((s: any) =>
              s.fresh && (t.id === 'all' || s.strategy === t.id)
            ).length;
            const active = localTrack === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setLocalTrack(t.id)}
                style={{
                  ...pillBase(active),
                  color: active ? t.color : 'var(--text-dim)',
                  borderColor: active ? t.color + '40' : 'transparent',
                }}
              >
                {t.label}
                {cnt > 0 && (
                  <span style={{ marginLeft: 4, color: 'var(--text-faint)', fontWeight: 400 }}>{cnt}</span>
                )}
              </button>
            );
          })}
        </div>

        {/* RIGHT — status filter */}
        <div style={{ display: 'flex', gap: 2 }}>
          {STATUS_PILLS.map(f => {
            const cnt    = countByFilter(tab, f.id);
            const active = filter === f.id;
            return (
              <button key={f.id} onClick={() => setFilter(f.id)} style={pillBase(active)}>
                {f.label}
                <span style={{ marginLeft: 4, color: 'var(--text-faint)', fontWeight: 400 }}>{cnt}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Feed body — flex: 1 so it fills remaining terminal height ── */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <SignalsFeedBody type={tab} state={state} filter={filter} localMode={localMode} localTrack={localTrack} />
      </div>
    </div>
  );
}
