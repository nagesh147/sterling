import React from 'react';
import { useKiteStatus, useKiteMargins, useKiteHoldings } from '../../hooks/useKite';

function formatCurrency(val: number) {
  if (!val) return '0';
  return val.toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

function MarginCard({ title, available, used, opening }: { title: string, available: number, used: number, opening: number }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 32 }}>
        <div style={{ width: 14, height: 14, borderRadius: '50%', border: `1px solid #f1f1f1`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: title === 'Equity' ? '#387ed1' : '#ff5722' }} />
        </div>
        <span style={{ fontSize: 18, color: '#444', fontWeight: 400 }}>{title}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <div style={{ fontSize: 44, fontWeight: 300, color: '#444', lineHeight: 1, marginBottom: 12 }}>{formatCurrency(available)}</div>
          <div style={{ fontSize: 13, color: '#9b9b9b' }}>Margin available</div>
        </div>
        <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', gap: 16, marginTop: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 40 }}>
            <div style={{ fontSize: 13, color: '#9b9b9b' }}>Margins used</div>
            <div style={{ fontSize: 13, color: '#444' }}>{formatCurrency(used)}</div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 40 }}>
            <div style={{ fontSize: 13, color: '#9b9b9b' }}>Opening balance</div>
            <div style={{ fontSize: 13, color: '#444' }}>{formatCurrency(opening)}</div>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 'auto', paddingTop: 8 }}>
        <a href="#" style={{ color: '#387ed1', fontSize: 13, textDecoration: 'none' }}>View statement</a>
      </div>
    </div>
  );
}

export function KiteDashboard() {
  const { data: status } = useKiteStatus();
  const { data: margins } = useKiteMargins(!!status?.connected);
  const { data: holdings } = useKiteHoldings(!!status?.connected);

  const name = status?.user_name ? status.user_name.split(' ')[0] : 'Madaram';
  
  const eq = margins?.equity?.net || 293.2;
  const eqUsed = margins?.equity?.utilised?.debits || 0;
  const eqOpening = margins?.equity?.available?.opening_balance || 293.2;
  
  const com = margins?.commodity?.net || 0;
  const comUsed = margins?.commodity?.utilised?.debits || 0;
  const comOpening = margins?.commodity?.available?.opening_balance || 0;

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '32px 32px 0 32px' }}>
        <h1 style={{ fontSize: 22, fontWeight: 400, color: '#444', marginBottom: 40, marginTop: 0 }}>
        Hi, {name}
      </h1>
      
      {/* Margins Row */}
      <div style={{ display: 'flex', gap: 80, marginBottom: 48 }}>
        <MarginCard title="Equity" available={eq} used={eqUsed} opening={eqOpening} />
        <MarginCard title="Commodity" available={com} used={comUsed} opening={comOpening} />
      </div>
      </div>

      {/* Holdings Section */}
      <div style={{ borderTop: `1px solid #f1f1f1`, borderBottom: `1px solid #f1f1f1`, padding: '48px 0', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'center' }}>
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#9b9b9b" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.6 }}>
              <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
            </svg>
          </div>
          <div style={{ fontSize: 13, color: '#9b9b9b', marginBottom: 24, lineHeight: 1.5 }}>
            You don't have any stocks in your DEMAT yet. Get started<br/>with absolutely free equity investments.
          </div>
          <button style={{ background: '#387ed1', color: '#fff', border: 'none', borderRadius: 3, padding: '10px 24px', fontSize: 14, fontWeight: 500, cursor: 'pointer' }}>
            Start investing
          </button>
        </div>
      </div>

      {/* Overview & Positions Row */}
      <div style={{ display: 'flex', gap: 80, padding: '40px 32px 32px 32px' }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 16, fontWeight: 400, color: '#444', marginBottom: 24, margin: 0 }}>
            Market overview
          </h2>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 8px', border: `1px solid #e0e0e0`, borderRadius: 3, cursor: 'pointer', marginBottom: 16 }}>
            <span style={{ fontSize: 10, color: '#9b9b9b' }}>NIFTY 50</span>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#9b9b9b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
          </div>
          <div style={{ width: '100%' }}>
            <svg width="100%" height="80" viewBox="0 0 400 80" preserveAspectRatio="none">
              <path d="M0,50 L20,45 L40,60 L60,55 L80,60 L100,50 L120,45 L140,40 L160,35 L180,45 L200,40 L220,55 L240,65 L260,55 L280,75 L300,55 L320,65 L340,60 L360,70 L380,65 L400,70" fill="none" stroke="#4184f3" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: `1px solid #f1f1f1`, paddingTop: 8, fontSize: 10, color: '#9b9b9b' }}>
              <span>Jul 25</span>
              <span>Oct 25</span>
              <span>Jan 26</span>
              <span>Apr 26</span>
            </div>
          </div>
        </div>

        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 16, fontWeight: 400, color: '#444', marginBottom: 24, margin: 0 }}>
            Positions (1)
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 40 }}>
            <span style={{ fontSize: 10, color: '#9b9b9b', whiteSpace: 'nowrap' }}>SENSEX 18th JUN 75500 PE (NRML)</span>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', background: '#f1f1f1', height: 6 }}>
              <div style={{ width: '100%', height: 6, background: '#4184f3', borderRadius: 0 }}></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

