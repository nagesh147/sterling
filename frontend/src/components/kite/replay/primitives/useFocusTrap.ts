import React, { useEffect, useRef } from 'react';

const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export function focusableWithin(root: HTMLElement | null): HTMLElement[] {
  if (!root) return [];
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el.offsetParent !== null || el === document.activeElement,
  );
}

/**
 * Trap Tab inside `ref` while `active`, and return focus where it came from.
 *
 * Returning focus matters more than trapping it: a dialog that dumps focus onto
 * `<body>` when it closes strands a keyboard user at the top of the document,
 * which is how the previous overlays behaved.
 */
export function useFocusTrap(
  ref: React.RefObject<HTMLElement | null>,
  active: boolean,
  opts: { onEscape?: () => void; initialFocus?: () => HTMLElement | null } = {},
) {
  const restoreTo = useRef<HTMLElement | null>(null);
  const { onEscape, initialFocus } = opts;

  useEffect(() => {
    if (!active) return;
    restoreTo.current = document.activeElement as HTMLElement | null;

    const node = ref.current;
    const first = initialFocus?.() ?? focusableWithin(node)[0] ?? node;
    // Defer past the mount animation so the browser does not scroll to a node
    // that is still transforming into place.
    const raf = requestAnimationFrame(() => first?.focus?.());

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onEscape?.();
        return;
      }
      if (e.key !== 'Tab') return;
      const items = focusableWithin(ref.current);
      if (!items.length) return;
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      const current = document.activeElement;
      if (e.shiftKey && (current === firstEl || !ref.current?.contains(current))) {
        e.preventDefault();
        lastEl.focus();
      } else if (!e.shiftKey && current === lastEl) {
        e.preventDefault();
        firstEl.focus();
      }
    };

    document.addEventListener('keydown', onKey, true);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('keydown', onKey, true);
      restoreTo.current?.focus?.();
    };
  }, [active, ref, onEscape, initialFocus]);
}

/** Lock background scroll while an overlay is up. */
export function useScrollLock(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [active]);
}
