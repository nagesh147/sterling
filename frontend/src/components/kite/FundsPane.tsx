import React from 'react';
import { c as t } from '../../styles/terminalUI';
import { useKiteMargins } from '../../hooks/useKite';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.bg, borderRadius: 4, marginBottom: 24 },
  row: { display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '12px 0', borderBottom: `1px solid ${t.border}` },
  k: { color: t.dim },
  v: { color: t.bright },
  hint: { color: t.dim, fontSize: 13 },
  btnBlue: { background: '#4184f3', color: '#fff', border: 'none', borderRadius: 4, padding: '8px 24px', fontSize: 13, cursor: 'pointer', fontWeight: 500, transition: 'background 0.2s' },
  btnOutline: { background: 'transparent', color: '#4184f3', border: '1px solid #4184f3', borderRadius: 4, padding: '8px 24px', fontSize: 13, cursor: 'pointer', fontWeight: 500, transition: 'background 0.2s' },
};

const inr = (v: any) => new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v ?? 0));

function SegmentTable({ seg, info }: { seg: string; info: any }) {
  const avail = info?.available || {};
  const used = info?.utilised || {};
  const isEquity = seg.toLowerCase() === 'equity';
  
  return (
    <div style={{ flex: 1, minWidth: 350 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24 }}>
        <div style={{ width: 12, height: 12, borderRadius: '50%', background: isEquity ? '#4184f3' : '#FF5722' }} />
        <h2 style={{ fontSize: 20, fontWeight: 400, color: t.bright, margin: 0 }}>{isEquity ? 'Equity' : 'Commodity'}</h2>
      </div>

      <div style={{ display: 'flex', gap: 24, marginBottom: 32 }}>
        <div style={{ flex: 1, textAlign: 'center', background: t.surface, padding: '24px 16px', borderRadius: 4, border: `1px solid ${t.border}` }}>
          <div style={{ fontSize: 28, color: t.bright, marginBottom: 4 }}>{inr(info?.net)}</div>
          <div style={{ fontSize: 13, color: t.dim }}>Available margin</div>
        </div>
        <div style={{ flex: 1, textAlign: 'center', background: t.surface, padding: '24px 16px', borderRadius: 4, border: `1px solid ${t.border}` }}>
          <div style={{ fontSize: 28, color: t.bright, marginBottom: 4 }}>{inr(used.debits)}</div>
          <div style={{ fontSize: 13, color: t.dim }}>Used margin</div>
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
        <div style={S.row}><span style={S.k}>Collateral (Liquid funds)</span><span style={S.v}>0.00</span></div>
        <div style={S.row}><span style={S.k}>Collateral (Equity)</span><span style={S.v}>{inr(avail.collateral)}</span></div>
        <div style={{ ...S.row, borderBottom: 'none' }}><span style={S.k}>Total collateral</span><span style={S.v}>{inr(avail.collateral)}</span></div>
      </div>
    </div>
  );
}

export function FundsPane() {
  const { data: margins, isLoading, error } = useKiteMargins(true);
  
  const eq = margins?.equity;
  const com = margins?.commodity;

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1000, margin: '0 auto', width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 48 }}>
        <h1 style={{ fontSize: 24, fontWeight: 400, color: t.bright, margin: 0 }}>Funds</h1>
        <div style={{ display: 'flex', gap: 12 }}>
          <button style={S.btnBlue}>Add funds</button>
          <button style={S.btnOutline}>Withdraw</button>
        </div>
      </div>

      {isLoading && <div style={S.hint}>Loading funds...</div>}
      {error && <div style={{ color: t.red }}>Error loading funds: {(error as Error).message}</div>}

      <div style={{ display: 'flex', gap: 64, flexWrap: 'wrap' }}>
        {eq && <SegmentTable seg="Equity" info={eq} />}
        {com && <SegmentTable seg="Commodity" info={com} />}
        {!eq && !com && !isLoading && !error && (
          <div style={S.hint}>No funds data available. Connect a live session.</div>
        )}
      </div>
    </div>
  );
}
