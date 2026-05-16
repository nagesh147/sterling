import React, { useRef } from 'react';
import { useWatchlist } from '../hooks/useWatchlist';
import { useLivePrices } from '../hooks/useLivePrices';

function fmtPrice(price: number) {
  return price >= 1000
    ? price.toLocaleString('en-US', { maximumFractionDigits: 0 })
    : price.toLocaleString('en-US', { maximumFractionDigits: 3 });
}

export function TickerStrip() {
  const { data } = useWatchlist();
  const liveP = useLivePrices();
  const stripRef = useRef<HTMLDivElement>(null);

  /* useWatchlist provides metadata (regime, trend, score).
     useLivePrices overlays the latest spot price (updated ~2s via SSE). */
  const items = data?.items ?? [];

  const renderItem = (item: typeof items[0], key: string) => {
    const trend = item.signal_trend ?? 0;
    const score = Math.max(item.score_long ?? 0, item.score_short ?? 0);
    const cls   = trend > 0 ? 'up' : trend < 0 ? 'dn' : 'neu';
    const arrow = trend > 0 ? '▲' : trend < 0 ? '▼' : '◆';

    /* Prefer SSE live price; fall back to watchlist price */
    const price = liveP[item.underlying] ?? item.spot_price ?? null;
    if (price == null) return null;

    return (
      <span key={key} style={{ display: 'inline-flex', gap: 5, alignItems: 'center', flexShrink: 0 }}>
        <span style={{ color: 'var(--t-bright)', fontWeight: 700, letterSpacing: 1, fontSize: 11 }}>
          {item.underlying}
        </span>
        <span className={'num ' + cls} style={{ fontSize: 11 }}>${fmtPrice(price)}</span>
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

  /* Show from SSE alone while watchlist is still loading */
  const liveOnly = Object.keys(liveP);
  const hasItems = items.length > 0 || liveOnly.length > 0;

  /* Render from watchlist items when available, otherwise from SSE prices only */
  const displayItems: Array<{ underlying: string; signal_trend?: number; score_long?: number; score_short?: number; spot_price?: number | null }> =
    items.length > 0
      ? items
      : liveOnly.map((sym) => ({ underlying: sym }));

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
      {!hasItems ? (
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
            animation: displayItems.length > 3 ? 'ticker-move 60s linear infinite' : undefined,
          }}
        >
          {displayItems.map((i) => renderItem(i as typeof items[0], i.underlying))}
          {displayItems.length > 3 && displayItems.map((i) => renderItem(i as typeof items[0], i.underlying + '_dup'))}
        </div>
      )}
    </div>
  );
}
