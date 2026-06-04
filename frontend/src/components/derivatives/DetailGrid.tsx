/**
 * DetailGrid — the label/value grid used in the expandable detail row of the
 * futures & options candidate tables (mirrors the signal table's execution-row
 * detail). The optional `pnlVal` tints the P&L value green/red.
 */
import React from 'react';
import { c } from '../../styles/terminalUI';

const TOOLTIPS: Record<string, string> = {
  'Contract': 'Option contract details (Type, Strike, DTE)',
  'Option': 'Specific option instrument',
  'Direction': 'Trade direction (LONG/SHORT)',
  'Strike': 'Strike price',
  'DTE': 'Days to expiration',
  'Delta': 'Price sensitivity to $1 underlying move',
  'Gamma': 'Rate of change of Delta',
  'Theta': 'Daily time decay',
  'Vega': 'Sensitivity to 1% implied volatility change',
  'Premium': 'Option price / Entry premium paid',
  'Contracts': 'Number of contracts traded',
  'Expected R': 'Expected Risk-Reward Ratio at take-profit',
  'θ burn': 'Projected total theta burn over expected hold time',
  'Liquidity': 'Liquidity health score (0-100)',
  'Position': 'Current position status',
  'Unrealized P&L': 'Estimated Live Profit/Loss',
  'Realized P&L': 'Locked Profit/Loss',
  'Margin': 'Required margin',
  'Leverage': 'Effective leverage',
  'Liq. Price': 'Estimated liquidation price',
  'Maint. Margin': 'Maintenance margin required',
  'Funding Rate': 'Current funding rate'
};

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
      const tooltip = TOOLTIPS[label];
      return (
        <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span 
            title={tooltip}
            style={{ 
              fontSize: 9, 
              color: c.muted, 
              letterSpacing: '0.04em', 
              textTransform: 'uppercase',
              cursor: tooltip ? 'help' : 'default',
              borderBottom: tooltip ? `1px dotted ${c.muted}` : 'none',
              width: 'fit-content'
            }}
          >
            {label}
          </span>
          <span style={{ fontSize: 11, fontWeight: 700, color }}>{value}</span>
        </div>
      );
    })}
  </div>
);
