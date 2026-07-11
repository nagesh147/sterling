# Kite Order-Management Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the dead-but-built management actions across Orders/GTT/Alerts/bulk-position-actions, fix the protective-GTT-on-fill timing bug, add Holdings T1 distinction + partial conversion, itemize charges, and document Auctions/MTF as explicit backlog.

**Architecture:** Additive/wiring changes to existing panes, reusing the established modal convention (`k.bg`/`borderRadius:4`/`rgba(0,0,0,0.06)` backdrop, first established in `OrderWindow.tsx` and already matched by `BasketPane.tsx`/`KitePortfolioAnalyticsModal.tsx`/`KiteSettingsPopover.tsx`) and the `KiteActionButtons` optional-prop-per-action pattern. One new small store (`useKitePendingProtectionStore`) and one new always-mounted watcher component for the GTT-on-fill fix.

**Tech Stack:** React 19 + TypeScript, Zustand, TanStack Query, Vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-07-11-kite-order-management-parity-design.md`

---

## Task 1: Pending-protection store (pure state, no UI)

**Files:**
- Create: `frontend/src/store/useKitePendingProtectionStore.ts`
- Create: `frontend/src/store/useKitePendingProtectionStore.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/store/useKitePendingProtectionStore.test.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { useKitePendingProtectionStore } from './useKitePendingProtectionStore';
import type { PlaceGttBody } from '../types/kite';

const gtt = (): PlaceGttBody => ({
  trigger_type: 'single', tradingsymbol: 'INFY', exchange: 'NSE',
  last_price: 1500, trigger_values: [1400], orders: [
    { tradingsymbol: 'INFY', exchange: 'NSE', transaction_type: 'SELL', quantity: 10, order_type: 'LIMIT', product: 'CNC', price: 1400 },
  ],
});

beforeEach(() => {
  useKitePendingProtectionStore.setState({ pending: [] });
});

describe('useKitePendingProtectionStore', () => {
  it('adds a pending protection entry keyed by order id', () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    expect(useKitePendingProtectionStore.getState().pending).toHaveLength(1);
    expect(useKitePendingProtectionStore.getState().pending[0].orderId).toBe('o1');
  });

  it('removes a pending entry by order id', () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    useKitePendingProtectionStore.getState().add({ orderId: 'o2', gtt: gtt() });
    useKitePendingProtectionStore.getState().remove('o1');
    const pending = useKitePendingProtectionStore.getState().pending;
    expect(pending).toHaveLength(1);
    expect(pending[0].orderId).toBe('o2');
  });

  it('removing a non-existent id is a no-op', () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    useKitePendingProtectionStore.getState().remove('does-not-exist');
    expect(useKitePendingProtectionStore.getState().pending).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/store/useKitePendingProtectionStore.test.ts`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the store**

Create `frontend/src/store/useKitePendingProtectionStore.ts`:

```ts
import { create } from 'zustand';
import type { PlaceGttBody } from '../types/kite';

export interface PendingProtection {
  orderId: string;
  gtt: PlaceGttBody;
}

interface PendingProtectionState {
  pending: PendingProtection[];
  add: (entry: PendingProtection) => void;
  remove: (orderId: string) => void;
}

/**
 * Orders placed with a Stoploss/Target toggle in OrderWindow need their
 * protective GTT created once the order actually FILLS, not the instant
 * it's accepted — OrderWindow closes immediately on submit, so this state
 * has to outlive the ticket. See PendingGttProtectionWatcher (mounted once
 * near the app root) for the consumer side.
 */
export const useKitePendingProtectionStore = create<PendingProtectionState>((set) => ({
  pending: [],
  add: (entry) => set((s) => ({ pending: [...s.pending, entry] })),
  remove: (orderId) => set((s) => ({ pending: s.pending.filter((p) => p.orderId !== orderId) })),
}));
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/store/useKitePendingProtectionStore.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/store/useKitePendingProtectionStore.ts frontend/src/store/useKitePendingProtectionStore.test.ts
git commit -m "feat(kite): add pending-GTT-protection store"
```

**IMPORTANT — commit hygiene:** Stage ONLY the two exact files above. Do NOT run `git add -A`/`git add .`/`git add <directory>`.

---

## Task 2: Wire pending-protection into OrderWindow + add the watcher

**Files:**
- Modify: `frontend/src/components/kite/OrderWindow.tsx`
- Create: `frontend/src/components/kite/PendingGttProtectionWatcher.tsx`
- Create: `frontend/src/components/kite/__tests__/PendingGttProtectionWatcher.test.tsx`
- Modify: `frontend/src/components/kite/KiteTab.tsx`

- [ ] **Step 1: Stop firing the GTT immediately in OrderWindow**

In `frontend/src/components/kite/OrderWindow.tsx`, add the import:

```tsx
import { useKitePendingProtectionStore } from '../../store/useKitePendingProtectionStore';
```

Add a hook call near the other hooks (alongside `placeOrder`/`placeGtt`):

```tsx
  const addPendingProtection = useKitePendingProtectionStore((s) => s.add);
```

Find `submit()`'s `onSuccess` callback — it currently looks like this:

```tsx
      onSuccess: (res: any) => {
        // Carry positions can attach a protective GTT created on fill.
        if (product !== 'MIS' && (slOn || tgtOn)) {
          const base = needsPrice(orderType) ? price : instr.lastPrice;
          const gtt = buildProtectionGtt({
            tradingsymbol: instr.symbol, exchange: instr.exchange, entrySide: side, quantity: qty,
            product, basePrice: base, slPct: slOn ? slPct : undefined, tgtPct: tgtOn ? tgtPct : undefined,
          });
          if (gtt) placeGtt.mutate(gtt);
        }
        onPlaced?.(res?.order_id || ''); onClose();
      },
```

Replace the `if (gtt) placeGtt.mutate(gtt);` line with a queue instead of an immediate fire (keep everything else in this block unchanged):

```tsx
      onSuccess: (res: any) => {
        // Carry positions can attach a protective GTT — queued until the
        // order actually fills (see PendingGttProtectionWatcher), not fired
        // on mere submission-acceptance.
        if (product !== 'MIS' && (slOn || tgtOn)) {
          const base = needsPrice(orderType) ? price : instr.lastPrice;
          const gtt = buildProtectionGtt({
            tradingsymbol: instr.symbol, exchange: instr.exchange, entrySide: side, quantity: qty,
            product, basePrice: base, slPct: slOn ? slPct : undefined, tgtPct: tgtOn ? tgtPct : undefined,
          });
          if (gtt && res?.order_id) addPendingProtection({ orderId: res.order_id, gtt });
        }
        onPlaced?.(res?.order_id || ''); onClose();
      },
```

The `placeGtt` mutation hook declared earlier in this file (`const placeGtt = usePlaceKiteGtt();`) is no longer used by `submit()` — but leave the declaration in place if anything else in the file references it; if `placeGtt` is now unused anywhere else in `OrderWindow.tsx` (check with a search), remove its declaration and its import usage to avoid an unused-variable lint warning (but do NOT remove `usePlaceKiteGtt` from the import list if it's still imported for other reasons — check first).

- [ ] **Step 2: Write the failing test for the watcher**

Create `frontend/src/components/kite/__tests__/PendingGttProtectionWatcher.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import React from 'react';
import { PendingGttProtectionWatcher } from '../PendingGttProtectionWatcher';
import { useKitePendingProtectionStore } from '../../../store/useKitePendingProtectionStore';

const mockGttMutate = vi.fn();
let mockOrders: any[] = [];
vi.mock('../../../hooks/useKite', () => ({
  useKiteOrders: () => ({ data: mockOrders }),
  usePlaceKiteGtt: () => ({ mutate: mockGttMutate }),
}));

const gtt = () => ({
  trigger_type: 'single' as const, tradingsymbol: 'INFY', exchange: 'NSE',
  last_price: 1500, trigger_values: [1400], orders: [
    { tradingsymbol: 'INFY', exchange: 'NSE', transaction_type: 'SELL' as const, quantity: 10, order_type: 'LIMIT', product: 'CNC', price: 1400 },
  ],
});

beforeEach(() => {
  useKitePendingProtectionStore.setState({ pending: [] });
  mockGttMutate.mockReset();
  mockOrders = [];
});

describe('PendingGttProtectionWatcher', () => {
  it('does nothing while the pending order has not reached a terminal status', () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    mockOrders = [{ order_id: 'o1', status: 'OPEN' }];
    render(<PendingGttProtectionWatcher />);
    expect(mockGttMutate).not.toHaveBeenCalled();
    expect(useKitePendingProtectionStore.getState().pending).toHaveLength(1);
  });

  it('fires the protective GTT and clears the entry once the order is COMPLETE', async () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    mockOrders = [{ order_id: 'o1', status: 'COMPLETE' }];
    render(<PendingGttProtectionWatcher />);
    await waitFor(() => expect(mockGttMutate).toHaveBeenCalledTimes(1));
    expect(mockGttMutate).toHaveBeenCalledWith(gtt());
    await waitFor(() => expect(useKitePendingProtectionStore.getState().pending).toHaveLength(0));
  });

  it('clears the entry WITHOUT firing the GTT if the order is cancelled or rejected', async () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    mockOrders = [{ order_id: 'o1', status: 'CANCELLED' }];
    render(<PendingGttProtectionWatcher />);
    await waitFor(() => expect(useKitePendingProtectionStore.getState().pending).toHaveLength(0));
    expect(mockGttMutate).not.toHaveBeenCalled();
  });

  it('leaves unrelated pending entries alone', async () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    useKitePendingProtectionStore.getState().add({ orderId: 'o2', gtt: gtt() });
    mockOrders = [{ order_id: 'o1', status: 'COMPLETE' }];
    render(<PendingGttProtectionWatcher />);
    await waitFor(() => expect(mockGttMutate).toHaveBeenCalledTimes(1));
    const pending = useKitePendingProtectionStore.getState().pending;
    expect(pending).toHaveLength(1);
    expect(pending[0].orderId).toBe('o2');
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/PendingGttProtectionWatcher.test.tsx`
Expected: FAIL — `../PendingGttProtectionWatcher` doesn't exist.

- [ ] **Step 4: Implement the watcher**

Create `frontend/src/components/kite/PendingGttProtectionWatcher.tsx`:

```tsx
import { useEffect, useRef } from 'react';
import { useKiteOrders, usePlaceKiteGtt } from '../../hooks/useKite';
import { useKitePendingProtectionStore } from '../../store/useKitePendingProtectionStore';

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
        placeGtt.mutate(entry.gtt);
        remove(entry.orderId);
      } else if (TERMINAL_NON_FILL.has(order.status)) {
        remove(entry.orderId);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orders, pending]);

  return null;
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/PendingGttProtectionWatcher.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 6: Mount the watcher once in KiteTab.tsx**

