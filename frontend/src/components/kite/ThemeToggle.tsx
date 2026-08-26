/**
 * The app-level light/dark switch.
 *
 * One control, one job. The status bar's three-way DK/GR/LT picker still
 * exists for the grey shell, but the thing a user reaches for a dozen times a
 * day should not make them think about a third option.
 *
 * The icon shows the theme you will GET, not the one you are in — a sun means
 * "click for light". That reads correctly whether or not you can see the
 * current state, which matters on a terminal that is mostly dark chrome.
 */
import React from 'react';
import { useTheme, useToggleLightDark } from '../../store/useStore';

function SunIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2.4v2.4M12 19.2v2.4M4.2 4.2l1.7 1.7M18.1 18.1l1.7 1.7M2.4 12h2.4M19.2 12h2.4M4.2 19.8l1.7-1.7M18.1 5.9l1.7-1.7" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M20.5 14.6A8.6 8.6 0 0 1 9.4 3.5a8.6 8.6 0 1 0 11.1 11.1Z" />
    </svg>
  );
}

export function ThemeToggle({ size = 32 }: { size?: number }) {
  const theme = useTheme();
  const toggle = useToggleLightDark();
  const isLight = theme === 'light';
  const next = isLight ? 'dark' : 'light';

  return (
    <button
      type="button"
      onClick={toggle}
      // Named for the outcome, so a screen reader announces the action rather
      // than a state the user then has to invert in their head.
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className="sk-theme-toggle"
      style={{
        width: size,
        height: size,
        borderRadius: 8,
        border: '1px solid var(--t-border)',
        background: 'none',
        color: 'var(--t-dim)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        padding: 0,
        transition: 'color .15s ease, border-color .15s ease',
      }}
    >
      <span
        // The two glyphs are the same shape budget, so the swap reads as one
        // control changing rather than two controls trading places.
        style={{ display: 'inline-flex', transition: 'transform .28s cubic-bezier(.4,0,.2,1)' }}
      >
        {isLight ? <MoonIcon /> : <SunIcon />}
      </span>
    </button>
  );
}
