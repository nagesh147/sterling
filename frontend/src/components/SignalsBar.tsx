import React from 'react';
import { useSignals } from '../hooks/useSignals';
import type { SignalItem } from '../hooks/useSignals';
import { useSelectedUnderlying, useSetSelectedUnderlying } from '../store/useStore';
import { usePositions } from '../hooks/usePositions';
import { useExchanges } from '../hooks/useExchanges';

const STATE_META: Record<string, { color: string; label: string }> = {
  ENTRY_ARMED_PULLBACK:     { color: 'var(--blue)',    label: 'ARMED·PB' },
  ENTRY_ARMED_CONTINUATION: { color: 'var(--blue)',    label: 'ARMED·CT' },
  CONFIRMED_SETUP_ACTIVE:   { color: 'var(--warning)', label: 'CONFIRMED' },
  EARLY_SETUP_ACTIVE:       { color: 'var(--warning)', label: 'FORMING' },
  FILTERED:                 { color: 'var(--text-dim)',   label: 'FILTERED' },
  IDLE:                     { color: 'var(--text-faint)', label: 'IDLE' },
};

const REGIME_COLOR = (r: string) => {
  const u = r.toUpperCase();
  if (u.includes('BULL')) return 'var(--accent)';
  if (u.includes('BEAR')) return 'var(--danger)';
  if (u === 'VOLATILE')   return 'var(--warning)';
  return 'var(--text-dim)';
};

const DIR_COLOR = (d: string) =>
  d === 'long' ? 'var(--accent)' : d === 'short' ? 'var(--danger)' : 'var(--text-dim)';