In `frontend/src/components/kite/KiteTab.tsx`, add the import alongside the existing `KiteNotifications` import:

```tsx
import { PendingGttProtectionWatcher } from './PendingGttProtectionWatcher';
```

Render it once, alongside the existing `<KiteNotifications />` render (find where that's rendered in the component's return and add the new component as a sibling):

```tsx
      <PendingGttProtectionWatcher />
```

- [ ] **Step 7: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Run `cd frontend && npx vitest run` — expect the established pre-existing failure baseline (`PositionHeatmap.snapshot.test.tsx`, two Playwright specs picked up by the vitest glob, `SterlingKiteEnginePane.hybrid.test.tsx`'s missing QueryClientProvider) plus your new tests passing, no other new failures.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/kite/OrderWindow.tsx frontend/src/components/kite/PendingGttProtectionWatcher.tsx frontend/src/components/kite/__tests__/PendingGttProtectionWatcher.test.tsx frontend/src/components/kite/KiteTab.tsx
git commit -m "fix(kite): fire protective GTT on actual fill, not order-accepted"
```

**IMPORTANT — commit hygiene:** stage ONLY the four exact files above.

---

## Task 3: Orders — status badges + variety tag

**Files:**
- Modify: `frontend/src/components/kite/OrdersPane.tsx`

- [ ] **Step 1: Add a status-color helper and variety tag, wire them into the orders table**

In `frontend/src/components/kite/OrdersPane.tsx`, add near the top of the file (after the `S` style object):

```tsx
const STATUS_COLOR: Record<string, { fg: string; bg: string }> = {
  COMPLETE: { fg: '#4caf50', bg: 'rgba(76, 175, 80, 0.1)' },
  OPEN: { fg: '#ff9800', bg: 'rgba(255, 152, 0, 0.1)' },
  'TRIGGER PENDING': { fg: '#ff9800', bg: 'rgba(255, 152, 0, 0.1)' },
  CANCELLED: { fg: '#df514c', bg: 'rgba(223, 81, 76, 0.1)' },
  REJECTED: { fg: '#df514c', bg: 'rgba(223, 81, 76, 0.1)' },
};
function statusStyle(status: string): React.CSSProperties {
  const c = STATUS_COLOR[status] ?? { fg: '#9b9b9b', bg: 'rgba(155, 155, 155, 0.1)' };
  return { padding: '2px 6px', background: c.bg, color: c.fg, borderRadius: 3, fontSize: 11 };
}
const MODIFIABLE_STATUSES = new Set(['OPEN', 'TRIGGER PENDING']);
```

Replace the status cell (currently):

```tsx
              <td style={S.td}>
                <span style={{ padding: '2px 6px', background: 'rgba(155, 155, 155, 0.1)', color: '#9b9b9b', borderRadius: 3, fontSize: 11 }}>{o.status}</span>
              </td>
```

with:

```tsx
              <td style={S.td}>
                <span style={statusStyle(o.status)}>{o.status}</span>
                {o.variety && o.variety !== 'regular' && (
                  <span style={{ marginLeft: 6, padding: '1px 5px', background: '#f1f1f1', color: '#9b9b9b', borderRadius: 2, fontSize: 9, fontWeight: 600, textTransform: 'uppercase' }}>{o.variety}</span>
                )}
              </td>
```

- [ ] **Step 2: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Manual check (dev server): open Orders with at least one order of each status if possible, confirm color-coding matches; place one AMO order (or inspect one from history) and confirm the "AMO" tag shows next to non-regular varieties.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/kite/OrdersPane.tsx
git commit -m "feat(kite): color-code order status, show non-regular variety tag"
```

---

## Task 4: Orders — Modify Order modal

**Files:**
- Create: `frontend/src/components/kite/ModifyOrderModal.tsx`
- Create: `frontend/src/components/kite/__tests__/ModifyOrderModal.test.tsx`
- Modify: `frontend/src/components/kite/OrdersPane.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/kite/__tests__/ModifyOrderModal.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { ModifyOrderModal } from '../ModifyOrderModal';

const mockMutate = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  useModifyKiteOrder: () => ({ mutate: mockMutate, isPending: false }),
}));

const order = {
  order_id: 'o1', variety: 'regular', tradingsymbol: 'INFY', exchange: 'NSE',
  quantity: 10, price: 1500, trigger_price: 0, order_type: 'LIMIT', validity: 'DAY',
};

describe('ModifyOrderModal', () => {
  it('prefills quantity and price from the order', () => {
    render(<ModifyOrderModal order={order} onClose={vi.fn()} />);
    expect(screen.getByDisplayValue('10')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1500')).toBeInTheDocument();
  });

  it('submits the edited quantity and price with the order id and variety', () => {
    render(<ModifyOrderModal order={order} onClose={vi.fn()} />);
    fireEvent.change(screen.getByDisplayValue('10'), { target: { value: '20' } });
    fireEvent.click(screen.getByText('Modify'));
    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'o1', variety: 'regular', quantity: 20, price: 1500 }),
      expect.anything(),
    );
  });

  it('closes on cancel without submitting', () => {
    const onClose = vi.fn();
    render(<ModifyOrderModal order={order} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
    expect(mockMutate).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/ModifyOrderModal.test.tsx`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `ModifyOrderModal.tsx`**

Create `frontend/src/components/kite/ModifyOrderModal.tsx`:

```tsx
import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useModifyKiteOrder } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';

interface OrderRow {
  order_id: string;
  variety: string;
  tradingsymbol: string;
  exchange: string;
  quantity: number;
  price: number;
  trigger_price?: number;
  order_type: string;
  validity: string;
}

export function ModifyOrderModal({ order, onClose }: { order: OrderRow; onClose: () => void }) {
  const modify = useModifyKiteOrder();
  const [quantity, setQuantity] = useState(order.quantity);
  const [price, setPrice] = useState(order.price);
  const [triggerPrice, setTriggerPrice] = useState(order.trigger_price ?? 0);
  const [error, setError] = useState<string | null>(null);
  const needsPrice = order.order_type === 'LIMIT' || order.order_type === 'SL';
  const needsTrigger = order.order_type === 'SL' || order.order_type === 'SL-M';

  const submit = () => {
    setError(null);
    if (!(quantity > 0)) { setError('Enter a quantity greater than 0'); return; }
    if (needsPrice && !(price > 0)) { setError('Enter a valid price'); return; }
    if (needsTrigger && !(triggerPrice > 0)) { setError('Enter a valid trigger price'); return; }
    modify.mutate(
      { id: order.order_id, variety: order.variety, quantity, price, trigger_price: triggerPrice, validity: order.validity },
      { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Modify failed') },
    );
  };

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 100, left: '50%', transform: 'translateX(-50%)', width: 380, background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${k.border}` }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 500, color: '#444' }}>
            Modify order <InstrumentLabel symbol={`${order.exchange}:${order.tradingsymbol}`} />
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <label style={{ fontSize: 12, color: '#9b9b9b' }}>Quantity
            <input type="number" min={1} value={quantity} onChange={(e) => setQuantity(Number(e.target.value))}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
          </label>
          {needsPrice && (
            <label style={{ fontSize: 12, color: '#9b9b9b' }}>Price
              <input type="number" step={0.05} value={price} onChange={(e) => setPrice(Number(e.target.value))}
                style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
            </label>
          )}
          {needsTrigger && (
            <label style={{ fontSize: 12, color: '#9b9b9b' }}>Trigger price
              <input type="number" step={0.05} value={triggerPrice} onChange={(e) => setTriggerPrice(Number(e.target.value))}
                style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
            </label>
          )}
          {error && <div style={{ color: k.red, fontSize: 12 }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '14px 18px', borderTop: `1px solid ${k.border}` }}>
          <button onClick={onClose} style={{ flex: 1, background: '#fff', color: '#444', border: `1px solid ${k.border}`, borderRadius: 3, padding: '9px', fontSize: 13, cursor: 'pointer' }}>Cancel</button>
          <button onClick={submit} disabled={modify.isPending} style={{ flex: 1, background: k.blue, color: '#fff', border: 'none', borderRadius: 3, padding: '9px', fontSize: 13, fontWeight: 600, cursor: modify.isPending ? 'not-allowed' : 'pointer', opacity: modify.isPending ? 0.6 : 1 }}>
            {modify.isPending ? '…' : 'Modify'}
          </button>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/ModifyOrderModal.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Wire it into `OrdersPane.tsx`**

Add the import:

```tsx
import { ModifyOrderModal } from './ModifyOrderModal';
```

In `OrdersSubPane()`, add state near the top of the function:

```tsx
  const [modifyOrder, setModifyOrder] = useState<any | null>(null);
```

