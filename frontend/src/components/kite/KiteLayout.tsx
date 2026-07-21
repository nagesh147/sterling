import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { k, Icons } from '../../styles/kiteUI';
import { useMacKite } from '../../hooks/useMacKite';
import { useEngineActivity } from '../../hooks/useSterlingKiteEngine';
import { useLiveSignalCount } from '../../store/useLiveSignalCount';
import { MacKiteToggle } from './mac/MacKiteToggle';
import { MacStageLayout } from './mac/MacStageLayout';
import {
  WORKSPACE_LAYOUT_KEY,
  WORKSPACE_PANES,
  WORKSPACE_SLOTS,
  applyWorkspacePreset,
  clampWorkspaceSizes,
  cloneDefaultWorkspaceLayout,
  loadWorkspaceLayout,
  minimizePane,
  movePaneToSlot,
  paneSlot,
  restoreAllPanes,
  restorePane,
  type WorkspaceFocus,
  type WorkspaceFocusMode,
  type WorkspacePaneId,
  type WorkspacePresetId,
  type WorkspaceSlotId,
} from './workspaceLayout';

export type NavItem = 'dashboard' | 'orders' | 'holdings' | 'positions' | 'more' | 'connect';
export type MoreTab = 'bids' | 'funds' | 'mf' | 'alerts' | 'backtest' | 'data';

interface KiteLayoutProps {
  activeNav: NavItem;
  onNavClick: (nav: NavItem) => void;
  sidebar?: React.ReactNode;
  rightSidebar?: React.ReactNode;
  bottomBar?: React.ReactNode;
  centerTopBar?: React.ReactNode;
  content: React.ReactNode;
  onBasketClick?: () => void;
  basketCount?: number;
}

interface PaneDefinition {
  id: WorkspacePaneId;
  title: string;
  shortTitle: string;
  accent: string;
  content: React.ReactNode;
}

type ResizeAxis = 'left' | 'right' | 'bottom';

interface ResizeSession {
  axis: ResizeAxis;
  pointerId: number;
  startX: number;
  startY: number;
  startLeft: number;
  startRight: number;
  startBottom: number;
}

const SLOT_LABEL: Record<WorkspaceSlotId, string> = {
  left: 'Left dock',
  center: 'Main dock',
  right: 'Right dock',
  bottom: 'Bottom dock',
};

const PRESET_META: Array<{ id: WorkspacePresetId; label: string; detail: string }> = [
  { id: 'classic', label: 'Classic', detail: 'Balanced four-pane desk' },
  { id: 'chart', label: 'Chart focus', detail: 'More room for the dashboard' },
  { id: 'execution', label: 'Execution', detail: 'Signals and terminal forward' },
];

const WORKSPACE_CSS = `
@keyframes kl-scan-pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .3; transform: scale(.65); } }
@keyframes kl-scan-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
@keyframes kw-pane-in { from { opacity: .65; transform: scale(.995); } to { opacity: 1; transform: scale(1); } }
.kl-scan-dot { animation: kl-scan-pulse 1.1s ease-in-out infinite; }
.kl-scan-text { background-image: linear-gradient(90deg,#d35400 0%,#d35400 38%,#ffb27a 50%,#d35400 62%,#d35400 100%); background-size:200% 100%; -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; color:transparent; animation:kl-scan-shimmer 1.6s linear infinite; }
.kw-pane { animation: kw-pane-in .16s cubic-bezier(.2,.8,.2,1); }
.kw-pane-control { width:26px; height:24px; padding:0; display:inline-flex; align-items:center; justify-content:center; border:0; border-radius:5px; color:#898989; background:transparent; cursor:pointer; transition:color .15s,background .15s,transform .15s; }
.kw-pane-control:hover { color:#f06428; background:rgba(240,100,40,.09); }
.kw-pane-control:active { transform:scale(.92); }
.kw-pane-control[aria-pressed="true"] { color:#f06428; background:rgba(240,100,40,.11); }
.kw-resizer { position:absolute; z-index:40; touch-action:none; background:transparent; transition:background .15s,box-shadow .15s; }
.kw-resizer:hover,.kw-resizer[data-active="true"] { background:rgba(240,100,40,.22); box-shadow:0 0 0 1px rgba(240,100,40,.08); }
.kw-drop-zone { border:1px dashed rgba(240,100,40,.48); background:rgba(255,255,255,.72); color:#9a674f; font:600 11px/1 system-ui,sans-serif; letter-spacing:.02em; backdrop-filter:blur(5px); transition:background .14s,border-color .14s,transform .14s; }
.kw-drop-zone:hover,.kw-drop-zone[data-active="true"] { border-color:#f06428; background:rgba(240,100,40,.12); color:#d35400; transform:scale(.985); }
.kw-dock-chip { height:26px; display:inline-flex; align-items:center; gap:7px; padding:0 10px; border:1px solid #ddd; border-radius:7px; background:#fff; color:#555; cursor:pointer; font:600 11px/1 system-ui,sans-serif; box-shadow:0 1px 2px rgba(0,0,0,.04); transition:border-color .15s,color .15s,transform .15s; }
.kw-dock-chip:hover { color:#f06428; border-color:rgba(240,100,40,.55); transform:translateY(-1px); }
.kw-menu-button { width:100%; min-height:38px; padding:7px 9px; display:flex; align-items:center; gap:10px; text-align:left; border:1px solid transparent; border-radius:7px; background:transparent; color:#444; cursor:pointer; }
.kw-menu-button:hover { border-color:#e8e8e8; background:#fafafa; }
.kw-pane[data-workspace-pane="terminal"] .kite-terminal-window-header { display:none !important; }
body.kw-resizing { cursor:inherit; user-select:none; }
@media (prefers-reduced-motion: reduce) { .kl-scan-dot,.kl-scan-text,.kw-pane { animation:none; } .kl-scan-text { -webkit-text-fill-color:#d35400; color:#d35400; } }
`;