function ScoreMiniBar({ long, short }: { long: number; short: number }) {
  const longW  = Math.min(100, (long  / 100) * 100);
  const shortW = Math.min(100, (short / 100) * 100);
  return (
    <div style={{ display: 'flex', gap: 2, alignItems: 'center', width: '100%', marginTop: 8 }}>
      <div style={{ flex: 1, height: 2, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', display: 'flex', justifyContent: 'flex-end' }}>
        <div style={{ width: `${longW}%`, height: '100%', background: 'var(--accent)', borderRadius: 2, opacity: 0.8 }} />
      </div>
      <div style={{ width: 1, height: 8, background: 'var(--border-light)', flexShrink: 0 }} />
      <div style={{ flex: 1, height: 2, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${shortW}%`, height: '100%', background: 'var(--danger)', borderRadius: 2, opacity: 0.8 }} />
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
  const scoreColor = score >= 75 ? 'var(--accent)' : score >= 60 ? 'var(--warning)' : 'var(--text-dim)';
  const dirColor = DIR_COLOR(item.direction);

  const borderColor = selected
    ? 'var(--blue)80'
    : isActionable
      ? sm.color + '55'
      : 'var(--border)';

  const spotDisplay = item.spot_price != null
    ? item.spot_price >= 1000
      ? `$${(item.spot_price / 1000).toFixed(1)}k`
      : `$${item.spot_price.toFixed(2)}`
    : '—';

  return (
    <div
      onClick={onClick}
      style={{
        width: 176,
        flexShrink: 0,
        padding: '10px 12px',
        background: selected ? '#1A1F2E' : 'var(--bg-card)',
        border: `1px solid ${borderColor}`,
        borderTop: isActionable ? `2px solid ${sm.color}` : `1px solid ${borderColor}`,
        borderRadius: 8,
        cursor: 'pointer',
        transition: 'border-color 0.15s, background 0.1s',
      }}
    >
      {/* Row 1: symbol + spot price */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <span style={{
          fontSize: 13,
          fontWeight: 700,
          letterSpacing: '0.05em',
          color: selected ? 'var(--blue)' : 'var(--text-primary)',
        }}>
          {item.underlying}
        </span>
        <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
          {openCount > 0 && (
            <span style={{
              fontSize: 8,
              fontWeight: 700,
              color: 'var(--accent)',
              background: 'var(--accent)18',
              border: '1px solid var(--accent)35',
              borderRadius: 3,
              padding: '0 5px',
              lineHeight: '14px',
            }}>●{openCount}</span>
          )}
          <span style={{ fontSize: 10, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
            {spotDisplay}
          </span>
        </div>
      </div>

      {/* Row 2: regime pill + direction badge */}
      <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' as const }}>
        {item.regime && (
          <span style={{
            fontSize: 8,
            fontWeight: 600,
            letterSpacing: '0.04em',
            color: REGIME_COLOR(item.regime),
            background: REGIME_COLOR(item.regime) + '15',
            padding: '2px 5px',
            borderRadius: 4,
          }}>
            {item.regime.replace(/_/g, ' ').slice(0, 9).toUpperCase()}
          </span>
        )}
        {item.direction !== 'neutral' && (
          <span style={{
            fontSize: 8,
            fontWeight: 700,
            color: dirColor,
            background: dirColor + '18',
            padding: '2px 5px',
            borderRadius: 4,
          }}>
            {item.direction === 'long' ? '↑ LONG' : '↓ SHORT'}
          </span>
        )}
        {item.exec_mode && item.exec_mode !== 'wait' && (
          <span style={{
            fontSize: 8,
            color: 'var(--blue)',
            background: 'var(--blue)18',
            padding: '2px 5px',
            borderRadius: 4,
          }}>
            {item.exec_mode === 'pullback' ? 'PB' : 'CT'}
          </span>
        )}
      </div>

      {/* Score bar */}
      <ScoreMiniBar long={item.score_long} short={item.score_short} />

      {/* Row 3: state label + score + freshness */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
        <span style={{ fontSize: 8, color: sm.color, fontWeight: 600, letterSpacing: '0.05em' }}>
          {sm.label}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          {item.green_arrow && <span style={{ color: 'var(--accent)', fontSize: 10, lineHeight: 1 }}>▲</span>}
          {item.red_arrow   && <span style={{ color: 'var(--danger)', fontSize: 10, lineHeight: 1 }}>▼</span>}
          {score > 0 && (
            <span style={{ fontSize: 12, fontWeight: 700, color: scoreColor, fontVariantNumeric: 'tabular-nums' }}>
              {score.toFixed(0)}
            </span>
          )}
          {item.ivr != null && (
            <span style={{ fontSize: 8, color: 'var(--text-faint)' }}>
              I{item.ivr.toFixed(0)}
            </span>
          )}
          {!item.fresh && (
            <span
              style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--text-faint)', display: 'inline-block' }}
              title="Stale"
            />
          )}
        </div>
      </div>
    </div>
  );
}

export function SignalsBar() {
  const { data, isLoading } = useSignals();
  const { data: exData }    = useExchanges();
  const delta   = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);
  const isLive  = !!(delta?.has_credentials && !delta.is_paper);
  const { data: posData }   = usePositions();  // all modes — badge counts paper/shadow/live alike
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
    <div style={{ height: 96, display: 'flex', alignItems: 'center', paddingLeft: 4 }}>
      <span style={{ color: 'var(--text-faint)', fontSize: 11 }}>Loading signals…</span>
    </div>
  );

  const signals = data?.signals ?? [];
  if (signals.length === 0) return null;

  const actionable = signals.filter(s => s.state.startsWith('ENTRY_ARMED') || s.state === 'CONFIRMED_SETUP_ACTIVE');

  return (
    <div style={{ marginBottom: 20 }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: '0.12em',
            color: 'var(--text-dim)',
          }}>
            SIGNALS
          </span>

          {/* Live/Paper badge */}
          <span style={{
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: '0.08em',
            color: isLive ? 'var(--accent)' : 'var(--blue)',
            background: isLive ? 'var(--accent)14' : 'var(--blue)14',
            borderRadius: 4,
            padding: '2px 7px',
          }}>
            {isLive ? '● LIVE' : 'PAPER'}
          </span>

          {/* Actionable count */}
          {actionable.length > 0 && (
            <span style={{
              fontSize: 9,
              fontWeight: 600,
              color: 'var(--warning)',
              background: 'var(--warning)14',
              borderRadius: 4,
              padding: '2px 7px',
            }}>
              {actionable.length} actionable
            </span>
          )}
        </div>

        {/* Timestamp */}
        <span style={{ color: 'var(--text-faint)', fontSize: 9, fontVariantNumeric: 'tabular-nums' }}>
          {data?.timestamp_ms
            ? new Date(data.timestamp_ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
            : ''}
        </span>
      </div>

      {/* Card scroll strip */}
      <div style={{
        display: 'flex',
        gap: 8,
        overflowX: 'auto',
        paddingBottom: 6,
        scrollbarWidth: 'none',
        msOverflowStyle: 'none',
      } as React.CSSProperties}>
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
