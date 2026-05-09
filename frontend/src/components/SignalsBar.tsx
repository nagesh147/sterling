import React from 'react';
import { useSignals } from '../hooks/useSignals';
import type { SignalItem } from '../hooks/useSignals';
import { useSelectedUnderlying, useSetSelectedUnderlying } from '../store/useStore';

// ── colour helpers ────────────────────────────────────────────────────────────

const STATE_META: Record<string, { color: string; label: string }> = {
  ENTRY_ARMED_PULLBACK:     { color: '#44aaff', label: 'ARMED·PB' },
  ENTRY_ARMED_CONTINUATION: { color: '#66ccff', label: 'ARMED·CT' },
  CONFIRMED_SETUP_ACTIVE:   { color: '#f0c040', label: 'CONFIRMED' },
  EARLY_SETUP_ACTIVE:       { color: '#f0a500', label: 'EARLY' },
  FILTERED:                 { color: '#555',    label: 'FILTERED' },
  IDLE:                     { color: '#333',    label: 'IDLE' },
};

const REGIME_COLOR = (r: string) => {
  const u = r.toUpperCase();
  if (u.includes('BULL')) return '#44cc88';
  if (u.includes('BEAR')) return '#cc4444';
  if (u === 'VOLATILE')   return '#f0c040';
  if (u === 'RANGING' || u === 'CHOPPY') return '#888';
  return '#555';
};

const DIR_COLOR = (d: string) =>
  d === 'long' ? '#44cc88' : d === 'short' ? '#cc4444' : '#555';

const SCORE_COLOR = (s: number) =>
  s >= 75 ? '#44cc88' : s >= 60 ? '#f0c040' : '#666';

// ── sub-components ────────────────────────────────────────────────────────────

function Pill({ children, color }: { children: React.ReactNode; color: string }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 5px', borderRadius: 3,
      background: color + '1a', border: `1px solid ${color}33`,
      color, fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
      lineHeight: '14px',
    }}>
      {children}
    </span>
  );
}

function Arrow({ type }: { type: 'green' | 'red' }) {
  const color = type === 'green' ? '#44cc88' : '#cc4444';
  return (
    <span style={{ color, fontSize: 13, lineHeight: 1, fontWeight: 900 }}>
      {type === 'green' ? '▲' : '▼'}
    </span>
  );
}

function SignalCard({ item, selected, onClick }: {
  item: SignalItem;
  selected: boolean;
  onClick: () => void;
}) {
  const sm = STATE_META[item.state] ?? { color: '#444', label: item.state.slice(0, 8) };
  const score = item.direction === 'short' ? item.score_short : item.score_long;
  const isActionable = item.state.startsWith('ENTRY_ARMED') || item.state === 'CONFIRMED_SETUP_ACTIVE';

  return (
    <div
      onClick={onClick}
      style={{
        minWidth: 160, maxWidth: 180, flexShrink: 0,
        padding: '8px 10px',
        background: selected ? '#1a1a2a' : '#111',
        border: `1px solid ${selected ? '#88aaff55' : isActionable ? sm.color + '44' : '#1e1e1e'}`,
        borderRadius: 5,
        cursor: 'pointer',
        transition: 'border-color 0.15s, background 0.15s',
        position: 'relative',
      }}
    >
      {/* top row: symbol + spot */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
        <span style={{
          fontSize: 13, fontWeight: 800, letterSpacing: 1,
          color: selected ? '#88aaff' : '#e0e0e0',
        }}>
          {item.underlying}
        </span>
        <span style={{ fontSize: 11, color: '#666', fontVariantNumeric: 'tabular-nums' }}>
          {item.spot_price != null
            ? item.spot_price >= 1000
              ? `$${(item.spot_price / 1000).toFixed(1)}k`
              : `$${item.spot_price.toFixed(2)}`
            : '—'}
        </span>
      </div>

      {/* middle row: regime + direction */}
      <div style={{ display: 'flex', gap: 4, alignItems: 'center', marginBottom: 5, flexWrap: 'wrap' }}>
        {item.regime ? (
          <Pill color={REGIME_COLOR(item.regime)}>
            {item.regime.replace('_', ' ').slice(0, 10)}
          </Pill>
        ) : (
          <span style={{ color: '#333', fontSize: 9 }}>—</span>
        )}
        {item.direction !== 'neutral' && (
          <Pill color={DIR_COLOR(item.direction)}>
            {item.direction.toUpperCase()}
          </Pill>
        )}
      </div>

      {/* bottom row: state + arrows + score */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 9, color: sm.color, fontWeight: 700, letterSpacing: 0.3 }}>
          {sm.label}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {item.green_arrow && <Arrow type="green" />}
          {item.red_arrow  && <Arrow type="red" />}
          {score > 0 && (
            <span style={{
              fontSize: 11, fontWeight: 700, color: SCORE_COLOR(score),
              fontVariantNumeric: 'tabular-nums',
            }}>
              {score.toFixed(0)}
            </span>
          )}
          {item.ivr != null && (
            <span style={{ fontSize: 9, color: '#555' }}>
              IVR{item.ivr.toFixed(0)}
            </span>
          )}
        </div>
      </div>

      {/* stale indicator */}
      {!item.fresh && (
        <div style={{
          position: 'absolute', top: 3, right: 5,
          width: 5, height: 5, borderRadius: '50%',
          background: '#333',
        }} title="No live data yet — open stream to refresh" />
      )}
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export function SignalsBar() {
  const { data, isLoading } = useSignals();
  const selected = useSelectedUnderlying();
  const setUnderlying = useSetSelectedUnderlying();

  if (isLoading && !data) {
    return (
      <div style={{ height: 90, display: 'flex', alignItems: 'center', paddingLeft: 4 }}>
        <span style={{ color: '#333', fontSize: 11 }}>Loading signals…</span>
      </div>
    );
  }

  const signals = data?.signals ?? [];
  if (signals.length === 0) return null;

  const actionable = signals.filter(s =>
    s.state.startsWith('ENTRY_ARMED') || s.state === 'CONFIRMED_SETUP_ACTIVE'
  );

  return (
    <div style={{ marginBottom: 16 }}>
      {/* header row */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 8,
      }}>
        <span style={{ color: '#444', fontSize: 10, letterSpacing: 2 }}>
          SIGNALS · {signals.length} instruments
        </span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {actionable.length > 0 && (
            <span style={{
              fontSize: 10, color: '#f0c040',
              background: '#f0c04018', border: '1px solid #f0c04044',
              borderRadius: 3, padding: '1px 7px',
            }}>
              {actionable.length} actionable
            </span>
          )}
          <span style={{ color: '#2a2a2a', fontSize: 9 }}>
            {data?.timestamp_ms
              ? new Date(data.timestamp_ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
              : ''}
          </span>
        </div>
      </div>

      {/* scrollable card strip */}
      <div style={{
        display: 'flex', gap: 8,
        overflowX: 'auto',
        paddingBottom: 4,
        scrollbarWidth: 'none',
      }}>
        {signals.map(item => (
          <SignalCard
            key={item.underlying}
            item={item}
            selected={item.underlying === selected}
            onClick={() => setUnderlying(item.underlying)}
          />
        ))}
      </div>
    </div>
  );
}
