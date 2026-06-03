import React from 'react';
import { card, cardHead, cardBody, c } from '../styles/terminalUI';

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={card}>
      <div style={cardHead}><span>{title}</span></div>
      <div style={cardBody}>{children}</div>
    </div>
  );
}

export function GrokSettingsPane() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionCard title="GROK ENGINE">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 0' }}>
          <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 10, fontWeight: 600, color: 'var(--t-muted)' }}>
            <span>DSR Threshold</span>
            <input type="number" defaultValue={0.85} step={0.01} style={{
              width: 68, background: 'var(--t-bg)', border: '1px solid var(--t-border)',
              borderRadius: 5, color: 'var(--t-bright)', fontFamily: 'inherit', fontSize: 10,
              padding: '3px 6px', textAlign: 'right'
            }} />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 10, fontWeight: 600, color: 'var(--t-muted)' }}>
            <span>P(Loss) Max</span>
            <input type="number" defaultValue={15} step={1} style={{
              width: 68, background: 'var(--t-bg)', border: '1px solid var(--t-border)',
              borderRadius: 5, color: 'var(--t-bright)', fontFamily: 'inherit', fontSize: 10,
              padding: '3px 6px', textAlign: 'right'
            }} />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 10, fontWeight: 600, color: 'var(--t-muted)' }}>
            <span>WFA Consistency</span>
            <input type="number" defaultValue={60} step={1} style={{
              width: 68, background: 'var(--t-bg)', border: '1px solid var(--t-border)',
              borderRadius: 5, color: 'var(--t-bright)', fontFamily: 'inherit', fontSize: 10,
              padding: '3px 6px', textAlign: 'right'
            }} />
          </label>
        </div>
      </SectionCard>
      
      <SectionCard title="ROBUSTNESS GATES">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '4px 0' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 10, color: 'var(--t-bright)' }}>
            <input type="checkbox" defaultChecked />
            <span>Enable Auto-Arbitration</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 10, color: 'var(--t-bright)' }}>
            <input type="checkbox" defaultChecked />
            <span>Strict Pearson De-duplication</span>
          </label>
        </div>
      </SectionCard>
    </div>
  );
}
