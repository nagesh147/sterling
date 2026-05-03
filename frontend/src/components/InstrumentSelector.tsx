import React, { useEffect } from 'react';
import { useInstruments } from '../hooks/useInstruments';
import { useDataSource } from '../hooks/useExchanges';
import { useSelectedUnderlying, useSetSelectedUnderlying } from '../store/useStore';

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0' },
  label: { color: '#888', fontSize: 13, letterSpacing: 1 },
  select: {
    background: '#1a1a1a', color: '#e0e0e0', border: '1px solid #333',
    padding: '6px 12px', fontSize: 14, borderRadius: 4, cursor: 'pointer',
    fontFamily: 'inherit',
  },
  badge: {
    fontSize: 11, padding: '2px 6px', borderRadius: 3,
    background: '#2a2a2a', color: '#aaa',
  },
  incompatibleBadge: {
    fontSize: 11, padding: '2px 6px', borderRadius: 3,
    background: '#2a1a1a', color: '#cc6644',
  },
};

export function InstrumentSelector() {
  const { data, isLoading } = useInstruments();
  const { data: dsData } = useDataSource();
  const selectedUnderlying = useSelectedUnderlying();
  const setSelectedUnderlying = useSetSelectedUnderlying();

  const activeSource = dsData?.exchange ?? 'deribit';
  const instruments = data?.instruments ?? [];

  // Partition into compatible and incompatible for current source
  const compatible = instruments.filter(i =>
    (i.compatible_sources ?? []).includes(activeSource)
  );
  const incompatible = instruments.filter(i =>
    !(i.compatible_sources ?? []).includes(activeSource)
  );

  // Auto-switch to first compatible instrument when source changes and
  // current selection is no longer compatible
  useEffect(() => {
    if (!compatible.length) return;
    const currentOk = compatible.some(i => i.underlying === selectedUnderlying);
    if (!currentOk) {
      setSelectedUnderlying(compatible[0].underlying);
    }
  }, [activeSource, compatible.length]);

  // Fallback: show default instruments if API failed or hasn't loaded yet
  const FALLBACK = ['BTC', 'ETH', 'SOL', 'XRP'];
  const displayList = compatible.length > 0
    ? compatible
    : isLoading
      ? []
      : FALLBACK.map(u => ({ underlying: u, has_options: true, compatible_sources: [activeSource] } as any));

  if (isLoading) return <div style={styles.label}>Loading…</div>;

  const selected = instruments.find(i => i.underlying === selectedUnderlying);

  return (
    <div style={styles.container}>
      <span style={styles.label}>UNDERLYING</span>
      <select
        style={styles.select}
        value={selectedUnderlying}
        onChange={e => setSelectedUnderlying(e.target.value)}
      >
        {displayList.map(inst => (
          <option key={inst.underlying} value={inst.underlying}>
            {inst.underlying}{inst.has_options === false ? ' (spot)' : ''}
          </option>
        ))}
        {incompatible.length > 0 && (
          <optgroup label="Other sources only">
            {incompatible.map(inst => (
              <option key={inst.underlying} value={inst.underlying} disabled>
                {inst.underlying} — {inst.compatible_sources?.join('/')}
              </option>
            ))}
          </optgroup>
        )}
      </select>
      {selected && (
        <span style={styles.badge}>
          {selected.exchange?.toUpperCase()} · {selected.has_options ? 'OPTIONS' : 'SPOT'}
        </span>
      )}
    </div>
  );
}
