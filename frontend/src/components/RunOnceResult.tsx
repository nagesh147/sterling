import React from 'react';
import { useRunOnce } from '../hooks/useRunOnce';
import { useEnterPosition } from '../hooks/usePositions'; // used inside TradeCard
import type { SizedTrade } from '../types';
import { fmtN, fmtStructure, fmtState } from '../utils/fmt';

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

const SCORE_META: Record<string, { label: string; tooltip: string }> = {
  regime:     { label: 'Macro trend',    tooltip: 'Price vs 50-bar EMA on 4H chart. High = strong trend alignment with trade direction.' },
  signal:     { label: '1H signal',      tooltip: 'SuperTrend agreement across 3 periods (7,3 · 14,2 · 21,1) on Heikin-Ashi candles. 100 = all three aligned.' },
  exec_timing:{ label: 'Entry timing',   tooltip: 'Pullback into support scores highest (60–100). Continuation breakout scores 50–90. Waiting scores 20.' },
  health:     { label: 'Contract quality', tooltip: 'Bid-ask spread, open interest, volume, and quote freshness. Low score = wide spread or thin market — avoid.' },
  dte:        { label: 'Days to expiry', tooltip: 'Preferred 10–15 DTE scores 100. Below 5 DTE = veto. Above 15 DTE loses time-value efficiency.' },
  rr:         { label: 'Risk / reward',  tooltip: 'Max gain ÷ max loss. 2:1 scores 80, 3:1 scores 100. Naked calls/puts have undefined RR — scored 40.' },
};

function ScoreBreakdown({ bd, ivr }: { bd: Record<string, number>; ivr?: number | null }) {
  const entries = Object.entries(bd).filter(([k]) => k !== 'total');
  if (!entries.length) return null;
  return (
    <div style={{ marginTop: 8, borderTop: '1px solid #1a1a1a', paddingTop: 8 }}>
      <div style={{ color: '#444', fontSize: 10, letterSpacing: 1, marginBottom: 6 }}>SCORE BREAKDOWN</div>
      {entries.map(([key, val]) => {
        const meta = SCORE_META[key];
        const color = val >= 70 ? '#44cc88' : val >= 50 ? '#f0c040' : '#cc4444';
        return (
          <div key={key} title={meta?.tooltip} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, cursor: 'help' }}>
            <span style={{ color: '#555', fontSize: 10, width: 90, flexShrink: 0 }}>
              {meta?.label ?? key}
            </span>
            <div style={{ flex: 1, height: 4, background: '#1a1a1a', borderRadius: 2 }}>
              <div style={{ width: `${Math.min(100, val)}%`, height: '100%', background: color, borderRadius: 2 }} />
            </div>
            <span style={{ color, fontSize: 10, fontWeight: 600, width: 28, textAlign: 'right' as const }}>{fmtN(val, 0)}</span>
          </div>
        );
      })}
      {ivr != null && ivr > 60 && (
        <div style={{ marginTop: 6, fontSize: 10, color: '#f0a500' }}>
          ⚠ IV Rank {ivr.toFixed(0)} — elevated premium cost. Spreads provide better defined risk than naked calls/puts.
        </div>
      )}
      {ivr == null && (
        <div style={{ marginTop: 6, fontSize: 10, color: '#888' }}>
          IV data unavailable — prefer defined-risk spreads.
        </div>
      )}
    </div>
  );
}

function TradeCard({ t, rank, underlying, ivr }: { t: SizedTrade; rank: number; underlying: string; ivr?: number | null }) {
  const s = t.structure;
  const leg = s.legs[0];
  const enter = useEnterPosition();
  return (
    <div style={styles.tradeRow}>
      <div style={styles.tradeHeader}>
        <span style={styles.structType}>{fmtStructure(s.structure_type)}</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ ...styles.score, color: s.score >= 70 ? '#44cc88' : s.score >= 50 ? '#f0c040' : '#cc4444' }}>
            {fmtN(s.score, 1)}
          </span>
          <button
            style={{
              background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc8866',
              padding: '3px 8px', borderRadius: 3, cursor: enter.isPending ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit', fontSize: 10, letterSpacing: 1,
              opacity: enter.isPending ? 0.5 : 1,
            }}
            onClick={() => enter.mutate({ underlying, structure_rank: rank })}
            disabled={enter.isPending}
            title={`Enter this structure (rank #${rank + 1})`}
          >
            {enter.isPending ? '…' : '+ ENTER'}
          </button>
        </div>
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
      <ScoreBreakdown bd={s.score_breakdown} ivr={ivr} />
    </div>
  );
}

interface Props { underlying: string }

export function RunOnceResult({ underlying }: Props) {
  const { mutate, data, isPending, error } = useRunOnce();

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
      </div>

      {error && <div style={styles.error}>{(error as Error).message}</div>}

      {data && (
        <div style={styles.result}>
          <div style={{ ...styles.recommend, color: recColor }}>
            {data.recommendation === 'no_trade' ? '✗ No trade' : `✓ ${fmtStructure(data.recommendation)}`}
          </div>
          <div style={styles.reason}>{data.reason}</div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
            {[
              ['Status', fmtState(data.state)],
              ['Direction', data.direction === 'long' ? 'Bullish' : data.direction === 'short' ? 'Bearish' : 'Neutral'],
              ['Entry', data.exec_mode === 'pullback' ? 'Pullback' : data.exec_mode === 'continuation' ? 'Breakout' : 'Wait'],
              data.ivr != null ? ['IV Rank', `${data.ivr.toFixed(0)} · ${data.ivr_band}`] : ['IV Rank', 'Unknown'],
              ['No-trade score', fmtN(data.no_trade_score, 1)],
            ].filter((x): x is [string, string] => Boolean(x)).map(([k, v]) => (
              <span key={k as string} style={{ background: '#1a1a1a', border: '1px solid #222', borderRadius: 3, padding: '3px 8px', fontSize: 11 }}>
                <span style={{ color: '#555' }}>{k} </span>
                <span style={{ color: '#ccc' }}>{v}</span>
              </span>
            ))}
          </div>

          {data.ranked_structures.length > 0 && (
            <>
              <div style={{ color: '#555', fontSize: 11, letterSpacing: 1, marginBottom: 8 }}>RANKED STRUCTURES · click + ENTER to paper-enter that structure</div>
              {data.ranked_structures.map((t, i) => (
                <TradeCard key={i} t={t} rank={i} underlying={underlying} ivr={data.ivr} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
