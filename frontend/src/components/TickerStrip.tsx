import React, { useRef } from 'react';
import { useWatchlist } from '../hooks/useWatchlist';

export function TickerStrip() {
  const { data } = useWatchlist();
  const stripRef = useRef<HTMLDivElement>(null);

  const items = data?.items?.filter((i) => i.spot_price) ?? [];

  const renderItem = (item: typeof items[0], key: string) => {
    const trend = item.signal_trend ?? 0;
    const score = Math.max(item.score_long ?? 0, item.score_short ?? 0);
    const cls = trend > 0 ? 'up' : trend < 0 ? 'dn' : 'neu';
    const arrow = trend > 0 ? '▲' : trend < 0 ? '▼' : '◆';
    const price = item.spot_price!;
    const fmt = price >= 1000
      ? price.toLocaleString('en-US', { maximumFractionDigits: 0 })
      : price.toLocaleString('en-US', { maximumFractionDigits: 3 });
    return (
      <span key={key} style={{ display: 'inline-flex', gap: 5, alignItems: 'center', flexShrink: 0 }}>
        <span style={{ color: 'var(--t-bright)', fontWeight: 700, letterSpacing: 1, fontSize: 11 }}>
          {item.underlying}
        </span>
        <span className={'num ' + cls} style={{ fontSize: 11 }}>${fmt}</span>
        <span className={cls} style={{ fontSize: 9 }}>{arrow}</span>
        {score >= 75 && (
          <span className="tag" style={{ background: 'var(--t-border)', color: 'var(--t-text)' }}>
            {score}
          </span>
        )}
        <span style={{ color: 'var(--t-br2)', marginLeft: 8 }}>│</span>
      </span>
    );
  };

  return (
    <div
      style={{
        height: 48,
        background: 'var(--t-bg2)',
        borderBottom: '1px solid var(--t-border)',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        flexShrink: 0,
      }}
      onMouseEnter={() => { if (stripRef.current) stripRef.current.style.animationPlayState = 'paused'; }}
      onMouseLeave={() => { if (stripRef.current) stripRef.current.style.animationPlayState = 'running'; }}
    >
      {items.length === 0 ? (
        <span style={{ padding: '0 16px', color: 'var(--t-dim)', fontSize: 11 }}>
          Loading market data…
        </span>
      ) : (
        <div
          ref={stripRef}
          style={{
            display: 'inline-flex',
            gap: 16,
            padding: '0 16px',
            whiteSpace: 'nowrap',
            animation: items.length > 3 ? 'ticker-move 60s linear infinite' : undefined,
          }}
        >
          {items.map((i) => renderItem(i, i.underlying))}
          {items.length > 3 && items.map((i) => renderItem(i, i.underlying + '_dup'))}
        </div>
      )}
    </div>
  );
}
