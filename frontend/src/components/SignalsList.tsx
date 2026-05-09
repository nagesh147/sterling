import React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSignals } from '../hooks/useSignals';
import type { SignalItem } from '../hooks/useSignals';
import { useSelectedUnderlying, useSetSelectedUnderlying } from '../store/useStore';
import { usePositions } from '../hooks/usePositions';
import { api } from '../utils/api';

function useDirectEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { underlying: string; direction: string; leverage: number; notes: string }) =>
      api.post('/api/v1/positions/enter-direct', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }),
  });
}

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return 'N/A';
  if (v >= 10_000) return v.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (v >= 100)   return v.toLocaleString('en-US', { maximumFractionDigits: 2 });
  return v.toFixed(4);
}

const STATE_RANK: Record<string, number> = {
  ENTRY_ARMED_PULLBACK: 0, ENTRY_ARMED_CONTINUATION: 1,
  CONFIRMED_SETUP_ACTIVE: 2, EARLY_SETUP_ACTIVE: 3,
  FILTERED: 4, IDLE: 5,
};

type ActionLevel = 'enter' | 'ready' | 'early' | 'watching';

function actionLevel(state: string): ActionLevel {
  if (state.startsWith('ENTRY_ARMED')) return 'enter';
  if (state === 'CONFIRMED_SETUP_ACTIVE') return 'ready';
  if (state === 'EARLY_SETUP_ACTIVE') return 'early';
  return 'watching';
}

const ACTION_CFG: Record<ActionLevel, { label: string; bg: string; color: string; border: string }> = {
  enter:    { label: 'ENTER NOW',  bg: '#0f2a0f', color: '#44cc88', border: '#44cc88' },
  ready:    { label: 'GET READY',  bg: '#2a2000', color: '#f0c040', border: '#f0c040' },
  early:    { label: 'EARLY',      bg: '#1a1a00', color: '#f0a500', border: '#f0a500' },
  watching: { label: 'WATCHING',   bg: 'transparent', color: '#333', border: '#2a2a2a' },
};

// ── asset icon/badge ──────────────────────────────────────────────────────────

function AssetBadge({ sym, direction }: { sym: string; direction: string }) {
  const color = direction === 'long' ? '#44cc88' : direction === 'short' ? '#cc4444' : '#555';
  const bg    = direction === 'long' ? '#0f2a0f' : direction === 'short' ? '#2a0f0f' : '#1a1a1a';
  return (
    <div style={{
      width: 44, height: 44, borderRadius: 8, flexShrink: 0,
      background: bg, border: `1px solid ${color}44`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: sym.length > 3 ? 9 : 12, fontWeight: 900, color, letterSpacing: 0.5,
    }}>
      {sym.slice(0, 4)}
    </div>
  );
}

// ── price cell ────────────────────────────────────────────────────────────────

function PriceCell({
  label, value, highlight, dimmed,
}: { label: string; value: string; highlight?: boolean; dimmed?: boolean }) {
  return (
    <div style={{ flex: 1, textAlign: 'center' as const }}>
      <div style={{ fontSize: 9, color: '#444', letterSpacing: 1, marginBottom: 4 }}>{label}</div>
      <div style={{
        padding: '6px 8px', borderRadius: 4,
        background: highlight ? '#1a2e1a' : dimmed ? '#111' : '#131313',
        border: `1px solid ${highlight ? '#44cc8833' : '#1e1e1e'}`,
        fontSize: 14, fontWeight: 700,
        color: dimmed ? '#333' : highlight ? '#44cc88' : '#888',
        fontVariantNumeric: 'tabular-nums',
        minWidth: 80,
      }}>
        {value}
      </div>
    </div>
  );
}

// ── stop/target cells use direction colour ────────────────────────────────────

function LevelCell({ label, value, type }: { label: string; value: string; type: 'stop' | 'target' }) {
  const color = type === 'stop' ? '#cc4444' : '#44cc88';
  const isNA = value === 'N/A';
  return (
    <div style={{ flex: 1, textAlign: 'center' as const }}>
      <div style={{ fontSize: 9, color: '#444', letterSpacing: 1, marginBottom: 4 }}>{label}</div>
      <div style={{
        padding: '6px 8px', borderRadius: 4,
        background: isNA ? '#111' : type === 'stop' ? '#2a0f0f' : '#0f2a0f',
        border: `1px solid ${isNA ? '#1e1e1e' : color + '33'}`,
        fontSize: 14, fontWeight: 700,
        color: isNA ? '#2a2a2a' : color,
        fontVariantNumeric: 'tabular-nums',
        minWidth: 80,
      }}>
        {value}
      </div>
    </div>
  );
}

// ── single signal row ─────────────────────────────────────────────────────────

