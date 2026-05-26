/**
 * DataSourceSelector — compact market data source switcher for the terminal header.
 * Shows current source, a reachability dot, a select to hot-swap, and a ↺ reconnect
 * button that force-reinits the adapter + clears stale price cache without a server restart.
 */
import React, { useEffect, useState } from 'react';
import { useDataSource, useSetDataSource, useInvalidateCache } from '../hooks/useExchanges';
import { useConfigInfo } from '../hooks/useConfigInfo';
import { useQueryClient } from '@tanstack/react-query';

const SHORT: Record<string, string> = {
  deribit:     'Deribit',
  binance:     'Binance',
  okx:         'OKX',
  delta_india: 'DELTA EXCHANGE',
};

export function DataSourceSelector({ chipStyle }: { chipStyle?: React.CSSProperties } = {}) {
  const { data: ds, isLoading } = useDataSource();
  const { data: cfg }           = useConfigInfo();
  const { mutate: setSource, isPending }       = useSetDataSource();
  const { mutate: invalidate, isPending: inv } = useInvalidateCache();
  const qc = useQueryClient();

  const current = ds?.exchange ?? '';
  const sources = cfg?.supported_data_sources ?? {} as Record<string, string>;
  const hasData = Object.keys(sources).length > 0;

  const [selected, setSelected] = useState(current);
  useEffect(() => { setSelected(current); }, [current]);

  const busy = isPending || inv || isLoading;

  const reachable = ds?.reachable ?? null;
  const dotColor  = busy              ? 'var(--t-amber)'
                  : reachable === true  ? 'var(--t-green)'
                  : reachable === false ? 'var(--t-red)'
                  :                      'var(--t-dim)';

  const _invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ['data-source'] });
    qc.invalidateQueries({ queryKey: ['watchlist'] });
    qc.invalidateQueries({ queryKey: ['snapshot'] });
    qc.invalidateQueries({ queryKey: ['signals-all'] });
    qc.invalidateQueries({ queryKey: ['candles'] });
  };

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    setSelected(next);
    setSource(
      { exchange: next },
      {
        onSuccess: () => _invalidateAll(),
        onError:   () => setSelected(current),
      }
    );
  };

  /** Force-reinit the current adapter + clear price cache. No server restart needed. */
  const handleReconnect = () => {
    if (!current || busy) return;
    // Re-apply current source → rebuilds adapter with latest code/config
    setSource(
      { exchange: current },
      {
        onSuccess: () => {
          // Then clear the adapter's in-memory price cache
          invalidate(undefined, { onSuccess: () => _invalidateAll() });
        },
      }
    );
  };

  if (!hasData && !current) return null;

  const baseBorder = reachable === false ? 'var(--t-red)55' : (chipStyle ? 'inherit' : 'var(--t-border)');

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0,
        ...(chipStyle ?? {}),
        padding: 0,
        overflow: 'hidden',
      }}
      title={ds
        ? `${ds.display_name} — ${reachable ? 'reachable' : 'unreachable'}. Click ↺ to reconnect.`
        : 'Market data source'}
    >
      {/* Reachability dot */}
      <span style={{
        width: 6, height: 6, borderRadius: '50%',
        background: dotColor, display: 'inline-block', flexShrink: 0,
        marginLeft: 10,
        transition: 'background 0.3s',
      }} />

      {/* Source select */}
      <select
        value={selected}
        onChange={handleChange}
        disabled={busy}
        style={{
          background: 'transparent',
          color: busy ? 'var(--t-amber)' : (chipStyle ? 'inherit' : 'var(--t-bright)'),
          border: 'none',
          padding: '4px 8px',
          fontSize: chipStyle?.fontSize ?? 10,
          fontFamily: chipStyle?.fontFamily ?? 'JetBrains Mono, monospace',
          fontWeight: chipStyle?.fontWeight ?? 600,
          letterSpacing: chipStyle?.letterSpacing ?? '0.04em',
          cursor: busy ? 'wait' : 'pointer',
          outline: 'none',
          appearance: 'none',
          WebkitAppearance: 'none',
          minWidth: 56,
        }}
      >
        {hasData
          ? Object.entries(sources).map(([k, _]) => (
              <option key={k} value={k}>{SHORT[k] ?? k}</option>
            ))
          : current
            ? <option value={current}>{SHORT[current] ?? current}</option>
            : null}
      </select>

      {/* Reconnect / refresh button */}
      <button
        onClick={handleReconnect}
        disabled={busy}
        title="Reconnect market data (force-reload adapter + clear price cache)"
        style={{
          background: 'transparent',
          border: 'none',
          borderLeft: `1px solid ${baseBorder}`,
          padding: '4px 8px',
          color: busy ? 'var(--t-amber)' : reachable === false ? 'var(--t-red)' : (chipStyle?.color ?? 'var(--t-dim)'),
          cursor: busy ? 'wait' : 'pointer',
          fontFamily: 'inherit',
          fontSize: 12,
          lineHeight: 1,
          animation: busy ? 't-blink 0.6s infinite' : undefined,
        }}
      >
        {busy ? '…' : '↺'}
      </button>
    </div>
  );
}
