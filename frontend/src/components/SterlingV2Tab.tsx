import React from 'react';

export function SterlingV2Tab() {
  return (
    <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: 16, background: 'var(--t-bg)' }}>
      <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>
        STERLING V2 <span style={{ color: 'var(--t-amber)', fontSize: 11 }}>(experimental)</span>
      </div>
      <div style={{ color: 'var(--t-dim)', marginTop: 8, fontSize: 12 }}>
        Leak-free harness + short-side / conviction-gate / exit-engine / vol-sizing /
        correlation-aware portfolio. Panes wired in a later task.
      </div>
    </div>
  );
}
