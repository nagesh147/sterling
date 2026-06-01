/**
 * SourceBadge — labels which feed a derivatives candidate came from.
 *
 *  • "edge"   → the backtest-validated 4h winner feed (BACKTEST_EDGE_REPORT).
 *  • "engine" → the live scalping / triple-ST strategy engine.
 *
 * Edge rows are display-only by default (auto_execute stays OFF) — the pill
 * lets the operator tell a proven-setup row apart from an engine row at a glance.
 */
import React from 'react';
import { alpha, c } from '../../styles/terminalUI';

export const SourceBadge: React.FC<{ source?: string }> = ({ source }) => {
  const isEdge = source === 'edge';
  const color = isEdge ? c.green : c.dim;
  return (
    <span
      title={isEdge
        ? 'Backtest-validated edge feed (4h winner) — display-only until enabled'
        : 'Live strategy engine feed'}
      style={{
        display: 'inline-block', padding: '1px 5px', borderRadius: 3,
        background: alpha(color, 0.14), border: `1px solid ${alpha(color, 0.4)}`,
        color, fontSize: 8, fontWeight: 800, letterSpacing: '0.08em',
        marginRight: 6, verticalAlign: 'middle',
      }}
    >
      {isEdge ? 'EDGE' : 'ENG'}
    </span>
  );
};

/** Strip feed prefixes for a clean strategy label. */
export const cleanStrategy = (s: string): string =>
  s.replace('scalping/', '').replace('edge/', '').toUpperCase();
