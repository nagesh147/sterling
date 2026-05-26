import React from 'react';
import { useRunOnce } from '../hooks/useRunOnce';
import { useEnterPosition } from '../hooks/usePositions'; // used inside TradeCard
import type { SizedTrade } from '../types';
import { fmtN, fmtStructure, fmtState } from '../utils/fmt';
import { c as ui, tint } from '../styles/terminalUI';

const styles: Record<string, React.CSSProperties> = {
  card: { background: ui.raised, border: `1px solid ${ui.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: ui.dim, fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  btn: {
    background: '#1e2e1e', color: ui.green, border: `1px solid ${ui.green}`,
    padding: '8px 20px', borderRadius: 4, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 13, letterSpacing: 1,
    transition: 'background 0.15s',
  },
  btnDisabled: {
    background: ui.raised, color: ui.dim, border: `1px solid ${ui.border}`,
    padding: '8px 20px', borderRadius: 4, cursor: 'not-allowed',
    fontFamily: 'inherit', fontSize: 13, letterSpacing: 1,
  },
  result: { marginTop: 16 },
  recommend: { fontSize: 20, fontWeight: 700, marginBottom: 8 },
  reason: { color: ui.dim, fontSize: 12, marginBottom: 16 },
  tradeRow: { background: ui.bg, border: `1px solid ${ui.border}`, borderRadius: 4, padding: 12, marginBottom: 8 },
  tradeHeader: { display: 'flex', justifyContent: 'space-between', marginBottom: 6 },
  structType: { color: ui.blue, fontWeight: 700, fontSize: 13 },
  score: { fontSize: 13, fontWeight: 600 },
  tradeGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, fontSize: 11 },
  cell: { display: 'flex', flexDirection: 'column', gap: 2 },
  key: { color: ui.dim },
  val: { color: ui.text },
  error: { color: ui.red, fontSize: 12, marginTop: 8 },
  noTrade: { color: ui.red, fontSize: 16, fontWeight: 700 },
  paperBadge: { display: 'inline-block', background: '#1a2a1a', color: ui.green, padding: '2px 8px', borderRadius: 3, fontSize: 11, marginLeft: 8 },
};

const SCORE_META: Record<string, { label: string; max: number; tooltip: string }> = {
  // v2 keys
  macro_trend:     { label: 'Macro trend',      max: 20, tooltip: 'Dual EMA (21/55) crossover + ADX strength. Max 20 pts.' },
  signal:          { label: 'Signal strength',  max: 20, tooltip: 'Weighted confluence: ST flip, RSI, BB/KC squeeze, volume, HA body. Max 20 pts.' },
  entry:           { label: 'Entry timing',     max: 15, tooltip: 'Mode A pullback (14 pts) or Mode B breakout (10 pts) with 2× volume. Max 15 pts.' },
  contract_health: { label: 'Contract quality', max: 20, tooltip: 'Spread, OI tiers, funding rate penalty. Max 20 pts.' },
  dte:             { label: 'Days to expiry',   max: 10, tooltip: '7-45 DTE sweet spot. < 7 DTE = veto. Max 10 pts.' },
  rr:              { label: 'Risk / reward',    max: 15, tooltip: 'rr≥2.5→15 · rr≥2.0→11 · rr≥1.5→7 · rr<1.5→0. Max 15 pts.' },
  // v1 legacy keys (backward compat)
  regime:          { label: 'Macro trend',      max: 100, tooltip: 'Macro regime score.' },
  exec_timing:     { label: 'Entry timing',     max: 100, tooltip: 'Entry timing score.' },
  health:          { label: 'Contract quality', max: 100, tooltip: 'Contract health score.' },
};

function ScoreBreakdown({ bd, ivr }: { bd: Record<string, number | string>; ivr?: number | null }) {
  const entries = Object.entries(bd).filter(([k]) => k !== 'total' && k !== 'veto_reason');
  const vetoReason = bd['veto_reason'] as string | undefined;
  if (!entries.length) return null;
  return (
    <div style={{ marginTop: 8, borderTop: `1px solid ${ui.border}`, paddingTop: 8 }}>
      <div style={{ color: ui.dim, fontSize: 10, letterSpacing: 1, marginBottom: 6 }}>SCORE BREAKDOWN</div>
      {vetoReason && (
        <div style={{ color: ui.red, fontSize: 10, marginBottom: 6 }}>✕ VETOED: {vetoReason}</div>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10 }}>
        <thead>
          <tr>
            <th style={{ color: ui.dim, textAlign: 'left', padding: '2px 4px' }}>COMPONENT</th>
            <th style={{ color: ui.dim, textAlign: 'right', padding: '2px 4px' }}>SCORE</th>
            <th style={{ color: ui.dim, textAlign: 'right', padding: '2px 4px' }}>MAX</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, val]) => {
            const meta = SCORE_META[key];
            const numVal = typeof val === 'number' ? val : 0;
            const maxVal = meta?.max ?? 100;
            const pct = (numVal / maxVal) * 100;
            const color = pct >= 70 ? ui.green : pct >= 40 ? ui.amber : ui.red;
            return (
              <tr key={key} title={meta?.tooltip} style={{ cursor: meta?.tooltip ? 'help' : 'default' }}>
                <td style={{ padding: '3px 4px', color: ui.dim }}>{meta?.label ?? key}</td>
                <td style={{ padding: '3px 4px', textAlign: 'right', color, fontWeight: 600 }}>{fmtN(numVal, 1)}</td>
                <td style={{ padding: '3px 4px', textAlign: 'right', color: ui.dim }}>{maxVal}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {ivr != null && ivr > 60 && (
        <div style={{ marginTop: 6, fontSize: 10, color: ui.amber }}>
          ⚠ IV Rank {ivr.toFixed(0)} — elevated premium. Spreads preferred over naked.
        </div>
      )}
      {ivr == null && (
        <div style={{ marginTop: 6, fontSize: 10, color: ui.dim }}>IV data unavailable — prefer defined-risk spreads.</div>
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
          <span style={{ ...styles.score, color: s.score >= 70 ? ui.green : s.score >= 50 ? ui.amber : ui.red }}>
            {fmtN(s.score, 1)}
          </span>
          <button
            style={{
              background: '#1a2a1a', color: ui.green, border: '1px solid #44cc8866',
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
    ? data.recommendation === 'no_trade' ? ui.red : ui.green
    : ui.bright;

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
              <span key={k as string} style={{ background: ui.raised, border: `1px solid ${ui.border}`, borderRadius: 3, padding: '3px 8px', fontSize: 11 }}>
                <span style={{ color: ui.dim }}>{k} </span>
                <span style={{ color: ui.text }}>{v}</span>
              </span>
            ))}
          </div>

          {data.ranked_structures.length > 0 && (
            <>
              <div style={{ color: ui.dim, fontSize: 11, letterSpacing: 1, marginBottom: 8 }}>RANKED STRUCTURES · click + ENTER to paper-enter that structure</div>
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
