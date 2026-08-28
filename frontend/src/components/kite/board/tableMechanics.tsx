import React from 'react';

/**
 * Table mechanics shared by both signal tables.
 *
 * Drag-to-reorder and per-row sideways scrolling were built inside SuperTrend's
 * bespoke pane, which is most of the reason that pane still exists: they were the
 * features a move to the shared board would have cost. They are not
 * SuperTrend-specific in any way, so they live here and either table can offer
 * them.
 */

/** Drag-to-reorder header cell wrapper. Uses raw pointer events (not native
 *  HTML5 draggable/dragstart) because native drag-and-drop's gesture
 *  recognition is unreliable for plain `<div>`s across browsers/trackpads —
 *  many devices never fire `dragstart` for a generic element, which is why
 *  this looked wired up correctly yet didn't respond to a real drag. Pointer
 *  events are dispatched directly for every mouse/touch/pen down-move-up, so
 *  there's no browser-level gesture heuristic in the way. */
export function DraggableColHeader<G extends string>({
  colKey, group, width, reorder, children, enabled = true, flex, minWidth,
}: {
  colKey: string;
  /**
   * Which run of columns this heading belongs to.
   *
   * SuperTrend keeps two independent sections (one flowing after the instrument,
   * one pinned past the action buttons) and a heading may only be dropped inside
   * its own. A table with a single run passes one constant for every heading.
   */
  group: G;
  width: number;
  /**
   * For a column that is sized by flex rather than by a fixed width.
   *
   * Without this the wrapper imposed `width: <the column's width>` on every
   * heading — and a flex-sized column declares `width: 0`, because the number is
   * a placeholder it never uses. The instrument heading therefore rendered a
   * 200px label inside a 0px box with `flex-shrink: 0`, overflowed it, and
   * painted on top of itself and the heading beside it: "INSTRUMENT" came out as
   * "INSEROMENT".
   *
   * When `flex` is given the wrapper becomes layout-transparent — it takes the
   * column's flex sizing and lays its child out as a flex item, so wrapping a
   * heading for dragging changes nothing about where it sits.
   */
  flex?: string;
  minWidth?: number;
  /**
   * Generic over the group so a caller keeps its own narrow union.
   *
   * A plain `string` here does not work: `reorder` is contravariant in its
   * parameter, so SuperTrend's `(group: 'left' | 'right', ...) => void` is not
   * assignable to `(group: string, ...) => void` -- it cannot accept the group
   * names it does not know about.
   */
  reorder: (group: G, fromKey: string, toKey: string) => void;
  children: React.ReactNode;
  /**
   * Off leaves the heading a plain sort control.
   *
   * The wrapper still renders with the same width and data attributes, so the
   * header lays out identically -- only the pointer handling and the grab cursor
   * go. Returning a different element shape here would shift the columns.
   */
  enabled?: boolean;
}) {
  const draggingRef = React.useRef(false);
  const startRef = React.useRef<{ x: number; y: number } | null>(null);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    startRef.current = { x: e.clientX, y: e.clientY };
    draggingRef.current = false;

    const clearHighlight = () => {
      document.querySelectorAll('.col-drag-over').forEach((el) => el.classList.remove('col-drag-over'));
    };
    const targetAt = (x: number, y: number) =>
      document.elementFromPoint(x, y)?.closest('[data-col-key]') as HTMLElement | null;

    const onMove = (ev: PointerEvent) => {
      const start = startRef.current;
      if (!start) return;
      if (!draggingRef.current) {
        // Small movement threshold so a plain click still reaches the sort handler.
        if (Math.abs(ev.clientX - start.x) < 4 && Math.abs(ev.clientY - start.y) < 4) return;
        draggingRef.current = true;
        document.body.style.cursor = 'grabbing';
      }
      clearHighlight();
      const el = targetAt(ev.clientX, ev.clientY);
      if (el && el.getAttribute('data-col-group') === group && el.getAttribute('data-col-key') !== colKey) {
        el.classList.add('col-drag-over');
      }
    };
    const onUp = (ev: PointerEvent) => {
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      document.body.style.cursor = '';
      clearHighlight();
      if (draggingRef.current) {
        const el = targetAt(ev.clientX, ev.clientY);
        const toKey = el?.getAttribute('data-col-key');
        if (toKey && el?.getAttribute('data-col-group') === group && toKey !== colKey) {
          reorder(group, colKey, toKey);
        }
        // A drag that ends over a different header would otherwise still fire
        // that header's onClick (sort) right after pointerup - swallow it once.
        document.addEventListener('click', (ce) => { ce.stopPropagation(); ce.preventDefault(); }, { capture: true, once: true });
      }
      draggingRef.current = false;
      startRef.current = null;
    };
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
  };

  return (
    <div
      data-col-key={colKey}
      data-col-group={group}
      onPointerDown={enabled ? onPointerDown : undefined}
      style={{
        ...(flex
          // Flex-sized: pass the sizing through and become a flex container, so
          // the child's own flex still fills the wrapper.
          ? { flex, minWidth, display: 'flex', alignItems: 'center' }
          : { width, flexShrink: 0 }),
        cursor: enabled ? 'grab' : undefined,
        userSelect: 'none',
        touchAction: enabled ? 'none' : undefined,
      }}
      title={enabled ? 'Drag to reorder column' : undefined}
    >
      {children}
    </div>
  );
}

/**
 * Keep every row's sideways scroll in step with the header's.
 *
 * When rows scroll independently, a row scrolled 80px right puts its LTP under
 * the header's Chg. label — so the offsets have to be shared. Driven off the DOM
 * rather than React state on purpose: this fires on every scroll frame, and
 * re-rendering a table of option legs at that rate is what the native scroll was
 * chosen to avoid.
 *
 * `selector` names the rows to keep in step, so each table passes its own class
 * and two tables on one screen cannot drag each other sideways.
 */
export function makeHscrollSync(selector: string) {
  return (e: React.UIEvent<HTMLDivElement>) => {
    const left = e.currentTarget.scrollLeft;
    document.querySelectorAll(selector).forEach((el) => {
      if (el !== e.currentTarget) (el as HTMLElement).scrollLeft = left;
    });
  };
}
