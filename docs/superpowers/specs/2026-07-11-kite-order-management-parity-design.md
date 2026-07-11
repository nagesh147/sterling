# Kite Order-Management Parity — Design

**Date:** 2026-07-11
**Status:** Approved for implementation

## Context

Following the "Kite Parity Polish" pass (AMO, dead-UI wiring, basket orders — see
`docs/superpowers/specs/2026-07-10-kite-parity-polish-design.md`), a broader
audit of the order-execution and management surface (Orders, GTT, Alerts,
Positions bulk actions, Holdings, Auctions, MTF) found a recurring pattern:
**the backend routes and frontend data-fetching hooks are complete and
correct, but several management panes never wire user actions to them** —
the same "dead UI over live backend" shape found and fixed earlier for
Positions/Holdings search/download/analytics, just missed in these panes.

One genuine correctness bug was also found (not a UI gap): the
"protective GTT on fill" feature creates its GTT the instant an order is
*accepted* by the broker, not when it actually *fills* — for a LIMIT/SL
order that can sit open indefinitely, this creates a live stop-loss/target
GTT for a position that may not exist yet.

Two structural gaps (capabilities that don't exist anywhere, backend
included) were found and are **explicitly deferred as backlog**, per the
same pattern as MCX in the prior pass: **Auctions bid placement** (no
backend endpoint exists; bids are irreversible) and **MTF** (a product type
present in one type definition, wired nowhere; needs broker-side
eligibility we haven't verified). Both get a documented backlog marker,
not implementation, in this pass.

## Goal

Wire the dead-but-built management actions (Orders, GTT, Alerts, bulk
position actions), fix the GTT-on-fill timing bug, add the two smaller
structural fixes that are genuinely in scope (Holdings T1 distinction,
partial position conversion), and itemize charges display. All of this
reuses patterns already established: the `k.bg`/`borderRadius:4`/
`rgba(0,0,0,0.06)` modal convention (`OrderWindow.tsx`, and now
`BasketPane.tsx`/`KitePortfolioAnalyticsModal.tsx`/`KiteSettingsPopover.tsx`
from the prior pass), `KiteActionButtons`' optional-prop-per-action slot
pattern, and the client-side search-filter pattern from the Positions/
Holdings fix.

## 1. Bug fix: protective-GTT-on-fill timing

**Current**: `OrderWindow.tsx`'s `submit()` fires `placeGtt.mutate(gtt)`
inside `placeOrder.mutate(...)`'s `onSuccess` callback — i.e. the moment
the order *submission* is accepted, not when it *fills*.

**Constraint that rules out the obvious fix**: `submit()`'s `onSuccess`
calls `onClose()` right after (same handler), which unmounts
`OrderWindow` immediately. Any "wait for the fill" logic living in
`OrderWindow`'s own component state/effects would be destroyed the moment
the ticket closes — before a non-MARKET order could realistically fill.
So this cannot be fixed by adding an effect inside `OrderWindow` itself;
the pending-protection state has to live somewhere that outlives the
ticket. (Correction from initial design: `useKiteOrderUpdates` is also
already consumed by `KiteNotifications.tsx` for toasts — each hook call
opens its own WebSocket, so a second independent call from a
short-lived component would add a redundant connection on top of the
lifecycle problem above.)

**Fix**: a new small Zustand store, `useKitePendingProtectionStore`
(`{pending: {orderId, gtt: PlaceGttBody}[], add, remove}`). `submit()`'s
`onSuccess` calls `add({orderId: res.order_id, gtt})` instead of placing
the GTT directly — ticket still closes immediately, same UX as today. A
new always-mounted watcher component, `PendingGttProtectionWatcher`
(rendered once in `KiteTab.tsx`, alongside the existing `BasketPane`
conditional render), polls `useKiteOrders(pending.length > 0)` (only
active while something is pending — reuses the existing 5s-interval,
already-shared React Query cache, no new WS connection) and
`usePlaceKiteGtt()`; on each refetch, for every pending entry it looks up
the matching order by `order_id`: if `status === 'COMPLETE'`, fires
`placeGtt.mutate(entry.gtt)` and removes the entry; if the status is a
terminal non-fill state (`CANCELLED`/`REJECTED`), removes the entry
without firing. This is a genuine differentiator vs. real Kite (which has
no equivalent auto-GTT-on-fill at all) — the fix makes it correctly *wait
for the fill* rather than removing the feature.

## 2. Orders management (`OrdersPane.tsx`)

- **Modify**: add an action (via `KiteActionButtons`, following its
  existing optional-prop pattern) opening a modal — matching the unified
  modal convention — prefilled with the order's current
  qty/price/trigger/validity, calling the already-built
  `useModifyKiteOrder({id, variety, quantity?, price?, order_type?,
  trigger_price?, validity?})`. Only enabled for cancellable/modifiable
  statuses (OPEN/TRIGGER PENDING), matching real Kite's own restriction.
- **Cancel**: add an action calling `useCancelKiteOrder({id, variety})`,
  gated behind a confirm step (this is irreversible on a real order).
- **Status badges**: color-code `o.status` using existing `k.green`
  (COMPLETE) / `k.red` (REJECTED/CANCELLED) / `k.orange` (OPEN/TRIGGER
  PENDING) tokens instead of the current raw-text passthrough.
- **Order history / trades**: click-to-expand a row to show
  `useKiteOrderHistory(orderId)`/`useKiteOrderTrades(orderId)` — a simple
  state-transition timeline and fill list, matching real Kite's
  click-to-expand order row.
- **Variety-aware**: modify/cancel must read/pass the order's actual
  `variety` (regular/amo/co/iceberg/auction) — not hardcode `'regular'` —
  and the table should show a small variety tag (e.g. "AMO") so AMO orders
  are visually distinguishable, since we now generate them.
- **Baskets tab fix**: `OrdersPane.tsx` currently has a static, disconnected
  "Baskets" placeholder (fake empty-state, inert "New basket" button). Wire
  it to reflect the real `useKiteBasketStore` state (entry count, a button
  that opens the real `BasketPane`) instead of the dead mock. Real Kite's
  own "Baskets" tab is for **saved/reusable basket templates** — a
  different, bigger feature (create-name-save-reload) that we are not
  building this pass; this fix only stops the current tab from actively
  misleading users away from the working ephemeral basket feature that
  already exists via the nav trigger.

## 3. GTT management (`GttPane.tsx`)

Same shape as Orders: wire "Create new GTT" to open a create modal calling
the already-built `usePlaceKiteGtt`, wire the row "Options" action to a
modal offering Modify (`useModifyKiteGtt`) and Delete
(`useDeleteKiteGtt`, confirm-gated), and color-code status badges
(active/triggered/expired/deleted/cancelled/rejected) the same way as
Orders.

## 4. Alerts management (`AlertsPane.tsx`)

Wire "New alert" to a create modal (`useCreateKiteAlert`), add a per-row
edit action (`useModifyKiteAlert`) and delete action
(`useDeleteKiteAlerts`, confirm-gated), wire the dead search box (same
client-side case-insensitive filter pattern already used in
`PortfolioPane.tsx`), and replace the hardcoded `"Triggered": 0` column
with real data from `useKiteAlertHistory`.

## 5. Bulk position actions (`PortfolioPane.tsx`)

The `selectedPos`/`toggleAllPos`/`togglePos` state already exists and
correctly tints selected rows but drives nothing. Add an "Exit Selected"
button (enabled when `selectedPos.size > 0`) that squares off every
selected position — reusing the same per-row Buy/Sell direction logic
already used by the individual Exit action — confirm-gated since this
places multiple live orders at once. No separate "Exit All" button;
"select all" + "Exit Selected" covers that case without a second code path.

## 6. Holdings T1 distinction + partial conversion (`PortfolioPane.tsx`)

- **T1 badge**: Kite's raw `/portfolio/holdings` payload includes
  `t1_quantity` (not-yet-settled, not sellable) alongside `quantity`
  (already read) — show a small badge on holdings rows where
  `t1_quantity > 0`, and cap the Exit action's max sellable quantity at
  `quantity - t1_quantity` with an inline warning if the user's existing
  Sell path would otherwise imply selling unsettled shares.
- **Partial conversion**: add an editable quantity input to
  `ConvertControl` (default: full position quantity, max: full position
  quantity), replacing the current hardcoded
  `Math.abs(num(p.quantity))` in the convert mutate call.

## 7. Charges itemization (`OrderWindow.tsx`) — lower priority

Currently `margin.charges` is a lump sum from `/margins/orders`'s
response. Add a call to the existing `/charges/orders` route (already
consumed by `KitePortfolioAnalyticsModal` from the prior pass) and show
the itemized breakdown (STT, exchange txn charges, GST, stamp duty, SEBI
charges) in a small hover/click tooltip next to the existing charges
figure, rather than replacing the lump-sum display outright.

## Out of scope (backlog, matching the MCX pattern)

- **Auctions bid placement** — no backend endpoint exists; would need a
  new `POST` route + real broker-facing order flow on wholly untested
  territory (irreversible auction bids). Mark explicitly in code/docs as
  a backlog item, same as MCX.
- **MTF product** — present only as an unused type-union member; wiring
  it into order placement and position conversion needs verified
  broker-side MTF eligibility we don't have. Mark explicitly as backlog.

## Testing

- Pure logic (fill-gated GTT creation's status-matching, T1 quantity
  cap calculation, itemized-charges parsing) gets unit tests.
- New modals (Modify Order, Modify/Delete GTT, Alert create/edit) get
  component tests mocking the relevant mutation hooks, following the
  `BasketPane.test.tsx` pattern (assert the right mutation is called with
  the right payload, confirm-gated actions require the confirm step).
- Bulk exit and partial conversion get tests confirming the correct set
  of orders/quantities are submitted.
- Manual browser verification per surface (dev server), per this
  project's UI-change verification norm.

## Rollout

All additive/wiring changes to existing, already-tested backend routes —
no backend changes except reading two already-existing-in-payload fields
(`t1_quantity`) that simply weren't consumed yet. No flag needed; low risk
since every mutation this pass calls is either already used elsewhere
(place/cancel/modify — same primitives as the working order ticket) or
newly confirm-gated for anything irreversible (cancel, delete, bulk exit).
