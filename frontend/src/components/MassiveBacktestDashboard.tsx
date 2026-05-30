import React, { useState, useEffect, useRef } from 'react';
import { createChart, IChartApi, ColorType, LineSeries } from 'lightweight-charts';

export function MassiveBacktestDashboard({ underlying }: { underlying: string }) {
  const [tf, setTf] = useState('1m');
  const [strategy, setStrategy] = useState('Sterling: Mean Reversion (RSI)');
  const [profile, setProfile] = useState('Aggressive');
  const [capital, setCapital] = useState(500);
  
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState('');

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const strategies = [
    { id: 'mean_reversion', name: 'Sterling: Mean Reversion (RSI)' },
    { id: 'ma_crossover', name: 'Sterling: MA Crossover (9/21)' },
    { id: 'breakout', name: 'Sterling: 20-Period Breakout' },
    { id: 'price_action', name: 'Sterling: Price Action (Engulfing)' },
    { id: 'smc', name: 'Sterling: Smart Money Concepts (FVG)' },
    { id: 'supertrend', name: 'Community: SuperTrend Scalp' },
    { id: 'bollinger', name: 'Community: Bollinger Bands Breakout' },
    { id: 'ict', name: 'Community: ICT Silver Bullet' },
    { id: 'supply_demand', name: 'Community: 1H Supply/Demand' },
  ];

  const timeframes = ['1m', '5m', '15m', '30m', '45m', '1h', '2h', '4h'];
  const profiles = ['Intraday', 'Scalping', 'Aggressive'];

  const runBacktest = async () => {
    setLoading(true);
    setError('');
    setResults(null);
    try {
      const activeStrategy = strategies.find(s => s.name === strategy)?.id || 'mean_reversion';
      const res = await fetch('/api/v1/vectorized/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: underlying,
          timeframe: tf,
          strategy: activeStrategy,
          profile: profile,
          starting_capital: Number(capital)
        })
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || 'Failed to run backtest');
      }
      const data = await res.json();
      setResults(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!results || !chartContainerRef.current) return;
    
    if (chartRef.current) {
      chartRef.current.remove();
    }

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'var(--text-dim)',
      },
      grid: { vertLines: { color: 'var(--border)' }, horzLines: { color: 'var(--border)' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true },
      width: chartContainerRef.current.clientWidth,
      height: 300,
    });
    chartRef.current = chart;

    const ro = new ResizeObserver(() => {
      if (chartContainerRef.current) chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    });
    ro.observe(chartContainerRef.current);

    const series = chart.addSeries(LineSeries, {
      color: 'var(--accent)',
      lineWidth: 2,
    });
    
    if (results.equity_curve && results.equity_curve.length > 0) {
      // Map equity curve for lightweight-charts: it needs a valid Unix timestamp
      const chartData = results.equity_curve.map((p: any, i: number) => {
        // Mocking a sequential timestamp based on current time (just for visualization as the backend doesn't seem to pass real timestamps right now)
        const timestamp = Math.floor(Date.now() / 1000) - ((results.equity_curve.length - i) * 60);
        return {
          time: timestamp as any,
          value: p.value,
        };
      });
      series.setData(chartData);
      chart.timeScale().fitContent();
    }

    return () => { ro.disconnect(); chart.remove(); chartRef.current = null; };
  }, [results]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Controls */}
      <div style={{ 
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12,
        background: 'var(--bg-surface)', padding: 16, borderRadius: 8, border: '1px solid var(--border)' 
      }}>
        <div>
          <label style={{ display: 'block', fontSize: 10, color: 'var(--text-faint)', marginBottom: 4 }}>SYMBOL</label>
          <div style={{ padding: '6px 12px', background: 'var(--bg-base)', borderRadius: 4, fontSize: 13, border: '1px solid var(--border)' }}>
            {underlying}
          </div>
        </div>
        
        <div>
          <label style={{ display: 'block', fontSize: 10, color: 'var(--text-faint)', marginBottom: 4 }}>TIMEFRAME</label>
          <select value={tf} onChange={e => setTf(e.target.value)} style={{ width: '100%', padding: '6px 12px', background: 'var(--bg-base)', borderRadius: 4, color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
            {timeframes.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: 10, color: 'var(--text-faint)', marginBottom: 4 }}>STRATEGY</label>
          <select value={strategy} onChange={e => setStrategy(e.target.value)} style={{ width: '100%', padding: '6px 12px', background: 'var(--bg-base)', borderRadius: 4, color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
            {strategies.map((s, i) => <option key={i} value={s.name}>{s.name}</option>)}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: 10, color: 'var(--text-faint)', marginBottom: 4 }}>PROFILE</label>
          <select value={profile} onChange={e => setProfile(e.target.value)} style={{ width: '100%', padding: '6px 12px', background: 'var(--bg-base)', borderRadius: 4, color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
            {profiles.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        
        <div>
          <label style={{ display: 'block', fontSize: 10, color: 'var(--text-faint)', marginBottom: 4 }}>CAPITAL ($)</label>
          <input type="number" value={capital} onChange={e => setCapital(Number(e.target.value))} style={{ width: '100%', padding: '6px 12px', background: 'var(--bg-base)', borderRadius: 4, color: 'var(--text-primary)', border: '1px solid var(--border)' }} />
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button 
            onClick={runBacktest} 
            disabled={loading}
            style={{ 
              width: '100%', padding: '8px', background: 'var(--accent)', color: '#fff', 
              border: 'none', borderRadius: 4, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1
            }}
          >
            {loading ? 'COMPILING...' : 'RUN VECTOR BACKTEST'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: 12, background: 'var(--danger)22', color: 'var(--danger)', borderRadius: 8, border: '1px solid var(--danger)' }}>
          {error}
        </div>
      )}

      {/* Results */}
      {results && (
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {/* Metrics Card */}
          <div style={{ flex: '1 1 300px', background: 'var(--bg-surface)', padding: 16, borderRadius: 8, border: '1px solid var(--border)' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: 14, color: 'var(--text-muted)' }}>PERFORMANCE METRICS</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-dim)' }}>Net Profit</span>
                <span style={{ fontWeight: 600, color: results.metrics["End Capital"] > capital ? 'var(--accent)' : 'var(--danger)' }}>
                  ${(results.metrics["End Capital"] - capital).toFixed(2)}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-dim)' }}>Win Rate</span>
                <span style={{ fontWeight: 600 }}>{(results.metrics["Win Rate"] * 100).toFixed(1)}%</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-dim)' }}>Profit Factor</span>
                <span style={{ fontWeight: 600 }}>{results.metrics["PF"].toFixed(2)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-dim)' }}>Sharpe Ratio</span>
                <span style={{ fontWeight: 600 }}>{results.metrics["Sharpe"].toFixed(2)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-dim)' }}>Total Trades</span>
                <span style={{ fontWeight: 600 }}>{results.metrics["Trades"].toLocaleString()}</span>
              </div>
            </div>
            
            <div style={{ marginTop: 24, paddingTop: 12, borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-faint)' }}>
              Computed 5 years of historical data in {results.time_taken.toFixed(3)}s.
            </div>
          </div>

          {/* Equity Curve Chart */}
          <div style={{ flex: '2 1 500px', background: 'var(--bg-surface)', padding: 16, borderRadius: 8, border: '1px solid var(--border)', height: 332 }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: 14, color: 'var(--text-muted)' }}>EQUITY CURVE</h3>
            <div ref={chartContainerRef} style={{ width: '100%', height: 300 }} />
          </div>
        </div>
      )}
    </div>
  );
}
