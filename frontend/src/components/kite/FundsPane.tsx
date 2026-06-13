import React from 'react';
import { useKiteMargins } from '../../hooks/useKite';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#fff', borderRadius: 4, marginBottom: 24 },
  row: { display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '12px 0', borderBottom: `1px solid #f1f1f1` },
  k: { color: '#9b9b9b' },
  v: { color: '#444' },
  hint: { color: '#9b9b9b', fontSize: 13 },
  btnGreen: { background: '#4caf50', color: '#fff', border: 'none', borderRadius: 4, padding: '8px 24px', fontSize: 13, cursor: 'pointer', fontWeight: 500, transition: 'background 0.2s' },
  btnBlue: { background: '#387ed1', color: '#fff', border: 'none', borderRadius: 4, padding: '8px 24px', fontSize: 13, cursor: 'pointer', fontWeight: 500, transition: 'background 0.2s' },
};

const inr = (v: any) => new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v ?? 0));

function SegmentTable({ seg, info }: { seg: string; info: any }) {
  const avail = info?.available || {};
  const used = info?.utilised || {};
  const isEquity = seg.toLowerCase() === 'equity';
  
  return (
    <div style={{ flex: 1, minWidth: 400, maxWidth: 500 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 32 }}>
        <div style={{ width: 14, height: 14, borderRadius: '50%', background: isEquity ? '#387ed1' : '#ff5722' }} />
        <h2 style={{ fontSize: 20, fontWeight: 400, color: '#444', margin: 0 }}>{isEquity ? 'Equity' : 'Commodity'}</h2>
      </div>

      <div style={{ display: 'flex', gap: 64, marginBottom: 40 }}>
        <div>
          <div style={{ fontSize: 42, color: (info?.net ?? 0) >= 0 ? '#387ed1' : '#df514c', marginBottom: 8, fontWeight: 400 }}>{inr(info?.net)}</div>
          <div style={{ fontSize: 13, color: '#9b9b9b' }}>Available margin</div>
        </div>
        <div>
          <div style={{ fontSize: 42, color: '#444', marginBottom: 8, fontWeight: 400 }}>{inr(used.debits)}</div>
          <div style={{ fontSize: 13, color: '#9b9b9b' }}>Used margin</div>
        </div>
      </div>

      <div>
        <div style={S.row}><span style={S.k}>Available cash</span><span style={S.v}>{inr(avail.live_balance ?? avail.cash)}</span></div>
        <div style={S.row}><span style={S.k}>Opening balance</span><span style={S.v}>{inr(avail.opening_balance)}</span></div>
        <div style={S.row}><span style={S.k}>Payin</span><span style={S.v}>{inr(avail.intraday_payin)}</span></div>
        <div style={S.row}><span style={S.k}>Payout</span><span style={S.v}>{inr(used.payout)}</span></div>
        <div style={S.row}><span style={S.k}>SPAN</span><span style={S.v}>{inr(used.span)}</span></div>
        <div style={S.row}><span style={S.k}>Delivery margin</span><span style={S.v}>{inr(used.delivery)}</span></div>
        <div style={S.row}><span style={S.k}>Exposure</span><span style={S.v}>{inr(used.exposure)}</span></div>
        <div style={S.row}><span style={S.k}>Options premium</span><span style={S.v}>{inr(used.option_premium)}</span></div>
        <div style={S.row}><span style={S.k}>Collateral (Liquid funds)</span><span style={S.v}>{inr(used.liquid_collateral || 0)}</span></div>
        <div style={S.row}><span style={S.k}>Collateral (Equity)</span><span style={S.v}>{inr(avail.collateral)}</span></div>
        <div style={{ ...S.row, borderBottom: 'none' }}><span style={S.k}>Total collateral</span><span style={S.v}>{inr(avail.collateral + (used.liquid_collateral || 0))}</span></div>
      </div>
    </div>
  );
}

export function FundsPane() {
  const { data: margins, isLoading, error } = useKiteMargins(true);
  
  const eq = margins?.equity;
  const com = margins?.commodity;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff', color: '#444', fontFamily: 'inherit' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid #f1f1f1`, padding: '0 32px 24px 32px', marginTop: 12 }}>
        <h1 style={{ fontSize: 24, fontWeight: 400, color: '#444', margin: 0 }}>Funds</h1>
        <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
          <span style={{ fontSize: 13, color: '#9b9b9b', letterSpacing: 0.3 }}>Instant, zero-cost fund transfers with UPI</span>
          <button style={S.btnGreen}>Add funds</button>
          <button style={S.btnBlue}>Withdraw</button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>
      {isLoading && <div style={S.hint}>Loading funds...</div>}
      {error && <div style={{ color: '#df514c' }}>Error loading funds: {(error as Error).message}</div>}

      <div style={{ display: 'flex', gap: 80, flexWrap: 'wrap' }}>
        <SegmentTable seg="Equity" info={eq || {}} />
        <SegmentTable seg="Commodity" info={com || {}} />
      </div>
      </div>
    </div>
  );
}
