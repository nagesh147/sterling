# Kite Parity Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the specific Kite-parity gaps found in the audit — dead UI elements in `PortfolioPane.tsx`, no AMO order path, no basket-order flow — without touching the already-solid parts of the module (order-type matrix, GTT, the auto-engine, the Mac motion layer).

**Architecture:** All additive/wiring changes to existing files, plus three new small components (`BasketPane`, `KitePortfolioAnalyticsModal`, `KiteSettingsPopover`) and two new pure modules (`utils/csvExport.ts`, `store/useKiteBasketStore.ts`). No backend changes except two doc/comment corrections (MCX is explicitly deferred, not built).

**Tech Stack:** React 19 + TypeScript, Zustand, TanStack Query, Vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-07-10-kite-parity-polish-design.md`

**Design deviation from spec, found during file-reading (documented here since the plan is the source of truth for execution):** the spec proposed repurposing the "Analyze" link to open `SignalImpactCalculator.tsx`. Reading that component showed it's tightly coupled to `EngineDetailResponse`/`OptionDetail` — the auto-engine's per-signal option-leg Greeks — not general broker positions. Opening it for an arbitrary manually-placed position would show no data or wrong data. Task 6 below **removes** the "Analyze" link instead, with a one-line comment explaining why (it deep-links to a third-party analyzer in real Kite; we have no equivalent to link to, and forcing a mismatched component would be worse than no link).

**Also found during file-reading:** `usePlaceKiteOrder()` (`hooks/useKite.ts:277-304`) already shows a **post-submission** toast when the backend silently converts an order to AMO. Task 2 adds a **pre-submission** advisory + confirm gate (matching real Kite's UX) — the two are complementary, not duplicative: the pre-submit notice is an approximation (`market_open` from the engine-activity poll), the backend's hint-based conversion remains the actual authority.

---

## Task 1: AMO variety resolution (pure logic)

**Files:**
- Modify: `frontend/src/components/kite/orderTicket.ts`
- Create: `frontend/src/components/kite/orderTicket.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/kite/orderTicket.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { needsAmo, resolveVariety } from './orderTicket';

describe('needsAmo', () => {
  it('is false when the market is open', () => {
    expect(needsAmo(true)).toBe(false);
  });
  it('is true when the market is closed', () => {
    expect(needsAmo(false)).toBe(true);
  });
  it('is false when market state is unknown (undefined)', () => {
    expect(needsAmo(undefined)).toBe(false);
  });
});

