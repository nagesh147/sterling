import React from 'react';
import { useSnapshot } from '../hooks/useSnapshot';
import { fmtN, ivrColor, ivrWidth, fmtAge } from '../utils/fmt';
import { RegimeSparkline } from './RegimeSparkline';
import { useInstruments } from '../hooks/useInstruments';

const STATE_COLOR: Record<string, string> = {
  CONFIRMED_SETUP_ACTIVE: '#f0c040',
  ENTRY_ARMED_PULLBACK: '#44aaff',
  ENTRY_ARMED_CONTINUATION: '#66ccff',
  EARLY_SETUP_ACTIVE: '#f0a500',
  FILTERED: '#555', IDLE: '#333',
};

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 },
  cell: { display: 'flex', flexDirection: 'column', gap: 3 },
  key: { color: '#555', fontSize: 10, letterSpacing: 1 },
  val: { fontSize: 14, fontWeight: 600 },
  badge: { display: 'inline-block', padding: '3px 8px', borderRadius: 3, fontSize: 11, fontWeight: 700 },
  arrows: { display: 'flex', gap: 6, marginTop: 10 },
  arrowBadge: { padding: '4px 12px', borderRadius: 4, fontSize: 13, fontWeight: 800 },
  execRow: { marginTop: 10, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' },
  reason: { color: '#555', fontSize: 11 },
};

function IVRMini({ ivr, band, hasDvol }: { ivr: number | null | undefined; band: string; hasDvol?: boolean }) {
  const color = ivrColor(ivr);
  const source = ivr != null ? (hasDvol ? 'DVOL' : 'HV') : 'N/A';
  return (
    <div style={S.cell}>
      <span style={S.key}>IVR · {band.toUpperCase()} · <span style={{ color: hasDvol ? '#88aaff' : '#f0a500', fontSize: 9 }}>{source}</span></span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ width: 50, height: 5, background: '#1e1e1e', borderRadius: 3 }}>
          <div style={{ width: `${ivrWidth(ivr)}%`, height: '100%', background: color, borderRadius: 3 }} />
        </div>
        <span style={{ ...S.val, color, fontSize: 13 }}>{ivr != null ? ivr.toFixed(0) : '—'}</span>
      </div>
    </div>
  );
}

function STTrends({ trends, values, spot }: { trends: number[]; values?: number[]; spot: number }) {
  const labels = ['7,3', '14,2', '21,1'];
  return (
    <div style={S.cell}>
      <span style={S.key}>ST TRENDS</span>
      <div style={{ display: 'flex', gap: 4, marginTop: 2 }}>
        {(trends ?? []).map((t, i) => (
          <span key={i} title={values?.[i] ? `Level: ${values[i].toLocaleString('en-US', { maximumFractionDigits: 0 })}` : undefined} style={{
            fontSize: 11, padding: '2px 5px', borderRadius: 2, cursor: values?.[i] ? 'help' : 'default',
            background: t === 1 ? '#44cc8822' : t === -1 ? '#cc444422' : '#333',
            color: t === 1 ? '#44cc88' : t === -1 ? '#cc4444' : '#555',
          }}>{labels[i]}</span>
        ))}
      </div>
      {values?.[0] != null && values[0] > 0 && (
        <div style={{ fontSize: 10, color: '#555', marginTop: 3 }}>
          ST(7,3): <span style={{ color: spot > values[0] ? '#44cc88' : '#cc4444' }}>
            ${values[0].toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </span>
          {' '}({spot > values[0] ? `+${((spot - values[0]) / spot * 100).toFixed(2)}%` : `-${((values[0] - spot) / spot * 100).toFixed(2)}%`})
        </div>
      )}
    </div>
  );
}

export function SnapshotPanel({ underlying }: { underlying: string }) {
  const { data, isLoading, dataUpdatedAt } = useSnapshot(underlying);
  const { data: instruments } = useInstruments();
  const updatedAt = dataUpdatedAt ? fmtAge(dataUpdatedAt) : '—';
  const inst = instruments?.instruments.find(i => i.underlying === underlying);
  const hasDvol = !!inst?.dvol_symbol;

  if (isLoading) return <div style={S.card}><span style={{ color: '#444', fontSize: 12 }}>Snapshot loading…</span></div>;
  if (!data) return null;

  const regimeColor = { bullish: '#44cc88', bearish: '#cc4444', neutral: '#888' }[data.macro_regime] ?? '#888';
  const stateColor = STATE_COLOR[data.state] ?? '#444';
  const dirColor = data.direction === 'long' ? '#44cc88' : data.direction === 'short' ? '#cc4444' : '#888';

  return (
    <div style={S.card}>
      <div style={S.title}>SNAPSHOT · {underlying} · {updatedAt}</div>
      <div style={S.grid}>
        <div style={S.cell}>
          <span style={S.key}>SPOT</span>
          <span style={{ ...S.val, color: '#e0e0e0' }}>
            ${(data.spot_price ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>MACRO · {fmtN(data.regime_score, 0)}</span>
          <span style={{ ...S.val, color: regimeColor }}>{data.macro_regime.toUpperCase()}</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>1H SIGNAL</span>
          <span style={{ ...S.val, color: data.signal_trend === 1 ? '#44cc88' : data.signal_trend === -1 ? '#cc4444' : '#aaa' }}>
            {data.all_green ? '▲ ALL GREEN' : data.all_red ? '▼ ALL RED' : '~ MIXED'}
          </span>
        </div>
        <STTrends trends={data.st_trends} values={data.st_values} spot={data.spot_price} />
        <IVRMini ivr={data.ivr} band={data.ivr_band} hasDvol={hasDvol} />
      </div>

      {(data.green_arrow || data.red_arrow) && (
        <div style={S.arrows}>
          {data.green_arrow && (
            <span style={{ ...S.arrowBadge, background: '#44cc8822', color: '#44cc88', border: '1px solid #44cc88' }}>▲ BULLISH ARROW</span>
          )}
          {data.red_arrow && (
            <span style={{ ...S.arrowBadge, background: '#cc444422', color: '#cc4444', border: '1px solid #cc4444' }}>▼ BEARISH ARROW</span>
          )}
        </div>
      )}

      <div style={{ marginTop: 12, marginBottom: 4 }}>
        <div style={{ ...S.key, marginBottom: 4 }}>4H REGIME TREND (price vs EMA50)</div>
        <RegimeSparkline underlying={underlying} />
      </div>

      <div style={S.execRow}>
        <span style={{ ...S.badge, background: stateColor + '18', color: stateColor }}>{data.state}</span>
        <span style={{ ...S.badge, background: dirColor + '18', color: dirColor }}>{data.direction.toUpperCase()}</span>
        <span style={{ ...S.badge, background: '#1a1a2a', color: '#88aaff' }}>
          {data.exec_mode.toUpperCase()} {fmtN((data.exec_confidence ?? 0) * 100, 0)}%
        </span>
        <span style={S.reason}>{data.exec_reason}</span>
      </div>
    </div>
  );
}
