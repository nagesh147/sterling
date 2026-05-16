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
              </div>
            ));
          })()}

          {/* Live price — only meaningful for futures (options premium ≠ spot price) */}
          {isFutures && entry.currentPrice && (
            <div className="live-price-cell" style={{
              background: 'var(--bg)', border: `1px solid ${livePnl != null && livePnl >= 0 ? '#00d4aa44' : '#ff475744'}`,
              borderRadius: 4, padding: '7px 10px', textAlign: 'center', minWidth: 80,
            }}>
              <div style={{ fontSize: 8, color: 'var(--text-faint)', letterSpacing: 1.2, marginBottom: 2 }}>NOW</div>
              <div style={{ fontSize: 14, fontWeight: 900, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
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

    {/* ── Order confirmation modal ─────────────────────────────────── */}
    {showConfirm && (
      <div
        style={{
          position: 'fixed', inset: 0, zIndex: 4000,
          background: 'rgba(0,0,0,0.75)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 10, width: 380,
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
            {([
              { id: 'market', label: 'Market' },
              { id: 'limit',  label: 'Limit'  },
              { id: 'maker',  label: 'Maker Only', hint: 'Post-only — rejected if it would take liquidity. Fee rebate eligible.' },
            ] as { id: string; label: string; hint?: string }[]).map(t => (
              <button key={t.id} onClick={() => setOrderType(t.id as typeof orderType)} title={t.hint} style={{
                background: 'none', border: 'none', padding: '7px 14px',
                fontFamily: 'inherit', fontSize: 12, fontWeight: 700, cursor: 'pointer',
                color: orderType === t.id ? dirColor : 'var(--text-faint)',
                borderBottom: orderType === t.id ? `2px solid ${dirColor}` : '2px solid transparent',
                marginBottom: -1,
              }}>{t.label}</button>
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

          {/* ── Order options row: GTC/IOC + Reduce Only + Scalper ── */}
          <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' as const, alignItems: 'center' }}>
            {/* GTC / IOC — only for non-market orders */}
            {orderType !== 'market' && (
              <div style={{ display: 'flex', background: 'var(--bg-input)', borderRadius: 4, overflow: 'hidden', border: '1px solid var(--border)' }}>
                {(['gtc','ioc'] as const).map(t => (
                  <button key={t} onClick={() => setTimeInForce(t)} style={{
                    padding: '3px 9px', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                    fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
                    background: timeInForce === t ? 'var(--bg-card)' : 'transparent',
                    color: timeInForce === t ? 'var(--text-primary)' : 'var(--text-faint)',
                  }} title={t === 'gtc' ? 'Good Till Cancel' : 'Immediate Or Cancel'}>
                    {t.toUpperCase()}
                  </button>
                ))}
              </div>
            )}
            {/* Reduce Only toggle */}
            <button onClick={() => setReduceOnly(r => !r)} style={{
              padding: '3px 10px', borderRadius: 4, fontFamily: 'inherit',
              fontSize: 9, fontWeight: 700, cursor: 'pointer',
              background: reduceOnly ? 'var(--accent)15' : 'transparent',
              color: reduceOnly ? 'var(--accent)' : 'var(--text-faint)',
              border: `1px solid ${reduceOnly ? 'var(--accent)44' : 'var(--border)'}`,
            }} title="Close-only — never opens a new position">
              {reduceOnly ? '✓ ' : ''}Reduce Only
            </button>
            {/* Scalper mode */}
            <button onClick={() => setScalperMode(s => !s)} style={{
              padding: '3px 10px', borderRadius: 4, fontFamily: 'inherit',
              fontSize: 9, fontWeight: 700, cursor: 'pointer',
              background: scalperMode ? '#f0c04015' : 'transparent',
              color: scalperMode ? '#f0c040' : 'var(--text-faint)',
              border: `1px solid ${scalperMode ? '#f0c04044' : 'var(--border)'}`,
            }} title={`One-click order without re-confirming. Auto-cancels unfilled after ${scalperSecs}s.`}>
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
              { label: 'Notional',  val: fmtCost(notionalUsd) },
              { label: `Exchange fee · ${
                  feeRole === 'taker'        ? 'Taker 0.05%'      :
                  feeRole === 'maker-rebate' ? 'Maker-Only 0%'    :
                                               'Maker 0.02%'
                }`, val: feeUsd > 0 ? fmtCost(feeUsd) : feeRole === 'maker-rebate' ? 'Rebate eligible' : fmtCost(feeUsd) },
              { label: 'GST 18% (on fee, est.)', val: fmtCost(gstUsd), hint: true },
              { label: 'Margin required', val: fmtCost(marginUsd) },
              { label: 'Funds req. (margin + fee + GST)', val: fmtCost(totalCostUsd), bold: true, warn: insufficientFunds },
            ].filter(Boolean) as {label:string;val:string;bold?:boolean;warn?:boolean;hint?:boolean}[])
            .map(({ label, val, bold, warn, hint }) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 12px', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: 11, color: hint ? 'var(--text-faint)' : 'var(--text-faint)' }}>{label}</span>
                <span style={{ fontSize: 11, fontWeight: bold ? 700 : 400, color: warn ? 'var(--danger)' : bold ? 'var(--text-primary)' : hint ? '#888' : 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{val}</span>
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 12px' }}>
              <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>Available Funds</span>
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
                : modalStatus.type === 'error' ? `Retry`
                : `${tradeActionLabel}${isLive ? '' : ' (Paper)'}`}
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

// ── feed body: empty-state + rows + footer (no outer wrapper, no header) ──────

function SignalsFeedBody({ type, state }: { type: 'futures' | 'options'; state: PanelState }) {
  const { feed, dismiss, signals, currentMode, isLive, availFunds, openByUnderlying } = state;

  const isFut = type === 'futures';

  // Dedup at render time: if feed transiently contains duplicates (race between
  // stream events), never show more than one card per (underlying, direction).
  const visible = (() => {
    const seen = new Set<string>();
    return feed.filter(e => {
      if (e.dismissed || e.type !== type) return false;
      if (currentMode !== 'all' && currentMode && resolveMode(e) !== currentMode) return false;
      const key = `${e.underlying}_${e.direction}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  })();

  return (
    <>
      {/* empty state */}
      {visible.length === 0 && (
        <div style={{ background: 'var(--bg-card)', padding: '20px 16px' }}>
          {(() => {
            const fresh = (signals?.signals ?? []).filter((s: any) => s.fresh &&
              (type === 'options' ? s.has_options : true));
            const modeLabel = currentMode
              ? currentMode.charAt(0).toUpperCase() + currentMode.slice(1)
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
        <div className="signal-feed-scroll" style={{ maxHeight: 540, overflowY: 'auto' }}>
          {visible.map(entry => (
            <FeedRow
              key={entry.id}
              entry={entry}
              hasOpen={(openByUnderlying[entry.underlying] ?? 0) > 0}
              isLive={isLive}
              availFunds={availFunds}
              showModeTag={currentMode === 'all'}
              dismiss={dismiss}
            />
          ))}
        </div>
      )}

      {/* footer */}
      <div style={{
        padding: '6px 14px', background: 'var(--bg)',
        borderTop: '1px solid var(--border)',
        fontSize: 9, color: 'var(--text-faint)',
      }}>
        {isFut
          ? 'Prices frozen at signal time · NOW = live · Leverage pre-set on Delta'
          : 'Premium estimated · verify on exchange · Strike = nearest round'}
      </div>
    </>
  );
}

// Standalone wrapper (for direct use outside the tabbed component)
function SignalsFeedPanel({ type }: { type: 'futures' | 'options' }) {
  const state = useSignalsPanelState();
  return (
    <div style={{ borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)' }}>
      <SignalsFeedBody type={type} state={state} />
    </div>
  );
}

// ── public exports ────────────────────────────────────────────────────────────

// ── tabbed public component ───────────────────────────────────────────────────

export function SignalsTable() {
  const [tab, setTab] = React.useState<'futures' | 'options'>('futures');
  // Single hook instance — both tab-bar counts and SignalsFeedBody share this state.
  // Calling useSignalsPanelState() a second time (inside SignalsFeedBody) would create
  // a separate useState, causing counts and displayed cards to diverge.
  const state = useSignalsPanelState();
  const { feed, signals, currentMode, streamStatus } = state;

  // Count actionable entries per type so tabs can show a badge
  const count = (type: 'futures' | 'options') =>
    feed.filter(e =>
      !e.dismissed && e.type === type &&
      (currentMode === 'all' || !currentMode || resolveMode(e) === currentMode) &&
      ['ENTRY_ARMED_PULLBACK','ENTRY_ARMED_CONTINUATION','CONFIRMED_SETUP_ACTIVE','EARLY_SETUP_ACTIVE']
        .includes(e.currentState)
    ).length;

  const futCount = count('futures');
  const optCount = count('options');

  const TAB: Array<{ id: 'futures' | 'options'; label: string; icon: string; accent: string; bg: string; cnt: number }> = [
    { id: 'futures', label: 'FUTURES', icon: '▣', accent: 'var(--accent)', bg: '#003d2e', cnt: futCount },
    { id: 'options', label: 'OPTIONS', icon: '◈', accent: '#a78bfa',      bg: '#1a0d2e', cnt: optCount },
  ];

  // Notify when options panel gets a new actionable signal while futures is active
  const hasOptAlert = tab === 'futures' && optCount > 0;

  const freshCount = (signals?.signals ?? []).filter((s: any) => s.fresh).length;

  return (
    <div style={{ marginBottom: 16, borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)' }}>

      {/* ── tab bar ─────────────────────────────────────────────────────── */}
      <div style={{
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border)',
        padding: '0 12px',
        display: 'flex', alignItems: 'stretch', gap: 0,
      }}>
        {TAB.map(t => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                background: active ? t.accent + '0a' : 'none',
                border: 'none', cursor: 'pointer',
                padding: '11px 18px', fontFamily: 'inherit',
                borderBottom: active ? `2px solid ${t.accent}` : '2px solid transparent',
                marginBottom: -1,
                display: 'flex', alignItems: 'center', gap: 7,
                color: active ? t.accent : 'var(--text-faint)',
                transition: 'color 0.15s, border-color 0.15s, background 0.15s',
              }}
            >
              <span style={{ fontSize: 11, fontWeight: 900, letterSpacing: 1.5 }}>
                {t.icon} {t.label}
              </span>
              {t.cnt > 0 && (
                <span style={{
                  fontSize: 10, fontWeight: 800, letterSpacing: 0.3,
                  color: active ? t.accent : 'var(--warning)',
                  background: active ? t.accent + '20' : 'rgba(255,165,2,0.12)',
                  border: `1px solid ${active ? t.accent + '55' : 'rgba(255,165,2,0.3)'}`,
                  borderRadius: 12, padding: '1px 7px', minWidth: 18, textAlign: 'center',
                }}>
                  {t.cnt}
                </span>
              )}
              {t.id === 'options' && hasOptAlert && !active && (
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#a78bfa', flexShrink: 0, boxShadow: '0 0 4px #a78bfa' }} />
              )}
            </button>
          );
        })}

        {/* right-side: stream status + instrument count */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, paddingRight: 6 }}>
          <StreamBadge status={streamStatus} />
          {freshCount > 0 && (
            <span style={{
              fontSize: 9, color: 'var(--text-faint)',
              background: 'var(--bg-input)', border: '1px solid var(--border)',
              borderRadius: 3, padding: '1px 6px', fontFamily: 'inherit',
              letterSpacing: 0.5,
            }}>
              {freshCount} live
            </span>
          )}
        </div>
      </div>

      {/* ── active tab body — same state instance as the tab-bar counts above ── */}
      <SignalsFeedBody type={tab} state={state} />
    </div>
  );
}
