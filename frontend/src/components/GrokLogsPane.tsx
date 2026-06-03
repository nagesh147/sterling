import React from 'react';
import { card, cardHead, cardBody, c, alpha } from '../styles/terminalUI';

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={card}>
      <div style={cardHead}><span>{title}</span></div>
      <div style={cardBody}>{children}</div>
    </div>
  );
}

export function GrokLogsPane() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 16 }}>
      <SectionCard title="ARBITRATOR LOGS">
        <div style={{ 
          fontFamily: 'JetBrains Mono, monospace', 
          fontSize: 9, 
          display: 'flex', 
          flexDirection: 'column', 
          gap: 6,
          lineHeight: 1.4
        }}>
          <div style={{ color: c.dim }}>[10:45:02] Engine initialized. Loading edge configurations...</div>
          <div style={{ color: c.bright }}>[10:45:03] <span style={{ color: c.green, fontWeight: 700 }}>[PASS]</span> BTCUSD 15m bb_rsi_reversion (DSR: 0.88, WFA: 80%)</div>
          <div style={{ color: c.bright }}>[10:45:03] <span style={{ color: c.green, fontWeight: 700 }}>[PASS]</span> SOLUSD 15m vwap_cross (DSR: 0.84, WFA: 60%)</div>
          <div style={{ color: c.dim }}>[10:45:04] <span style={{ color: c.red, fontWeight: 700 }}>[REJECT]</span> ETHUSD 5m vwap_cross (WFA Failure: 40%)</div>
          <div style={{ color: c.dim }}>[10:45:04] <span style={{ color: c.red, fontWeight: 700 }}>[REJECT]</span> SOLUSD 5m bb_rsi_reversion (DSR &lt; 0.85)</div>
          <div style={{ color: c.bright }}>[10:45:05] Running Pearson correlation scan across surviving edges...</div>
          <div style={{ color: c.bright }}>[10:45:05] <span style={{ color: c.green, fontWeight: 700 }}>[CLEAR]</span> Correlation scan passed. No edges exceed 0.50 overlap.</div>
          <div style={{ color: c.amber, marginTop: 8, padding: '4px 8px', background: alpha(c.amber, 0.1), borderRadius: 4, border: `1px solid ${alpha(c.amber, 0.3)}` }}>
            [10:45:06] Arbitrator active. Awaiting signals.
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
