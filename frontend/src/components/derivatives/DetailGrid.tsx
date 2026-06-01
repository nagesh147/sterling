/**
 * DetailGrid — the label/value grid used in the expandable detail row of the
 * futures & options candidate tables (mirrors the signal table's execution-row
 * detail). The optional `pnlVal` tints the P&L value green/red.
 */
import React from 'react';
import { c } from '../../styles/terminalUI';

export const DetailGrid: React.FC<{
  items: [string, string][];
  pnlVal?: number | null;
}> = ({ items, pnlVal }) => (
  <div style={{
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: '6px 16px',
  }}>
    {items.map(([label, value]) => {
      const isPnl = label.includes('P&L');
      const color = isPnl && pnlVal != null ? (pnlVal >= 0 ? c.green : c.red) : c.bright;
      return (
        <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span style={{ fontSize: 8.5, color: c.dim, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{label}</span>
          <span style={{ fontSize: 11, fontWeight: 700, color }}>{value}</span>
        </div>
      );
    })}
  </div>
);
