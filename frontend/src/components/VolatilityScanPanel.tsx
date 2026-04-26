import React from 'react';
import { useVolatilityScan } from '../hooks/useVolatilityScan';
import { fmtN } from '../utils/fmt';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  btn: {
    background: '#1a1a2a', color: '#88aaff', border: '1px solid #88aaff',
    padding: '7px 18px', borderRadius: 4, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 12, letterSpacing: 1,
  },
  struct: { background: '#111', border: '1px solid #1e1e1e', borderRadius: 4, padding: 12, marginBottom: 8 },
  type: { color: '#88aaff', fontWeight: 700, fontSize: 13, marginBottom: 8 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, fontSize: 11 },
  cell: { display: 'flex', flexDirection: 'column', gap: 2 },
  key: { color: '#555', fontSize: 10 },
  val: { color: '#ccc' },
  note: { color: '#444', fontSize: 10, marginTop: 10, fontStyle: 'italic' },
  empty: { color: '#444', fontSize: 12, padding: '16px 0', textAlign: 'center' },
};

const TYPE_LABEL: Record<string, string> = {
  long_straddle: 'LONG STRADDLE (ATM)',
  long_strangle: 'LONG STRANGLE (OTM)',
};

interface Props { underlying: string }

export function VolatilityScanPanel({ underlying }: Props) {
  const scan = useVolatilityScan();

  return (
    <div style={S.card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={S.title}>VOLATILITY STRUCTURES — {underlying}</div>
        <button
          style={scan.isPending ? { ...S.btn, opacity: 0.5, cursor: 'not-allowed' } : S.btn}
          onClick={() => scan.mutate(underlying)}
          disabled={scan.isPending}
        >
          {scan.isPending ? 'SCANNING…' : '⬡ STRADDLE / STRANGLE SCAN'}
        </button>
      </div>

      {scan.error && (
        <div style={{ color: '#cc4444', fontSize: 12 }}>{(scan.error as Error).message}</div>
      )}

      {!scan.data && !scan.isPending && (
        <div style={S.empty}>
          Scan finds ATM straddle + OTM strangle candidates — use when expecting big move but uncertain direction.
        </div>
      )}

      {scan.data && (
        <>
          <div style={{ color: '#555', fontSize: 11, marginBottom: 12 }}>
            Spot: ${scan.data.spot_price.toLocaleString('en-US', { maximumFractionDigits: 0 })} ·
            {scan.data.healthy_candidates} healthy contracts scanned
          </div>

          {scan.data.structures.length === 0 ? (
            <div style={S.empty}>No valid structures found — option chain may be empty or unhealthy.</div>
          ) : (
            scan.data.structures.map((s, i) => (
              <div key={i} style={S.struct}>
                <div style={S.type}>{TYPE_LABEL[s.structure_type] ?? s.structure_type}</div>
                <div style={S.grid}>
                  <div style={S.cell}>
                    <span style={S.key}>STRIKE(S)</span>
                    <span style={S.val}>
                      {s.structure_type === 'long_straddle'
                        ? s.strike?.toLocaleString()
                        : `${s.put_strike?.toLocaleString()} / ${s.call_strike?.toLocaleString()}`}
                    </span>
                  </div>
                  <div style={S.cell}>
                    <span style={S.key}>EXPIRY</span>
                    <span style={S.val}>{s.expiry_date} ({s.dte}d)</span>
                  </div>
                  <div style={S.cell}>
                    <span style={S.key}>NET DEBIT</span>
                    <span style={{ ...S.val, color: '#cc6644' }}>{fmtN(s.net_debit, 4)}</span>
                  </div>
                  <div style={S.cell}>
                    <span style={S.key}>MAX LOSS</span>
                    <span style={S.val}>{fmtN(s.max_loss, 4)}</span>
                  </div>
                  <div style={S.cell}>
                    <span style={S.key}>B/E UP</span>
                    <span style={{ ...S.val, color: '#44cc88' }}>${s.breakeven_up.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
                  </div>
                  <div style={S.cell}>
                    <span style={S.key}>B/E DOWN</span>
                    <span style={{ ...S.val, color: '#cc4444' }}>${s.breakeven_down.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
                  </div>
                  <div style={S.cell}>
                    <span style={S.key}>AVG IV</span>
                    <span style={S.val}>{fmtN(s.avg_iv, 1)}%</span>
                  </div>
                  <div style={S.cell}>
                    <span style={S.key}>HEALTH</span>
                    <span style={{ ...S.val, color: s.health_score > 60 ? '#44cc88' : '#f0c040' }}>
                      {fmtN(s.health_score, 0)}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
          <div style={S.note}>{scan.data.note}</div>
        </>
      )}
    </div>
  );
}
