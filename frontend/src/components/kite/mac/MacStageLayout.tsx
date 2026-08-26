import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useMacKite } from '../../../hooks/useMacKite';

/* ─────────────────────────────────────────────────────────────────────────
 * MacStageLayout — macOS Stage-Manager-style free-drag workspace.
 *
 * Rendered ONLY when Mac Kite mode is on (KiteLayout branches on `useMacKite().on`).
 * The same four Kite panels (watchlist / content / supertrend / terminal) become
 * draggable, reorderable widgets. Dragging a panel by its grip handle makes the
 * neighbours part ways and resize with the `stage` spring (Framer layout / FLIP);
 * dropping snaps the panel into the slot under the pointer, and a ghost
 * placeholder previews the target slot during the drag.
 *
 * Slot model — four named slots arranged like the canonical Kite layout:
 *   ┌──────────┬─────────────┬──────────┐
 *   │   left   │   center    │  right   │   (top row, flexes by slot widths)
 *   ├──────────┴─────────────┴──────────┤
 *   │            bottom (dock)          │
 *   └───────────────────────────────────┘
 * Each panel lives in exactly one slot. Arrangement persists to localStorage
 * (`kite_stage_layout`); a reset restores the canonical mapping.
 *
 * The whole panel surface is NOT draggable — these panels contain live trading
 * controls. Only the grip handle in each panel's top strip starts a drag (via
 * Framer `dragControls` + `dragListener={false}`). `will-change: transform`
 * is applied only while a panel is actively dragging.
 * ───────────────────────────────────────────────────────────────────────── */

type PanelKey = 'sidebar' | 'content' | 'rightSidebar' | 'bottomBar';
type SlotKey = 'left' | 'center' | 'right' | 'bottom';

const STORAGE_KEY = 'kite_stage_layout';

const PANEL_TITLE: Record<PanelKey, string> = {
  sidebar: 'Watchlist',
  content: 'Markets',
  rightSidebar: 'SuperTrend',
  bottomBar: 'Terminal',
};

// Canonical arrangement that mirrors the stock Kite layout.
const DEFAULT_MAP: Record<PanelKey, SlotKey> = {
  sidebar: 'left',
  content: 'center',
  rightSidebar: 'right',
  bottomBar: 'bottom',
};

const ALL_PANELS: PanelKey[] = ['sidebar', 'content', 'rightSidebar', 'bottomBar'];
const VALID_SLOTS: SlotKey[] = ['left', 'center', 'right', 'bottom'];

/* ── Snap-layout presets ─────────────────────────────────────────────────────
 * Full arrangements offered as one-click "suggested layouts", and as drop
 * targets while dragging (drop a panel onto a suggestion to apply that whole
 * arrangement — macOS/Win11 snap-layout style). Each maps all four panels to a
 * slot; two panels in the same slot stack within it. */
interface LayoutPreset {
  id: string;
  label: string;
  map: Record<PanelKey, SlotKey>;
}
const LAYOUT_PRESETS: LayoutPreset[] = [
  { id: 'classic', label: 'Classic', map: { sidebar: 'left', content: 'center', rightSidebar: 'right', bottomBar: 'bottom' } },
  { id: 'focus', label: 'Focus markets', map: { sidebar: 'left', content: 'center', rightSidebar: 'right', bottomBar: 'center' } },
  { id: 'rstack', label: 'Right stack', map: { sidebar: 'left', content: 'center', rightSidebar: 'right', bottomBar: 'right' } },
  { id: 'lstack', label: 'Left stack', map: { sidebar: 'left', content: 'center', rightSidebar: 'left', bottomBar: 'bottom' } },
  { id: 'twoup', label: 'Two-up center', map: { sidebar: 'left', content: 'center', rightSidebar: 'center', bottomBar: 'bottom' } },
  { id: 'dock', label: 'Wide + dock', map: { sidebar: 'left', content: 'center', rightSidebar: 'bottom', bottomBar: 'bottom' } },
];