(`useState` is already imported in this file per its existing `import React, { useState } from 'react';`.)

In the orders table, replace the closing of the row (the `</tr>` after the status cell) so there's a new "Actions" column with a Modify link, only for modifiable statuses. Change the header row from:

```tsx
        <thead><tr>
          <th style={S.th}>Time</th><th style={S.th}>Type</th><th style={S.th}>Instrument</th>
          <th style={S.th}>Product</th><th style={S.th}>Qty.</th><th style={S.th}>Avg. price</th>
          <th style={S.th}>Status</th>
        </tr></thead>
```

to:

```tsx
        <thead><tr>
          <th style={S.th}>Time</th><th style={S.th}>Type</th><th style={S.th}>Instrument</th>
          <th style={S.th}>Product</th><th style={S.th}>Qty.</th><th style={S.th}>Avg. price</th>
          <th style={S.th}>Status</th><th style={S.th} />
        </tr></thead>
```

And add a new cell right after the status `<td>` (before the row's closing `</tr>`):

```tsx
              <td style={{ ...S.td, textAlign: 'right' }}>
                {MODIFIABLE_STATUSES.has(o.status) && (
                  <span onClick={() => setModifyOrder(o)} style={{ cursor: 'pointer', color: '#387ed1', fontSize: 12 }}>Modify</span>
                )}
              </td>
```

At the end of `OrdersSubPane`'s returned JSX (after the closing `</table>` of the non-empty branch, inside the same `return (...)`), add the conditional modal render:

```tsx
      {modifyOrder && <ModifyOrderModal order={modifyOrder} onClose={() => setModifyOrder(null)} />}
```

- [ ] **Step 6: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Run `cd frontend && npx vitest run` — expect the established baseline plus your new passing tests, no new failures.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/kite/ModifyOrderModal.tsx frontend/src/components/kite/__tests__/ModifyOrderModal.test.tsx frontend/src/components/kite/OrdersPane.tsx
git commit -m "feat(kite): add order-modify modal, wire into Orders pane"
```

---

## Task 5: Orders — Cancel action with confirm

**Files:**
- Modify: `frontend/src/components/kite/OrdersPane.tsx`

- [ ] **Step 1: Add cancel with a native confirm step**

In `frontend/src/components/kite/OrdersPane.tsx`, add the import:

```tsx
import { useCancelKiteOrder } from '../../hooks/useKite';
```

In `OrdersSubPane()`, add a hook call:

```tsx
  const cancelOrder = useCancelKiteOrder();
```

Change the Actions cell added in Task 4 to also include a Cancel action, only for cancellable statuses:

```tsx
              <td style={{ ...S.td, textAlign: 'right' }}>
                {MODIFIABLE_STATUSES.has(o.status) && (
                  <>
                    <span onClick={() => setModifyOrder(o)} style={{ cursor: 'pointer', color: '#387ed1', fontSize: 12, marginRight: 12 }}>Modify</span>
                    <span
                      onClick={() => {
                        if (window.confirm(`Cancel this ${o.transaction_type} ${o.quantity} ${o.tradingsymbol} order?`)) {
                          cancelOrder.mutate({ id: o.order_id, variety: o.variety });
                        }
                      }}
                      style={{ cursor: 'pointer', color: '#df514c', fontSize: 12 }}
                    >
                      Cancel
                    </span>
                  </>
                )}
              </td>
```

- [ ] **Step 2: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Manual check (dev server, PAPER mode): place a LIMIT order far from market price so it stays OPEN, confirm Cancel shows a confirm dialog, confirm clicking OK actually cancels it and the row updates/disappears; confirm clicking Cancel-the-dialog (browser "Cancel" button) leaves the order untouched.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/kite/OrdersPane.tsx
git commit -m "feat(kite): add confirm-gated order cancellation"
```

---

## Task 6: Orders — click-to-expand history/trades

**Files:**
- Create: `frontend/src/components/kite/OrderHistoryRow.tsx`
- Create: `frontend/src/components/kite/__tests__/OrderHistoryRow.test.tsx`
- Modify: `frontend/src/components/kite/OrdersPane.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/kite/__tests__/OrderHistoryRow.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { OrderHistoryRow } from '../OrderHistoryRow';

vi.mock('../../../hooks/useKite', () => ({
  useKiteOrderHistory: () => ({ data: [{ status: 'OPEN', order_timestamp: '2026-07-11 09:15:01' }, { status: 'COMPLETE', order_timestamp: '2026-07-11 09:15:03' }] }),
  useKiteOrderTrades: () => ({ data: [{ quantity: 10, average_price: 1500.5, fill_timestamp: '2026-07-11 09:15:03' }] }),
}));

describe('OrderHistoryRow', () => {
  it('renders each history status transition', () => {
    render(<OrderHistoryRow orderId="o1" colSpan={8} />);
    expect(screen.getByText('OPEN')).toBeInTheDocument();
    expect(screen.getByText('COMPLETE')).toBeInTheDocument();
  });

  it('renders fill trades', () => {
    render(<OrderHistoryRow orderId="o1" colSpan={8} />);
    expect(screen.getByText(/1500.50/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/OrderHistoryRow.test.tsx`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `OrderHistoryRow.tsx`**

Create `frontend/src/components/kite/OrderHistoryRow.tsx`:

```tsx
import React from 'react';
import { useKiteOrderHistory, useKiteOrderTrades } from '../../hooks/useKite';

const num = (v: any) => Number(v ?? 0);

export function OrderHistoryRow({ orderId, colSpan }: { orderId: string; colSpan: number }) {
  const { data: history } = useKiteOrderHistory(orderId);
  const { data: trades } = useKiteOrderTrades(orderId);

  return (
    <tr>
      <td colSpan={colSpan} style={{ padding: '10px 24px', background: '#fafafa', borderBottom: '1px solid #f1f1f1' }}>
        <div style={{ display: 'flex', gap: 32, fontSize: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ color: '#9b9b9b', marginBottom: 6, fontSize: 11 }}>Status history</div>
            {(!history || history.length === 0) && <div style={{ color: '#9b9b9b' }}>No history yet.</div>}
            {history?.map((h: any, i: number) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', color: '#444' }}>
                <span>{h.status}</span>
                <span style={{ color: '#9b9b9b' }}>{h.order_timestamp}</span>
              </div>
            ))}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ color: '#9b9b9b', marginBottom: 6, fontSize: 11 }}>Fills</div>
            {(!trades || trades.length === 0) && <div style={{ color: '#9b9b9b' }}>No fills yet.</div>}
            {trades?.map((t: any, i: number) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', color: '#444' }}>
                <span>{num(t.quantity)} @ {num(t.average_price).toFixed(2)}</span>
                <span style={{ color: '#9b9b9b' }}>{t.fill_timestamp}</span>
              </div>
            ))}
          </div>
        </div>
      </td>
    </tr>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/OrderHistoryRow.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Wire click-to-expand into `OrdersPane.tsx`**

Add the import:

```tsx
import { OrderHistoryRow } from './OrderHistoryRow';
```

In `OrdersSubPane()`, add state:

```tsx
  const [expandedId, setExpandedId] = useState<string | null>(null);
```

Make the order row clickable to toggle expansion — add `onClick` to the `<tr>` and render an `OrderHistoryRow` conditionally right after it. Change:

```tsx
            <tr key={o.order_id}>
```

to:

```tsx
            <React.Fragment key={o.order_id}>
            <tr onClick={() => setExpandedId(expandedId === o.order_id ? null : o.order_id)} style={{ cursor: 'pointer' }}>
```

and change the row's closing `</tr>` (the one right before the `))}` that ends the `.map(...)`) to:

```tsx
            </tr>
            {expandedId === o.order_id && <OrderHistoryRow orderId={o.order_id} colSpan={8} />}
            </React.Fragment>
```

(Adjust `colSpan={8}` if Task 4/5's Actions column changes the actual column count from what's shown here — count the current `<th>` cells in the header row and use that number.)

- [ ] **Step 6: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Manual check (dev server): click an order row, confirm the history/fills panel expands beneath it; click again to collapse.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/kite/OrderHistoryRow.tsx frontend/src/components/kite/__tests__/OrderHistoryRow.test.tsx frontend/src/components/kite/OrdersPane.tsx
git commit -m "feat(kite): click-to-expand order history and fills"
```

---

## Task 7: Orders — fix the disconnected "Baskets" tab

**Files:**
- Modify: `frontend/src/components/kite/OrdersPane.tsx`

- [ ] **Step 1: Replace the static Baskets placeholder with a real reflection of the basket feature**

In `frontend/src/components/kite/OrdersPane.tsx`, add the import:

```tsx
import { useKiteBasketStore } from '../../store/useKiteBasketStore';
```

Replace the entire `BasketsPane` function:

```tsx
function BasketsPane() {
  return (
    <div style={S.emptyContainer}>
      <div style={{ marginBottom: 24 }}>
        <svg width="84" height="84" viewBox="0 0 24 24" fill="none">
          <path d="M4 8l2 12h12l2-12H4z" fill="#f8f8f8" stroke="#dfe1e4" strokeWidth="1" strokeLinejoin="round" />
          <path d="M8 8V6a4 4 0 018 0v2" stroke="#dfe1e4" strokeWidth="1" strokeLinecap="round" />
          <path d="M6 11h12M7 14h10M8 17h8" stroke="#dfe1e4" strokeWidth="1" strokeLinecap="round" strokeDasharray="1 2" />
          <text x="12" y="15" fill="#dfe1e4" fontSize="5" fontWeight="bold" textAnchor="middle" style={{ letterSpacing: 1 }}>000</text>
        </svg>
      </div>
      <div style={S.emptyTitle}>You haven't created any baskets.</div>
      <button style={S.primaryBtn}>New basket</button>
    </div>
  );
}
```

