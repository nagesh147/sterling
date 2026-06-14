import React from 'react';

// A light-themed two-segment toggle pill (e.g. PAPER|LIVE, MANUAL|AUTO) that
// matches the Kite Connect page styling. Purely presentational: it reports which
// side the user picked via `onSelect` and lets the parent decide whether a
// transition needs a confirmation step. The currently-selected side is inert.

type Side = 'left' | 'right';

export interface ModeToggleProps {
  left: string;
  right: string;
  value: Side;
  onSelect: (side: Side) => void;
  /** colour of the LEFT (safe/default) segment when active — default Kite blue. */
  leftColor?: string;
  /** colour of the RIGHT (armed) segment when active — default green. */
  rightColor?: string;
  /** show a ● before the right label when it's the active side. */
  rightDotWhenActive?: boolean;
  /** disable only the right segment (e.g. can't go live without API keys). */
  rightDisabled?: boolean;
  /** tooltip for the right segment (e.g. why it's disabled). */
  rightTitle?: string;
  /** whole control is mid-mutation. */
  busy?: boolean;
  size?: 'sm' | 'md';
}

export function ModeToggle({
  left, right, value, onSelect,
  leftColor = '#387ed1', rightColor = '#4caf50',
  rightDotWhenActive = false, rightDisabled = false, rightTitle,
  busy = false, size = 'md',
}: ModeToggleProps) {
  const isLeft = value === 'left';
  const pad = size === 'sm' ? '3px 10px' : '4px 13px';
  const fs = size === 'sm' ? 9.5 : 10;

  const seg = (active: boolean, color: string, clickable: boolean): React.CSSProperties => ({
    padding: pad,
    border: 'none',
    borderRadius: 4,
    background: active ? '#fff' : 'transparent',
    color: active ? color : '#9b9b9b',
    fontFamily: 'inherit',
    fontSize: fs,
    fontWeight: active ? 700 : 500,
    letterSpacing: '0.07em',
    lineHeight: 1,
    whiteSpace: 'nowrap',
    cursor: busy ? 'wait' : clickable ? 'pointer' : 'default',
    boxShadow: active ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
    transition: 'background .15s, color .15s',
  });

  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 2,
      padding: 2,
      background: '#f1f1f1',
      border: `1px solid ${isLeft ? '#e0e0e0' : `${rightColor}66`}`,
      borderRadius: 5,
      opacity: busy ? 0.6 : 1,
    }}>
      <button
        type="button"
        disabled={busy || isLeft}
        onClick={() => !isLeft && onSelect('left')}
        style={seg(isLeft, leftColor, !isLeft && !busy)}
      >
        {left}
      </button>
      <button
        type="button"
        title={rightTitle}
        disabled={busy || !isLeft || rightDisabled}
        onClick={() => isLeft && !rightDisabled && onSelect('right')}
        style={{ ...seg(!isLeft, rightColor, isLeft && !rightDisabled && !busy), opacity: rightDisabled ? 0.45 : 1 }}
      >
        {rightDotWhenActive && !isLeft ? '● ' : ''}{right}
      </button>
    </div>
  );
}

export default ModeToggle;
