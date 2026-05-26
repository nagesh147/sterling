import React from 'react';
import { useAnalytics } from '../hooks/useAnalytics';
import { fmtN, fmtUSD } from '../utils/fmt';
import { c as t, tint } from '../styles/terminalUI';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 },
  cell: { display: 'flex', flexDirection: 'column', gap: 3 },
  key: { color: t.dim, fontSize: 10, letterSpacing: 1 },
  val: { fontSize: 16, fontWeight: 700 },
  noData: { color: t.dim, fontSize: 12, textAlign: 'center', padding: 20 },
};

export function AnalyticsPanel() {
  const { data, isLoading } = useAnalytics();

  if (isLoading) return null;
  if (!data || data.total_closed === 0) {
    return (
      <div style={S.card}>
        <div style={S.title}>TRADE ANALYTICS</div>
        <div style={S.noData}>No closed trades yet.</div>
      </div>
    );
  }

  const pnlColor = data.total_realized_pnl_usd >= 0 ? t.green : t.red;
  const pfColor = data.profit_factor >= 1.5 ? t.green : data.profit_factor >= 1 ? t.amber : t.red;

  return (
    <div style={S.card}>
      <div style={S.title}>TRADE ANALYTICS · {data.total_closed} closed trades</div>
      <div style={S.grid}>
        <div style={S.cell}>
          <span style={S.key}>WIN RATE</span>
          <span style={{ ...S.val, color: data.win_rate_pct >= 50 ? t.green : t.red }}>
            {fmtN(data.win_rate_pct, 0)}%
          </span>
          <span style={{ color: t.dim, fontSize: 10 }}>{data.winners}W / {data.losers}L</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>TOTAL P&L</span>
          <span style={{ ...S.val, color: pnlColor }}>
            {data.total_realized_pnl_usd >= 0 ? '+' : ''}${fmtUSD(data.total_realized_pnl_usd)}
          </span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>AVG TRADE</span>
          <span style={{ ...S.val, color: data.avg_pnl_usd >= 0 ? t.green : t.red, fontSize: 14 }}>
            {data.avg_pnl_usd >= 0 ? '+' : ''}${fmtUSD(data.avg_pnl_usd)}
          </span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>PROFIT FACTOR</span>
          <span style={{ ...S.val, color: pfColor }}>
            {data.profit_factor >= 999.9 ? '∞' : fmtN(data.profit_factor, 2)}
          </span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>AVG WINNER</span>
          <span style={{ ...S.val, color: t.green, fontSize: 13 }}>+${fmtUSD(data.avg_winner_usd)}</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>AVG LOSER</span>
          <span style={{ ...S.val, color: t.red, fontSize: 13 }}>${fmtUSD(data.avg_loser_usd)}</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>BEST TRADE</span>
          <span style={{ ...S.val, color: t.green, fontSize: 13 }}>+${fmtUSD(data.best_trade_usd)}</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>WORST TRADE</span>
          <span style={{ ...S.val, color: t.red, fontSize: 13 }}>${fmtUSD(data.worst_trade_usd)}</span>
        </div>
      </div>
    </div>
  );
}