with:

```tsx
function BasketsPane({ onOpenBasket }: { onOpenBasket: () => void }) {
  const count = useKiteBasketStore((s) => s.entries.length);
  if (count === 0) {
    return (
      <div style={S.emptyContainer}>
        <div style={{ marginBottom: 24 }}>
          <svg width="84" height="84" viewBox="0 0 24 24" fill="none">
            <path d="M4 8l2 12h12l2-12H4z" fill="#f8f8f8" stroke="#dfe1e4" strokeWidth="1" strokeLinejoin="round" />
            <path d="M8 8V6a4 4 0 018 0v2" stroke="#dfe1e4" strokeWidth="1" strokeLinecap="round" />
            <path d="M6 11h12M7 14h10M8 17h8" stroke="#dfe1e4" strokeWidth="1" strokeLinecap="round" strokeDasharray="1 2" />
            <text x="12" y="15" fill="#dfe1e4" fontSize="5" fontWeight="bold" textAnchor="middle" style={{ letterSpacing: 1 }}>000</text>
          </svg>
        </div>
        <div style={S.emptyTitle}>Basket is empty.</div>
        <button style={S.primaryBtn} onClick={onOpenBasket}>Open basket</button>
      </div>
    );
  }
  return (
    <div style={S.emptyContainer}>
      <div style={{ ...S.emptyTitle, marginBottom: 0 }}>{count} order{count !== 1 ? 's' : ''} staged in your basket.</div>
      <button style={{ ...S.primaryBtn, marginTop: 20 }} onClick={onOpenBasket}>Open basket</button>
    </div>
  );
}
```

(This intentionally does NOT build real Kite's separate "saved/reusable basket templates" feature — that's a distinct, bigger capability, out of scope for this pass. This just stops the tab from showing a disconnected fake empty-state and instead reflects/opens the real ephemeral staging-cart basket feature that already exists via the nav trigger.)

- [ ] **Step 2: Thread a way to open the real basket panel through to `BasketsPane`**

`OrdersPane` itself doesn't currently own basket-open state (that lives in `KiteTab.tsx`, alongside `KiteLayout`'s nav trigger, per the prior "Kite Parity Polish" plan). Add an optional prop to `OrdersPane` so its caller can pass the open-handler down:

Change the `export function OrdersPane()` signature to:

```tsx
export function OrdersPane({ onOpenBasket }: { onOpenBasket?: () => void }) {
```

And change the tab-content render:

```tsx
        {tab === 'baskets' && <BasketsPane />}
```

to:

```tsx
        {tab === 'baskets' && <BasketsPane onOpenBasket={onOpenBasket ?? (() => {})} />}
```

- [ ] **Step 3: Pass the real handler down from `KiteTab.tsx`**

In `frontend/src/components/kite/KiteTab.tsx`, find where `<OrdersPane` is rendered (it's one of the panes switched on the active nav tab) and pass the existing `setBasketOpen` setter (already defined in this file from the prior basket-wiring task) through:

```tsx
<OrdersPane onOpenBasket={() => setBasketOpen(true)} />
```

(If `OrdersPane` is rendered in more than one place in this file, thread the prop through each call site the same way.)

- [ ] **Step 4: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Manual check (dev server): stage an item into the basket (from a watchlist row, per the prior pass), open Orders → Baskets tab, confirm it shows the real count and "Open basket" actually opens the real `BasketPane`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/kite/OrdersPane.tsx frontend/src/components/kite/KiteTab.tsx
git commit -m "fix(kite): Orders' Baskets tab reflects the real basket feature instead of a disconnected mock"
```

---

## Task 8: GTT — status badges + Create GTT modal

**Files:**
- Create: `frontend/src/components/kite/CreateGttModal.tsx`
- Create: `frontend/src/components/kite/__tests__/CreateGttModal.test.tsx`
- Modify: `frontend/src/components/kite/GttPane.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/kite/__tests__/CreateGttModal.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { CreateGttModal } from '../CreateGttModal';

const mockMutate = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  usePlaceKiteGtt: () => ({ mutate: mockMutate, isPending: false }),
}));

