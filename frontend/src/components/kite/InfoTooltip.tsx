import React from 'react';
import { createPortal } from 'react-dom';
import { k } from '../../styles/kiteUI';

// Splits on this pane's existing "label — detail" tooltip convention so the
// card gets a bold heading for free, without rewriting any copy.
function splitLabel(text: string): [string | null, string] {
  const idx = text.indexOf(' — ');
  if (idx === -1 || idx > 60) return [null, text];
  return [text.slice(0, idx), text.slice(idx + 3)];
}

/** Rich hover tooltip — replaces the native `title` attribute's OS-drawn
 *  black box (no theme, clipped by scrolling table rows) with a themed card
 *  portaled to <body>. Clones the single child instead of wrapping it in a
 *  new element, so it never disturbs the child's own flex-item sizing (most
 *  of these cells carry `width`/`flexShrink`/`textAlign` that must stay
 *  direct flex children of the row). Renders nothing extra when `text` is
 *  falsy, matching the old behavior of an absent/undefined `title`. */
export function Tip({ text, children }: { text?: string; children: React.ReactElement }) {
  const anchorRef = React.useRef<HTMLElement | null>(null);
  const [open, setOpen] = React.useState(false);
  const [visible, setVisible] = React.useState(false);
  const [pos, setPos] = React.useState<{ top: number; left: number; placement: 'top' | 'bottom' } | null>(null);
  const hideTimer = React.useRef<number | null>(null);
  // Read once per mount: a tooltip that animates against an explicit OS
  // preference is exactly the kind of motion the preference exists to stop.
  const reduceMotion = React.useMemo(
    () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
    [],
  );

  const show = () => {
    if (hideTimer.current) { window.clearTimeout(hideTimer.current); hideTimer.current = null; }
    const el = anchorRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const placement: 'top' | 'bottom' = rect.top > 130 ? 'top' : 'bottom';
    setPos({
      top: placement === 'top' ? rect.top - 9 : rect.bottom + 9,
      left: Math.min(Math.max(rect.left + rect.width / 2, 150), window.innerWidth - 150),
      placement,
    });
    setOpen(true);
    requestAnimationFrame(() => setVisible(true));
  };
  const hide = () => {
    setVisible(false);
    hideTimer.current = window.setTimeout(() => setOpen(false), 100);
  };

  React.useEffect(() => {
    if (!open) return;
    // A scrolled table row would otherwise leave a stale tooltip floating
    // over the wrong cell — just dismiss it, same as most native tooltips.
    const onScroll = () => hide();
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onScroll);
    return () => {
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onScroll);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!text) return children;

  const [label, detail] = splitLabel(text);
  const child = React.cloneElement(children as React.ReactElement<any>, {
    ref: anchorRef,
    onMouseEnter: show,
    onMouseLeave: hide,
    onFocus: show,
    onBlur: hide,
  } as any);

  return (
    <>
      {child}
      {open && pos && createPortal(
        <div
          role="tooltip"
          style={{
            position: 'fixed',
            top: pos.top,
            left: pos.left,
            transform: `translate(-50%, ${pos.placement === 'top' ? '-100%' : '0'}) translateY(${visible || reduceMotion ? 0 : pos.placement === 'top' ? 3 : -3}px)`,
            opacity: visible ? 1 : 0,
            transition: reduceMotion ? 'none' : 'opacity 110ms ease-out, transform 110ms ease-out',
            zIndex: 20000,
            pointerEvents: 'none',
            maxWidth: 290,
            background: 'var(--k-bg)',
            // A hairline of near-black was invisible against a dark surface,
            // leaving the card floating with no edge. The token carries an
            // edge in both themes, and the shadow deepens for dark, where a
            // light wash reads as fog rather than elevation.
            border: '1px solid var(--k-border-strong)',
            borderRadius: 8,
            boxShadow: '0 12px 28px rgba(0, 0, 0, .28), 0 2px 6px rgba(0, 0, 0, .14)',
            padding: '9px 11px',
            fontFamily: k.fontFamily,
          }}
        >
          {label && (
            <div style={{ fontSize: 11, fontWeight: 700, color: k.text, marginBottom: 3, letterSpacing: 0.1 }}>
              {label}
            </div>
          )}
          <div style={{ fontSize: 11, color: label ? k.dim : k.text, lineHeight: 1.5 }}>{detail}</div>
          <span
            aria-hidden
            style={{
              position: 'absolute', left: '50%', transform: 'translateX(-50%)', width: 0, height: 0,
              borderLeft: '6px solid transparent', borderRight: '6px solid transparent',
              ...(pos.placement === 'top'
                ? { bottom: -6, borderTop: '6px solid var(--k-bg)' }
                : { top: -6, borderBottom: '6px solid var(--k-bg)' }),
              filter: 'drop-shadow(0 0 0 var(--k-border-strong))',
            }}
          />
        </div>,
        document.body,
      )}
    </>
  );
}
