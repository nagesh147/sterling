import React from 'react';
import { k } from '../../../styles/kiteUI';

/**
 * The scan's state, in the space the rescan icon occupies.
 *
 * This replaces a 2px progress band that used to sit above the search row. The
 * band spent a full row of a dense dock restating something the button beside it
 * could say on its own.
 *
 * **There is deliberately no percentage while a scan is running.** A scan in
 * flight is indeterminate — the engine reports that it is scanning and which
 * instrument it is on, not how far through a known total it is. A number there
 * would be invented, and an invented number on a trading dock is worse than no
 * number. So a live scan gets motion, and the percentage belongs to the thing
 * that genuinely has one: the countdown to the next automatic scan.
 */
export function ScanProgressRing({
  fraction, scanning, size = 15,
}: {
  /** 0..1 through the wait for the next scan. */
  fraction: number;
  /** A scan is in flight — indeterminate, so no number. */
  scanning: boolean;
  size?: number;
}) {
  const stroke = 2;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.round(Math.min(1, Math.max(0, fraction)) * 100);

  return (
    <span
      style={{
        position: 'relative', display: 'inline-flex', alignItems: 'center',
        justifyContent: 'center', width: size, height: size, flexShrink: 0,
      }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={k.border} strokeWidth={stroke}
        />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={k.orange} strokeWidth={stroke} strokeLinecap="round"
          // Drawn from twelve o'clock, which is where a reader expects a dial to
          // start; the default arc begins at three.
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          strokeDasharray={c}
          strokeDashoffset={scanning ? c * 0.75 : c * (1 - pct / 100)}
          className={scanning ? 'st-scan-ring' : undefined}
          style={scanning ? undefined : { transition: 'stroke-dashoffset 1s linear' }}
        />
      </svg>
      {!scanning && (
        // No unit and no leading zero — at this size the ring says it is a
        // proportion and the digits only have room to say which.
        <span style={{
          position: 'absolute', fontSize: 6.5, fontWeight: 800, lineHeight: 1,
          color: k.dim, fontVariantNumeric: 'tabular-nums',
        }}>
          {pct}
        </span>
      )}
      <style>{
        '@keyframes st-scan-ring-spin{to{transform:rotate(270deg)}}'
        + '.st-scan-ring{transform-origin:center;animation:st-scan-ring-spin .9s linear infinite}'
        + '@media (prefers-reduced-motion: reduce){.st-scan-ring{animation:none}}'
      }</style>
    </span>
  );
}

export default ScanProgressRing;
