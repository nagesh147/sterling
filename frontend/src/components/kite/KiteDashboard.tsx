import React, { useEffect, useRef } from 'react';
import { useKiteStatus, useKiteMargins, useKiteHoldings } from '../../hooks/useKite';
import { createChart, ColorType, AreaSeries } from 'lightweight-charts';
import { useCandles } from '../../hooks/useCandles';
import { InstrumentLabel } from './InstrumentLabel';
import { k } from '../../styles/kiteUI';

function formatCurrency(val: number) {
  if (!val) return '0';
  return val.toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

function MarginCard({ title, available, used, opening, loading }: { title: string, available: number, used: number, opening: number, loading: boolean }) {
  const Icon = title === 'Equity' 
    ? <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9b9b9b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"></path><path d="M22 12A10 10 0 0 0 12 2v10z"></path></svg>
    : <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9b9b9b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"></path></svg>;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 24 }}>
        {Icon}
        <span style={{ fontSize: 14, color: '#444', fontWeight: 500 }}>{title}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ 
            fontSize: '2.625rem', 
            fontWeight: 300, 
            color: loading ? '#ccc' : '#444', 
            lineHeight: 1.3, 
            letterSpacing: 0,
            fontFamily: k.fontFamily,
            marginBottom: 4
          }}>
            {loading ? '—' : formatCurrency(available)}
          </div>
          <div style={{ fontSize: 12, color: '#9b9b9b' }}>Margin available</div>
        </div>
        <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', gap: 12, marginTop: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 40 }}>
            <div style={{ fontSize: 12, color: '#9b9b9b' }}>Margins used</div>
            <div style={{ fontSize: 12, color: loading ? '#ccc' : '#444' }}>{loading ? '—' : formatCurrency(used)}</div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 40 }}>
            <div style={{ fontSize: 12, color: '#9b9b9b' }}>Opening balance</div>
            <div style={{ fontSize: 12, color: loading ? '#ccc' : '#444' }}>{loading ? '—' : formatCurrency(opening)}</div>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 'auto', paddingTop: 8 }}>
        <a href="#" style={{ color: '#387ed1', fontSize: 12, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 6 }}>
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
          View statement
        </a>
      </div>
    </div>
  );
}

function DashboardChart({ symbol }: { symbol: string }) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const { data: candles } = useCandles(symbol, '1H', 500);

  useEffect(() => {
    if (!chartContainerRef.current || !candles || candles.length === 0) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#9b9b9b',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      width: chartContainerRef.current.clientWidth,
      height: 80,
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      handleScroll: false,
      handleScale: false,
    });

    const lineSeries = chart.addSeries(AreaSeries, {
      lineColor: '#4184f3',
      topColor: 'rgba(65, 132, 243, 0.2)',
      bottomColor: 'rgba(65, 132, 243, 0)',
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });

    const formattedData = candles.map(c => ({
      time: c.time as any,
      value: c.close
    }));
    
    // Ensure uniqueness and sorted order
    formattedData.sort((a, b) => a.time - b.time);
    const uniqueData = formattedData.filter((v, i, a) => i === 0 || v.time !== a[i - 1].time);
    
    lineSeries.setData(uniqueData);

    const handleResize = () => {
      chart.applyOptions({ width: chartContainerRef.current?.clientWidth });
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [candles]);

  return <div ref={chartContainerRef} style={{ width: '100%', height: '80px' }} />;
}

export function KiteDashboard() {
  const { data: status } = useKiteStatus();
  const { data: margins } = useKiteMargins(!!status?.connected);
  const { data: holdings } = useKiteHoldings(!!status?.connected);

  const name = status?.user_name ? status.user_name.split(' ')[0] : 'Madaram';
  
  const eq = margins?.equity?.net ?? 0;
  const eqUsed = margins?.equity?.utilised?.debits ?? 0;
  const eqOpening = margins?.equity?.available?.opening_balance ?? 0;
  
  const com = margins?.commodity?.net ?? 0;
  const comUsed = margins?.commodity?.utilised?.debits ?? 0;
  const comOpening = margins?.commodity?.available?.opening_balance ?? 0;
  
  const marginsLoading = !margins;

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '32px 32px 0 32px' }}>
        <h1 style={{ fontSize: 20, fontWeight: 400, color: '#444', marginBottom: 24, marginTop: 0 }}>
        Hi, {name}
      </h1>
      
      {/* Margins Row */}
      <div style={{ display: 'flex', marginBottom: 48 }}>
        <div style={{ flex: 1, paddingRight: 40, borderRight: '1px solid #e0e0e0' }}>
          <MarginCard title="Equity" available={eq} used={eqUsed} opening={eqOpening} loading={marginsLoading} />
        </div>
        <div style={{ flex: 1, paddingLeft: 40 }}>
          <MarginCard title="Commodity" available={com} used={comUsed} opening={comOpening} loading={marginsLoading} />
        </div>
      </div>
      </div>

      {/* Holdings Section */}
      <div style={{ borderTop: `1px solid #e0e0e0`, borderBottom: `1px solid #e0e0e0`, padding: '48px 0', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
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
      <div style={{ display: 'flex', padding: '40px 32px 32px 32px' }}>
        <div style={{ flex: 1, paddingRight: 40 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 24 }}>
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9b9b9b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline><polyline points="16 7 22 7 22 13"></polyline></svg>
            <h2 style={{ fontSize: 14, fontWeight: 500, color: '#444', margin: 0 }}>
              Market overview
            </h2>
          </div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 8px', border: `1px solid #e0e0e0`, borderRadius: 3, cursor: 'pointer', marginBottom: 16 }}>
            <span style={{ fontSize: 10, color: '#9b9b9b' }}>NIFTY 50</span>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#9b9b9b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
          </div>
          <div style={{ width: '100%' }}>
            <DashboardChart symbol="NSE:NIFTY 50" />
            <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: `1px solid #e0e0e0`, paddingTop: 8, fontSize: 10, color: '#9b9b9b' }}>
              <span>Jul 25</span>
              <span>Oct 25</span>
              <span>Jan 26</span>
              <span>Apr 26</span>
            </div>
          </div>
        </div>

        <div style={{ flex: 1, paddingLeft: 40 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 24 }}>
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9b9b9b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            <h2 style={{ fontSize: 14, fontWeight: 500, color: '#444', margin: 0 }}>
              Positions (1)
            </h2>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 40 }}>
            <span style={{ fontSize: 10, color: '#9b9b9b', whiteSpace: 'nowrap' }}>
              <InstrumentLabel symbol="SENSEX2461875500CE" fallback="SENSEX 18th w JUN 75500 PE" /> (NRML)
            </span>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', background: '#f1f1f1', height: 6 }}>
              <div style={{ width: '100%', height: 6, background: '#4184f3', borderRadius: 0 }}></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

