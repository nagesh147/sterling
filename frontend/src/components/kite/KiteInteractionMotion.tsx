import React from 'react';

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
/*
 * Sterling Kite interaction motion.
 *
 * Only compositor-friendly transform/opacity plus paint-cheap colour/border
 * transitions are used. No width/height/top/left animation, no perpetual
 * will-change layers, and no JS animation loop.
 */
.kite-motion-enabled {
  --kite-motion-fast: 105ms;
  --kite-motion-ui: 145ms;
  --kite-motion-row: 180ms;
  --kite-motion-ease: cubic-bezier(.2,.8,.2,1);
  --kite-motion-pop: cubic-bezier(.16,1,.3,1);
}

.kite-motion-enabled button,
.kite-motion-enabled a[href],
.kite-motion-enabled [role='button'],
.kite-motion-enabled summary,
.kite-motion-enabled label,
.kite-motion-enabled input,
.kite-motion-enabled select,
.kite-motion-enabled textarea {
  transition-property: color, background-color, border-color, box-shadow, opacity, transform, filter;
  transition-duration: var(--kite-motion-ui);
  transition-timing-function: var(--kite-motion-ease);
}

.kite-motion-enabled button:not(:disabled),
.kite-motion-enabled [role='button']:not([aria-disabled='true']),
.kite-motion-enabled summary,
.kite-motion-enabled a[href] {
  -webkit-tap-highlight-color: transparent;
}

@media (hover: hover) and (pointer: fine) {
  .kite-motion-enabled button:not(:disabled):hover,
  .kite-motion-enabled [role='button']:not([aria-disabled='true']):hover,
  .kite-motion-enabled summary:hover {
    filter: brightness(.985);
  }

  .kite-motion-enabled button:not(:disabled):hover svg,
  .kite-motion-enabled [role='button']:not([aria-disabled='true']):hover svg,
  .kite-motion-enabled a[href]:hover svg {
    transform: translate3d(0,-.5px,0) scale(1.035);
  }

  .kite-motion-enabled .mw-item:hover,
  .kite-motion-enabled .st-parent-row:hover,
  .kite-motion-enabled .st-leg-row:hover,
  .kite-motion-enabled .kv-rows > *:hover,
  .kite-motion-enabled tbody > tr:hover,
  .kite-motion-enabled [data-motion-row]:hover {
    transform: translate3d(1px,0,0);
  }
}

.kite-motion-enabled button:not(:disabled):active,
.kite-motion-enabled [role='button']:not([aria-disabled='true']):active,
.kite-motion-enabled summary:active {
  transform: translate3d(0,1px,0) scale(.975);
  transition-duration: 55ms;
}

.kite-motion-enabled a[href]:active {
  opacity: .68;
  transition-duration: 55ms;
}

.kite-motion-enabled button:focus-visible,
.kite-motion-enabled a[href]:focus-visible,
.kite-motion-enabled [role='button']:focus-visible,
.kite-motion-enabled input:focus-visible,
.kite-motion-enabled select:focus-visible,
.kite-motion-enabled textarea:focus-visible,
.kite-motion-enabled summary:focus-visible {
  outline: 2px solid rgba(65,132,243,.32);
  outline-offset: 2px;
}

.kite-motion-enabled button:disabled,
.kite-motion-enabled [aria-disabled='true'] {
  transform: none !important;
  filter: none !important;
}

.kite-motion-enabled button svg,
.kite-motion-enabled a[href] svg,
.kite-motion-enabled [role='button'] svg,
.kite-motion-enabled summary svg {
  transition: transform var(--kite-motion-ui) var(--kite-motion-pop), opacity var(--kite-motion-fast) linear, color var(--kite-motion-ui) ease;
  transform-origin: center;
}