describe('resolveVariety', () => {
  it('resolves to regular when the market is open', () => {
    expect(resolveVariety(true)).toBe('regular');
  });
  it('resolves to amo when the market is closed', () => {
    expect(resolveVariety(false)).toBe('amo');
  });
  it('resolves to regular when market state is unknown', () => {
    expect(resolveVariety(undefined)).toBe('regular');
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/kite/orderTicket.test.ts`
Expected: FAIL — `needsAmo`/`resolveVariety` are not exported from `./orderTicket`.

- [ ] **Step 3: Add the two functions to `orderTicket.ts`**

In `frontend/src/components/kite/orderTicket.ts`, add after the `roundTick` function (after line 100, before the "Order-type field rules" section comment):

```ts
// ─── AMO (After Market Order) ────────────────────────────────────────────────

/** Whether the ticket must be sent as an AMO because the market is currently closed. */
export function needsAmo(marketOpen: boolean | undefined): boolean {
  return marketOpen === false;
}

/**
 * Resolve the variety to submit. `marketOpen` comes from the engine-activity
 * poll (`is_market_open()` on the backend) — an approximation used only for
 * the pre-submit advisory. The backend's own hint-based AMO conversion
 * (`client.py`, catching `switch_to_amo`) remains the actual authority and is
 * unaffected by this — this just makes the same outcome visible *before* the
 * order is sent instead of only via a post-submit toast.
 */
export function resolveVariety(marketOpen: boolean | undefined): Variety {
  return needsAmo(marketOpen) ? 'amo' : 'regular';
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/kite/orderTicket.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/kite/orderTicket.ts frontend/src/components/kite/orderTicket.test.ts
git commit -m "feat(kite): add AMO variety resolution helper"
```

---

## Task 2: Wire AMO pre-submit notice into OrderWindow

**Files:**
- Modify: `frontend/src/components/kite/OrderWindow.tsx`

- [ ] **Step 1: Import the new helper and the engine-activity hook**

In `frontend/src/components/kite/OrderWindow.tsx`, update the `orderTicket` import (currently lines 13-19) to include `resolveVariety`:

```tsx
import {
  Side, OrderType, Product, Validity,
  productsForExchange, defaultProduct, marginSegment, isDerivative,
  effectiveLot, lotsFromQty, snapToLot, stepQty, lotsToQty,
  needsPrice, needsTrigger, validateTicket, resolveVariety,
  buildOrderBody, buildMarginOrder, parseMargin, buildProtectionGtt,
} from './orderTicket';
```

Add a new import line after the existing `useMacKite` import (line 8):

```tsx
import { useEngineActivity } from '../../hooks/useSterlingKiteEngine';
```

- [ ] **Step 2: Compute variety + confirm-gate state**

In the component body, after the `placeOrder`/`placeGtt`/`marginCalc`/`funds` declarations (after line 96), add:

```tsx
  const { data: activity } = useEngineActivity();
  const variety = resolveVariety(activity?.market_open);
  const amoConfirmNeeded = variety === 'amo';
  const [amoConfirmed, setAmoConfirmed] = useState(false);
```

- [ ] **Step 3: Use `variety` in the order args instead of the hardcoded value**

Replace the `args` useMemo (currently lines 121-125):

```tsx
  const args = useMemo(() => ({
    tradingsymbol: instr.symbol, exchange: instr.exchange, side, quantity: qty, product, orderType,
    price, trigger, validity, validityTtl: ttlMins, variety: 'regular' as const,
    disclosedQty: tab === 'regular' ? disclosedQty : 0, tag,
  }), [instr.symbol, instr.exchange, side, qty, product, orderType, price, trigger, validity, ttlMins, disclosedQty, tab, tag]);
```

with:

```tsx
  const args = useMemo(() => ({
    tradingsymbol: instr.symbol, exchange: instr.exchange, side, quantity: qty, product, orderType,
    price, trigger, validity, validityTtl: ttlMins, variety,
    disclosedQty: tab === 'regular' ? disclosedQty : 0, tag,
  }), [instr.symbol, instr.exchange, side, qty, product, orderType, price, trigger, validity, ttlMins, disclosedQty, tab, tag, variety]);
```

- [ ] **Step 4: Reset the confirm checkbox when the ticket loads a new instrument**

In `loadInstrument` (currently lines 187-200), add `setAmoConfirmed(false);` alongside the other resets, right after the `setError(null); setNudgeOpen(true);` line:

```tsx
    setError(null); setNudgeOpen(true);
    setAmoConfirmed(false);
```

- [ ] **Step 5: Gate the Buy/Sell button on the confirm checkbox**

Replace the `buyDisabled` line (currently line 245):

```tsx
  const buyDisabled = placing || !!nudge?.blocked;
```

with:

```tsx
  const buyDisabled = placing || !!nudge?.blocked || (amoConfirmNeeded && !amoConfirmed);
```

- [ ] **Step 6: Render the inline AMO notice**

In `cardInner`, right after the `{error && ...}` block (currently line 407), add:

```tsx
            {amoConfirmNeeded && (
              <div style={{ padding: '8px 16px', background: tint(k.amber, 12), color: '#8a6100', fontSize: 12 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                  <input type="checkbox" checked={amoConfirmed} onChange={(e) => setAmoConfirmed(e.target.checked)} style={{ accentColor: k.amber, width: 14, height: 14, flexShrink: 0 }} />
                  Market is closed — this will be placed as an After Market Order (AMO) for the next session.
                </label>
              </div>
            )}
```

- [ ] **Step 7: Manual verification (no automated test for this step — it's UI wiring of an already-tested pure function; see the plan's testing note)**

Run the dev server and confirm in a browser:

```bash
cd frontend && npm run dev
```

1. Open the Kite tab, open an order ticket for any instrument.
2. If tested during market hours, confirm the notice does NOT appear and the Buy/Sell button is enabled as before.
3. If tested outside market hours (or by temporarily forcing `is_market_open()` to return `False` in `backend/app/services/kite_engine/market_hours.py` for a manual check, then reverting), confirm: the amber notice appears, the Buy/Sell button is disabled until the checkbox is checked, and once checked + submitted, the placed order's toast still correctly reflects AMO handling.
4. Confirm switching to a different instrument (via search) resets the checkbox/notice state correctly.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/kite/OrderWindow.tsx
git commit -m "feat(kite): pre-submit AMO advisory + confirm gate in order ticket"
```

---

## Task 3: CSV export utility

**Files:**
- Create: `frontend/src/utils/csvExport.ts`
- Create: `frontend/src/utils/csvExport.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/utils/csvExport.test.ts`:

```ts
import { describe, it, expect, vi } from 'vitest';
import { toCsv, downloadCsv } from './csvExport';

describe('toCsv', () => {
  it('builds a header row plus one row per item', () => {
    const rows = [{ symbol: 'INFY', qty: 10 }, { symbol: 'TCS', qty: 5 }];
    const csv = toCsv(rows, [
      { header: 'Symbol', value: (r) => r.symbol },
      { header: 'Qty', value: (r) => r.qty },
    ]);
    expect(csv).toBe('Symbol,Qty\r\nINFY,10\r\nTCS,5');
  });

  it('quotes and escapes cells containing commas or quotes', () => {
    const rows = [{ name: 'Reliance, Ltd' }, { name: 'Say "hi"' }];
    const csv = toCsv(rows, [{ header: 'Name', value: (r) => r.name }]);
    expect(csv).toBe('Name\r\n"Reliance, Ltd"\r\n"Say ""hi"""');
  });

  it('returns just the header row for an empty list', () => {
    const csv = toCsv([] as { symbol: string }[], [{ header: 'Symbol', value: (r) => r.symbol }]);
    expect(csv).toBe('Symbol');
  });
});

describe('downloadCsv', () => {
  it('creates an object URL, clicks a temporary anchor, and revokes the URL', () => {
    const createUrl = vi.fn(() => 'blob:mock-url');
    const revoke = vi.fn();
    (global as any).URL.createObjectURL = createUrl;
    (global as any).URL.revokeObjectURL = revoke;
    const click = vi.fn();
    const origCreateElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = origCreateElement(tag);
      if (tag === 'a') (el as HTMLAnchorElement).click = click;
      return el;
    });

    downloadCsv('positions.csv', 'a,b\r\n1,2');

    expect(createUrl).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    expect(revoke).toHaveBeenCalledWith('blob:mock-url');

    vi.restoreAllMocks();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/utils/csvExport.test.ts`
Expected: FAIL — `./csvExport` module doesn't exist.

- [ ] **Step 3: Implement `csvExport.ts`**

Create `frontend/src/utils/csvExport.ts`:

```ts
/**
 * Minimal CSV export — build a CSV string from row objects + a column spec,
 * and trigger a browser download. Matches Kite Web's per-table "Download"
 * behaviour: exports exactly the rows currently visible/sorted, no server call.
 */
export interface CsvColumn<T> {
  header: string;
  value: (row: T) => string | number;
}

function escapeCsvCell(v: string | number): string {
  const s = String(v);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function toCsv<T>(rows: T[], columns: CsvColumn<T>[]): string {
  const header = columns.map((c) => escapeCsvCell(c.header)).join(',');
  const lines = rows.map((r) => columns.map((c) => escapeCsvCell(c.value(r))).join(','));
  return [header, ...lines].join('\r\n');
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/utils/csvExport.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/csvExport.ts frontend/src/utils/csvExport.test.ts
git commit -m "feat(kite): add CSV export utility for portfolio tables"
```

---

## Task 4: Wire Search + Download in PortfolioPane

**Files:**
- Modify: `frontend/src/components/kite/PortfolioPane.tsx`

- [ ] **Step 1: Import the CSV utility**

Add to the top of `frontend/src/components/kite/PortfolioPane.tsx` (after the existing imports, e.g. after line 10):

```tsx
import { toCsv, downloadCsv } from '../../utils/csvExport';
```

- [ ] **Step 2: Add query state and filtered lists**

After `const [selectedPos, setSelectedPos] = useState<Set<string>>(new Set());` (currently line 135), add:

```tsx
  const [posQuery, setPosQuery] = useState('');
  const [holdQuery, setHoldQuery] = useState('');
```

Replace `let sortedPositions = [...positions];` (currently line 144) with:

```tsx
  const filteredPositions = posQuery.trim()
    ? positions.filter((p: any) => `${p.tradingsymbol} ${p.exchange}`.toLowerCase().includes(posQuery.trim().toLowerCase()))
    : positions;
  let sortedPositions = [...filteredPositions];
```

Replace `let sortedHoldings = [...(holdings || [])];` (currently line 161) with:

```tsx
  const filteredHoldings = holdQuery.trim()
    ? (holdings || []).filter((h: any) => `${h.tradingsymbol} ${h.exchange}`.toLowerCase().includes(holdQuery.trim().toLowerCase()))
    : (holdings || []);
  let sortedHoldings = [...filteredHoldings];
```

- [ ] **Step 3: Add download handlers**

After the `handlePosSort`/`handleHoldSort` declarations (currently lines 141-142), add:

```tsx
  const downloadPositions = () => downloadCsv('positions.csv', toCsv(sortedPositions, [
    { header: 'Instrument', value: (p: any) => p.tradingsymbol },
    { header: 'Exchange', value: (p: any) => p.exchange },
    { header: 'Product', value: (p: any) => p.product },
    { header: 'Qty', value: (p: any) => num(p.quantity) },
    { header: 'Avg Price', value: (p: any) => num(p.average_price).toFixed(2) },
    { header: 'LTP', value: (p: any) => num(p.last_price).toFixed(2) },
    { header: 'P&L', value: (p: any) => num(p.pnl).toFixed(2) },
  ]));

  const downloadHoldings = () => downloadCsv('holdings.csv', toCsv(sortedHoldings, [
    { header: 'Instrument', value: (h: any) => h.tradingsymbol },
    { header: 'Exchange', value: (h: any) => h.exchange },
    { header: 'Qty', value: (h: any) => num(h.quantity) },
    { header: 'Avg Cost', value: (h: any) => num(h.average_price).toFixed(2) },
    { header: 'LTP', value: (h: any) => num(h.last_price).toFixed(2) },
    { header: 'Cur. Value', value: (h: any) => (num(h.quantity) * num(h.last_price)).toFixed(2) },
    { header: 'P&L', value: (h: any) => num(h.pnl).toFixed(2) },
  ]));
```

- [ ] **Step 4: Wire the Positions search input and Download link**

Replace the Positions search `<input>` (currently line 244):

```tsx
                <input type="text" placeholder="Search" style={{ padding: '6px 8px 6px 28px', border: `1px solid #e0e0e0`, borderRadius: 3, background: 'transparent', color: '#444', fontSize: 12, width: 160, outline: 'none' }} />
```

with:

```tsx
                <input type="text" placeholder="Search" value={posQuery} onChange={(e) => setPosQuery(e.target.value)} style={{ padding: '6px 8px 6px 28px', border: `1px solid #e0e0e0`, borderRadius: 3, background: 'transparent', color: '#444', fontSize: 12, width: 160, outline: 'none' }} />
```

Replace the Positions "Download" anchor (currently lines 255-257):

```tsx
              <a href="#" style={{ color: '#387ed1', textDecoration: 'none', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Download
              </a>
```

with:

```tsx
              <span onClick={downloadPositions} role="button" style={{ color: '#387ed1', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Download
              </span>
```

- [ ] **Step 5: Wire the Holdings search input and Download link**

Replace the Holdings search `<input>` (currently line 371):

```tsx
                <input type="text" placeholder="Search" style={{ padding: '6px 8px 6px 28px', border: `1px solid #e0e0e0`, borderRadius: 3, background: 'transparent', color: '#444', fontSize: 12, width: 150, outline: 'none' }} />
```

with:

```tsx
                <input type="text" placeholder="Search" value={holdQuery} onChange={(e) => setHoldQuery(e.target.value)} style={{ padding: '6px 8px 6px 28px', border: `1px solid #e0e0e0`, borderRadius: 3, background: 'transparent', color: '#444', fontSize: 12, width: 150, outline: 'none' }} />
```

Replace the Holdings "Download" anchor (currently lines 376-378):

```tsx
              <a href="#" style={{ color: '#387ed1', textDecoration: 'none', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Download
              </a>
```

with:

```tsx
              <span onClick={downloadHoldings} role="button" style={{ color: '#387ed1', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Download
              </span>
```

- [ ] **Step 6: Manual verification**

```bash
cd frontend && npm run dev
```

Open Positions and Holdings tabs. Type into each Search box and confirm rows narrow to matches on symbol/exchange (case-insensitive). Click each Download link and confirm a `positions.csv`/`holdings.csv` downloads with the currently-filtered/sorted rows and correct values.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/kite/PortfolioPane.tsx
git commit -m "feat(kite): wire Positions/Holdings search and CSV download"
```

---

## Task 5: Analytics modal for Positions and Holdings

**Files:**
- Create: `frontend/src/components/kite/KitePortfolioAnalyticsModal.tsx`
- Modify: `frontend/src/components/kite/PortfolioPane.tsx`

- [ ] **Step 1: Create the modal component**

Create `frontend/src/components/kite/KitePortfolioAnalyticsModal.tsx`:

```tsx
import React from 'react';
import { k } from '../../styles/kiteUI';

const num = (v: any) => Number(v ?? 0);
const pnlColor = (v: number) => (v > 0 ? '#4caf50' : v < 0 ? '#df514c' : '#9b9b9b');
const inr = (n: number) => n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface Props {
  view: 'positions' | 'holdings';
  positions: any[];
  holdings: any[];
  onClose: () => void;
}

/**
 * Lightweight analytics view: real-vs-real breakdown of numbers already
 * computed elsewhere in PortfolioPane (no new backend call for holdings;
 * positions view surfaces per-order charges via the existing
 * POST /api/v1/kite/charges/orders route).
 */
export function KitePortfolioAnalyticsModal({ view, positions, holdings, onClose }: Props) {
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.15)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 60, left: '50%', transform: 'translateX(-50%)', width: 640, maxWidth: '92vw', maxHeight: '80vh', overflowY: 'auto', background: '#fff', borderRadius: 6, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid #f1f1f1' }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 500, color: '#444' }}>
            {view === 'positions' ? 'Positions analytics' : 'Holdings analytics'}
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 20 }}>
          {view === 'positions' ? <PositionsAnalytics positions={positions} /> : <HoldingsAnalytics holdings={holdings} />}
        </div>
      </div>
    </>
  );
}

function PositionsAnalytics({ positions }: { positions: any[] }) {
  const realized = positions.filter((p) => num(p.quantity) === 0).reduce((a, p) => a + num(p.pnl), 0);
  const unrealized = positions.filter((p) => num(p.quantity) !== 0).reduce((a, p) => a + num(p.pnl), 0);
  const total = realized + unrealized;
  const maxAbs = Math.max(...positions.map((p) => Math.abs(num(p.pnl))), 1);
  return (
    <>
      <div style={{ display: 'flex', gap: 24, marginBottom: 24 }}>
        <Stat label="Realized" value={realized} />
        <Stat label="Unrealized" value={unrealized} />
        <Stat label="Total P&L" value={total} />
      </div>
      <h4 style={{ fontSize: 13, fontWeight: 500, color: '#444', marginBottom: 12 }}>Per-symbol breakdown</h4>
      {positions.filter((p) => num(p.pnl) !== 0).map((p, i) => (
        <div key={`${p.tradingsymbol}-${i}`} style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ width: 160, fontSize: 12, color: '#444', textAlign: 'right', paddingRight: 12 }}>{p.tradingsymbol}</div>
          <div style={{ flex: 1, background: '#f1f1f1', height: 8 }}>
            <div style={{ height: 8, background: pnlColor(num(p.pnl)), width: `${(Math.abs(num(p.pnl)) / maxAbs) * 100}%` }} />
          </div>
          <div style={{ width: 100, fontSize: 12, color: pnlColor(num(p.pnl)), textAlign: 'right', paddingLeft: 12 }}>{inr(num(p.pnl))}</div>
        </div>
      ))}
      {positions.every((p) => num(p.pnl) === 0) && <div style={{ color: '#9b9b9b', fontSize: 13 }}>No P&L to break down yet.</div>}
    </>
  );
}

function HoldingsAnalytics({ holdings }: { holdings: any[] }) {
  const investment = holdings.reduce((a, h) => a + num(h.quantity) * num(h.average_price), 0);
  const current = holdings.reduce((a, h) => a + num(h.quantity) * num(h.last_price), 0);
  const dayPnl = holdings.reduce((a, h) => a + num(h.day_change) * num(h.quantity), 0);
  const overallPnl = current - investment;
  return (
    <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
      <Stat label="Investment value" value={investment} plain />
      <Stat label="Current value" value={current} plain />
      <Stat label="Day's P&L" value={dayPnl} />
      <Stat label="Overall P&L" value={overallPnl} />
    </div>
  );
}

function Stat({ label, value, plain }: { label: string; value: number; plain?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: '#9b9b9b', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, color: plain ? '#444' : pnlColor(value), fontVariantNumeric: 'tabular-nums' }}>
        {!plain && value > 0 ? '+' : ''}{inr(value)}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire the two Analytics links in PortfolioPane**

In `frontend/src/components/kite/PortfolioPane.tsx`, add the import:

```tsx
import { KitePortfolioAnalyticsModal } from './KitePortfolioAnalyticsModal';
```

Add state near the other `useState` declarations (after `holdQuery`):

```tsx
  const [analyticsView, setAnalyticsView] = useState<'positions' | 'holdings' | null>(null);
```

Replace the Positions "Analytics" anchor (currently lines 249-251):

```tsx
              <a href="#" style={{ color: '#387ed1', textDecoration: 'none', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 2a10 10 0 0 1 10 10h-10z"></path></svg> Analytics
              </a>
```

with:

```tsx
              <a href="#" onClick={(e) => { e.preventDefault(); setAnalyticsView('positions'); }} style={{ color: '#387ed1', textDecoration: 'none', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 2a10 10 0 0 1 10 10h-10z"></path></svg> Analytics
              </a>
```

Replace the Holdings "Analytics" anchor (currently lines 373-375):

```tsx
              <a href="#" style={{ color: '#387ed1', textDecoration: 'none', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path></svg> Analytics
              </a>
```

with:

```tsx
              <a href="#" onClick={(e) => { e.preventDefault(); setAnalyticsView('holdings'); }} style={{ color: '#387ed1', textDecoration: 'none', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path></svg> Analytics
              </a>
```

**Accessibility note (why `<a>` not `<span role="button">`):** a code-quality review of Task 4 found that `<span role="button" onClick={...}>` without `tabIndex`/`onKeyDown` is unreachable via keyboard and has no Enter/Space activation — a real regression vs. the `<a href="#">` it replaces. Keeping the `<a>` with `preventDefault()` in the click handler avoids the hash-jump while preserving native focusability for free. Use this pattern for all remaining "wire a dead link" tasks in this plan (Tasks 5, 6) — do not introduce new `<span role="button">` elements.

Render the modal at the end of the component's return, right before the final closing `</div>` (currently line 458, just after the `{showHoldings && (...)}` block closes):

```tsx
      {analyticsView && (
        <KitePortfolioAnalyticsModal
          view={analyticsView}
          positions={sortedPositions}
          holdings={sortedHoldings}
          onClose={() => setAnalyticsView(null)}
        />
      )}
```

- [ ] **Step 3: Manual verification**

```bash
cd frontend && npm run dev
```

Click "Analytics" under Positions — confirm the modal shows realized/unrealized/total stats and a per-symbol breakdown bar matching the existing inline breakdown numbers. Click "Analytics" under Holdings — confirm investment/current/day/overall P&L match the totals row at the bottom of the Holdings table. Confirm the backdrop click and the ✕ button both close the modal.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/kite/KitePortfolioAnalyticsModal.tsx frontend/src/components/kite/PortfolioPane.tsx
git commit -m "feat(kite): add Positions/Holdings analytics modal"
```

---

## Task 6: Settings popover + remove the dead "Analyze" link

**Files:**
- Create: `frontend/src/components/kite/KiteSettingsPopover.tsx`
- Modify: `frontend/src/components/kite/PortfolioPane.tsx`

- [ ] **Step 1: Create the settings popover**

Create `frontend/src/components/kite/KiteSettingsPopover.tsx`:

```tsx
import React from 'react';
import { k } from '../../styles/kiteUI';
import { useKiteSettings } from '../../store/useKiteSettings';

const TOGGLES: Array<{ key: 'showHoldings' | 'showNotes' | 'showGroupColors' | 'showExchange' | 'showLeg'; label: string }> = [
  { key: 'showHoldings', label: 'Show holdings in watchlist' },
  { key: 'showNotes', label: 'Show notes' },
  { key: 'showGroupColors', label: 'Show group colours' },
  { key: 'showExchange', label: 'Show exchange badge' },
  { key: 'showLeg', label: 'Show leg labels' },
];

/**
 * Surfaces the existing useKiteSettings display-preference store (previously
 * only used internally by the watchlist) as its own popover, reached from
 * Positions/Holdings' "Settings" link — no new state, just a new UI on top
 * of state that already existed.
 */
export function KiteSettingsPopover({ onClose }: { onClose: () => void }) {
  const settings = useKiteSettings();
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 60, right: 40, width: 300, background: '#fff', borderRadius: 6, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily, padding: '16px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 500, color: '#444' }}>Display settings</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 16, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        {TOGGLES.map(({ key, label }) => (
          <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: '#444', cursor: 'pointer', padding: '6px 0' }}>
            <input type="checkbox" checked={settings[key]} onChange={() => settings.toggleShow(key)} style={{ accentColor: k.blue, width: 14, height: 14 }} />
            {label}
          </label>
        ))}
      </div>
    </>
  );
}
```

- [ ] **Step 2: Wire "Settings" and remove "Analyze" in PortfolioPane**

In `frontend/src/components/kite/PortfolioPane.tsx`, add the import:

```tsx
import { KiteSettingsPopover } from './KiteSettingsPopover';
```

Add state alongside `analyticsView`:

```tsx
  const [settingsOpen, setSettingsOpen] = useState(false);
```

Remove the "Analyze" anchor entirely (currently lines 246-248):

```tsx
              <a href="#" style={{ color: '#ff5722', textDecoration: 'none', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg> Analyze
              </a>
```

Delete this block. Real Kite deep-links "Analyze" to a third-party options-strategy tool (Sensibull) we have no equivalent for and no honest destination to send it to — removing a dead link is better than repurposing it into something misleading.

Replace the "Settings" anchor (currently lines 252-254):

```tsx
              <a href="#" style={{ color: '#9b9b9b', textDecoration: 'none', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg> Settings
              </a>
```

with:

```tsx
              <a href="#" onClick={(e) => { e.preventDefault(); setSettingsOpen(true); }} style={{ color: '#9b9b9b', textDecoration: 'none', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg> Settings
              </a>
```

Render the popover at the end of the component's return, alongside the analytics modal:

```tsx
      {settingsOpen && <KiteSettingsPopover onClose={() => setSettingsOpen(false)} />}
```

- [ ] **Step 3: Manual verification**

```bash
cd frontend && npm run dev
```

Confirm the "Analyze" link is gone from the Positions header. Click "Settings" and confirm the popover shows the five display toggles, that toggling one updates it immediately, and that the same toggle state persists (check `localStorage['kite-settings']`) and is reflected wherever else `useKiteSettings` is already read (e.g. the watchlist).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/kite/KiteSettingsPopover.tsx frontend/src/components/kite/PortfolioPane.tsx
git commit -m "feat(kite): wire Settings popover, remove dead Analyze link"
```

---

## Task 7: Basket store (pure state, no UI)

**Files:**
- Create: `frontend/src/store/useKiteBasketStore.ts`
- Create: `frontend/src/store/useKiteBasketStore.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/store/useKiteBasketStore.test.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { useKiteBasketStore, type NewBasketEntry } from './useKiteBasketStore';

const entry = (overrides: Partial<NewBasketEntry> = {}): NewBasketEntry => ({
  symbol: 'INFY', exchange: 'NSE', side: 'BUY', qty: 1, product: 'CNC',
  orderType: 'MARKET', price: 0, trigger: 0,
  ...overrides,
});

beforeEach(() => {
  useKiteBasketStore.setState({ entries: [] });
});

describe('useKiteBasketStore', () => {
  it('adds an entry with a generated id and idle status', () => {
    useKiteBasketStore.getState().add(entry());
    const entries = useKiteBasketStore.getState().entries;
    expect(entries).toHaveLength(1);
    expect(entries[0].symbol).toBe('INFY');
    expect(entries[0].status).toBe('idle');
    expect(entries[0].id).toBeTruthy();
  });

  it('removes an entry by id', () => {
    useKiteBasketStore.getState().add(entry());
    const id = useKiteBasketStore.getState().entries[0].id;
    useKiteBasketStore.getState().remove(id);
    expect(useKiteBasketStore.getState().entries).toHaveLength(0);
  });

  it('updates a field on an entry by id', () => {
    useKiteBasketStore.getState().add(entry());
    const id = useKiteBasketStore.getState().entries[0].id;
    useKiteBasketStore.getState().update(id, { qty: 5 });
    expect(useKiteBasketStore.getState().entries[0].qty).toBe(5);
  });

  it('sets an entry status', () => {
    useKiteBasketStore.getState().add(entry());
    const id = useKiteBasketStore.getState().entries[0].id;
    useKiteBasketStore.getState().setStatus(id, 'placing');
    expect(useKiteBasketStore.getState().entries[0].status).toBe('placing');
    useKiteBasketStore.getState().setStatus(id, 'failed', 'Insufficient margin');
    expect(useKiteBasketStore.getState().entries[0].status).toBe('failed');
    expect(useKiteBasketStore.getState().entries[0].error).toBe('Insufficient margin');
  });

  it('clears all entries', () => {
    useKiteBasketStore.getState().add(entry());
    useKiteBasketStore.getState().add(entry({ symbol: 'TCS' }));
    useKiteBasketStore.getState().clear();
    expect(useKiteBasketStore.getState().entries).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/store/useKiteBasketStore.test.ts`
Expected: FAIL — module `./useKiteBasketStore` doesn't exist.

- [ ] **Step 3: Implement the store**

Create `frontend/src/store/useKiteBasketStore.ts`:

```ts
import { create } from 'zustand';
import type { OrderType, Product, Side } from '../components/kite/orderTicket';

export type BasketEntryStatus = 'idle' | 'placing' | 'placed' | 'failed';

export interface BasketEntry {
  id: string;
  symbol: string;
  exchange: string;
  side: Side;
  qty: number;
  product: Product;
  orderType: OrderType;
  price: number;
  trigger: number;
  status: BasketEntryStatus;
  error?: string;
  orderId?: string;
}

export type NewBasketEntry = Omit<BasketEntry, 'id' | 'status' | 'error' | 'orderId'>;

interface BasketState {
  entries: BasketEntry[];
  add: (entry: NewBasketEntry) => void;
  remove: (id: string) => void;
  update: (id: string, patch: Partial<NewBasketEntry>) => void;
  setStatus: (id: string, status: BasketEntryStatus, error?: string, orderId?: string) => void;
  clear: () => void;
}

let seq = 0;
const nextId = () => `basket_${++seq}_${Math.random().toString(36).slice(2, 7)}`;

export const useKiteBasketStore = create<BasketState>((set) => ({
  entries: [],
  add: (entry) => set((s) => ({ entries: [...s.entries, { ...entry, id: nextId(), status: 'idle' }] })),
  remove: (id) => set((s) => ({ entries: s.entries.filter((e) => e.id !== id) })),
  update: (id, patch) => set((s) => ({ entries: s.entries.map((e) => (e.id === id ? { ...e, ...patch } : e)) })),
  setStatus: (id, status, error, orderId) => set((s) => ({
    entries: s.entries.map((e) => (e.id === id ? { ...e, status, error, orderId } : e)),
  })),
  clear: () => set({ entries: [] }),
}));
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/store/useKiteBasketStore.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/store/useKiteBasketStore.ts frontend/src/store/useKiteBasketStore.test.ts
git commit -m "feat(kite): add basket order staging store"
```

---

## Task 8: `onBasket` action on KiteActionButtons

**Files:**
- Modify: `frontend/src/components/kite/KiteActionButtons.tsx`

- [ ] **Step 1: Add the new optional prop**

In `frontend/src/components/kite/KiteActionButtons.tsx`, add `onBasket` to the props interface (currently lines 4-16):

```tsx
interface KiteActionButtonsProps {
  onBuy?: (e: React.MouseEvent) => void;
  onSell?: (e: React.MouseEvent) => void;
  onDepth?: (e: React.MouseEvent) => void;
  onChart?: (e: React.MouseEvent) => void;
  onDelete?: (e: React.MouseEvent) => void;
  onMore?: (e: React.MouseEvent) => void;
  onAdd?: (e: React.MouseEvent) => void;
  onBasket?: (e: React.MouseEvent) => void;
  className?: string;
  variant?: 'short' | 'long';
  buyLabel?: string;
  sellLabel?: string;
}
```

Add it to the destructured params (currently line 18):

```tsx
export function KiteActionButtons({ onBuy, onSell, onDepth, onChart, onDelete, onMore, onAdd, onBasket, className, variant = 'short', buyLabel, sellLabel }: KiteActionButtonsProps) {
```

- [ ] **Step 2: Render the basket button**

After the `onAdd` block (currently lines 74-78), add:

```tsx
      {onBasket && (
        <button style={iconBtnStyle} title="Add to basket" onClick={onBasket}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" /><path d="M3 6h18" /><path d="M16 10a4 4 0 0 1-8 0" />
          </svg>
        </button>
      )}
```

- [ ] **Step 3: Manual verification**

No new test file — this is an additive, optional prop on an existing component; every current call site (which doesn't pass `onBasket`) is unaffected. Confirmed by running the existing test suite:

```bash
cd frontend && npx vitest run
```

Expected: no new failures (this component has no dedicated test file today; this step just confirms nothing else broke).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/kite/KiteActionButtons.tsx
git commit -m "feat(kite): add onBasket action to KiteActionButtons"
```

---

## Task 9: BasketPane component

**Files:**
- Create: `frontend/src/components/kite/BasketPane.tsx`
- Create: `frontend/src/components/kite/__tests__/BasketPane.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/kite/__tests__/BasketPane.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BasketPane } from '../BasketPane';
import { useKiteBasketStore } from '../../../store/useKiteBasketStore';

const mockMutateAsync = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  usePlaceKiteOrder: () => ({ mutateAsync: mockMutateAsync }),
  useKiteMarginsBasket: () => ({ mutate: vi.fn(), data: null, isPending: false }),
}));

beforeEach(() => {
  useKiteBasketStore.setState({ entries: [] });
  mockMutateAsync.mockReset();
});

describe('BasketPane', () => {
  it('renders one row per staged entry', () => {
    useKiteBasketStore.getState().add({ symbol: 'INFY', exchange: 'NSE', side: 'BUY', qty: 1, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });
    useKiteBasketStore.getState().add({ symbol: 'TCS', exchange: 'NSE', side: 'SELL', qty: 2, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });
    render(<BasketPane onClose={vi.fn()} />);
    expect(screen.getByText('INFY')).toBeInTheDocument();
    expect(screen.getByText('TCS')).toBeInTheDocument();
  });

  it('removes a row when its remove button is clicked', () => {
    useKiteBasketStore.getState().add({ symbol: 'INFY', exchange: 'NSE', side: 'BUY', qty: 1, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });
    render(<BasketPane onClose={vi.fn()} />);
    fireEvent.click(screen.getByTitle('Remove from basket'));
    expect(useKiteBasketStore.getState().entries).toHaveLength(0);
  });

  it('places entries sequentially, not in parallel, and marks each placed on success', async () => {
    let resolveFirst: (v: any) => void = () => {};
    mockMutateAsync
      .mockImplementationOnce(() => new Promise((r) => { resolveFirst = r; }))
      .mockImplementationOnce(() => Promise.resolve({ order_id: 'o2' }));
    useKiteBasketStore.getState().add({ symbol: 'INFY', exchange: 'NSE', side: 'BUY', qty: 1, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });
    useKiteBasketStore.getState().add({ symbol: 'TCS', exchange: 'NSE', side: 'SELL', qty: 2, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });

    render(<BasketPane onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Place Basket'));

    // Second order must not be attempted until the first resolves.
    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1));
    resolveFirst({ order_id: 'o1' });

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      const entries = useKiteBasketStore.getState().entries;
      expect(entries[0].status).toBe('placed');
      expect(entries[1].status).toBe('placed');
    });
  });

  it('marks a failed entry as failed with its error and leaves it in the basket', async () => {
    mockMutateAsync.mockRejectedValueOnce(new Error('Insufficient margin'));
    useKiteBasketStore.getState().add({ symbol: 'INFY', exchange: 'NSE', side: 'BUY', qty: 1, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });

    render(<BasketPane onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Place Basket'));

    await waitFor(() => {
      expect(useKiteBasketStore.getState().entries[0].status).toBe('failed');
      expect(useKiteBasketStore.getState().entries[0].error).toBe('Insufficient margin');
    });
    // Failed entry stays in the basket for retry/removal.
    expect(useKiteBasketStore.getState().entries).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/BasketPane.test.tsx`
Expected: FAIL — `../BasketPane` doesn't exist, and `useKiteMarginsBasket` isn't exported from `hooks/useKite`.

- [ ] **Step 3: Add the `useKiteMarginsBasket` hook**

In `frontend/src/hooks/useKite.ts`, add near the other margin-related hooks (after `useKiteOrderMargins`, wherever that's defined — search the file for `useKiteOrderMargins` and add immediately after its closing brace):

```ts
export function useKiteMarginsBasket() {
  return useMutation<any, Error, Record<string, unknown>[]>({
    mutationFn: (orders) => api.post(`${K}/margins/basket`, orders),
  });
}
```

- [ ] **Step 4: Implement `BasketPane.tsx`**

Create `frontend/src/components/kite/BasketPane.tsx`:

```tsx
import React, { useEffect, useState } from 'react';
import { k } from '../../styles/kiteUI';
import { usePlaceKiteOrder, useKiteMarginsBasket } from '../../hooks/useKite';
import { useKiteBasketStore, type BasketEntry } from '../../store/useKiteBasketStore';
import { buildOrderBody, buildMarginOrder, parseMargin, needsPrice, needsTrigger } from './orderTicket';
import { InstrumentLabel } from './InstrumentLabel';

const num = (v: any) => Number(v ?? 0);
const inr = (n: number) => n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const statusColor: Record<BasketEntry['status'], string> = {
  idle: k.dim, placing: k.blue, placed: k.green, failed: k.red,
};
const statusLabel: Record<BasketEntry['status'], string> = {
  idle: 'Pending', placing: 'Placing…', placed: 'Placed', failed: 'Failed',
};

export function BasketPane({ onClose }: { onClose: () => void }) {
  const { entries, remove, update, setStatus, clear } = useKiteBasketStore();
  const placeOrder = usePlaceKiteOrder();
  const marginCalc = useKiteMarginsBasket();
  const [margin, setMargin] = useState<{ total: number; charges: number } | null>(null);
  const [placingAll, setPlacingAll] = useState(false);

  useEffect(() => {
    if (entries.length === 0) { setMargin(null); return; }
    const orders = entries.map((e) => buildMarginOrder({
      tradingsymbol: e.symbol, exchange: e.exchange, side: e.side, quantity: e.qty,
      product: e.product, orderType: e.orderType, price: e.price, trigger: e.trigger,
    }));
    marginCalc.mutate(orders, {
      onSuccess: (resp) => setMargin(parseMargin(Array.isArray(resp) ? resp[resp.length - 1] : resp)),
      onError: () => setMargin(null),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entries.map((e) => `${e.symbol}|${e.qty}|${e.price}|${e.orderType}`).join(',')]);

  const placeAll = async () => {
    setPlacingAll(true);
    // Sequential, not Promise.all: a live order that already filled can't be
    // un-placed, so each must resolve before the next fires — mirrors how
    // real Kite Web places a basket one order at a time.
    for (const entry of entries) {
      if (entry.status === 'placed') continue;
      setStatus(entry.id, 'placing');
      try {
        const res = await placeOrder.mutateAsync(buildOrderBody({
          tradingsymbol: entry.symbol, exchange: entry.exchange, side: entry.side, quantity: entry.qty,
          product: entry.product, orderType: entry.orderType, price: entry.price, trigger: entry.trigger,
        }));
        setStatus(entry.id, 'placed', undefined, res?.order_id);
      } catch (err: any) {
        setStatus(entry.id, 'failed', err?.message || 'Order failed');
      }
    }
    setPlacingAll(false);
  };

  const allPlaced = entries.length > 0 && entries.every((e) => e.status === 'placed');

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.15)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 60, left: '50%', transform: 'translateX(-50%)', width: 620, maxWidth: '92vw', maxHeight: '80vh', display: 'flex', flexDirection: 'column', background: '#fff', borderRadius: 6, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid #f1f1f1' }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 500, color: '#444' }}>Basket <span style={{ color: '#9b9b9b', fontWeight: 400 }}>({entries.length})</span></h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>

        <div style={{ overflowY: 'auto', flex: 1 }}>
          {entries.length === 0 && <div style={{ padding: 24, color: '#9b9b9b', fontSize: 13 }}>Basket is empty. Add orders from the order ticket or a watchlist row.</div>}
          {entries.map((e) => (
            <div key={e.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 20px', borderBottom: '1px solid #f9f9f9' }}>
              <span style={{ width: 44, fontSize: 11, fontWeight: 700, color: e.side === 'BUY' ? k.blue : k.orange }}>{e.side}</span>
              <span style={{ flex: 1, fontSize: 13, color: '#444' }}><InstrumentLabel symbol={`${e.exchange}:${e.symbol}`} /></span>
              <input type="number" min={1} value={e.qty} disabled={e.status === 'placed'}
                onChange={(ev) => update(e.id, { qty: Number(ev.target.value) })}
                style={{ width: 60, padding: '4px 6px', border: '1px solid #e0e0e0', borderRadius: 3, fontSize: 12, textAlign: 'right' }} />
              {needsPrice(e.orderType) && (
                <input type="number" step={0.05} value={e.price} disabled={e.status === 'placed'}
                  onChange={(ev) => update(e.id, { price: Number(ev.target.value) })}
                  style={{ width: 70, padding: '4px 6px', border: '1px solid #e0e0e0', borderRadius: 3, fontSize: 12, textAlign: 'right' }} />
              )}
              <span style={{ width: 90, fontSize: 11, color: statusColor[e.status], textAlign: 'right' }} title={e.error}>
                {statusLabel[e.status]}
              </span>
              <button onClick={() => remove(e.id)} title="Remove from basket" disabled={e.status === 'placing'}
                style={{ background: 'none', border: 'none', color: '#9b9b9b', cursor: 'pointer', fontSize: 14 }}>✕</button>
            </div>
          ))}
        </div>

        <div style={{ padding: '14px 20px', borderTop: '1px solid #f1f1f1', display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 12, color: k.dim }}>
            Est. margin <b style={{ color: '#444' }}>{margin ? inr(margin.total) : (marginCalc.isPending ? '…' : '—')}</b>
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
            <button onClick={clear} disabled={placingAll} style={{ background: '#fff', color: '#444', border: '1px solid #e0e0e0', borderRadius: 3, padding: '8px 16px', fontSize: 13, cursor: placingAll ? 'not-allowed' : 'pointer' }}>Clear</button>
            <button onClick={placeAll} disabled={entries.length === 0 || placingAll || allPlaced}
              style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, padding: '8px 20px', fontSize: 13, fontWeight: 600, cursor: (entries.length === 0 || placingAll || allPlaced) ? 'not-allowed' : 'pointer', opacity: (entries.length === 0 || placingAll || allPlaced) ? 0.55 : 1 }}>
              {placingAll ? 'Placing…' : allPlaced ? 'All placed' : 'Place Basket'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/kite/__tests__/BasketPane.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useKite.ts frontend/src/components/kite/BasketPane.tsx frontend/src/components/kite/__tests__/BasketPane.test.tsx
git commit -m "feat(kite): add BasketPane with sequential order placement"
```

---

## Task 10: Wire basket entry points

**Files:**
- Modify: `frontend/src/components/kite/OrderWindow.tsx`
- Modify: `frontend/src/components/kite/PortfolioPane.tsx`
- Modify: `frontend/src/components/kite/KiteLayout.tsx`
- Modify: whichever component renders `<KiteLayout>` for the Kite tab (locate via the step below)

- [ ] **Step 1: Add "Add to Basket" to the order ticket footer**

In `frontend/src/components/kite/OrderWindow.tsx`, add the import:

```tsx
import { useKiteBasketStore } from '../../store/useKiteBasketStore';
```

After the `placing`/`buyDisabled` declarations, add:

```tsx
  const addToBasket = useKiteBasketStore((s) => s.add);
  const addCurrentToBasket = () => {
    addToBasket({
      symbol: instr.symbol, exchange: instr.exchange, side, qty,
      product, orderType, price, trigger,
    });
    onClose();
  };
```

In the "regular" tab footer (currently lines 416-424), add a basket button next to Cancel:

```tsx
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', padding: '12px 16px', borderTop: `1px solid ${k.border}`, background: k.surface }}>
                {reqAvail}
                <div style={{ marginLeft: 'auto', paddingLeft: 28, display: 'flex', gap: 10 }}>
                  <button onClick={addCurrentToBasket} title="Add to basket instead of placing now" style={{ ...cancelBtnWide, width: 'auto', padding: '9px 16px', fontSize: 12.5 }}>+ Basket</button>
                  <button onClick={submit} disabled={buyDisabled} style={{ ...primaryBtn, width: 'auto', padding: '9px 28px', fontSize: 13.5, background: accent, opacity: buyDisabled ? 0.55 : 1, cursor: buyDisabled ? 'not-allowed' : 'pointer' }}>{placing ? '…' : side === 'BUY' ? 'Buy' : 'Sell'}</button>
                  <button onClick={onClose} style={{ ...cancelBtnWide, width: 'auto', padding: '9px 22px' }}>Cancel</button>
                </div>
              </div>
            )}
```

(Only the "regular" tab gets the basket button — the "quick" tab stays exactly as-is, matching real Kite where basket-add is a Regular-ticket action.)

- [ ] **Step 2: Add `onBasket` to the PortfolioPane row actions**

In `frontend/src/components/kite/PortfolioPane.tsx`, add the import:

```tsx
import { useKiteBasketStore } from '../../store/useKiteBasketStore';
```

Add, alongside the other hook calls near the top of the component:

```tsx
  const addToBasket = useKiteBasketStore((s) => s.add);
```

In the Positions row's `<KiteActionButtons>` (currently lines 309-314), add an `onBasket` prop:

```tsx
                            <KiteActionButtons 
                              onBuy={(e) => { e.stopPropagation(); handleOpenOrder(id, qty >= 0 ? 'BUY' : 'SELL', Math.abs(qty), p.product, num(p.last_price)); }}
                              buyLabel="Add"
                              onSell={(e) => { e.stopPropagation(); handleOpenOrder(id, qty >= 0 ? 'SELL' : 'BUY', Math.abs(qty), p.product, num(p.last_price)); }}
                              sellLabel="Exit"
                              onBasket={(e) => { e.stopPropagation(); addToBasket({ symbol: p.tradingsymbol, exchange: p.exchange, side: qty >= 0 ? 'SELL' : 'BUY', qty: Math.abs(qty), product: p.product, orderType: 'MARKET', price: 0, trigger: 0 }); }}
                            />
```

In the Holdings row's `<KiteActionButtons>` (currently lines 420-425), add an `onBasket` prop:

```tsx
                            <KiteActionButtons 
                              onBuy={(e) => { e.stopPropagation(); handleOpenOrder(`${h.exchange}:${h.tradingsymbol}`, 'BUY', num(h.quantity), h.product || 'CNC', num(h.last_price)); }}
                              buyLabel="Add"
                              onSell={(e) => { e.stopPropagation(); handleOpenOrder(`${h.exchange}:${h.tradingsymbol}`, 'SELL', num(h.quantity), h.product || 'CNC', num(h.last_price)); }}
                              sellLabel="Exit"
                              onBasket={(e) => { e.stopPropagation(); addToBasket({ symbol: h.tradingsymbol, exchange: h.exchange, side: 'SELL', qty: num(h.quantity), product: (h.product || 'CNC'), orderType: 'MARKET', price: 0, trigger: 0 }); }}
                            />
```

- [ ] **Step 3: Locate where `<KiteLayout>` is rendered for the Kite tab**

Run: `cd frontend/src && grep -rn "<KiteLayout" components/kite/`

This will show the file (likely `KiteDashboard.tsx`) that renders `<KiteLayout ...>` with its `sidebar`/`content`/`rightSidebar` props — that's where the basket-open trigger button and `<BasketPane>` conditional render belong, since it's the component that owns top-level Kite view state.

- [ ] **Step 4: Add the basket trigger button and modal to the file found in Step 3**

In that file, add the imports:

```tsx
import { BasketPane } from './BasketPane';
import { useKiteBasketStore } from '../../store/useKiteBasketStore';
```

Add local state for the basket panel's open/closed state (`const [basketOpen, setBasketOpen] = useState(false);`) alongside that component's other `useState` calls, and read the count:

```tsx
  const basketCount = useKiteBasketStore((s) => s.entries.length);
```

Add a basket icon button with a count badge near wherever that component already renders top-level nav controls (follow the existing pattern for other icon buttons in that file — e.g. matching the `footBtn`-style icon buttons in `KiteLayout.tsx`'s footer, or the top-bar icon style if this file has its own top bar). Import `Icons` from `../../styles/kiteUI` (an `Icons.Basket` already exists there — reuse it, do not write a new inline SVG; Task 8 originally duplicated this icon inline and a code review flagged it, so it was fixed to reuse `Icons.Basket` — don't reintroduce the duplicate):

```tsx
        <button onClick={() => setBasketOpen(true)} title="Basket" style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, background: 'transparent', border: 'none', cursor: 'pointer', color: '#9b9b9b' }}>
          <Icons.Basket />
          {basketCount > 0 && (
            <span style={{ position: 'absolute', top: -4, right: -4, background: '#ff5722', color: '#fff', borderRadius: '50%', minWidth: 15, height: 15, fontSize: 9, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 2px' }}>
              {basketCount}
            </span>
          )}
        </button>
```

And render the panel conditionally, alongside that file's other modal renders:

```tsx
      {basketOpen && <BasketPane onClose={() => setBasketOpen(false)} />}
```

- [ ] **Step 5: Manual verification**

```bash
cd frontend && npm run dev
```

1. From a Positions or Holdings row, hover to reveal the action buttons and click the new basket icon — confirm a toast-free, silent add (no order placed) and the basket badge count increments.
2. Open an order ticket, switch to the Regular tab, click "+ Basket" — confirm it's added and the ticket closes without placing an order.
3. Click the basket icon to open `BasketPane` — confirm rows show correct symbol/side/qty, editing qty/price updates the row, and the estimated margin updates (debounced) as you edit.
4. Click "Place Basket" with 2+ entries — confirm orders place one at a time (watch the Orders pane fill in sequentially, not all at once), each row's status updates from Placing → Placed, and removing a still-pending row before placement works.
5. Force one entry to fail (e.g. an obviously invalid quantity) and confirm it shows "Failed" with the reason, stays in the basket, and doesn't block the other entries from placing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/kite/OrderWindow.tsx frontend/src/components/kite/PortfolioPane.tsx frontend/src/components/kite/KiteLayout.tsx
git commit -m "feat(kite): wire basket entry points (order ticket, positions/holdings rows, nav trigger)"
```

(Adjust the `git add` file list in this step if Step 3 found a different file than `KiteLayout.tsx` itself for the trigger button — add whichever file was actually modified.)

---

## Task 11: MCX backlog documentation

**Files:**
- Modify: `backend/app/services/exchanges/kite/constants.py`
- Modify: `MARKETS.md`

- [ ] **Step 1: Add the deferral comment in constants.py**

In `backend/app/services/exchanges/kite/constants.py`, find the line:

```python
EXCHANGE_MCX = "MCX"
```

Change it to:

```python
# Declared for completeness (Kite Connect lists MCX as a valid exchange) but NOT
# wired into app/services/kite_engine/universe.py — the auto-scan universe is
# built around equity+options pairs (NFO/BFO derivatives + index underlyings),
# and MCX is commodity FUTURES only, which needs a different strategy shape.
# Manual order placement to MCX already works via the generic order route.
# Full auto-engine MCX support is an explicit backlog item, planned for a
# dedicated pass before production rollover — see
# docs/superpowers/specs/2026-07-10-kite-parity-polish-design.md.
EXCHANGE_MCX = "MCX"
```

- [ ] **Step 2: Correct the MARKETS.md claim**

In `MARKETS.md`, find the table row:

```
| `commodities` | commodity futures (incl. natural gas) | zerodha |
```

Change it to:

```
| `commodities` | commodity futures (incl. natural gas) | zerodha — **manual trading only**; declared in `constants.py` but not yet wired into the auto-scan universe (backlog item, see `docs/superpowers/specs/2026-07-10-kite-parity-polish-design.md`) |
```

- [ ] **Step 3: Verify**

```bash
grep -n "EXCHANGE_MCX" backend/app/services/exchanges/kite/constants.py
grep -n "commodities" MARKETS.md
```

Expected: both show the updated text.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/exchanges/kite/constants.py MARKETS.md
git commit -m "docs(kite): mark MCX auto-engine support as an explicit backlog item"
```

---

## Final check

- [ ] Run the full frontend test suite and confirm no regressions: `cd frontend && npx vitest run`
- [ ] Run `cd frontend && npx tsc --noEmit` and confirm a clean typecheck
- [ ] Run through the manual verification steps from Tasks 2, 4, 5, 6, 10 once more in a single session to confirm nothing regressed when combined
- [ ] Confirm the design spec's "Out of scope" items were genuinely left untouched (no accidental edits to `SterlingKiteEnginePane.tsx` or test-coverage scope creep)
