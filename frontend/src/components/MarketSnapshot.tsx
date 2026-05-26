import React from 'react';
import { useMarketSnapshot } from '../hooks/useMarketSnapshot';
import { fmtN, fmtUSD, ivrColor } from '../utils/fmt';
import { c as t, tint } from '../styles/terminalUI';

const styles: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 },
  cell: { display: 'flex', flexDirection: 'column', gap: 4 },
  key: { color: t.dim, fontSize: 11 },
  val: { fontSize: 14, fontWeight: 600, color: t.bright },
  source: { marginTop: 10, color: t.dim, fontSize: 11 },
  candles: { display: 'flex', gap: 8, marginTop: 10 },
  candleBadge: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 3, padding: '2px 8px', fontSize: 11, color: t.dim },
  error: { color: t.red, fontSize: 12 },
};

interface Props { underlying: string }

export function MarketSnapshot({ underlying }: Props) {
  const { data, isLoading, error } = useMarketSnapshot(underlying);

  if (isLoading) return <div style={styles.card}><div style={styles.title}>MARKET SNAPSHOT — loading…</div></div>;
  if (error) return (
    <div style={styles.card}>
      <div style={styles.title}>MARKET SNAPSHOT</div>
      <div style={styles.error}>{(error as Error).message}</div>
    </div>
  );
  if (!data) return null;

  const ivColor = ivrColor(data.ivr);

  return (
    <div style={styles.card}>
      <div style={styles.title}>MARKET SNAPSHOT · {underlying} · {data.data_source}</div>
      <div style={styles.grid}>
        <div style={styles.cell}>
          <span style={styles.key}>INDEX PRICE</span>
          <span style={styles.val}>${fmtUSD(data.index_price)}</span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>PERP PRICE</span>
          <span style={styles.val}>${fmtUSD(data.perp_price)}</span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>{data.dvol != null ? 'DVOL' : 'VOL INDEX'}</span>
          <span style={styles.val}>{data.dvol != null ? fmtN(data.dvol, 1) : '—'}</span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>IVR {data.dvol == null ? '(HV)' : '(DVOL)'}</span>
          <span style={{ ...styles.val, color: ivColor }}>
            {data.ivr != null ? `${data.ivr.toFixed(1)}%` : '—'}
          </span>
        </div>
      </div>
      <div style={styles.candles}>
        <span style={styles.candleBadge}>4H: {data.candles_4h_count} candles</span>
        <span style={styles.candleBadge}>1H: {data.candles_1h_count} candles</span>
        <span style={styles.candleBadge}>15m: {data.candles_15m_count} candles</span>
      </div>
      <div style={styles.source}>ts: {new Date(data.timestamp_ms).toISOString()}</div>
    </div>
  );
}