.kite-motion-enabled .mw-item,
.kite-motion-enabled .st-parent-row,
.kite-motion-enabled .st-leg-row,
.kite-motion-enabled .kv-rows > *,
.kite-motion-enabled tbody > tr,
.kite-motion-enabled [data-motion-row] {
  transition: background-color var(--kite-motion-fast) linear, box-shadow var(--kite-motion-ui) var(--kite-motion-ease), transform var(--kite-motion-ui) var(--kite-motion-ease), opacity var(--kite-motion-ui) ease;
  transform-origin: center;
}

.kite-motion-enabled [aria-expanded='true'] > svg:last-child,
.kite-motion-enabled button[aria-expanded='true'] svg:last-child {
  transform: rotate(180deg);
}

.kite-motion-enabled [data-motion-popover],
.kite-motion-enabled [role='menu'],
.kite-motion-enabled [role='dialog'] {
  animation: kite-motion-pop-in var(--kite-motion-row) var(--kite-motion-pop) both;
}

@keyframes kite-motion-pop-in {
  from { opacity: 0; transform: translate3d(0,5px,0) scale(.985); }
  to { opacity: 1; transform: translate3d(0,0,0) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .kite-motion-enabled *,
  .kite-motion-enabled *::before,
  .kite-motion-enabled *::after {
    scroll-behavior: auto !important;
    animation-duration: .001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .001ms !important;
  }
}
`;

let styleInstalled = false;

function ensureStyles() {
  if (styleInstalled || typeof document === 'undefined') return;
  const existing = document.getElementById('sterling-kite-interaction-motion');
  if (existing) {
    styleInstalled = true;
    return;
  }
  const style = document.createElement('style');
  style.id = 'sterling-kite-interaction-motion';
  style.textContent = MOTION_CSS;
  document.head.appendChild(style);
  styleInstalled = true;
}

function matchingRows(node: Node): HTMLElement[] {
  if (!(node instanceof HTMLElement)) return [];
  const out: HTMLElement[] = [];
  if (node.matches(ROW_SELECTOR)) out.push(node);
  node.querySelectorAll<HTMLElement>(ROW_SELECTOR).forEach((el) => out.push(el));
  return out;
}

function isVisibleRect(rect: DOMRect) {
  return rect.width > 0 && rect.height > 0
    && rect.bottom >= 0 && rect.right >= 0
    && rect.top <= window.innerHeight && rect.left <= window.innerWidth;
}

function animateAdded(el: HTMLElement) {
  if (el.dataset.motionEntered === '1' || typeof el.animate !== 'function') return;
  el.dataset.motionEntered = '1';
  el.animate(
    [
      { opacity: 0, transform: 'translate3d(0,6px,0) scale(.995)' },
      { opacity: 1, transform: 'translate3d(0,0,0) scale(1)' },
    ],
    { duration: 180, easing: 'cubic-bezier(.16,1,.3,1)' },
  );
}

function animateRemoved(el: HTMLElement, rect: DOMRect) {
  if (!isVisibleRect(rect) || typeof el.animate !== 'function') return;
  const clone = el.cloneNode(true) as HTMLElement;
  clone.removeAttribute('id');
  clone.querySelectorAll('[id]').forEach((child) => child.removeAttribute('id'));
  Object.assign(clone.style, {
    position: 'fixed',
    zIndex: '100000',
    pointerEvents: 'none',
    margin: '0',
    left: `${rect.left}px`,
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
    boxSizing: 'border-box',
    overflow: 'hidden',
  });
  document.body.appendChild(clone);
  const animation = clone.animate(
    [
      { opacity: 1, transform: 'translate3d(0,0,0) scale(1)' },
      { opacity: 0, transform: 'translate3d(8px,-1px,0) scale(.985)' },
    ],
    { duration: 145, easing: 'cubic-bezier(.4,0,1,1)' },
  );
  animation.finished.catch(() => undefined).finally(() => clone.remove());
}

/**
 * Adds low-cost, app-wide interaction feedback and structural row motion.
 *
 * Structural animation is event-driven: positions are sampled only immediately
 * before a likely user mutation, never on a continuous frame loop. Mutation
 * observation is restricted to row-shaped additions/removals; quote text ticks
 * and chart updates are ignored.
 */
export function KiteInteractionMotion({ children }: { children: React.ReactNode }) {
  const rootRef = React.useRef<HTMLDivElement>(null);
  const beforeRects = React.useRef(new Map<HTMLElement, DOMRect>());
  const reducedRef = React.useRef(false);
  const scheduledRef = React.useRef<number | null>(null);

  ensureStyles();

  React.useEffect(() => {
    const root = rootRef.current;
    if (!root || typeof window === 'undefined') return;

    document.body.classList.add('kite-motion-enabled');
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    reducedRef.current = !!media?.matches;
    const onMotionPreference = (event: MediaQueryListEvent) => { reducedRef.current = event.matches; };
    media?.addEventListener?.('change', onMotionPreference);

    const captureRects = () => {
      if (reducedRef.current) return;
      const rows = Array.from(root.querySelectorAll<HTMLElement>(ROW_SELECTOR)).slice(0, 180);
      const next = new Map<HTMLElement, DOMRect>();
      for (const row of rows) {
        const rect = row.getBoundingClientRect();
        if (isVisibleRect(rect)) next.set(row, rect);
      }
      beforeRects.current = next;
    };

    const runFlip = () => {
      scheduledRef.current = null;
      if (reducedRef.current || beforeRects.current.size === 0) return;
      for (const [row, before] of beforeRects.current) {
        if (!row.isConnected || typeof row.animate !== 'function') continue;
        const after = row.getBoundingClientRect();
        const dx = before.left - after.left;
        const dy = before.top - after.top;
        if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
        row.animate(
          [
            { transform: `translate3d(${dx}px,${dy}px,0)` },
            { transform: 'translate3d(0,0,0)' },
          ],
          { duration: 210, easing: 'cubic-bezier(.2,.8,.2,1)' },
        );
      }
      beforeRects.current.clear();
    };

    const scheduleFlip = () => {
      if (scheduledRef.current != null) cancelAnimationFrame(scheduledRef.current);
      scheduledRef.current = requestAnimationFrame(runFlip);
    };

    const observer = new MutationObserver((records) => {
      if (reducedRef.current) return;
      let structural = false;
      for (const record of records) {
        if (record.type !== 'childList') continue;
        for (const node of Array.from(record.removedNodes)) {
          for (const row of matchingRows(node)) {
            const rect = beforeRects.current.get(row);
            if (rect) animateRemoved(row, rect);
            structural = true;
          }
        }
        for (const node of Array.from(record.addedNodes)) {
          for (const row of matchingRows(node)) {
            animateAdded(row);
            structural = true;
          }
        }
      }
      if (structural) scheduleFlip();
    });

    const onPointerDown = (event: Event) => {
      const target = event.target as Element | null;
      if (!target?.closest('button, a[href], [role="button"], [draggable="true"], input, select, summary, label')) return;
      captureRects();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Enter' && event.key !== ' ' && event.key !== 'Delete' && event.key !== 'Backspace') return;
      captureRects();
    };
    const onDragStart = () => captureRects();

    root.addEventListener('pointerdown', onPointerDown, true);
    root.addEventListener('keydown', onKeyDown, true);
    root.addEventListener('dragstart', onDragStart, true);
    observer.observe(root, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      root.removeEventListener('pointerdown', onPointerDown, true);
      root.removeEventListener('keydown', onKeyDown, true);
      root.removeEventListener('dragstart', onDragStart, true);
      media?.removeEventListener?.('change', onMotionPreference);
      if (scheduledRef.current != null) cancelAnimationFrame(scheduledRef.current);
      document.body.classList.remove('kite-motion-enabled');
    };
  }, []);

  return <div ref={rootRef} style={{ display: 'contents' }}>{children}</div>;
}

export default KiteInteractionMotion;
