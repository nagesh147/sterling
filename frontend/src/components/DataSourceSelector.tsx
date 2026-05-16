/**
 * DataSourceSelector — compact market data source switcher for the terminal header.
 * Shows current source, a reachability dot, and a select to hot-swap.
 */
import React, { useEffect, useState } from 'react';
import { useDataSource, useSetDataSource } from '../hooks/useExchanges';
import { useConfigInfo } from '../hooks/useConfigInfo';
import { useQueryClient } from '@tanstack/react-query';

/* Short display labels so the select stays narrow */
const SHORT: Record<string, string> = {
  deribit:     'Deribit',
  binance:     'Binance',
  okx:         'OKX',
  delta_india: 'Delta IN',
};

export function DataSourceSelector() {
  const { data: ds, isLoading } = useDataSource();
  const { data: cfg } = useConfigInfo();
  const { mutate: setSource, isPending } = useSetDataSource();
  const qc = useQueryClient();

  const current  = ds?.exchange ?? '';
  const sources  = cfg?.supported_data_sources ?? {} as Record<string, string>;
  const hasData  = Object.keys(sources).length > 0;

  /* Local select state so the UI updates instantly, not after server round-trip */
  const [selected, setSelected] = useState(current);
  useEffect(() => { setSelected(current); }, [current]);

  const reachable = ds?.reachable ?? null;
  const dotColor  = isLoading || isPending ? 'var(--t-amber)'
                  : reachable === true      ? 'var(--t-green)'
                  : reachable === false     ? 'var(--t-red)'
                  :                           'var(--t-dim)';

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    setSelected(next);
    setSource(
      { exchange: next },
      {
        onSuccess: () => {
          qc.invalidateQueries({ queryKey: ['data-source'] });
        },
        onError: () => {
          setSelected(current); // roll back on error
        },
      }
    );
  };

  if (!hasData && !current) return null;

  return (
    <div
      style={{ display: 'flex', alignItems: 'center', gap: 5 }}
      title={ds ? `${ds.display_name} — ${reachable ? 'reachable' : 'unreachable'}` : 'Market data source'}
    >
      {/* Reachability dot */}
      <span style={{
        width: 6, height: 6, borderRadius: '50%',
        background: dotColor, display: 'inline-block', flexShrink: 0,
        transition: 'background 0.3s',
        boxShadow: reachable ? `0 0 4px ${dotColor}` : 'none',
      }} />

      {/* Source select */}
      <select
        value={selected}
        onChange={handleChange}
        disabled={isPending || isLoading}
        style={{
          background: 'none',
          color: isPending ? 'var(--t-amber)' : 'var(--t-bright)',
          border: `1px solid ${reachable === false ? 'var(--t-red)55' : 'var(--t-border)'}`,
          borderRadius: 3,
          padding: '2px 4px',
          fontSize: 10,
          fontFamily: 'JetBrains Mono, monospace',
          fontWeight: 600,
          cursor: isPending ? 'wait' : 'pointer',
          outline: 'none',
          appearance: 'none',
          WebkitAppearance: 'none',
          minWidth: 56,
        }}
      >
        {hasData
          ? Object.entries(sources).map(([key, label]) => (
              <option key={key} value={key}>
                {SHORT[key] ?? key}
              </option>
            ))
          : current
            ? <option value={current}>{SHORT[current] ?? current}</option>
            : null
        }
      </select>

      {/* Pending spinner text */}
      {isPending && (
        <span style={{ fontSize: 9, color: 'var(--t-amber)', fontFamily: 'JetBrains Mono, monospace' }}>
          …
        </span>
      )}
    </div>
  );
}
