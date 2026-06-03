import React from 'react';
import { c } from '../styles/terminalUI';
import { V2SignalsPane } from './sterling_v2/V2SignalsPane';
import { V2ResearchPane } from './sterling_v2/V2ResearchPane';

export function SterlingV2Tab() {
  return (
    <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: 16, background: 'var(--t-bg)' }}>
      <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>
        STERLING V2 <span style={{ color: c.amber, fontSize: 11 }}>(experimental)</span>
      </div>
      <div style={{ color: c.dim, marginTop: 8, marginBottom: 16, fontSize: 12, lineHeight: 1.5 }}>
        Leak-free harness (next-bar fills, realistic costs, realized-frequency Sharpe). Validated
        levers: short side + vol-targeted sizing + correlation-aware portfolio with a −20% drawdown
        breaker. Everything below is paper-only; nothing executes automatically.
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <V2ResearchPane active={true} />
        <V2SignalsPane active={true} />
      </div>
    </div>
  );
}
