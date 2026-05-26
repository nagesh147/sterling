import React from 'react';
import { usePreview } from '../hooks/usePreview';
import { useRunOnce } from '../hooks/useRunOnce';
import type { TradeStructure } from '../types';
import { fmtN, fmtAge } from '../utils/fmt';
import { c as t, tint } from '../styles/terminalUI';

const styles: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
  th: { color: t.dim, textAlign: 'left', padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', borderBottom: `1px solid ${t.border}`, color: t.text },
  badge: { padding: '2px 6px', borderRadius: 3, fontSize: 11, fontWeight: 600 },
  noData: { color: t.dim, fontSize: 12, padding: 12, textAlign: 'center' },
  reason: { color: t.dim, fontSize: 12, marginTop: 8 },
  sectionTitle: { color: t.dim, fontSize: 11, letterSpacing: 1, margin: '12px 0 6px' },
};

function scoreColor(score: number) {
  if (score >= 95) return '#00e5ff';   // cyan — max
  if (score >= 85) return t.green;   // green — elevated
  if (score >= 75) return t.amber;   // amber — standard
  return t.red;                    // red — no-trade
}

function leverageBadge(score: number, strength?: string): number {
  const s = strength ?? 'NONE';
  if (score >= 95 && s === 'STRONG') return 50;
  if (score >= 90 && s === 'STRONG') return 25;
  if (score >= 85 && s === 'STRONG') return 10;
  if (score >= 80) return 5;
  if (score >= 75) return 3;
  return 1;
}

const BD_META: Record<string, { label: string; max: number }> = {
  macro_trend: { label: 'MT', max: 20 }, signal: { label: 'SG', max: 20 },
  entry: { label: 'ET', max: 15 }, contract_health: { label: 'CH', max: 20 },
  dte: { label: 'DT', max: 10 }, rr: { label: 'RR', max: 15 },
  // legacy
  regime: { label: 'R', max: 100 }, exec_timing: { label: 'E', max: 100 },
  health: { label: 'H', max: 100 },
};

function MiniScoreBars({ bd }: { bd: Record<string, number | string> }) {
  const entries = Object.entries(bd).filter(([k]) => k !== 'total' && k !== 'veto_reason' && typeof bd[k] === 'number');
  if (!entries.length) return null;
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center', marginTop: 4 }}>
      {entries.map(([k, v]) => {
        const meta = BD_META[k] ?? { label: k.slice(0,2), max: 100 };
        const numV = typeof v === 'number' ? v : 0;
        const pct = (numV / meta.max) * 100;
        const color = pct >= 70 ? t.green : pct >= 40 ? t.amber : t.red;
        return (
          <div key={k} title={`${meta.label}: ${fmtN(numV, 0)}/${meta.max}`}
            style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
            <div style={{ width: 18, height: 18, position: 'relative' }}>
              <div style={{ position: 'absolute', bottom: 0, width: '100%',
                height: `${Math.min(100, pct)}%`, background: color,
                borderRadius: 2, opacity: 0.8 }} />
            </div>
            <span style={{ fontSize: 8, color: t.dim }}>{meta.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function StructureRow({ s }: { s: TradeStructure }) {
  const leg = s.legs[0];
  return (
    <tr>
      <td style={styles.td}>
        <span style={{ ...styles.badge, background: s.structure_type.includes('call') ? '#1a3322' : '#331a1a', color: s.structure_type.includes('call') ? t.green : t.red }}>
          {s.structure_type}
        </span>
      </td>
      <td style={styles.td}>{leg?.strike.toLocaleString() ?? '—'}</td>
      <td style={styles.td}>{leg?.expiry_date ?? '—'} ({leg?.dte}d)</td>
      <td style={styles.td}>{fmtN(s.net_premium, 4)}</td>
      <td style={styles.td}>{s.risk_reward != null ? s.risk_reward.toFixed(2) : '∞'}</td>
      <td style={{ ...styles.td, color: scoreColor(s.score ?? 0), fontWeight: 700 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {fmtN(s.score, 1)}
          {s.score >= 75 && (
            <span style={{
              fontSize: 9, padding: '1px 4px', borderRadius: 2, fontWeight: 600,
              background: t.raised, color: t.blue, border: '1px solid #88aaff33',
            }}>{leverageBadge(s.score)}x</span>
          )}
        </div>
        <MiniScoreBars bd={s.score_breakdown} />
      </td>
    </tr>
  );
}

interface Props { underlying: string }

export function PreviewCandidates({ underlying }: Props) {
  const { data, isLoading, error, dataUpdatedAt } = usePreview(underlying);
  const runOnce = useRunOnce();
  const updatedAt = dataUpdatedAt ? fmtAge(dataUpdatedAt) : '—';

  if (isLoading) return <div style={styles.card}><div style={styles.title}>PREVIEW CANDIDATES — loading…</div></div>;

  return (
    <div style={styles.card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={styles.title}>PREVIEW CANDIDATES · {underlying} · {updatedAt}</div>
        <button
          style={{
            background: t.raised, color: t.blue, border: `1px solid ${t.blue}`,
            padding: '4px 12px', borderRadius: 3, cursor: runOnce.isPending ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit', fontSize: 11, letterSpacing: 1, opacity: runOnce.isPending ? 0.5 : 1,
          }}
          onClick={() => runOnce.mutate(underlying)}
          disabled={runOnce.isPending}
          title="Run full evaluation with sizing — scroll down for results"
        >
          {runOnce.isPending ? 'EVALUATING…' : '▶ RUN ONCE'}
        </button>
      </div>

      {error && <div style={{ color: t.red, fontSize: 12 }}>{(error as Error).message}</div>}

      {data && (
        <>
          <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
            <span style={{ ...styles.badge, background: t.raised, color: t.blue }}>
              {data.state}
            </span>
            <span style={{ ...styles.badge, background: t.raised, color: t.dim }}>
              {data.direction.toUpperCase()}
            </span>
            {data.ivr != null && (
              <span style={{ ...styles.badge, background: t.raised, color: t.text }}>
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
