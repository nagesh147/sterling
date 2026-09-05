# A01 — `ReplayDock` (the shell)

**File:** `frontend/src/components/kite/replay/ReplayDock.tsx`
**Replaces:** the outer shell of `SimulationBar.tsx` (`:1077–1191`)
**Fixes:** D3 (mount), D4 (stacking), D6 (decomposition), D8 (hex), D11 (resizer a11y),
D17 (host coupling), D20 (persistence)

---

## 1. Responsibility

The shell owns exactly four things and nothing else:

1. Which **mode** the dock is in, and the geometry that mode implies.
2. The **height** in the resizable modes, and its persistence.
3. **Portalling** for `overlay` and `fullscreen`.
4. Hosting the single **live region** and the **keyboard scope** root.

It renders no controls, no data, no tables. Everything else is a child.

## 2. Public contract

```tsx
export function ReplayDock(): JSX.Element | null;
```

No props. It reads `useReplayStore` and is mounted exactly where `SimulationBar` is
today (`KiteLayout.tsx:316` classic, `:700` Mac stage). Returning `null` when
`!open` is preserved.

## 3. Structure

```tsx
<>
  {mode === 'docked' || mode === 'expanded'
    ? shell
    : createPortal(mode === 'fullscreen' ? fullscreenWrapper : overlayWrapper, document.body)}

  {createPortal(<ReplayToastHost />, document.body)}
  {createPortal(<ReplaySummaryModal />, document.body)}
</>
```

`shell`:

```tsx
<section
  ref={rootRef}
  tabIndex={-1}
  data-replay-root=""
  data-testid="replay-dock"
  data-mode={mode}
  data-state={state}
  data-width={widthBucket}          // xl | lg | md | sm, from ResizeObserver
  className="replay-dock kw-pane"
  aria-label="Market replay"
  style={geometry[mode]}
>
  {isResizable && <ReplayResizer height={height} onHeight={setHeight} />}
  <ReplayShellBar />
  <ReplayCommandRail />          {/* ReplayTransport + ReplayTimeline */}
  <ReplayMetricsStrip />
  <ReplayViewBar />              {/* Segmented + session + filters */}
  <ReplayContent />              {/* the active tab only — mounted, not display:none */}
  <ReplayConfigSheet />          {/* absolutely positioned inside the dock */}
  <div aria-live="polite" aria-atomic="true" className="rd-sr-only">{announcement}</div>
</section>
```

Keeping `kw-pane` gives the dock the workspace's entry animation and border idiom for
free. Keep it.

## 4. Geometry

```ts
const geometry: Record<Mode, React.CSSProperties> = {
  docked: {
    width: '100%',
    flexShrink: 0,
    height: `${height}px`,
    borderTop: '1px solid var(--k-border-strong-4)',
  },
  expanded: {
    width: '100%', height: '100%', flex: 1, minHeight: 0, borderTop: 'none',
  },
  overlay: {
    position: 'fixed', left: 0, right: 0, bottom: FOOTER_H,   // FOOTER_H = 36
    height: `${height}px`,
    zIndex: 'var(--rd-z-dock)',
    borderTop: '1px solid var(--k-border-strong-4)',
    boxShadow: '0 -8px 24px color-mix(in srgb, var(--k-text) 10%, transparent)',
  },
  fullscreen: {
    position: 'fixed', inset: 0, zIndex: 'var(--rd-z-fullscreen)',
  },
};
```

`FOOTER_H` must be imported from a shared constant, not re-typed as `36`. Define it in
`frontend/src/components/kite/layoutConstants.ts` and have `KiteLayout` consume the same
value, so a footer height change cannot desync the dock.

The current fullscreen wrapper hardcodes `background: '#efefef'` and
`border: '1px solid #e4e4e4'` (D8). Replace with `var(--k-surface-sunken)` and
`var(--k-border-strong)`.

## 5. Resizer — must be accessible

Replace the bare `<div onMouseDown>` with:

```tsx
<div
  role="separator"
  aria-orientation="horizontal"
  aria-label="Resize replay dock"
  aria-valuenow={height}
  aria-valuemin={MIN_H}
  aria-valuemax={maxHeight}
  tabIndex={0}
  className="rd-resizer"
  data-active={dragging}
  onPointerDown={startDrag}
  onKeyDown={onResizeKey}   // ↑/↓ = 16px, Shift+↑/↓ = 64px, Home/End = min/max
/>
```

