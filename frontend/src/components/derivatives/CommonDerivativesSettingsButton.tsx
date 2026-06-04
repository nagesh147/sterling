/**
 * CommonDerivativesSettingsButton — sibling to the existing SETTINGS / BACKTEST
 * triggers in every strategy tab. Opens the same drawer the SETTINGS
 * button uses (so the operator sees one drawer, not three), with the
 * CommonDerivativesPanel section auto-scrolled into view.
 */
import React from 'react';
import { c, alpha } from '../../styles/terminalUI';

interface Props {
  onClick: () => void;
  active?: boolean;
}

export const CommonDerivativesSettingsButton: React.FC<Props> = ({ onClick, active }) => {
  return (
    <button
      onClick={onClick}
      title="Per-strategy derivatives selector profile"
      style={{
        padding: '4px 10px', borderRadius: 5, fontSize: 10, fontWeight: 700,
        letterSpacing: '0.08em', textTransform: 'uppercase',
        background: active ? alpha(c.blue, 0.13) : 'transparent',
        border: `1px solid ${active ? alpha(c.blue, 0.4) : c.border}`,
        color: active ? c.blue : c.dim,
        cursor: 'pointer', fontFamily: 'inherit',
      }}>
      ⚙ DERIVATIVES
    </button>
  );
};
