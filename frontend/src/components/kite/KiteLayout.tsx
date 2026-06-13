import React from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import { useKiteStatus } from '../../hooks/useKite';

export type NavItem = 'dashboard' | 'orders' | 'holdings' | 'positions' | 'bids' | 'funds' | 'data' | 'connect' | 'mf' | 'alerts';

interface KiteLayoutProps {
  activeNav: NavItem;
  onNavClick: (nav: NavItem) => void;
  sidebar: React.ReactNode;
  content: React.ReactNode;
}

export function KiteLayout({ activeNav, onNavClick, sidebar, content }: KiteLayoutProps) {
  const { data: status } = useKiteStatus();
  
  const navItems: NavItem[] = ['dashboard', 'orders', 'holdings', 'positions', 'bids', 'funds', 'mf', 'alerts', 'data', 'connect'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: t.bg }}>
      {/* ── TOP NAVBAR ── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        height: 56,
        background: t.surface,
        borderBottom: `1px solid ${t.border}`,
        boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
        zIndex: 10
      }}>
        {/* Logo area */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ color: '#FF5722', fontSize: 24, fontWeight: 900, transform: 'scaleX(-1)' }}>◩</div>
          <div style={{ fontSize: 13, fontWeight: 500, color: t.bright, letterSpacing: 1 }}>STERLING KITE</div>
        </div>

        {/* Navigation items */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 24, height: '100%' }}>
          {navItems.map((item) => (
              <div
                key={item}
                onClick={() => onNavClick(item)}
                style={{
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: activeNav === item ? 600 : 400,
                  color: activeNav === item ? '#FF5722' : t.dim,
                  borderBottom: activeNav === item ? '2px solid #FF5722' : '2px solid transparent',
                  textTransform: 'capitalize',
                  transition: 'color 0.2s',
                }}
                onMouseEnter={(e) => {
                  if (activeNav !== item) (e.currentTarget as HTMLElement).style.color = '#FF5722';
                }}
                onMouseLeave={(e) => {
                  if (activeNav !== item) (e.currentTarget as HTMLElement).style.color = t.dim;
                }}
              >
                {item === 'mf' ? 'Mutual Funds' : item}
              </div>
          ))}

          {/* Spacer */}
          <div style={{ width: 16 }} />

          {/* Right side icons/profile */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ color: t.dim, cursor: 'pointer', fontSize: 16 }}>🔔</div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              cursor: 'pointer'
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: 14, background: tint('#FF5722', 20),
                color: '#FF5722', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 600
              }}>
                {status?.user_name ? status.user_name.substring(0, 2).toUpperCase() : 'SK'}
              </div>
              <div style={{ fontSize: 12, color: t.dim }}>
                {status?.user_name ? status.user_name.split(' ')[0] : 'Guest'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── MAIN LAYOUT ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left Sidebar (Watchlist) */}
        <div style={{
          width: 380,
          flexShrink: 0,
          borderRight: `1px solid ${t.border}`,
          background: t.bg,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto'
        }}>
          {sidebar}
        </div>

        {/* Right Content */}
        <div style={{
          flex: 1,
          background: t.bg,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto',
          padding: 24
        }}>
          {content}
        </div>
      </div>
    </div>
  );
}