- `MIN_H = 220` (see `02_DESIGN_SYSTEM.md §4.2`; today's 160 leaves 54 px of content).
- `maxHeight = containerHeight - 120` in `docked`, `window.innerHeight - FOOTER_H - 80`
  in `overlay`.
- Use **pointer events with capture**, not `window` mouse listeners:
  `e.currentTarget.setPointerCapture(e.pointerId)`. The current implementation attaches
  and removes `window` listeners inside the handler and leaks if the component unmounts
  mid-drag.
- Throttle to `requestAnimationFrame`; write to `localStorage` only on `pointerup`, not
  on every move (today it writes on every `mousemove`).
- Add `user-select: none` on `document.body` during drag and remove it after, or the
  drag selects table text.

`KiteLayout.tsx` already implements exactly this pattern for its workspace resizers.
Read it and match it rather than inventing a second one.

## 6. Mode changes

```ts
function cycleMode() { docked → expanded → overlay → docked }
```

Rules:
- Entering `expanded` sets `dockHostHidden` in the store; `KiteLayout` subscribes to
  **that one boolean** instead of deriving `isSimFullHeight` from
  `mode === 'fullheight'` (fixes D17 — the host no longer needs to know the dock's mode
  vocabulary).
- Leaving `fullscreen` always returns to the mode you were in before it, stored in
  `prevMode`.
- `Escape` steps *down* one level rather than jumping straight to docked, so a user in
  fullscreen does not lose their overlay sizing.
- Mode changes animate per M3. Because `docked`/`expanded` change the *host's* layout,
  the transition must be on the dock's `height` only — never on the host's flex — or the
  workspace janks.

## 7. Width buckets

```ts
useEffect(() => {
  const ro = new ResizeObserver(([entry]) => {
    const w = entry.contentRect.width;
    setWidthBucket(w >= 1100 ? 'xl' : w >= 900 ? 'lg' : w >= 700 ? 'md' : 'sm');
  });
  if (rootRef.current) ro.observe(rootRef.current);
  return () => ro.disconnect();
}, []);
```

Children read `[data-width]` from an ancestor selector in CSS. No component takes a
`width` prop.

## 8. Keyboard scope

```ts
useEffect(() => {
  if (!open) return;
  const onKey = (e: KeyboardEvent) => {
    const owned = mode === 'overlay' || mode === 'fullscreen'
      || (rootRef.current?.contains(document.activeElement) ?? false);
    if (!owned) return;
    if (isTextEntry(e.target)) return;   // input, textarea, select, [contenteditable], [role=textbox], [data-swallow-keys]
    dispatchShortcut(e);
  };
  document.addEventListener('keydown', onKey);
  return () => document.removeEventListener('keydown', onKey);
}, [open, mode]);
```

Bind on `document`, not `window`, and always in the bubble phase so a focused control can
`stopPropagation` first.

## 9. Acceptance criteria

- [ ] Dock renders in all four modes; each mode's geometry matches §4 exactly.
- [ ] Height persists across reload; mode and tab persist; `fullscreen` does **not**.
- [ ] Resizer is reachable by Tab, resizable by ↑/↓, announces `aria-valuenow`.
- [ ] Dragging the resizer to the top clamps at `maxHeight`; to the bottom at 220 px.
- [ ] No hardcoded hex anywhere in the file (`grep -n "#[0-9a-fA-F]\{3,6\}"` returns nothing).
- [ ] In dark mode the dock's border and shadow are visible against `--k-bg`.
- [ ] Pressing Space while a *different* pane's input has focus does not toggle the replay.
- [ ] Unmounting mid-drag leaves no listener (verified by a test that unmounts during a
      synthetic pointer sequence).
- [ ] Toast and summary render **above** the fullscreen dock.

## 10. Tests

`frontend/src/components/kite/replay/__tests__/ReplayDock.test.tsx`

1. renders nothing when `open === false`
2. each mode applies its geometry (assert on `data-mode` + computed style keys)
3. resizer keyboard: ArrowUp raises height by 16, Shift+ArrowUp by 64, clamps at bounds
4. height persists to `sterling:replay-dock:ui` on pointerup only (spy on `setItem`)
5. `fullscreen` in stored prefs loads as `overlay`
6. Space in an input outside the dock does not call `transport.pause`
7. Escape steps fullscreen→overlay→docked→closed
8. width bucket updates `data-width` when `ResizeObserver` fires (mock it)
