/**
 * Runtime app-font picker. The Google Fonts <link> in index.html loads the 14
 * non-system options (System UI needs no download) at the three weights the
 * codebase uses, so switching is instant — we just rewrite the --app-font CSS
 * variable that `body` and `.term-root` read.
 *
 * The choice persists in localStorage as 'app.font.stack' and is applied
 * pre-paint by the inline script in index.html (no flash on reload).
 */
import { useEffect, useState } from 'react';

export type AppFont = { name: string; stack: string };

// Top 15 UI font families — curated for dashboards / trading interfaces.
export const APP_FONTS: AppFont[] = [
  { name: 'Inter',             stack: "'Inter', system-ui, sans-serif" },
  { name: 'IBM Plex Sans',     stack: "'IBM Plex Sans', system-ui, sans-serif" },
  { name: 'Geist',             stack: "'Geist', system-ui, sans-serif" },
  { name: 'DM Sans',           stack: "'DM Sans', system-ui, sans-serif" },
  { name: 'Manrope',           stack: "'Manrope', system-ui, sans-serif" },
  { name: 'Plus Jakarta Sans', stack: "'Plus Jakarta Sans', system-ui, sans-serif" },
  { name: 'Outfit',            stack: "'Outfit', system-ui, sans-serif" },
  { name: 'Poppins',           stack: "'Poppins', system-ui, sans-serif" },
  { name: 'Roboto',            stack: "'Roboto', system-ui, sans-serif" },
  { name: 'Open Sans',         stack: "'Open Sans', system-ui, sans-serif" },
  { name: 'Source Sans 3',     stack: "'Source Sans 3', system-ui, sans-serif" },
  { name: 'Lato',              stack: "'Lato', system-ui, sans-serif" },
  { name: 'Work Sans',         stack: "'Work Sans', system-ui, sans-serif" },
  { name: 'Nunito Sans',       stack: "'Nunito Sans', system-ui, sans-serif" },
  { name: 'System UI',         stack: "system-ui, -apple-system, 'Segoe UI', sans-serif" },
];

const STORAGE_KEY = 'app.font.stack';
export const DEFAULT_FONT_STACK = APP_FONTS[0].stack; // Inter

function readStored(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_FONT_STACK;
  } catch {
    return DEFAULT_FONT_STACK;
  }
}

function applyStack(stack: string) {
  document.documentElement.style.setProperty('--app-font', stack);
}

/** Hook that returns the current font stack and a setter. Persists the choice
 *  and updates the --app-font CSS variable live (every element that uses
 *  var(--app-font) re-renders in the new face immediately). */
export function useAppFont(): readonly [string, (stack: string) => void] {
  const [stack, setStack] = useState<string>(readStored);
  useEffect(() => {
    applyStack(stack);
    try { localStorage.setItem(STORAGE_KEY, stack); } catch { /* private mode */ }
  }, [stack]);
  return [stack, setStack] as const;
}

/** Compact picker — a labelled `<select>` plus a single-line live preview that
 *  renders in the currently-selected face. Fits the left nav / settings drawer. */
export function FontPicker() {
  const [stack, setStack] = useAppFont();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{
        fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
        color: 'var(--t-dim)', textTransform: 'uppercase',
      }}>Font</label>
      <select
        value={stack}
        onChange={(e) => setStack(e.target.value)}
        style={{
          width: '100%', padding: '6px 8px', fontFamily: 'inherit', fontSize: 12,
          background: 'var(--t-bg)', color: 'var(--t-text)',
          border: '1px solid var(--t-border)', borderRadius: 'var(--radius-md, 6px)',
          cursor: 'pointer', outline: 'none',
        }}
      >
        {APP_FONTS.map((f) => (
          // Render each option in its own face so the dropdown previews itself.
          <option key={f.name} value={f.stack} style={{ fontFamily: f.stack }}>
            {f.name}
          </option>
        ))}
      </select>
      <div style={{
        fontFamily: stack, fontSize: 12, color: 'var(--t-text)',
        lineHeight: 1.4, padding: '6px 8px', borderRadius: 'var(--radius-md, 6px)',
        background: 'var(--t-bg)', border: '1px solid var(--t-border)',
      }}>
        <div style={{ fontWeight: 700 }}>The quick brown fox</div>
        <div style={{ fontWeight: 400, color: 'var(--t-dim)' }}>jumps over · 0123456789</div>
      </div>
    </div>
  );
}
