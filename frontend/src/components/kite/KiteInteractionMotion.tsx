import React from 'react';
import { useKiteSettings } from '../../store/useKiteSettings';

const ROW_SELECTOR = [
  '[data-motion-row]',
  '.mw-item',
  '.st-parent-row',
  '.st-leg-row',
  '.kv-rows > *',
  'tbody > tr',
  '[role="row"]',
].join(',');

const MOTION_CSS = `
.kite-motion-enabled {
  --km-fast: 90ms;
  --km-ui: 130ms;
  --km-pop: 165ms;
  --km-ease: cubic-bezier(.2,.8,.2,1);
  --km-pop-ease: cubic-bezier(.16,1,.3,1);
  --km-accent: #e95420;
  --km-hover: rgba(233,84,32,.055);
  --km-ring: rgba(233,84,32,.28);
}

.kite-motion-enabled[data-motion-style='mac'] {
  --km-fast: 110ms; --km-ui: 170ms; --km-pop: 220ms;
  --km-ease: cubic-bezier(.22,1,.36,1); --km-pop-ease: cubic-bezier(.16,1,.3,1);
  --km-accent: #4184f3; --km-hover: rgba(65,132,243,.055); --km-ring: rgba(65,132,243,.28);
}
.kite-motion-enabled[data-motion-style='material'] {
  --km-fast: 100ms; --km-ui: 155ms; --km-pop: 190ms;
  --km-ease: cubic-bezier(.4,0,.2,1); --km-pop-ease: cubic-bezier(.2,0,0,1);
  --km-accent: #6750a4; --km-hover: rgba(103,80,164,.055); --km-ring: rgba(103,80,164,.28);
}
.kite-motion-enabled[data-motion-style='windows'] {
  --km-fast: 85ms; --km-ui: 135ms; --km-pop: 170ms;
  --km-ease: cubic-bezier(.1,.9,.2,1); --km-pop-ease: cubic-bezier(.1,.9,.2,1);
  --km-accent: #0078d4; --km-hover: rgba(0,120,212,.05); --km-ring: rgba(0,120,212,.28);
}
.kite-motion-enabled[data-motion-style='gnome'] {
  --km-fast: 105ms; --km-ui: 165ms; --km-pop: 205ms;
  --km-ease: cubic-bezier(.25,.46,.45,.94); --km-pop-ease: cubic-bezier(.22,1,.36,1);
  --km-accent: #3584e4; --km-hover: rgba(53,132,228,.05); --km-ring: rgba(53,132,228,.28);
}
.kite-motion-enabled[data-motion-style='kde'] {
  --km-fast: 75ms; --km-ui: 120ms; --km-pop: 150ms;
  --km-ease: cubic-bezier(.2,.7,.2,1); --km-pop-ease: cubic-bezier(.2,.85,.25,1);
  --km-accent: #1d99f3; --km-hover: rgba(29,153,243,.05); --km-ring: rgba(29,153,243,.28);
}
.kite-motion-enabled[data-motion-style='minimal'] {
  --km-fast: 1ms; --km-ui: 1ms; --km-pop: 1ms;
  --km-ease: linear; --km-pop-ease: linear;
  --km-accent: #666; --km-hover: rgba(0,0,0,.025); --km-ring: rgba(0,0,0,.18);
}

.kite-motion-enabled button,
.kite-motion-enabled a[href],
.kite-motion-enabled [role='button'],
.kite-motion-enabled summary,
.kite-motion-enabled input,
.kite-motion-enabled select,
.kite-motion-enabled textarea {
  transition-property: color, background-color, border-color, box-shadow, opacity, filter;
  transition-duration: var(--km-ui);
  transition-timing-function: var(--km-ease);
}

.kite-motion-enabled button:not(:disabled),
.kite-motion-enabled [role='button']:not([aria-disabled='true']),
.kite-motion-enabled summary,
.kite-motion-enabled a[href] {
  -webkit-tap-highlight-color: transparent;
}

@media (hover:hover) and (pointer:fine) {
  .kite-motion-enabled button:not(:disabled):hover,
  .kite-motion-enabled [role='button']:not([aria-disabled='true']):hover,
  .kite-motion-enabled summary:hover {
    filter: brightness(.985);
  }

  /* Watchlist hover keeps only the vertical interaction strip. Component-level
   * hover fills are intentionally suppressed so the row body stays clean. */
  .kite-motion-enabled .mw-item:hover {
    background-color: transparent !important;
    box-shadow: inset 2px 0 0 var(--km-accent);
  }

  .kite-motion-enabled tbody > tr:hover,
  .kite-motion-enabled [data-motion-row]:hover {
    background-color: var(--km-hover);
    box-shadow: inset 2px 0 0 var(--km-accent);
  }

  /* Signal hover also keeps only the vertical interaction strip. !important
   * wins over inline/component hover fills without touching the inset shadow. */
  .kite-motion-enabled .st-parent-row:hover,
  .kite-motion-enabled .st-leg-row:hover,
  .kite-motion-enabled .kv-rows > *:hover {
    background-color: transparent !important;
    box-shadow: inset 2px 0 0 var(--km-accent);
  }
}

.kite-motion-enabled button:not(:disabled):active,
.kite-motion-enabled [role='button']:not([aria-disabled='true']):active,
.kite-motion-enabled summary:active {
  opacity: .82;
  transition-duration: 45ms;
}

.kite-motion-enabled a[href]:active { opacity: .66; transition-duration: 45ms; }

.kite-motion-enabled button:focus-visible,
.kite-motion-enabled a[href]:focus-visible,
.kite-motion-enabled [role='button']:focus-visible,
.kite-motion-enabled input:focus-visible,
.kite-motion-enabled select:focus-visible,
.kite-motion-enabled textarea:focus-visible,
.kite-motion-enabled summary:focus-visible {
  outline: 2px solid var(--km-ring);
  outline-offset: 2px;
}

.kite-motion-enabled .mw-item,
.kite-motion-enabled .st-parent-row,
.kite-motion-enabled .st-leg-row,
.kite-motion-enabled .kv-rows > *,
.kite-motion-enabled tbody > tr,
.kite-motion-enabled [data-motion-row] {
  transition: background-color var(--km-fast) linear, box-shadow var(--km-fast) linear, opacity var(--km-ui) var(--km-ease);
  transform: none !important;
}

.kite-motion-enabled [data-motion-popover],
.kite-motion-enabled [role='menu'],
.kite-motion-enabled [role='dialog'] {
  animation: km-pop-in var(--km-pop) var(--km-pop-ease) both;
}

@keyframes km-pop-in {
  from { opacity: 0; transform: translate3d(0,4px,0) scale(.99); }
  to { opacity: 1; transform: translate3d(0,0,0) scale(1); }
}

@keyframes km-row-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.kite-motion-enabled .km-row-enter {
  animation: km-row-in var(--km-ui) var(--km-ease) both;
}

@media (prefers-reduced-motion: reduce) {
  .kite-motion-enabled *, .kite-motion-enabled *::before, .kite-motion-enabled *::after {
    animation-duration: .001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .001ms !important;
    scroll-behavior: auto !important;
  }
}
`;

