import React from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import { useKiteStatus, useKiteMargins, useKiteHoldings } from '../../hooks/useKite';

function formatCurrency(val: number) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(val || 0);
}

function MarginCard({ title, available, used, opening }: { title: string, available: number, used: number, opening: number }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 32 }}>
        <div style={{ width: 14, height: 14, borderRadius: '50%', border: `1px solid ${tint(t.border, 20)}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: title === 'Equity' ? '#4184f3' : '#FF5722' }} />
        </div>
        <span style={{ fontSize: 20, color: t.bright }}>{title}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <div style={{ fontSize: 40, fontWeight: 300, color: t.bright, lineHeight: 1.1, marginBottom: 8 }}>{formatCurrency(available).replace('₹', '')}</div>
          <div style={{ fontSize: 13, color: t.dim }}>Margin available</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 15, color: t.bright, marginBottom: 4 }}>{formatCurrency(used).replace('₹', '')}</div>
          <div style={{ fontSize: 12, color: t.dim }}>Margins used</div>
          
          <div style={{ fontSize: 15, color: t.bright, marginBottom: 4, marginTop: 24 }}>{formatCurrency(opening).replace('₹', '')}</div>
          <div style={{ fontSize: 12, color: t.dim }}>Opening balance</div>
        </div>
      </div>

      <div style={{ marginTop: 'auto', paddingTop: 16, borderTop: `1px solid ${tint(t.border, 20)}` }}>
        <a href="#" style={{ color: '#4184f3', fontSize: 13, textDecoration: 'none' }}>View statement</a>
      </div>
    </div>
  );
}

export function KiteDashboard() {
  const { data: status } = useKiteStatus();
  const { data: margins } = useKiteMargins(!!status?.connected);
  const { data: holdings } = useKiteHoldings(!!status?.connected);

  const name = status?.user_name ? status.user_name.split(' ')[0] : 'Guest';
  
  const eq = margins?.equity?.net || 0;
  const eqUsed = margins?.equity?.utilised?.debits || 0;
  const eqOpening = margins?.equity?.available?.opening_balance || 0;
  
  const com = margins?.commodity?.net || 0;
  const comUsed = margins?.commodity?.utilised?.debits || 0;
  const comOpening = margins?.commodity?.available?.opening_balance || 0;

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', width: '100%', padding: '24px 32px' }}>
      <h1 style={{ fontSize: 28, fontWeight: 400, color: t.bright, marginBottom: 48 }}>
        Hi, {name}
      </h1>
      
      {/* Margins Row */}
      <div style={{ display: 'flex', gap: 80, marginBottom: 64 }}>
        <MarginCard title="Equity" available={eq} used={eqUsed} opening={eqOpening} />
        <MarginCard title="Commodity" available={com} used={comUsed} opening={comOpening} />
      </div>

      <div style={{ borderTop: `1px solid ${tint(t.border, 20)}`, paddingTop: 48, display: 'flex', gap: 80 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <h2 style={{ fontSize: 16, fontWeight: 400, color: t.bright, margin: 0 }}>
              Holdings ({holdings?.length || 0})
            </h2>
            <a href="#" style={{ color: '#4184f3', fontSize: 13, textDecoration: 'none' }}>View all</a>
          </div>
          
          {(!holdings || holdings.length === 0) ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '64px 0' }}>
              <div style={{ color: t.dim, marginBottom: 24 }}>
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.3 }}>
                  <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
                  <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
                </svg>
              </div>
              <div style={{ fontSize: 14, color: t.dim }}>
                You don't have any stocks in your DEMAT account...
              </div>
            </div>
          ) : (
            <div style={{ fontSize: 14, color: t.dim, padding: '24px 0' }}>
              You have {holdings.length} holdings. 
              <div style={{ marginTop: 16 }}>
                Total P&L: <span style={{ color: t.green, fontWeight: 500 }}>+₹{(holdings.reduce((a: number, b: any) => a + Number(b.pnl || 0), 0)).toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>

        <div style={{ width: 1, background: tint(t.border, 20) }} />

        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 16, fontWeight: 400, color: t.bright, marginBottom: 24, margin: 0 }}>
            Market overview
          </h2>
          <div style={{ paddingTop: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 14, color: t.bright, fontWeight: 500 }}>NIFTY 50</span>
              <span style={{ fontSize: 14, color: t.green }}>+120.45 <span style={{ fontSize: 12 }}>(0.54%)</span></span>
            </div>
            <div style={{ height: 4, background: t.border, borderRadius: 2, overflow: 'hidden', marginBottom: 32 }}>
              <div style={{ width: '60%', height: '100%', background: t.green }} />
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 14, color: t.bright, fontWeight: 500 }}>SENSEX</span>
              <span style={{ fontSize: 14, color: t.green }}>+340.10 <span style={{ fontSize: 12 }}>(0.48%)</span></span>
            </div>
            <div style={{ height: 4, background: t.border, borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ width: '55%', height: '100%', background: t.green }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
