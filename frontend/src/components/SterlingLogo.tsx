/**
 * Sterling brand mark — a macOS-style terminal window with a `>_` prompt.
 * Rendered as inline SVG (not <img>) so the cursor can blink via CSS.
 * The static <img> equivalent lives at /public/logo.svg for the favicon.
 */
export function SterlingLogo({ size = 24 }: { size?: number }) {
  return (
    <span style={{ display: 'inline-flex', lineHeight: 0 }} aria-label="Sterling" role="img">
      <style>{`
        @keyframes sterling-blink { 0%, 55% { opacity: 1; } 56%, 100% { opacity: 0.12; } }
        .sterling-cursor { animation: sterling-blink 1.05s steps(1, end) infinite; transform-box: fill-box; }
        @media (prefers-reduced-motion: reduce) { .sterling-cursor { animation: none; opacity: 1; } }
      `}</style>
      <svg width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="sterling-screen-live" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#2A2D31" />
            <stop offset="1" stopColor="#161719" />
          </linearGradient>
        </defs>
        {/* Terminal tile */}
        <rect width="64" height="64" rx="15" fill="url(#sterling-screen-live)" />
        <rect x="1.25" y="1.25" width="61.5" height="61.5" rx="13.75" fill="none" stroke="#3A3D42" strokeWidth="1.5" />
        {/* Prompt  >_ */}
        <polyline points="19 24 29 32 19 40" stroke="#E3E3E3" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        <rect className="sterling-cursor" x="33" y="36" width="14" height="5" rx="2.5" fill="#34D399" />
      </svg>
    </span>
  );
}

export default SterlingLogo;