let styleInstalled = false;
function ensureStyles() {
  if (styleInstalled || typeof document === 'undefined') return;
  const existing = document.getElementById('sterling-kite-interaction-motion');
  if (existing instanceof HTMLStyleElement) {
    // Keep injected interaction CSS current across Vite hot reloads.
    if (existing.textContent !== MOTION_CSS) existing.textContent = MOTION_CSS;
    styleInstalled = true;
    return;
  }
  const style = document.createElement('style');
  style.id = 'sterling-kite-interaction-motion';
  style.textContent = MOTION_CSS;
  document.head.appendChild(style);
  styleInstalled = true;
}

function normalizeStyle(style: string) {
  if (style === 'classic') return 'material';
  if (style === 'off') return 'minimal';
  return style;
}

function matchingRows(node: Node): HTMLElement[] {
  if (!(node instanceof HTMLElement)) return [];
  const rows: HTMLElement[] = [];
  if (node.matches(ROW_SELECTOR)) rows.push(node);
  node.querySelectorAll<HTMLElement>(ROW_SELECTOR).forEach((row) => rows.push(row));
  return rows;
}

export function KiteInteractionMotion({ children }: { children: React.ReactNode }) {
  const rootRef = React.useRef<HTMLDivElement>(null);
  const style = useKiteSettings((state) => state.loaderStyle);

  ensureStyles();

  React.useEffect(() => {
    const root = rootRef.current;
    if (!root || typeof document === 'undefined') return;

    document.body.classList.add('kite-motion-enabled');
    document.body.dataset.motionStyle = normalizeStyle(style);

    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const observer = new MutationObserver((records) => {
      if (reduced) return;
      for (const record of records) {
        if (record.type !== 'childList') continue;
        for (const node of Array.from(record.addedNodes)) {
          for (const row of matchingRows(node)) {
            row.classList.remove('km-row-enter');
            void row.offsetWidth;
            row.classList.add('km-row-enter');
            window.setTimeout(() => row.classList.remove('km-row-enter'), 260);
          }
        }
      }
    });

    observer.observe(root, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      document.body.classList.remove('kite-motion-enabled');
      delete document.body.dataset.motionStyle;
    };
  }, [style]);

  return <div ref={rootRef} style={{ display: 'contents' }}>{children}</div>;
}

export default KiteInteractionMotion;
