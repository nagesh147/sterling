import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useKiteOrderUpdates, useKiteStatus } from '../../hooks/useKite';
import { useKiteNotifications, notifyOrder, type KiteNotif, type NotifKind } from '../../store/useKiteNotifications';
import { useMacKite } from '../../hooks/useMacKite';

// Kite's own colour language: cancelled=blue, complete=green, rejected=red,
// open/pending=amber, placed=blue.
const COLOR: Record<NotifKind, string> = {
  placed: 'var(--k-blue-kite)', open: 'var(--k-amber)', complete: 'var(--k-green)',
  cancelled: 'var(--k-blue-kite)', rejected: 'var(--k-red-strong)', error: 'var(--k-red-strong)', info: 'var(--k-blue-kite)',
};

function statusToKind(status: string): NotifKind {
  const s = (status || '').toUpperCase();
  if (s.includes('REJECT')) return 'rejected';
  if (s.includes('CANCEL')) return 'cancelled';
  if (s.includes('COMPLETE')) return 'complete';
  if (s.includes('OPEN') || s.includes('TRIGGER') || s.includes('PENDING') || s.includes('RECEIVED')) return 'open';
  return 'info';
}

const TITLE: Record<NotifKind, string> = {
  placed: 'Order placed', open: 'Open', complete: 'Complete',
  cancelled: 'Cancelled', rejected: 'Rejected', error: 'Order failed', info: 'Order update',
};

// Live order postbacks (Kite → stream WS) → notification store. Dormant for paper
// (no live WS); paper placements are surfaced by the mutation hooks instead.
function OrderUpdateBridge() {
  const { data: status } = useKiteStatus();
  const live = !!status?.connected && !status?.is_paper;
  const update = useKiteOrderUpdates(live);
  useEffect(() => {
    if (!update) return;
    const kind = statusToKind(update.status || '');
    const side = (update.transaction_type || '').toUpperCase();
    const verb = kind === 'complete' ? 'is complete' : kind === 'cancelled' ? 'is cancelled'
      : kind === 'rejected' ? 'is rejected' : kind === 'open' ? 'is open' : 'updated';
    notifyOrder({
      kind, title: TITLE[kind],
      message: `${side ? side + ' ' : ''}${update.tradingsymbol ?? 'Order'} ${verb}.`,
      orderId: update.order_id,
    });
  }, [update]);
  return null;
}

function Toast({ n, mac }: { n: KiteNotif; mac?: boolean }) {
  const dismiss = useKiteNotifications((s) => s.dismiss);
  const color = COLOR[n.kind] ?? 'var(--k-blue-kite)';
  useEffect(() => {
    const ttl = n.kind === 'rejected' || n.kind === 'error' ? 9000 : 6000;
    const t = window.setTimeout(() => dismiss(n.id), ttl);
    return () => window.clearTimeout(t);
  }, [n.id, n.kind, dismiss]);
  return (
    <div style={{
      display: 'flex', background: 'var(--k-bg)', borderRadius: 8, overflow: 'hidden',
      boxShadow: '0 8px 28px rgba(0,0,0,0.16)', border: '1px solid var(--k-border-3)',
      // In Mac mode the parent motion.div drives the spring entrance, so the
      // CSS keyframe is disabled to avoid a double-animation.
      minWidth: 300, maxWidth: 380, animation: mac ? 'none' : 'kn-in .18s ease',
    }}>
      <div style={{ width: 6, background: color, flexShrink: 0 }} />
      <div style={{ padding: '12px 14px', flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <span style={{ color, fontSize: 15, fontWeight: 700 }}>{n.title}</span>
          <button onClick={() => dismiss(n.id)} aria-label="Dismiss"
            style={{ background: 'none', border: 'none', color: 'var(--k-dim)', cursor: 'pointer', fontSize: 17, lineHeight: 1, padding: 0, flexShrink: 0 }}>×</button>
        </div>
        <div style={{ fontSize: 13, color: 'var(--k-text)', marginTop: 3, lineHeight: 1.45, wordBreak: 'break-word' }}>{n.message}</div>
        {n.orderId && <div style={{ fontSize: 11, color: 'var(--k-dim)', marginTop: 6, fontFamily: 'monospace' }}>#{n.orderId}</div>}
      </div>
    </div>
  );
}

// Stack of order toasts, bottom-right. Portaled to <body> with zIndex above
// .term-root (10000) so it isn't trapped by the app's z-index:1 children — see
// reference_modal_stacking_term_root.
export function KiteNotifications() {
  const items = useKiteNotifications((s) => s.items);
  const { on, motion, AnimatePresence, sp } = useMacKite();
  return (
    <>
      <OrderUpdateBridge />
      {createPortal(
        <div style={{ position: 'fixed', right: 20, bottom: 20, zIndex: 100000, display: 'flex', flexDirection: 'column', gap: 10, pointerEvents: 'none' }}>
          <style>{'@keyframes kn-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }'}</style>
          {on ? (
            // Mac mode: spring entrance from the right + layout reflow as the stack grows/shrinks.
            <AnimatePresence initial={false}>
              {items.map((n) => (
                <motion.div
                  key={n.id}
                  layout
                  initial={{ opacity: 0, x: 40, scale: 0.96 }}
                  animate={{ opacity: 1, x: 0, scale: 1 }}
                  exit={{ opacity: 0, x: 40, scale: 0.96 }}
                  transition={sp('standard')}
                  style={{ pointerEvents: 'auto' }}
                >
                  <Toast n={n} mac />
                </motion.div>
              ))}
            </AnimatePresence>
          ) : (
            items.map((n) => (
              <div key={n.id} style={{ pointerEvents: 'auto' }}><Toast n={n} /></div>
            ))
          )}
        </div>,
        document.body,
      )}
    </>
  );
}

export default KiteNotifications;
