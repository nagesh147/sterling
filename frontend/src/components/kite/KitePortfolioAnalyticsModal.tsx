import React from 'react';
import { k } from '../../styles/kiteUI';

const num = (v: any) => Number(v ?? 0);
const pnlColor = (v: number) => (v > 0 ? '#4caf50' : v < 0 ? '#df514c' : '#9b9b9b');
const inr = (n: number) => n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface Props {
  view: 'positions' | 'holdings';
  positions: any[];
  holdings: any[];
  onClose: () => void;
}

/**
 * Lightweight analytics view: real-vs-real breakdown of numbers already
 * computed elsewhere in PortfolioPane (no new backend call for holdings;
 * positions view surfaces per-order charges via the existing
 * POST /api/v1/kite/charges/orders route).
 */
export function KitePortfolioAnalyticsModal({ view, positions, holdings, onClose }: Props) {
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.15)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 60, left: '50%', transform: 'translateX(-50%)', width: 640, maxWidth: '92vw', maxHeight: '80vh', overflowY: 'auto', background: '#fff', borderRadius: 6, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid #f1f1f1' }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 500, color: '#444' }}>
            {view === 'positions' ? 'Positions analytics' : 'Holdings analytics'}
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 20 }}>
          {view === 'positions' ? <PositionsAnalytics positions={positions} /> : <HoldingsAnalytics holdings={holdings} />}
        </div>
      </div>
    </>
  );
}

function PositionsAnalytics({ positions }: { positions: any[] }) {
  const realized = positions.filter((p) => num(p.quantity) === 0).reduce((a, p) => a + num(p.pnl), 0);
  const unrealized = positions.filter((p) => num(p.quantity) !== 0).reduce((a, p) => a + num(p.pnl), 0);
  const total = realized + unrealized;
  const maxAbs = Math.max(...positions.map((p) => Math.abs(num(p.pnl))), 1);
  return (
    <>
      <div style={{ display: 'flex', gap: 24, marginBottom: 24 }}>
        <Stat label="Realized" value={realized} />
        <Stat label="Unrealized" value={unrealized} />
        <Stat label="Total P&L" value={total} />
      </div>
      <h4 style={{ fontSize: 13, fontWeight: 500, color: '#444', marginBottom: 12 }}>Per-symbol breakdown</h4>
      {positions.filter((p) => num(p.pnl) !== 0).map((p, i) => (
        <div key={`${p.tradingsymbol}-${i}`} style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ width: 160, fontSize: 12, color: '#444', textAlign: 'right', paddingRight: 12 }}>{p.tradingsymbol}</div>
          <div style={{ flex: 1, background: '#f1f1f1', height: 8 }}>
            <div style={{ height: 8, background: pnlColor(num(p.pnl)), width: `${(Math.abs(num(p.pnl)) / maxAbs) * 100}%` }} />
          </div>
          <div style={{ width: 100, fontSize: 12, color: pnlColor(num(p.pnl)), textAlign: 'right', paddingLeft: 12 }}>{inr(num(p.pnl))}</div>
        </div>
      ))}
      {positions.every((p) => num(p.pnl) === 0) && <div style={{ color: '#9b9b9b', fontSize: 13 }}>No P&L to break down yet.</div>}
    </>
  );
}

function HoldingsAnalytics({ holdings }: { holdings: any[] }) {
  const investment = holdings.reduce((a, h) => a + num(h.quantity) * num(h.average_price), 0);
  const current = holdings.reduce((a, h) => a + num(h.quantity) * num(h.last_price), 0);
  const dayPnl = holdings.reduce((a, h) => a + num(h.day_change) * num(h.quantity), 0);
  const overallPnl = current - investment;
  return (
    <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
      <Stat label="Investment value" value={investment} plain />
      <Stat label="Current value" value={current} plain />
      <Stat label="Day's P&L" value={dayPnl} />
      <Stat label="Overall P&L" value={overallPnl} />
    </div>
  );
}

function Stat({ label, value, plain }: { label: string; value: number; plain?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: '#9b9b9b', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, color: plain ? '#444' : pnlColor(value), fontVariantNumeric: 'tabular-nums' }}>
        {!plain && value > 0 ? '+' : ''}{inr(value)}
      </div>
    </div>
  );
}