describe('CreateGttModal', () => {
  it('submits a single-leg GTT with the entered trigger and price', () => {
    render(<CreateGttModal onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Symbol'), { target: { value: 'INFY' } });
    fireEvent.change(screen.getByLabelText('Exchange'), { target: { value: 'NSE' } });
    fireEvent.change(screen.getByLabelText('Last price'), { target: { value: '1500' } });
    fireEvent.change(screen.getByLabelText('Trigger price'), { target: { value: '1400' } });
    fireEvent.change(screen.getByLabelText('Order price'), { target: { value: '1400' } });
    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '10' } });
    fireEvent.click(screen.getByText('Create GTT'));
    expect(mockMutate).toHaveBeenCalledWith(expect.objectContaining({
      trigger_type: 'single', tradingsymbol: 'INFY', exchange: 'NSE',
      last_price: 1500, trigger_values: [1400],
    }));
  });

  it('shows a validation error when the trigger price is missing', () => {
    render(<CreateGttModal onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Create GTT'));
    expect(mockMutate).not.toHaveBeenCalled();
    expect(screen.getByText(/trigger price/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/CreateGttModal.test.tsx`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `CreateGttModal.tsx`**

Create `frontend/src/components/kite/CreateGttModal.tsx`:

```tsx
import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { usePlaceKiteGtt } from '../../hooks/useKite';

export function CreateGttModal({ onClose }: { onClose: () => void }) {
  const place = usePlaceKiteGtt();
  const [symbol, setSymbol] = useState('');
  const [exchange, setExchange] = useState('NSE');
  const [side, setSide] = useState<'BUY' | 'SELL'>('SELL');
  const [product, setProduct] = useState<'CNC' | 'NRML'>('CNC');
  const [lastPrice, setLastPrice] = useState(0);
  const [triggerPrice, setTriggerPrice] = useState(0);
  const [orderPrice, setOrderPrice] = useState(0);
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    if (!symbol.trim()) { setError('Enter a symbol'); return; }
    if (!(lastPrice > 0)) { setError('Enter the current last price'); return; }
    if (!(triggerPrice > 0)) { setError('Enter a valid trigger price'); return; }
    if (!(orderPrice > 0)) { setError('Enter a valid order price'); return; }
    if (!(quantity > 0)) { setError('Enter a quantity greater than 0'); return; }
    place.mutate(
      {
        trigger_type: 'single', tradingsymbol: symbol.trim().toUpperCase(), exchange,
        last_price: lastPrice, trigger_values: [triggerPrice],
        orders: [{ tradingsymbol: symbol.trim().toUpperCase(), exchange, transaction_type: side, quantity, order_type: 'LIMIT', product, price: orderPrice }],
      },
      { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Create GTT failed') },
    );
  };

  const field = (label: string, value: number | string, onChange: (v: string) => void, type: 'text' | 'number' = 'number') => (
    <label style={{ fontSize: 12, color: '#9b9b9b' }}>{label}
      <input type={type} step={type === 'number' ? 0.05 : undefined} value={value} onChange={(e) => onChange(e.target.value)}
        style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
    </label>
  );

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 80, left: '50%', transform: 'translateX(-50%)', width: 420, maxHeight: '80vh', overflowY: 'auto', background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${k.border}` }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 500, color: '#444' }}>Create GTT</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', gap: 10 }}>
            <div style={{ flex: 2 }}>{field('Symbol', symbol, (v) => setSymbol(v), 'text')}</div>
            <div style={{ flex: 1 }}>{field('Exchange', exchange, (v) => setExchange(v), 'text')}</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}><input type="radio" checked={side === 'BUY'} onChange={() => setSide('BUY')} /> Buy</label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}><input type="radio" checked={side === 'SELL'} onChange={() => setSide('SELL')} /> Sell</label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, marginLeft: 16 }}><input type="radio" checked={product === 'CNC'} onChange={() => setProduct('CNC')} /> CNC</label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}><input type="radio" checked={product === 'NRML'} onChange={() => setProduct('NRML')} /> NRML</label>
          </div>
          {field('Last price', lastPrice, (v) => setLastPrice(Number(v)))}
          {field('Trigger price', triggerPrice, (v) => setTriggerPrice(Number(v)))}
          {field('Order price', orderPrice, (v) => setOrderPrice(Number(v)))}
          {field('Quantity', quantity, (v) => setQuantity(Number(v)))}
          {error && <div style={{ color: k.red, fontSize: 12 }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '14px 18px', borderTop: `1px solid ${k.border}` }}>
          <button onClick={onClose} style={{ flex: 1, background: '#fff', color: '#444', border: `1px solid ${k.border}`, borderRadius: 3, padding: '9px', fontSize: 13, cursor: 'pointer' }}>Cancel</button>
          <button onClick={submit} disabled={place.isPending} style={{ flex: 1, background: k.blue, color: '#fff', border: 'none', borderRadius: 3, padding: '9px', fontSize: 13, fontWeight: 600, cursor: place.isPending ? 'not-allowed' : 'pointer', opacity: place.isPending ? 0.6 : 1 }}>
            {place.isPending ? '…' : 'Create GTT'}
          </button>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/CreateGttModal.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Wire status badges + the create modal into `GttPane.tsx`**

In `frontend/src/components/kite/GttPane.tsx`, add imports:

```tsx
import { useState } from 'react';
import { CreateGttModal } from './CreateGttModal';
```

(Change the existing `import React from 'react';` to `import React, { useState } from 'react';`.)

Add a status-color helper near the top (mirroring Task 3's Orders helper):

```tsx
const GTT_STATUS_COLOR: Record<string, { fg: string; bg: string }> = {
  active: { fg: '#4caf50', bg: 'rgba(76, 175, 80, 0.1)' },
  triggered: { fg: '#387ed1', bg: 'rgba(56, 126, 209, 0.1)' },
  expired: { fg: '#9b9b9b', bg: 'rgba(155, 155, 155, 0.1)' },
  cancelled: { fg: '#df514c', bg: 'rgba(223, 81, 76, 0.1)' },
  deleted: { fg: '#df514c', bg: 'rgba(223, 81, 76, 0.1)' },
  rejected: { fg: '#df514c', bg: 'rgba(223, 81, 76, 0.1)' },
};
function gttStatusStyle(status: string): React.CSSProperties {
  const c = GTT_STATUS_COLOR[(status || '').toLowerCase()] ?? { fg: '#9b9b9b', bg: 'rgba(155, 155, 155, 0.1)' };
  return { padding: '2px 6px', background: c.bg, color: c.fg, borderRadius: 3, fontSize: 11 };
}
```

Add state in `GttPane()`:

```tsx
  const [createOpen, setCreateOpen] = useState(false);
```

Wire both "Create new GTT" buttons (the empty-state one and any header one, if a second exists — this file currently only has the empty-state one) to open the modal. Change:

```tsx
        <button style={S.primaryBtn}>Create new GTT</button>
```

to:

```tsx
        <button style={S.primaryBtn} onClick={() => setCreateOpen(true)}>Create new GTT</button>
```

Replace the status `<td>` in the non-empty table:

```tsx
              <td style={{ ...S.td, color: '#9b9b9b' }}>{g.status}</td>
```

with:

```tsx
              <td style={S.td}><span style={gttStatusStyle(g.status)}>{g.status}</span></td>
```

At the very end of the component's return (both the empty-state branch and the table branch need this), restructure the function body so both branches share one trailing modal render. This step does NOT touch the "Options" span — it stays exactly as it is today (Task 9, which runs after this one, wires it). Replace the ENTIRE `GttPane` function with:

```tsx
export function GttPane() {
  const { data: gtts } = useKiteGtts(true);
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <>
      {(!gtts || gtts.length === 0) ? (
        <div style={S.emptyContainer}>
          <div style={{ marginBottom: 24 }}>
            <svg width="120" height="84" viewBox="0 0 120 70" fill="none">
              <circle cx="30" cy="30" r="20" fill="#f8f8f8" />
              <circle cx="30" cy="30" r="15" fill="#fff" stroke="#dfe1e4" strokeWidth="2" />
              <path d="M30 20v10l5 5" stroke="#dfe1e4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <rect x="50" y="25" width="40" height="6" rx="2" fill="#ffb74d" />
              <rect x="40" y="35" width="50" height="6" rx="2" fill="#bbdefb" />
              <text x="50" y="55" fill="#387ed1" fontSize="22" fontWeight="bold" fontStyle="italic" letterSpacing="1">gtt</text>
              <circle cx="15" cy="45" r="2" fill="#387ed1" />
              <circle cx="20" cy="50" r="1.5" fill="#387ed1" />
              <circle cx="10" cy="50" r="1" fill="#387ed1" />
            </svg>
          </div>
          <div style={S.emptyTitle}>
            You have not created any triggers. <a href="#" style={{ color: '#387ed1', textDecoration: 'none' }}>Learn more</a> about setting automatic stoploss and target orders for your holdings.
          </div>
          <button style={S.primaryBtn} onClick={() => setCreateOpen(true)}>Create new GTT</button>
        </div>
      ) : (
        <div style={{ padding: '0 16px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>ID</th><th style={S.th}>Symbol</th><th style={S.th}>Type</th><th style={S.th}>Status</th><th style={S.th} />
            </tr></thead>
            <tbody>
              {gtts.map((g: any) => (
                <tr key={g.id}>
                  <td style={S.td}>{g.id}</td>
                  <td style={S.td}><InstrumentLabel symbol={g.condition?.tradingsymbol ?? ''} fallback="—" /></td>
                  <td style={S.td}>{g.type}</td>
                  <td style={S.td}><span style={gttStatusStyle(g.status)}>{g.status}</span></td>
                  <td style={{ ...S.td, textAlign: 'right' }}>
                    <span style={{ cursor: 'pointer', color: '#387ed1', marginRight: 12 }}>Options</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {createOpen && <CreateGttModal onClose={() => setCreateOpen(false)} />}
    </>
  );
}
```

- [ ] **Step 6: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Run `cd frontend && npx vitest run` — established baseline plus new passing tests.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/kite/CreateGttModal.tsx frontend/src/components/kite/__tests__/CreateGttModal.test.tsx frontend/src/components/kite/GttPane.tsx
git commit -m "feat(kite): add Create GTT modal, color-code GTT status"
```

---

## Task 9: GTT — Modify/Delete modal

**Files:**
- Create: `frontend/src/components/kite/GttOptionsModal.tsx`
- Create: `frontend/src/components/kite/__tests__/GttOptionsModal.test.tsx`
- Modify: `frontend/src/components/kite/GttPane.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/kite/__tests__/GttOptionsModal.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { GttOptionsModal } from '../GttOptionsModal';

const mockModify = vi.fn();
const mockDelete = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  useModifyKiteGtt: () => ({ mutate: mockModify, isPending: false }),
  useDeleteKiteGtt: () => ({ mutate: mockDelete, isPending: false }),
}));

const gtt = {
  id: 42,
  condition: { tradingsymbol: 'INFY', exchange: 'NSE', trigger_values: [1400], last_price: 1500 },
  orders: [{ transaction_type: 'SELL', quantity: 10, product: 'CNC', order_type: 'LIMIT', price: 1400 }],
  type: 'single',
};

describe('GttOptionsModal', () => {
  it('prefills the trigger price from the GTT condition', () => {
    render(<GttOptionsModal gtt={gtt} onClose={vi.fn()} />);
    expect(screen.getByDisplayValue('1400')).toBeInTheDocument();
  });

  it('submits a modify with the edited trigger price', () => {
    render(<GttOptionsModal gtt={gtt} onClose={vi.fn()} />);
    fireEvent.change(screen.getByDisplayValue('1400'), { target: { value: '1350' } });
    fireEvent.click(screen.getByText('Save changes'));
    expect(mockModify).toHaveBeenCalledWith(expect.objectContaining({ id: 42, trigger_values: [1350] }), expect.anything());
  });

  it('requires confirmation before deleting', () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<GttOptionsModal gtt={gtt} onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Delete'));
    expect(confirmSpy).toHaveBeenCalled();
    expect(mockDelete).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('deletes when the confirmation is accepted', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<GttOptionsModal gtt={gtt} onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Delete'));
    expect(mockDelete).toHaveBeenCalledWith(42, expect.anything());
    vi.restoreAllMocks();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/GttOptionsModal.test.tsx`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `GttOptionsModal.tsx`**

Create `frontend/src/components/kite/GttOptionsModal.tsx`:

```tsx
import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useModifyKiteGtt, useDeleteKiteGtt } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';

export function GttOptionsModal({ gtt, onClose }: { gtt: any; onClose: () => void }) {
  const modify = useModifyKiteGtt();
  const del = useDeleteKiteGtt();
  const initialTrigger = gtt.condition?.trigger_values?.[0] ?? 0;
  const [triggerPrice, setTriggerPrice] = useState(initialTrigger);
  const [error, setError] = useState<string | null>(null);
  const leg = gtt.orders?.[0];

  const save = () => {
    setError(null);
    if (!(triggerPrice > 0)) { setError('Enter a valid trigger price'); return; }
    modify.mutate(
      {
        id: gtt.id, trigger_type: gtt.type, tradingsymbol: gtt.condition?.tradingsymbol,
        exchange: gtt.condition?.exchange, last_price: gtt.condition?.last_price,
        trigger_values: [triggerPrice], orders: gtt.orders,
      },
      { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Modify failed') },
    );
  };

  const remove = () => {
    if (!window.confirm(`Delete this GTT for ${gtt.condition?.tradingsymbol}?`)) return;
    del.mutate(gtt.id, { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Delete failed') });
  };

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 100, left: '50%', transform: 'translateX(-50%)', width: 380, background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${k.border}` }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 500, color: '#444' }}>
            GTT #{gtt.id} <InstrumentLabel symbol={`${gtt.condition?.exchange}:${gtt.condition?.tradingsymbol}`} />
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {leg && <div style={{ fontSize: 12, color: '#9b9b9b' }}>{leg.transaction_type} {leg.quantity} @ {leg.product}</div>}
          <label style={{ fontSize: 12, color: '#9b9b9b' }}>Trigger price
            <input type="number" step={0.05} value={triggerPrice} onChange={(e) => setTriggerPrice(Number(e.target.value))}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
          </label>
          {error && <div style={{ color: k.red, fontSize: 12 }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '14px 18px', borderTop: `1px solid ${k.border}` }}>
          <button onClick={remove} disabled={del.isPending} style={{ background: '#fff', color: k.red, border: `1px solid ${k.red}`, borderRadius: 3, padding: '9px 16px', fontSize: 13, cursor: del.isPending ? 'not-allowed' : 'pointer' }}>Delete</button>
          <button onClick={save} disabled={modify.isPending} style={{ flex: 1, background: k.blue, color: '#fff', border: 'none', borderRadius: 3, padding: '9px', fontSize: 13, fontWeight: 600, cursor: modify.isPending ? 'not-allowed' : 'pointer', opacity: modify.isPending ? 0.6 : 1 }}>
            {modify.isPending ? '…' : 'Save changes'}
          </button>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/GttOptionsModal.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Wire the "Options" link in `GttPane.tsx`**

Add the import:

```tsx
import { GttOptionsModal } from './GttOptionsModal';
```

Add state alongside `createOpen`:

```tsx
  const [optionsGtt, setOptionsGtt] = useState<any | null>(null);
```

Replace the row's "Options" span:

```tsx
                <span style={{ cursor: 'pointer', color: '#387ed1', marginRight: 12 }}>Options</span>
```

with:

```tsx
                <span onClick={() => setOptionsGtt(g)} style={{ cursor: 'pointer', color: '#387ed1', marginRight: 12 }}>Options</span>
```

Add the conditional modal render alongside the existing `{createOpen && ...}` render (from Task 8):

```tsx
      {optionsGtt && <GttOptionsModal gtt={optionsGtt} onClose={() => setOptionsGtt(null)} />}
```

- [ ] **Step 6: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Manual check (dev server): create a GTT (Task 8), click "Options" on it, modify its trigger price, confirm the list updates; create another and delete it with confirm.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/kite/GttOptionsModal.tsx frontend/src/components/kite/__tests__/GttOptionsModal.test.tsx frontend/src/components/kite/GttPane.tsx
git commit -m "feat(kite): wire GTT modify/delete via an Options modal"
```

---

## Task 10: Alerts — search wiring + real "Triggered" data + Create modal

**Files:**
- Create: `frontend/src/components/kite/CreateAlertModal.tsx`
- Create: `frontend/src/components/kite/__tests__/CreateAlertModal.test.tsx`
- Modify: `frontend/src/components/kite/AlertsPane.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/kite/__tests__/CreateAlertModal.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { CreateAlertModal } from '../CreateAlertModal';

const mockMutate = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  useCreateKiteAlert: () => ({ mutate: mockMutate, isPending: false }),
}));

describe('CreateAlertModal', () => {
  it('submits a simple price alert', () => {
    render(<CreateAlertModal onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'INFY above 1600' } });
    fireEvent.change(screen.getByLabelText('Symbol'), { target: { value: 'INFY' } });
    fireEvent.change(screen.getByLabelText('Exchange'), { target: { value: 'NSE' } });
    fireEvent.change(screen.getByLabelText('Threshold'), { target: { value: '1600' } });
    fireEvent.click(screen.getByText('Create alert'));
    expect(mockMutate).toHaveBeenCalledWith(expect.objectContaining({
      name: 'INFY above 1600', lhs_exchange: 'NSE', lhs_tradingsymbol: 'INFY', rhs_constant: 1600,
    }));
  });

  it('requires a name before submitting', () => {
    render(<CreateAlertModal onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Create alert'));
    expect(mockMutate).not.toHaveBeenCalled();
    expect(screen.getByText(/name/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/CreateAlertModal.test.tsx`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `CreateAlertModal.tsx`**

Create `frontend/src/components/kite/CreateAlertModal.tsx`:

```tsx
import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useCreateKiteAlert } from '../../hooks/useKite';

const OPERATORS = ['>=', '<=', '>', '<', '=='] as const;

export function CreateAlertModal({ onClose }: { onClose: () => void }) {
  const create = useCreateKiteAlert();
  const [name, setName] = useState('');
  const [symbol, setSymbol] = useState('');
  const [exchange, setExchange] = useState('NSE');
  const [operator, setOperator] = useState<(typeof OPERATORS)[number]>('>=');
  const [threshold, setThreshold] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    if (!name.trim()) { setError('Enter a name for this alert'); return; }
    if (!symbol.trim()) { setError('Enter a symbol'); return; }
    if (!(threshold > 0)) { setError('Enter a threshold value'); return; }
    create.mutate(
      {
        name: name.trim(), lhs_exchange: exchange, lhs_tradingsymbol: symbol.trim().toUpperCase(),
        lhs_attribute: 'LastTradedPrice', operator, rhs_constant: threshold,
      },
      { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Create alert failed') },
    );
  };

  const field = (label: string, value: string | number, onChange: (v: string) => void, type: 'text' | 'number' = 'text') => (
    <label style={{ fontSize: 12, color: '#9b9b9b' }}>{label}
      <input type={type} step={type === 'number' ? 0.05 : undefined} value={value} onChange={(e) => onChange(e.target.value)}
        style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
    </label>
  );

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 80, left: '50%', transform: 'translateX(-50%)', width: 400, background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${k.border}` }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 500, color: '#444' }}>New alert</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {field('Name', name, setName)}
          <div style={{ display: 'flex', gap: 10 }}>
            <div style={{ flex: 2 }}>{field('Symbol', symbol, setSymbol)}</div>
            <div style={{ flex: 1 }}>{field('Exchange', exchange, setExchange)}</div>
          </div>
          <label style={{ fontSize: 12, color: '#9b9b9b' }}>Condition
            <select value={operator} onChange={(e) => setOperator(e.target.value as any)}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }}>
              {OPERATORS.map((op) => <option key={op} value={op}>Last price {op}</option>)}
            </select>
          </label>
          {field('Threshold', threshold, (v) => setThreshold(Number(v)), 'number')}
          {error && <div style={{ color: k.red, fontSize: 12 }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '14px 18px', borderTop: `1px solid ${k.border}` }}>
          <button onClick={onClose} style={{ flex: 1, background: '#fff', color: '#444', border: `1px solid ${k.border}`, borderRadius: 3, padding: '9px', fontSize: 13, cursor: 'pointer' }}>Cancel</button>
          <button onClick={submit} disabled={create.isPending} style={{ flex: 1, background: k.blue, color: '#fff', border: 'none', borderRadius: 3, padding: '9px', fontSize: 13, fontWeight: 600, cursor: create.isPending ? 'not-allowed' : 'pointer', opacity: create.isPending ? 0.6 : 1 }}>
            {create.isPending ? '…' : 'Create alert'}
          </button>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/CreateAlertModal.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Wire search, real Triggered count, and the create modal into `AlertsPane.tsx`**

Add the import and change the React import to include `useState`:

```tsx
import React, { useState } from 'react';
import { CreateAlertModal } from './CreateAlertModal';
import { useKiteAlertHistory } from '../../hooks/useKite';
```

Add state in `AlertsPane()`:

```tsx
  const [query, setQuery] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
```

Filter the alerts before rendering — replace:

```tsx
  const { data: alerts } = useKiteAlerts(true);
```

with:

```tsx
  const { data: allAlerts } = useKiteAlerts(true);
  const alerts = query.trim()
    ? (allAlerts || []).filter((a) => a.name.toLowerCase().includes(query.trim().toLowerCase()))
    : allAlerts;
```

Wire the "New alert" button and the search input. Replace:

```tsx
          <button style={S.primaryBtn}>
```

with:

```tsx
          <button style={S.primaryBtn} onClick={() => setCreateOpen(true)}>
```

Replace:

```tsx
            <input style={S.searchInput} placeholder="Search" />
```

with:

```tsx
            <input style={S.searchInput} placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} />
```

Replace the hardcoded "Triggered" cell:

```tsx
                <td style={{ ...S.td, color: '#387ed1' }}>0</td>
```

with a small per-row component that queries real history (extract this into a tiny sub-component so each row's `useKiteAlertHistory` call is independently scoped):

```tsx
                <td style={{ ...S.td, color: '#387ed1' }}><TriggeredCount uuid={a.uuid} /></td>
```

Add this component at the bottom of the file, before the final closing (or anywhere else at module scope in the file):

```tsx
function TriggeredCount({ uuid }: { uuid: string }) {
  const { data } = useKiteAlertHistory(uuid);
  return <>{data?.length ?? 0}</>;
}
```

Add the conditional modal render at the end of `AlertsPane`'s returned JSX (right before the closing `</div>` of the outer container):

```tsx
      {createOpen && <CreateAlertModal onClose={() => setCreateOpen(false)} />}
```

- [ ] **Step 6: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Run `cd frontend && npx vitest run` — established baseline plus new passing tests.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/kite/CreateAlertModal.tsx frontend/src/components/kite/__tests__/CreateAlertModal.test.tsx frontend/src/components/kite/AlertsPane.tsx
git commit -m "feat(kite): wire alert search, real triggered-count, Create Alert modal"
```

---

## Task 11: Alerts — Edit/Delete

**Files:**
- Create: `frontend/src/components/kite/EditAlertModal.tsx`
- Create: `frontend/src/components/kite/__tests__/EditAlertModal.test.tsx`
- Modify: `frontend/src/components/kite/AlertsPane.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/kite/__tests__/EditAlertModal.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { EditAlertModal } from '../EditAlertModal';

const mockModify = vi.fn();
const mockDelete = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  useModifyKiteAlert: () => ({ mutate: mockModify, isPending: false }),
  useDeleteKiteAlerts: () => ({ mutate: mockDelete, isPending: false }),
}));

const alert = { uuid: 'a1', name: 'INFY above 1600', rhs_constant: 1600, status: 'enabled' };

describe('EditAlertModal', () => {
  it('prefills the threshold', () => {
    render(<EditAlertModal alert={alert} onClose={vi.fn()} />);
    expect(screen.getByDisplayValue('1600')).toBeInTheDocument();
  });

  it('submits the edited threshold', () => {
    render(<EditAlertModal alert={alert} onClose={vi.fn()} />);
    fireEvent.change(screen.getByDisplayValue('1600'), { target: { value: '1650' } });
    fireEvent.click(screen.getByText('Save changes'));
    expect(mockModify).toHaveBeenCalledWith(expect.objectContaining({ uuid: 'a1', rhs_constant: 1650 }), expect.anything());
  });

  it('deletes with confirmation', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<EditAlertModal alert={alert} onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Delete'));
    expect(mockDelete).toHaveBeenCalledWith(['a1'], expect.anything());
    vi.restoreAllMocks();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/EditAlertModal.test.tsx`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `EditAlertModal.tsx`**

Create `frontend/src/components/kite/EditAlertModal.tsx`:

```tsx
import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useModifyKiteAlert, useDeleteKiteAlerts } from '../../hooks/useKite';
import type { KiteAlert } from '../../types/kite';

export function EditAlertModal({ alert, onClose }: { alert: KiteAlert; onClose: () => void }) {
  const modify = useModifyKiteAlert();
  const del = useDeleteKiteAlerts();
  const [threshold, setThreshold] = useState(alert.rhs_constant ?? 0);
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    setError(null);
    if (!(threshold > 0)) { setError('Enter a threshold value'); return; }
    modify.mutate({ uuid: alert.uuid, rhs_constant: threshold }, { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Modify failed') });
  };

  const remove = () => {
    if (!window.confirm(`Delete the "${alert.name}" alert?`)) return;
    del.mutate([alert.uuid], { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Delete failed') });
  };

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 100, left: '50%', transform: 'translateX(-50%)', width: 380, background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${k.border}` }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 500, color: '#444' }}>{alert.name}</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <label style={{ fontSize: 12, color: '#9b9b9b' }}>Threshold
            <input type="number" step={0.05} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
          </label>
          {error && <div style={{ color: k.red, fontSize: 12 }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '14px 18px', borderTop: `1px solid ${k.border}` }}>
          <button onClick={remove} disabled={del.isPending} style={{ background: '#fff', color: k.red, border: `1px solid ${k.red}`, borderRadius: 3, padding: '9px 16px', fontSize: 13, cursor: del.isPending ? 'not-allowed' : 'pointer' }}>Delete</button>
          <button onClick={save} disabled={modify.isPending} style={{ flex: 1, background: k.blue, color: '#fff', border: 'none', borderRadius: 3, padding: '9px', fontSize: 13, fontWeight: 600, cursor: modify.isPending ? 'not-allowed' : 'pointer', opacity: modify.isPending ? 0.6 : 1 }}>
            {modify.isPending ? '…' : 'Save changes'}
          </button>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/EditAlertModal.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Wire it into `AlertsPane.tsx`**

Add the import:

```tsx
import { EditAlertModal } from './EditAlertModal';
```

Add state alongside `createOpen`:

```tsx
  const [editingAlert, setEditingAlert] = useState<KiteAlert | null>(null);
```

Make each alert row clickable to open the edit modal — add `onClick` to the row `<tr>`:

```tsx
              <tr key={a.uuid} style={{ transition: 'background 0.2s', cursor: 'pointer' }} onClick={() => setEditingAlert(a)}>
```

(Note: the row checkbox at column 1 should stop propagation so clicking it doesn't also open the modal — add `onClick={(e) => e.stopPropagation()}` to that `<input type="checkbox">`.)

Add the conditional modal render alongside `{createOpen && ...}`:

```tsx
      {editingAlert && <EditAlertModal alert={editingAlert} onClose={() => setEditingAlert(null)} />}
```

- [ ] **Step 6: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Manual check (dev server): create an alert, click its row, confirm the edit modal opens prefilled, edit + save, confirm the list updates; delete another with confirm.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/kite/EditAlertModal.tsx frontend/src/components/kite/__tests__/EditAlertModal.test.tsx frontend/src/components/kite/AlertsPane.tsx
git commit -m "feat(kite): wire alert edit/delete via row click"
```

---

## Task 12: Positions — bulk "Exit Selected"

**Files:**
- Modify: `frontend/src/components/kite/PortfolioPane.tsx`

- [ ] **Step 1: Add an "Exit Selected" action consuming the existing selection state**

**Important — do not loop `handleOpenOrder`.** `handleOpenOrder` calls `openOrderWindow(...)`, which writes into `useOrderWindowStore` — a single-slot store (`{isOpen, options}`, not a queue). Calling it N times in a loop does not open N sequential tickets; it just overwrites `options` N times in the same tick (React batches these), so only the last position's ticket would ever actually render. Bulk exit needs to place orders directly instead, the same way `BasketPane.tsx` already does (sequential `mutateAsync` calls, not `Promise.all`, since a live order that already filled can't be un-placed).

In `frontend/src/components/kite/PortfolioPane.tsx`, add `usePlaceKiteOrder` to the existing `useKite` import:

```tsx
import {
  useConvertKitePosition, useKiteHoldings, useKitePositions,
  useKiteAuctions, useInitiateHoldingsAuth, useKiteLtp, usePlaceKiteOrder
} from '../../hooks/useKite';
```

Add a hook call and bulk-exit handler near `handleOpenOrder`'s declaration:

```tsx
  const placeOrder = usePlaceKiteOrder();
  const [exitingSelected, setExitingSelected] = useState(false);

  const exitSelected = async () => {
    const targets = positions.filter((p: any) => selectedPos.has(`${p.exchange}:${p.tradingsymbol}`) && num(p.quantity) !== 0);
    if (targets.length === 0) return;
    if (!window.confirm(`Exit ${targets.length} selected position${targets.length !== 1 ? 's' : ''} at market price?`)) return;
    setExitingSelected(true);
    for (const p of targets) {
      const qty = num(p.quantity);
      try {
        await placeOrder.mutateAsync({
          tradingsymbol: p.tradingsymbol, exchange: p.exchange,
          transaction_type: qty >= 0 ? 'SELL' : 'BUY', quantity: Math.abs(qty),
          order_type: 'MARKET', product: p.product, variety: 'regular', validity: 'DAY',
        });
      } catch {
        // usePlaceKiteOrder's own onError handler already surfaces a toast per
        // failed leg (see hooks/useKite.ts) — swallow here so one failure
        // doesn't stop the remaining selected positions from being attempted.
      }
    }
    setExitingSelected(false);
    setSelectedPos(new Set());
  };
```

Add a small header bar showing the button, only when something is selected. Find the Positions section header (the `<div style={{display:'flex',justifyContent:'space-between',...}}>` containing the "Positions (count)" `<h2>` and the Search/Analytics/Settings/Download row) and add the button into that same row's right-hand group, before the Search input:

```tsx
              {selectedPos.size > 0 && (
                <button onClick={exitSelected} disabled={exitingSelected} style={{ background: '#df514c', color: '#fff', border: 'none', borderRadius: 3, padding: '6px 14px', fontSize: 12, fontWeight: 500, cursor: exitingSelected ? 'not-allowed' : 'pointer', opacity: exitingSelected ? 0.6 : 1 }}>
                  {exitingSelected ? 'Exiting…' : `Exit Selected (${selectedPos.size})`}
                </button>
              )}
```

- [ ] **Step 2: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Manual check (dev server, PAPER mode): select two positions via checkboxes, confirm "Exit Selected (2)" appears, click it, confirm the confirm dialog appears, and — on accept — confirm both positions are actually squared off (check the Orders pane fills sequentially, not both at once) and the selection clears afterward.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/kite/PortfolioPane.tsx
git commit -m "feat(kite): wire bulk Exit Selected using the existing position-selection state"
```

---

## Task 13: Holdings — T1/settled distinction

**Files:**
- Modify: `frontend/src/components/kite/PortfolioPane.tsx`

- [ ] **Step 1: Show a T1 badge and cap sellable quantity**

In the Holdings table row rendering (inside the `sortedHoldings.map(...)` block), find the Instrument cell:

```tsx
                        <td style={{...S.td, whiteSpace: 'nowrap'}}>
                          <span style={{ color: '#444', marginRight: 8 }}><InstrumentLabel symbol={h.tradingsymbol} /></span>
                          <span style={{ fontSize: 9, color: '#9b9b9b', background: '#f1f1f1', padding: '1px 3px', borderRadius: 2 }}>{h.exchange}</span>
                        </td>
```

Add a T1 badge when applicable:

```tsx
                        <td style={{...S.td, whiteSpace: 'nowrap'}}>
                          <span style={{ color: '#444', marginRight: 8 }}><InstrumentLabel symbol={h.tradingsymbol} /></span>
                          <span style={{ fontSize: 9, color: '#9b9b9b', background: '#f1f1f1', padding: '1px 3px', borderRadius: 2 }}>{h.exchange}</span>
                          {num(h.t1_quantity) > 0 && (
                            <span style={{ marginLeft: 6, fontSize: 9, color: '#ff9800', background: 'rgba(255, 152, 0, 0.1)', padding: '1px 4px', borderRadius: 2, fontWeight: 600 }} title={`${num(h.t1_quantity)} of ${num(h.quantity)} shares not yet settled — not sellable today`}>
                              T1: {num(h.t1_quantity)}
                            </span>
                          )}
                        </td>
```

Cap the sellable quantity in that row's `KiteActionButtons` `onSell` handler. Find:

```tsx
                              onSell={(e) => { e.stopPropagation(); handleOpenOrder(`${h.exchange}:${h.tradingsymbol}`, 'SELL', num(h.quantity), h.product || 'CNC', num(h.last_price)); }}
```

Replace with:

```tsx
                              onSell={(e) => { e.stopPropagation(); const sellable = num(h.quantity) - num(h.t1_quantity); handleOpenOrder(`${h.exchange}:${h.tradingsymbol}`, 'SELL', Math.max(sellable, 0), h.product || 'CNC', num(h.last_price)); }}
```

(Also apply the same `sellable` cap to the Holdings row's `onBasket` handler added in the prior plan, so a basket-staged sell can't exceed settled quantity either — find `onBasket={(e) => { e.stopPropagation(); if (num(h.quantity) === 0) return; addToBasket({ symbol: h.tradingsymbol, ..., qty: num(h.quantity), ...`, and change the `qty:` field to `qty: Math.max(num(h.quantity) - num(h.t1_quantity), 0),` — keep the existing `if (num(h.quantity) === 0) return;` zero-qty guard as-is, since that guards the raw total, not the settled-sellable amount.)

- [ ] **Step 2: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Manual check (dev server, if any T1 holdings exist on the connected account): confirm the badge shows and the Exit/basket qty defaults to the settled amount, not the full T1-inclusive total.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/kite/PortfolioPane.tsx
git commit -m "feat(kite): show T1/unsettled badge on holdings, cap sell qty at settled amount"
```

---

## Task 14: Position conversion — partial quantity

**Files:**
- Modify: `frontend/src/components/kite/PortfolioPane.tsx`

- [ ] **Step 1: Add an editable quantity field to `ConvertControl`**

Replace the `ConvertControl` function:

```tsx
function ConvertControl({ p }: { p: any }) {
  const convert = useConvertKitePosition();
  const products = ['MIS', 'CNC', 'NRML'].filter((x) => x !== p.product);
  const [target, setTarget] = useState(products[0]);
  if (!num(p.quantity)) return null;
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', justifyContent: 'flex-end' }}>
      <select style={S.inSm} value={target} onChange={(e) => setTarget(e.target.value)}>
        {products.map((x) => <option key={x} value={x}>{x}</option>)}
      </select>
      <span
        style={{ cursor: 'pointer', color: convert.isError ? '#df514c' : '#387ed1', fontSize: 11 }}
        title={convert.isError ? (convert.error as Error).message : `Convert ${p.product} → ${target}`}
        onClick={() => convert.mutate({
          tradingsymbol: p.tradingsymbol, exchange: p.exchange,
          transaction_type: num(p.quantity) >= 0 ? 'BUY' : 'SELL', position_type: 'day',
          quantity: Math.abs(num(p.quantity)), old_product: p.product, new_product: target,
        })}
      >
        {convert.isPending ? '…' : convert.isSuccess ? '✓' : 'convert'}
      </span>
    </div>
  );
}
```

with:

```tsx
function ConvertControl({ p }: { p: any }) {
  const convert = useConvertKitePosition();
  const products = ['MIS', 'CNC', 'NRML'].filter((x) => x !== p.product);
  const [target, setTarget] = useState(products[0]);
  const fullQty = Math.abs(num(p.quantity));
  const [qty, setQty] = useState(fullQty);
  if (!num(p.quantity)) return null;
  const invalidQty = !(qty > 0) || qty > fullQty;
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', justifyContent: 'flex-end' }}>
      <input
        type="number" min={1} max={fullQty} value={qty}
        onChange={(e) => setQty(Number(e.target.value))}
        style={{ ...S.inSm, width: 56, textAlign: 'right' }}
        title={`Max: ${fullQty}`}
      />
      <select style={S.inSm} value={target} onChange={(e) => setTarget(e.target.value)}>
        {products.map((x) => <option key={x} value={x}>{x}</option>)}
      </select>
      <span
        style={{ cursor: invalidQty ? 'not-allowed' : 'pointer', color: invalidQty ? '#bdbdbd' : convert.isError ? '#df514c' : '#387ed1', fontSize: 11 }}
        title={invalidQty ? `Enter a quantity between 1 and ${fullQty}` : convert.isError ? (convert.error as Error).message : `Convert ${qty} of ${fullQty} ${p.product} → ${target}`}
        onClick={() => {
          if (invalidQty) return;
          convert.mutate({
            tradingsymbol: p.tradingsymbol, exchange: p.exchange,
            transaction_type: num(p.quantity) >= 0 ? 'BUY' : 'SELL', position_type: 'day',
            quantity: qty, old_product: p.product, new_product: target,
          });
        }}
      >
        {convert.isPending ? '…' : convert.isSuccess ? '✓' : 'convert'}
      </span>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Manual check (dev server): open a position's convert control, confirm the quantity field defaults to the full position size, confirm entering a smaller number and converting only converts that amount (verify via the resulting position split in the table after conversion), confirm entering 0 or a number above the max disables the convert action.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/kite/PortfolioPane.tsx
git commit -m "feat(kite): support partial-quantity position conversion"
```

---

## Task 15: Charges itemization in the order ticket

**Files:**
- Modify: `frontend/src/components/kite/OrderWindow.tsx`

- [ ] **Step 1: Fetch itemized charges alongside the existing margin calc**

In `frontend/src/components/kite/OrderWindow.tsx`, add the import:

```tsx
import { useKiteOrderCharges } from '../../hooks/useKite';
```

Add a hook call alongside `marginCalc`:

```tsx
  const chargesCalc = useKiteOrderCharges();
  const [charges, setCharges] = useState<Record<string, number> | null>(null);
```

In `runMargin()` (the existing debounced margin-calc function), after the existing `marginCalc.mutate([buildMarginOrder(args)], {...})` call, add a parallel charges call using the same guarded/debounced trigger point (reuse the same `id`/`reqId` staleness guard already present in `runMargin`):

```tsx
    chargesCalc.mutate([buildMarginOrder(args)], {
      onSuccess: (resp) => { if (id === reqId.current) setCharges(Array.isArray(resp) ? resp[0]?.charges ?? null : resp?.charges ?? null); },
      onError: () => { if (id === reqId.current) setCharges(null); },
    });
```

(Insert this right after the existing `marginCalc.mutate(...)` call inside `runMargin`, using the same `id` variable already computed there via `const id = ++reqId.current;` — do not compute a second `id`.)

- [ ] **Step 2: Show the itemized breakdown next to the existing charges figure**

Find the existing `reqAvail` JSX block, specifically the part rendering the lump-sum charges:

```tsx
      <span>Req. <b style={{ color: insufficient ? k.red : accent, fontWeight: 600 }}>{required != null ? inr(required) : (marginCalc.isPending ? '…' : '—')}</b>{margin && margin.charges > 0 ? <span> + {margin.charges.toFixed(2)}</span> : null}</span>
```

Replace the trailing charges span with a hoverable itemized breakdown, using the browser's native `title` tooltip (matching the lightweight-tooltip pattern already used elsewhere in this file, e.g. the T1-badge `title` added in Task 13):

```tsx
      <span>Req. <b style={{ color: insufficient ? k.red : accent, fontWeight: 600 }}>{required != null ? inr(required) : (marginCalc.isPending ? '…' : '—')}</b>{margin && margin.charges > 0 ? (
        <span title={charges ? Object.entries(charges).filter(([k]) => k !== 'total').map(([k, v]) => `${k}: ${Number(v).toFixed(2)}`).join('\n') : undefined} style={{ cursor: charges ? 'help' : 'default' }}> + {margin.charges.toFixed(2)}</span>
      ) : null}</span>
```

- [ ] **Step 3: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean.
Manual check (dev server): open an order ticket with a valid price/qty, wait for the margin calc to resolve, hover over the "+X.XX" charges figure, confirm a tooltip breakdown (STT/GST/etc. — whatever fields the backend's `/charges/orders` actually returns) appears.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/kite/OrderWindow.tsx
git commit -m "feat(kite): show itemized charges breakdown on hover in the order ticket"
```

---

## Task 16: Backlog documentation — Auctions + MTF

**Files:**
- Modify: `frontend/src/components/kite/PortfolioPane.tsx`
- Modify: `frontend/src/types/kite.ts`
- Modify: `frontend/src/components/kite/orderTicket.ts`

- [ ] **Step 1: Mark Auctions as read-only-by-design in code**

In `frontend/src/components/kite/PortfolioPane.tsx`, find the `AuctionsSection` function and add a one-line comment above its `return` statement (do not change any behavior):

```tsx
  // Read-only by design this pass: real Kite lets you place an auction bid
  // from this tab, but there's no backend endpoint for it yet (no POST route
  // exists for auction participation) — explicit backlog item, see
  // docs/superpowers/specs/2026-07-11-kite-order-management-parity-design.md.
```

- [ ] **Step 2: Mark MTF as an unused, backlogged product type**

In `frontend/src/types/kite.ts`, find the `PlaceOrderBody` interface's `product` field:

```ts
  product: 'MIS' | 'CNC' | 'NRML' | 'MTF';
```

Add a comment directly above the interface (or above this field, whichever reads more naturally in context):

```ts
// `MTF` is accepted by the backend/Kite Connect API but is not offered
// anywhere in the order ticket UI (`orderTicket.ts`'s `Product` type
// deliberately excludes it) — wiring it in needs verified broker-side MTF
// eligibility we don't have. Explicit backlog item, see
// docs/superpowers/specs/2026-07-11-kite-order-management-parity-design.md.
```

In `frontend/src/components/kite/orderTicket.ts`, find the `Product` type:

```ts
export type Product = 'MIS' | 'CNC' | 'NRML';
```

Add a one-line comment directly above it:

```ts
// MTF intentionally excluded — see the backlog note on PlaceOrderBody.product in types/kite.ts.
```

- [ ] **Step 3: Verify**

Run `cd frontend && npx tsc --noEmit` — expect clean (comments only, no behavior change).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/kite/PortfolioPane.tsx frontend/src/types/kite.ts frontend/src/components/kite/orderTicket.ts
git commit -m "docs(kite): mark Auctions bid placement and MTF product as explicit backlog items"
```

---

## Final check

- [ ] Run the full frontend test suite: `cd frontend && npx vitest run` — confirm only the established pre-existing failure set, no new regressions.
- [ ] Run `cd frontend && npx tsc --noEmit` — confirm clean.
- [ ] Manually walk through, in a single dev-server session: place a LIMIT order with SL/Target toggled on, confirm the GTT does NOT appear until the order actually fills (or confirm it's queued as pending if left unfilled); modify and cancel a pending order; create/modify/delete a GTT; create/edit/delete an alert and confirm search filters the list; select 2+ positions and Exit Selected; partially convert a position; check a T1 holding's badge and capped sell quantity if one exists on the connected account; hover the order ticket's charges figure for the itemized breakdown.
- [ ] Confirm the two backlog comments (Auctions, MTF) are in place and no actual Auctions/MTF capability was accidentally built.
