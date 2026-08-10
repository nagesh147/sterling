import React from 'react';
import { k } from '../../styles/kiteUI';

export type AdaptiveEdgeDecision = 'ENTER' | 'HOLD' | 'EXIT' | 'REJECT';

export interface AdaptiveEdgeRow {
  id: string;
  instrument: string;
  observationTime: number;
  featureQuality?: string | null;
  edgeScore?: number | null;
  edgeConfidence?: number | null;
  expectedGrossValue?: number | null;
  executionCost?: number | null;
  expectedNetValue?: number | null;
  economicallyEligible?: boolean | null;
  mode?: string | null;
  authorizedRisk?: number | null;
  consumedRisk?: number | null;
  quantity?: number | null;
  entryPrice?: number | null;
  ltp?: number | null;
  currentPnl?: number | null;
  peakPnl?: number | null;
  profitGiveback?: number | null;
  protectionState?: string | null;
  decision: AdaptiveEdgeDecision;
  reason?: string | null;
  formulaIds?: string[];
}

interface Props {
  rows: AdaptiveEdgeRow[];
  selectedId?: string | null;
  onSelect?: (row: AdaptiveEdgeRow) => void;
  onScan?: () => void;
  scanning?: boolean;
}

const fmt = (v: number | null | undefined, d = 2) =>
  v == null || !Number.isFinite(v) ? '—' : v.toFixed(d);

