import React from 'react';
import { useKiteSettings, type LoaderStyle } from '../../store/useKiteSettings';
import { KiteLoader } from './KiteLoader';

const OPTIONS: Array<{ value: LoaderStyle; label: string; desc: string }> = [
  { value: 'ubuntu', label: 'Ubuntu', desc: 'Crisp, fast and direct' },
  { value: 'mac', label: 'Mac', desc: 'Soft spring and glass' },
  { value: 'material', label: 'Material', desc: 'Clean scale and ripple' },
  { value: 'windows', label: 'Windows', desc: 'Precise fluent motion' },
  { value: 'gnome', label: 'GNOME', desc: 'Calm ease and fade' },
  { value: 'kde', label: 'KDE', desc: 'Snappy desktop feedback' },
  { value: 'minimal', label: 'Minimal', desc: 'Almost instant, no flourish' },
];

export function MotionStyleSettings() {
  const style = useKiteSettings((s) => s.loaderStyle);
  const setStyle = useKiteSettings((s) => s.setLoaderStyle);

  return (
    <section style={{ margin: '0 0 14px', padding: 16, background: '#fff', border: '1px solid #e0e0e0', borderRadius: 6 }}>
      <div style={{ color: '#9b9b9b', fontSize: 11, letterSpacing: 1, marginBottom: 6, fontWeight: 700 }}>
        INTERACTION & LOADER STYLE
      </div>
      <div style={{ color: '#777', fontSize: 11.5, lineHeight: 1.5, marginBottom: 12 }}>
        Controls loaders, startup surfaces, menus, dialogs, buttons and transition timing. Table rows remain stationary for accurate scrolling and pointer targeting.
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(118px, 1fr))', gap: 8 }}>
        {OPTIONS.map((option) => {
          const selected = option.value === style;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={selected}
              onClick={() => setStyle(option.value)}
              style={{
                minHeight: 92,
                padding: '11px 9px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 7,
                cursor: 'pointer',
                fontFamily: 'inherit',
                borderRadius: 6,
                border: `1px solid ${selected ? '#f06428' : '#e0e0e0'}`,
                background: selected ? 'rgba(240,100,40,.055)' : '#fff',
                color: selected ? '#d35400' : '#444',
                boxShadow: selected ? '0 0 0 1px rgba(240,100,40,.08)' : 'none',
              }}
            >
              <span style={{ height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <KiteLoader size={24} styleOverride={option.value} />
              </span>
              <span style={{ fontSize: 12, fontWeight: selected ? 700 : 600 }}>{option.label}</span>
              <span style={{ fontSize: 9.5, color: '#999', lineHeight: 1.25 }}>{option.desc}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export default MotionStyleSettings;
