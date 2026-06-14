import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useKiteStatus } from '../../hooks/useKite';

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

  const isDragging = useRef(false);
  const isDraggingBottom = useRef(false);

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

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
  }, []);

  const handleBottomMouseDown = useCallback((e: React.MouseEvent) => {
    isDraggingBottom.current = true;
    document.body.style.cursor = 'row-resize';
  }, []);

  const handleMouseUp = useCallback(() => {
    isDragging.current = false;
    isDraggingBottom.current = false;
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
  }, []);

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleMouseMove, handleMouseUp]);

  const navItems: NavItem[] = ['dashboard', 'orders', 'holdings', 'positions', 'bids', 'funds', 'mf', 'alerts', 'data', 'connect'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif' }}>
      <style>{`
        .kite-nav-item { transition: color 0.2s; }
        .kite-nav-item:hover { color: #ff5722 !important; }
        .kite-icon-btn { transition: color 0.2s; }
        .kite-icon-btn:hover { color: #ff5722 !important; }
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
        borderBottom: '1px solid #f1f1f1',
        boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
        zIndex: 10
      }}>
        {/* Logo area */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ color: '#ff5722', fontSize: 24, fontWeight: 900, transform: 'scaleX(-1)' }}>◩</div>
          </div>
          <div style={{ fontSize: 14, fontWeight: 500, color: '#444', letterSpacing: 0.5 }}>STERLING KITE</div>
          {sidebar && (
            <div 
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              style={{ 
                cursor: 'pointer', 
                padding: '4px', 
                color: isSidebarOpen ? '#ff5722' : '#9b9b9b', 
                marginLeft: 16,
                display: 'flex',
                alignItems: 'center',
                background: isSidebarOpen ? 'rgba(255, 87, 34, 0.1)' : 'transparent',
                borderRadius: 4,
                transition: 'background 0.2s, color 0.2s'
              }}
              title="Toggle Left Sidebar"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <line x1="9" y1="3" x2="9" y2="21" />
              </svg>
            </div>
          )}
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
                  color: activeNav === item ? '#ff5722' : '#444',
                  borderBottom: activeNav === item ? '2px solid #ff5722' : '2px solid transparent',
                  textTransform: 'capitalize'
                }}
              >
                {item === 'mf' ? 'Mutual Funds' : item}
              </div>
          ))}

          {/* Spacer */}
          <div style={{ width: 16 }} />

          {/* Right side icons/profile */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {rightSidebar && (
              <div 
                onClick={() => setIsRightSidebarOpen(!isRightSidebarOpen)}
                style={{ 
                  cursor: 'pointer', 
                  padding: '4px', 
                  color: isRightSidebarOpen ? '#ff5722' : '#9b9b9b', 
                  display: 'flex',
                  alignItems: 'center',
                  background: isRightSidebarOpen ? 'rgba(255, 87, 34, 0.1)' : 'transparent',
                  borderRadius: 4,
                  transition: 'background 0.2s, color 0.2s'
                }}
                title="Toggle Right Sidebar"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <line x1="15" y1="3" x2="15" y2="21" />
                </svg>
              </div>
            )}
            {bottomBar && (
              <div
                onClick={() => setIsBottomBarOpen(!isBottomBarOpen)}
                style={{
                  cursor: 'pointer',
                  padding: '4px',
                  color: isBottomBarOpen ? '#ff5722' : '#9b9b9b',
                  display: 'flex',
                  alignItems: 'center',
                  background: isBottomBarOpen ? 'rgba(255, 87, 34, 0.1)' : 'transparent',
                  borderRadius: 4,
                  transition: 'background 0.2s, color 0.2s'
                }}
                title="Toggle Kite Terminal"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <line x1="3" y1="15" x2="21" y2="15" />
                </svg>
              </div>
            )}
            <div className="kite-icon-btn" style={{ color: '#444', cursor: 'pointer', fontSize: 16 }}>🔔</div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              cursor: 'pointer'
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: 14, background: 'rgba(255, 87, 34, 0.1)',
                color: '#ff5722', display: 'flex', alignItems: 'center', justifyContent: 'center',
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

      {/* ── MAIN LAYOUT ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
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
                width: 4,
                background: '#f1f1f1',
                cursor: 'col-resize',
                zIndex: 10,
                flexShrink: 0,
                transition: 'background 0.2s',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#ff5722'}
              onMouseLeave={(e) => {
                if (!isDragging.current) e.currentTarget.style.background = '#f1f1f1';
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
          borderLeft: (sidebar && isSidebarOpen) ? 'none' : '1px solid #f1f1f1'
        }}>
          <div style={{ flex: 1, background: '#fff', overflow: 'auto' }}>
            {content}
          </div>

          {/* ── Bottom Bar (Kite Terminal) — spans only the center column ── */}
          {bottomBar && isBottomBarOpen && (
            <>
              <div
                onMouseDown={handleBottomMouseDown}
                style={{ height: 4, background: '#f1f1f1', cursor: 'row-resize', flexShrink: 0, transition: 'background 0.2s' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#ff5722')}
                onMouseLeave={(e) => { if (!isDraggingBottom.current) e.currentTarget.style.background = '#f1f1f1'; }}
              />
              <div style={{ height: bottomBarHeight, flexShrink: 0, borderTop: '1px solid #f1f1f1', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                {bottomBar}
              </div>
            </>
          )}
        </div>

        {/* Right Sidebar */}
        {rightSidebar && isRightSidebarOpen && (
          <div style={{
            width: 640,
            flexShrink: 0,
            background: '#fff',
            borderLeft: '1px solid #f1f1f1',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'auto'
          }}>
            {rightSidebar}
          </div>
        )}
      </div>
    </div>
  );
}
