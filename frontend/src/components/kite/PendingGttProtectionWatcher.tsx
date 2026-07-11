import { useEffect, useRef } from 'react';
import { useKiteOrders, usePlaceKiteGtt } from '../../hooks/useKite';
import { useKitePendingProtectionStore } from '../../store/useKitePendingProtectionStore';
import { notifyOrder } from '../../store/useKiteNotifications';

const TERMINAL_NON_FILL = new Set(['CANCELLED', 'REJECTED']);

/**
 * Always-mounted (see KiteTab.tsx). Watches the shared, already-polling
 * `useKiteOrders` cache for pending protective-GTT entries reaching a
 * terminal state: fires the GTT on COMPLETE, drops the entry silently on
 * CANCELLED/REJECTED. Deliberately reuses the existing 5s-interval order
 * poll rather than opening a second WebSocket connection.
 */
export function PendingGttProtectionWatcher() {
  const pending = useKitePendingProtectionStore((s) => s.pending);
  const remove = useKitePendingProtectionStore((s) => s.remove);
  const { data: orders } = useKiteOrders(pending.length > 0);
  const placeGtt = usePlaceKiteGtt();
  const firing = useRef(new Set<string>());

  useEffect(() => {
    if (!orders || pending.length === 0) return;
    for (const entry of pending) {
      if (firing.current.has(entry.orderId)) continue;
      const order = orders.find((o: any) => o.order_id === entry.orderId);
      if (!order) continue;
      if (order.status === 'COMPLETE') {
        firing.current.add(entry.orderId);
        placeGtt.mutate(entry.gtt, {
          onError: (err: any) => {
            notifyOrder({
              kind: 'rejected',
              title: 'Protective GTT failed',
              message: `Order ${entry.orderId} filled, but the protective GTT could not be created: ${err?.message || 'unknown error'}. Consider setting a manual stop.`,
            });
          },
        });
        remove(entry.orderId);
      } else if (TERMINAL_NON_FILL.has(order.status)) {
        remove(entry.orderId);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orders, pending]);

  return null;
}