function mapsEqual(a: Record<PanelKey, SlotKey>, b: Record<PanelKey, SlotKey>): boolean {
  return ALL_PANELS.every((p) => a[p] === b[p]);
}

// `useDragControls` is not exposed by MacMotionProvider's context (which only
// hands out motion / AnimatePresence / LayoutGroup). We resolve it from the same
// dynamically-imported framer-motion module — never a STATIC import. The provider
// has already loaded the module by the time `on` is true, so this resolves from
// cache synchronously on the first effect tick.
let useDragControlsRef: ((...args: any[]) => any) | null = null;

function loadMap(): Record<PanelKey, SlotKey> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_MAP };
    const parsed = JSON.parse(raw) as Partial<Record<PanelKey, SlotKey>>;
    const merged: Record<PanelKey, SlotKey> = { ...DEFAULT_MAP };
    for (const p of ALL_PANELS) {
      const s = parsed[p];
      if (s && VALID_SLOTS.includes(s)) merged[p] = s;
    }
    return merged;
  } catch {
    return { ...DEFAULT_MAP };
  }
}

function saveMap(map: Record<PanelKey, SlotKey>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    // localStorage may throw in private mode / quota exceeded — layout is non-critical
    void 0;
  }
}

export interface MacStageLayoutProps {
  sidebar?: React.ReactNode;
  content: React.ReactNode;
  rightSidebar?: React.ReactNode;
  bottomBar?: React.ReactNode;
}

interface StagePanelProps {
  panelKey: PanelKey;
  child: React.ReactNode;
  isDragging: boolean;
  collapsed?: boolean;
  motion: any;
  stage: any;
  onDragStart: (key: PanelKey) => void;
  onDrag: (info: { point: { x: number; y: number } }) => void;
  onDragEnd: (key: PanelKey, info: { point: { x: number; y: number } }) => void;
}

/* Shared panel chrome. `controls` is either a real Framer DragControls instance
 * (handle-only drag) or null (whole-surface drag fallback before the hook loads). */
function StagePanelInner({
  panelKey,
  child,
  isDragging,
  collapsed,
  motion,
  stage,
  onDragStart,
  onDrag,
  onDragEnd,
  controls,
}: StagePanelProps & { controls: { start: (e: any) => void } | null }) {
  const MotionDiv = motion.div;

  return (
    <MotionDiv
      layout
      layoutId={`stage-panel-${panelKey}`}
      transition={stage}
      drag
      dragControls={controls ?? undefined}
      dragListener={controls ? false : true}
      dragMomentum={false}
      dragElastic={0.12}
      dragSnapToOrigin
      onDragStart={() => onDragStart(panelKey)}
      onDrag={(_e: any, info: any) => onDrag(info)}
      onDragEnd={(_e: any, info: any) => onDragEnd(panelKey, info)}
      className="mac-gpu"
      style={{
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        minHeight: 0,
        // Collapsed (terminal minimized) → shrink to the grip + footer bar so it
        // never fills the slot as a tall empty panel.
        flex: collapsed ? '0 0 auto' : 1,
        background: 'var(--k-bg)',
        border: '1px solid var(--k-border)',
        borderRadius: 8,
        overflow: 'hidden',
        boxShadow: isDragging ? '0 12px 40px rgba(0,0,0,0.18)' : '0 1px 3px rgba(0,0,0,0.06)',
        willChange: isDragging ? 'transform' : 'auto',
        zIndex: isDragging ? 1000 : 1,
        position: 'relative',
      }}
    >
      {/* ── Drag handle strip (the ONLY draggable surface) ── */}
      <div
        title="Drag to rearrange"
        onPointerDown={(e) => {
          if (controls) controls.start(e);
        }}
        style={{
          flexShrink: 0,
          height: 26,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '0 10px',
          borderBottom: '1px solid var(--k-border-3)',
          background: 'var(--k-surface-2)',
          cursor: 'grab',
          userSelect: 'none',
          touchAction: 'none',
        }}
      >
        <span style={{ display: 'flex', gap: 2, color: '#c4c4c4' }}>
          <Dot />
          <Dot />
          <Dot />
        </span>
        <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--k-dim)', letterSpacing: 0.4 }}>
          {PANEL_TITLE[panelKey]}
        </span>
      </div>

      {/* ── Live panel content (interactive — never starts a drag) ── */}
      <div style={{ flex: collapsed ? '0 0 auto' : 1, minHeight: 0, overflow: collapsed ? 'visible' : 'auto' }}>{child}</div>
    </MotionDiv>
  );
}

