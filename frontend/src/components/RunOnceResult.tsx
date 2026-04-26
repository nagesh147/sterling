import React from 'react';
import { useRunOnce } from '../hooks/useRunOnce';
import { useEnterPosition } from '../hooks/usePositions';
import type { SizedTrade } from '../types';
import { fmtN } from '../utils/fmt';

const styles: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  btn: {
    background: '#1e2e1e', color: '#44cc88', border: '1px solid #44cc88',
    padding: '8px 20px', borderRadius: 4, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 13, letterSpacing: 1,
    transition: 'background 0.15s',
  },
  btnDisabled: {
    background: '#1a1a1a', color: '#444', border: '1px solid #333',
    padding: '8px 20px', borderRadius: 4, cursor: 'not-allowed',
    fontFamily: 'inherit', fontSize: 13, letterSpacing: 1,
  },
  result: { marginTop: 16 },
  recommend: { fontSize: 20, fontWeight: 700, marginBottom: 8 },
  reason: { color: '#888', fontSize: 12, marginBottom: 16 },
  tradeRow: { background: '#111', border: '1px solid #1e1e1e', borderRadius: 4, padding: 12, marginBottom: 8 },
  tradeHeader: { display: 'flex', justifyContent: 'space-between', marginBottom: 6 },
  structType: { color: '#aaddff', fontWeight: 700, fontSize: 13 },
  score: { fontSize: 13, fontWeight: 600 },
  tradeGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, fontSize: 11 },
  cell: { display: 'flex', flexDirection: 'column', gap: 2 },
  key: { color: '#555' },
  val: { color: '#ccc' },
  error: { color: '#cc4444', fontSize: 12, marginTop: 8 },
  noTrade: { color: '#cc4444', fontSize: 16, fontWeight: 700 },
  paperBadge: { display: 'inline-block', background: '#1a2a1a', color: '#44cc88', padding: '2px 8px', borderRadius: 3, fontSize: 11, marginLeft: 8 },
};

const SCORE_LABELS: Record<string, string> = {
  regime: 'REGIME', signal: 'SIGNAL', exec_timing: 'EXEC',
  health: 'HEALTH', dte: 'DTE', rr: 'R/R',
};

function ScoreBreakdown({ bd }: { bd: Record<string, number> }) {
  const entries = Object.entries(bd).filter(([k]) => k !== 'total');
  if (!entries.length) return null;
  return (
    <div style={{ marginTop: 8, borderTop: '1px solid #1a1a1a', paddingTop: 8 }}>
      <div style={{ color: '#444', fontSize: 10, letterSpacing: 1, marginBottom: 4 }}>SCORE BREAKDOWN</div>
      {entries.map(([key, val]) => (
        <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
          <span style={{ color: '#444', fontSize: 10, width: 60 }}>{SCORE_LABELS[key] ?? key.toUpperCase()}</span>
          <div style={{ flex: 1, height: 4, background: '#1a1a1a', borderRadius: 2 }}>
            <div style={{ width: `${Math.min(100, val)}%`, height: '100%', background: val >= 70 ? '#44cc88' : val >= 50 ? '#f0c040' : '#cc4444', borderRadius: 2 }} />
          </div>
          <span style={{ color: '#666', fontSize: 10, width: 28, textAlign: 'right' }}>{fmtN(val, 0)}</span>
        </div>
      ))}
    </div>
  );
}

