import React from 'react';
import { useWfoState, useWfoLogs, useRunWfo } from '../hooks/useWfo';
import { c, gridStyle, tint } from '../styles/terminalUI';

const S: Record<string, React.CSSProperties> = {
  card: { background: c.surface, border: `1px solid ${c.border}`, borderRadius: 6, padding: 16, marginBottom: 16, flex: 1, display: 'flex', flexDirection: 'column' as const },
  title: { color: c.dim, fontSize: 11, fontWeight: 700, letterSpacing: 2, marginBottom: 12 },
  row: { display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' as const },
  btn: { background: tint(c.blue, 14), color: c.blue, border: `1px solid ${c.blue}`, padding: '6px 14px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12 },
  statCard: { background: c.bg, border: `1px solid ${c.border}`, borderRadius: 4, padding: 10 },
  statLabel: { color: c.dim, fontSize: 10, letterSpacing: 1, marginBottom: 4 },
  statVal: { fontSize: 16, fontWeight: 700, color: c.bright },
  grid4: { ...gridStyle(110, 8), marginBottom: 16 },
  logContainer: { background: c.bg, border: `1px solid ${c.border}`, borderRadius: 4, padding: 12, height: 180, overflowY: 'auto', fontFamily: 'monospace', fontSize: 10, color: c.text, whiteSpace: 'pre-wrap' },
  sectionHeader: { color: c.dim, fontSize: 10, letterSpacing: 1, marginBottom: 8, marginTop: 8 },
  verdict: { background: tint(c.amber, 10), border: `1px solid ${c.amber}`, color: c.amber, padding: 12, borderRadius: 4, fontSize: 12, lineHeight: 1.5, marginBottom: 12 },
};

function badge(color: string): React.CSSProperties {
  return { background: tint(color), color, border: `1px solid ${tint(color, 40)}`, borderRadius: 3, padding: '2px 10px', fontSize: 12, fontWeight: 700 };
}

export function WFOImpactPanel() {
  const { data: state, isLoading } = useWfoState();
  const { data: logsData } = useWfoLogs(50);
  const { mutate: runWfo, isPending } = useRunWfo();

  const impact = state?.impact;
  
  // Format dates securely
  let lastUpdated = "—";
  if (impact?.last_updated) {
    try {
      lastUpdated = new Date(impact.last_updated).toLocaleString();
    } catch(e) {}
  }

  return (
    <div style={S.card}>
      <div style={S.title}>WALK-FORWARD OPTIMIZATION ENGINE</div>
      
      <div style={S.row}>
        <button 
          style={S.btn} 
          disabled={isPending}
          onClick={() => runWfo()}
        >
          {isPending ? 'Launching...' : 'Run Full WFO Matrix'}
        </button>
        <span style={{ color: c.dim, fontSize: 11 }}>
          Evaluates 135 Strategy × Asset × Timeframe combinations
        </span>
      </div>

      {impact && impact.whitelisted ? (
        <>
          <div style={S.verdict}>
            <strong>💡 ORCHESTRATION VERDICT</strong><br/>
            The AI Gatekeeper improved the Global Profit Factor by <strong>+{(impact.improvement_pf || 0).toFixed(2)}</strong>.<br/>
            It successfully blocked <strong>{impact.blocked_toxic_trades || 0}</strong> toxic, negative-expectancy trades from executing.
          </div>

          <div style={S.sectionHeader}>UNFILTERED (Brute-Force Retail Approach)</div>
          <div style={S.grid4}>
            <div style={S.statCard}>
              <div style={S.statLabel}>Trades Taken</div>
              <div style={S.statVal}>{impact.unfiltered.trades}</div>
            </div>
            <div style={S.statCard}>
              <div style={S.statLabel}>Profit Factor</div>
              <div style={S.statVal}>{impact.unfiltered.profit_factor.toFixed(2)}</div>
            </div>
            <div style={S.statCard}>
              <div style={S.statLabel}>Expectancy</div>
              <div style={S.statVal}>{impact.unfiltered.expectancy > 0 ? '+' : ''}{impact.unfiltered.expectancy.toFixed(2)}R</div>
            </div>
            <div style={S.statCard}>
              <div style={S.statLabel}>Win Rate</div>
              <div style={S.statVal}>{impact.unfiltered.win_rate.toFixed(1)}%</div>
            </div>
          </div>

          <div style={S.sectionHeader}>WHITELISTED (Institutional AI Gated)</div>
          <div style={S.grid4}>
            <div style={{ ...S.statCard, border: `1px solid ${c.blue}` }}>
              <div style={S.statLabel}>Trades Taken</div>
              <div style={{ ...S.statVal, color: c.blue }}>{impact.whitelisted.trades}</div>
            </div>
            <div style={{ ...S.statCard, border: `1px solid ${c.green}` }}>
              <div style={S.statLabel}>Profit Factor</div>
              <div style={{ ...S.statVal, color: c.green }}>{impact.whitelisted.profit_factor.toFixed(2)}</div>
            </div>
            <div style={{ ...S.statCard, border: `1px solid ${c.green}` }}>
              <div style={S.statLabel}>Expectancy</div>
              <div style={{ ...S.statVal, color: c.green }}>{impact.whitelisted.expectancy > 0 ? '+' : ''}{impact.whitelisted.expectancy.toFixed(2)}R</div>
            </div>
            <div style={{ ...S.statCard, border: `1px solid ${c.blue}` }}>
              <div style={S.statLabel}>Win Rate</div>
              <div style={{ ...S.statVal, color: c.blue }}>{impact.whitelisted.win_rate.toFixed(1)}%</div>
            </div>
          </div>
          
          <div style={{ color: c.dim, fontSize: 10, textAlign: 'right' }}>
            Last Optimized: {lastUpdated}
          </div>
        </>
      ) : (
        <div style={{ padding: 20, textAlign: 'center', color: c.dim, fontSize: 12 }}>
          {isLoading ? "Loading optimization state..." : "No impact report found. Run the optimizer to generate metrics."}
        </div>
      )}

      <div style={{ flex: 1, minHeight: 16 }} />
      <div style={S.sectionHeader}>LIVE OPTIMIZER LOGS</div>
      <div style={S.logContainer}>
        {logsData?.logs ? logsData.logs.join('') : "Awaiting logs..."}
      </div>
    </div>
  );
}