/* Mounted only after `useDragControlsRef` is set — always calls the hook
 * unconditionally (Rules of Hooks). Switching between this and StagePanelFallback
 * is a component swap (unmount/remount), not a conditional hook call. */
function StagePanelWithControls(props: StagePanelProps) {
  // useDragControlsRef is guaranteed non-null by the parent branch.
  const controls = useDragControlsRef!();
  return <StagePanelInner {...props} controls={controls} />;
}

/* Fallback before framer-motion drag controls resolve: whole-surface drag. */
function StagePanelFallback(props: StagePanelProps) {
  return <StagePanelInner {...props} controls={null} />;
}

function StagePanel(props: StagePanelProps) {
  const Panel = useDragControlsRef ? StagePanelWithControls : StagePanelFallback;
  return <Panel {...props} />;
}

export function MacStageLayout({ sidebar, content, rightSidebar, bottomBar }: MacStageLayoutProps) {
  const { motion, LayoutGroup, sp } = useMacKite();

  const [map, setMap] = useState<Record<PanelKey, SlotKey>>(loadMap);
  const [dragging, setDragging] = useState<PanelKey | null>(null);
  const [hoverSlot, setHoverSlot] = useState<SlotKey | null>(null);
  const [hoverPreset, setHoverPreset] = useState<string | null>(null);
  // Bump once useDragControls resolves so panels re-render with handle-only drag.
  const [controlsReady, setControlsReady] = useState(() => !!useDragControlsRef);

  // Listen to terminal minimize so we can collapse the bottom slot height and give space to chart/content.
  const [terminalMode, setTerminalMode] = useState<'minimized' | 'normal' | 'partial' | 'full'>(() => {
    const v = localStorage.getItem('kite_terminal_mode');
    return v === 'minimized' || v === 'partial' || v === 'full' ? v : 'normal';
  });
  useEffect(() => {
    const cb = (e: any) => {
      setTerminalMode(e.detail);
      // Deeper sync: notify charts to resize when terminal min/max affects space
      window.dispatchEvent(new CustomEvent('kite-pane-toggle'));
    };
    window.addEventListener('kite-terminal-mode', cb);
    return () => window.removeEventListener('kite-terminal-mode', cb);
  }, []);

  // Resolve useDragControls from the (already cached) framer-motion module.
  // Mount-once: only needs to resolve the lazy framer-motion export; no reactive deps.
  useEffect(() => {
    if (useDragControlsRef) {
      setControlsReady(true);
      return;
    }
    let alive = true;
    import('framer-motion').then((m) => {
      if (!alive) return;
      useDragControlsRef = m.useDragControls;
      setControlsReady(true);
    });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional one-shot module resolve
  }, []);

  // Live geometry of each slot so we can hit-test the pointer against the
  // actual rendered slots (robust to resizing/reflow).
  const slotRects = useRef<Partial<Record<SlotKey, DOMRect>>>({});
  const registerSlot = useCallback((slot: SlotKey, el: HTMLElement | null) => {
    if (el) slotRects.current[slot] = el.getBoundingClientRect();
  }, []);

  // Live geometry of the suggested-layout thumbnails (drop targets while dragging).
  const presetRects = useRef<Partial<Record<string, DOMRect>>>({});
  const registerPreset = useCallback((id: string, el: HTMLElement | null) => {
    if (el) presetRects.current[id] = el.getBoundingClientRect();
  }, []);

  const nodeFor = useCallback(
    (key: PanelKey): React.ReactNode => {
      switch (key) {
        case 'sidebar':
          return sidebar;
        case 'content':
          return content;
        case 'rightSidebar':
          return rightSidebar;
        case 'bottomBar':
          return bottomBar;
      }
    },
    [sidebar, content, rightSidebar, bottomBar],
  );

  const panelsInSlot = useCallback(
    (slot: SlotKey): PanelKey[] => ALL_PANELS.filter((p) => map[p] === slot && nodeFor(p) != null),
    [map, nodeFor],
  );

  const hitTest = useCallback((x: number, y: number): SlotKey | null => {
    const rects = slotRects.current;
    let found: SlotKey | null = null;
    VALID_SLOTS.forEach((slot) => {
      const r = rects[slot];
      if (r && x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) found = slot;
    });
    return found;
  }, []);

  const hitTestPreset = useCallback((x: number, y: number): string | null => {
    const rects = presetRects.current;
    let found: string | null = null;
    LAYOUT_PRESETS.forEach((p) => {
      const r = rects[p.id];
      if (r && x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) found = p.id;
    });
    return found;
  }, []);

  const applyPreset = useCallback((m: Record<PanelKey, SlotKey>) => {
    const next = { ...m };
    setMap(next);
    saveMap(next);
  }, []);

  const resetLayout = useCallback(() => {
    applyPreset(DEFAULT_MAP);
  }, [applyPreset]);

  // The footer reset button (KiteLayout) drives the stage reset in Mac mode.
  useEffect(() => {
    const cb = () => resetLayout();
    window.addEventListener('kite-stage-reset', cb);
    return () => window.removeEventListener('kite-stage-reset', cb);
  }, [resetLayout]);

  const onDragStart = useCallback((key: PanelKey) => {
    document.querySelectorAll<HTMLElement>('[data-stage-slot]').forEach((el) => {
      const raw = el.getAttribute('data-stage-slot');
      const s = raw && (VALID_SLOTS as readonly string[]).includes(raw) ? (raw as SlotKey) : null;
      if (s) slotRects.current[s] = el.getBoundingClientRect();
    });
    document.querySelectorAll<HTMLElement>('[data-stage-preset]').forEach((el) => {
      const id = el.getAttribute('data-stage-preset');
      if (id) presetRects.current[id] = el.getBoundingClientRect();
    });
    setDragging(key);
  }, []);

  const onDrag = useCallback(
    (info: { point: { x: number; y: number } }) => {
      // A suggested-layout thumbnail under the pointer takes priority over a slot.
      const preset = hitTestPreset(info.point.x, info.point.y);
      setHoverPreset(preset);
      setHoverSlot(preset ? null : hitTest(info.point.x, info.point.y));
    },
    [hitTest, hitTestPreset],
  );

  const onDragEnd = useCallback(
    (key: PanelKey, info: { point: { x: number; y: number } }) => {
      const presetId = hitTestPreset(info.point.x, info.point.y);
      if (presetId) {
        // Dropped onto a suggested layout → apply that whole arrangement.
        const preset = LAYOUT_PRESETS.find((p) => p.id === presetId);
        if (preset) applyPreset(preset.map);
      } else {
        const target = hitTest(info.point.x, info.point.y);
        setMap((prev) => {
          if (target && target !== prev[key]) {
            const next = { ...prev, [key]: target };
            saveMap(next);
            return next;
          }
          return prev;
        });
      }
      setDragging(null);
      setHoverSlot(null);
      setHoverPreset(null);
    },
    [hitTest, hitTestPreset, applyPreset],
  );

  const MotionDiv = motion?.div;
  const Group = LayoutGroup;
  // KiteLayout only renders this when `on` is true (framer loaded), so these are
  // present. Guard anyway to keep tsc/runtime safe.
  if (!MotionDiv || !Group) return null;

  const stage = sp('stage');

  const renderSlot = (slot: SlotKey, flexBasis: string) => {
    const panels = panelsInSlot(slot);
    const isBottom = slot === 'bottom';
    const isTarget = hoverSlot === slot && dragging !== null;
    // Minimized terminal: collapse the bottom dock to just the grip + footer bar
    // (grip 26 + footer ~32). Avoids a tall empty terminal panel.
    const termMinimized = terminalMode === 'minimized';
    const bottomHeight = isBottom && termMinimized ? 60 : 220;
    return (
      <MotionDiv
        layout
        data-stage-slot={slot}
        ref={(el: HTMLElement | null) => registerSlot(slot, el)}
        transition={stage}
        style={{
          position: 'relative',
          display: 'flex',
          flexDirection: isBottom ? 'row' : 'column',
          gap: 8,
          minWidth: 0,
          minHeight: 0,
          ...(isBottom
            ? { height: bottomHeight, flexShrink: 0 }
            : { flex: panels.length === 0 ? '0 0 0px' : flexBasis }),
        }}
      >
        {isTarget && (
          <MotionDiv
            layout
            transition={stage}
            style={{
              position: 'absolute',
              inset: 4,
              border: '2px dashed var(--k-brand)',
              borderRadius: 10,
              background: 'rgba(240,100,40,0.06)',
              pointerEvents: 'none',
              zIndex: 5,
            }}
          />
        )}
        {panels.map((p) => (
          <StagePanel
            key={`${p}-${controlsReady ? 'c' : 'n'}`}
            panelKey={p}
            child={nodeFor(p)}
            isDragging={dragging === p}
            collapsed={p === 'bottomBar' && termMinimized}
            motion={motion}
            stage={stage}
            onDragStart={onDragStart}
            onDrag={onDrag}
            onDragEnd={onDragEnd}
          />
        ))}
      </MotionDiv>
    );
  };

  const TOP_SLOTS: SlotKey[] = ['left', 'center', 'right'];
  const topEmpty = TOP_SLOTS.every((s) => panelsInSlot(s).length === 0);
  const bottomPanels = panelsInSlot('bottom');

  return (
    <div
      className="mac-canvas"
      style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden', position: 'relative' }}
    >
      {/* Stage toolbar — reset to canonical arrangement. */}
      <div
        style={{
          flexShrink: 0,
          height: 28,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '0 12px',
          borderBottom: '1px solid var(--k-border-3)',
          background: 'var(--k-bg)',
        }}
      >
        <span style={{ fontSize: 10, color: 'var(--k-dim)', letterSpacing: 0.4 }}>STAGE</span>
        <span style={{ fontSize: 10, color: dragging ? 'var(--k-brand)' : '#c4c4c4', transition: 'color 0.2s' }}>
          {dragging ? 'drop on a layout below, or into a slot' : 'drag a panel grip to rearrange'}
        </span>

        {/* Suggested layouts — click to apply, or drop a dragged panel onto one. */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          {LAYOUT_PRESETS.map((p) => (
            <PresetThumb
              key={p.id}
              preset={p}
              active={mapsEqual(map, p.map)}
              highlighted={hoverPreset === p.id}
              dragging={dragging !== null}
              onApply={() => applyPreset(p.map)}
              registerRef={(el) => registerPreset(p.id, el)}
            />
          ))}
          <span style={{ width: 1, height: 16, background: 'var(--k-border)', margin: '0 2px' }} />
          <button
            onClick={resetLayout}
            title="Reset stage arrangement to default"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              height: 20,
              padding: '0 8px',
              fontSize: 10,
              color: 'var(--k-dim)',
              background: 'transparent',
              border: '1px solid var(--k-border)',
              borderRadius: 4,
              cursor: 'pointer',
            }}
          >
            Reset
          </button>
        </div>
      </div>

      <Group>
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            padding: 8,
            overflow: 'hidden',
            minHeight: 0,
          }}
        >
          {/* Top row: left | center | right */}
          <div style={{ flex: 1, display: 'flex', gap: 8, minHeight: 0, minWidth: 0 }}>
            {renderSlot('left', '0 0 360px')}
            {renderSlot('center', '1 1 0%')}
            {renderSlot('right', '0 0 520px')}
            {topEmpty && <div style={{ flex: 1 }} />}
          </div>

          {/* Bottom dock */}
          {bottomPanels.length > 0 ? (
            renderSlot('bottom', '')
          ) : (
            /* Empty dock target — only visible while dragging, so a panel can be
               docked even when the bottom slot is currently empty. */
            <div
              data-stage-slot="bottom"
              ref={(el) => registerSlot('bottom', el)}
              style={{
                flexShrink: 0,
                height: dragging ? 48 : 0,
                transition: 'height 0.2s',
                borderRadius: 8,
                position: 'relative',
                border: dragging ? '2px dashed var(--k-border)' : 'none',
              }}
            >
              {hoverSlot === 'bottom' && dragging && (
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    border: '2px dashed var(--k-brand)',
                    borderRadius: 8,
                    background: 'rgba(240,100,40,0.06)',
                  }}
                />
              )}
            </div>
          )}
        </div>
      </Group>
    </div>
  );
}