function TradeCard({ t }: { t: SizedTrade }) {
  const s = t.structure;
  const leg = s.legs[0];
  return (
    <div style={styles.tradeRow}>
      <div style={styles.tradeHeader}>
        <span style={styles.structType}>{s.structure_type}</span>
        <span style={{ ...styles.score, color: s.score >= 70 ? '#44cc88' : s.score >= 50 ? '#f0c040' : '#cc4444' }}>
          {fmtN(s.score, 1)}
        </span>
      </div>
      <div style={styles.tradeGrid}>
        <div style={styles.cell}><span style={styles.key}>STRIKE</span><span style={styles.val}>{leg?.strike.toLocaleString()}</span></div>
        <div style={styles.cell}><span style={styles.key}>EXPIRY</span><span style={styles.val}>{leg?.expiry_date} ({leg?.dte}d)</span></div>
        <div style={styles.cell}><span style={styles.key}>CONTRACTS</span><span style={styles.val}>{t.contracts}</span></div>
        <div style={styles.cell}><span style={styles.key}>MAX RISK</span><span style={styles.val}>${t.max_risk_usd.toFixed(0)}</span></div>
        <div style={styles.cell}><span style={styles.key}>PREMIUM</span><span style={styles.val}>{s.net_premium.toFixed(4)}</span></div>
        <div style={styles.cell}><span style={styles.key}>R/R</span><span style={styles.val}>{s.risk_reward?.toFixed(2) ?? '∞'}</span></div>
        <div style={styles.cell}><span style={styles.key}>CAPITAL AT RISK</span><span style={styles.val}>{t.capital_at_risk_pct.toFixed(2)}%</span></div>
        <div style={styles.cell}><span style={styles.key}>IV</span><span style={styles.val}>{leg?.mark_iv?.toFixed(1)}%</span></div>
      </div>
      <ScoreBreakdown bd={s.score_breakdown} />
    </div>
  );
}

interface Props { underlying: string }

export function RunOnceResult({ underlying }: Props) {
  const { mutate, data, isPending, error } = useRunOnce();
  const enter = useEnterPosition();  // hook already invalidates ['positions'] on success
  const canEnter = data && data.recommendation !== 'no_trade' && data.ranked_structures.length > 0;

  const recColor = data
    ? data.recommendation === 'no_trade' ? '#cc4444' : '#44cc88'
    : '#e0e0e0';

  return (
    <div style={styles.card}>
      <div style={styles.title}>
        RUN-ONCE EVALUATION
        <span style={styles.paperBadge}>PAPER ONLY — NO ORDERS PLACED</span>
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          style={isPending ? styles.btnDisabled : styles.btn}
          onClick={() => mutate(underlying)}
          disabled={isPending}
        >
          {isPending ? 'EVALUATING…' : `▶ RUN ONCE — ${underlying}`}
        </button>
        {canEnter && (
          <button
            style={{
              background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc88',
              padding: '8px 18px', borderRadius: 4, cursor: enter.isPending ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit', fontSize: 12, letterSpacing: 1,
              opacity: enter.isPending ? 0.5 : 1,
            }}
            onClick={() => enter.mutate({ underlying })}
            disabled={enter.isPending}
          >
            {enter.isPending ? 'ENTERING…' : '+ PAPER ENTER'}
          </button>
        )}
        {enter.data && (
          <span style={{ color: '#44cc88', fontSize: 11 }}>
            Position {enter.data.id} created ✓
          </span>
        )}
        {enter.error && (
          <span style={{ color: '#cc4444', fontSize: 11 }}>{(enter.error as Error).message}</span>
        )}
      </div>

      {error && <div style={styles.error}>{(error as Error).message}</div>}

      {data && (
        <div style={styles.result}>
          <div style={{ ...styles.recommend, color: recColor }}>
            {data.recommendation === 'no_trade' ? '✗ NO TRADE' : `✓ ${data.recommendation.toUpperCase()}`}
          </div>
          <div style={styles.reason}>{data.reason}</div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
            {[
              ['STATE', data.state],
              ['DIRECTION', data.direction.toUpperCase()],
              ['EXEC', data.exec_mode.toUpperCase()],
              data.ivr != null ? ['IVR', `${data.ivr.toFixed(1)}% · ${data.ivr_band.toUpperCase()}`] : null,
              ['NO-TRADE SCORE', fmtN(data.no_trade_score, 1)],
            ].filter((x): x is [string, string] => Boolean(x)).map(([k, v]) => (
              <span key={k as string} style={{ background: '#1a1a1a', border: '1px solid #222', borderRadius: 3, padding: '3px 8px', fontSize: 11 }}>
                <span style={{ color: '#555' }}>{k} </span>
                <span style={{ color: '#ccc' }}>{v}</span>
              </span>
            ))}
          </div>

          {data.ranked_structures.length > 0 && (
            <>
              <div style={{ color: '#555', fontSize: 11, letterSpacing: 1, marginBottom: 8 }}>RANKED STRUCTURES</div>
              {data.ranked_structures.map((t, i) => <TradeCard key={i} t={t} />)}
            </>
          )}
        </div>
      )}
    </div>
  );
}
