import React, { useState } from 'react';
import { useConfigInfo } from '../hooks/useConfigInfo';
import { useSetDataSource, useDataSource, useInvalidateCache } from '../hooks/useExchanges';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 14 },
  cell: { display: 'flex', flexDirection: 'column', gap: 3 },
  key: { color: '#555', fontSize: 10, letterSpacing: 1 },
  val: { fontSize: 13, color: '#ccc', fontWeight: 600 },
  stack: {
    background: '#111', border: '1px solid #1e1e1e', borderRadius: 4,
    padding: '8px 12px', fontSize: 11, color: '#888', fontFamily: 'Courier New, monospace',
    marginBottom: 12,
  },
  row: { display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 },
  chip: {
    padding: '2px 8px', borderRadius: 3, fontSize: 11,
    background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#aaa',
  },
  chipGreen: {
    padding: '2px 8px', borderRadius: 3, fontSize: 11,
    background: '#44cc8818', border: '1px solid #44cc8844', color: '#44cc88',
  },
  dsRow: {
    display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap',
    background: '#0d0d1a', border: '1px solid #1a1a3a', borderRadius: 4,
    padding: '10px 12px', marginBottom: 12,
  },
  select: {
    background: '#141414', color: '#e0e0e0', border: '1px solid #2a2a2a',
    borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 12, flex: 1,
  },
  btn: {
    background: '#1a1a2a', color: '#88aaff', border: '1px solid #334',
    padding: '5px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
  },
  btnPurple: {
    background: '#1a1a2a', color: '#aa88ff', border: '1px solid #aa88ff',
    padding: '5px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
  },
  btnOrange: {
    background: '#1a1500', color: '#f0a500', border: '1px solid #f0a500',
    padding: '5px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
  },
  status: { fontSize: 11, color: '#666' },
  success: { fontSize: 11, color: '#44cc88' },
  error: { fontSize: 11, color: '#cc4444' },
};

export function SystemInfoPanel() {
  const { data, isLoading } = useConfigInfo();
  const { data: dsData } = useDataSource();
  const setDs = useSetDataSource();
  const invalidate = useInvalidateCache();
  const [selectedDs, setSelectedDs] = useState('');
  const [dsMsg, setDsMsg] = useState('');

  const currentDs = dsData?.exchange ?? data?.active_data_source ?? '';
  const sources = data?.supported_data_sources ?? {};

  const handleSwitchDs = () => {
    const target = selectedDs || currentDs;
    if (!target) return;
    setDs.mutate(
      { exchange: target },
      {
        onSuccess: (r) => {
          setDsMsg(`✓ Switched to ${r.display_name} — ${r.reachable ? 'reachable' : 'unreachable'}`);
          setTimeout(() => setDsMsg(''), 4000);
        },
        onError: (e) => setDsMsg(`✗ ${e.message}`),
      }
    );
  };

  const handleInvalidate = () => {
    invalidate.mutate(undefined, {
      onSuccess: () => {
        setDsMsg('✓ Cache cleared — next requests fetch live data');
        setTimeout(() => setDsMsg(''), 3000);
      },
    });
  };

  if (isLoading) return (
    <div style={S.card}><div style={{ color: '#444', fontSize: 12 }}>Loading system info…</div></div>
  );
  if (!data) return null;

  return (
    <div style={S.card}>
      <div style={S.title}>SYSTEM INFO</div>

      {/* Data source switcher */}
      <div style={{ ...S.key, marginBottom: 6 }}>MARKET DATA SOURCE</div>
      <div style={S.dsRow}>
        <select
          style={S.select}
          value={selectedDs || currentDs}
          onChange={e => setSelectedDs(e.target.value)}
        >
          {Object.entries(sources).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <button style={S.btnPurple} onClick={handleSwitchDs} disabled={setDs.isPending}>
          {setDs.isPending ? 'SWITCHING…' : 'SWITCH'}
        </button>
        <button style={S.btnOrange} onClick={handleInvalidate} disabled={invalidate.isPending}
          title="Clear cache — next requests fetch live data from exchange">
          {invalidate.isPending ? '…' : 'CLEAR CACHE'}
        </button>
        {dsData && (
          <span style={{ color: dsData.reachable ? '#44cc88' : '#cc4444', fontSize: 11 }}>
            {dsData.reachable ? '● live' : '● unreachable'}
          </span>
        )}
      </div>
      {dsMsg && (
        <div style={dsMsg.startsWith('✓') ? S.success : S.error}>{dsMsg}</div>
      )}

      <div style={S.grid}>
        <div style={S.cell}>
          <span style={S.key}>VERSION</span>
          <span style={S.val}>{data.version}</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>ENVIRONMENT</span>
          <span style={{ ...S.val, color: data.environment === 'production' ? '#f0a500' : '#44cc88' }}>
            {data.environment.toUpperCase()}
          </span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>ACTIVE SOURCE</span>
          <span style={{ ...S.val, color: '#aa88ff' }}>
            {data.active_data_source.toUpperCase()}
          </span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>MODE</span>
          <span style={{ ...S.val, color: data.paper_trading ? '#44cc88' : '#cc4444' }}>
            {data.paper_trading ? 'PAPER' : 'LIVE'}
          </span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>DEFAULT UNDERLYING</span>
          <span style={S.val}>{data.default_underlying}</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>DB</span>
          <span style={{ ...S.val, fontSize: 11, color: '#666', fontFamily: 'monospace' }}>
            {data.db_path.split('/').pop()}
          </span>
        </div>
      </div>

      <div style={{ ...S.key, marginBottom: 6 }}>ADAPTER STACK</div>
      <div style={S.stack}>{data.adapter_stack}</div>

      <div style={{ marginBottom: 8 }}>
        <div style={{ ...S.key, marginBottom: 6 }}>SUPPORTED UNDERLYINGS</div>
        <div style={S.row}>
          {data.supported_underlyings.map(u => (
            <span
              key={u}
              style={data.underlyings_with_options.includes(u) ? S.chipGreen : S.chip}
              title={data.underlyings_with_options.includes(u) ? 'Options available' : 'No options'}
            >
              {u}
            </span>
          ))}
        </div>
        <div style={{ ...S.key, marginTop: 4 }}>GREEN = options · GRAY = spot/perp only</div>
      </div>
    </div>
  );
}