function Dot() {
  return <span style={{ width: 4, height: 4, borderRadius: 2, background: 'currentColor' }} />;
}

/* A mini diagram of a full arrangement. Click to apply; while a panel is being
 * dragged it doubles as a drop target (data-stage-preset + registered rect). */
interface PresetThumbProps {
  preset: LayoutPreset;
  active: boolean;
  highlighted: boolean;
  dragging: boolean;
  onApply: () => void;
  registerRef: (el: HTMLElement | null) => void;
}
function PresetThumb({ preset, active, highlighted, dragging, onApply, registerRef }: PresetThumbProps) {
  const perSlot = (slot: SlotKey) => ALL_PANELS.filter((p) => preset.map[p] === slot);
  const ORANGE = 'var(--k-brand)';

  const cells = (slot: SlotKey, dir: 'col' | 'row') => {
    const n = perSlot(slot).length;
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: dir === 'col' ? 'column' : 'row', gap: 1, minWidth: 0, minHeight: 0 }}>
        {n === 0
          ? <div style={{ flex: 1, borderRadius: 1, background: 'var(--k-surface-hover-2)' }} />
          : perSlot(slot).map((p) => (
              <div key={p} style={{ flex: 1, borderRadius: 1, background: highlighted || active ? ORANGE : '#bcbcbc' }} />
            ))}
      </div>
    );
  };

  const hasBottom = perSlot('bottom').length > 0;
  const borderColor = highlighted ? ORANGE : active ? ORANGE : 'var(--k-border)';

  return (
    <button
      ref={registerRef as any}
      data-stage-preset={preset.id}
      onClick={onApply}
      title={`${preset.label}${active ? ' (current)' : ''}`}
      style={{
        width: 46,
        height: 26,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        padding: 2,
        cursor: 'pointer',
        background: highlighted ? 'rgba(240,100,40,0.10)' : active ? 'rgba(240,100,40,0.06)' : 'var(--k-bg)',
        border: `1px solid ${borderColor}`,
        borderRadius: 4,
        boxShadow: highlighted ? `0 0 0 2px rgba(240,100,40,0.25)` : 'none',
        transform: dragging && highlighted ? 'scale(1.08)' : 'scale(1)',
        transition: 'transform 0.18s cubic-bezier(0.16,1,0.3,1), box-shadow 0.18s, background 0.18s, border-color 0.18s',
      }}
    >
      {/* top row: left | center | right */}
      <div style={{ flex: 1, display: 'flex', gap: 1, minHeight: 0 }}>
        <div style={{ flexBasis: '28%', display: 'flex', minWidth: 0 }}>{cells('left', 'col')}</div>
        <div style={{ flex: 1, display: 'flex', minWidth: 0 }}>{cells('center', 'col')}</div>
        <div style={{ flexBasis: '28%', display: 'flex', minWidth: 0 }}>{cells('right', 'col')}</div>
      </div>
      {/* bottom dock */}
      {hasBottom && <div style={{ height: 6, display: 'flex' }}>{cells('bottom', 'row')}</div>}
    </button>
  );
}
