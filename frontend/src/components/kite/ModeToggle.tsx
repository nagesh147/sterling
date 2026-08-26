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
  leftColor = 'var(--k-blue-kite)', rightColor = 'var(--k-green)',
  rightDotWhenActive = false, rightDisabled = false, rightTitle,
  busy = false, size = 'md',
}: ModeToggleProps) {
  const isLeft = value === 'left';
  const height = size === 'sm' ? 28 : 32;
  const pad = size === 'sm' ? '0 10px' : '0 13px';
  const fs = size === 'sm' ? 10 : 10.5;

  const seg = (active: boolean, color: string, clickable: boolean): React.CSSProperties => ({
    padding: pad,
    minHeight: height,
    border: 'none',
    borderRadius: 6,
    background: active ? 'var(--k-bg)' : 'transparent',
    color: active ? 'var(--k-text)' : 'var(--k-ink-6)',
    fontFamily: 'inherit',
    fontSize: fs,
    fontWeight: active ? 700 : 500,
    letterSpacing: '0.07em',
    lineHeight: 1,
    whiteSpace: 'nowrap',
    cursor: busy ? 'wait' : clickable ? 'pointer' : 'default',
    boxShadow: active ? `inset 0 -2px ${color}, 0 1px 2px rgba(0,0,0,0.08)` : 'none',
    transition: 'background .15s, color .15s',
  });

  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 2,
      padding: 3,
      background: '#f6f6f7',
      border: '1px solid var(--k-border)',
      borderRadius: 8,
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
