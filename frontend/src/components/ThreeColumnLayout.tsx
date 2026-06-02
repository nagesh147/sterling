import React from 'react';
import { tint } from '../styles/terminalUI';

/**
 * Shared 3-column layout: left sidebar (220px) | center (1fr) | right sidebar (260px)
 * Sidebars get var(--t-bg2) background with border separators.
 * Center gets var(--t-bg) background.
 * Matches the Copilot-style centered-content aesthetic across all tabs.
 */

type SectionProps = {
  label?: string;
  children?: React.ReactNode;
  border?: boolean;
  collapsible?: boolean;
  defaultOpen?: boolean;
};

function CollapsibleSection({ label, children, border = true, collapsible, defaultOpen = true, side }: SectionProps & { side: 'left' | 'right' }) {
  const [open, setOpen] = React.useState(defaultOpen);
  if (!collapsible) {
    return (
      <div style={{
        padding: '10px 14px',
        borderBottom: border ? '1px solid var(--t-border)' : 'none',
      }}>
        {label && <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: '0.06em', color: 'var(--t-muted)', marginBottom: 8, textTransform: 'uppercase' }}>{label}</div>}
        {children}
      </div>
    );
  }
  return (
    <div style={{ borderBottom: border ? '1px solid var(--t-border)' : 'none' }}>
      <button onClick={() => setOpen((v) => !v)} style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%',
        padding: '10px 14px', background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
      }}>
        <span style={{ fontSize: 9, fontWeight: 600, letterSpacing: '0.06em', color: 'var(--t-muted)', textTransform: 'uppercase' }}>{label}</span>
        <span style={{ fontSize: 8, color: 'var(--t-muted)', transition: 'transform .15s', transform: open ? 'rotate(180deg)' : 'rotate(0deg)', display: 'inline-block' }}>▼</span>
      </button>
      {open && <div style={{ padding: '0 14px 12px' }}>{children}</div>}
    </div>
  );
}

export function LeftSection({ label, children, border = true, collapsible, defaultOpen }: SectionProps) {
  return <CollapsibleSection label={label} children={children} border={border} collapsible={collapsible} defaultOpen={defaultOpen} side="left" />;
}

export function RightSection({ label, children, border = true, collapsible, defaultOpen }: SectionProps) {
  return <CollapsibleSection label={label} children={children} border={border} collapsible={collapsible} defaultOpen={defaultOpen} side="right" />;
}

type NavItem = {
  id: string;
  label: string;
  color: string;
  count?: number;
};

type ThreeColumnLayoutProps = {
  leftNav?: NavItem[];
  activeNav?: string;
  onNavClick?: (id: string) => void;
  leftSidebar?: React.ReactNode;
  centerHeader?: React.ReactNode;
  centerContent: React.ReactNode;
  centerFullBleed?: boolean;  // If true, center content fills the column with no padding
  rightSidebar?: React.ReactNode;
  leftWidth?: number | string;   // override the left sidebar width (default 240px)
  rightWidth?: number | string;  // override the right sidebar width (default 280px)
};

export function ThreeColumnLayout({
  leftNav,
  activeNav,
  onNavClick,
  leftSidebar,
  centerHeader,
  centerContent,
  centerFullBleed,
  rightSidebar,
  leftWidth = 240,
  rightWidth = 280,
}: ThreeColumnLayoutProps) {
  const px = (v: number | string) => (typeof v === 'number' ? `${v}px` : v);
  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'grid', gridTemplateColumns: `${px(leftWidth)} 1fr ${px(rightWidth)}`, gridTemplateRows: 'minmax(0, 1fr)', background: 'var(--t-bg)' }}>
      {/* ── LEFT SIDEBAR ── */}
      <div style={{ background: 'var(--t-bg2)', borderRight: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column', overflow: 'auto', minHeight: 0 }}>
        {leftNav && leftNav.length > 0 && (
          <CollapsibleSection label="Navigation" collapsible defaultOpen side="left">
            {leftNav.map((item) => {
              const active = activeNav === item.id;
              return (
                <button key={item.id} onClick={() => onNavClick?.(item.id)} style={{
                  display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                  padding: '10px 12px', borderRadius: 8, cursor: 'pointer', fontFamily: 'inherit',
                  background: active ? `var(--t-bg)` : 'transparent',
                  border: active ? `1px solid var(--t-border)` : '1px solid transparent',
                  color: active ? item.color : 'var(--t-dim)',
                  marginBottom: 4, transition: 'all .2s ease',
                  transform: active ? 'translateX(2px)' : 'none'
                }}>
                  <div style={{ width: 8, height: 8, borderRadius: 4, background: item.color, flexShrink: 0, opacity: active ? 1 : 0.4 }} />
                  <span style={{ fontSize: 12, fontWeight: active ? 800 : 500, letterSpacing: '0.02em' }}>{item.label}</span>
                  {item.count != null && <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 800, opacity: 0.8 }}>{item.count}</span>}
                </button>
              );
            })}
          </CollapsibleSection>
        )}
        {leftSidebar}
      </div>

      {/* ── CENTER COLUMN ── (header fixed, only the content area scrolls) */}
      <div style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', minHeight: 0, minWidth: 0 }}>
        {centerHeader && (
          <div style={{
            padding: '16px 24px', borderBottom: '1px solid var(--t-border)',
            background: 'var(--t-bg)',
            display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
          }}>
            {centerHeader}
          </div>
        )}
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: centerFullBleed ? 0 : '16px 20px', display: 'flex', flexDirection: 'column', gap: centerFullBleed ? 0 : 8 }}>
          {centerContent}
        </div>
      </div>

      {/* ── RIGHT SIDEBAR ── */}
      <div style={{ background: 'var(--t-bg2)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column', overflow: 'auto', minHeight: 0 }}>
        {rightSidebar}
      </div>
    </div>
  );
}

/** Stat card for sidebar use — optionally clickable with a highlighted active state. */
export function StatCard({ label, value, color, active, onClick }: {
  label: string; value: string | number; color?: string; active?: boolean; onClick?: () => void;
}) {
  const accent = color || 'var(--t-blue)';
  return (
    <div
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      style={{
        background: active ? tint(accent, 8) : 'var(--t-bg)',
        border: `1px solid ${active ? tint(accent, 60) : 'var(--t-border)'}`,
        borderRadius: 6, padding: '8px 10px',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'border-color .12s, background .12s',
      }}
    >
      <div style={{ fontSize: 9, letterSpacing: '0.08em', color: active ? accent : 'var(--t-dim)', fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 800, color: color || 'var(--t-bright)', lineHeight: 1.1 }}>{value}</div>
    </div>
  );
}

export default ThreeColumnLayout;