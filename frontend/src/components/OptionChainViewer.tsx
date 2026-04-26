import React, { useState } from 'react';
import { useOptionChain } from '../hooks/useOptionChain';
import { fmtN } from '../utils/fmt';
import type { CandidateContract } from '../types';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  controls: { display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 14 },
  select: { background: '#111', color: '#e0e0e0', border: '1px solid #2a2a2a', borderRadius: 3, padding: '4px 8px', fontFamily: 'inherit', fontSize: 11 },
  input: { background: '#111', color: '#e0e0e0', border: '1px solid #2a2a2a', borderRadius: 3, padding: '4px 6px', fontFamily: 'inherit', fontSize: 11, width: 52 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 10 },
  th: { color: '#444', textAlign: 'left', padding: '4px 7px', borderBottom: '1px solid #1e1e1e', letterSpacing: 1 },
  td: { padding: '5px 7px', borderBottom: '1px solid #141414', color: '#aaa' },
  expiry: { color: '#888', fontSize: 10, letterSpacing: 1, margin: '10px 0 4px', fontWeight: 700 },
  healthDot: { width: 6, height: 6, borderRadius: '50%', display: 'inline-block', marginRight: 4 },
  meta: { color: '#444', fontSize: 10, marginTop: 10 },
  noData: { color: '#444', fontSize: 12, textAlign: 'center', padding: 24 },
};

function ContractRow({ c }: { c: CandidateContract }) {
  const dotColor = c.healthy ? '#44cc88' : '#cc4444';
  const ivColor = (c.mark_iv ?? 0) > 80 ? '#cc4444' : (c.mark_iv ?? 0) > 60 ? '#f0a500' : '#aaa';
  return (
    <tr>
      <td style={S.td}>
        <span style={{ ...S.healthDot, background: dotColor }} />
        {c.strike.toLocaleString()}
      </td>
      <td style={S.td}>{fmtN(c.bid, 4)}</td>
      <td style={S.td}>{fmtN(c.ask, 4)}</td>
      <td style={S.td}>{fmtN(c.mid_price, 4)}</td>
      <td style={{ ...S.td, color: ivColor }}>{fmtN(c.mark_iv, 1)}%</td>
      <td style={S.td}>{fmtN(c.delta, 3)}</td>
      <td style={S.td}>{c.open_interest.toLocaleString()}</td>
      <td style={S.td}>{fmtN(c.spread_pct * 100, 1)}%</td>
      <td style={{ ...S.td, color: c.healthy ? '#44cc88' : '#cc6666', fontSize: 9 }}>
        {c.healthy ? 'OK' : c.health_veto_reason?.slice(0, 20) ?? 'VETOED'}
      </td>
    </tr>
  );
}

interface Props { underlying: string }

export function OptionChainViewer({ underlying }: Props) {
  const [type, setType] = useState<'call' | 'put' | 'all'>('call');
  const [minDte, setMinDte] = useState(5);
  const [maxDte, setMaxDte] = useState(30);
  const { data, isLoading } = useOptionChain(underlying, type, minDte, maxDte);

  return (
    <div style={S.card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div style={S.title}>OPTION CHAIN · {underlying}</div>
        {data && (
          <span style={{ color: '#555', fontSize: 10 }}>
            {data.healthy_contracts}/{data.total_contracts} healthy · {data.exchange}
          </span>
        )}
      </div>

      <div style={S.controls}>
        <select style={S.select} value={type} onChange={e => setType(e.target.value as typeof type)}>
          <option value="call">CALLS</option>
          <option value="put">PUTS</option>
          <option value="all">ALL</option>
        </select>
        <span style={{ color: '#555', fontSize: 10 }}>DTE</span>
        <input style={S.input} type="number" min={0} value={minDte} onChange={e => setMinDte(+e.target.value)} />
        <span style={{ color: '#555', fontSize: 10 }}>–</span>
        <input style={S.input} type="number" max={365} value={maxDte} onChange={e => setMaxDte(+e.target.value)} />
        {data && <span style={{ color: '#555', fontSize: 10 }}>spot: ${data.spot_price.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>}
      </div>

      {isLoading && <div style={S.noData}>Loading option chain…</div>}

      {!isLoading && data && Object.keys(data.by_expiry).length === 0 && (
        <div style={S.noData}>No contracts found for selected filters.</div>
      )}

      {data && Object.entries(data.by_expiry).map(([expiry, contracts]) => (
        <div key={expiry}>
          <div style={S.expiry}>{expiry} · {contracts[0]?.dte}d</div>
          <table style={S.table}>
            <thead>
              <tr>{['STRIKE', 'BID', 'ASK', 'MID', 'IV', 'DELTA', 'OI', 'SPREAD', 'HEALTH'].map(h => (
                <th key={h} style={S.th}>{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {contracts.map((c, i) => <ContractRow key={i} c={c as CandidateContract} />)}
            </tbody>
          </table>
        </div>
      ))}

      {data && data.iv_stats && data.iv_stats.sample_count > 0 && (
        <div style={{ display: 'flex', gap: 16, marginTop: 10, flexWrap: 'wrap' }}>
          {[
            ['ATM IV', data.iv_stats.atm_iv != null ? `${data.iv_stats.atm_iv.toFixed(1)}%` : '—'],
            ['AVG IV', `${data.iv_stats.avg_iv.toFixed(1)}%`],
            ['MIN IV', `${data.iv_stats.min_iv.toFixed(1)}%`],
            ['MAX IV', `${data.iv_stats.max_iv.toFixed(1)}%`],
            ['SKEW', `${data.iv_stats.iv_skew.toFixed(1)}%`],
          ].map(([k, v]) => (
            <span key={k as string} style={{ fontSize: 10, color: '#555' }}>
              <span style={{ color: '#444' }}>{k} </span>
              <span style={{ color: '#888', fontWeight: 700 }}>{v}</span>
            </span>
          ))}
        </div>
      )}
      {data && (
        <div style={S.meta}>
          {data.expiry_count} expiries · {data.healthy_contracts}/{data.total_contracts} healthy · {new Date(data.timestamp_ms).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
