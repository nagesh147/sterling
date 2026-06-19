import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useKiteStatus } from '../../hooks/useKite';
import { MacKiteToggle } from './mac/MacKiteToggle';
import { useMacKite } from '../../hooks/useMacKite';
import { MacStageLayout } from './mac/MacStageLayout';

export type NavItem = 'dashboard' | 'orders' | 'holdings' | 'positions' | 'bids' | 'funds' | 'data' | 'connect' | 'mf' | 'alerts';

interface KiteLayoutProps {
  activeNav: NavItem;
  onNavClick: (nav: NavItem) => void;
  sidebar?: React.ReactNode;
  rightSidebar?: React.ReactNode;
  bottomBar?: React.ReactNode;
  content: React.ReactNode;
}

export function KiteLayout({ activeNav, onNavClick, sidebar, rightSidebar, bottomBar, content }: KiteLayoutProps) {
  const { data: status } = useKiteStatus();
  const { on: macOn } = useMacKite();

  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('kite_sidebar_width');
    return saved ? parseInt(saved, 10) : 420;
  });
  
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    const saved = localStorage.getItem('kite_sidebar_open');
    return saved ? saved === 'true' : true;
  });
  
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(() => {
    const saved = localStorage.getItem('kite_right_sidebar_open');
    return saved ? saved === 'true' : true;
  });

  const [isBottomBarOpen, setIsBottomBarOpen] = useState(() => {
    const saved = localStorage.getItem('kite_bottombar_open');
    return saved ? saved === 'true' : true;
  });

  const [bottomBarHeight, setBottomBarHeight] = useState(() => {
    const saved = localStorage.getItem('kite_bottombar_height');
    return saved ? parseInt(saved, 10) : 200;
  });

  const [rightSidebarWidth, setRightSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('kite_right_sidebar_width');
    return saved ? parseInt(saved, 10) : 640;
  });

  const [isLocked, setIsLocked] = useState(() => {
    return localStorage.getItem('kite_layout_locked') === 'true';
  });

  const [terminalMode, setTerminalMode] = useState<'minimized' | 'normal' | 'partial' | 'full'>('normal');

  useEffect(() => {
    const cb = (e: any) => setTerminalMode(e.detail);
    window.addEventListener('kite-terminal-mode', cb);
    return () => window.removeEventListener('kite-terminal-mode', cb);
  }, []);

  // Defaults — used by the reset button.
  const DEFAULTS = { left: 420, right: 640, bottom: 200 };

  const isDragging = useRef(false);
  const isDraggingBottom = useRef(false);
  const isDraggingRight = useRef(false);

  useEffect(() => {
    localStorage.setItem('kite_sidebar_width', sidebarWidth.toString());
  }, [sidebarWidth]);

  useEffect(() => {
    localStorage.setItem('kite_sidebar_open', isSidebarOpen.toString());
  }, [isSidebarOpen]);

  useEffect(() => {
    localStorage.setItem('kite_right_sidebar_open', isRightSidebarOpen.toString());
  }, [isRightSidebarOpen]);

  useEffect(() => {
    localStorage.setItem('kite_bottombar_open', isBottomBarOpen.toString());
  }, [isBottomBarOpen]);

  useEffect(() => {
    localStorage.setItem('kite_bottombar_height', bottomBarHeight.toString());
  }, [bottomBarHeight]);

  useEffect(() => {
    localStorage.setItem('kite_right_sidebar_width', rightSidebarWidth.toString());
  }, [rightSidebarWidth]);

  useEffect(() => {
    localStorage.setItem('kite_layout_locked', isLocked.toString());
  }, [isLocked]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (isLocked) return;
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
  }, [isLocked]);

  const handleBottomMouseDown = useCallback((e: React.MouseEvent) => {
    if (isLocked) return;
    isDraggingBottom.current = true;
    document.body.style.cursor = 'row-resize';
  }, [isLocked]);

  const handleRightMouseDown = useCallback((e: React.MouseEvent) => {
    if (isLocked) return;
    isDraggingRight.current = true;
    document.body.style.cursor = 'col-resize';
  }, [isLocked]);

  const handleMouseUp = useCallback(() => {
    isDragging.current = false;
    isDraggingBottom.current = false;
    isDraggingRight.current = false;
    document.body.style.cursor = '';
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (isDragging.current) {
      const newWidth = Math.max(250, Math.min(e.clientX, 800));
      setSidebarWidth(newWidth);
    }
    if (isDraggingBottom.current) {
      const newHeight = Math.max(80, Math.min(window.innerHeight - e.clientY, 600));
      setBottomBarHeight(newHeight);
    }
    if (isDraggingRight.current) {
      const newWidth = Math.max(320, Math.min(window.innerWidth - e.clientX, 1000));
      setRightSidebarWidth(newWidth);
    }
  }, []);

  const resetLayout = useCallback(() => {
    // In Mac mode the resizable layout isn't rendered — the footer reset instead
    // restores the Stage Manager arrangement to its default (MacStageLayout listens).
    if (macOn) { window.dispatchEvent(new CustomEvent('kite-stage-reset')); return; }
    if (isLocked) return;
    setSidebarWidth(DEFAULTS.left);
    setRightSidebarWidth(DEFAULTS.right);
    setBottomBarHeight(DEFAULTS.bottom);
  }, [isLocked, macOn]);

  const resetLayout2 = useCallback(() => {
    if (isLocked) return;
    
    // Using exact pixel values requested to prevent layout breakage
    setSidebarWidth(425);
    setRightSidebarWidth(900);
    setBottomBarHeight(425);
  }, [isLocked]);

  // Right pane has three quick layouts from the footer: hidden (the toggle), the
  // default width (640px), and a compact width (450px). This button flips between
  // compact and default — opening the pane straight into compact if it was hidden.
  const RIGHT_COMPACT = 450;
  const toggleRightCompact = useCallback(() => {
    if (isLocked) return;
    if (!isRightSidebarOpen) {
      setIsRightSidebarOpen(true);
      setRightSidebarWidth(RIGHT_COMPACT);
    } else {
      setRightSidebarWidth((w) => (w === RIGHT_COMPACT ? DEFAULTS.right : RIGHT_COMPACT));
    }
  }, [isRightSidebarOpen, isLocked]);

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleMouseMove, handleMouseUp]);

  const navItems: NavItem[] = ['dashboard', 'orders', 'holdings', 'positions', 'bids', 'funds', 'mf', 'alerts', 'data', 'connect'];

  const footBtn = (active: boolean, disabled = false): React.CSSProperties => ({
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    width: 24, height: 22, padding: 0, cursor: disabled ? 'default' : 'pointer', borderRadius: 4, border: 'none',
    background: active ? 'rgba(240, 100, 40, 0.1)' : 'transparent',
    color: active ? '#f06428' : '#9b9b9b', transition: 'background 0.2s, color 0.2s',
    opacity: disabled ? 0.35 : 1,
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif' }}>
      <style>{`
        .kite-nav-item { transition: color 0.2s; }
        .kite-nav-item:hover { color: #f06428 !important; }
        .kite-icon-btn { transition: color 0.2s; }
        .kite-icon-btn:hover { color: #f06428 !important; }
        .kite-reset-btn { transition: background 0.2s, color 0.2s; }
        .kite-reset-btn:hover { color: #444 !important; background: #f9f9f9 !important; }
      `}</style>
      
      {/* ── TOP NAVBAR ── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        height: 56,
        background: '#fff',
        borderBottom: '1px solid #e0e0e0',
        zIndex: 10
      }}>
        {/* Logo area */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ color: '#f06428', fontSize: 24, fontWeight: 900, transform: 'scaleX(-1)' }}>◩</div>
          </div>
          <div style={{ fontSize: 14, fontWeight: 500, color: '#444', letterSpacing: 0.5 }}>KITE</div>
        </div>

        {/* Navigation items */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 24, height: '100%' }}>
          {navItems.map((item) => (
              <div
                key={item}
                className="kite-nav-item"
                onClick={() => onNavClick(item)}
                style={{
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: activeNav === item ? 500 : 400,
                  color: activeNav === item ? '#f06428' : '#444',
                  textTransform: 'capitalize',
                  textDecoration: 'none'
                }}
              >
                {item === 'mf' ? 'Mutual Funds' : item}
              </div>
          ))}

          {/* Spacer */}
          <div style={{ width: 16 }} />

          {/* Right side icons/profile (panel controls live in the Kite footer below) */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div className="kite-icon-btn" style={{ color: '#444', cursor: 'pointer', fontSize: 16 }}>🔔</div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              cursor: 'pointer'
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: 14, background: 'rgba(240, 100, 40, 0.1)',
                color: '#f06428', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 500
              }}>
                {status?.user_name ? status.user_name.substring(0, 2).toUpperCase() : 'SK'}
              </div>
              <div style={{ fontSize: 12, color: '#444' }}>
                {status?.user_name ? status.user_name.split(' ')[0] : 'Guest'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── MAIN LAYOUT ── (mac-canvas: dims + scales 2% behind the order ticket) */}
      {macOn ? (
        <MacStageLayout sidebar={sidebar} content={content} rightSidebar={rightSidebar} bottomBar={bottomBar} />
      ) : (
      <div className="mac-canvas" style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left Sidebar (Watchlist) */}
        {sidebar && isSidebarOpen && (
          <>
            <div style={{
              width: sidebarWidth,
              flexShrink: 0,
              background: '#fff',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'auto'
            }}>
              {sidebar}
            </div>
            
            {/* Resizer Handle */}
            <div
              onMouseDown={handleMouseDown}
              style={{
                width: 5,
                marginLeft: -5,
                background: 'transparent',
                cursor: isLocked ? 'default' : 'col-resize',
                zIndex: 10,
                flexShrink: 0,
                transition: 'background 0.2s',
              }}
              onMouseEnter={(e) => { if (!isLocked) e.currentTarget.style.background = 'rgba(240, 100, 40, 0.2)'; }}
              onMouseLeave={(e) => {
                if (!isDragging.current) e.currentTarget.style.background = 'transparent';
              }}
            />
          </>
        )}

        {/* Center column: content + bottom bar (terminal stays BETWEEN the sidebars) */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          position: 'relative',
          borderLeft: (sidebar && isSidebarOpen) ? '1px solid #e0e0e0' : 'none'
        }}>
          <div style={{ flex: 1, background: '#fff', overflow: 'auto' }}>
            {content}
          </div>

          {/* ── Bottom Bar (Kite Terminal) — spans only the center column ── */}
          {bottomBar && isBottomBarOpen && (
            terminalMode === 'full' ? (
              <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999, background: '#fff', display: 'flex', flexDirection: 'column' }}>
                {bottomBar}
              </div>
            ) : terminalMode === 'partial' ? (
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, zIndex: 50, background: '#fff', display: 'flex', flexDirection: 'column' }}>
                {bottomBar}
              </div>
            ) : (
              <>
                <div
                  onMouseDown={handleBottomMouseDown}
                  style={{ height: 5, marginBottom: -5, background: 'transparent', cursor: isLocked ? 'default' : 'row-resize', flexShrink: 0, transition: 'background 0.2s', zIndex: 10 }}
                  onMouseEnter={(e) => { if (!isLocked) e.currentTarget.style.background = 'rgba(240, 100, 40, 0.2)'; }}
                  onMouseLeave={(e) => { if (!isDraggingBottom.current) e.currentTarget.style.background = 'transparent'; }}
                />
                <div id="kite-bottom-bar-wrapper" style={{ height: terminalMode === 'minimized' ? 33 : bottomBarHeight, flexShrink: 0, borderTop: '1px solid #e0e0e0', overflow: 'hidden', display: 'flex', flexDirection: 'column', transition: 'height 0.2s ease-out' }}>
                  {bottomBar}
                </div>
              </>
            )
          )}
        </div>

        {/* Right Sidebar (resizable) */}
        {rightSidebar && isRightSidebarOpen && (
          <>
            {/* Resizer handle — left edge of the right sidebar */}
            <div
              onMouseDown={handleRightMouseDown}
              style={{
                width: 5,
                marginRight: -5,
                background: 'transparent',
                cursor: isLocked ? 'default' : 'col-resize',
                zIndex: 10,
                flexShrink: 0,
                transition: 'background 0.2s',
              }}
              onMouseEnter={(e) => { if (!isLocked) e.currentTarget.style.background = 'rgba(240, 100, 40, 0.2)'; }}
              onMouseLeave={(e) => { if (!isDraggingRight.current) e.currentTarget.style.background = 'transparent'; }}
            />
            <div style={{
              width: rightSidebarWidth,
              flexShrink: 0,
              background: '#fff',
              borderLeft: '1px solid #e0e0e0',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'auto'
            }}>
              {rightSidebar}
            </div>
          </>
        )}
      </div>
      )}

      {/* ── Kite Footer — panel show/hide + reset + lock (Kite-specific) ── */}
      <div style={{ height: 30, flexShrink: 0, background: '#fff', borderTop: '1px solid #e0e0e0', display: 'flex', alignItems: 'center', gap: 12, padding: '0 14px' }}>
        <span style={{ fontSize: 10, color: '#9b9b9b', letterSpacing: 0.4 }}>KITE</span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          <MacKiteToggle />
          <span style={{ width: 1, height: 16, background: '#e0e0e0', margin: '0 2px' }} />
          {sidebar && (
            <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} title="Show / hide left sidebar" style={footBtn(isSidebarOpen)}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><line x1="9" y1="3" x2="9" y2="21" />
              </svg>
            </button>
          )}
          {rightSidebar && (
            <button onClick={() => setIsRightSidebarOpen(!isRightSidebarOpen)} title="Show / hide right sidebar" style={footBtn(isRightSidebarOpen)}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><line x1="15" y1="3" x2="15" y2="21" />
              </svg>
            </button>
          )}
          {rightSidebar && (
            <button
              onClick={toggleRightCompact}
              title={isLocked ? 'Unlock to resize panes' : isRightSidebarOpen && rightSidebarWidth === RIGHT_COMPACT ? 'Right pane: back to default width' : 'Right pane: compact (450px)'}
              style={footBtn(isRightSidebarOpen && rightSidebarWidth === RIGHT_COMPACT, isLocked)}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <line x1="14" y1="3" x2="14" y2="21" />
                <rect x="14" y="3" width="7" height="18" fill="currentColor" stroke="none" opacity="0.25" />
              </svg>
            </button>
          )}
          {bottomBar && (
            <button onClick={() => setIsBottomBarOpen(!isBottomBarOpen)} title="Show / hide Kite terminal" style={footBtn(isBottomBarOpen)}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><line x1="3" y1="15" x2="21" y2="15" />
              </svg>
            </button>
          )}
          <span style={{ width: 1, height: 16, background: '#e0e0e0', margin: '0 2px' }} />
          <button onClick={resetLayout} title={macOn ? 'Reset Mac stage layout to default' : isLocked ? 'Unlock to reset panel sizes' : 'Reset panel sizes to defaults'} style={footBtn(false, macOn ? false : isLocked)}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
            </svg>
          </button>
          <button onClick={resetLayout2} title={isLocked ? 'Unlock to reset panel sizes' : 'Reset panel sizes to preset 2'} style={footBtn(false, isLocked)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
              </svg>
              <span style={{ fontSize: '10px', fontWeight: 'bold', lineHeight: 1 }}>2</span>
            </div>
          </button>
          <button onClick={() => setIsLocked(!isLocked)} title={isLocked ? 'Unlock panel sizes' : 'Lock panel sizes'} style={footBtn(isLocked)}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              {isLocked ? <path d="M7 11V7a5 5 0 0 1 10 0v4" /> : <path d="M7 11V7a5 5 0 0 1 9.9-1" />}
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
