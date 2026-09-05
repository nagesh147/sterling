import React from 'react';

/**
 * The replay dock's icon set.
 *
 * Replaces the emoji the previous surface used as iconography. Emoji do not
 * inherit `currentColor`, so they ignore the theme; they render with
 * platform-specific metrics, which breaks the tabular alignment the dense
 * tables depend on; and screen readers announce them verbatim ("chart
 * increasing button").
 *
 * Every glyph is a 14×14 stroked path on `currentColor`, so colour and state
 * come from the button that hosts it.
 */

type IconProps = {
  size?: number;
  className?: string;
};

function svg(path: React.ReactNode, filled = false) {
  return function Icon({ size = 14, className }: IconProps) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        className={className}
        fill={filled ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth={filled ? 0 : 1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        focusable="false"
      >
        {path}
      </svg>
    );
  };
}

export const Play = svg(<path d="M7 4.5v15l13-7.5z" />, true);
export const Pause = svg(
  <>
    <rect x="6.5" y="4.5" width="4" height="15" rx="1" />
    <rect x="13.5" y="4.5" width="4" height="15" rx="1" />
  </>,
  true,
);
export const Stop = svg(<rect x="6" y="6" width="12" height="12" rx="1.5" />, true);
export const SkipStart = svg(
  <>
    <path d="M6 5v14" />
    <path d="M20 5.5v13L9 12z" />
  </>,
);
export const SkipEnd = svg(
  <>
    <path d="M18 5v14" />
    <path d="M4 5.5v13L15 12z" />
  </>,
);
export const StepBack = svg(
  <>
    <path d="M11 7l-5 5 5 5" />
    <path d="M18 7l-5 5 5 5" />
  </>,
);
export const StepFwd = svg(
  <>
    <path d="M13 7l5 5-5 5" />
    <path d="M6 7l5 5-5 5" />
  </>,
);

export const Signal = svg(<path d="M13 2L4.5 13.5H11L10 22l8.5-11.5H12z" />);
export const Trades = svg(
  <>
    <rect x="2.5" y="7" width="19" height="13" rx="2" />
    <path d="M8.5 7V5.5a2 2 0 012-2h3a2 2 0 012 2V7" />
    <path d="M2.5 12h19" />
  </>,
);
export const Split = svg(
  <>
    <rect x="2.5" y="4.5" width="19" height="15" rx="2" />
    <path d="M12 4.5v15" />
  </>,
);
export const Config = svg(
  <>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.6 1.6 0 00.32 1.77l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.6 1.6 0 00-1.77-.32 1.6 1.6 0 00-1 1.47V21a2 2 0 11-4 0v-.1A1.6 1.6 0 008.1 19.4a1.6 1.6 0 00-1.77.32l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.6 1.6 0 004 15a1.6 1.6 0 00-1.47-1H2.4a2 2 0 110-4h.1A1.6 1.6 0 004 8.6a1.6 1.6 0 00-.32-1.77l-.06-.06a2 2 0 112.83-2.83l.06.06A1.6 1.6 0 008.28 4H8.4A1.6 1.6 0 009.87 2.5V2.4a2 2 0 114 0v.1A1.6 1.6 0 0015.4 4a1.6 1.6 0 001.77-.32l.06-.06a2 2 0 112.83 2.83l-.06.06A1.6 1.6 0 0019.68 8.3V8.4a1.6 1.6 0 001.5 1.47h.1a2 2 0 110 4h-.1a1.6 1.6 0 00-1.47 1z" />
  </>,
);
export const Export = svg(
  <>
    <path d="M12 3v11" />
    <path d="M8 11l4 4 4-4" />
    <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
  </>,
);
export const Calendar = svg(
  <>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 10h18M8 3v4M16 3v4" />
  </>,
);
export const Filter = svg(<path d="M3 5h18l-7 8v6l-4 2v-8z" />);
export const Target = svg(
  <>
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="12" r="3" />
  </>,
);
export const Close = svg(<path d="M6 6l12 12M18 6L6 18" />);
export const ChevronDown = svg(<path d="M6 9l6 6 6-6" />);
export const ChevronUp = svg(<path d="M18 15l-6-6-6 6" />);
export const Alert = svg(
  <>
    <path d="M12 3l9.5 16.5H2.5z" />
    <path d="M12 9v5M12 17.2v.1" />
  </>,
);

/* ── Window controls ─────────────────────────────────────────────────────── */

export const Minimise = svg(<path d="M5 18h14" />);
export const Expand = svg(
  <>
    <rect x="4" y="3" width="16" height="18" rx="2" />
    <path d="M12 7v10M8.5 10.5L12 7l3.5 3.5M8.5 13.5L12 17l3.5-3.5" />
  </>,
);
export const Overlay = svg(
  <>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M3 14h18" />
  </>,
);
export const Fullscreen = svg(<path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5" />);
export const Restore = svg(
  <>
    <rect x="5" y="8" width="12" height="11" rx="1.5" />
    <path d="M8 8V5h11v11h-2" />
  </>,
);

/** A six-dot drag affordance. Colour comes from the token, not a literal hex. */
export function DragGrip() {
  return (
    <span aria-hidden="true" className="rd-grip">
      {Array.from({ length: 6 }, (_, i) => (
        <span key={i} />
      ))}
    </span>
  );
}

/** Small inline spinner for the loading state. */
export function Spinner({ size = 12 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className="rd-spinner"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M12 3a9 9 0 019 9" />
    </svg>
  );
}
