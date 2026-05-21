import React from 'react';
import { useV4Analytics } from '../hooks/useV4Analytics';
import { useSterlingStream } from '../hooks/useSterlingStream';
import { useAppStream } from '../hooks/useAppStream';
import type { LivePnlResponse } from '../hooks/useLivePnl';

interface V4AnalyticsDashboardProps {
  activeSymbol: string;
}

export const V4AnalyticsDashboard: React.FC<V4AnalyticsDashboardProps> = ({ activeSymbol }) => {
  // Format the symbol to match the backend broadcasting format (e.g. BTCUSD)
  const streamSymbol = activeSymbol.includes('USD') ? activeSymbol : `${activeSymbol}USD`;
  
  // Fetch REST data
  const { data: restData, isLoading } = useV4Analytics(streamSymbol);
  
  // Fetch live WebSocket data (OFI, etc.)
  const { status, metrics } = useSterlingStream(streamSymbol);

  // Fetch real PnL from shared SSE stream (same source as PortfolioSummary)
  const { data: pnlData } = useAppStream<LivePnlResponse>('pnl');
  const unrealizedPnl = React.useMemo(() => {
    if (!pnlData?.positions) return 0;
    const matching = pnlData.positions.filter(p =>
      p.underlying.toUpperCase() === streamSymbol.toUpperCase()
    );
    if (matching.length === 0) return pnlData.total_estimated_pnl_usd;
    return matching.reduce((sum, p) => sum + (p.estimated_pnl_usd ?? 0), 0);
  }, [pnlData, streamSymbol]);

  // Merge REST data with Live data over the top
  const mergedData = {
    ...restData,
    ofi: metrics.ofi !== 0 ? metrics.ofi : (restData?.ofi || 0),
    unrealized_pnl: unrealizedPnl,
    drift_bps: metrics.drift_bps !== 0 ? metrics.drift_bps : (restData?.drift_bps || 0),
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return '#10b981'; // emerald-500
      case 'reconnecting': return '#f59e0b'; // amber-500
      case 'disconnected': return '#ef4444'; // red-500
      default: return '#6b7280'; // gray-500
    }
  };

  const isOFIThresholdBreached = mergedData.ofi < -5000 || mergedData.ofi > 5000;
  
  const getOFIColor = (ofi: number) => {
    if (ofi < -5000) return '#ef4444'; // red
    if (ofi > 5000) return '#10b981';  // green
    return 'var(--text-primary, #f3f4f6)';
  };

  return (
    <div style={{
      padding: '16px 20px',
      background: 'var(--bg-surface, rgba(20, 20, 30, 0.4))',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      borderRadius: '12px',
      border: '1px solid var(--border, rgba(255, 255, 255, 0.08))',
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
      color: 'var(--text-primary, #fff)',
      position: 'relative',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ 
          fontSize: '14px', 
          fontWeight: 700, 
          margin: 0, 
          letterSpacing: '0.05em',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 3v18h18" />
            <path d="m19 9-5 5-4-4-3 3" />
          </svg>
          V4 ANALYTICS
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 10px',
            background: 'rgba(0, 0, 0, 0.2)',
            borderRadius: '999px',
            border: '1px solid rgba(255, 255, 255, 0.05)'
          }}>
            <div style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: getStatusColor(status),
              boxShadow: `0 0 8px ${getStatusColor(status)}`
            }} />
            <span style={{
              fontSize: '10px',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: 'var(--text-muted, #9ca3af)'
            }}>
              SHADOW TRADING
            </span>
          </div>
        </div>
      </div>

      {isLoading && !restData ? (
        <div style={{
          height: '60px',
          background: 'rgba(255, 255, 255, 0.02)',
          borderRadius: '8px',
          animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
        }} />
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
          {/* OFI Metric Card */}
          <div style={{
            position: 'relative',
            padding: '16px',
            background: 'rgba(0, 0, 0, 0.15)',
            borderRadius: '10px',
            border: '1px solid rgba(255, 255, 255, 0.04)',
            overflow: 'hidden',
            transition: 'transform 0.2s ease, box-shadow 0.2s ease',
            cursor: 'default',
          }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim, #6b7280)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Live Market Pressure
            </div>
            <div style={{
              fontSize: '24px',
              fontWeight: 800,
              color: getOFIColor(mergedData.ofi),
              fontFamily: 'JetBrains Mono, monospace',
              textShadow: isOFIThresholdBreached ? `0 0 12px ${getOFIColor(mergedData.ofi)}40` : 'none',
              transition: 'color 0.3s ease, text-shadow 0.3s ease'
            }}>
              {mergedData.ofi > 0 ? '+' : ''}{mergedData.ofi.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </div>
            
            {/* Veto Active Badge */}
            {isOFIThresholdBreached ? (
              <div style={{
                position: 'absolute',
                top: '12px',
                right: '12px',
                padding: '2px 6px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#ef4444',
                fontSize: '9px',
                fontWeight: 800,
                textTransform: 'uppercase',
                borderRadius: '4px',
                animation: 'pulse 1.5s infinite',
                boxShadow: '0 0 8px rgba(239, 68, 68, 0.4)'
              }}>
                TRADE OFF
              </div>
            ) : (
              <div style={{
                position: 'absolute',
                top: '12px',
                right: '12px',
                padding: '2px 6px',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                color: '#10b981',
                fontSize: '9px',
                fontWeight: 800,
                textTransform: 'uppercase',
                borderRadius: '4px',
              }}>
                TRADE ON
              </div>
            )}
            
            {/* Background Gradient Effect */}
            {isOFIThresholdBreached && (
              <div style={{
                position: 'absolute',
                top: 0, left: 0, right: 0, bottom: 0,
                background: `linear-gradient(45deg, transparent, ${getOFIColor(mergedData.ofi)}08)`,
                pointerEvents: 'none'
              }} />
            )}
          </div>

          {/* Unrealized PnL Card */}
          <div style={{
            padding: '16px',
            background: 'rgba(0, 0, 0, 0.15)',
            borderRadius: '10px',
            border: '1px solid rgba(255, 255, 255, 0.04)',
          }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim, #6b7280)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Open Profit/Loss
            </div>
            <div style={{
              fontSize: '24px',
              fontWeight: 800,
              color: mergedData.unrealized_pnl >= 0 ? '#10b981' : '#ef4444',
              fontFamily: 'JetBrains Mono, monospace'
            }}>
              {mergedData.unrealized_pnl >= 0 ? '+' : ''}${mergedData.unrealized_pnl.toFixed(2)}
            </div>
          </div>

          {/* Drift Card */}
          <div style={{
            padding: '16px',
            background: 'rgba(0, 0, 0, 0.15)',
            borderRadius: '10px',
            border: '1px solid rgba(255, 255, 255, 0.04)',
          }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim, #6b7280)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Execution Slippage
            </div>
            <div style={{
              fontSize: '24px',
              fontWeight: 800,
              color: 'var(--text-primary, #f3f4f6)',
              fontFamily: 'JetBrains Mono, monospace'
            }}>
              {mergedData.drift_bps > 0 ? '+' : ''}{mergedData.drift_bps.toFixed(2)} <span style={{ fontSize: '14px', color: 'var(--text-dim, #6b7280)', fontWeight: 600 }}>bps</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
