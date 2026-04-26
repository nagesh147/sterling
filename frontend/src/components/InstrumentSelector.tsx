import React from 'react';
import { useInstruments } from '../hooks/useInstruments';
import { useStore } from '../store/useStore';

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
};

export function InstrumentSelector() {
  const { data, isLoading } = useInstruments();
  const { selectedUnderlying, setSelectedUnderlying } = useStore();

  if (isLoading) return <div style={styles.label}>Loading instruments…</div>;

  const instruments = data?.instruments ?? [];
  const selected = instruments.find(i => i.underlying === selectedUnderlying);

  return (
    <div style={styles.container}>
      <span style={styles.label}>UNDERLYING</span>
      <select
        style={styles.select}
        value={selectedUnderlying}
        onChange={e => setSelectedUnderlying(e.target.value)}
      >
        {instruments.map(inst => (
          <option key={inst.underlying} value={inst.underlying}>
            {inst.underlying} {!inst.has_options ? '(no options)' : ''}
          </option>
        ))}
      </select>
      {selected && (
        <span style={styles.badge}>
          {selected.exchange.toUpperCase()} · {selected.quote_currency}
          {selected.has_options ? ' · OPTIONS' : ' · SPOT ONLY'}
        </span>
      )}
    </div>
  );
}