function SignalRow({
  item, selected, hasOpenPosition, onSelect,
}: {
  item: SignalItem;
  selected: boolean;
  hasOpenPosition: boolean;
  onSelect: () => void;
}) {
  const level   = actionLevel(item.state);
  const actCfg  = ACTION_CFG[level];
  const dirColor = item.direction === 'long' ? '#44cc88' : item.direction === 'short' ? '#cc4444' : '#444';
  const score   = item.direction === 'short' ? item.score_short : item.score_long;
  const isActionable = level === 'enter' || level === 'ready';
  const { mutate: enterDirect, isPending: entering } = useDirectEntry();

  const handleAction = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (level === 'enter' && !hasOpenPosition) {
      enterDirect({
        underlying: item.underlying,
        direction: item.direction,
        leverage: 1,
        notes: `Signal entry — ${item.state}`,
      });
    }
  };

  const entryStr  = fmtPrice(item.spot_price);
  const stopStr   = fmtPrice(item.stop_price);
  const targetStr = fmtPrice(item.target_price);

  return (
    <div
      onClick={onSelect}
      style={{
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '14px 16px',
        background: selected ? '#13131f' : '#141414',
        borderLeft: `3px solid ${selected ? '#88aaff' : isActionable ? dirColor : 'transparent'}`,
        borderBottom: '1px solid #1a1a1a',
        cursor: 'pointer',
        transition: 'background 0.15s',
      }}
    >
      {/* left: asset + info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, width: 200, flexShrink: 0 }}>
        <AssetBadge sym={item.underlying} direction={item.direction} />
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 7 }}>
            <span style={{ fontSize: 14, fontWeight: 800, color: '#e0e0e0', letterSpacing: 0.5 }}>
              {item.underlying}
            </span>
            {item.spot_price != null && (
              <span style={{ fontSize: 11, color: '#555', fontVariantNumeric: 'tabular-nums' }}>
                ({fmtPrice(item.spot_price)})
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3 }}>
            <span style={{ fontSize: 10, color: '#444' }}>
              {level === 'enter' ? 'Active' : level === 'ready' ? 'Confirmed' : level === 'early' ? 'Forming' : 'Watching'}
            </span>
            {hasOpenPosition && (
              <span style={{ fontSize: 9, color: '#44cc88', background: '#44cc8818', border: '1px solid #44cc8833', borderRadius: 3, padding: '0 4px' }}>OPEN</span>
            )}
          </div>
          {item.regime ? (
            <div style={{ fontSize: 9, color: '#3a3a3a', marginTop: 2, letterSpacing: 0.3 }}>
              {item.regime.replace(/_/g, ' ')}
            </div>
          ) : null}
        </div>
      </div>

      {/* direction badge */}
      <div style={{ width: 52, flexShrink: 0, textAlign: 'center' as const }}>
        {item.direction !== 'neutral' ? (
          <span style={{
            fontSize: 12, fontWeight: 900, color: dirColor, letterSpacing: 1,
            background: dirColor + '18', border: `1px solid ${dirColor}44`,
            borderRadius: 4, padding: '4px 8px', display: 'inline-block',
          }}>
            {item.direction === 'long' ? 'BUY' : 'SELL'}
          </span>
        ) : (
          <span style={{ color: '#2a2a2a', fontSize: 11 }}>—</span>
        )}
      </div>

      {/* price cells */}
      <div style={{ display: 'flex', gap: 8, flex: 1 }}>
        <PriceCell
          label="ENTRY PRICE"
          value={entryStr}
          highlight={isActionable && item.spot_price != null}
          dimmed={!item.fresh}
        />
        <LevelCell label="STOP LOSS" value={stopStr} type="stop" />
        <LevelCell label="TAKE PROFIT" value={targetStr} type="target" />
      </div>

      {/* score */}
      <div style={{ width: 50, flexShrink: 0, textAlign: 'center' as const }}>
        {score > 0 ? (
          <>
            <div style={{ fontSize: 9, color: '#333', letterSpacing: 1, marginBottom: 4 }}>SCORE</div>
            <div style={{
              fontSize: 16, fontWeight: 800, fontVariantNumeric: 'tabular-nums',
              color: score >= 75 ? '#44cc88' : score >= 55 ? '#f0c040' : '#555',
            }}>
              {score.toFixed(0)}
            </div>
          </>
        ) : null}
      </div>

      {/* action button */}
      <div style={{ width: 110, flexShrink: 0 }}>
        <button
          onClick={handleAction}
          disabled={level === 'watching' || level === 'early' || hasOpenPosition || entering}
          style={{
            width: '100%', padding: '9px 0',
            background: hasOpenPosition && level === 'enter' ? '#111' : actCfg.bg,
            color: hasOpenPosition && level === 'enter' ? '#333' : actCfg.color,
            border: `1px solid ${hasOpenPosition && level === 'enter' ? '#1e1e1e' : actCfg.border}`,
            borderRadius: 5, cursor: level === 'enter' && !hasOpenPosition ? 'pointer' : 'default',
            fontFamily: 'inherit', fontSize: 11, fontWeight: 800, letterSpacing: 0.5,
            opacity: level === 'watching' ? 0.3 : 1,
            transition: 'opacity 0.15s',
          }}
        >
          {entering ? 'Entering…' : hasOpenPosition && level === 'enter' ? 'OPEN' : actCfg.label}
        </button>
        {(item.green_arrow || item.red_arrow) && (
          <div style={{ textAlign: 'center' as const, marginTop: 4, fontSize: 10 }}>
            {item.green_arrow && <span style={{ color: '#44cc88' }}>▲ </span>}
            {item.red_arrow   && <span style={{ color: '#cc4444' }}>▼ </span>}
            <span style={{ color: '#333' }}>arrow</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export function SignalsList() {
  const { data, isLoading } = useSignals();
  const { data: posData } = usePositions();
  const selected    = useSelectedUnderlying();
  const setSelected = useSetSelectedUnderlying();

  const openByUnderlying: Record<string, number> = {};
  (posData?.positions ?? []).forEach(p => {
    if (p.status === 'open' || p.status === 'partially_closed') {
      openByUnderlying[p.underlying] = (openByUnderlying[p.underlying] || 0) + 1;
    }
  });

  const signals = data?.signals ?? [];
  const actionable = signals.filter(s => STATE_RANK[s.state] <= 2);
  const ts = data?.timestamp_ms
    ? new Date(data.timestamp_ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '';

  return (
    <div style={{ marginBottom: 16, borderRadius: 6, overflow: 'hidden', border: '1px solid #1e1e1e' }}>

      {/* header bar */}
      <div style={{
        background: '#14291a',
        borderBottom: '1px solid #1e3a22',
        padding: '10px 16px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{
            fontSize: 12, fontWeight: 900, color: '#44cc88', letterSpacing: 2,
          }}>
            ● LIVE SIGNALS
          </span>
          <span style={{ fontSize: 10, color: '#2a4a2a', letterSpacing: 1 }}>
            {signals.length} instruments
          </span>
          {actionable.length > 0 && (
            <span style={{
              fontSize: 10, fontWeight: 700, color: '#f0c040',
              background: '#2a2000', border: '1px solid #f0c04044',
              borderRadius: 3, padding: '2px 8px', letterSpacing: 0.5,
            }}>
              {actionable.length} ACTIONABLE
            </span>
          )}
        </div>
        <span style={{ fontSize: 9, color: '#1e3a22', fontVariantNumeric: 'tabular-nums' }}>
          {isLoading ? 'refreshing…' : ts}
        </span>
      </div>

      {/* column headers */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '6px 16px 6px 19px',
        background: '#0f0f0f', borderBottom: '1px solid #1a1a1a',
      }}>
        <div style={{ width: 200, flexShrink: 0, fontSize: 9, color: '#2a2a2a', letterSpacing: 1 }}>INSTRUMENT</div>
        <div style={{ width: 52, flexShrink: 0, fontSize: 9, color: '#2a2a2a', letterSpacing: 1, textAlign: 'center' as const }}>DIR</div>
        <div style={{ flex: 1, display: 'flex', gap: 8 }}>
          {['ENTRY PRICE', 'STOP LOSS', 'TAKE PROFIT'].map(h => (
            <div key={h} style={{ flex: 1, textAlign: 'center' as const, fontSize: 9, color: '#2a2a2a', letterSpacing: 1 }}>{h}</div>
          ))}
        </div>
        <div style={{ width: 50, flexShrink: 0 }} />
        <div style={{ width: 110, flexShrink: 0 }} />
      </div>

      {/* rows */}
      {isLoading && signals.length === 0 ? (
        <div style={{ padding: '24px 16px', background: '#141414', color: '#2a2a2a', fontSize: 12 }}>
          Computing signals…
        </div>
      ) : signals.length === 0 ? (
        <div style={{ padding: '24px 16px', background: '#141414', color: '#333', fontSize: 12 }}>
          No instruments found
        </div>
      ) : (
        signals.map(item => (
          <SignalRow
            key={item.underlying}
            item={item}
            selected={item.underlying === selected}
            hasOpenPosition={(openByUnderlying[item.underlying] || 0) > 0}
            onSelect={() => setSelected(item.underlying)}
          />
        ))
      )}
    </div>
  );
}
