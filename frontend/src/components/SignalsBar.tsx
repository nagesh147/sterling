import React from 'react';
import { useSignals } from '../hooks/useSignals';
import type { SignalItem } from '../hooks/useSignals';
import { useSelectedUnderlying, useSetSelectedUnderlying } from '../store/useStore';
import { usePositions } from '../hooks/usePositions';

const STATE_META: Record<string, { color: string; label: string }> = {
  ENTRY_ARMED_PULLBACK:     { color: '#44aaff', label: 'ARMED·PB' },
  ENTRY_ARMED_CONTINUATION: { color: '#66ccff', label: 'ARMED·CT' },
  CONFIRMED_SETUP_ACTIVE:   { color: '#f0c040', label: 'CONFIRMED' },
  EARLY_SETUP_ACTIVE:       { color: '#f0a500', label: 'EARLY' },
  FILTERED:                 { color: 'var(--text-dim)',   label: 'FILTERED' },
  IDLE:                     { color: 'var(--text-faint)', label: 'IDLE' },
};

const REGIME_COLOR = (r: string) => {
  const u = r.toUpperCase();
  if (u.includes('BULL')) return '#44cc88';
  if (u.includes('BEAR')) return '#cc4444';
  if (u === 'VOLATILE')   return '#f0c040';
  return 'var(--text-dim)';
};

const DIR_COLOR = (d: string) =>
  d === 'long' ? '#44cc88' : d === 'short' ? '#cc4444' : 'var(--text-dim)';

function ScoreMiniBar({ long, short }: { long: number; short: number }) {
  const total = 100;
  const longW = Math.min(50, (long / total) * 100);
  const shortW = Math.min(50, (short / total) * 100);
  return (
    <div style={{ display: 'flex', gap: 2, alignItems: 'center', height: 4, width: '100%' }}>
      <div style={{ flex: 1, background: 'var(--bg)', borderRadius: 2, overflow: 'hidden', display: 'flex', justifyContent: 'flex-end' }}>
        <div style={{ width: `${longW}%`, height: 4, background: 'var(--accent)', borderRadius: 2 }} />
      </div>
      <div style={{ width: 1, height: 6, background: 'var(--text-faint)', flexShrink: 0 }} />
      <div style={{ flex: 1, background: 'var(--bg)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${shortW}%`, height: 4, background: '#cc4444', borderRadius: 2 }} />
      </div>
    </div>
  );
}

function SignalCard({
  item, selected, openCount, onClick,
}: { item: SignalItem; selected: boolean; openCount: number; onClick: () => void }) {
  const sm = STATE_META[item.state] ?? { color: 'var(--text-faint)', label: item.state.slice(0, 8) };
  const isActionable = item.state.startsWith('ENTRY_ARMED') || item.state === 'CONFIRMED_SETUP_ACTIVE';
  const score = item.direction === 'short' ? item.score_short : item.score_long;
  const scoreColor = score >= 75 ? '#44cc88' : score >= 60 ? '#f0c040' : 'var(--text-muted)';

  return (
    <div onClick={onClick} style={{
      minWidth: 170, maxWidth: 195, flexShrink: 0, padding: '8px 10px',
      background: selected ? '#16182a' : 'var(--bg)',
      border: `1px solid ${selected ? '#88aaff66' : isActionable ? sm.color + '55' : 'var(--border)'}`,
      borderRadius: 5, cursor: 'pointer', position: 'relative',
      transition: 'border-color 0.15s',
    }}>
      {/* row 1: symbol + spot */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 800, letterSpacing: 1, color: selected ? '#88aaff' : 'var(--text-primary)' }}>
          {item.underlying}
        </span>
        <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
          {openCount > 0 && (
            <span style={{
              fontSize: 9, fontWeight: 700, color: '#44cc88',
              background: '#44cc8822', border: '1px solid #44cc8844',
              borderRadius: 3, padding: '0 4px', lineHeight: '14px',
            }}>&#9679;{openCount}</span>
          )}
          <span style={{ fontSize: 11, color: 'var(--text-dim)', fontVariantNumeric: 'tabular-nums' }}>
            {item.spot_price != null
              ? item.spot_price >= 1000 ? `$${(item.spot_price / 1000).toFixed(1)}k`
              : `$${item.spot_price.toFixed(2)}`
              : '—'}
          </span>
        </div>
      </div>

      {/* row 2: regime + direction + exec */}
      <div style={{ display: 'flex', gap: 3, alignItems: 'center', marginBottom: 5, flexWrap: 'wrap' as const }}>
        {item.regime ? (
          <span style={{
            fontSize: 9, fontWeight: 700, color: REGIME_COLOR(item.regime),
            background: REGIME_COLOR(item.regime) + '18', border: `1px solid ${REGIME_COLOR(item.regime)}33`,
            padding: '1px 4px', borderRadius: 3,
          }}>{item.regime.replace(/_/g, ' ').slice(0, 9)}</span>
        ) : null}
        {item.direction !== 'neutral' && (
          <span style={{
            fontSize: 9, fontWeight: 700, color: DIR_COLOR(item.direction),
            background: DIR_COLOR(item.direction) + '18', border: `1px solid ${DIR_COLOR(item.direction)}33`,
            padding: '1px 4px', borderRadius: 3,
          }}>{item.direction === 'long' ? '↑ L' : '↓ S'}</span>
        )}
        {item.exec_mode && item.exec_mode !== 'wait' && (
          <span style={{ fontSize: 9, color: '#88aaff', background: '#88aaff18', border: '1px solid #88aaff33', padding: '1px 4px', borderRadius: 3 }}>
            {item.exec_mode === 'pullback' ? 'PB' : 'CT'}
          </span>
        )}
      </div>

      {/* score bar */}
      <ScoreMiniBar long={item.score_long} short={item.score_short} />

      {/* row 3: state + score + arrows + ivr */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 5 }}>
        <span style={{ fontSize: 9, color: sm.color, fontWeight: 700, letterSpacing: 0.3 }}>{sm.label}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {item.green_arrow && <span style={{ color: '#44cc88', fontSize: 11, lineHeight: 1 }}>▲</span>}
          {item.red_arrow   && <span style={{ color: '#cc4444', fontSize: 11, lineHeight: 1 }}>▼</span>}
          {score > 0 && <span style={{ fontSize: 11, fontWeight: 700, color: scoreColor, fontVariantNumeric: 'tabular-nums' }}>{score.toFixed(0)}</span>}
          {item.ivr != null && <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>I{item.ivr.toFixed(0)}</span>}
          {!item.fresh && <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--border-light)', display: 'inline-block' }} title="Stale" />}
        </div>
      </div>
    </div>
  );
}

