/**
 * macOS-style scrollbar auto-hide. The CSS in globals.css reveals a scrollbar on
 * hover; this adds the other half of the native feel — reveal *while scrolling*
 * (trackpad/keyboard/programmatic, no hover needed), then fade out when idle.
 *
 * One capture-phase listener catches scroll on any descendant scroll container and
 * tags it with `.is-scrolling` for a short window. Cheap: a class toggle + one
 * per-element timeout, no per-frame work.
 */
const IDLE_MS = 700;
const timers = new WeakMap<HTMLElement, number>();

function onScroll(e: Event): void {
  const el = e.target as HTMLElement;
  if (!el || el.nodeType !== 1 || !el.classList) return;
  el.classList.add('is-scrolling');
  const prev = timers.get(el);
  if (prev) clearTimeout(prev);
  timers.set(el, window.setTimeout(() => el.classList.remove('is-scrolling'), IDLE_MS));
}

let installed = false;

/** Attach the global scroll listener once. Safe to call multiple times. */
export function installScrollAutohide(): void {
  if (installed || typeof document === 'undefined') return;
  installed = true;
  document.addEventListener('scroll', onScroll, { capture: true, passive: true });
}
