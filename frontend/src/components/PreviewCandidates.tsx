import React from 'react';
import { usePreview } from '../hooks/usePreview';
import type { TradeStructure } from '../types';
import { fmtN } from '../utils/fmt';

const styles: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
  th: { color: '#555', textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #222' },
  td: { padding: '6px 8px', borderBottom: '1px solid #1a1a1a', color: '#ccc' },
  badge: { padding: '2px 6px', borderRadius: 3, fontSize: 11, fontWeight: 600 },
  noData: { color: '#555', fontSize: 12, padding: 12, textAlign: 'center' },
  reason: { color: '#555', fontSize: 12, marginTop: 8 },
  sectionTitle: { color: '#666', fontSize: 11, letterSpacing: 1, margin: '12px 0 6px' },
};

function scoreColor(score: number) {
  if (score >= 70) return '#44cc88';
  if (score >= 50) return '#f0c040';
  return '#cc4444';
}

const BD_LABELS: Record<string, string> = {
  regime: 'R', signal: 'S', exec_timing: 'E', health: 'H', dte: 'D', rr: 'RR',
};

function MiniScoreBars({ bd }: { bd: Record<string, number> }) {
  const entries = Object.entries(bd).filter(([k]) => k !== 'total');
  if (!entries.length) return null;
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center', marginTop: 4 }}>
      {entries.map(([k, v]) => (
        <div key={k} title={`${BD_LABELS[k] ?? k}: ${fmtN(v, 0)}`}
          style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
          <div style={{ width: 18, height: 18, position: 'relative' }}>
            <div style={{ position: 'absolute', bottom: 0, width: '100%',
              height: `${Math.min(100, v)}%`, background: v >= 70 ? '#44cc88' : v >= 50 ? '#f0c040' : '#cc4444',
              borderRadius: 2, opacity: 0.8 }} />
          </div>
          <span style={{ fontSize: 8, color: '#555' }}>{BD_LABELS[k] ?? k}</span>
        </div>
      ))}
    </div>
  );
}

function StructureRow({ s }: { s: TradeStructure }) {
  const leg = s.legs[0];
  return (
    <tr>
      <td style={styles.td}>
        <span style={{ ...styles.badge, background: s.structure_type.includes('call') ? '#1a3322' : '#331a1a', color: s.structure_type.includes('call') ? '#44cc88' : '#cc4444' }}>
          {s.structure_type}
        </span>
      </td>
      <td style={styles.td}>{leg?.strike.toLocaleString() ?? '—'}</td>
      <td style={styles.td}>{leg?.expiry_date ?? '—'} ({leg?.dte}d)</td>
      <td style={styles.td}>{fmtN(s.net_premium, 4)}</td>
      <td style={styles.td}>{s.risk_reward != null ? s.risk_reward.toFixed(2) : '∞'}</td>
      <td style={{ ...styles.td, color: scoreColor(s.score ?? 0), fontWeight: 700 }}>
        <div>{fmtN(s.score, 1)}</div>
        <MiniScoreBars bd={s.score_breakdown} />
      </td>
    </tr>
  );
}

interface Props { underlying: string }

export function PreviewCandidates({ underlying }: Props) {
  const { data, isLoading, error } = usePreview(underlying);

  if (isLoading) return <div style={styles.card}><div style={styles.title}>PREVIEW CANDIDATES — loading…</div></div>;

  return (
    <div style={styles.card}>
      <div style={styles.title}>PREVIEW CANDIDATES · {underlying}</div>

      {error && <div style={{ color: '#cc4444', fontSize: 12 }}>{(error as Error).message}</div>}

      {data && (
        <>
          <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
            <span style={{ ...styles.badge, background: '#1a1a2a', color: '#88aaff' }}>
              {data.state}
            </span>
            <span style={{ ...styles.badge, background: '#1a1a1a', color: '#888' }}>
              {data.direction.toUpperCase()}
            </span>
            {data.ivr != null && (
              <span style={{ ...styles.badge, background: '#222', color: '#aaa' }}>
                IVR {fmtN(data.ivr, 1)}% · {data.ivr_band.toUpperCase()}
              </span>
            )}
          </div>

          {data.ranked_structures.length === 0 ? (
            <div style={styles.noData}>No candidate structures — {data.reason}</div>
          ) : (
            <>
              <div style={styles.sectionTitle}>RANKED STRUCTURES</div>
              <table style={styles.table}>
                <thead>
                  <tr>
                    {['TYPE', 'STRIKE', 'EXPIRY', 'PREMIUM', 'R/R', 'SCORE'].map(h => (
                      <th key={h} style={styles.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.ranked_structures.map((s, i) => <StructureRow key={i} s={s} />)}
                </tbody>
              </table>
            </>
          )}

          {data.reason && <div style={styles.reason}>{data.reason}</div>}
        </>
      )}
    </div>
  );
}