function fmtAgo(ms: number): string {
  if (!ms) return 'never';
  const seconds = Math.max(0, Math.round((Date.now() - ms) / 1000));
  if (seconds < 60) return `${seconds} Sec ago`;
  return `${Math.floor(seconds / 60)} Min ago`;
}

function fmtNext(ms: number): string {
  if (!ms) return '—';
  const seconds = Math.max(0, Math.round((ms - Date.now()) / 1000));
  if (seconds <= 0) return 'now';
  return seconds >= 60 ? `${Math.floor(seconds / 60)}m` : `${seconds}s`;
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function sameSizes(a: { left: number; right: number; bottom: number }, b: { left: number; right: number; bottom: number }) {
  return a.left === b.left && a.right === b.right && a.bottom === b.bottom;
}

function PaneGlyph({ pane, size = 14 }: { pane: WorkspacePaneId; size?: number }) {
  if (pane === 'watchlist') {
    return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M5 6h14M5 12h14M5 18h9"/><circle cx="3" cy="6" r=".8" fill="currentColor" stroke="none"/><circle cx="3" cy="12" r=".8" fill="currentColor" stroke="none"/><circle cx="3" cy="18" r=".8" fill="currentColor" stroke="none"/></svg>;
  }
  if (pane === 'dashboard') {
    return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="8" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="15" width="7" height="6" rx="1.5"/></svg>;
  }
  if (pane === 'signals') {
    return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 17l5-5 4 3 7-9"/><path d="M16 6h4v4"/></svg>;
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M12 15h5"/></svg>;
}

function DragDots() {
  return (
    <span aria-hidden="true" style={{ width: 10, display: 'grid', gridTemplateColumns: 'repeat(2,3px)', gap: 2, color: '#c2c2c2', flexShrink: 0 }}>
      {Array.from({ length: 6 }).map((_, index) => <span key={index} style={{ width: 2.5, height: 2.5, borderRadius: '50%', background: 'currentColor' }} />)}
    </span>
  );
}

function ControlIcon({ kind }: { kind: 'minimize' | 'half' | 'maximize' | 'fullscreen' | 'restore' }) {
  if (kind === 'minimize') return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 18h14"/></svg>;
  if (kind === 'half') return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/><path d="M3 4h9v16H3z" fill="currentColor" opacity=".14" stroke="none"/></svg>;
  if (kind === 'maximize') return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>;
  if (kind === 'restore') return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="5" y="8" width="12" height="11" rx="1.5"/><path d="M8 8V5h11v11h-2"/></svg>;
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5"/></svg>;
}

interface PaneWindowProps {
  pane: PaneDefinition;
  slot: WorkspaceSlotId;
  locked: boolean;
  focus: WorkspaceFocus | null;
  compact?: boolean;
  onMinimize: (pane: WorkspacePaneId) => void;
  onFocus: (pane: WorkspacePaneId, mode: WorkspaceFocusMode) => void;
  onRestoreFocus: () => void;
  onDragStart: (pane: WorkspacePaneId, event: React.DragEvent<HTMLDivElement>) => void;
  onDragEnd: () => void;
}

function PaneWindow({ pane, slot, locked, focus, compact = false, onMinimize, onFocus, onRestoreFocus, onDragStart, onDragEnd }: PaneWindowProps) {
  const focusedHere = focus?.pane === pane.id;
  const canDrag = !locked && focus === null;
  const control = (kind: 'minimize' | 'half' | 'maximize' | 'fullscreen', label: string, mode?: WorkspaceFocusMode) => (
    <button
      type="button"
      draggable={false}
      className="kw-pane-control"
      aria-label={`${label} ${pane.title}`}
      aria-pressed={mode ? focusedHere && focus?.mode === mode : undefined}
      title={`${label} ${pane.title}`}
      onMouseDown={(event) => event.stopPropagation()}
      onClick={(event) => {
        event.stopPropagation();
        if (kind === 'minimize') onMinimize(pane.id);
        else onFocus(pane.id, mode!);
      }}
    >
      <ControlIcon kind={kind} />
    </button>
  );

  return (
    <section
      className="kw-pane"
      data-workspace-pane={pane.id}
      aria-label={`${pane.title} pane`}
      style={{ height: '100%', minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#fff', border: '1px solid #e4e4e4', boxShadow: focusedHere ? '0 10px 36px rgba(0,0,0,.09)' : '0 1px 2px rgba(0,0,0,.025)' }}
    >
      <div
        draggable={canDrag}
        onDragStart={(event) => onDragStart(pane.id, event)}
        onDragEnd={onDragEnd}
        onDoubleClick={() => focusedHere ? onRestoreFocus() : onFocus(pane.id, 'maximized')}
        title={locked ? 'Layout locked' : focusedHere ? 'Double-click to restore workspace' : focus ? 'Double-click to focus this pane' : 'Drag to reposition · double-click to maximize'}
        style={{ height: compact ? 28 : 31, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 7, padding: '0 5px 0 9px', borderBottom: '1px solid #e8e8e8', background: '#fbfbfc', cursor: canDrag ? 'grab' : 'default', userSelect: 'none' }}
      >
        {canDrag && <DragDots />}
        <span style={{ color: pane.accent, display: 'inline-flex' }}><PaneGlyph pane={pane.id} size={13} /></span>
        <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11, fontWeight: 650, color: '#444', letterSpacing: '.01em' }}>{pane.title}</span>
        {!compact && <span style={{ fontSize: 9, color: '#aaa', whiteSpace: 'nowrap' }}>{SLOT_LABEL[slot]}</span>}
        <div draggable={false} style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 1 }}>
          {focusedHere && (
            <button type="button" className="kw-pane-control" aria-label={`Restore ${pane.title}`} title="Restore workspace" onClick={(event) => { event.stopPropagation(); onRestoreFocus(); }}>
              <ControlIcon kind="restore" />
            </button>
          )}
          {control('minimize', 'Minimize')}
          {!compact && control('half', 'Half screen', 'half')}
          {control('maximize', 'Maximize', 'maximized')}
          {!compact && control('fullscreen', 'Full screen', 'fullscreen')}
        </div>
      </div>
      <div style={{ flex: 1, minWidth: 0, minHeight: 0, overflow: 'auto', position: 'relative' }}>
        {pane.content}
      </div>
    </section>
  );
}