export function SignalsBar() {
  const { data, isLoading } = useSignals();
  const { data: posData } = usePositions();
  const selected = useSelectedUnderlying();
  const setUnderlying = useSetSelectedUnderlying();

  // Build map: underlying -> open position count
  const openByUnderlying: Record<string, number> = {};
  (posData?.positions ?? []).forEach(p => {
    if (p.status === 'open' || p.status === 'partially_closed') {
      openByUnderlying[p.underlying] = (openByUnderlying[p.underlying] || 0) + 1;
    }
  });

  if (isLoading && !data) return (
    <div style={{ height: 88, display: 'flex', alignItems: 'center', paddingLeft: 4 }}>
      <span style={{ color: 'var(--border-light)', fontSize: 11 }}>Loading signals…</span>
    </div>
  );

  const signals = data?.signals ?? [];
  if (signals.length === 0) return null;

  const actionable = signals.filter(s => s.state.startsWith('ENTRY_ARMED') || s.state === 'CONFIRMED_SETUP_ACTIVE');

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 7 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: 'var(--text-faint)', fontSize: 10, letterSpacing: 2 }}>SIGNALS</span>
          {actionable.length > 0 && (
            <span style={{ fontSize: 10, color: '#f0c040', background: '#f0c04014', border: '1px solid #f0c04044', borderRadius: 3, padding: '1px 7px' }}>
              {actionable.length} actionable
            </span>
          )}
        </div>
        <span style={{ color: 'var(--border)', fontSize: 9 }}>
          {data?.timestamp_ms ? new Date(data.timestamp_ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 7, overflowX: 'auto', paddingBottom: 4, scrollbarWidth: 'none' }}>
        {signals.map(item => (
          <SignalCard
            key={item.underlying}
            item={item}
            selected={item.underlying === selected}
            openCount={openByUnderlying[item.underlying] || 0}
            onClick={() => setUnderlying(item.underlying)}
          />
        ))}
      </div>
    </div>
  );
}