const fmtMoney = (v: number | null | undefined) =>
  v == null || !Number.isFinite(v)
    ? '—'
    : `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

function tone(decision: AdaptiveEdgeDecision) {
  if (decision === 'ENTER') return k.green;
  if (decision === 'EXIT' || decision === 'REJECT') return k.red;
  return k.amber;
}

function Cell({ label, value, align = 'left' }: { label: string; value: React.ReactNode; align?: 'left' | 'right' }) {
  return (
    <div style={{ minWidth: 88, textAlign: align }}>
      <div style={{ fontSize: 8, color: k.dim, letterSpacing: '0.06em', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ marginTop: 2, fontSize: 11, color: k.bright, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
    </div>
  );
}

function Detail({ row }: { row: AdaptiveEdgeRow }) {
  return (
    <div style={{ padding: '10px 12px', borderTop: `1px solid ${k.border}`, background: 'rgba(255,255,255,.015)' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(130px, 1fr))', gap: 10 }}>
        <Cell label="Observation" value={new Date(row.observationTime).toLocaleTimeString()} />
        <Cell label="Feature quality" value={row.featureQuality || '—'} />
        <Cell label="Edge formula" value={row.formulaIds?.find((x) => x.startsWith('F-10')) || '—'} />
        <Cell label="Decision" value={row.decision} />
        <Cell label="Gross value" value={fmtMoney(row.expectedGrossValue)} align="right" />
        <Cell label="Execution cost" value={fmtMoney(row.executionCost)} align="right" />
        <Cell label="Net value" value={fmtMoney(row.expectedNetValue)} align="right" />
        <Cell label="Economic gate" value={row.economicallyEligible == null ? '—' : row.economicallyEligible ? 'ELIGIBLE' : 'BLOCKED'} align="right" />
        <Cell label="Mode" value={row.mode || '—'} />
        <Cell label="Authorized risk" value={fmtMoney(row.authorizedRisk)} align="right" />
        <Cell label="Consumed risk" value={fmtMoney(row.consumedRisk)} align="right" />
        <Cell label="Protection" value={row.protectionState || '—'} />
      </div>
      {row.reason && (
        <div style={{ marginTop: 9, fontSize: 9, color: k.muted }}>
          <span style={{ color: k.dim }}>REASON </span>{row.reason}
        </div>
      )}
      {row.formulaIds?.length ? (
        <div style={{ marginTop: 5, fontSize: 8, color: k.dim }}>
          FORMULAS: {row.formulaIds.join(' · ')}
        </div>
      ) : null}
    </div>
  );
}

export function AdaptiveEdgePanel({ rows, selectedId, onSelect, onScan, scanning }: Props) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', minHeight: 0, height: '100%', background: k.bg }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderBottom: `1px solid ${k.border}` }}>
        <strong style={{ fontSize: 11, letterSpacing: '0.07em', color: k.bright }}>ADAPTIVE EDGE</strong>
        <span style={{ fontSize: 8, color: k.dim }}>OPPORTUNITY → EDGE → ECONOMICS → RISK</span>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 9, color: k.dim }}>{rows.length} candidates</span>
        {onScan && (
          <button onClick={onScan} disabled={scanning} style={{ fontSize: 9, padding: '4px 9px', border: `1px solid ${k.border}`, background: 'transparent', color: k.bright, borderRadius: 4, cursor: scanning ? 'default' : 'pointer' }}>
            {scanning ? 'SCANNING…' : 'SCAN'}
          </button>
        )}
      </header>

      <div style={{ overflow: 'auto', flex: 1 }}>
        <div style={{ minWidth: 980 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1.5fr .8fr 1fr .8fr 1fr 1fr 1fr', gap: 10, padding: '6px 10px', borderBottom: `1px solid ${k.border}`, position: 'sticky', top: 0, background: k.bg, zIndex: 1 }}>
            {['MARKET / STATE', 'EDGE', 'ECONOMICS', 'MODE', 'RISK', 'POSITION', 'PROTECTION'].map((x) => <div key={x} style={{ fontSize: 8, color: k.dim, letterSpacing: '0.06em' }}>{x}</div>)}
          </div>

          {rows.map((row) => {
            const selected = row.id === selectedId;
            const decisionColor = tone(row.decision);
            return (
              <React.Fragment key={row.id}>
                <button onClick={() => onSelect?.(row)} style={{ width: '100%', display: 'grid', gridTemplateColumns: '1.5fr .8fr 1fr .8fr 1fr 1fr 1fr', gap: 10, padding: '8px 10px', border: 0, borderBottom: `1px solid ${k.border}`, background: selected ? 'rgba(56,126,209,.08)' : 'transparent', color: k.bright, textAlign: 'left', cursor: 'pointer', fontFamily: 'inherit' }}>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700 }}>{row.instrument}</div>
                    <div style={{ marginTop: 2, fontSize: 8, color: k.dim }}>{row.featureQuality || 'FEATURES READY'}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, fontVariantNumeric: 'tabular-nums' }}>{fmt(row.edgeScore)}</div>
                    <div style={{ fontSize: 8, color: k.dim }}>conf {fmt(row.edgeConfidence, 0)}%</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: row.economicallyEligible === false ? k.red : k.bright }}>{fmtMoney(row.expectedNetValue)}</div>
                    <div style={{ fontSize: 8, color: k.dim }}>gross {fmtMoney(row.expectedGrossValue)} · cost {fmtMoney(row.executionCost)}</div>
                  </div>
                  <div style={{ fontSize: 10, color: k.bright }}>{row.mode || '—'}</div>
                  <div>
                    <div style={{ fontSize: 10 }}>{fmtMoney(row.authorizedRisk)}</div>
                    <div style={{ fontSize: 8, color: k.dim }}>used {fmtMoney(row.consumedRisk)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10 }}>{row.quantity ?? '—'} @ {fmt(row.entryPrice)}</div>
                    <div style={{ fontSize: 8, color: k.dim }}>LTP {fmt(row.ltp)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: row.profitGiveback != null && row.profitGiveback > 0 ? k.amber : k.bright }}>{fmtMoney(row.profitGiveback)}</div>
                    <div style={{ fontSize: 8, color: k.dim }}>peak {fmtMoney(row.peakPnl)} · {row.protectionState || 'idle'}</div>
                    <span style={{ display: 'inline-block', marginTop: 3, padding: '1px 5px', border: `1px solid ${decisionColor}`, color: decisionColor, borderRadius: 3, fontSize: 7, letterSpacing: '.06em' }}>{row.decision}</span>
                  </div>
                </button>
                {selected && <Detail row={row} />}
              </React.Fragment>
            );
          })}

          {!rows.length && <div style={{ padding: 30, textAlign: 'center', color: k.dim, fontSize: 10 }}>NO ADAPTIVE EDGE CANDIDATES</div>}
        </div>
      </div>
    </section>
  );
}