function PresetDiagram({ preset }: { preset: WorkspacePresetId }) {
  const right = preset === 'execution' ? '38%' : preset === 'chart' ? '23%' : '29%';
  const left = preset === 'chart' ? '18%' : '23%';
  const bottom = preset === 'execution' ? '35%' : preset === 'chart' ? '20%' : '27%';
  return (
    <span style={{ width: 42, height: 27, display: 'grid', gridTemplateColumns: `${left} 1fr ${right}`, gridTemplateRows: `1fr ${bottom}`, gap: 1, padding: 2, border: '1px solid #ddd', borderRadius: 4, background: '#fff', flexShrink: 0 }}>
      <i style={{ gridColumn: 1, gridRow: '1 / 3', background: '#d7d7d7', borderRadius: 1 }} />
      <i style={{ gridColumn: 2, gridRow: 1, background: '#f06428', opacity: .72, borderRadius: 1 }} />
      <i style={{ gridColumn: 3, gridRow: '1 / 3', background: '#bdbdbd', borderRadius: 1 }} />
      <i style={{ gridColumn: 2, gridRow: 2, background: '#8f8f8f', borderRadius: 1 }} />
    </span>
  );
}

export function KiteLayout({ activeNav, onNavClick: _onNavClick, sidebar, rightSidebar, bottomBar, centerTopBar, content, onBasketClick, basketCount = 0 }: KiteLayoutProps) {
  const { on: macOn } = useMacKite();
  const { data: activity } = useEngineActivity();
  const liveCount = useLiveSignalCount((state) => state.count);
  const [layout, setLayout] = useState(() => loadWorkspaceLayout(localStorage));
  const [focus, setFocus] = useState<WorkspaceFocus | null>(null);
  const [draggingPane, setDraggingPane] = useState<WorkspacePaneId | null>(null);
  const [dropSlot, setDropSlot] = useState<WorkspaceSlotId | null>(null);
  const [resizing, setResizing] = useState<ResizeAxis | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const resizeRef = useRef<ResizeSession | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const panes = useMemo<Record<WorkspacePaneId, PaneDefinition>>(() => ({
    watchlist: { id: 'watchlist', title: 'Watchlist', shortTitle: 'Watchlist', accent: '#4f79ce', content: sidebar },
    dashboard: {
      id: 'dashboard', title: titleCase(activeNav), shortTitle: 'Dashboard', accent: '#f06428',
      content: (
        <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {centerTopBar && <div style={{ flexShrink: 0 }}>{centerTopBar}</div>}
          <div style={{ flex: 1, minHeight: 0, overflow: 'auto', scrollbarGutter: 'stable', display: 'flex', flexDirection: 'column' }}>{content}</div>
        </div>
      ),
    },
    signals: { id: 'signals', title: 'Signals', shortTitle: 'Signals', accent: '#16a066', content: rightSidebar },
    terminal: { id: 'terminal', title: 'Terminal', shortTitle: 'Terminal', accent: '#7d63c5', content: bottomBar },
  }), [activeNav, sidebar, rightSidebar, bottomBar, centerTopBar, content]);

  const available = useMemo(() => WORKSPACE_PANES.filter((id) => panes[id].content != null), [panes]);
  const isVisible = useCallback((id: WorkspacePaneId) => available.includes(id) && !layout.minimized.includes(id), [available, layout.minimized]);
  const slotIsVisible = useCallback((slot: WorkspaceSlotId) => isVisible(layout.slots[slot]), [isVisible, layout.slots]);

  useEffect(() => {
    try { localStorage.setItem(WORKSPACE_LAYOUT_KEY, JSON.stringify(layout)); } catch { void 0; }
  }, [layout]);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setFocus((current) => {
        if (current?.pane === 'terminal') {
          try { localStorage.setItem('kite_terminal_mode', 'normal'); } catch { void 0; }
        }
        return null;
      });
      setDraggingPane(null);
      setMenuOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    const reclamp = () => {
      if (macOn) return;
      const rect = workspaceRef.current?.getBoundingClientRect();
      if (!rect) return;
      setLayout((current) => {
        const next = clampWorkspaceSizes(current.sizes, rect, {
          left: available.includes(current.slots.left) && !current.minimized.includes(current.slots.left),
          right: available.includes(current.slots.right) && !current.minimized.includes(current.slots.right),
          bottom: available.includes(current.slots.bottom) && !current.minimized.includes(current.slots.bottom),
        });
        return sameSizes(current.sizes, next) ? current : { ...current, sizes: next };
      });
    };
    reclamp();
    window.addEventListener('resize', reclamp);
    return () => window.removeEventListener('resize', reclamp);
  }, [available, macOn]);

  useEffect(() => {
    if (!macOn) return;
    setFocus(null);
    setDraggingPane(null);
    setDropSlot(null);
    setMenuOpen(false);
  }, [macOn]);

  useEffect(() => {
    const frame = requestAnimationFrame(() => window.dispatchEvent(new CustomEvent('kite-pane-toggle')));
    return () => cancelAnimationFrame(frame);
  }, [layout.sizes, layout.minimized, layout.slots, focus]);

  useEffect(() => {
    const onTerminalMode = (event: Event) => {
      const mode = (event as CustomEvent<string>).detail;
      if (mode === 'minimized') {
        setLayout((current) => minimizePane(current, 'terminal'));
        setFocus((current) => current?.pane === 'terminal' ? null : current);
      } else if (mode === 'normal') {
        setLayout((current) => restorePane(current, 'terminal'));
        setFocus((current) => current?.pane === 'terminal' ? null : current);
      } else if (mode === 'partial' || mode === 'full') {
        setLayout((current) => restorePane(current, 'terminal'));
        setFocus({ pane: 'terminal', mode: mode === 'full' ? 'fullscreen' : 'maximized' });
      }
    };
    window.addEventListener('kite-terminal-mode', onTerminalMode);
    return () => window.removeEventListener('kite-terminal-mode', onTerminalMode);
  }, []);

  const syncTerminalStorage = useCallback((pane: WorkspacePaneId, mode: 'minimized' | 'normal' | 'partial' | 'full') => {
    if (pane !== 'terminal') return;
    try { localStorage.setItem('kite_terminal_mode', mode); } catch { void 0; }
  }, []);

  const minimize = useCallback((pane: WorkspacePaneId) => {
    setLayout((current) => minimizePane(current, pane));
    setFocus((current) => current?.pane === pane ? null : current);
    syncTerminalStorage(pane, 'minimized');
  }, [syncTerminalStorage]);

  const restore = useCallback((pane: WorkspacePaneId) => {
    setLayout((current) => restorePane(current, pane));
    syncTerminalStorage(pane, 'normal');
  }, [syncTerminalStorage]);

  const restoreFocus = useCallback(() => {
    setFocus((current) => {
      if (current) syncTerminalStorage(current.pane, 'normal');
      return null;
    });
  }, [syncTerminalStorage]);

  const toggleFocus = useCallback((pane: WorkspacePaneId, mode: WorkspaceFocusMode) => {
    setLayout((current) => restorePane(current, pane));
    setFocus((current) => {
      if (current?.pane === pane && current.mode === mode) {
        syncTerminalStorage(pane, 'normal');
        return null;
      }
      const side = mode === 'half' ? (paneSlot(layout, pane) === 'right' ? 'right' : 'left') : undefined;
      syncTerminalStorage(pane, mode === 'fullscreen' ? 'full' : mode === 'maximized' ? 'partial' : 'normal');
      return { pane, mode, side };
    });
  }, [layout, syncTerminalStorage]);

  const onDragStart = useCallback((pane: WorkspacePaneId, event: React.DragEvent<HTMLDivElement>) => {
    if (layout.locked || focus) { event.preventDefault(); return; }
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', pane);
    setDraggingPane(pane);
  }, [layout.locked, focus]);

  const onDrop = useCallback((slot: WorkspaceSlotId, event: React.DragEvent) => {
    event.preventDefault();
    const raw = draggingPane ?? event.dataTransfer.getData('text/plain');
    if (WORKSPACE_PANES.includes(raw as WorkspacePaneId)) {
      setLayout((current) => movePaneToSlot(current, raw as WorkspacePaneId, slot));
    }
    setDraggingPane(null);
    setDropSlot(null);
  }, [draggingPane]);

  const endDrag = useCallback(() => {
    setDraggingPane(null);
    setDropSlot(null);
  }, []);

  const startResize = useCallback((axis: ResizeAxis, event: React.PointerEvent<HTMLDivElement>) => {
    if (layout.locked) return;
    resizeRef.current = {
      axis, pointerId: event.pointerId, startX: event.clientX, startY: event.clientY,
      startLeft: layout.sizes.left, startRight: layout.sizes.right, startBottom: layout.sizes.bottom,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    document.body.classList.add('kw-resizing');
    document.body.style.cursor = axis === 'bottom' ? 'row-resize' : 'col-resize';
    setResizing(axis);
  }, [layout.locked, layout.sizes]);

  const moveResize = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const session = resizeRef.current;
    const rect = workspaceRef.current?.getBoundingClientRect();
    if (!session || session.pointerId !== event.pointerId || !rect) return;
    const sizes = {
      left: session.axis === 'left' ? session.startLeft + event.clientX - session.startX : session.startLeft,
      right: session.axis === 'right' ? session.startRight - event.clientX + session.startX : session.startRight,
      bottom: session.axis === 'bottom' ? session.startBottom - event.clientY + session.startY : session.startBottom,
    };
    const next = clampWorkspaceSizes(sizes, rect, {
      left: slotIsVisible('left'), right: slotIsVisible('right'), bottom: slotIsVisible('bottom'),
    });
    setLayout((current) => ({ ...current, sizes: next }));
  }, [slotIsVisible]);

  const endResize = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const session = resizeRef.current;
    if (!session || session.pointerId !== event.pointerId) return;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
    resizeRef.current = null;
    document.body.classList.remove('kw-resizing');
    document.body.style.cursor = '';
    setResizing(null);
  }, []);

  const resizeWithKeyboard = useCallback((axis: ResizeAxis, event: React.KeyboardEvent<HTMLDivElement>) => {
    const horizontal = axis !== 'bottom';
    if ((horizontal && event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') || (!horizontal && event.key !== 'ArrowUp' && event.key !== 'ArrowDown')) return;
    event.preventDefault();
    const rect = workspaceRef.current?.getBoundingClientRect();
    if (!rect) return;
    const step = event.shiftKey ? 48 : 16;
    setLayout((current) => {
      const direction = axis === 'left'
        ? (event.key === 'ArrowRight' ? 1 : -1)
        : axis === 'right'
          ? (event.key === 'ArrowLeft' ? 1 : -1)
          : (event.key === 'ArrowUp' ? 1 : -1);
      const sizes = { ...current.sizes, [axis]: current.sizes[axis] + direction * step };
      return { ...current, sizes: clampWorkspaceSizes(sizes, rect, { left: slotIsVisible('left'), right: slotIsVisible('right'), bottom: slotIsVisible('bottom') }) };
    });
  }, [slotIsVisible]);

  useEffect(() => () => {
    document.body.classList.remove('kw-resizing');
    document.body.style.cursor = '';
  }, []);

  const applyPreset = useCallback((preset: WorkspacePresetId) => {
    setLayout((current) => applyWorkspacePreset(current, preset));
    setFocus(null);
    setMenuOpen(false);
  }, []);

  const resetArrangement = useCallback(() => {
    setLayout((current) => ({ ...current, slots: { ...cloneDefaultWorkspaceLayout().slots } }));
    setFocus(null);
    setMenuOpen(false);
  }, []);

  const renderPane = (paneId: WorkspacePaneId, compact = false) => (
    <PaneWindow
      key={paneId}
      pane={panes[paneId]}
      slot={paneSlot(layout, paneId)}
      locked={layout.locked}
      focus={focus}
      compact={compact}
      onMinimize={minimize}
      onFocus={toggleFocus}
      onRestoreFocus={restoreFocus}
      onDragStart={onDragStart}
      onDragEnd={endDrag}
    />
  );

  const leftVisible = slotIsVisible('left');
  const centerVisible = slotIsVisible('center');
  const rightVisible = slotIsVisible('right');
  const bottomVisible = slotIsVisible('bottom');
  const centerColumnOccupied = centerVisible || bottomVisible;
  const onlyEdgePanes = !centerColumnOccupied;

  const slotStyle = (slot: WorkspaceSlotId): React.CSSProperties => {
    if (slot === 'center') return { gridColumn: '2 / 3', gridRow: '1 / 2' };
    if (slot === 'bottom') return centerVisible ? { gridColumn: '2 / 3', gridRow: '2 / 3' } : { gridColumn: '2 / 3', gridRow: '1 / 3' };
    if (slot === 'left') {
      if (onlyEdgePanes && !rightVisible) return { gridColumn: '1 / 4', gridRow: '1 / 3' };
      if (onlyEdgePanes) return { gridColumn: '1 / 3', gridRow: '1 / 3' };
      return { gridColumn: '1 / 2', gridRow: '1 / 3' };
    }
    if (onlyEdgePanes && !leftVisible) return { gridColumn: '1 / 4', gridRow: '1 / 3' };
    return { gridColumn: '3 / 4', gridRow: '1 / 3' };
  };

  const standardWorkspace = (
    <div
      style={{
        position: 'absolute', inset: 0, display: 'grid', minWidth: 0, minHeight: 0,
        gridTemplateColumns: `${leftVisible ? layout.sizes.left : 0}px minmax(0,1fr) ${rightVisible ? layout.sizes.right : 0}px`,
        gridTemplateRows: `minmax(0,1fr) ${bottomVisible && centerVisible ? layout.sizes.bottom : 0}px`,
        gap: 0, background: '#ececec',
      }}
    >
      {WORKSPACE_SLOTS.map((slot) => {
        const paneId = layout.slots[slot];
        if (!isVisible(paneId)) return null;
        return <div key={slot} data-workspace-slot={slot} style={{ ...slotStyle(slot), minWidth: 0, minHeight: 0, padding: 1, overflow: 'hidden' }}>{renderPane(paneId)}</div>;
      })}
    </div>
  );

  const focusedWorkspace = focus && isVisible(focus.pane) ? (() => {
    if (focus.mode === 'maximized') {
      return (
        <div style={{ position: 'absolute', inset: 0, zIndex: 60, padding: 1, background: '#ececec' }}>
          {renderPane(focus.pane)}
        </div>
      );
    }
    if (focus.mode === 'fullscreen') return null;
    const companions = available.filter((id) => id !== focus.pane && isVisible(id));
    return (
      <div style={{ position: 'absolute', inset: 0, zIndex: 60, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 3, padding: 3, background: '#e8e8e8' }}>
        <div style={{ minWidth: 0, minHeight: 0, order: focus.side === 'right' ? 2 : 1 }}>{renderPane(focus.pane)}</div>
        <div style={{ minWidth: 0, minHeight: 0, order: focus.side === 'right' ? 1 : 2, display: 'grid', gridTemplateColumns: companions.length > 1 ? 'repeat(2,minmax(0,1fr))' : '1fr', gridAutoRows: 'minmax(0,1fr)', gap: 3 }}>
          {companions.map((id, index) => <div key={id} style={{ minWidth: 0, minHeight: 0, gridColumn: companions.length === 3 && index === 0 ? '1 / -1' : undefined }}>{renderPane(id, true)}</div>)}
        </div>
      </div>
    );
  })() : null;

  const fullscreenWorkspace = focus?.mode === 'fullscreen' && isVisible(focus.pane)
    ? createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 12000, padding: 8, background: '#efefef', fontFamily: k.fontFamily }}>
          <style>{WORKSPACE_CSS}</style>
          {renderPane(focus.pane)}
        </div>,
        document.body,
      )
    : null;

  const minimizedAvailable = layout.minimized.filter((id) => available.includes(id));
  const scanning = !!activity?.scanning;
  const autoScan = !!activity?.auto_scan;
  const marketClosed = autoScan && activity?.market_open === false;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0, minHeight: 0, overflow: 'hidden', background: '#fff', fontFamily: k.fontFamily }}>
      <style>{WORKSPACE_CSS}</style>
      <div ref={workspaceRef} className="mac-canvas" data-testid="kite-workspace" style={{ position: 'relative', display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, minHeight: 0, overflow: 'hidden' }}>
        {macOn ? (
          <>
            {centerTopBar && <div style={{ flexShrink: 0 }}>{centerTopBar}</div>}
            <MacStageLayout sidebar={sidebar} content={content} rightSidebar={rightSidebar} bottomBar={bottomBar} />
          </>
        ) : (
          <>
            {!focus && standardWorkspace}
            {focusedWorkspace}
          </>
        )}

        {!macOn && !layout.locked && !focus && leftVisible && centerColumnOccupied && (
          <div className="kw-resizer" data-active={resizing === 'left'} aria-label="Resize left dock" role="separator" tabIndex={0} aria-orientation="vertical" aria-valuenow={layout.sizes.left} onKeyDown={(event) => resizeWithKeyboard('left', event)} onPointerDown={(event) => startResize('left', event)} onPointerMove={moveResize} onPointerUp={endResize} onPointerCancel={endResize} style={{ top: 0, bottom: 0, left: layout.sizes.left - 4, width: 8, cursor: 'col-resize' }} />
        )}
        {!macOn && !layout.locked && !focus && rightVisible && (centerColumnOccupied || leftVisible) && (
          <div className="kw-resizer" data-active={resizing === 'right'} aria-label="Resize right dock" role="separator" tabIndex={0} aria-orientation="vertical" aria-valuenow={layout.sizes.right} onKeyDown={(event) => resizeWithKeyboard('right', event)} onPointerDown={(event) => startResize('right', event)} onPointerMove={moveResize} onPointerUp={endResize} onPointerCancel={endResize} style={{ top: 0, bottom: 0, right: layout.sizes.right - 4, width: 8, cursor: 'col-resize' }} />
        )}
        {!macOn && !layout.locked && !focus && centerVisible && bottomVisible && (
          <div className="kw-resizer" data-active={resizing === 'bottom'} aria-label="Resize bottom dock" role="separator" tabIndex={0} aria-orientation="horizontal" aria-valuenow={layout.sizes.bottom} onKeyDown={(event) => resizeWithKeyboard('bottom', event)} onPointerDown={(event) => startResize('bottom', event)} onPointerMove={moveResize} onPointerUp={endResize} onPointerCancel={endResize} style={{ left: leftVisible ? layout.sizes.left : 0, right: rightVisible ? layout.sizes.right : 0, bottom: layout.sizes.bottom - 4, height: 8, cursor: 'row-resize' }} />
        )}

        {!macOn && draggingPane && (
          <div aria-label="Pane drop targets" style={{ position: 'absolute', inset: 8, zIndex: 200, display: 'grid', gridTemplateColumns: '24% 1fr 24%', gridTemplateRows: '1fr 24%', gap: 8, pointerEvents: 'none' }}>
            {WORKSPACE_SLOTS.map((slot) => {
              const area: React.CSSProperties = slot === 'left' ? { gridColumn: 1, gridRow: '1 / 3' } : slot === 'right' ? { gridColumn: 3, gridRow: '1 / 3' } : slot === 'center' ? { gridColumn: 2, gridRow: 1 } : { gridColumn: 2, gridRow: 2 };
              return (
                <button key={slot} type="button" className="kw-drop-zone" data-active={dropSlot === slot} style={{ ...area, pointerEvents: 'auto', borderRadius: 9 }} onDragEnter={(event) => { event.preventDefault(); setDropSlot(slot); }} onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; }} onDrop={(event) => onDrop(slot, event)}>
                  {SLOT_LABEL[slot]}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <footer style={{ position: 'relative', height: 36, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 12px', gap: 9, borderTop: '1px solid #dedede', background: 'rgba(255,255,255,.98)', zIndex: 150 }}>
        <div ref={menuRef} style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 7 }}>
          <MacKiteToggle />
          {!macOn && <span aria-hidden="true" style={{ width: 1, height: 18, background: '#e2e2e2' }} />}
          {!macOn && (
            <button type="button" className="kw-dock-chip" aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)} title="Open workspace layouts">
              <PaneGlyph pane="dashboard" size={13} />
              Layout
              <svg width="9" height="9" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 6l4 4 4-4"/></svg>
            </button>
          )}
          {onBasketClick && (
            <button type="button" className="kw-pane-control" onClick={onBasketClick} title="Basket" aria-label="Open basket" style={{ position: 'relative' }}>
              <Icons.Basket />
              {basketCount > 0 && <span style={{ position: 'absolute', top: -3, right: -4, minWidth: 14, height: 14, padding: '0 2px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 8, background: '#f06428', color: '#fff', fontSize: 8, fontWeight: 750 }}>{basketCount}</span>}
            </button>
          )}

          {!macOn && menuOpen && (
            <div role="dialog" aria-label="Workspace layout menu" style={{ position: 'absolute', left: 0, bottom: 33, width: 294, padding: 9, border: '1px solid #ddd', borderRadius: 10, background: '#fff', boxShadow: '0 14px 44px rgba(0,0,0,.16)', zIndex: 300 }}>
              <div style={{ padding: '3px 5px 7px', fontSize: 10, fontWeight: 750, color: '#999', letterSpacing: '.08em', textTransform: 'uppercase' }}>Workspace presets</div>
              {PRESET_META.map((preset) => (
                <button key={preset.id} type="button" className="kw-menu-button" onClick={() => applyPreset(preset.id)}>
                  <PresetDiagram preset={preset.id} />
                  <span><strong style={{ display: 'block', fontSize: 11.5 }}>{preset.label}</strong><small style={{ color: '#999', fontSize: 10 }}>{preset.detail}</small></span>
                </button>
              ))}
              <div style={{ height: 1, background: '#ececec', margin: '7px 3px' }} />
              <button type="button" className="kw-menu-button" onClick={resetArrangement}><ControlIcon kind="restore" /><span style={{ fontSize: 11.5 }}>Reset pane positions</span></button>
              <button type="button" className="kw-menu-button" onClick={() => setLayout((current) => restoreAllPanes(current))}><PaneGlyph pane="dashboard" /><span style={{ fontSize: 11.5 }}>Restore all panes</span></button>
              <button type="button" className="kw-menu-button" aria-pressed={layout.locked} onClick={() => setLayout((current) => ({ ...current, locked: !current.locked }))}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="4" y="10" width="16" height="11" rx="2"/><path d={layout.locked ? 'M8 10V7a4 4 0 018 0v3' : 'M8 10V7a4 4 0 017.5-2'} /></svg>
                <span style={{ fontSize: 11.5 }}>{layout.locked ? 'Unlock pane movement' : 'Lock pane movement'}</span>
                <span style={{ marginLeft: 'auto', width: 28, height: 16, padding: 2, borderRadius: 10, background: layout.locked ? '#f06428' : '#ddd', display: 'flex', justifyContent: layout.locked ? 'flex-end' : 'flex-start' }}><i style={{ width: 12, height: 12, borderRadius: '50%', background: '#fff' }} /></span>
              </button>
              <div style={{ padding: '8px 6px 3px', fontSize: 9.5, lineHeight: 1.45, color: '#aaa' }}>Drag any pane title to dock it elsewhere. Double-click a title to maximize. Press Esc to leave focus mode.</div>
            </div>
          )}
        </div>

        <div aria-label={macOn ? 'Mac workspace status' : 'Minimized panes'} style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)', display: 'flex', alignItems: 'center', gap: 6, maxWidth: '48%', overflow: 'hidden' }}>
          {macOn ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#aaa', fontSize: 10.5, whiteSpace: 'nowrap' }}><span style={{ width: 5, height: 5, borderRadius: '50%', background: '#f4a67f' }} />Mac stage active</span>
          ) : minimizedAvailable.length > 0 ? minimizedAvailable.map((id) => (
            <button key={id} type="button" className="kw-dock-chip" onClick={() => restore(id)} title={`Restore ${panes[id].title}`}>
              <span style={{ color: panes[id].accent, display: 'inline-flex' }}><PaneGlyph pane={id} size={13} /></span>
              {panes[id].shortTitle}
            </button>
          )) : (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#aaa', fontSize: 10.5, whiteSpace: 'nowrap' }}><span style={{ width: 5, height: 5, borderRadius: '50%', background: '#9bc7b2' }} />All panes active</span>
          )}
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#777', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
          {liveCount > 0 && <><span title={`${liveCount} signal${liveCount === 1 ? '' : 's'} currently running`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontWeight: 650, color: k.green }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: k.green }} />{liveCount} live</span><span style={{ width: 1, height: 14, background: '#e0e0e0' }} /></>}
          <span className={scanning ? 'kl-scan-dot' : undefined} style={{ width: 6, height: 6, borderRadius: '50%', background: scanning ? k.orange : marketClosed ? '#bbb' : autoScan ? k.orange : '#bbb' }} />
          <span className={scanning ? 'kl-scan-text' : undefined} style={{ color: scanning ? undefined : '#777', fontWeight: scanning ? 650 : 400, textTransform: 'capitalize' }}>{scanning ? activity?.scanning_label || 'scanning…' : autoScan ? 'AUTO' : 'MANUAL'}</span>
          {!scanning && (activity?.last_scan_ms ?? 0) > 0 && <span style={{ opacity: .7 }}>· {fmtAgo(activity?.last_scan_ms ?? 0)}</span>}
          {!scanning && marketClosed ? <span style={{ opacity: .7 }}>· Market closed</span> : !scanning && autoScan && (activity?.next_scan_ms ?? 0) > 0 ? <span style={{ opacity: .7 }}>· Next Due {fmtNext(activity?.next_scan_ms ?? 0)}</span> : null}
        </div>
      </footer>
      {!macOn && fullscreenWorkspace}
    </div>
  );
}
